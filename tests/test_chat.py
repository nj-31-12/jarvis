"""Tests Phase 2, Schritt 3: JARVIS-Chat – python3 -m unittest -v"""
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

from jarvis import web_auth as wa
from jarvis.budget import BudgetExceeded
from jarvis.chat import (MAX_MESSAGE_CHARS, RATE_LIMIT_MESSAGES, ChatError, ChatService, ChatStore,
                         clean_message, detect_areas)
from jarvis.config import DEFAULTS
from jarvis.core import Jarvis
from jarvis.web import MAX_BODY, WebApp

PORT = 8765
HOST = f"127.0.0.1:{PORT}"
PW = "Kaffee-Hantel-Duft-Motor-42"


class Clock:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t


class PaidFakeModel:
    """Simuliert ein kostenpflichtiges Modell, um die Kostenbremse zu prüfen (keine echte Verbindung)."""
    name = "fake-bezahlt"
    is_test_mode = False
    cost_per_call_eur = 0.40

    def __init__(self):
        self.calls = 0

    def chat(self, system_prompt, history, text):
        self.calls += 1
        self.last_system_prompt, self.last_history = system_prompt, history
        return f"Antwort {self.calls}"

    def complete(self, task, text):
        return "x"


class BrokenModel(PaidFakeModel):
    name = "kaputt"
    cost_per_call_eur = 0.0

    def chat(self, *a):
        raise ConnectionError("Server nicht erreichbar: geheimer-api-key-123")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.clock = Clock()
        self.cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                        telegram={"allowed_user_ids": [1], "approval_chat_id": 1})
        self.jarvis = Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": "z" * 48}, channel=lambda *a: None)
        self.store = ChatStore(self.tmp / "d" / "chat.db", clock=self.clock)
        self.svc = ChatService(self.jarvis, self.store, clock=self.clock)
        self.conv = self.store.new_conversation()

    def tearDown(self):
        shutil.rmtree(self.tmp)


# ------------------------------------------------------------------ Verlauf
class HistoryTests(Base):
    def test_message_and_reply_are_stored_in_order(self):
        self.svc.send(self.conv, "Hallo JARVIS", "nj")
        self.svc.send(self.conv, "Zweite Frage", "nj")
        h = self.store.history(self.conv)
        self.assertEqual([m["role"] for m in h], ["du", "jarvis", "du", "jarvis"])
        self.assertEqual(h[0]["text"], "Hallo JARVIS")
        self.assertEqual(h[1]["mode"], "test")

    def test_history_survives_restart(self):
        self.svc.send(self.conv, "Merk dir das", "nj")
        again = ChatStore(self.tmp / "d" / "chat.db")
        self.assertEqual(again.history(self.conv)[0]["text"], "Merk dir das")

    def test_conversations_are_separate(self):
        other = self.store.new_conversation()
        self.svc.send(self.conv, "Gespräch A", "nj")
        self.svc.send(other, "Gespräch B", "nj")
        self.assertEqual(self.store.history(self.conv)[0]["text"], "Gespräch A")
        self.assertEqual(self.store.history(other)[0]["text"], "Gespräch B")
        titles = [c["title"] for c in self.store.conversations()]
        self.assertIn("Gespräch A", titles)
        self.assertIn("Gespräch B", titles)

    def test_model_gets_persona_areas_and_history(self):
        fake = PaidFakeModel()
        fake.cost_per_call_eur = 0.0
        self.jarvis.llm.allow_test_double(fake)
        self.svc.send(self.conv, "Erste", "nj")
        self.svc.send(self.conv, "Zweite", "nj")
        self.assertIn("JARVIS", fake.last_system_prompt)
        self.assertIn("Young Living Network-Marketing", fake.last_system_prompt)
        self.assertIn("Freigabeschicht", fake.last_system_prompt)
        self.assertEqual([m["text"] for m in fake.last_history], ["Erste", "Antwort 1"])

    def test_test_mode_is_labelled(self):
        reply = self.svc.send(self.conv, "Wie wachse ich mit Scent Edit auf Instagram?", "nj")
        self.assertTrue(self.svc.test_mode)
        self.assertIn("Testmodus", reply["text"])
        self.assertIn("Scent Edit", reply["text"])


# ------------------------------------------------------------------ Eingaben + Fehler
class InputTests(Base):
    def test_empty_and_too_long_rejected(self):
        for bad in ("", "   \n  ", "\x00\x07"):
            with self.subTest(bad=bad), self.assertRaises(ChatError):
                self.svc.send(self.conv, bad, "nj")
        with self.assertRaises(ChatError):
            self.svc.send(self.conv, "a" * (MAX_MESSAGE_CHARS + 1), "nj")
        self.assertEqual(self.store.history(self.conv), [])

    def test_control_characters_removed(self):
        self.assertEqual(clean_message("Hal\x00lo​\r\nWelt\x1b[31m"), "Hallo\nWelt[31m")

    def test_unknown_conversation_rejected(self):
        for bad in ("../../etc/passwd", "000000000000", "ABCDEF123456", "x" * 12, "", "1' OR '1'='1"):
            with self.subTest(bad=bad), self.assertRaises(ChatError):
                self.svc.send(bad, "Hallo", "nj")

    def test_rate_limit(self):
        for i in range(RATE_LIMIT_MESSAGES):
            self.svc.send(self.conv, f"Nachricht {i}", "nj")
        with self.assertRaises(ChatError):
            self.svc.send(self.conv, "eine zu viel", "nj")
        self.clock.t += 61
        self.svc.send(self.conv, "wieder erlaubt", "nj")

    def test_model_error_is_friendly_and_leaks_nothing(self):
        self.jarvis.llm.allow_test_double(BrokenModel())
        reply = self.svc.send(self.conv, "Hallo", "nj")
        self.assertEqual(reply["role"], "system")
        self.assertNotIn("geheimer-api-key", reply["text"])
        self.assertNotIn("geheimer-api-key", self.jarvis.audit.path.read_text())
        self.assertIn("chat_model_error", self.jarvis.audit.path.read_text())


# ------------------------------------------------------------------ Kosten + Sicherheit
class CostAndSafetyTests(Base):
    def test_budget_limit_stops_calls_before_they_happen(self):
        fake = PaidFakeModel()                      # 0,40 € pro Aufruf, Tageslimit 1,00 €
        self.jarvis.llm.allow_test_double(fake)
        self.svc.send(self.conv, "eins", "nj")
        self.svc.send(self.conv, "zwei", "nj")
        reply = self.svc.send(self.conv, "drei", "nj")
        self.assertEqual(fake.calls, 2)              # dritter Aufruf fand NICHT statt
        self.assertIn("Kostenbremse", reply["text"])
        self.assertLessEqual(self.jarvis.budget.spent_today(), 1.0)

    def test_killswitch_blocks_chat_model_and_commands(self):
        fake = PaidFakeModel()
        self.jarvis.llm.allow_test_double(fake)
        self.jarvis.kill.activate("Test")
        self.assertIn("Notabschaltung", self.svc.send(self.conv, "Hallo", "nj")["text"])
        self.assertIn("Notabschaltung", self.svc.send(self.conv, "/idee Test", "nj")["text"])
        self.assertEqual(fake.calls, 0)

    def test_mail_command_only_proposes_never_sends(self):
        reply = self.svc.send(self.conv, "/mail a@b.de | Hallo | Text", "nj")
        self.assertIn("Freigabe", reply["text"])
        self.assertEqual(len(self.jarvis.gate.pending()), 1)
        outbox = self.tmp / "d" / "sandbox" / "outbox"
        self.assertEqual(list(outbox.glob("*.json")), [])      # nichts ausgeführt, nicht einmal simuliert

    def test_forbidden_actions_stay_forbidden(self):
        reply = self.svc.send(self.conv, "/mail a@b.de | Konto | meine IBAN ist DE00", "nj")
        self.assertIn("⛔", reply["text"])
        self.assertEqual(self.jarvis.gate.pending(), [])

    def test_notes_only_new_files_in_inbox(self):
        self.svc.send(self.conv, "/notiz ../../../etc/hack", "nj")
        self.svc.send(self.conv, "/notiz ../../../etc/hack", "nj")
        vault = Path(self.cfg["vault_dir"])
        inbox_files = list((vault / "00_Inbox" / "JARVIS").glob("*.md"))
        self.assertEqual(len(inbox_files), 2)                       # zweite Notiz überschreibt nicht
        all_md = [p for p in vault.rglob("*.md") if "00_Inbox" not in str(p) and "99_Vorlagen" not in str(p)
                  and "01_Ziele" not in str(p)]
        self.assertEqual(all_md, [])
        self.assertFalse((self.tmp / "etc").exists())

    def test_later_and_unknown_commands(self):
        self.assertIn("späteren Schritt", self.svc.send(self.conv, "/briefing", "nj")["text"])
        self.assertIn("Unbekannter", self.svc.send(self.conv, "/rm -rf /", "nj")["text"])

    def test_area_detection_word_boundaries(self):
        areas = DEFAULTS["business_areas"]
        self.assertNotIn("Automobilbranche und Fahrzeughandel", detect_areas("Automatisierung für mein Coaching", areas))
        self.assertIn("Automobilbranche und Fahrzeughandel", detect_areas("Im Autohaus heute", areas))
        self.assertIn("Young Living Network-Marketing", detect_areas("Was ist mit Young Living?", areas))


# ------------------------------------------------------------------ Browser
class WebChatTests(Base):
    def setUp(self):
        super().setUp()
        self.auth = wa.AuthStore(self.tmp / "d", self.jarvis.audit, clock=self.clock, iterations=1000)
        self.auth.set_password("nj", PW)
        self.app = WebApp(self.cfg, self.auth, self.jarvis, clock=self.clock)

    def req(self, method, path, body=None, cookie=None, **headers):
        h = {"Host": HOST}
        if cookie:
            h["Cookie"] = f"jarvis_session={cookie}"
        h.update({k.replace("_", "-"): v for k, v in headers.items()})
        data = urlencode(body).encode() if body is not None else b""
        return self.app.handle(method, path, h, data)

    def login(self):
        page = self.req("GET", "/login").body.decode()
        nonce = re.search(r'name="nonce" value="([^"]+)"', page).group(1)
        r = self.req("POST", "/login", {"username": "nj", "password": PW, "nonce": nonce})
        return r.header("Set-Cookie").split(";")[0].split("=", 1)[1]

    def chat_page(self, sid, path="/chat"):
        r = self.req("GET", path, cookie=sid)
        body = r.body.decode()
        csrf = re.search(r'name="csrf" value="([^"]+)"', body)
        conv = re.search(r'name="g" value="([0-9a-f]{12})"', body)
        return r, body, (csrf.group(1) if csrf else None), (conv.group(1) if conv else None)

    def test_chat_requires_login(self):
        self.assertEqual(self.req("GET", "/chat").header("Location"), "/login")
        self.assertEqual(self.req("POST", "/chat", {"text": "x"}).header("Location"), "/login")

    def test_send_and_show(self):
        sid = self.login()
        r, body, csrf, conv = self.chat_page(sid)
        self.assertEqual(r.status, 200)
        self.assertIn("Testmodus", body)
        r = self.req("POST", "/chat", {"csrf": csrf, "g": conv, "text": "Hallo JARVIS"}, cookie=sid,
                     Origin=f"http://{HOST}")
        self.assertEqual(r.status, 303)
        self.assertEqual(r.header("Location"), f"/chat?g={conv}#ende")
        _, body, _, _ = self.chat_page(sid, f"/chat?g={conv}")
        self.assertIn("Hallo JARVIS", body)
        self.assertIn("TESTMODUS", body)

    def test_csrf_and_origin_required(self):
        sid = self.login()
        _, _, csrf, conv = self.chat_page(sid)
        self.assertEqual(self.req("POST", "/chat", {"csrf": "falsch", "g": conv, "text": "x"}, cookie=sid).status, 403)
        self.assertEqual(self.req("POST", "/chat", {"csrf": csrf, "g": conv, "text": "x"}, cookie=sid,
                                  Origin="https://evil.example").status, 403)
        self.assertEqual(self.store.history(conv), [])

    def test_xss_in_messages_is_neutralized(self):
        sid = self.login()
        _, _, csrf, conv = self.chat_page(sid)
        attack = '<script>alert(1)</script><img src=x onerror=alert(1)> [x](javascript:alert(1))'
        self.req("POST", "/chat", {"csrf": csrf, "g": conv, "text": attack}, cookie=sid)
        self.req("POST", "/chat", {"csrf": csrf, "g": conv, "text": "/notiz " + attack}, cookie=sid)
        _, body, _, _ = self.chat_page(sid, f"/chat?g={conv}")
        self.assertNotIn("<script>alert", body)
        self.assertNotRegex(body, r"<img[^>]*onerror")
        self.assertNotIn('href="javascript:', body)

    def test_bad_conversation_ids_give_404(self):
        sid = self.login()
        for g in ("../../etc/passwd", "%2e%2e%2f", "000000000000", "abc"):
            self.assertEqual(self.req("GET", f"/chat?g={g}", cookie=sid).status, 404, g)
        _, _, csrf, _ = self.chat_page(sid)
        self.assertEqual(self.req("POST", "/chat", {"csrf": csrf, "g": "../x", "text": "hi"}, cookie=sid).status, 404)

    def test_errors_shown_and_draft_kept(self):
        sid = self.login()
        _, _, csrf, conv = self.chat_page(sid)
        self.req("POST", "/chat", {"csrf": csrf, "g": conv, "text": "   "}, cookie=sid)
        _, body, _, _ = self.chat_page(sid, f"/chat?g={conv}")
        self.assertIn("Die Nachricht ist leer", body)

    def test_long_umlaut_message_fits_body_limit(self):
        sid = self.login()
        _, _, csrf, conv = self.chat_page(sid)
        text = "ä" * MAX_MESSAGE_CHARS
        self.assertLess(len(urlencode({"csrf": csrf, "g": conv, "text": text})), MAX_BODY)
        r = self.req("POST", "/chat", {"csrf": csrf, "g": conv, "text": text}, cookie=sid)
        self.assertEqual(r.status, 303)
        self.assertEqual(len(self.store.history(conv)[0]["text"]), MAX_MESSAGE_CHARS)

    def test_new_conversation(self):
        sid = self.login()
        _, _, csrf, conv = self.chat_page(sid)
        r = self.req("POST", "/chat/neu", {"csrf": csrf}, cookie=sid)
        new = r.header("Location").split("g=")[1]
        self.assertNotEqual(new, conv)
        self.assertTrue(self.store.exists(new))

    def test_expired_session_cannot_chat(self):
        sid = self.login()
        _, _, csrf, conv = self.chat_page(sid)
        self.clock.t += 31 * 60
        r = self.req("POST", "/chat", {"csrf": csrf, "g": conv, "text": "Hallo"}, cookie=sid)
        self.assertEqual(r.header("Location"), "/login")
        self.assertEqual(self.store.history(conv), [])

    def test_pages_have_no_scripts_or_external_resources(self):
        sid = self.login()
        _, body, csrf, conv = self.chat_page(sid)
        self.req("POST", "/chat", {"csrf": csrf, "g": conv, "text": "Test"}, cookie=sid)
        _, body, _, _ = self.chat_page(sid, f"/chat?g={conv}")
        # Version 5.3: genau ein eigenes, lokales Skript (Stimme, Denk-Anzeige) – kein Inline-Code, kein CDN
        self.assertEqual(re.findall(r"<script[^>]*>", body),
                         ['<script src="/static/hud.js" defer>', '<script src="/static/chat.js" defer>'])
        self.assertIn('<script src="/static/chat.js" defer></script>', body)
        self.assertNotRegex(body, r"<script(?![^>]*src=\"/static/)")                 # nie Inline-Code
        self.assertNotRegex(body, r'(src|href)="https?://')
        js = self.req("GET", "/static/chat.js").body
        js = js.decode() if isinstance(js, bytes) else js
        self.assertNotRegex(js, r"https?://")
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("eval(", js)
        self.assertIsNotNone(self.req("GET", "/chat", cookie=sid).header("Content-Security-Policy"))


if __name__ == "__main__":
    unittest.main()
