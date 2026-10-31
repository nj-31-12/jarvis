"""Version 5 · Phase C: Skill-System mit sicheren Testadaptern."""
from __future__ import annotations

import ast
import json
import re
import shutil
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlencode

from jarvis import approval as ap
from jarvis import policy
from jarvis import web_auth as wa
from jarvis.config import DEFAULTS, PROJECT_ROOT
from jarvis.core import Jarvis
from jarvis.skills import CATALOG, PERMISSIONS, SkillBlocked, SkillError, SkillRunner, SkillSpec, SkillState
from jarvis.skills.base import Operation, SkillResult
from jarvis.web import WebApp

HOST = "127.0.0.1:8765"
PW = "Kaffee-Hantel-Duft-Motor-42"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                        telegram={"allowed_user_ids": [1], "approval_chat_id": 1})
        self.j = Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": "z" * 48}, channel=lambda *a: None)
        self.addCleanup(self.j.close)
        self.s = self.j.skills

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def approve(self, action):
        ok, msg = self.j.gate.handle_callback(self.j.gate.callback_data("ok", action.id), 1, 1)
        self.assertTrue(ok, msg)
        return self.j.gate.execute(action.id)

    def enable(self, skill):
        self.approve(self.s.request_enable(skill, self.j.gate))

    def log(self):
        return self.j.audit.path.read_text(encoding="utf-8")

    def outbox(self):
        return list((self.tmp / "d" / "sandbox" / "outbox").glob("*.json"))


class Catalog(Base):
    def test_c1_six_skills_with_complete_description(self):
        self.assertEqual(sorted(CATALOG), ["briefing", "calendar", "gmail", "knowledge", "research", "shopify"])
        for spec in CATALOG.values():
            with self.subTest(spec.id):
                self.assertRegex(spec.id, r"^[a-z][a-z0-9_]+$")
                self.assertTrue(spec.name and spec.description)
                self.assertTrue(spec.permissions)
                self.assertTrue(set(spec.permissions) <= set(PERMISSIONS))
                for name, op in spec.operations.items():
                    self.assertIn(op.kind, ("lesen", "entwurf", "vorschlag"))
                    if op.kind == "vorschlag":
                        self.assertTrue(op.permission.endswith(".propose"))
                self.assertEqual([lvl for lvl, _ in self.s.security_check(spec.id)], ["ok"])

    def test_c1_skill_modules_import_no_network_libraries(self):
        banned = {"socket", "urllib", "http", "requests", "ssl", "smtplib", "imaplib", "ftplib", "subprocess"}
        for f in (PROJECT_ROOT / "jarvis" / "skills").glob("*.py"):
            tree = ast.parse(f.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module or ""]
                for n in names:
                    with self.subTest(file=f.name, module=n):
                        self.assertNotIn(n.split(".")[0], banned)


class NoAutomaticActivation(Base):
    def test_c2_all_skills_off_and_blocked(self):
        for spec in CATALOG.values():
            self.assertFalse(self.s.is_enabled(spec.id))
            op = next(iter(spec.operations))
            with self.assertRaises(SkillBlocked):
                self.s.run(spec.id, op)
        self.assertIn("skill_blocked", self.log())

    def test_c3_activation_only_through_approval(self):
        a = self.s.request_enable("calendar", self.j.gate)
        self.assertEqual(a.action_type, "enable_skill")
        self.assertIn("calendar.read", " ".join(a.meta["daten"]))
        self.assertFalse(self.s.is_enabled("calendar"))           # Antrag allein schaltet nichts ein
        self.approve(a)
        self.assertTrue(self.s.is_enabled("calendar"))
        self.assertEqual(self.s.state.get("calendar")[1], set(CATALOG["calendar"].permissions))
        self.assertIn("Heute", self.s.run("calendar", "list_today").text)

    def test_c3_rejected_request_keeps_skill_off(self):
        a = self.s.request_enable("gmail", self.j.gate)
        self.j.gate.handle_callback(self.j.gate.callback_data("no", a.id), 1, 1)
        self.assertFalse(self.s.is_enabled("gmail"))

    def test_c4_enable_handler_rejects_foreign_permissions_and_real_adapters(self):
        with self.assertRaises(SkillBlocked):
            self.s.handle_enable({"skill": "research", "berechtigungen": ["mail.read"], "adapter": "test"})
        with self.assertRaises(SkillBlocked):
            self.s.handle_enable({"skill": "research", "berechtigungen": ["internet.read"], "adapter": "echt"})
        with self.assertRaises(SkillBlocked):
            self.s.handle_enable({"skill": "gibtsnicht", "berechtigungen": ["x"], "adapter": "test"})
        self.assertFalse(self.s.is_enabled("research"))

    def test_c5_disable_is_immediate_and_revokes_everything(self):
        self.enable("research")
        self.s.disable("research", via="test")
        self.assertEqual(self.s.state.get("research"), (False, set()))
        with self.assertRaises(SkillBlocked):
            self.s.run("research", "search", query="Shopify")

    def test_c6_missing_permission_blocks_and_grant_needs_approval(self):
        self.s.state.enable("gmail", {"mail.read"}, via="test")       # nur Lesen erteilt
        self.s.run("gmail", "list_unread")
        with self.assertRaises(SkillBlocked) as ctx:
            self.s.run("gmail", "draft_reply", message_id="m1", text="Danke!")
        self.assertIn("mail.draft", str(ctx.exception))
        a = self.j.gate.propose("grant_permission", {"skill": "gmail", "berechtigungen": ["mail.draft"]}, "mehr Rechte",
                                meta={"beschreibung": "Gmail darf Entwürfe schreiben", "kosten_eur": 0})
        self.assertEqual(policy.classify("grant_permission"), policy.APPROVAL)
        self.approve(a)
        self.assertIn("nicht gesendet", self.s.run("gmail", "draft_reply", message_id="m1", text="Danke!").text)

    def test_c18_switched_off_skill_with_leftover_permissions_stays_blocked(self):
        self.s.state.enable("research", {"internet.read"}, via="test")
        self.s.state.db.execute("UPDATE skill_state SET enabled=0 WHERE skill='research'")   # Rechte noch eingetragen
        with self.assertRaises(SkillBlocked):
            self.s.run("research", "search", query="x")

    def test_c18_corrupted_state_means_no_permissions(self):
        self.s.state.enable("research", {"internet.read"}, via="test")
        self.s.state.db.execute("UPDATE skill_state SET permissions='kaputt{' WHERE skill='research'")
        with self.assertRaises(SkillBlocked):
            self.s.run("research", "search", query="x")


class ProposalsNeedApproval(Base):
    def test_c7_external_actions_are_only_proposed(self):
        for skill in ("gmail", "calendar", "shopify"):
            self.enable(skill)
        r1 = self.s.run("gmail", "propose_send", to="kunde@example.com", subject="Angebot", text="Hallo")
        r2 = self.s.run("calendar", "propose_event", title="Training", date="2026-11-02", time="18:00")
        r3 = self.s.run("shopify", "propose_price_change", product_id="p1", new_price=19)
        pend = {a.id: a for a in self.j.gate.pending()}
        for r, t in ((r1, "send_email"), (r2, "calendar_write"), (r3, "shopify_update_product")):
            self.assertIn(r.proposal_id, pend)
            self.assertEqual(pend[r.proposal_id].action_type, t)
            self.assertIsNotNone(pend[r.proposal_id].meta)
        self.assertEqual(self.outbox(), [])           # nichts ausgeführt
        self.assertEqual(pend[r3.proposal_id].payload["preis_neu"], 19.0)

    def test_c7_invalid_input_gives_clear_error_and_no_proposal(self):
        for skill in ("gmail", "calendar", "shopify"):
            self.enable(skill)
        cases = [("gmail", "propose_send", dict(to="kein-empfaenger", subject="x", text="y")),
                 ("calendar", "propose_event", dict(title="x", date="morgen", time="18:00")),
                 ("calendar", "propose_event", dict(title="x", date="2026-11-02", time="25:99")),
                 ("shopify", "propose_price_change", dict(product_id="p9", new_price=5)),
                 ("shopify", "propose_price_change", dict(product_id="p1", new_price=-5)),
                 ("gmail", "draft_reply", dict(message_id="m99", text="x"))]
        for skill, op, params in cases:
            with self.subTest(op=op, params=params):
                with self.assertRaises(SkillError):
                    self.s.run(skill, op, **params)
        self.assertEqual(self.j.gate.pending(), [])
        self.assertIn("skill_failed", self.log())

    def test_c8_forbidden_terms_block_proposal(self):
        self.enable("gmail")
        with self.assertRaises(policy.PolicyViolation):
            self.s.run("gmail", "propose_send", to="a@example.com", subject="Daten", text="Hier meine IBAN und PIN")
        self.assertEqual(self.j.gate.pending(), [])
        self.assertIn("skill_blocked", self.log())

    def test_c12_unknown_or_oversized_parameters_rejected(self):
        self.enable("research")
        with self.assertRaises(SkillBlocked):
            self.s.run("research", "search", query="x", url="https://evil.example")
        with self.assertRaises(SkillBlocked):
            self.s.run("research", "search", query="x" * 5000)
        with self.assertRaises(SkillBlocked):
            self.s.run("research", "search", query=["liste"])


class SafetyAndErrors(Base):
    def test_c9_no_network_during_any_skill_operation(self):
        for skill in CATALOG:
            self.enable(skill)
        calls = {"research": [("search", {"query": "Shopify"})],
                 "gmail": [("list_unread", {}), ("draft_reply", {"message_id": "m1", "text": "Hi"}),
                           ("propose_send", {"to": "a@example.com", "subject": "s", "text": "t"})],
                 "calendar": [("list_today", {}), ("list_week", {}),
                              ("propose_event", {"title": "T", "date": "2026-11-02", "time": "10:00"})],
                 "shopify": [("list_products", {}), ("propose_price_change", {"product_id": "p2", "new_price": 35})],
                 "knowledge": [("search", {"query": "Ziel"}), ("open_goals", {}),
                               ("save_note", {"title": "Test", "text": "Inhalt"})],
                 "briefing": [("compose", {})]}
        self.assertEqual(set(calls), set(CATALOG))
        for skill, ops in calls.items():
            self.assertEqual({o for o, _ in ops}, set(CATALOG[skill].operations))

        def no_net(*a, **k):
            raise AssertionError("Netzwerkzugriff versucht!")
        with mock.patch.object(socket.socket, "connect", no_net), \
                mock.patch.object(socket, "create_connection", no_net), \
                mock.patch.object(socket, "getaddrinfo", no_net):
            for skill, ops in calls.items():
                for op, params in ops:
                    self.s.run(skill, op, **params)

    def test_c10_unexpected_adapter_error_is_contained_and_logged_without_details(self):
        class Broken:
            connects_account = False
            uses_network = False

            def __init__(self, ctx):
                pass

            def boom(self):
                raise KeyError("geheimer-interner-wert")
        catalog = {"kaputt": SkillSpec("kaputt", "Kaputt", "Test", {"boom": Operation("internet.read", "lesen", "x")},
                                       Broken)}
        state = SkillState(self.tmp / "s2.db", self.j.audit)
        self.addCleanup(state.close)
        runner = SkillRunner(catalog, state, self.j, self.j.audit, self.j.kill)
        state.enable("kaputt", {"internet.read"}, via="test")
        with self.assertRaises(SkillError) as ctx:
            runner.run("kaputt", "boom")
        self.assertIn("nichts gesendet", str(ctx.exception))
        self.assertIn("KeyError", self.log())
        self.assertNotIn("geheimer-interner-wert", self.log())

    def test_c11_adapter_with_account_connection_is_blocked_everywhere(self):
        class RealAdapter:
            connects_account = True
            uses_network = True

            def __init__(self, ctx):
                pass

            def read(self):
                return SkillResult("echt", "read", "nie")
        catalog = {"echt": SkillSpec("echt", "Echt", "Test", {"read": Operation("mail.read", "lesen", "x")},
                                     RealAdapter)}
        state = SkillState(self.tmp / "s3.db", self.j.audit)
        self.addCleanup(state.close)
        runner = SkillRunner(catalog, state, self.j, self.j.audit, self.j.kill)
        self.assertIn("fehler", [lvl for lvl, _ in runner.security_check("echt")])
        with self.assertRaises(SkillBlocked):
            runner.request_enable("echt", self.j.gate)
        state.enable("echt", {"mail.read"}, via="manipuliert")      # selbst wenn jemand die Datei ändert …
        with self.assertRaises(SkillBlocked):
            runner.run("echt", "read")                              # … läuft er nicht

    def test_c11_each_adapter_flag_blocks_on_its_own(self):
        for flags in ({"connects_account": True, "uses_network": False},
                      {"connects_account": False, "uses_network": True}, {}):
            with self.subTest(flags):
                Adapter = type("Adapter", (), dict(flags, __init__=lambda self, ctx: None))
                catalog = {"x": SkillSpec("x", "X", "Test", {"read": Operation("vault.read", "lesen", "x")}, Adapter)}
                state = SkillState(self.tmp / f"s{len(flags)}{sorted(flags.items())[0][1] if flags else ''}.db")
                self.addCleanup(state.close)
                runner = SkillRunner(catalog, state, self.j, self.j.audit, self.j.kill)
                self.assertIn("fehler", [lvl for lvl, _ in runner.security_check("x")])

    def test_c13_killswitch_blocks_skills(self):
        self.enable("research")
        self.j.kill.activate("Test")
        with self.assertRaises(Exception):
            self.s.run("research", "search", query="x")

    def test_c14_rate_limit(self):
        self.enable("research")
        with self.assertRaises(SkillBlocked):
            for _ in range(40):
                self.s.run("research", "search", query="Shopify")

    def test_c20_log_contains_no_mail_content(self):
        self.enable("gmail")
        self.s.run("gmail", "list_unread")
        self.s.run("gmail", "draft_reply", message_id="m1", text="Streng geheimer Antworttext")
        log = self.log()
        self.assertNotIn("12-Wochen-Paket", log)
        self.assertNotIn("Streng geheimer", log)
        self.assertIn("skill_run", log)


class KnowledgeAndBriefing(Base):
    def test_c15_knowledge_skill_hides_confidential_and_writes_only_inbox(self):
        vault = Path(self.cfg["vault_dir"])
        (vault / "90_Privat").mkdir(parents=True, exist_ok=True)
        (vault / "90_Privat" / "Gehalt.md").write_text("# Gehalt\nShopify Gehalt 1234", encoding="utf-8")
        (vault / "02_Projekte").mkdir(parents=True, exist_ok=True)
        (vault / "02_Projekte" / "Shop.md").write_text("# Shop\nShopify Plan", encoding="utf-8")
        self.j.kb.invalidate()
        self.enable("knowledge")
        res = self.s.run("knowledge", "search", query="Shopify")
        self.assertIn("Shop", res.text)
        self.assertNotIn("1234", res.text)
        before = sorted(p.relative_to(vault).as_posix() for p in vault.rglob("*.md"))
        self.s.run("knowledge", "save_note", title="Idee", text="Text")
        self.s.run("knowledge", "save_note", title="Idee", text="Text 2")     # gleicher Titel: nie überschreiben
        after = sorted(p.relative_to(vault).as_posix() for p in vault.rglob("*.md"))
        new = sorted(set(after) - set(before))
        self.assertEqual(len(new), 2)
        self.assertTrue(all(n.startswith("00_Inbox/JARVIS/") for n in new))

    def test_c16_briefing_uses_only_enabled_skills(self):
        self.enable("briefing")
        text = self.s.run("briefing", "compose").text
        self.assertIn("Termine: Skill ist aus", text)
        self.assertNotIn("Coaching-Paket", text)
        self.enable("calendar")
        self.enable("gmail")
        text = self.s.run("briefing", "compose").text
        self.assertIn("Training Oberkörper", text)
        self.assertIn("Coaching-Paket", text)
        self.assertIn("Warten auf deine Freigabe", text)

    def test_c19_skills_command(self):
        out = self.j.handle_text("/skills")
        self.assertIn("Gmail", out)
        self.assertIn("aus", out)


class SkillsPage(Base):
    def setUp(self):
        super().setUp()
        store = wa.AuthStore(self.tmp / "d", self.j.audit, iterations=1000)
        store.set_password("inhaber", PW)
        self.app = WebApp(self.cfg, store, self.j)
        self.addCleanup(store.close)
        nonce = re.search(r'name="nonce" value="([^"]+)"', self.req("GET", "/login").body.decode()).group(1)
        r = self.req("POST", "/login", {"username": "inhaber", "password": PW, "nonce": nonce})
        self.sid = r.header("Set-Cookie").split(";")[0].split("=", 1)[1]
        self.csrf = re.search(r'name="csrf" value="([^"]+)"', self.req("GET", "/").body.decode()).group(1)

    def req(self, method, path, body=None):
        h = {"Host": HOST, "Origin": f"http://{HOST}"}
        if getattr(self, "sid", None):
            h["Cookie"] = f"jarvis_session={self.sid}"
        return self.app.handle(method, path, h, urlencode(body).encode() if body is not None else b"")

    def test_c17_page_request_disable_and_testrun(self):
        body = self.req("GET", "/skills").body.decode()
        self.assertEqual(body.count("Aktivierung beantragen"), 6)
        self.req("POST", "/skills/beantragen", {"csrf": self.csrf, "skill": "calendar"})
        self.assertFalse(self.s.is_enabled("calendar"))
        pend = self.j.gate.pending()
        self.assertEqual([a.action_type for a in pend], ["enable_skill"])
        self.assertIn("Aktivierung beantragt", self.req("GET", "/skills").body.decode())
        self.approve(pend[0])
        self.req("POST", "/skills/test", {"csrf": self.csrf, "skill": "calendar", "op": "list_today"})
        self.assertIn("Training Oberkörper", self.req("GET", "/skills").body.decode())
        self.req("POST", "/skills/test", {"csrf": self.csrf, "skill": "calendar", "op": "propose_event"})
        self.assertEqual(self.j.gate.pending(), [])          # Vorschläge nie per Testlauf
        self.req("POST", "/skills/aus", {"csrf": self.csrf, "skill": "calendar"})
        self.assertFalse(self.s.is_enabled("calendar"))

    def test_c17_requires_login_and_csrf(self):
        self.sid = None
        self.assertEqual(self.req("GET", "/skills").status, 303)
        self.sid = re.search(r"jarvis_session=([^;]+)", "jarvis_session=x").group(1)
        self.assertEqual(self.req("POST", "/skills/beantragen", {"csrf": "x", "skill": "gmail"}).status, 303)
        self.assertEqual(self.j.gate.pending(), [])


if __name__ == "__main__":
    unittest.main()
