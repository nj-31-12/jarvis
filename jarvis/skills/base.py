"""Grundbausteine des Skill-Systems: Berechtigungen, Skill-Beschreibung, Zustand und Ausführung."""
from __future__ import annotations

import collections
import json
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .. import policy
from ..db import LockedDB

# Alle Berechtigungen, die es gibt. Kennung → (Beschreibung, Risiko)
PERMISSIONS = {
    "internet.read": ("Öffentliche Informationen suchen und lesen", "niedrig"),
    "mail.read": ("E-Mails lesen (Betreff, Absender, Text)", "hoch"),
    "mail.draft": ("Antwort-Entwürfe erstellen – nichts wird gesendet", "mittel"),
    "mail.send.propose": ("E-Mail-Versand vorschlagen – nur nach deiner Freigabe", "hoch"),
    "calendar.read": ("Termine lesen", "mittel"),
    "calendar.write.propose": ("Termin eintragen vorschlagen – nur nach deiner Freigabe", "hoch"),
    "shop.read": ("Produkte und Bestellungen im Shop lesen", "mittel"),
    "shop.write.propose": ("Produktänderung vorschlagen – nur nach deiner Freigabe", "hoch"),
    "vault.read": ("Nicht vertrauliche Obsidian-Notizen lesen", "niedrig"),
    "vault.inbox.write": ("Neue Notizen nur in 00_Inbox/JARVIS anlegen", "niedrig"),
    "briefing.compose": ("Tagesbriefing aus freigegebenen Skills zusammenstellen", "niedrig"),
}
SKILL_ID = re.compile(r"[a-z][a-z0-9_]{1,30}")
OPERATION_KINDS = ("lesen", "entwurf", "vorschlag")
MAX_PARAM_CHARS = 2000
RUNS_PER_MINUTE = 30


class SkillError(RuntimeError):
    """Verständliche Fehlermeldung eines Skills. Es wurde nichts nach außen gesendet."""


class SkillBlocked(PermissionError):
    """Skill oder Operation ist nicht erlaubt (aus, fehlende Berechtigung, Notaus, Sicherheitsprüfung)."""


@dataclass(frozen=True)
class Operation:
    permission: str
    kind: str                       # lesen · entwurf · vorschlag
    description: str
    params: tuple = ()              # erlaubte Parameter (alles andere wird abgelehnt)


@dataclass(frozen=True)
class SkillSpec:
    id: str
    name: str
    description: str
    operations: dict                # Name → Operation
    adapter_factory: Callable       # erzeugt den (Test-)Adapter; bekommt den Kontext
    proposes: tuple = ()            # Aktionstypen, die dieser Skill vorschlagen darf
    notes: str = ""

    @property
    def permissions(self) -> list:
        return sorted({op.permission for op in self.operations.values()})


@dataclass
class SkillResult:
    skill: str
    operation: str
    text: str
    data: list = field(default_factory=list)
    proposal_id: str | None = None
    test_data: bool = True


class SkillState:
    """Ein/Aus und erteilte Berechtigungen je Skill (data/skills.db). Fehlt ein Eintrag: AUS."""

    def __init__(self, db_path: str | Path, audit=None):
        self.db = LockedDB(db_path)
        self.audit = audit
        self.db.execute("""CREATE TABLE IF NOT EXISTS skill_state (
            skill TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0, permissions TEXT NOT NULL DEFAULT '[]',
            changed REAL, via TEXT)""")

    def get(self, skill: str) -> tuple:
        row = self.db.execute("SELECT enabled, permissions FROM skill_state WHERE skill=?", (skill,)).fetchone()
        if not row:
            return False, set()
        try:
            perms = set(json.loads(row[1]))
        except ValueError:
            perms = set()          # beschädigt → sicherheitshalber keine Berechtigungen
        return bool(row[0]), perms

    def _write(self, skill: str, enabled: bool, perms: set, via: str) -> None:
        # Bewusst ohne „UPSERT“ (braucht SQLite ≥ 3.24): so auch mit älterem SQLite auf macOS Catalina
        values = (int(enabled), json.dumps(sorted(perms)), time.time(), via, skill)
        with self.db.transaction():
            cur = self.db.execute("UPDATE skill_state SET enabled=?, permissions=?, changed=?, via=? WHERE skill=?",
                                  values)
            if cur.rowcount == 0:
                self.db.execute("INSERT INTO skill_state (enabled, permissions, changed, via, skill) VALUES (?,?,?,?,?)",
                                values)
        if self.audit:
            self.audit.write("skill_state", skill=skill, state="an" if enabled else "aus",
                             permissions=sorted(perms), source=via)

    def enable(self, skill: str, perms: set, via: str) -> None:
        with self.db.lock:
            self._write(skill, True, set(perms), via)

    def grant(self, skill: str, perms: set, via: str) -> None:
        with self.db.lock:
            enabled, current = self.get(skill)
            self._write(skill, enabled, current | set(perms), via)

    def disable(self, skill: str, via: str) -> None:
        """Ausschalten entzieht auch alle Berechtigungen. Erneutes Einschalten braucht eine neue Freigabe."""
        with self.db.lock:
            self._write(skill, False, set(), via)

    def close(self) -> None:
        self.db.close()


class SkillRunner:
    """Führt Skill-Operationen aus – immer mit denselben Prüfungen in derselben Reihenfolge:
    Notaus → Skill bekannt → Operation bekannt → Skill an → Berechtigung erteilt → Parameter geprüft
    → Ratenbegrenzung → Adapter. Fehler werden protokolliert (nur Art, nie Inhalte)."""

    def __init__(self, catalog: dict, state: SkillState, context, audit, kill, clock=time.time):
        self.catalog = catalog
        self.state = state
        self.ctx = context
        self.audit = audit
        self.kill = kill
        self.clock = clock
        self._runs = collections.defaultdict(collections.deque)
        self._lock = threading.Lock()
        self._adapters = {}

    # ------------------------------------------------------------------ Sicherheitsprüfung je Skill
    def security_check(self, skill_id: str) -> list:
        """NUR LESEN. Liefert Befunde (Stufe, Text). Ein ⛔-Befund sperrt den Skill."""
        spec = self.catalog.get(skill_id)
        if spec is None:
            return [("fehler", "Unbekannter Skill.")]
        out = []
        unknown = [p for p in spec.permissions if p not in PERMISSIONS]
        if unknown:
            out.append(("fehler", f"Unbekannte Berechtigungen: {unknown}"))
        for name, op in spec.operations.items():
            if op.kind not in OPERATION_KINDS:
                out.append(("fehler", f"Operation {name}: unbekannte Art '{op.kind}'."))
            if op.kind == "vorschlag" and not op.permission.endswith(".propose"):
                out.append(("fehler", f"Operation {name}: Vorschläge brauchen eine *.propose-Berechtigung."))
        for action_type in spec.proposes:
            if policy.classify(action_type) != policy.APPROVAL:
                out.append(("fehler", f"Aktion {action_type} ist nicht freigabepflichtig oder gesperrt."))
        adapter = self._adapter(spec)
        if getattr(adapter, "connects_account", True):
            out.append(("fehler", "Adapter verbindet ein echtes Konto – das ist noch nicht freigegeben."))
        if getattr(adapter, "uses_network", True):
            out.append(("fehler", "Adapter würde das Netzwerk benutzen."))
        enabled, perms = self.state.get(skill_id)
        extra = perms - set(spec.permissions)
        if extra:
            out.append(("fehler", f"Erteilte Berechtigungen, die der Skill gar nicht braucht: {sorted(extra)}"))
        if not out:
            out.append(("ok", "Keine Kontoverbindung, kein Netzwerk, Berechtigungen vollständig beschrieben."))
        return out

    def _adapter(self, spec: SkillSpec):
        if spec.id not in self._adapters:
            self._adapters[spec.id] = spec.adapter_factory(self.ctx)
        return self._adapters[spec.id]

    # ------------------------------------------------------------------ Übersicht
    def overview(self) -> list:
        rows = []
        for spec in self.catalog.values():
            enabled, perms = self.state.get(spec.id)
            blocked = any(level == "fehler" for level, _ in self.security_check(spec.id))
            rows.append({"spec": spec, "enabled": enabled, "granted": sorted(perms),
                         "missing": sorted(set(spec.permissions) - perms), "blocked": blocked})
        return rows

    def is_enabled(self, skill_id: str) -> bool:
        return self.state.get(skill_id)[0]

    # ------------------------------------------------------------------ Ausführen
    def run(self, skill_id: str, operation: str, **params) -> SkillResult:
        try:
            spec, op = self._admit(skill_id, operation, params)
        except SkillBlocked as exc:
            self.audit.write("skill_blocked", skill=str(skill_id)[:32], operation=str(operation)[:32],
                             reason=str(exc)[:200])
            raise
        try:
            result = getattr(self._adapter(spec), operation)(**params)
        except SkillError as exc:
            self.audit.write("skill_failed", skill=spec.id, operation=operation, error=str(exc)[:200])
            raise
        except (SkillBlocked, policy.PolicyViolation) as exc:
            self.audit.write("skill_blocked", skill=spec.id, operation=operation, reason=str(exc)[:200])
            raise
        except Exception as exc:  # noqa: BLE001 – Adapterfehler werden zu einer verständlichen Meldung
            self.audit.write("skill_failed", skill=spec.id, operation=operation, error=type(exc).__name__)
            raise SkillError(f"Der Skill „{spec.name}“ hatte einen Fehler. Es wurde nichts gesendet oder "
                             f"verändert.") from exc
        if not isinstance(result, SkillResult):
            self.audit.write("skill_failed", skill=spec.id, operation=operation, error="ungültiges Ergebnis")
            raise SkillError(f"Der Skill „{spec.name}“ lieferte ein ungültiges Ergebnis.")
        if result.proposal_id and op.kind != "vorschlag":
            raise SkillError("Nur Vorschlags-Operationen dürfen Aktionen anlegen.")
        self.audit.write("skill_run", skill=spec.id, operation=operation, kind=op.kind,
                         proposal=result.proposal_id, items=len(result.data))
        return result

    def _admit(self, skill_id: str, operation: str, params: dict) -> tuple:
        self.kill.check()
        spec = self.catalog.get(skill_id)
        if spec is None:
            raise SkillBlocked("Unbekannter Skill.")
        op = spec.operations.get(operation)
        if op is None:
            raise SkillBlocked(f"Der Skill „{spec.name}“ kennt die Operation '{str(operation)[:32]}' nicht.")
        enabled, perms = self.state.get(skill_id)
        if not enabled:
            raise SkillBlocked(f"Der Skill „{spec.name}“ ist ausgeschaltet. Einschalten über die Freigabezentrale.")
        if op.permission not in perms:
            raise SkillBlocked(f"Dem Skill „{spec.name}“ fehlt die Berechtigung {op.permission}.")
        if any(level == "fehler" for level, _ in self.security_check(skill_id)):
            raise SkillBlocked(f"Der Skill „{spec.name}“ hat die Sicherheitsprüfung nicht bestanden.")
        unknown = set(params) - set(op.params)
        if unknown:
            raise SkillBlocked(f"Unbekannte Angaben: {sorted(unknown)}")
        for k, v in params.items():
            if not isinstance(v, (str, int, float)) or isinstance(v, bool) or len(str(v)) > MAX_PARAM_CHARS:
                raise SkillBlocked(f"Angabe '{k}' ist ungültig oder zu lang.")
        with self._lock:
            q, now = self._runs[skill_id], self.clock()
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= RUNS_PER_MINUTE:
                raise SkillBlocked("Zu viele Aufrufe in kurzer Zeit. Bitte eine Minute warten.")
            q.append(now)
        return spec, op

    # ------------------------------------------------------------------ Aktivierung über die Freigabezentrale
    def request_enable(self, skill_id: str, gate) -> object:
        """Legt eine Freigabe-Anfrage an. Der Skill bleibt AUS, bis du genehmigst."""
        spec = self.catalog.get(skill_id)
        if spec is None:
            raise SkillBlocked("Unbekannter Skill.")
        if any(level == "fehler" for level, _ in self.security_check(skill_id)):
            raise SkillBlocked("Sicherheitsprüfung nicht bestanden – Aktivierung nicht möglich.")
        perms = spec.permissions
        return gate.propose("enable_skill", {"skill": spec.id, "berechtigungen": perms, "adapter": "test"},
                            reason=f"Skill „{spec.name}“ einschalten",
                            meta={"beschreibung": f"Skill „{spec.name}“ mit Testadapter einschalten.",
                                  "konten": ["keine – Testadapter mit erfundenen Daten, keine Kontoverbindung"],
                                  "daten": [f"{p}: {PERMISSIONS[p][0]}" for p in perms],
                                  "kosten_eur": 0, "kosten_hinweis": "Testadapter, keine Kosten",
                                  "quelle": "Skill-Verwaltung"})

    def handle_enable(self, payload: dict) -> str:
        """Ausführer für die genehmigte Aktion enable_skill. Prüft den Inhalt nochmals streng."""
        spec, perms = self._check_payload(payload)
        if payload.get("adapter") != "test":
            raise SkillBlocked("Nur Testadapter sind freigegeben.")
        self.state.enable(spec.id, perms, via="Freigabezentrale")
        return f"Skill „{spec.name}“ eingeschaltet (Testadapter)."

    def handle_grant(self, payload: dict) -> str:
        spec, perms = self._check_payload(payload)
        self.state.grant(spec.id, perms, via="Freigabezentrale")
        return f"Berechtigungen für „{spec.name}“ erweitert: {', '.join(sorted(perms))}."

    def _check_payload(self, payload: dict) -> tuple:
        spec = self.catalog.get(str(payload.get("skill", "")))
        if spec is None:
            raise SkillBlocked("Unbekannter Skill.")
        perms = payload.get("berechtigungen")
        if not isinstance(perms, list) or not perms or not set(perms) <= set(spec.permissions):
            raise SkillBlocked("Angeforderte Berechtigungen passen nicht zum Skill.")
        return spec, set(perms)

    def disable(self, skill_id: str, via: str) -> None:
        if skill_id not in self.catalog:
            raise SkillBlocked("Unbekannter Skill.")
        self.state.disable(skill_id, via)
