"""Threadsicherer SQLite-Zugriff.

Ein Webserver beantwortet mehrere Anfragen gleichzeitig. Damit sich dabei keine
Datenbankzugriffe überschneiden, läuft jeder Befehl unter einer Sperre und die
Ergebnisse werden sofort vollständig gelesen.
"""
from __future__ import annotations

import contextlib
import sqlite3
import threading
import weakref
from pathlib import Path


class Result:
    """Ergebnis eines Befehls. Verhält sich wie ein sqlite3-Cursor (fetchone, fetchall, rowcount, for)."""

    def __init__(self, rows: list, rowcount: int):
        self._rows = rows
        self.rowcount = rowcount

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list:
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


class DatabaseUnavailable(RuntimeError):
    """Datenbank fehlt nicht, ist aber beschädigt oder unlesbar. Die Datei wird NICHT verändert."""


class LockedDB:
    def __init__(self, path: str | Path, autocommit: bool = True):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = Path(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False,
                                     isolation_level=None if autocommit else "DEFERRED", timeout=10)
        self._autocommit = autocommit
        try:
            with self._lock:
                # Lesbarkeit prüfen, BEVOR irgendetwas geschrieben wird (auch der Journal-Modus ist ein Schreibvorgang)
                self._conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
                if self._conn.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                    self._conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError as exc:
            self._conn.close()
            raise DatabaseUnavailable(
                f"Die Datenbank {self.path.name} ist beschädigt oder unlesbar ({exc}). Sie wurde NICHT verändert. "
                f"Bitte JARVIS beenden und die Datei aus deiner Sicherung wiederherstellen.") from exc
        # Verbindung wird sicher geschlossen: ausdrücklich per close() ODER automatisch, sobald dieses Objekt
        # nicht mehr gebraucht wird bzw. das Programm endet (vorher blieben Verbindungen offen → ResourceWarning).
        self._finalizer = weakref.finalize(self, LockedDB._close_connection, self._conn, self._lock)

    @staticmethod
    def _close_connection(conn, lock) -> None:
        with lock:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 – Schließen darf nie einen Fehler auslösen
                pass

    @property
    def closed(self) -> bool:
        return not self._finalizer.alive

    @property
    def lock(self) -> threading.RLock:
        """Für Abläufe aus mehreren Befehlen, die zusammen atomar sein müssen."""
        return self._lock

    def execute(self, sql: str, params: tuple = ()) -> Result:
        if not self._finalizer.alive:
            raise sqlite3.ProgrammingError("Datenbankverbindung ist bereits geschlossen.")
        with self._lock:
            cur = self._conn.execute(sql, params)
            rows = cur.fetchall()
            if not self._autocommit:
                self._conn.commit()
            return Result(rows, cur.rowcount)

    @contextlib.contextmanager
    def transaction(self):
        """Mehrere Befehle als Einheit: entweder alle oder keiner (z. B. bei Absturz oder Fehler)."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    def backup_to(self, target: str | Path) -> Path:
        """Konsistente Sicherungskopie (SQLite-Backup-Schnittstelle), auch bei laufendem Betrieb."""
        target = Path(target)
        with self._lock:
            dest = sqlite3.connect(str(target))
            try:
                self._conn.backup(dest)
            finally:
                dest.close()
        return target

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def close(self) -> None:
        """Schließt die Verbindung (mehrfacher Aufruf ist unbedenklich)."""
        self._finalizer()
