"""Benachrichtigungen mit Nachtruhe.

Regeln (Nachtruhe standardmäßig 22:00–07:00):
  - normal / niedrig  -> nachts in eine Warteschlange, erscheint im Morgenbriefing
  - wichtig (urgent)  -> nachts als STUMME Telegram-Nachricht (kein Ton, keine Vibration)
  - tagsüber          -> normale Nachricht
JARVIS ruft niemals an.
"""
from __future__ import annotations

import datetime as dt
import time
from pathlib import Path
from typing import Callable, Optional

from .db import LockedDB

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

# Signatur eines Kanals: send(text, silent, buttons) ; buttons = [[(label, callback_data), ...]]
Channel = Callable[[str, bool, Optional[list]], None]


def _parse_hm(value: str) -> dt.time:
    h, m = value.split(":")
    return dt.time(int(h), int(m))


def is_quiet(now: dt.datetime, start: str, end: str) -> bool:
    s, e, t = _parse_hm(start), _parse_hm(end), now.time()
    return (t >= s or t < e) if s > e else (s <= t < e)


class Notifier:
    def __init__(self, db_path: str | Path, quiet_start: str, quiet_end: str, timezone: str,
                 channel: Channel, clock: Callable[[], dt.datetime] | None = None):
        self.quiet_start, self.quiet_end = quiet_start, quiet_end
        self.tz = ZoneInfo(timezone) if ZoneInfo else None
        self.channel = channel
        self.clock = clock or (lambda: dt.datetime.now(self.tz))
        self.db = LockedDB(db_path)
        self.db.execute("CREATE TABLE IF NOT EXISTS queue (ts REAL, priority TEXT, text TEXT, delivered INTEGER)")
        # Nachrichtenprotokoll: jede ausgehende Meldung wird gespeichert (für Browser-Ansicht und Nachvollziehbarkeit).
        self.db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, "
                        "priority TEXT, text TEXT, mode TEXT, action_id TEXT)")

    def quiet_now(self) -> bool:
        return is_quiet(self.clock(), self.quiet_start, self.quiet_end)

    def notify(self, text: str, priority: str = "normal", buttons: list | None = None,
               action_id: str | None = None) -> str:
        """Gibt zurück, was passiert ist: 'sent', 'sent_silent' oder 'queued'."""
        if not self.quiet_now():
            mode = "sent"
            self.channel(text, False, buttons)
        elif priority == "urgent" or buttons:
            # Freigabe-Anfragen und Wichtiges: stumm zustellen, damit nichts verloren geht.
            mode = "sent_silent"
            self.channel(text, True, buttons)
        else:
            mode = "queued"
            self.db.execute("INSERT INTO queue VALUES (?,?,?,0)", (time.time(), priority, text))
        self.db.execute("INSERT INTO messages (ts, priority, text, mode, action_id) VALUES (?,?,?,?,?)",
                        (time.time(), priority, text, mode, action_id))
        return mode

    def drain_queue(self) -> list[str]:
        # Unter Sperre: Meldungen, die währenddessen neu eintreffen, gehen nicht verloren.
        with self.db.transaction():          # ganz oder gar nicht (Version 4.2)
            rows = self.db.execute("SELECT rowid, text FROM queue WHERE delivered=0 ORDER BY ts").fetchall()
            for rowid, _ in rows:
                self.db.execute("UPDATE queue SET delivered=1 WHERE rowid=?", (rowid,))
        return [r[1] for r in rows]

    def history(self, limit: int = 50, after_id: int = 0) -> list[dict]:
        """Letzte Meldungen (neueste zuletzt). Grundlage für die Browser-Ansicht."""
        rows = self.db.execute(
            "SELECT id, ts, priority, text, mode, action_id FROM messages WHERE id>? ORDER BY id DESC LIMIT ?",
            (int(after_id), max(1, min(int(limit), 500)))).fetchall()
        keys = ("id", "ts", "priority", "text", "mode", "action_id")
        return [dict(zip(keys, r)) for r in reversed(rows)]

    def queued_count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM queue WHERE delivered=0").fetchone()[0]

    def close(self) -> None:
        """Datenbankverbindung schließen."""
        self.db.close()

def console_channel(text: str, silent: bool, buttons: list | None) -> None:
    tag = "🔕 stumm" if silent else "🔔"
    print(f"\n[{tag} → Telegram]\n{text}")
    if buttons:
        for row in buttons:
            print("   " + "   ".join(f"[{label}]" for label, _ in row))

