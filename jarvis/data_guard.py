"""Daten-Wächter (Stand 18): Nachrichten, die sensible Daten von Noah anfordern, werden erkannt und gemeldet.

Beispiele: weitergeleitete E-Mails oder SMS mit „Bestätigen Sie Ihr Passwort“, „Code eingeben“, „Konto gesperrt“,
Link + Zeitdruck, Bitte um IBAN, Ausweis oder Geschenkkarten. JARVIS gibt dann einen Sicherheitshinweis aus, gibt
selbst nie Daten heraus und handelt nur mit Noahs Freigabe. Erkennung über Muster: kein Ersatz für Vorsicht,
aber ein zusätzlicher Schutz. Protokolliert wird nur, DASS etwas erkannt wurde – nie der Inhalt.
"""
from __future__ import annotations

import re

SIGNALS = [
    ("Passwort oder PIN", re.compile(r"(?i)\b(passwort|kennwort|password|pin|zugangsdaten|login-?daten|anmeldedaten)\b")),
    ("Code oder TAN", re.compile(r"(?i)\b(tan|bestätigungs-?code|sicherheits-?code|verifizierungs-?code|einmal-?code|"
                                 r"2fa|zwei-?faktor|sms-?code|verification code)\b")),
    ("Konto verifizieren/gesperrt", re.compile(r"(?i)(konto|account|zugang)\S*\s+(\S+\s+){0,3}(gesperrt|eingeschränkt|"
                                               r"verifizier|bestätig|aktualisier)")),
    ("Bank- oder Kartendaten", re.compile(r"(?i)\b(iban|kreditkarte|kartennummer|cvc|cvv|bankdaten|überweis\w*)\b")),
    ("Ausweis", re.compile(r"(?i)\b(personalausweis|ausweis-?kopie|ausweisnummer|reisepass)\b")),
    ("Geschenkkarten", re.compile(r"(?i)\b(gutschein-?code|geschenkkarte|gift ?card|itunes-?karte|paysafe)\w*")),
    ("Zeitdruck", re.compile(r"(?i)(innerhalb von \d+ (stunden|tagen)|sofort|umgehend|letzte mahnung|dringend)")),
    ("Link", re.compile(r"(?i)\bhttps?://\S+|\bwww\.\S+")),
]
STRONG = {"Passwort oder PIN", "Code oder TAN", "Bank- oder Kartendaten", "Ausweis", "Geschenkkarten"}
REQUEST = re.compile(r"(?i)(geben sie|senden sie|schicken sie|bestätigen sie|klicken sie|teilen sie|"
                     r"gib|schick|sende|bestätige|klick|teile|eingeben|mitteilen|übermitteln|anfordern|fordert)")


def check(text: str) -> dict:
    """{"level": "" | "mittel" | "hoch", "signals": [...]}. „hoch“ = sensible Daten + Aufforderung oder viele Signale."""
    text = text or ""
    found = [label for label, pattern in SIGNALS if pattern.search(text)]
    strong = [f for f in found if f in STRONG]
    asks = bool(REQUEST.search(text))
    level = ""
    if strong and (asks or len(found) >= 3):
        level = "hoch"
    elif strong or (len(found) >= 2 and asks):
        level = "mittel"
    return {"level": level, "signals": found}


def banner(result: dict) -> str:
    """Hinweis über der Antwort. Leer, wenn nichts erkannt wurde."""
    if not result.get("level"):
        return ""
    signs = ", ".join(result["signals"])
    if result["level"] == "hoch":
        return ("🛡 **Sicherheitsprüfung: Achtung.** Hier werden sensible Daten angefordert (" + signs + "). Das sind "
                "typische Merkmale von Betrugsnachrichten. **Gib nichts weiter und klick keinen Link**, bevor wir es "
                "gemeinsam geprüft haben – am sichersten direkt über die offizielle App oder Website. Ich selbst gebe "
                "keine Daten heraus und handle nur mit deiner Freigabe.\n\n")
    return ("🛡 **Sicherheitsprüfung:** Es geht um sensible Daten (" + signs + "). Ich speichere oder sende keine "
            "Passwörter, Codes oder Bankdaten. Bevor etwas weitergegeben wird, sprechen wir uns ab.\n\n")
