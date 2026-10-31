"""Version 5.3 (Schnellspur): Claude-Anbindung, Kostenbremse über Prozessgrenzen, Sicherungen ohne Geheimnisse.

Alle Tests laufen gegen einen LOKALEN Fake-Server auf 127.0.0.1. Kein Internet, keine Kosten.
Alle Schlüssel sind erfundene Testwerte.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jarvis.ai_models import ModelBlocked, ModelPolicy, make_model
from jarvis.ai_providers.anthropic import (API_URL, API_VERSION, AIServiceError, AnthropicModel, to_messages)
from jarvis.audit import AuditLog
from jarvis.budget import BudgetExceeded, BudgetGuard
from jarvis.killswitch import KillSwitch, KillSwitchActive
from jarvis.llm import LLMRouter
from jarvis.outbound import OutboundGuard

FAKE_KEY = "nur-ein-testwert-kein-echter-schluessel"
TODAY = dt.date(2026, 10, 31)
MODEL = "claude-haiku-5-5"
ROOT = Path(__file__).resolve().parent.parent


def ok_reply(text="Guten Tag, Sir.", usage=None, stop="end_turn"):
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": MODEL, "stop_reason": stop,
            "content": [{"type": "thinking", "thinking": "", "signature": "x"}, {"type": "text", "text": text}],
            "usage": usage if usage is not None else {"input_tokens": 1000, "output_tokens": 200}}


class FakeClaude:
    """Lokaler Fake-Server. Hält jede Anfrage fest und antwortet wie vorgegeben."""

    def __init__(self):
        self.requests = []
        self.status, self.body, self.ctype, self.delay = 200, ok_reply(), "application/json", 0.0
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                n = int(self.headers.get("content-length", 0))
                fake.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                                      "body": json.loads(self.rfile.read(n).decode("utf-8"))})
                if fake.delay:
                    time.sleep(fake.delay)
                raw = fake.body if isinstance(fake.body, bytes) else json.dumps(fake.body).encode("utf-8")
                try:
                    self.send_response(fake.status)
                    self.send_header("content-type", fake.ctype)
                    self.send_header("content-length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass                     # Gegenseite hat absichtlich abgebrochen (Zeitlimit, Größe)

            def log_message(self, *_a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1/messages"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def model_entry(**over):
    e = {"kind": "external", "provider": "anthropic", "approved": True, "privacy_reviewed_on": "2026-10-31",
         "key_env": "JARVIS_ANTHROPIC_KEY", "cost_per_call_eur": 0.01, "tasks": ["chat", "idea", "research"]}
    e.update(over)
    return e


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.fake = FakeClaude()
        self.addCleanup(self.fake.close)
        self.audit = AuditLog(self.tmp / "audit.jsonl")
        self.budget = BudgetGuard(self.tmp / "budget.db", 1.0, 15.0)
        self.addCleanup(self.budget.close)
        self.kill = KillSwitch(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def router(self, entry=None, allowed=True, secrets=None, timeout=5):
        cfg = {"privacy": {"external_ai_allowed": allowed, "max_chars_external": 12000},
               "knowledge": {"confidential_terms": ["Autohaus Beispiel"]},
               "ai": {"active_model": MODEL, "models": {MODEL: entry or model_entry()}}}
        policy = ModelPolicy(cfg, self.audit, {"JARVIS_ANTHROPIC_KEY": FAKE_KEY} if secrets is None else secrets,
                             today=lambda: TODAY)
        model = AnthropicModel(MODEL, endpoint=self.fake.url, timeout=timeout)
        return LLMRouter(self.budget, self.kill, model=model, guard=OutboundGuard(cfg, self.audit), policy=policy)

    def audit_text(self):
        return (self.tmp / "audit.jsonl").read_text(encoding="utf-8") if (self.tmp / "audit.jsonl").exists() else ""


class AnfrageUndAntwort(Base):
    def test_erfolg_liefert_text_und_bucht_tatsaechliche_kosten(self):
        r = self.router()
        reply = r.chat("Du bist JARVIS.", [], "Was steht heute an?")
        self.assertEqual(reply, "Guten Tag, Sir.")
        expected = (1000 * 0.10 + 200 * 0.50) / 1_000_000
        self.assertAlmostEqual(r.last_cost_eur(), expected)
        self.assertAlmostEqual(self.budget.spent_today(), expected)

    def test_anfrage_hat_richtiges_format(self):
        self.router().chat("SYSTEM", [{"role": "du", "text": "Hallo"}, {"role": "jarvis", "text": "Hi"}], "Und?")
        req = self.fake.requests[0]
        self.assertEqual(req["headers"]["x-api-key"], FAKE_KEY)
        self.assertEqual(req["headers"]["anthropic-version"], API_VERSION)
        body = req["body"]
        self.assertEqual(body["model"], MODEL)
        self.assertEqual(body["system"], "SYSTEM")
        self.assertEqual([m["role"] for m in body["messages"]], ["user", "assistant", "user"])
        self.assertEqual(body["output_config"], {"effort": "low"})
        self.assertNotIn("temperature", body)
        self.assertLessEqual(body["max_tokens"], 4096)

    def test_sensible_daten_werden_vor_dem_senden_entfernt(self):
        self.router().chat("SYSTEM", [], "Schreib an max@beispiel.de, IBAN DE89370400440532013000, Autohaus Beispiel")
        sent = json.dumps(self.fake.requests[0]["body"], ensure_ascii=False)
        for secret in ("max@beispiel.de", "DE89370400440532013000", "Autohaus Beispiel"):
            self.assertNotIn(secret, sent)
        self.assertIn("[ENTFERNT", sent)

    def test_schluessel_steht_nie_im_protokoll(self):
        self.router().chat("SYSTEM", [], "Hallo")
        self.fake.status, self.fake.body = 401, {"type": "error"}
        with self.assertRaises(AIServiceError):
            self.router().chat("SYSTEM", [], "Hallo")
        self.assertNotIn(FAKE_KEY, self.audit_text())

    def test_complete_fuer_ideen(self):
        out = self.router().complete("idea", "Proteinriegel-Shop")
        self.assertEqual(out, "Guten Tag, Sir.")
        self.assertIn("Geschäftsidee", self.fake.requests[0]["body"]["system"])


class Fehlerfaelle(Base):
    def assert_fails_without_cost(self, status, body=None, ctype="application/json"):
        self.fake.status, self.fake.ctype = status, ctype
        if body is not None:
            self.fake.body = body
        r = self.router()
        with self.assertRaises(AIServiceError):
            r.chat("S", [], "Hallo")
        return r

    def test_401_429_400_kosten_null(self):
        for code in (400, 401, 429):
            with self.subTest(code=code):
                self.assert_fails_without_cost(code, {"type": "error"})
        self.assertEqual(self.budget.spent_today(), 0.0)
        self.assertEqual(len(self.fake.requests), 3)       # genau eine Anfrage je Versuch, keine Wiederholung

    def test_500_reservierung_bleibt(self):
        self.assert_fails_without_cost(500, {"type": "error"})
        self.assertAlmostEqual(self.budget.spent_today(), 0.01)
        self.assertEqual(len(self.fake.requests), 1)

    def test_zeitueberschreitung_ohne_wiederholung(self):
        self.fake.delay = 2.0
        r = self.router(timeout=0.5)
        with self.assertRaises(AIServiceError) as cm:
            r.chat("S", [], "Hallo")
        self.assertIn("Zeitüberschreitung", str(cm.exception))
        self.assertEqual(len(self.fake.requests), 1)
        self.assertAlmostEqual(self.budget.spent_today(), 0.01)   # könnte abgerechnet sein → Reservierung bleibt

    def test_falscher_inhaltstyp(self):
        self.assert_fails_without_cost(200, ok_reply(), ctype="text/html")

    def test_zu_grosse_antwort(self):
        self.assert_fails_without_cost(200, b"{" + b" " * 1_100_000 + b"}")

    def test_kaputtes_json(self):
        self.assert_fails_without_cost(200, b"{kein json")

    def test_ohne_kostenangabe_bleibt_volle_reservierung(self):
        self.fake.body = ok_reply(usage={})
        self.router().chat("S", [], "Hallo")
        self.assertAlmostEqual(self.budget.spent_today(), 0.01)

    def test_ablehnung_durch_claude(self):
        self.fake.body = ok_reply(text="", stop="refusal")
        self.assertIn("abgelehnt", self.router().chat("S", [], "Hallo"))

    def test_abgeschnittene_antwort(self):
        self.fake.body = ok_reply(text="Teil", stop="max_tokens")
        self.assertIn("abgeschnitten", self.router().chat("S", [], "Hallo"))

    def test_fehlermeldung_enthaelt_keine_inhalte(self):
        self.fake.status, self.fake.body = 500, {"error": "GEHEIMER-ANTWORTINHALT"}
        with self.assertRaises(AIServiceError) as cm:
            self.router().chat("S", [], "MEIN-GEHEIMER-TEXT")
        self.assertNotIn("GEHEIM", str(cm.exception))


class Sperren(Base):
    def test_ohne_freigabe_wird_nichts_gesendet(self):
        for kwargs in ({"allowed": False}, {"entry": model_entry(approved=False)}, {"secrets": {}},
                       {"entry": model_entry(privacy_reviewed_on="2025-01-01")}):
            with self.subTest(**{k: str(v)[:40] for k, v in kwargs.items()}):
                with self.assertRaises(ModelBlocked):
                    self.router(**kwargs).chat("S", [], "Hallo")
        self.assertEqual(self.fake.requests, [])
        self.assertEqual(self.budget.spent_today(), 0.0)

    def test_zu_niedrige_reservierung_sendet_nichts(self):
        with self.assertRaises(ModelBlocked) as cm:
            self.router(entry=model_entry(cost_per_call_eur=0.0001)).chat("S", [], "Hallo")
        self.assertIn("Höchstkosten", str(cm.exception))
        self.assertEqual(self.fake.requests, [])
        self.assertEqual(self.budget.spent_today(), 0.0)

    def test_notaus_sendet_nichts(self):
        self.kill.activate("test")
        with self.assertRaises(KillSwitchActive):
            self.router().chat("S", [], "Hallo")
        self.assertEqual(self.fake.requests, [])

    def test_kostenlimit_sendet_nichts(self):
        self.budget.daily = 0.005
        with self.assertRaises(BudgetExceeded):
            self.router().chat("S", [], "Hallo")
        self.assertEqual(self.fake.requests, [])

    def test_nur_offizieller_oder_lokaler_endpunkt(self):
        for bad in ("https://evil.example.com/v1/messages", "http://api.anthropic.com/v1/messages",
                    "http://127.0.0.1@evil.example.com/v1/messages", "https://api.anthropic.com.evil.de/v1/messages"):
            with self.subTest(bad=bad), self.assertRaises(AIServiceError):
                AnthropicModel(MODEL, endpoint=bad)
        self.assertEqual(AnthropicModel(MODEL).endpoint, API_URL)

    def test_unbekanntes_modell_ohne_preis(self):
        with self.assertRaises(AIServiceError):
            AnthropicModel("claude-unbekannt")

    def test_direkter_aufruf_ohne_router_ist_gesperrt(self):
        with self.assertRaises(AIServiceError):
            AnthropicModel(MODEL, endpoint=self.fake.url).chat("S", [], "Hallo")
        self.assertEqual(self.fake.requests, [])

    def test_make_model_waehlt_claude_nur_mit_eintrag(self):
        cfg = {"ai": {"active_model": MODEL, "models": {MODEL: model_entry()}}}
        self.assertIsInstance(make_model(cfg), AnthropicModel)
        cfg = {"ai": {"active_model": MODEL, "models": {}}}
        self.assertNotIsInstance(make_model(cfg), AnthropicModel)
        self.assertEqual(make_model({}).name, "mock")


class Gespraechsformat(unittest.TestCase):
    def test_beginnt_mit_user_und_wechselt_ab(self):
        msgs = to_messages([{"role": "jarvis", "text": "Hallo"}, {"role": "du", "text": "a"},
                            {"role": "du", "text": "b"}, {"role": "system", "text": "x"},
                            {"role": "jarvis", "text": ""}], "c")
        self.assertEqual(msgs, [{"role": "user", "content": "a\n\nb\n\nc"}])

    def test_zwanzig_runden(self):
        hist = []
        for i in range(20):
            hist += [{"role": "du", "text": f"F{i}"}, {"role": "jarvis", "text": f"A{i}"}]
        msgs = to_messages(hist, "letzte")
        self.assertEqual(len(msgs), 41)
        self.assertEqual(msgs[-1], {"role": "user", "content": "letzte"})

    def test_leere_nachricht(self):
        with self.assertRaises(AIServiceError):
            to_messages([], "   ")


CHILD = r"""
import sys, time
sys.path.insert(0, sys.argv[1])
from jarvis.budget import BudgetGuard, BudgetExceeded
b = BudgetGuard(sys.argv[2], daily_eur=1.0, monthly_eur=100.0)
ok = 0
for _ in range(20):
    try:
        b.charge("p", 0.03); ok += 1
    except BudgetExceeded:
        pass
print(ok)
"""


class KostenbremseUeberProzessgrenzen(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db = self.tmp / "budget.db"
        BudgetGuard(self.db, 1.0, 100.0).close()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_zwei_prozesse_ueberschreiten_das_limit_nie(self):
        procs = [subprocess.Popen([sys.executable, "-c", CHILD, str(ROOT), str(self.db)], stdout=subprocess.PIPE)
                 for _ in range(2)]
        counts = [int(p.communicate(timeout=60)[0].decode().strip()) for p in procs]
        b = BudgetGuard(self.db, 1.0, 100.0)
        self.addCleanup(b.close)
        self.assertLessEqual(b.spent_today(), 1.0 + 1e-9)
        self.assertEqual(sum(counts), 33)                 # 33 × 0,03 € = 0,99 € – genau berechenbar
        self.assertAlmostEqual(b.spent_today(), 0.99)

    def test_gesperrte_datenbank_fuehrt_zur_ablehnung(self):
        b = BudgetGuard(self.db, 1.0, 100.0, lock_wait_seconds=0.3)
        self.addCleanup(b.close)
        other = sqlite3.connect(str(self.db))
        self.addCleanup(other.close)
        other.execute("BEGIN IMMEDIATE")
        t = time.monotonic()
        with self.assertRaises(BudgetExceeded):
            b.charge("p", 0.1)
        self.assertLess(time.monotonic() - t, 5)
        other.execute("ROLLBACK")
        self.assertEqual(b.spent_today(), 0.0)
        b.charge("p", 0.1)                                # danach geht es wieder
        self.assertAlmostEqual(b.spent_today(), 0.1)

    def test_fehler_in_der_transaktion_hinterlaesst_keine_buchung(self):
        b = BudgetGuard(self.db, 1.0, 100.0)
        self.addCleanup(b.close)
        original = b.check

        def boom(cost):
            original(cost)
            raise RuntimeError("absichtlicher Fehler")
        b.check = boom
        with self.assertRaises(RuntimeError):
            b.charge("p", 0.1)
        b.check = original
        self.assertEqual(b.spent_today(), 0.0)

    def test_abrechnen_korrigiert_die_reservierung(self):
        b = BudgetGuard(self.db, 1.0, 100.0)
        self.addCleanup(b.close)
        booking = b.charge("p", 0.5)
        b.settle(booking, 0.002)
        self.assertAlmostEqual(b.spent_today(), 0.002)


class SicherungOhneGeheimnisse(unittest.TestCase):
    def test_passwortdateien_fehlen_im_archiv(self):
        from jarvis import server
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        data = tmp / "data"
        data.mkdir()
        (data / ".approval_secret").write_text("GEHEIMNIS-123")
        (data / "web_auth.json").write_text('{"hash": "GEHEIM"}')
        (data / "notiz.txt").write_text("normal")
        archive = server.make_backup({"data_dir": str(data), "backup": {"dir": str(tmp / "sicherungen")}})
        with tarfile.open(archive) as tar:
            names = tar.getnames()
            blob = b"".join(tar.extractfile(m).read() for m in tar.getmembers() if m.isfile())
        self.assertIn("data/notiz.txt", names)
        self.assertNotIn("data/.approval_secret", names)
        self.assertNotIn("data/web_auth.json", names)
        self.assertNotIn(b"GEHEIMNIS-123", blob)
        self.assertNotIn(b"GEHEIM\"", blob)


if __name__ == "__main__":
    unittest.main()


class UmstellungNurEinmal(unittest.TestCase):
    def test_nach_ja_fragt_der_start_nicht_erneut(self):
        from jarvis import server
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "data").mkdir()
        con = sqlite3.connect(str(tmp / "data" / "actions.db"))
        con.execute("CREATE TABLE actions (id TEXT PRIMARY KEY, status TEXT)")
        con.execute("INSERT INTO actions VALUES ('a1', 'offen')")
        con.commit(); con.close()
        cfg = {"data_dir": str(tmp / "data")}
        self.assertTrue(server.pending_upgrades(cfg))
        server.apply_upgrades(cfg)
        self.assertEqual(server.pending_upgrades(cfg), [])
        con = sqlite3.connect(str(tmp / "data" / "actions.db"))
        self.assertEqual(con.execute("SELECT id, status FROM actions").fetchall(), [("a1", "offen")])  # nichts verändert
        con.close()
