"""Schranke für Daten, die JARVIS künftig an EXTERNE KI-Dienste senden könnte (Version 4.2).

Aktuell ist KEIN externer Dienst angebunden. Diese Schranke wird schon jetzt eingebaut und getestet,
damit eine spätere Anbindung sie nicht umgehen kann:

1. Standard: GESPERRT. Ohne `privacy.external_ai_allowed = true` (deine ausdrückliche Entscheidung) wird
   jede externe Anfrage abgelehnt, bevor Daten den Rechner verlassen.
2. Wenn erlaubt: Muster für Zugangsdaten, Schlüssel, Bankdaten, Kartennummern, E-Mail-Adressen,
   Telefonnummern und deine geschützten Begriffe werden ENTFERNT und durch [ENTFERNT: …] ersetzt.
3. Längenbegrenzung pro Anfrage.
4. Jede Prüfung wird protokolliert – nur Anzahl und Art der Entfernungen, nie der Inhalt.

WICHTIG: Mustererkennung ist KEINE vollständige Datenschutzgarantie. Sie ist eine zusätzliche Schicht.
Die Hauptregel bleibt: Vertrauliche Notizen gelangen gar nicht erst in den Kontext (knowledge.py).
"""
from __future__ import annotations

import re

from .knowledge import SENSITIVE_PATTERNS


class ExternalAIBlocked(PermissionError):
    pass


# Zusätzliche personenbezogene Muster (über SENSITIVE_PATTERNS hinaus)
PERSONAL_PATTERNS = [
    ("E-Mail-Adresse", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("Telefonnummer", re.compile(r"(?<!\w)(?:\+49|0049|0)\s?[1-9][0-9 /()-]{6,}[0-9](?!\w)")),
]


class OutboundGuard:
    def __init__(self, cfg: dict, audit=None):
        privacy = cfg.get("privacy", {})
        self.allowed = bool(privacy.get("external_ai_allowed", False))
        self.max_chars = int(privacy.get("max_chars_external", 12000))
        terms = cfg.get("knowledge", {}).get("confidential_terms", []) or []
        self.terms = [t for t in terms if t.strip() and not t.strip().upper().startswith("NAME_DEINES")]
        self.audit = audit

    def redact(self, text: str) -> tuple[str, dict]:
        """Ersetzt erkannte sensible Stellen. Gibt (bereinigter Text, Zähler je Art) zurück."""
        counts: dict = {}

        def sub(label, pattern, value):
            def repl(_m):
                counts[label] = counts.get(label, 0) + 1
                return f"[ENTFERNT: {label}]"
            return pattern.sub(repl, value)

        for label, pattern in SENSITIVE_PATTERNS + PERSONAL_PATTERNS:
            text = sub(label, pattern, text)
        for term in self.terms:
            text = sub("geschützter Begriff", re.compile(re.escape(term), re.I), text)
        return text, counts

    def prepare(self, system_prompt: str, history: list, text: str) -> tuple[str, list, str]:
        """Prüft und bereinigt eine Anfrage an einen EXTERNEN Dienst. Löst ExternalAIBlocked aus, wenn nicht erlaubt."""
        if not self.allowed:
            if self.audit:
                self.audit.write("external_ai_blocked", reason="nicht freigegeben")
            raise ExternalAIBlocked("Externe KI ist nicht freigegeben (privacy.external_ai_allowed = false). "
                                    "Es wurden keine Daten gesendet.")
        total: dict = {}

        def clean(value: str) -> str:
            cleaned, counts = self.redact(value)
            for k, v in counts.items():
                total[k] = total.get(k, 0) + v
            return cleaned

        sp = clean(system_prompt)
        hist = [{"role": m.get("role", ""), "text": clean(m.get("text", ""))} for m in history]
        tx = clean(text)
        size = len(sp) + len(tx) + sum(len(m["text"]) for m in hist)
        if size > self.max_chars:
            # älteste Verlaufseinträge zuerst weglassen, nie die Systemanweisung
            while hist and size > self.max_chars:
                size -= len(hist.pop(0)["text"])
            if size > self.max_chars:
                if self.audit:
                    self.audit.write("external_ai_blocked", reason="zu groß", chars=size)
                raise ExternalAIBlocked("Die Anfrage ist zu groß für eine externe Übertragung. Es wurde nichts gesendet.")
        if self.audit:
            self.audit.write("external_ai_prepared", removed=total, chars=size)
        return sp, hist, tx
