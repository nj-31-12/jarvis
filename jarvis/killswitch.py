"""Notabschaltung.

Existiert die Datei data/KILL, verweigert JARVIS jede Ausführung und jeden KI-Aufruf.
- Aktivieren: per Telegram /stop oder lokal `python3 -m jarvis stop`.
- Aufheben: NUR lokal am Rechner/Server mit `python3 -m jarvis resume`
  (bewusst nicht per Telegram – ein gestohlenes Handy kann JARVIS so nur stoppen, nie starten).
"""
from __future__ import annotations

import time
from pathlib import Path


class KillSwitchActive(RuntimeError):
    pass


class KillSwitch:
    def __init__(self, data_dir: str | Path):
        self.path = Path(data_dir) / "KILL"

    def is_active(self) -> bool:
        return self.path.exists()

    def activate(self, reason: str = "manuell") -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {reason}\n", encoding="utf-8")

    def release(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def check(self) -> None:
        if self.is_active():
            raise KillSwitchActive("Notabschaltung aktiv – keine Aktionen erlaubt.")
