"""Version 5 · Phase A: KI-Modellverwaltung mit Erlaubnisliste.

Jeder Test steht für eine Anforderung aus dem Auftrag. Alle Schlüssel sind erfundene Testwerte.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from jarvis.ai_models import (AIConfigError, ModelBlocked, ModelPolicy, NotConnectedModel, find_secrets_in_ai_config,
                              make_model, validate_ai_config)
from jarvis.audit import AuditLog
from jarvis.budget import BudgetGuard
from jarvis.chat import ChatService, ChatStore
from jarvis.config import DEFAULTS, PROJECT_ROOT, load_config
from jarvis.core import Jarvis
from jarvis.killswitch import KillSwitch, KillSwitchActive
from jarvis.llm import LLMRouter, MockLLM
from jarvis.outbound import ExternalAIBlocked, OutboundGuard

SECRET = "z" * 48
FAKE_KEY = "nur-ein-testwert-kein-echter-schluessel"
TODAY = dt.date(2026, 10, 30)


class Recorder:
    """Ersatzmodell, das alle erhaltenen Daten festhält."""
    name = "extern-test"
    is_test_mode = False
    cost_per_call_eur = 0.0

    def __init__(self):
        self.calls = []

    def chat(self, system_prompt, history, text):
        self.calls.append((system_prompt, history, text))
        return "Antwort"

    def complete(self, task, text):
        self.calls.append(("", [], text))
        return "Antwort"


class LyingLocalModel(Recorder):
    """Behauptet, lokal und im Testmodus zu sein – genau die Schwäche aus Version 4.2."""
    name = "angeblich-lokal"
    is_test_mode = True
    is_external = False


def entry(**over):
    e = {"kind": "external", "approved": True, "privacy_reviewed_on": "2026-10-01",
         "key_env": "JARVIS_TEST_KEY", "cost_per_call_eur": 0.02}
    e.update(over)
    return e


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.audit = AuditLog(self.tmp / "audit.jsonl")
        self.budget = BudgetGuard(self.tmp / "b.db", 5, 10)
        self.addCleanup(self.budget.close)
        self.kill = KillSwitch(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def policy(self, models=None, allowed=True, secrets=None):
        cfg = {"privacy": {"external_ai_allowed": allowed}, "ai": {"active_model": "mock", "models": models or {}}}
        return ModelPolicy(cfg, self.audit, {"JARVIS_TEST_KEY": FAKE_KEY} if secrets is None else secrets,
                           today=lambda: TODAY)

    def router(self, model, policy=None, guard_cfg=None):
        guard = OutboundGuard(guard_cfg or {"privacy": {"external_ai_allowed": True}}, self.audit)
        return LLMRouter(self.budget, self.kill, model=model, guard=guard, policy=policy or self.policy())

    def log(self) -> str:
        return self.audit.path.read_text(encoding="utf-8") if self.audit.path.exists() else ""

    def assert_blocked(self, router, contains=""):
        model = router.model
        before = self.budget.spent_today()
        with self.assertRaises(ModelBlocked) as ctx:
            router.chat("System", [], "Hallo")
        self.assertEqual(getattr(model, "calls", []), [], "Modell darf nicht aufgerufen werden")
        self.assertEqual(self.budget.spent_today(), before, "Keine Kosten bei Sperre")
        self.assertIn(contains, str(ctx.exception))
        return str(ctx.exception)


class UnknownModelsAreBlocked(Base):
    def test_a1_unknown_model_blocked_by_default(self):
        r = self.router(Recorder())
        self.assert_blocked(r, "nicht in der Erlaubnisliste")
        self.assertIn("external_ai_blocked", self.log())

    def test_a1_self_declared_local_model_is_still_blocked(self):
        """Regression 4.2: is_external=False / is_test_mode=True darf NICHT mehr reichen."""
        self.assert_blocked(self.router(LyingLocalModel()), "nicht in der Erlaubnisliste")

    def test_a1_mock_subclass_or_renamed_mock_is_blocked(self):
        class FakeMock(MockLLM):
            pass
        self.assert_blocked(self.router(FakeMock()))
        renamed = MockLLM()
        renamed.name = "gpt-irgendwas"
        self.assert_blocked(self.router(renamed))

    def test_a1_router_without_policy_allows_only_builtin_mock(self):
        r = LLMRouter(self.budget, self.kill, model=Recorder())
        with self.assertRaises(ExternalAIBlocked):
            r.chat("S", [], "x")
        self.assertEqual(r.model.calls, [])
        self.assertIn("Testmodus", LLMRouter(self.budget, self.kill).chat("S", [], "x"))

    def test_a1_unknown_task_blocked(self):
        with self.assertRaises(ModelBlocked):
            self.router(MockLLM()).complete("bank_ueberweisung", "x")

    def test_a1_invalid_model_name_is_not_written_to_log(self):
        m = Recorder()
        m.name = "sk-abcdefghijklmnopqrstuvwxyz\nFALSCHER EINTRAG"
        self.assert_blocked(self.router(m), "ungültigem Namen")
        self.assertNotIn("abcdefghijklmnop", self.log())
        self.assertIn("(ungültiger Name)", self.log())

    def test_a1_killswitch_stops_before_any_check_or_cost(self):
        self.kill.activate("Test")
        with self.assertRaises(KillSwitchActive):
            self.router(MockLLM()).chat("S", [], "x")
        self.assertEqual(self.budget.spent_today(), 0.0)


class OnlyApprovedTestModelsRunWithoutPrivacyCheck(Base):
    def test_a2_builtin_mock_allowed_and_logged(self):
        self.assertIn("Testmodus", self.router(MockLLM()).chat("S", [], "Hallo"))
        log = [json.loads(l) for l in self.log().splitlines()]
        self.assertEqual(log[-1]["event"], "ai_access")
        self.assertEqual(log[-1]["details"]["kind"], "test")

    def test_a2_test_double_needs_explicit_approval(self):
        r = self.router(LyingLocalModel())
        self.assert_blocked(r)
        r.allow_test_double(r.model)
        self.assertEqual(r.chat("S", [], "x"), "Antwort")
        self.assertIn("ai_test_double_allowed", self.log())

    def test_a2_test_double_only_from_tests_package(self):
        Outside = type("Outside", (Recorder,), {"__module__": "jarvis.plugins.fremd"})
        with self.assertRaises(ModelBlocked):
            self.policy().allow_test_double(Outside())

    def test_a2_external_marked_model_cannot_become_test_double(self):
        ext = Recorder()
        ext.is_external = True
        with self.assertRaises(ModelBlocked):
            self.policy().allow_test_double(ext)

    def test_a2_approval_is_per_object_not_per_class(self):
        p = self.policy()
        a, b = LyingLocalModel(), LyingLocalModel()
        p.allow_test_double(a)
        self.assertEqual(p.authorize(a, "chat").kind, "test")
        with self.assertRaises(ModelBlocked):
            p.authorize(b, "chat")


class ExternalModelsNeedApprovalAndPrivacyReview(Base):
    def router_for(self, allowed=True, secrets=None, **over):
        return self.router(Recorder(), self.policy({"extern-test": entry(**over)}, allowed, secrets))

    def test_a3_fully_configured_external_model_works_through_guard(self):
        r = self.router_for()
        r.chat("System", [{"role": "du", "text": "IBAN DE89 3704 0044 0532 0130 00"}], "Mail an noah@example.com")
        sent = json.dumps(r.model.calls[-1], ensure_ascii=False)
        self.assertNotIn("DE89", sent)
        self.assertNotIn("noah@example.com", sent)
        self.assertIn("[ENTFERNT:", sent)
        self.assertAlmostEqual(self.budget.spent_today(), 0.02)    # Kosten aus der Konfiguration, nicht 0 €

    def test_a3_global_switch_off_blocks_even_approved_model(self):
        self.assert_blocked(self.router_for(allowed=False), "external_ai_allowed")

    def test_a3_global_switch_must_be_real_true(self):
        p = ModelPolicy({"privacy": {"external_ai_allowed": "true"}, "ai": {"models": {"extern-test": entry()}}},
                        self.audit, {"JARVIS_TEST_KEY": FAKE_KEY}, today=lambda: TODAY)
        self.assert_blocked(self.router(Recorder(), p), "external_ai_allowed")

    def test_a3_each_missing_condition_blocks(self):
        cases = {
            "approved fehlt": dict(approved=None),
            "approved als Text": dict(approved="ja"),
            "Prüfung fehlt": dict(privacy_reviewed_on=None),
            "Prüfung kein Datum": dict(privacy_reviewed_on="bald"),
            "Prüfung in Zukunft": dict(privacy_reviewed_on="2027-01-01"),
            "Prüfung zu alt": dict(privacy_reviewed_on="2025-01-01"),
            "falsche Art": dict(kind="local"),
            "Kosten fehlen": dict(cost_per_call_eur=None),
            "Kosten 0": dict(cost_per_call_eur=0),
            "Kosten als bool": dict(cost_per_call_eur=True),
            "Kosten zu hoch": dict(cost_per_call_eur=5),
            "key_env fehlt": dict(key_env=None),
            "key_env falscher Name": dict(key_env="OPENAI_API_KEY"),
            "unbekanntes Feld": dict(base_url="https://example.invalid"),
            "Aufgabe nicht erlaubt": dict(tasks=["research"]),
        }
        for label, over in cases.items():
            with self.subTest(label):
                e = entry(**over)
                for k in [k for k, v in over.items() if v is None]:
                    e.pop(k)
                r = self.router(Recorder(), self.policy({"extern-test": e}))
                self.assert_blocked(r)

    def test_a3_missing_key_blocks(self):
        self.assert_blocked(self.router_for(secrets={}), "nicht in .env")

    def test_a3_key_from_environment_variable(self):
        with mock.patch.dict("os.environ", {"JARVIS_TEST_KEY": FAKE_KEY}):
            r = self.router_for(secrets={})
            self.assertEqual(r.chat("S", [], "x"), "Antwort")

    def test_a3_external_without_guard_never_sends(self):
        p = self.policy({"extern-test": entry()})
        r = LLMRouter(self.budget, self.kill, model=Recorder(), guard=None, policy=p)
        with self.assertRaises(ExternalAIBlocked):
            r.chat("S", [], "x")
        self.assertEqual(r.model.calls, [])


class NoConfidentialDataWithoutApproval(Base):
    def test_a4_confidential_terms_removed_before_sending(self):
        guard_cfg = {"privacy": {"external_ai_allowed": True},
                     "knowledge": {"confidential_terms": ["Autohaus Beispiel"]}}
        r = self.router(Recorder(), self.policy({"extern-test": entry()}), guard_cfg)
        r.complete("research", "Umsatz im Autohaus Beispiel, Passwort: Hund123!")
        sent = r.model.calls[-1][2]
        self.assertNotIn("Beispiel", sent)
        self.assertNotIn("Hund123", sent)

    def test_a4_legacy_search_answers_are_withheld_and_never_sent(self):
        cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                   telegram={"allowed_user_ids": [1], "approval_chat_id": 1})
        j = Jarvis(cfg, {"JARVIS_APPROVAL_SECRET": SECRET}, channel=lambda *a: None)
        self.addCleanup(j.close)
        store = ChatStore(self.tmp / "d" / "chat.db")
        self.addCleanup(store.close)
        svc = ChatService(j, store)
        conv = store.new_conversation()
        # So sah eine /suche-Antwort in Schritt 3 aus: Auszug, aber keine Quellenangabe
        store.add(conv, "du", "/suche Gehalt")
        legacy = store.add(conv, "jarvis", "📄 90_Privat/Gehalt.md\n…Gehalt 1234 Euro…", "befehl")
        reason = svc.withheld_reason(store.get_message(legacy))
        self.assertIn("ohne Quellenangabe", reason)
        self.assertEqual([m["id"] for m in svc.affected_messages()], [legacy])
        model = Recorder()
        j.llm.allow_test_double(model)
        svc.send(conv, "Und was heißt das?", "nj")
        self.assertNotIn("1234", json.dumps(model.calls[-1], ensure_ascii=False))

    def test_a4_command_outputs_never_go_to_model(self):
        cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                   telegram={"allowed_user_ids": [1], "approval_chat_id": 1})
        j = Jarvis(cfg, {"JARVIS_APPROVAL_SECRET": SECRET}, channel=lambda *a: None)
        self.addCleanup(j.close)
        store = ChatStore(self.tmp / "d" / "chat.db")
        self.addCleanup(store.close)
        svc = ChatService(j, store)
        conv = store.new_conversation()
        svc.send(conv, "/mail coach@example.com | Vertrag | Geheimer Vertragstext 9876", "nj")
        svc.send(conv, "/offen", "nj")
        model = Recorder()
        j.llm.allow_test_double(model)
        svc.send(conv, "Fass zusammen", "nj")
        history = json.dumps(model.calls[-1][1], ensure_ascii=False)
        self.assertNotIn("9876", history)
        self.assertNotIn("coach@example.com", history)


class KeysNeverInCodeOrConfig(Base):
    def test_a5_key_field_in_config_refused(self):
        for bad in ({"models": {"x": {"api_key": "irgendwas"}}},
                    {"models": {"x": {"token": "irgendwas"}}},
                    {"models": {"x": {"description": "sk-abcdefghijklmnopqrstuvwx"}}},
                    {"openrouter_secret": "abc"}):
            with self.subTest(bad):
                with self.assertRaises(AIConfigError) as ctx:
                    validate_ai_config({"ai": bad})
                self.assertNotIn("abcdefghijklmnop", str(ctx.exception))    # Fehlermeldung nennt keinen Wert

    def test_a5_variable_name_is_fine(self):
        validate_ai_config({"ai": {"models": {"x": entry(key_env="JARVIS_OPENROUTER_KEY")}}})
        self.assertEqual(find_secrets_in_ai_config({"models": {"x": entry()}}), [])

    def test_a5_load_config_refuses_key_in_file(self):
        f = self.tmp / "jarvis.json"
        f.write_text(json.dumps({"ai": {"models": {"x": {"apiKey": "abc"}}}}), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_config(f)

    def test_a5_no_key_like_strings_in_program_code(self):
        pattern = re.compile(r"\b(sk|ghp|xoxb)-[A-Za-z0-9]{16,}|\bAKIA[0-9A-Z]{16}\b|-----BEGIN [A-Z ]*PRIVATE KEY")
        for f in sorted((PROJECT_ROOT / "jarvis").rglob("*.py")):
            with self.subTest(f.name):
                self.assertIsNone(pattern.search(f.read_text(encoding="utf-8")))

    def test_a5_api_key_only_for_external_decision_and_never_logged(self):
        p = self.policy({"extern-test": entry()})
        d = p.authorize(Recorder(), "chat")
        self.assertEqual(p.api_key(d), FAKE_KEY)
        with self.assertRaises(ModelBlocked):
            p.api_key(p.authorize(MockLLM(), "chat"))
        self.assertNotIn(FAKE_KEY, self.log())

    def test_a5_example_config_contains_no_keys(self):
        cfg = json.loads((PROJECT_ROOT / "config" / "jarvis.example.json").read_text(encoding="utf-8"))
        self.assertEqual(find_secrets_in_ai_config(cfg.get("ai", {})), [])


class MissingConfigurationBlocksSafely(Base):
    def test_a6_no_ai_section_means_only_mock(self):
        p = ModelPolicy({}, self.audit, {})
        self.assertEqual(p.authorize(MockLLM(), "chat").kind, "test")
        with self.assertRaises(ModelBlocked):
            p.authorize(Recorder(), "chat")

    def test_a6_garbage_ai_section_blocks(self):
        for ai in ("kaputt", [], {"models": "kaputt"}, {"models": {"extern-test": "kaputt"}}):
            with self.subTest(ai):
                p = ModelPolicy({"privacy": {"external_ai_allowed": True}, "ai": ai}, self.audit,
                                {"JARVIS_TEST_KEY": FAKE_KEY})
                with self.assertRaises(ModelBlocked):
                    p.authorize(Recorder(), "chat")

    def test_a6_unconnected_active_model_answers_with_clear_block(self):
        self.assertIsInstance(make_model({"ai": {"active_model": "mock"}}), MockLLM)
        self.assertIsInstance(make_model({}), MockLLM)
        cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                   telegram={"allowed_user_ids": [1], "approval_chat_id": 1},
                   ai={"active_model": "gpt-zukunft", "models": {}})
        j = Jarvis(cfg, {"JARVIS_APPROVAL_SECRET": SECRET}, channel=lambda *a: None)
        self.addCleanup(j.close)
        self.assertIsInstance(j.llm.model, NotConnectedModel)
        self.assertIn("nicht freigegeben", j.handle_text("Hallo JARVIS"))
        store = ChatStore(self.tmp / "d" / "chat.db")
        self.addCleanup(store.close)
        reply = ChatService(j, store).send(store.new_conversation(), "Hallo", "nj")
        self.assertIn("🔒", reply["text"])
        self.assertEqual(j.budget.spent_today(), 0.0)

    def test_a6_ki_status_lists_without_secrets(self):
        from jarvis import __main__ as cli
        cfg = dict(DEFAULTS, ai={"active_model": "mock", "models": {"extern-test": entry()}})
        buf = io.StringIO()
        with mock.patch.object(cli, "load_config", return_value=cfg), \
                mock.patch.object(cli, "load_secrets", return_value={"JARVIS_TEST_KEY": FAKE_KEY}), \
                redirect_stdout(buf):
            cli.ai_status()
        out = buf.getvalue()
        self.assertIn("extern-test", out)
        self.assertIn("gesperrt", out)            # globaler Schalter ist aus
        self.assertNotIn(FAKE_KEY, out)


class EveryAttemptIsLogged(Base):
    def test_a7_allowed_and_blocked_attempts_logged_without_content(self):
        self.router(MockLLM()).chat("System geheim-abc", [], "Inhalt geheim-xyz")
        with self.assertRaises(ModelBlocked):
            self.router(Recorder()).chat("System geheim-abc", [], "Inhalt geheim-xyz")
        log = self.log()
        events = [json.loads(l)["event"] for l in log.splitlines()]
        self.assertIn("ai_access", events)
        self.assertIn("external_ai_blocked", events)
        self.assertNotIn("geheim", log)
        ok, _ = self.audit.verify()
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
