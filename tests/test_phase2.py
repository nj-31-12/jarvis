"""Sicherheitstests Phase 2, Schritt 1 – ausführen mit:  python3 -m unittest -v"""
import json
import re
import shutil
import tempfile
import threading
import unittest
import datetime as dt
from pathlib import Path

from jarvis.approval import ApprovalGate
from jarvis.audit import AuditLog
from jarvis.budget import BudgetExceeded, BudgetGuard
from jarvis.config import DEFAULTS, load_config
from jarvis.core import Jarvis
from jarvis.killswitch import KillSwitch
from jarvis.markdown_safe import render
from jarvis.notify import Notifier
from jarvis.persona import build_system_prompt
from jarvis.policy import APPROVAL, FORBIDDEN, PolicyViolation, classify
from jarvis.rotation import TopicRotation
from jarvis.speech import SilentTTS, VoiceProfile, speakable

ME = 42
WEB_USER = "inhaber"
SECRET = "y" * 48


def run_parallel(fn, n):
    results, threads = [], []
    lock = threading.Lock()

    def worker():
        r = fn()
        with lock:
            results.append(r)
    for _ in range(n):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return results


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.audit = AuditLog(self.tmp / "audit.jsonl")
        self.kill = KillSwitch(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def gate(self, web=False):
        g = ApprovalGate(self.tmp / "a.db", SECRET, self.audit, self.kill, [ME], ME,
                         web_approvals_enabled=web, allowed_web_users=[WEB_USER])
        g.register_handler("send_email", lambda p: "ok")
        return g


# ---------------------------------------------------------------- 1. Gleichzeitige Zugriffe
class ConcurrencyTests(Base):
    def test_parallel_approvals_only_one_wins(self):
        g = self.gate()
        a = g.propose("send_email", {"an": "a@b.de"}, "t")
        data = g.callback_data("ok", a.id)
        results = run_parallel(lambda: g.handle_callback(data, ME, ME)[0], 25)
        self.assertEqual(results.count(True), 1)

    def test_parallel_execution_only_once(self):
        g = self.gate()
        calls = []
        g.register_handler("send_email", lambda p: calls.append(1) or "ok")
        a = g.propose("send_email", {"an": "a@b.de"}, "t")
        g.handle_callback(g.callback_data("ok", a.id), ME, ME)

        def try_exec():
            try:
                g.execute(a.id)
                return True
            except Exception:
                return False
        self.assertEqual(run_parallel(try_exec, 25).count(True), 1)
        self.assertEqual(len(calls), 1)

    def test_parallel_budget_never_exceeds_limit(self):
        b = BudgetGuard(self.tmp / "b.db", daily_eur=1.0, monthly_eur=5.0)

        def spend():
            try:
                b.charge("x", 0.1)
                return True
            except BudgetExceeded:
                return False
        ok = run_parallel(spend, 40).count(True)
        self.assertLessEqual(b.spent_today(), 1.0 + 1e-9)
        self.assertEqual(ok, 10)

    def test_queue_loses_nothing_under_load(self):
        n = Notifier(self.tmp / "n.db", "00:00", "23:59", "Europe/Berlin", lambda *a: None,
                     clock=lambda: dt.datetime(2026, 1, 1, 3, 0))
        seen = []
        stop = threading.Event()

        def drainer():
            while not stop.is_set():
                seen.extend(n.drain_queue())
        t = threading.Thread(target=drainer)
        t.start()
        run_parallel(lambda: n.notify("info"), 60)
        stop.set()
        t.join()
        seen.extend(n.drain_queue())
        self.assertEqual(len(seen), 60)


# ---------------------------------------------------------------- 2. Nachrichtenprotokoll
class MessageLogTests(Base):
    def test_history_records_every_message_with_mode(self):
        n = Notifier(self.tmp / "n.db", "22:00", "07:00", "Europe/Berlin", lambda *a: None,
                     clock=lambda: dt.datetime(2026, 1, 1, 2, 0))
        n.notify("leise", "normal")
        n.notify("wichtig", "urgent", action_id="abc")
        h = n.history()
        self.assertEqual([m["mode"] for m in h], ["queued", "sent_silent"])
        self.assertEqual(h[1]["action_id"], "abc")
        self.assertEqual(n.history(after_id=h[0]["id"])[0]["text"], "wichtig")


# ---------------------------------------------------------------- 3. Freigaben im Browser
class WebApprovalTests(Base):
    def test_disabled_by_default(self):
        g = self.gate(web=False)
        a = g.propose("send_email", {"an": "a@b.de"}, "t")
        tok = g.web_token("ok", a.id, "s1")
        self.assertFalse(g.handle_web_decision("ok", a.id, tok, WEB_USER, "s1", True)[0])

    def test_requires_second_factor_for_approval(self):
        g = self.gate(web=True)
        a = g.propose("send_email", {"an": "a@b.de"}, "t")
        tok = g.web_token("ok", a.id, "s1")
        self.assertFalse(g.handle_web_decision("ok", a.id, tok, WEB_USER, "s1", False)[0])
        self.assertTrue(g.handle_web_decision("ok", a.id, tok, WEB_USER, "s1", True)[0])

    def test_reject_works_without_second_factor(self):
        g = self.gate(web=True)
        a = g.propose("send_email", {"an": "a@b.de"}, "t")
        self.assertTrue(g.handle_web_decision("no", a.id, g.web_token("no", a.id, "s1"), WEB_USER, "s1", False)[0])

    def test_foreign_web_user_rejected(self):
        g = self.gate(web=True)
        a = g.propose("send_email", {"an": "a@b.de"}, "t")
        tok = g.web_token("ok", a.id, "s1")
        self.assertFalse(g.handle_web_decision("ok", a.id, tok, "angreifer", "s1", True)[0])

    def test_token_bound_to_session(self):
        g = self.gate(web=True)
        a = g.propose("send_email", {"an": "a@b.de"}, "t")
        tok = g.web_token("ok", a.id, "sitzung-A")
        self.assertFalse(g.handle_web_decision("ok", a.id, tok, WEB_USER, "sitzung-B", True)[0])

    def test_unicode_signature_does_not_crash(self):
        g = self.gate(web=True)
        a = g.propose("send_email", {"an": "a@b.de"}, "t")
        self.assertFalse(g.handle_callback(f"ok:{a.id}:ääääääää", ME, ME)[0])
        self.assertFalse(g.handle_web_decision("ok", a.id, "💥", WEB_USER, "s1", True)[0])

    def test_telegram_signature_not_valid_in_browser_and_vice_versa(self):
        g = self.gate(web=True)
        a = g.propose("send_email", {"an": "a@b.de"}, "t")
        tg_sig = g.callback_data("ok", a.id).split(":")[2]
        self.assertFalse(g.handle_web_decision("ok", a.id, tg_sig, WEB_USER, "", True)[0])
        web_tok = g.web_token("ok", a.id, "s1")
        self.assertFalse(g.handle_callback(f"ok:{a.id}:{web_tok}", ME, ME)[0])

    def test_end_to_end_web_approval_executes_simulated(self):
        cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                   telegram={"allowed_user_ids": [ME], "approval_chat_id": ME},
                   web=dict(DEFAULTS["web"], approvals_enabled=True, users=[WEB_USER]))
        j = Jarvis(cfg, {"JARVIS_APPROVAL_SECRET": SECRET}, channel=lambda *a: None)
        j.handle_text("/mail a@b.de | Hallo | Test")
        action = j.gate.pending()[0]
        tok = j.gate.web_token("ok", action.id, "s1")
        self.assertIn("⛔", j.on_web_decision("ok", action.id, tok, WEB_USER, "s1", False))
        self.assertIn("SIMULIERT", j.on_web_decision("ok", action.id, tok, WEB_USER, "s1", True))


# ---------------------------------------------------------------- 4. Sichere Anzeige (XSS)
ATTACKS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<svg/onload=alert(1)>",
    "[klick](javascript:alert(1))",
    "[klick](JaVaScRiPt:alert(1))",
    "[klick](data:text/html;base64,PHNjcmlwdD4=)",
    "[klick](vbscript:msgbox)",
    '[klick](https://a.de"onmouseover="alert(1))',
    "![x](https://boese.example/tracker.png)",
    "`<script>alert(1)</script>`",
    "```\n<script>alert(1)</script>\n```",
    "| <b onclick=alert(1)>x</b> | y |\n|---|---|\n| <iframe src=x> | z |",
    "---\ntitel: <script>alert(1)</script>\n---\nText",
    "**<img src=x onerror=alert(1)>**",
    "[[<script>x</script>]]",
    "> <a href=javascript:alert(1)>zitat</a>",
]


class SafeMarkdownTests(unittest.TestCase):
    def test_no_active_html_survives(self):
        for attack in ATTACKS:
            out = render(attack)
            with self.subTest(attack=attack):
                self.assertNotRegex(out, r"<\s*(script|img|svg|iframe|b\s|object|embed)", out)
                self.assertNotRegex(out, r"<[^>]*\son\w+\s*=", out)          # kein Event-Handler in einem Tag
                for href in re.findall(r'href="([^"]*)"', out):
                    self.assertTrue(href.startswith(("http://", "https://")), href)

    def test_normal_formatting_kept(self):
        out = render("# Titel\n\n**fett** und *kursiv*\n\n- [ ] Aufgabe\n- [x] Fertig\n\n[Quelle](https://ihk.de/x_y_z)")
        self.assertIn("<h1>Titel</h1>", out)
        self.assertIn("<strong>fett</strong>", out)
        self.assertIn("<em>kursiv</em>", out)
        self.assertIn('href="https://ihk.de/x_y_z"', out)   # Unterstriche in URLs bleiben intakt
        self.assertIn("☐", out)
        self.assertIn("☑", out)


# ---------------------------------------------------------------- 5. Regeln, Konfiguration, Rotation, Stimme
class RuleTests(Base):
    def test_new_actions_need_approval(self):
        for t in ("send_message", "connect_account", "install_program", "upload_data",
                  "activate_paid_service", "modify_file", "delete_file", "publish_post", "send_email"):
            self.assertEqual(classify(t), APPROVAL, t)

    def test_money_and_bank_forbidden(self):
        for t in ("spend_money", "purchase", "payment", "bank_access"):
            self.assertEqual(classify(t), FORBIDDEN, t)
        g = self.gate()
        with self.assertRaises(PolicyViolation):
            g.propose("spend_money", {"betrag": 5}, "t")

    def test_web_must_stay_local(self):
        p = self.tmp / "c.json"
        p.write_text(json.dumps({"web": {"host": "0.0.0.0"}}))
        with self.assertRaises(ValueError):
            load_config(p)
        p.write_text(json.dumps({"web": {"host": "127.0.0.1"}}))
        self.assertEqual(load_config(p)["web"]["host"], "127.0.0.1")

    def test_rotation_covers_all_areas(self):
        r = TopicRotation(self.tmp / "r.db")
        areas = list(DEFAULTS["business_areas"])
        seen = []
        for _ in range(-(-len(areas) // 3)):     # so viele Nächte, dass alle Bereiche einmal drankommen
            for t in r.pick(areas, 3):
                r.mark_done(t)
                seen.append(t)
        self.assertEqual(set(seen), set(areas))
        self.assertEqual(seen[:len(areas)], list(dict.fromkeys(seen[:len(areas)])))  # keine Wiederholung, bevor alle dran waren

    def test_persona_prompt_contains_all_areas_and_rules(self):
        prompt = build_system_prompt(DEFAULTS)
        for area in DEFAULTS["business_areas"]:
            self.assertIn(area, prompt)
        self.assertIn("Freigabeschicht", prompt)

    def test_speech_prepared_but_silent(self):
        self.assertEqual(SilentTTS().synthesize("Hallo", VoiceProfile()), b"")
        text = speakable("# Titel 🚀\n| a | b |\n- **Punkt** mit [Link](https://x.de)")
        self.assertNotIn("|", text)
        self.assertNotIn("🚀", text)
        self.assertIn("Punkt mit Link", text)


if __name__ == "__main__":
    unittest.main()
