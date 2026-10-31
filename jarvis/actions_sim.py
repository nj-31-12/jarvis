"""Simulierte Ausführer.

Phase 1: NICHTS wird wirklich gesendet, gekauft oder veröffentlicht.
Jede "Ausführung" schreibt nur eine JSON-Datei nach data/sandbox/outbox/.
Echte Ausführer kommen erst nach deiner ausdrücklichen Genehmigung (Phase 3+).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable


def make_handlers(sandbox_dir: str | Path) -> dict[str, Callable[[dict], str]]:
    outbox = Path(sandbox_dir) / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)

    def _store(kind: str, payload: dict) -> Path:
        path = outbox / f"{time.strftime('%Y%m%d-%H%M%S')}_{kind}_{time.time_ns() % 100000}.json"
        path.write_text(json.dumps({"simuliert": True, "art": kind, **payload}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path

    def send_email(p: dict) -> str:
        return f"SIMULIERT: E-Mail an {p.get('an')} gespeichert in {_store('email', p).name}"

    def publish_post(p: dict) -> str:
        return f"SIMULIERT: Post für {p.get('plattform')} gespeichert in {_store('post', p).name}"

    def write_file(p: dict) -> str:
        return f"SIMULIERT: Dateiänderung '{p.get('pfad')}' gespeichert in {_store('datei', p).name}"

    def calendar_event(p: dict) -> str:
        return f"SIMULIERT: Termin '{p.get('titel')}' gespeichert in {_store('termin', p).name}"

    def change_account(p: dict) -> str:
        return f"SIMULIERT: Kontoänderung gespeichert in {_store('konto', p).name}"

    def read_mailbox(p: dict) -> str:
        return "SIMULIERT: Postfach-Zugriff freigegeben (keine echte Verbindung in Phase 1)."

    def generic(kind: str):
        def run(p: dict) -> str:
            return f"SIMULIERT: {kind} gespeichert in {_store(kind, p).name}"
        return run

    return {
        "send_message": generic("nachricht"),
        "connect_account": generic("kontoverbindung"),
        "install_program": generic("installation"),
        "upload_data": generic("upload"),
        "activate_paid_service": generic("kostenpflichtiger_dienst"),
        "modify_file": generic("dateiaenderung"),
        "delete_file": generic("dateiloeschung"),
        "shopify_update_product": generic("shopify_produkt"),
        "install_skill": generic("skill_installation"),
        "enable_skill": generic("skill_aktivierung"),
        "grant_permission": generic("berechtigung"),
        "calendar_write": generic("kalender"),
        "send_email": send_email,
        "publish_post": publish_post,
        "write_file": write_file,
        "calendar_event": calendar_event,
        "change_account": change_account,
        "read_mailbox": read_mailbox,
    }
