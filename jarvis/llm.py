"""Sprachmodell-Anbindung.

Phase 1 nutzt ein SIMULIERTES Modell (MockLLM): kostenlos, offline, vorhersagbar.
Später übernimmt Hermes die echten Modelle (z. B. über OpenRouter). Jeder Aufruf
läuft durch Kostenbremse und Notabschaltung.
"""
from __future__ import annotations

import re

from .budget import BudgetGuard
from .killswitch import KillSwitch


class MockLLM:
    """Simuliertes Modell. Kostenlos, offline, vorhersagbar – und klar als TESTMODUS gekennzeichnet."""
    name = "mock"
    cost_per_call_eur = 0.0
    is_test_mode = True

    def chat(self, system_prompt: str, history: list, text: str) -> str:
        from .chat import detect_areas  # spät importieren, um Kreisbezüge zu vermeiden
        areas = detect_areas(text, _areas_from_prompt(system_prompt))
        turns = sum(1 for m in history if m.get("role") == "du") + 1
        lines = ["**Testmodus**: Ich antworte noch ohne echte KI. Meine Persönlichkeit ist geladen, "
                 "mein Denkvermögen kommt mit dem KI-Zugang.", ""]
        snippet = text if len(text) <= 160 else text[:157] + "…"
        lines.append(f"Deine Nachricht ist angekommen: „{snippet}“")
        if areas:
            lines.append("")
            lines.append("Erkannte Geschäftsbereiche: " + ", ".join(f"**{a}**" for a in areas) + ".")
        knowledge = _sources_from_prompt(system_prompt)
        if knowledge:
            lines += ["", "Dazu habe ich in deinem Wissen gefunden (siehe Quellen unten):"]
            lines += [f"- **{title}**: {excerpt}" for title, excerpt in knowledge]
        lines += ["", "Mit echter KI würde ich hier:",
                  "1. deine Frage einordnen und Zusammenhänge zu deinen anderen Bereichen zeigen,",
                  "2. Fakten, Schätzungen und Rechenbeispiele klar trennen,",
                  "3. mit höchstens drei konkreten nächsten Schritten schließen.", ""]
        if turns == 1:
            lines.append("Was schon richtig funktioniert: `/idee`, `/notiz`, `/suche`, `/status`. Probier `/hilfe`.")
        else:
            lines.append(f"Das ist deine {turns}. Nachricht in diesem Gespräch. Der Verlauf wird gespeichert.")
        return "\n".join(lines)

    def complete(self, task: str, text: str) -> str:
        if task == "idea":
            return _idea_analysis(text)
        if task == "post":
            return _post_draft(text)
        if task == "research":
            return (f"(Simulierte Nachtrecherche zu: {text})\n\n"
                    "- 3 Trends, die beobachtet werden sollten\n"
                    "- 2 mögliche Geschäftschancen\n"
                    "- 1 Risiko\n\n"
                    "Hinweis: In Phase 2 ersetzt Hermes dies durch echte Websuche mit Quellenangaben.")
        return (f"Verstanden: „{text}“.\n"
                "Ich würde das gern gründlich durchdenken, nur bin ich im Moment noch ein Simulator. "
                "Zuverlässig, aber nicht übermäßig gesprächig.\n"
                "(Echte KI-Antworten kommen in Phase 3 über Hermes, nach deiner Freigabe der API-Kosten.)")


def _idea_analysis(idea: str) -> str:
    return f"""## Idee
{idea}

## Bewertungsraster (je 1–5, bitte ergänzen/prüfen)
| Kriterium | Punkte | Begründung |
|---|---|---|
| Startkosten (5 = sehr niedrig) | ? | |
| Zeitaufwand neben der Ausbildung | ? | |
| Passt zu deinen Fähigkeiten (Fitness, Shopify, Social Media) | ? | |
| Nachfrage / Suchvolumen | ? | |
| Wettbewerb (5 = wenig) | ? | |
| Skalierbarkeit / Automatisierbarkeit | ? | |

## Umsatzpotenzial (Beispielrechnung)
Umsatz/Monat = Besucher × Conversion-Rate × Ø-Warenkorb
z. B. 2.000 × 1,5 % × 35 € = **1.050 €** Umsatz (vor Kosten, Steuern, Werbung).

## Nächste kleine Tests (unter 20 €)
1. Zielgruppe in 3 Sätzen beschreiben.
2. 5 Konkurrenten notieren, Preise vergleichen.
3. Einen Testpost/Landingpage-Entwurf erstellen und Reaktionen messen.

## Risiken
- Rechtliches (Impressum, Gewerbeanmeldung, Werbekennzeichnung) prüfen.
- Vereinbarkeit mit dem Ausbildungsvertrag (Nebentätigkeit) klären.

_(Simulierte Analyse – in Phase 2 mit echter KI und Zweitmeinung von ChatGPT.)_"""


def _post_draft(topic: str) -> str:
    return (f"🔥 {topic}\n\n"
            "3 Fakten, die dir keiner sagt:\n1️⃣ …\n2️⃣ …\n3️⃣ …\n\n"
            "Speichere den Post für später 💾 und folge für mehr!\n"
            "#fitness #motivation #ecommerce")


def _areas_from_prompt(system_prompt: str) -> list:
    """Liest die Geschäftsbereiche aus der Systemanweisung (Abschnitt mit Aufzählung)."""
    areas, inside = [], False
    for line in system_prompt.splitlines():
        if line.startswith("## Geschäftsbereiche"):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside and line.startswith("- "):
            areas.append(line[2:].strip())
    return areas


def _sources_from_prompt(system_prompt: str) -> list:
    """Testmodus: zeigt, welche Notizen als Wissen mitgegeben wurden (Titel + erster Satz)."""
    found, title, buf, inside = [], None, [], False
    for line in system_prompt.splitlines():
        if line.startswith("### Quelle: "):
            title = line[len("### Quelle: "):].rsplit(" (", 1)[0]
        elif re.fullmatch(r"<<<NOTIZ-[0-9a-f]+", line):     # Rahmen mit Zufallsmarke (Version 4.2)
            inside, buf = True, []
        elif inside and re.fullmatch(r"NOTIZ-[0-9a-f]+>>>", line):
            inside = False
            from .knowledge import plain_text
            first = plain_text("\n".join(l for l in buf if not l.startswith("#")))[:140]
            found.append((title or "Notiz", first + ("…" if len(first) == 140 else "")))
        elif inside:
            buf.append(line)
    return found


class LLMRouter:
    """Reihenfolge bei JEDEM Aufruf (Version 5):
    Notaus → Erlaubnisliste (ai_models.ModelPolicy) → Datenschutz-Schranke (alle Nicht-Testmodelle)
    → Kostenbremse → Modell.

    Seit Version 5 zählt NICHT mehr, was ein Modell über sich selbst behauptet (früher: `is_external`).
    Nur das eingebaute Testmodell und im Test ausdrücklich zugelassene Ersatzmodelle arbeiten ohne Schranke.
    Alles andere ist extern und braucht Freigabe, Datenschutzprüfung und Schlüssel in .env.
    """

    def __init__(self, budget: BudgetGuard, kill: KillSwitch, model=None, guard=None, policy=None):
        from .ai_models import ModelPolicy
        self.model = model or MockLLM()
        self.budget = budget
        self.kill = kill
        self.guard = guard
        # Ohne eigene Richtlinie gilt die strengste: nur das eingebaute Testmodell.
        self.policy = policy if policy is not None else ModelPolicy()

    def allow_test_double(self, model) -> None:
        """NUR in automatischen Tests: Ersatzmodell ausdrücklich zulassen und einsetzen."""
        self.policy.allow_test_double(model)
        self.model = model

    def _guard(self):
        if self.guard is None:     # ohne Schranke niemals extern senden
            from .outbound import ExternalAIBlocked
            raise ExternalAIBlocked("Keine Datenschutz-Schranke konfiguriert. Es wurden keine Daten gesendet.")
        return self.guard

    def _admit(self, task: str, chars: int):
        model = self.model                     # einmal lesen: Prüfung und Aufruf betreffen dasselbe Objekt
        self.kill.check()
        decision = self.policy.authorize(model, task, chars)
        return model, decision

    def _charge(self, model, decision) -> None:
        # Kosten werden VOR dem Aufruf verbucht: ist das Limit erreicht, findet kein Aufruf statt.
        # Bei externen Modellen zählt der höhere Wert aus Konfiguration und Selbstauskunft.
        claimed = getattr(model, "cost_per_call_eur", 0.0)
        claimed = float(claimed) if isinstance(claimed, (int, float)) and not isinstance(claimed, bool) else 0.0
        self.budget.charge(decision.model, max(decision.cost_eur, claimed, 0.0))

    def complete(self, task: str, text: str) -> str:
        model, decision = self._admit(task, len(text or ""))
        if decision.kind != "test":
            _, _, text = self._guard().prepare("", [], text)
        self._charge(model, decision)
        return model.complete(task, text)

    def chat(self, system_prompt: str, history: list, text: str) -> str:
        """Chat-Antwort. Notaus, Erlaubnisliste, Datenschutz-Schranke und Kostenbremse VOR dem Modellaufruf."""
        chars = len(system_prompt or "") + len(text or "") + sum(len(str(m.get("text", ""))) for m in history)
        model, decision = self._admit("chat", chars)
        if decision.kind != "test":
            system_prompt, history, text = self._guard().prepare(system_prompt, history, text)
        self._charge(model, decision)
        return model.chat(system_prompt, history, text)
