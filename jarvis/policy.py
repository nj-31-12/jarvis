"""Regelwerk: Welche Aktion ist erlaubt, welche braucht Freigabe, welche ist verboten.

Diese Liste ist FEST im Code. Das Sprachmodell kann sie nicht ändern.
Unbekannte Aktionstypen sind automatisch verboten ("deny by default").
"""
from __future__ import annotations

import json

AUTO = "auto"            # darf ohne Rückfrage (nur lesen/analysieren)
APPROVAL = "approval"    # braucht ausdrückliche Telegram-Freigabe
FORBIDDEN = "forbidden"  # niemals, auch nicht mit Freigabe

ACTION_POLICY = {
    # Nur lesend / analysierend
    "research": AUTO,
    "draft_note": AUTO,          # Entwurf im JARVIS-Inbox-Ordner des Vaults
    # Ausführend -> Freigabe nötig
    "send_email": APPROVAL,
    "publish_post": APPROVAL,
    "write_file": APPROVAL,
    "change_account": APPROVAL,
    "calendar_event": APPROVAL,
    "read_mailbox": APPROVAL,    # E-Mails lesen erst nach gesonderter Freigabe
    "send_message": APPROVAL,    # Nachrichten an andere Personen (WhatsApp, DM, ...)
    "connect_account": APPROVAL,
    "install_program": APPROVAL,
    "upload_data": APPROVAL,     # externe Daten hochladen
    "activate_paid_service": APPROVAL,
    "modify_file": APPROVAL,     # bestehende Datei ändern (auch im Vault)
    "delete_file": APPROVAL,
    # Version 5 (Freigabezentrale und Skills)
    "shopify_update_product": APPROVAL,   # Produkt ändern (Preis, Text, Bestand)
    "install_skill": APPROVAL,            # neuen Skill aufnehmen
    "enable_skill": APPROVAL,             # Skill einschalten
    "grant_permission": APPROVAL,         # Berechtigungen erweitern
    "calendar_write": APPROVAL,           # Termin eintragen/ändern
    # In Phase 1 komplett gesperrt
    "purchase": FORBIDDEN,
    "place_order": FORBIDDEN,             # Bestellungen: nie durch JARVIS (deine Regel 8)
    "bank_access": FORBIDDEN,
    "payment": FORBIDDEN,
    "spend_money": FORBIDDEN,    # Geld ausgeben nur durch dich selbst, nie durch JARVIS
}

RISK_LABEL = {AUTO: "niedrig", APPROVAL: "hoch", FORBIDDEN: "gesperrt"}


class PolicyViolation(PermissionError):
    pass


def classify(action_type: str) -> str:
    return ACTION_POLICY.get(action_type, FORBIDDEN)


def check_payload(payload: dict, forbidden_terms: list[str]) -> None:
    """Blockiert Aktionen, deren Inhalt verbotene Begriffe enthält (z. B. Bankdaten)."""
    text = json.dumps(payload, ensure_ascii=False).lower()
    for term in forbidden_terms:
        term = term.lower().strip()
        if not term:
            continue
        # einfache Wortgrenzen-Prüfung, damit z. B. "pin" nicht in "spinat" anschlägt
        padded = f" {text} "
        for sep in " .,;:!?\"'()[]{}/\\\n-_":
            padded = padded.replace(sep, " ")
        if f" {term} " in padded:
            raise PolicyViolation(f"Verbotener Begriff in Aktion: '{term}'")
