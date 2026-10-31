"""Sicherheitstests – ausführen mit:  python3 -m unittest -v"""
import datetime as dt
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from jarvis.approval import ApprovalError, ApprovalGate
from jarvis.audit import AuditLog
from jarvis.budget import BudgetExceeded, BudgetGuard
from jarvis.config import DEFAULTS
from jarvis.core import Jarvis
from jarvis.killswitch import KillSwitch, KillSwitchActive
from jarvis.notify import Notifier, is_quiet
from jarvis.obsidian import Vault
from jarvis.policy import PolicyViolation

ME, OTHER = 42, 666
SECRET = "x" * 48


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.audit = AuditLog(self.tmp / "audit.jsonl")
        self.kill = KillSwitch(self.tmp)
        self.gate = ApprovalGate(self.tmp / "a.db", SECRET, self.audit, self.kill, [ME], ME,
                                 ttl_minutes=60, forbidden_terms=["iban"])
        self.executed = []
        self.gate.register_handler("send_email", lambda p: self.executed.append(p) or "ok")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def proposed(self):
        return self.gate.propose("send_email", {"an": "a@b.de", "text": "Hallo"}, "Test")


class ApprovalTests(Base):
    def test_cannot_execute_without_approval(self):
        a = self.proposed()
        with self.assertRaises(ApprovalError):
            self.gate.execute(a.id)
        self.assertEqual(self.executed, [])

    def test_valid_approval_executes_once(self):
        a = self.proposed()
        ok, _ = self.gate.handle_callback(self.gate.callback_data("ok", a.id), ME, ME)
        self.assertTrue(ok)
        self.gate.execute(a.id)
        with self.assertRaises(ApprovalError):
            self.gate.execute(a.id)
        self.assertEqual(len(self.executed), 1)

    def test_foreign_user_rejected(self):
        a = self.proposed()
        ok, _ = self.gate.handle_callback(self.gate.callback_data("ok", a.id), OTHER, ME)
        self.assertFalse(ok)

    def test_wrong_chat_rejected(self):
        a = self.proposed()
        ok, _ = self.gate.handle_callback(self.gate.callback_data("ok", a.id), ME, 12345)
        self.assertFalse(ok)

    def test_forged_signature_rejected(self):
        a = self.proposed()
        ok, _ = self.gate.handle_callback(f"ok:{a.id}:{'A' * 20}", ME, ME)
        self.assertFalse(ok)

    def test_reject_button_cannot_be_turned_into_approve(self):
        a = self.proposed()
        sig = self.gate.callback_data("no", a.id).split(":")[2]
        ok, _ = self.gate.handle_callback(f"ok:{a.id}:{sig}", ME, ME)
        self.assertFalse(ok)

    def test_signature_bound_to_specific_action(self):
        a, b = self.proposed(), self.proposed()
        sig_a = self.gate.callback_data("ok", a.id).split(":")[2]
        ok, _ = self.gate.handle_callback(f"ok:{b.id}:{sig_a}", ME, ME)
        self.assertFalse(ok)

    def test_replay_rejected(self):
        a = self.proposed()
        data = self.gate.callback_data("ok", a.id)
        self.assertTrue(self.gate.handle_callback(data, ME, ME)[0])
        self.assertFalse(self.gate.handle_callback(data, ME, ME)[0])

    def test_expired_rejected(self):
        a = self.proposed()
        self.gate.db.execute("UPDATE actions SET expires=? WHERE id=?", (time.time() - 1, a.id))
        ok, _ = self.gate.handle_callback(self.gate.callback_data("ok", a.id), ME, ME)
        self.assertFalse(ok)

    def test_payload_tamper_after_approval_detected(self):
        a = self.proposed()
        self.gate.handle_callback(self.gate.callback_data("ok", a.id), ME, ME)
        self.gate.db.execute("UPDATE actions SET payload=? WHERE id=?", ('{"an": "boese@x.de", "text": "Hallo"}', a.id))
        with self.assertRaises(ApprovalError):
            self.gate.execute(a.id)
        self.assertEqual(self.executed, [])

    def test_forbidden_action_and_unknown_type(self):
        for t in ("purchase", "bank_access", "irgendwas_neues"):
            with self.assertRaises(PolicyViolation):
                self.gate.propose(t, {}, "x")

    def test_forbidden_term_blocked(self):
        with self.assertRaises(PolicyViolation):
            self.gate.propose("send_email", {"text": "Meine IBAN ist ..."}, "x")

    def test_killswitch_blocks_approval_and_execution(self):
        a = self.proposed()
        self.kill.activate()
        self.assertFalse(self.gate.handle_callback(self.gate.callback_data("ok", a.id), ME, ME)[0])
        with self.assertRaises(KillSwitchActive):
            self.gate.execute(a.id)

    def test_short_secret_refused(self):
        with self.assertRaises(ValueError):
            ApprovalGate(self.tmp / "b.db", "kurz", self.audit, self.kill, [ME])

    def test_callback_fits_telegram_limit(self):
        a = self.proposed()
        self.assertLessEqual(len(self.gate.callback_data("ok", a.id).encode()), 64)


class AuditTests(Base):
    def test_tampering_detected(self):
        self.audit.write("a", x=1)
        self.audit.write("b", x=2)
        self.assertTrue(self.audit.verify()[0])
        lines = self.audit.path.read_text().splitlines()
        lines[0] = lines[0].replace('"x": 1', '"x": 9')
        self.audit.path.write_text("\n".join(lines) + "\n")
        self.assertFalse(self.audit.verify()[0])


class BudgetTests(Base):
    def test_limits(self):
        b = BudgetGuard(self.tmp / "b.db", daily_eur=0.5, monthly_eur=1.0)
        b.check(0.4)
        b.record("x", 0.4)
        with self.assertRaises(BudgetExceeded):
            b.check(0.2)


class QuietHoursTests(Base):
    def test_is_quiet(self):
        at = lambda h: dt.datetime(2026, 1, 1, h, 0)
        self.assertTrue(is_quiet(at(23), "22:00", "07:00"))
        self.assertTrue(is_quiet(at(3), "22:00", "07:00"))
        self.assertFalse(is_quiet(at(7), "22:00", "07:00"))
        self.assertFalse(is_quiet(at(12), "22:00", "07:00"))

    def test_night_queues_normal_and_silences_urgent(self):
        sent = []
        n = Notifier(self.tmp / "n.db", "22:00", "07:00", "Europe/Berlin",
                     lambda t, s, b: sent.append((t, s)), clock=lambda: dt.datetime(2026, 1, 1, 2, 0))
        self.assertEqual(n.notify("info"), "queued")
        self.assertEqual(n.notify("wichtig", "urgent"), "sent_silent")
        self.assertEqual(sent, [("wichtig", True)])
        self.assertEqual(n.drain_queue(), ["info"])


class VaultTests(Base):
    def test_only_inbox_writable(self):
        v = Vault(self.tmp / "vault", ["00_Inbox/JARVIS"])
        v.init()
        self.assertTrue(v.write_draft("Test", "Inhalt").exists())
        with self.assertRaises(PermissionError):
            v.write_draft("X", "y", folder="01_Ziele")
        with self.assertRaises(PermissionError):
            v.write_draft("X", "y", folder="../../etc")

    def test_existing_notes_never_overwritten(self):
        v = Vault(self.tmp / "vault", ["00_Inbox/JARVIS"])
        v.init()
        first = v.write_draft("Gleich", "Original")
        second = v.write_draft("Gleich", "Neu")
        self.assertNotEqual(first, second)
        self.assertIn("Original", first.read_text())
        self.assertIn("Neu", second.read_text())

    def test_vault_has_no_edit_or_delete_functions(self):
        v = Vault(self.tmp / "vault", ["00_Inbox/JARVIS"])
        for name in ("delete", "remove", "edit", "update", "append", "overwrite"):
            self.assertFalse(hasattr(v, name), name)


class EndToEndTests(Base):
    def test_post_flow(self):
        cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                   telegram={"allowed_user_ids": [ME], "approval_chat_id": ME})
        msgs = []
        j = Jarvis(cfg, {"JARVIS_APPROVAL_SECRET": SECRET}, channel=lambda t, s, b: msgs.append(b))
        j.handle_text("/post Test")
        ok_data = msgs[-1][0][0][1]
        self.assertIn("⛔", j.on_button(ok_data, OTHER, OTHER))
        self.assertIn("SIMULIERT", j.on_button(ok_data, ME, ME))
        self.assertEqual(len(list((self.tmp / "d" / "sandbox" / "outbox").glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
