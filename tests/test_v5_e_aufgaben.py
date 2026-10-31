"""Version 5 · Phase E: lokaler Aufgabenplaner mit Testmodus."""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlencode

from jarvis import web_auth as wa
from jarvis.config import DEFAULTS, PROJECT_ROOT, load_config
from jarvis.core import Jarvis
from jarvis.scheduler import (ABORTED, DONE, FAILED, MISSED, TASKS, Scheduler, Task, TaskError, run_forever)
from jarvis.web import WebApp

HOST = "127.0.0.1:8765"
PW = "Kaffee-Hantel-Duft-Motor-42"


def ts(y, mo, d, h, mi=0):
    return dt.datetime(y, mo, d, h, mi).timestamp()


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


class Base(unittest.TestCase):
    mode = "test"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                        telegram={"allowed_user_ids": [1], "approval_chat_id": 1}, scheduler={"mode": self.mode})
        self.sent = []
        self.j = Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": "z" * 48},
                        channel=lambda text, silent, buttons: self.sent.append(text))
        self.addCleanup(self.j.close)
        self.clock = Clock(ts(2026, 11, 2, 6, 59))      # Montag, 06:59
        self.calls = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def scheduler(self, tasks=None, db="t.db", mode=None):
        s = Scheduler(self.j, self.tmp / db, mode=mode or self.mode, clock=self.clock, tasks=tasks)
        self.addCleanup(s.close)
        return s

    def counting_task(self, fail=False, time="07:00", days=tuple(range(7))):
        def run(j):
            self.calls.append(1)
            if fail:
                raise ValueError("geplanter Testfehler")
            return "Zähler", "ok"
        return {"z": Task("z", "Zähler", "Test", time, days, run)}

    def outputs(self):
        folder = self.tmp / "d" / "aufgaben-test"
        return sorted(folder.glob("*.md")) if folder.exists() else []


class Catalog(Base):
    def test_e1_all_example_tasks_run_in_test_mode_without_side_effects(self):
        self.assertEqual(set(TASKS), {"briefing", "offene_aufgaben", "projekte", "lernen", "ideen", "muster"})
        vault = Path(self.cfg["vault_dir"])
        before = sorted(p.relative_to(vault).as_posix() for p in vault.rglob("*.md"))
        s = self.scheduler()
        for tid in TASKS:
            with self.subTest(tid):
                r = s.run_now(tid)
                self.assertEqual(r["status"], DONE, r)
                self.assertTrue(r["text"].strip())
        after = sorted(p.relative_to(vault).as_posix() for p in vault.rglob("*.md"))
        self.assertEqual(before, after)                     # Testmodus: keine Notizen im Vault
        self.assertEqual(len(self.outputs()), len(TASKS))
        self.assertEqual(self.sent, [])                     # keine Meldungen
        self.assertEqual(self.j.gate.pending(), [])

    def test_e1_task_ids_fixed_in_code(self):
        for t in TASKS.values():
            self.assertRegex(t.id, r"^[a-z_]+$")
            self.assertRegex(t.time, r"^([01]\d|2[0-3]):[0-5]\d$")
            self.assertTrue(set(t.weekdays) <= set(range(7)))


class NoDoubleExecution(Base):
    def test_e2_same_slot_runs_once(self):
        s = self.scheduler(self.counting_task())
        self.clock.t = ts(2026, 11, 2, 7, 0)
        s.tick()
        s.tick()
        self.clock.t = ts(2026, 11, 2, 9, 0)
        s.tick()
        self.assertEqual(len(self.calls), 1)

    def test_e2_parallel_schedulers_sharing_database_run_once(self):
        tasks = self.counting_task()
        a = self.scheduler(tasks)
        b = self.scheduler(tasks)                           # zweite Verbindung = wie ein zweiter Prozess
        self.clock.t = ts(2026, 11, 2, 7, 1)
        threads = [threading.Thread(target=x.tick) for x in (a, b) * 4]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(self.calls), 1)

    def test_e14_manual_runs_are_separate(self):
        s = self.scheduler(self.counting_task())
        s.run_now("z")
        s.run_now("z")
        self.assertEqual(len(self.calls), 2)


class Timing(Base):
    def test_e3_daily_and_weekday_slots(self):
        s = self.scheduler(self.counting_task(days=(0, 2)))   # Mo, Mi
        s.tick()                                              # 06:59 → noch nicht
        self.assertEqual(self.calls, [])
        self.clock.t = ts(2026, 11, 2, 7, 0)
        s.tick()
        self.clock.t = ts(2026, 11, 3, 7, 30)                # Dienstag: kein Termin
        s.tick()
        self.clock.t = ts(2026, 11, 4, 7, 5)                 # Mittwoch
        s.tick()
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(s.next_run(s.tasks["z"]).strftime("%a %H:%M"), dt.datetime(2026, 11, 9, 7).strftime("%a %H:%M"))

    def test_e3_missed_slot_caught_up_within_6_hours_only(self):
        s = self.scheduler(self.counting_task())
        self.clock.t = ts(2026, 11, 2, 12, 0)                # 5 Std. zu spät → nachholen
        s.tick()
        self.assertEqual(len(self.calls), 1)
        self.clock.t = ts(2026, 11, 3, 20, 0)                # 13 Std. zu spät → verpasst, nicht nachholen
        s.tick()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(s.last_runs(1)[0]["status"], MISSED)


class PauseAndStatus(Base):
    def test_e4_paused_task_does_not_run_until_resumed(self):
        s = self.scheduler(self.counting_task())
        s.pause("z")
        self.clock.t = ts(2026, 11, 2, 7, 0)
        s.tick()
        self.assertEqual(self.calls, [])
        self.assertEqual(s.overview()[0]["status"], "pausiert")
        s.resume("z")
        s.tick()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(s.overview()[0]["last"]["status"], DONE)
        with self.assertRaises(TaskError):
            s.pause("gibtsnicht")

    def test_e5_failures_are_logged_and_three_in_a_row_pause(self):
        s = self.scheduler(self.counting_task(fail=True))
        for day in (2, 3, 4):
            self.clock.t = ts(2026, 11, day, 7, 0)
            r = s.tick()
            self.assertEqual(r[0]["status"], FAILED)
        self.assertEqual(s.overview()[0]["status"], "pausiert")
        self.assertIn("automatisch pausiert", s.overview()[0]["note"])
        self.clock.t = ts(2026, 11, 5, 7, 0)
        self.assertEqual(s.tick(), [])
        log = self.j.audit.path.read_text(encoding="utf-8")
        self.assertIn('"task_failed"', log)
        self.assertIn("ValueError", log)
        self.assertNotIn("geplanter Testfehler", log)     # Protokoll: nur Fehlerart

    def test_e5_success_resets_failure_count(self):
        state = {"fail": True}

        def run(j):
            if state["fail"]:
                raise RuntimeError("x")
            return "t", "ok"
        s = self.scheduler({"z": Task("z", "Z", "T", "07:00", tuple(range(7)), run)})
        for day, fail in ((2, True), (3, True), (4, False), (5, True), (6, True)):
            state["fail"] = fail
            self.clock.t = ts(2026, 11, day, 7, 0)
            s.tick()
        self.assertEqual(s.overview()[0]["status"], "aktiv")

    def test_e6_interrupted_run_is_marked_and_not_repeated(self):
        s = self.scheduler(self.counting_task())
        s.db.execute("INSERT INTO runs (task, slot, mode, started, status) VALUES ('z', '2026-11-02 07:00', 'test', ?, "
                     "'läuft')", (ts(2026, 11, 2, 7, 0),))
        self.clock.t = ts(2026, 11, 2, 7, 45)
        s.tick()
        self.assertEqual(self.calls, [])
        self.assertEqual(s.last_runs(1)[0]["status"], ABORTED)


class Safety(Base):
    def test_e7_killswitch_stops_planner(self):
        s = self.scheduler(self.counting_task())
        self.j.kill.activate("Test")
        self.clock.t = ts(2026, 11, 2, 7, 0)
        self.assertEqual(s.tick(), [])
        self.assertEqual(s.run_now("z")["status"], FAILED)
        self.assertEqual(self.calls, [])

    def test_e8_tasks_never_execute_external_actions(self):
        src = (PROJECT_ROOT / "jarvis" / "scheduler.py").read_text(encoding="utf-8")
        self.assertNotIn("gate.execute", src)
        self.assertNotIn("handle_callback", src)
        s = self.scheduler()
        with mock.patch.object(self.j.gate, "execute", side_effect=AssertionError("Ausführung versucht")):
            for tid in TASKS:
                self.assertEqual(s.run_now(tid)["status"], DONE)
        self.assertFalse((self.tmp / "d" / "sandbox" / "outbox").exists() and
                         any((self.tmp / "d" / "sandbox" / "outbox").iterdir()))

    def test_e8_model_access_still_goes_through_allowlist(self):
        class Unknown:
            name = "unbekannt"
            is_test_mode = False
            cost_per_call_eur = 0.0

            def complete(self, task, text):
                raise AssertionError("darf nie aufgerufen werden")
        self.j.llm.model = Unknown()
        self.j.vault.write_draft("Idee Testidee", "x", ["geschäftsidee"])
        r = self.scheduler().run_now("ideen")
        self.assertEqual(r["status"], FAILED)
        self.assertIn("ModelBlocked", r["message"])

    def test_e10_open_tasks_skip_confidential_notes(self):
        vault = Path(self.cfg["vault_dir"])
        (vault / "90_Privat").mkdir(parents=True, exist_ok=True)
        (vault / "90_Privat" / "Geheim.md").write_text("# Geheim\n- [ ] Gehalt verhandeln 1234", encoding="utf-8")
        (vault / "02_Projekte").mkdir(parents=True, exist_ok=True)
        (vault / "02_Projekte" / "Shop.md").write_text("# Shop\n- [ ] Produktfotos machen", encoding="utf-8")
        self.j.kb.invalidate()
        text = self.scheduler().run_now("offene_aufgaben")["text"]
        self.assertIn("Produktfotos", text)
        self.assertNotIn("1234", text)

    def test_e12_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            Scheduler(self.j, self.tmp / "x.db", mode="vollgas")
        f = self.tmp / "c.json"
        f.write_text(json.dumps({"scheduler": {"mode": "vollgas"}}), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_config(f)

    def test_e13_loop_stops_cleanly(self):
        s = self.scheduler(self.counting_task())
        self.clock.t = ts(2026, 11, 2, 7, 0)
        ticks = []
        run_forever(self.j, s, interval=0, stop=lambda: len(ticks.append(1) or ticks) > 2)
        self.assertEqual(len(self.calls), 1)


class ActiveMode(Base):
    mode = "aktiv"

    def test_e9_active_mode_writes_only_new_inbox_notes_and_notifies(self):
        vault = Path(self.cfg["vault_dir"])
        before = set(p.relative_to(vault).as_posix() for p in vault.rglob("*.md"))
        s = self.scheduler()
        self.clock.t = ts(2026, 11, 2, 19, 0)
        s.tick()
        new = set(p.relative_to(vault).as_posix() for p in vault.rglob("*.md")) - before
        self.assertTrue(new)
        self.assertTrue(all(n.startswith("00_Inbox/JARVIS/") for n in new))
        self.assertTrue(any("fertig" in m for m in self.sent))
        self.assertEqual(self.j.gate.pending(), [])

    def test_e9_manual_run_is_always_test_mode(self):
        vault = Path(self.cfg["vault_dir"])
        before = set(vault.rglob("*.md"))
        self.scheduler().run_now("lernen")
        self.assertEqual(set(vault.rglob("*.md")), before)


class TasksPage(Base):
    def setUp(self):
        super().setUp()
        store = wa.AuthStore(self.tmp / "d", self.j.audit, iterations=1000)
        store.set_password("inhaber", PW)
        self.addCleanup(store.close)
        self.app = WebApp(self.cfg, store, self.j)
        nonce = re.search(r'name="nonce" value="([^"]+)"', self.req("GET", "/login").body.decode()).group(1)
        r = self.req("POST", "/login", {"username": "inhaber", "password": PW, "nonce": nonce})
        self.sid = r.header("Set-Cookie").split(";")[0].split("=", 1)[1]
        self.csrf = re.search(r'name="csrf" value="([^"]+)"', self.req("GET", "/").body.decode()).group(1)

    def req(self, method, path, body=None):
        h = {"Host": HOST, "Origin": f"http://{HOST}"}
        if getattr(self, "sid", None):
            h["Cookie"] = f"jarvis_session={self.sid}"
        return self.app.handle(method, path, h, urlencode(body).encode() if body is not None else b"")

    def test_e11_page_pause_and_test_run(self):
        body = self.req("GET", "/aufgaben").body.decode()
        self.assertIn("Testmodus", body)
        self.assertIn("Lernaufgabe für die Ausbildung", body)
        self.req("POST", "/aufgaben/pause", {"csrf": self.csrf, "task": "lernen"})
        self.assertIn("pausiert", self.req("GET", "/aufgaben").body.decode())
        self.req("POST", "/aufgaben/test", {"csrf": self.csrf, "task": "lernen"})
        body = self.req("GET", "/aufgaben").body.decode()
        self.assertIn("Thema heute", body)
        self.assertEqual(self.req("POST", "/aufgaben/test", {"csrf": "falsch", "task": "lernen"}).status, 403)
        self.req("POST", "/aufgaben/test", {"csrf": self.csrf, "task": "../boese"})
        self.assertIn("Unbekannte Aufgabe", self.req("GET", "/aufgaben").body.decode())


if __name__ == "__main__":
    unittest.main()
