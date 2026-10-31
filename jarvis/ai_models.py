"""KI-Modellverwaltung mit Erlaubnisliste (Version 5, Phase A).

Grundsatz: Alles ist GESPERRT, was nicht ausdrücklich erlaubt ist.

Wer darf arbeiten?
  1. Das eingebaute Testmodell `mock` (Klasse MockLLM, genau diese Klasse, keine Unterklasse).
     Es läuft offline und kostenlos. Deshalb braucht es keine Datenschutzprüfung.
  2. Test-Doubles in den automatischen Tests, wenn sie im Test AUSDRÜCKLICH zugelassen werden
     (allow_test_double). Das geht nur für Klassen aus dem Ordner tests/ und wird protokolliert.
  3. Jedes andere Modell gilt als EXTERN, egal was es über sich selbst behauptet. Es darf nur arbeiten, wenn
     ALLE Bedingungen erfüllt sind:
       - es steht in config/jarvis.json unter ai.models,
       - dort steht "approved": true (deine ausdrückliche Freigabe),
       - "privacy_reviewed_on" enthält das Datum deiner Datenschutzprüfung (nicht älter als 180 Tage),
       - privacy.external_ai_allowed ist true,
       - der API-Schlüssel liegt in der Umgebungsvariable bzw. .env, die "key_env" nennt
         (NIE in der Konfiguration oder im Programmcode),
       - jede Anfrage läuft durch die Datenschutz-Schranke (outbound.py), die sensible Daten entfernt.
     Fehlt auch nur eine Angabe oder ist sie ungültig, wird blockiert.

Jeder Zugriffsversuch wird protokolliert: Modellname, Aufgabe, Entscheidung, Grund, Textlänge.
Niemals Inhalte, niemals Schlüssel.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass

from .outbound import ExternalAIBlocked

MODEL_NAME = re.compile(r"[a-z0-9][a-z0-9._:/-]{0,63}")
KEY_ENV_NAME = re.compile(r"JARVIS_[A-Z0-9_]{2,60}")
REVIEW_VALID_DAYS = 180
TASKS = {"chat", "idea", "post", "research", "briefing", "skill"}

# Feldnamen, die in einer Modell-Konfiguration NIE vorkommen dürfen: Schlüssel gehören in die .env
FORBIDDEN_FIELDS = re.compile(r"(?i)(api[_-]?key|secret|token|passwor|password|bearer|credential)")
# Werte, die wie echte Schlüssel aussehen
KEY_LIKE_VALUE = re.compile(r"(?i)\b(sk|pk|rk|sess|ghp|gho|xox[abp])[-_][A-Za-z0-9_-]{12,}|\bAKIA[0-9A-Z]{16}\b|"
                            r"\b[A-Za-z0-9_-]{40,}\b")
ALLOWED_FIELDS = {"kind", "provider", "approved", "privacy_reviewed_on", "privacy_note", "key_env",
                  "cost_per_call_eur", "tasks", "description"}


class ModelBlocked(ExternalAIBlocked):
    """Ein KI-Modell darf (noch) nicht arbeiten. Es wurden keine Daten gesendet und keine Kosten verbucht."""


class AIConfigError(ValueError):
    """Die KI-Konfiguration enthält etwas Gefährliches (z. B. einen Schlüssel). JARVIS startet dann nicht."""


@dataclass(frozen=True)
class Decision:
    model: str
    kind: str                 # "test" oder "extern"
    cost_eur: float
    key_env: str = ""


def find_secrets_in_ai_config(ai: object) -> list:
    """NUR LESEN: Fundstellen von Schlüsseln in der KI-Konfiguration (ohne den Wert zu nennen)."""
    found = []

    def walk(value, path):
        if isinstance(value, dict):
            for k, v in value.items():
                key = str(k)
                if FORBIDDEN_FIELDS.search(key) and key != "key_env":
                    found.append(f"{path}.{key}")
                walk(v, f"{path}.{key}")
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, f"{path}[{i}]")
        elif isinstance(value, str) and KEY_LIKE_VALUE.search(value) and not KEY_ENV_NAME.fullmatch(value):
            found.append(path)
    walk(ai, "ai")
    return sorted(set(found))


def validate_ai_config(cfg: dict) -> None:
    """Wird beim Laden der Konfiguration aufgerufen. Bricht ab, wenn ein Schlüssel in der Datei steht."""
    places = find_secrets_in_ai_config(cfg.get("ai", {}))
    if places:
        raise AIConfigError("In config/jarvis.json steht vermutlich ein API-Schlüssel (" + ", ".join(places) + "). "
                            "Schlüssel gehören NUR in die Datei .env (Rechte 600). Bitte dort eintragen, in der "
                            "Konfiguration nur den Namen der Variable unter \"key_env\" angeben, z. B. "
                            "\"JARVIS_OPENROUTER_KEY\".")


def _safe_name(model) -> str:
    """Modellname fürs Protokoll: nur wenn er dem erlaubten Muster entspricht, sonst ein Platzhalter."""
    name = getattr(model, "name", None)
    if isinstance(name, str) and MODEL_NAME.fullmatch(name):
        return name
    return "(ungültiger Name)"


class ModelPolicy:
    """Entscheidet bei JEDEM Aufruf neu, ob ein Modell arbeiten darf."""

    def __init__(self, cfg: dict | None = None, audit=None, secrets: dict | None = None,
                 today=None):
        cfg = cfg or {}
        self.audit = audit
        self._secrets = dict(secrets or {})
        self._today = today or dt.date.today
        privacy = cfg.get("privacy") or {}
        self.external_allowed = privacy.get("external_ai_allowed") is True      # nur echtes true zählt
        ai = cfg.get("ai") or {}
        models = ai.get("models") if isinstance(ai, dict) else None
        self.models = models if isinstance(models, dict) else {}
        self._test_doubles = set()

    # ------------------------------------------------------------------ Test-Doubles
    def allow_test_double(self, model) -> None:
        """NUR für automatische Tests: ein Ersatzmodell aus dem Ordner tests/ ausdrücklich zulassen."""
        module = type(model).__module__ or ""
        if not (module == "tests" or module.startswith("tests.")):
            raise ModelBlocked("Ersatzmodelle sind nur in den automatischen Tests erlaubt.")
        if getattr(model, "is_external", False):
            raise ModelBlocked("Ein als extern gekennzeichnetes Modell kann nicht als Testmodell zugelassen werden.")
        self._test_doubles.add(id(model))
        self._log("ai_test_double_allowed", model=_safe_name(model), klasse=type(model).__name__)

    # ------------------------------------------------------------------ Prüfung
    def authorize(self, model, task: str, chars: int = 0) -> Decision:
        name = _safe_name(model)
        try:
            decision = self._decide(model, task)
        except ModelBlocked as exc:
            self._log("external_ai_blocked", model=name, task=str(task)[:20], reason=str(exc)[:200], chars=chars)
            raise
        self._log("ai_access", model=name, task=str(task)[:20], kind=decision.kind, decision="erlaubt", chars=chars)
        return decision

    def _decide(self, model, task: str) -> Decision:
        from .llm import MockLLM          # spät importieren (llm importiert dieses Modul)
        if task not in TASKS:
            raise ModelBlocked(f"Unbekannte Aufgabe '{str(task)[:20]}' – KI-Aufruf gesperrt.")
        if type(model) is MockLLM and getattr(model, "name", None) == "mock":
            return Decision("mock", "test", 0.0)
        if id(model) in self._test_doubles and not getattr(model, "is_external", False):
            return Decision(_safe_name(model), "test", float(getattr(model, "cost_per_call_eur", 0.0) or 0.0))
        name = getattr(model, "name", None)
        if not isinstance(name, str) or not MODEL_NAME.fullmatch(name):
            raise ModelBlocked("KI-Modell mit ungültigem Namen ist nicht freigegeben. Es wurden keine Daten gesendet.")
        entry = self.models.get(name)
        if not isinstance(entry, dict):
            raise ModelBlocked(f"KI-Modell '{name}' ist nicht freigegeben (steht nicht in der Erlaubnisliste "
                               f"ai.models). Es wurden keine Daten gesendet.")
        return self._check_entry(name, entry, task)

    def _check_entry(self, name: str, entry: dict, task: str) -> Decision:
        unknown = sorted(set(entry) - ALLOWED_FIELDS)
        if unknown:
            raise ModelBlocked(f"KI-Modell '{name}': unbekannte Angaben {unknown} – zur Sicherheit gesperrt.")
        if entry.get("kind") != "external":
            raise ModelBlocked(f"KI-Modell '{name}': \"kind\" muss \"external\" sein. Nur das eingebaute "
                               f"Testmodell arbeitet ohne Datenschutzprüfung.")
        if entry.get("approved") is not True:
            raise ModelBlocked(f"KI-Modell '{name}' ist nicht freigegeben (\"approved\" fehlt oder ist nicht true).")
        reviewed = entry.get("privacy_reviewed_on")
        try:
            day = dt.date.fromisoformat(str(reviewed))
        except ValueError:
            raise ModelBlocked(f"KI-Modell '{name}': Datenschutzprüfung fehlt (privacy_reviewed_on, "
                               f"Format JJJJ-MM-TT).") from None
        today = self._today()
        if day > today:
            raise ModelBlocked(f"KI-Modell '{name}': Datum der Datenschutzprüfung liegt in der Zukunft.")
        if (today - day).days > REVIEW_VALID_DAYS:
            raise ModelBlocked(f"KI-Modell '{name}': Datenschutzprüfung ist älter als {REVIEW_VALID_DAYS} Tage. "
                               f"Bitte erneut prüfen.")
        tasks = entry.get("tasks")
        if tasks is not None and (not isinstance(tasks, list) or task not in tasks):
            raise ModelBlocked(f"KI-Modell '{name}' ist für die Aufgabe '{task}' nicht freigegeben.")
        cost = entry.get("cost_per_call_eur")
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not 0 < cost <= 1:
            raise ModelBlocked(f"KI-Modell '{name}': Kosten pro Anfrage fehlen (cost_per_call_eur, größer 0 "
                               f"und höchstens 1 €). Ohne Angabe kann die Kostenbremse nicht greifen.")
        key_env = entry.get("key_env")
        if not isinstance(key_env, str) or not KEY_ENV_NAME.fullmatch(key_env):
            raise ModelBlocked(f"KI-Modell '{name}': \"key_env\" muss der NAME einer Variable sein, "
                               f"die mit JARVIS_ beginnt (z. B. JARVIS_OPENROUTER_KEY).")
        if not self.has_key(key_env):
            raise ModelBlocked(f"KI-Modell '{name}': Schlüssel {key_env} ist nicht in .env bzw. der Umgebung gesetzt.")
        if not self.external_allowed:
            raise ModelBlocked("Externe KI ist nicht freigegeben (privacy.external_ai_allowed = false). "
                               "Es wurden keine Daten gesendet.")
        return Decision(name, "extern", float(cost), key_env)

    # ------------------------------------------------------------------ Schlüssel
    def has_key(self, key_env: str) -> bool:
        return bool(self._secrets.get(key_env) or os.environ.get(key_env))

    def api_key(self, decision: Decision) -> str:
        """Schlüssel NUR für eine gerade erteilte externe Freigabe. Wird nie protokolliert oder angezeigt."""
        if decision.kind != "extern" or not decision.key_env:
            raise ModelBlocked("Kein Schlüssel für dieses Modell.")
        key = self._secrets.get(decision.key_env) or os.environ.get(decision.key_env) or ""
        if not key:
            raise ModelBlocked("Schlüssel fehlt.")
        return key

    # ------------------------------------------------------------------ Übersicht
    def overview(self) -> list:
        """NUR LESEN: Zustand aller Modelle für `python3 -m jarvis ki-status` und den Sicherheitscheck."""
        rows = [("mock", "Testmodell (eingebaut)", "erlaubt", "offline, kostenlos, keine Daten verlassen den Rechner")]
        for name, entry in sorted(self.models.items()):
            if not isinstance(entry, dict):
                rows.append((str(name)[:64], "ungültig", "gesperrt", "Eintrag ist kein Objekt {…}"))
                continue
            try:
                if not MODEL_NAME.fullmatch(str(name)):
                    raise ModelBlocked("ungültiger Modellname")
                self._check_entry(str(name), entry, (entry.get("tasks") or ["chat"])[0]
                                  if isinstance(entry.get("tasks"), list) and entry.get("tasks") else "chat")
                rows.append((name, "extern", "erlaubt", "Freigabe, Datenschutzprüfung und Schlüssel vorhanden"))
            except ModelBlocked as exc:
                rows.append((str(name)[:64], "extern", "gesperrt", str(exc)))
        return rows

    def _log(self, event: str, **details) -> None:
        if self.audit is not None:
            self.audit.write(event, **details)


class NotConnectedModel:
    """Platzhalter für ein konfiguriertes, aber noch nicht programmiertes Modell. Antwortet nie."""
    is_test_mode = False
    cost_per_call_eur = 0.0

    def __init__(self, name: str):
        self.name = name

    def _refuse(self, *_a, **_k):
        raise ModelBlocked(f"Für das Modell '{self.name}' gibt es noch keine Anbindung. Es wurde nichts gesendet.")

    chat = _refuse
    complete = _refuse


def make_model(cfg: dict):
    """Erzeugt das in ai.active_model eingestellte Modell. Fehlt die Angabe: Testmodell."""
    from .llm import MockLLM
    ai = cfg.get("ai") or {}
    name = ai.get("active_model", "mock") if isinstance(ai, dict) else "mock"
    if name in (None, "", "mock"):
        return MockLLM()
    return NotConnectedModel(str(name)[:64])
