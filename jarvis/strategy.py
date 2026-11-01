"""Strategie-Werkstatt (Stand 17): Eine Geschäftsidee durch mehrere Experten-Brillen prüfen.

Noah erzählt eine Strategie (Chat: `/strategie <Text>` oder Second Brain → Strategie-Werkstatt). JARVIS antwortet
in festen Abschnitten („Skills“) und legt das Ergebnis als NEUE Notiz im Second Brain ab
(00_Inbox/JARVIS/Strategien, `typ: strategie`). Läuft über die normale Sicherheitskette (Notaus, Erlaubnisliste,
Datenschutz-Schranke, Kostenbremse). Ohne echte KI entsteht eine Arbeitsvorlage mit denselben Abschnitten.
"""
from __future__ import annotations

from .knowledge import SENSITIVE_PATTERNS

MAX_IDEA_CHARS = 3000
FOLDER = "00_Inbox/JARVIS/Strategien"

LENSES = [
    ("🎯 Kern und Zielgruppe", "Welches Problem wird gelöst, für wen genau, und warum würden sie zahlen?"),
    ("📊 Markt und Nachfrage", "Wie groß ist der erreichbare Markt, zuerst regional (Raum Aschaffenburg)? Annahmen offenlegen."),
    ("🥊 Wettbewerb und Unterscheidung", "Wer bietet so etwas schon an (Arten von Anbietern), und was ist hier anders?"),
    ("💶 Geschäftsmodell und Preise", "Wie wird Geld verdient? Rechne offen: Kunden × Preis × Monate."),
    ("🧮 Kosten, Startkapital und Break-even", "Was kostet der Start, was laufend, ab wann trägt es sich?"),
    ("📣 Marketing und Vertrieb", "Wie kommen die ersten 10 zahlenden Kunden? Konkrete Kanäle und Ansprache."),
    ("🛠 Technik und Umsetzung", "Kleinstes funktionierendes Angebot (MVP), Werkzeuge, was sich automatisieren lässt."),
    ("⚖️ Recht und Rahmen", "Gewerbe, Impressum, DSGVO, Verträge, Nebentätigkeit neben der Ausbildung. Nur Orientierung."),
    ("⚠️ Risiken und Annahmen", "Was muss stimmen, damit es funktioniert? Wie lässt sich das billig testen?"),
    ("🗓 90-Tage-Plan", "Drei Phasen mit klaren Zielen, dazu EIN konkreter Schritt für diese Woche."),
    ("🧠 JARVIS-Urteil", "Bewertung 1–10 für Nachfrage, Aufwand neben der Ausbildung, Startkosten, Skalierbarkeit, "
                        "Passung zu Noah. Ehrliches Fazit in zwei Sätzen."),
]


def system_prompt() -> str:
    parts = ["Du bist JARVIS in der Strategie-Werkstatt. Noah beschreibt eine Geschäftsidee oder Strategie. "
             "Analysiere sie wie ein Team aus erfahrenen Experten, konkret für Noahs Lage: 18 Jahre, Ausbildung zum "
             "Automobilkaufmann (hat Vorrang), wenig Startkapital, Werkzeugbudget höchstens 20 € im Monat, Raum "
             "Aschaffenburg, Stärken in Social Media, Shopify, Fitness-Community und Kundenkontakt.",
             "Regeln: Trenne Fakten, Schätzungen und Ideen. Kennzeichne jede Zahl ohne Quelle als Schätzung. "
             "Erfinde keine Studien, Firmen oder Zahlen als Fakten. Recht und Steuern nur als Orientierung mit Verweis "
             "auf IHK, Finanzamt oder Steuerberatung. Kurze Sätze, keine Floskeln.",
             "Antworte in GENAU diesen Abschnitten als Markdown-Überschriften (##), in dieser Reihenfolge:"]
    parts += [f"## {name} – {question}" for name, question in LENSES]
    parts.append("Beginne direkt mit dem ersten Abschnitt. Schließe mit dem JARVIS-Urteil.")
    return "\n".join(parts)


def offline_template(idea: str) -> str:
    """Arbeitsvorlage ohne echte KI (Testmodus): dieselben Abschnitte, mit Leitfragen statt Antworten."""
    lines = ["_Testmodus: Mit echter KI füllt JARVIS jeden Abschnitt aus. Bis dahin: die Leitfragen selbst beantworten._", ""]
    for name, question in LENSES:
        lines += [f"## {name}", f"- {question}", "- …", ""]
    return "\n".join(lines)


def run_strategy(jarvis, idea: str) -> tuple:
    """Analysiert die Idee und speichert sie im Second Brain. Gibt (Meldung, Notiz-Pfad oder None, Analyse) zurück."""
    idea = (idea or "").replace("\r\n", "\n").strip()[:MAX_IDEA_CHARS]
    if len(idea) < 15:
        return "Bitte beschreibe die Idee in ein, zwei Sätzen, z. B.: /strategie QR-Stempelkarten für Restaurants …", None, ""
    if jarvis.kill.is_active():
        return "🛑 Notabschaltung aktiv. Es wurde nichts analysiert oder gespeichert.", None, ""
    if any(p.search(idea) for _, p in SENSITIVE_PATTERNS):
        return "⛔ Die Beschreibung enthält vermutlich sensible Daten (z. B. Bank- oder Zugangsdaten). Bitte weglassen.", None, ""
    model = jarvis.llm.model
    if getattr(model, "is_test_mode", True):
        analysis = offline_template(idea)
    else:
        analysis = jarvis.llm.chat(system_prompt(), [], idea)          # Sicherheitskette und Kostenbremse greifen
    from .web_brain import PROJECTS, _area_of, _keywords      # spät importieren (Kreisbezug vermeiden)

    class _N:                                                 # kleine Hülle für die Bereichserkennung
        title, text, meta = idea[:80], idea, {}
    area = _area_of(_N, [(p["slug"], _keywords(p)) for p in PROJECTS]) or "ideen"
    body = "## 💡 Idee (Noahs Beschreibung)\n" + idea + "\n\n" + analysis.strip()
    path = jarvis.vault.write_draft("Strategie " + idea.splitlines()[0][:50], body, ["strategie"], folder=FOLDER,
                                    extra_meta={"typ": "strategie", "bereich": area,
                                                "herkunft": "Strategie-Werkstatt (Noah)"})
    jarvis.kb.invalidate()
    jarvis.audit.write("strategy_created", length=len(idea), area=area)
    return f"🧭 Strategie analysiert und im Second Brain abgelegt: {path.name}", path, analysis.strip()
