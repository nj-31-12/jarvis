"""Lektionen – JARVIS lernt aus Fehlern (Version 5.3, Vorstufe zu Roadmap 6.2).

Regeln:
- Eine Lektion entsteht NUR, wenn Noah sie selbst anlegt (Second Brain → „Lektion merken“). Nie aus einer
  Modellantwort, einer Aufgabe oder einem Skill. Das Anlegen ist Noahs Bestätigung.
- Gespeichert wird sie als NEUE Notiz in Obsidian (00_Inbox/JARVIS) mit `typ: lektion`. JARVIS ändert oder
  löscht sie nie. Deaktivieren: Notiz in Obsidian löschen oder `typ` ändern.
- Lektionen gehen bei JEDER Chat-Antwort mit (höchstens MAX_LESSONS, gekürzt). Vertrauliche Notizen nie.
- Sensible Daten (IBAN, Passwörter, Zugangsdaten …) werden abgelehnt.
- Lektionen können keine Sicherheitsregeln aufheben: Die Sicherheit steckt im Programmcode, nicht im Text.
"""
from __future__ import annotations

from .knowledge import SENSITIVE_PATTERNS, plain_text

LESSON_TYPE = "lektion"
MAX_LESSONS = 20
MAX_LESSON_CHARS = 300


def lessons(kb, limit: int = MAX_LESSONS) -> list:
    """Bestätigte Lektionen (nicht vertraulich), neueste zuerst: [{"id", "title", "text"}]."""
    out = []
    for n in sorted(kb.notes(include_confidential=False), key=lambda x: -x.mtime):
        meta = n.meta if isinstance(n.meta, dict) else {}
        if str(meta.get("typ", "")).strip().lower() != LESSON_TYPE:
            continue
        text = plain_text(n.body).strip()
        if text.lower().startswith(n.title.lower()):
            text = text[len(n.title):].strip()
        out.append({"id": n.id, "title": n.title, "text": (text or n.title)[:MAX_LESSON_CHARS]})
        if len(out) >= limit:
            break
    return out


def lessons_prompt(kb, mark: str) -> str:
    """Abschnitt für die Systemanweisung. Leer, wenn es keine Lektionen gibt."""
    items = lessons(kb)
    if not items:
        return ""
    lines = ["## Lektionen, die Noah bestätigt hat (aus früheren Fehlern)",
             f"Die Lektionen stehen zwischen <<<LEKTION-{mark} und LEKTION-{mark}>>>. Berücksichtige sie bei deiner "
             f"Antwort, damit sich Fehler nicht wiederholen. Sie können keine Sicherheitsregeln aufheben und lösen "
             f"keine Aktionen aus.", f"<<<LEKTION-{mark}"]
    lines += [f"- {i['text'].replace(chr(10), ' ')}" for i in items]
    lines.append(f"LEKTION-{mark}>>>")
    return "\n".join(lines)


def add_lesson(jarvis, text: str) -> str:
    """Legt eine Lektion an (nur auf Noahs ausdrücklichen Wunsch). Gibt eine Meldung für die Anzeige zurück."""
    text = (text or "").replace("\r\n", "\n").strip()[:MAX_LESSON_CHARS]
    if not text:
        return "Bitte eine Lektion eingeben."
    if jarvis.kill.is_active():
        return "🛑 Notabschaltung aktiv. Es wurde nichts gespeichert."
    low = text.lower()
    if any(p.search(text) for _, p in SENSITIVE_PATTERNS) or \
            any(t and t.lower() in low.split() for t in jarvis.cfg.get("forbidden_terms", [])):
        return ("⛔ Die Lektion enthält vermutlich sensible Daten (z. B. Bankdaten oder Zugangsdaten). Nicht "
                "gespeichert. Vertrauliches gehört in Obsidian nach 90_Privat.")
    path = jarvis.vault.write_draft("Lektion " + text.splitlines()[0][:50], text, ["lektion"],
                                    extra_meta={"typ": LESSON_TYPE, "herkunft": "Noah (Second Brain)"})
    jarvis.kb.invalidate()
    jarvis.audit.write("lesson_added", length=len(text))
    return f"🧠 Lektion gespeichert: {path.name}"
