"""Kostenbremse für KI-Aufrufe.

Vor jedem (kostenpflichtigen) Aufruf wird geprüft, ob Tages- und Monatslimit noch reichen.
Ist ein Limit erreicht, wird der Aufruf hart verweigert.
"""
from __future__ import annotations

import time
from pathlib import Path

from .db import LockedDB


class BudgetExceeded(RuntimeError):
    pass


class BudgetGuard:
    def __init__(self, db_path: str | Path, daily_eur: float, monthly_eur: float):
        self.daily = float(daily_eur)
        self.monthly = float(monthly_eur)
        self.db = LockedDB(db_path)
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

    def charge(self, provider: str, cost_eur: float) -> None:
        """Prüfen und verbuchen in einem Schritt, damit parallele Anfragen das Limit nicht gemeinsam überschreiten."""
        with self.db.lock:
            self.check(cost_eur)
            self.record(provider, cost_eur)

    def status(self) -> str:
        return (
            f"Heute {self.spent_today():.2f} / {self.daily:.2f} € · "
            f"Monat {self.spent_month():.2f} / {self.monthly:.2f} €"
        )

    def close(self) -> None:
        """Datenbankverbindung schließen."""
        self.db.close()
