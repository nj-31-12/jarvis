"""Version 5.2: „Nur lesen“ heißt wirklich nur lesen – auch mit macOS-Verhalten von SQLite.

Hintergrund: Auf Noahs MacBook (macOS Catalina, Python 3.8.2) schlug test_d5_health_check_changes_nothing fehl.
Das mit macOS ausgelieferte SQLite lässt -wal/-shm nach dem Schließen stehen („persistentes WAL“). Version 5.1
schloss aus einer vorhandenen -wal-Datei „JARVIS läuft“ und öffnete die Datenbank direkt – dabei entstanden bzw.
änderten sich -shm-Dateien. Diese Tests bilden das macOS-Verhalten unter jedem Betriebssystem nach.
"""
from __future__ import annotations

import hashlib
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from jarvis import server
from jarvis.chat import pending_migration
from jarvis.config import DEFAULTS
from jarvis.core import Jarvis


def strict_snapshot(folder: Path) -> dict:
    """Name, Größe, Inhalt UND Änderungszeit jeder Datei und jedes Ordners (strenger als data_fingerprint)."""
    out = {".": ("ordner", folder.stat().st_mtime_ns)}
    for p in sorted(folder.rglob("*")):
        st = p.stat()
        content = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "ordner"
        out[p.relative_to(folder).as_posix()] = (content, st.st_size, st.st_mtime_ns)
    return out


def describe_changes(before: dict, after: dict) -> str:
    lines = []
    for k in sorted(set(before) | set(after)):
        if before.get(k) != after.get(k):
            lines.append(f"{k}: " + ("NEU" if k not in before else "GELÖSCHT" if k not in after else "verändert"))
    return "\n".join(lines)


def leave_sqlite_side_files(data: Path, with_shm: bool) -> None:
    """Bildet macOS nach: nach dem Schließen bleiben eine (leere) -wal und ggf. -shm-Datei stehen."""
    for db in data.glob("*.db"):
        Path(str(db) + "-wal").write_bytes(b"")
        if with_shm:
            Path(str(db) + "-shm").write_bytes(b"\0" * 32768)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "data"
        self.cfg = dict(DEFAULTS, data_dir=str(self.data), vault_dir=str(self.data / "vault"),
                        telegram={"allowed_user_ids": [1], "approval_chat_id": 1},
                        backup={"dir": str(self.tmp / "sicherungen")})
        j = Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": "z" * 48}, channel=lambda *a: None)
        j.handle_text("/mail coach@example.com | Hallo | Text")
        j.handle_text("/notiz Test")
        j.close()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def assert_untouched(self, action):
        before = strict_snapshot(self.data)
        action()
        after = strict_snapshot(self.data)
        self.assertEqual(before, after, "Im Datenordner wurde etwas verändert:\n" + describe_changes(before, after))


class MacOsPersistentWal(Base):
    def test_r1_health_check_with_leftover_wal_and_shm(self):
        leave_sqlite_side_files(self.data, with_shm=True)
        self.assert_untouched(lambda: server.health_report(self.cfg))

    def test_r1_health_check_with_only_empty_wal(self):
        leave_sqlite_side_files(self.data, with_shm=False)      # genau hier entstanden in 5.1 neue -shm-Dateien
        self.assert_untouched(lambda: server.health_report(self.cfg))

    def test_r1_health_check_reports_databases_ok(self):
        leave_sqlite_side_files(self.data, with_shm=False)
        report = server.health_report(self.cfg)
        dbs = [(lvl, text) for lvl, area, text in report if area == "Datenbank"]
        self.assertTrue(dbs)
        self.assertTrue(all(lvl == "ok" for lvl, _ in dbs), dbs)

    def test_r2_other_reading_functions_change_nothing(self):
        leave_sqlite_side_files(self.data, with_shm=False)
        self.assert_untouched(lambda: server.pending_upgrades(self.cfg))
        self.assert_untouched(lambda: pending_migration(self.data / "actions.db"))
        self.assert_untouched(lambda: server.latest_backup(self.cfg))
        self.assert_untouched(lambda: server.jarvis_running(self.data))

    def test_r2_backup_changes_nothing_in_data_folder(self):
        leave_sqlite_side_files(self.data, with_shm=False)
        self.assert_untouched(lambda: server.make_backup(self.cfg))

    def test_r3_health_check_does_not_create_or_delete_files(self):
        """Früher: Testdatei .gesundheit-<pid> anlegen und löschen → Zeitstempel des Ordners änderte sich."""
        self.assert_untouched(lambda: server.health_report(self.cfg))


class CrashLeftoverWal(Base):
    def crashed_copy(self) -> Path:
        """Zustand nach einem Absturz: Einträge stehen nur im -wal, die .db-Datei kennt sie noch nicht."""
        live = self.tmp / "live.db"
        con = sqlite3.connect(str(live))
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA wal_autocheckpoint=0")
        con.execute("CREATE TABLE t (x TEXT)")
        con.execute("INSERT INTO t VALUES ('nur im WAL')")
        con.commit()
        shutil.copyfile(str(live), str(self.data / "absturz.db"))
        shutil.copyfile(str(live) + "-wal", str(self.data / "absturz.db-wal"))
        con.close()
        return self.data / "absturz.db"

    def test_r4_backup_keeps_entries_that_are_only_in_wal_and_changes_nothing(self):
        self.crashed_copy()
        self.assertGreater((self.data / "absturz.db-wal").stat().st_size, 0)
        before = strict_snapshot(self.data)
        archive = server.make_backup(self.cfg)
        self.assertEqual(strict_snapshot(self.data), before)
        restored = server.restore_backup(archive, self.tmp / "zurueck")
        con = sqlite3.connect(str(restored / "absturz.db"))
        try:
            self.assertEqual(con.execute("SELECT x FROM t").fetchall(), [("nur im WAL",)])
        finally:
            con.close()
        self.assertFalse((restored / "absturz.db-wal").exists())    # Sicherung ist eine vollständige Einzeldatei

    def test_r4_health_check_reads_wal_content_without_changes(self):
        self.crashed_copy()
        self.assert_untouched(lambda: self.assertTrue(server._db_ok(self.data / "absturz.db")[0]))


class RunningDetection(Base):
    def test_r5_running_is_detected_by_lock_not_by_wal_file(self):
        leave_sqlite_side_files(self.data, with_shm=True)
        self.assertFalse(server.jarvis_running(self.data))             # -wal vorhanden, aber JARVIS läuft nicht
        with server.instance_lock(self.data, "web"):
            self.assertTrue(server.jarvis_running(self.data))
        self.assertFalse(server.jarvis_running(self.data))

    def test_r5_check_does_not_create_lock_files(self):
        self.assertFalse((self.data / ".lock-web").exists())
        server.jarvis_running(self.data)
        self.assertFalse((self.data / ".lock-web").exists())

    def test_r5_health_check_works_while_jarvis_runs(self):
        j = Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": "z" * 48}, channel=lambda *a: None)
        self.addCleanup(j.close)
        with server.instance_lock(self.data, "web"):
            j.handle_text("/notiz während des Betriebs")
            report = server.health_report(self.cfg)
        self.assertTrue(all(lvl == "ok" for lvl, area, _ in report if area == "Datenbank"), report)

    def test_r5_copy_is_retried_when_file_changes_during_copy(self):
        calls = {"n": 0}
        original = server._stat_key

        def flaky(path):
            calls["n"] += 1
            if calls["n"] == 2:                    # erster Versuch: Vorher-/Nachher-Stand passt nicht → Wiederholung
                return (-1, -1)
            return original(path)
        server._stat_key = flaky
        try:
            self.assertTrue(server._db_ok(self.data / "actions.db")[0])
        finally:
            server._stat_key = original
        self.assertGreater(calls["n"], 4)          # mindestens ein zweiter Versuch


if __name__ == "__main__":
    unittest.main()
