"""Themen-Rotation für die Nachtrecherche.

Damit kein Geschäftsbereich vernachlässigt wird, wählt JARVIS pro Nacht die
Themen, die am längsten nicht mehr recherchiert wurden.
"""
from __future__ import annotations

import time
from pathlib import Path

from .db import LockedDB


class TopicRotation:
    def __init__(self, db_path: str | Path):
        self.db = LockedDB(db_path)
        self.db.execute("CREATE TABLE IF NOT EXISTS topics (topic TEXT PRIMARY KEY, last REAL, runs INTEGER)")

    def pick(self, topics: list[str], n: int) -> list[str]:
        """Die n Themen mit dem ältesten Zeitstempel (nie recherchiert = zuerst)."""
        with self.db.lock:
            last = dict((r[0], r[1]) for r in self.db.execute("SELECT topic, last FROM topics"))
            ordered = sorted(dict.fromkeys(topics), key=lambda t: (last.get(t, 0.0), topics.index(t)))
            return ordered[:max(0, n)]

    def mark_done(self, topic: str) -> None:
        with self.db.transaction():  # ohne "ON CONFLICT", damit auch ältere SQLite-Versionen (macOS 10.15) funktionieren
            self.db.execute("INSERT OR IGNORE INTO topics VALUES (?,?,0)", (topic, 0.0))
            self.db.execute("UPDATE topics SET last=?, runs=runs+1 WHERE topic=?", (time.time(), topic))

    def coverage(self, topics: list[str]) -> dict[str, int]:
        rows = dict((r[0], r[1]) for r in self.db.execute("SELECT topic, runs FROM topics"))
        return {t: int(rows.get(t, 0)) for t in topics}

    def close(self) -> None:
        """Datenbankverbindung schließen."""
        self.db.close()
