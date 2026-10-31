"""Version 5 · Phase F: Umstieg von älteren Daten, gleichzeitige Zugriffe, Gesamtregeln."""
from __future__ import annotations

import builtins
import contextlib
import io
import json
import shutil
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from jarvis import server
from jarvis.config import DEFAULTS
from jarvis.core import Jarvis

SECRET = "z" * 48


def old_actions_db(path: Path) -> str:
    """actions.db genau im Format bis Version 4.2, mit einer offenen Aktion."""
    import hashlib
    import time
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute("""CREATE TABLE actions (id TEXT PRIMARY KEY, action_type TEXT, payload TEXT, reason TEXT, status TEXT,
                   created REAL, expires REAL, payload_hash TEXT, nonce TEXT, approver TEXT, result TEXT)""")
    payload = {"an": "alt@example.com", "text": "aus 4.2"}
    h = hashlib.sha256(json.dumps({"t": "send_email", "p": payload}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    con.execute("INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("a1b2c3d4e5", "send_email", json.dumps(payload), "alt", "pending", time.time(), time.time() + 3600,
                 h, "0" * 16, None, None))
    con.commit()
    con.close()
    return "a1b2c3d4e5"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "data"
        self.cfg = dict(DEFAULTS, data_dir=str(self.data), vault_dir=str(self.data / "vault"),
                        telegram={"allowed_user_ids": [1], "approval_chat_id": 1},
                        backup={"dir": str(self.tmp / "sicherungen")})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tables(self):
        con = sqlite3.connect(str(self.data / "actions.db"))
        try:
            return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()


class Upgrade(Base):
    def test_f1_reading_commands_do_not_change_old_action_database(self):
        old_actions_db(self.data / "actions.db")
        j = Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": SECRET}, channel=lambda *a: None)
        j.status()
        j.morning_briefing()
        self.assertEqual([a.id for a in j.gate.pending()], ["a1b2c3d4e5"])
        j.close()
        self.assertEqual(self.tables(), {"actions"})
        self.assertTrue(server.pending_upgrades(self.cfg))

    def test_f1_old_pending_action_still_works(self):
        aid = old_actions_db(self.data / "actions.db")
        j = Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": SECRET}, channel=lambda *a: None)
        self.addCleanup(j.close)
        ok, _ = j.gate.handle_callback(j.gate.callback_data("ok", aid), 1, 1)
        self.assertTrue(ok)
        self.assertIn("SIMULIERT", j.gate.execute(aid))

    def test_f1_first_new_action_adds_table_and_keeps_old_rows(self):
        old_actions_db(self.data / "actions.db")
        j = Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": SECRET}, channel=lambda *a: None)
        self.addCleanup(j.close)
        j.handle_text("/mail neu@example.com | Neu | Text")
        self.assertIn("action_meta", self.tables())
        self.assertEqual(len(j.gate.pending()), 2)
        self.assertEqual(server.pending_upgrades(self.cfg), [])

    def test_f1_web_start_asks_and_changes_nothing_on_no(self):
        import jarvis.__main__ as main
        from jarvis.__main__ import data_fingerprint
        old_actions_db(self.data / "actions.db")
        before = data_fingerprint(self.data)[1]
        orig_cfg, orig_input = main.load_config, builtins.input
        main.load_config = lambda *a, **k: self.cfg
        builtins.input = lambda *a, **k: "nein"
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                main.start_web()
        finally:
            main.load_config, builtins.input = orig_cfg, orig_input
        self.assertIn("action_meta", out.getvalue())
        self.assertIn("nichts verändert", out.getvalue())
        self.assertEqual(data_fingerprint(self.data)[1], before)
        self.assertFalse((self.tmp / "sicherungen").exists())

    def test_f1_yes_creates_full_backup_before_changes(self):
        import jarvis.__main__ as main
        old_actions_db(self.data / "actions.db")
        answers = iter(["ja"])
        orig = (main.load_config, builtins.input, main._auth_store, main.web_password)

        class NoAuth:
            def is_configured(self):
                return False
        main.load_config = lambda *a, **k: self.cfg
        builtins.input = lambda *a, **k: next(answers)
        main._auth_store = lambda: NoAuth()
        main.web_password = lambda: None            # Passwort-Abfrage hier nicht nötig: Start endet danach
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                main.start_web()
        finally:
            main.load_config, builtins.input, main._auth_store, main.web_password = orig
        backups = list((self.tmp / "sicherungen").glob("*.tar.gz"))
        self.assertEqual(len(backups), 1)
        names = {f["pfad"] for f in server.verify_backup(backups[0])["dateien"]}
        self.assertIn("actions.db", names)


class Concurrency(Base):
    def test_f2_web_skills_scheduler_and_proposals_at_the_same_time(self):
        j = Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": SECRET}, channel=lambda *a: None)
        self.addCleanup(j.close)
        j.skills.state.enable("research", {"internet.read"}, via="test")
        j.skills.state.enable("knowledge", set(["vault.read", "vault.inbox.write"]), via="test")
        errors = []

        def guard(fn):
            def run():
                try:
                    fn()
                except Exception as exc:  # noqa: BLE001
                    errors.append(repr(exc))
            return run

        def proposals():
            for i in range(10):
                a = j.gate.propose("send_email", {"an": f"x{i}@example.com"}, "Last",
                                   meta={"beschreibung": "Last", "kosten_eur": 0})
                j.gate.handle_callback(j.gate.callback_data("ok", a.id), 1, 1)
                j.gate.execute(a.id)

        def skills():
            for _ in range(10):
                j.skills.run("knowledge", "save_note", title="Last", text="x")

        def tasks():
            for _ in range(5):
                j.scheduler.run_now("lernen")

        def chat():
            for _ in range(10):
                j.llm.chat("S", [], "Hallo")

        threads = [threading.Thread(target=guard(f)) for f in (proposals, skills, tasks, chat) * 2]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        ok, msg = j.audit.verify()
        self.assertTrue(ok, msg)
        executed = j.gate.db.execute("SELECT count(*) FROM actions WHERE status='executed'").fetchone()[0]
        self.assertEqual(executed, 20)
        notes = list((self.data / "vault" / "00_Inbox" / "JARVIS").glob("*Last*.md"))
        self.assertEqual(len(notes), 20)                      # nichts überschrieben


if __name__ == "__main__":
    unittest.main()
