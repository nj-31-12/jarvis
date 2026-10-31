"""Kostenbremse für KI-Aufrufe.

Vor jedem (kostenpflichtigen) Aufruf wird geprüft, ob Tages- und Monatslimit noch reichen.
Ist ein Limit erreicht, wird der Aufruf hart verweigert.

Version 5.3: Prüfen und Buchen laufen in EINER Datenbank-Transaktion (BEGIN IMMEDIATE). Damit können auch
mehrere Prozesse (Browser, Aufgabenplaner, Konsole) das Limit nicht gemeinsam überschreiten.
Gebucht wird VOR dem Aufruf eine Reservierung mit den höchstmöglichen Kosten. Nach der Antwort wird sie auf die
tatsächlichen Kosten korrigiert (settle). Kommt keine Kostenangabe, bleibt die volle Reservierung stehen.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .db import LockedDB

LOCK_WAIT_SECONDS = 10


class BudgetExceeded(RuntimeError):
    pass


class BudgetGuard:
    def __init__(self, db_path: str | Path, daily_eur: float, monthly_eur: float,
                 lock_wait_seconds: float = LOCK_WAIT_SECONDS):
        self.daily = float(daily_eur)
        self.monthly = float(monthly_eur)
        self.db = LockedDB(db_path)
        self.db.execute(f"PRAGMA busy_timeout = {int(float(lock_wait_seconds) * 1000)}")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS usage (ts REAL, day TEXT, month TEXT, provider TEXT, cost_eur REAL)"
        )
        self.db.commit()

    def _sum(self, column: str, value: str) -> float:
        row = self.db.execute(f"SELECT COALESCE(SUM(cost_eur),0) FROM usage WHERE {column}=?", (value,)).fetchone()
        return float(row[0])

    def spent_today(self) -> float:
        return self._sum("day", time.strftime("%Y-%m-%d"))

    def spent_month(self) -> float:
        return self._sum("month", time.strftime("%Y-%m"))

    def check(self, estimated_eur: float) -> None:
        if self.spent_today() + estimated_eur > self.daily:
            raise BudgetExceeded(f"Tageslimit {self.daily:.2f} € würde überschritten.")
        if self.spent_month() + estimated_eur > self.monthly:
            raise BudgetExceeded(f"Monatslimit {self.monthly:.2f} € würde überschritten.")

    def record(self, provider: str, cost_eur: float) -> None:
        self.db.execute(
            "INSERT INTO usage VALUES (?,?,?,?,?)",
            (time.time(), time.strftime("%Y-%m-%d"), time.strftime("%Y-%m"), provider, float(cost_eur)),
        )
        self.db.commit()

    def charge(self, provider: str, cost_eur: float) -> int:
        """Prüfen und verbuchen in EINER Transaktion – sicher auch über Prozessgrenzen hinweg.

        Gibt die Kennung der Buchung zurück (für settle). Ist die Datenbank länger als das Zeitlimit von einem
        anderen Prozess gesperrt, wird abgelehnt: keine Buchung, keine Anfrage."""
        cost = float(cost_eur)
        try:
            with self.db.transaction():
                self.check(cost)
                self.db.execute(
                    "INSERT INTO usage VALUES (?,?,?,?,?)",
                    (time.time(), time.strftime("%Y-%m-%d"), time.strftime("%Y-%m"), provider, cost),
                )
                row = self.db.execute("SELECT last_insert_rowid()").fetchone()
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                raise BudgetExceeded("Die Kostenbremse ist gerade von einem anderen Vorgang belegt. "
                                     "Zur Sicherheit wurde abgelehnt. Bitte gleich noch einmal versuchen.") from None
            raise
        return int(row[0])

    def settle(self, booking_id: int, actual_eur: float) -> None:
        """Reservierung nach der Antwort auf die tatsächlichen Kosten setzen."""
        actual = float(actual_eur)
        if actual < 0:
            return
        with self.db.transaction():
            self.db.execute("UPDATE usage SET cost_eur=? WHERE rowid=?", (actual, int(booking_id)))

    def status(self) -> str:
        return (
            f"Heute {self.spent_today():.2f} / {self.daily:.2f} € · "
            f"Monat {self.spent_month():.2f} / {self.monthly:.2f} €"
        )

    def close(self) -> None:
        """Datenbankverbindung schließen."""
        self.db.close()
