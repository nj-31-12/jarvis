"""Version 5.3: Chat als Portal/Reportage, JARVIS-Stimme, Antwortprüfung mit Referenzen."""
from __future__ import annotations

import io
import math
import re
import unittest
import wave
from array import array
from unittest import mock
from urllib.parse import urlencode

from jarvis import web_auth as wa
from jarvis.chat import ChatService, ChatStore, format_check, strip_check
from jarvis.voice_fx import VoiceUnavailable, iron_fx
from jarvis.web import WebApp
from tests.test_knowledge import HOST, PW, JarvisBase


def tone(seconds=1.0, rate=22050):
    a = array("h", (int(9000 * math.sin(2 * math.pi * 200 * i / rate)) for i in range(int(rate * seconds))))
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(a.tobytes())
    return b.getvalue()


class Effekt(unittest.TestCase):
    def test_effekt_liefert_gueltige_wav_ohne_uebersteuerung(self):
        out = iron_fx(tone())
        with wave.open(io.BytesIO(out)) as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, 22050))
            data = array("h"); data.frombytes(w.readframes(w.getnframes()))
        self.assertGreater(len(data), int(22050 / 0.84))          # tiefer = länger (+ Echo)
        self.assertLessEqual(max(abs(v) for v in data), 32767)
        self.assertGreater(max(abs(v) for v in data), 20000)       # normalisiert, nicht stumm

    def test_stimme_wird_tiefer(self):
        def freq(wav):
            with wave.open(io.BytesIO(wav)) as w:
                d = array("h"); d.frombytes(w.readframes(w.getnframes()))
            d = d[2000:20000]
            crossings = sum(1 for a, b in zip(d, d[1:]) if a < 0 <= b)
            return crossings / (len(d) / 22050)
        self.assertLess(freq(iron_fx(tone())), freq(tone()) * 0.9)     # 200 Hz → ca. 168 Hz

    def test_effekt_lehnt_8_bit_ab(self):
        b = io.BytesIO()
        with wave.open(b, "wb") as w:
            w.setnchannels(1); w.setsampwidth(1); w.setframerate(8000); w.writeframes(b"\x80" * 100)
        with self.assertRaises(ValueError):
            iron_fx(b.getvalue())


class Pruefung(unittest.TestCase):
    def test_nur_echte_quellen_werden_referenziert(self):
        raw = '{"status": "ok", "punkte": [], "quellen": ["Coaching Plan", "Erfundene Studie 2025"]}'
        out = format_check(raw, ["Coaching Plan", "Ziele"])
        self.assertIn("✅", out)
        self.assertIn("Coaching Plan", out)
        self.assertNotIn("Erfundene Studie", out)

    def test_unsicher_zeigt_hinweise(self):
        out = format_check('Hier: {"status": "unsicher", "punkte": ["Zahl 40 % ist nicht belegt"], "quellen": []}', [])
        self.assertIn("⚠️", out)
        self.assertIn("Zahl 40 % ist nicht belegt", out)
        self.assertIn("allgemeines Wissen", out)

    def test_kaputtes_ergebnis_gilt_als_unsicher(self):
        out = format_check("kein json", [])
        self.assertIn("⚠️", out)

    def test_pruefvermerk_geht_nicht_zurueck_ans_modell(self):
        text = "Antwort.\n\n---\n🔎 **Prüfung:** ✅ stimmig"
        self.assertEqual(strip_check(text), "Antwort.")


class ClaudeLike:
    """Ersatz für ein echtes Modell im Test: hat chat_billed (wie Claude), läuft aber über einen Test-Router."""
    name = "claude-test"
    is_test_mode = False

    def chat_billed(self, *a):
        raise AssertionError("nicht benutzt")


class ZweiterDurchgang(JarvisBase):
    def test_echte_ki_antwort_bekommt_pruefvermerk_mit_referenz(self):
        svc = ChatService(self.jarvis, ChatStore(self.tmp / "c.db"))
        calls = []

        def fake_chat(system, history, text, **_kw):
            calls.append(system)
            if system.startswith("Du bist die Prüfinstanz"):
                self.assertIn("PRUEF-", text)                       # Daten gerahmt
                return '{"status": "hinweis", "punkte": ["Preis ist eine Schätzung"], "quellen": ["Scent Edit Plan"]}'
            return "Konkrete Antwort."
        self.jarvis.llm.model = ClaudeLike()
        with mock.patch.object(self.jarvis.llm, "chat", side_effect=fake_chat), \
                mock.patch.object(self.jarvis.kb, "context_for",
                                  return_value=[{"id": "a" * 16, "title": "Scent Edit Plan", "relpath": "x.md",
                                                 "excerpt": "Pinterest"}]):
            conv = svc.store.new_conversation()
            out = svc.send(conv, "Was mache ich mit Pinterest?", "t")
        self.assertEqual(len(calls), 2, (calls, out))
        self.assertTrue(out["text"].startswith("Konkrete Antwort."))
        self.assertIn("ℹ️", out["text"])
        self.assertIn("Referenzen:** Scent Edit Plan", out["text"])
        self.assertIn("Preis ist eine Schätzung", out["text"])

    def test_fehler_bei_der_pruefung_blockiert_die_antwort_nicht(self):
        svc = ChatService(self.jarvis, ChatStore(self.tmp / "c2.db"))
        seq = iter(["Antwort steht.", RuntimeError("weg")])

        def fake_chat(*_a, **_kw):
            v = next(seq)
            if isinstance(v, Exception):
                raise v
            return v
        self.jarvis.llm.model = ClaudeLike()
        with mock.patch.object(self.jarvis.llm, "chat", side_effect=fake_chat):
            out = svc.send(svc.store.new_conversation(), "Frage", "t")
        self.assertIn("Antwort steht.", out["text"])
        self.assertIn("ungeprüft", out["text"])

    def test_testmodell_wird_nicht_doppelt_aufgerufen(self):
        svc = ChatService(self.jarvis, ChatStore(self.tmp / "c3.db"))
        out = svc.send(svc.store.new_conversation(), "Hallo", "t")
        self.assertNotIn("Prüfung", out["text"])


class WebReportage(JarvisBase):
    def setUp(self):
        super().setUp()
        self.auth = wa.AuthStore(self.tmp / "d", self.jarvis.audit, clock=self.clock, iterations=1000)
        self.auth.set_password("nj", PW)
        self.app = WebApp(self.cfg, self.auth, self.jarvis, clock=self.clock)
        page = self.req("GET", "/login").body.decode()
        nonce = re.search(r'name="nonce" value="([^"]+)"', page).group(1)
        r = self.req("POST", "/login", {"username": "nj", "password": PW, "nonce": nonce})
        self.sid = r.header("Set-Cookie").split(";")[0].split("=", 1)[1]

    def req(self, method, path, body=None, cookie=None):
        h = {"Host": HOST}
        if cookie:
            h["Cookie"] = f"jarvis_session={cookie}"
        return self.app.handle(method, path, h, urlencode(body).encode() if body is not None else b"")

    def page(self, path="/chat"):
        r = self.req("GET", path, cookie=self.sid)
        return r.body.decode() if isinstance(r.body, bytes) else r.body

    def send(self, text="Hallo"):
        body = self.page()
        csrf = re.search(r'name="csrf" value="([^"]+)"', body).group(1)
        conv = re.search(r'name="g" value="([^"]+)"', body).group(1)
        self.req("POST", "/chat", {"csrf": csrf, "g": conv, "text": text}, cookie=self.sid)
        return conv

    def test_portal_nur_beim_betreten(self):
        self.assertIn('class="portal"', self.page("/chat?portal=1"))
        self.assertNotIn('class="portal"', self.page("/chat"))
        self.assertIn('href="/chat?portal=1"', self.page("/"))

    def test_reportage_beschriftung_und_vorlesen_knopf(self):
        conv = self.send("Wie geht es?")
        body = self.page(f"/chat?g={conv}")
        self.assertIn("<b>Frage</b>", body)
        self.assertIn("JARVIS · Antwort", body)
        self.assertRegex(body, r'class="speak ghost" type="button" data-id="\d+"')

    def test_stimme_braucht_anmeldung_und_gueltige_id(self):
        self.assertEqual(self.req("GET", "/chat/stimme?id=1").header("Location"), "/login")
        for bad in ("abc", "../x", "1" * 12, ""):
            self.assertEqual(self.req("GET", "/chat/stimme?id=" + bad, cookie=self.sid).status, 404, bad)

    def test_stimme_nur_fuer_jarvis_antworten(self):
        self.send("Meine Frage")
        msgs = self.app.chat.store.history(self.app.chat.store.latest())
        user_id = [m for m in msgs if m["role"] == "du"][0]["id"]
        self.assertEqual(self.req("GET", f"/chat/stimme?id={user_id}", cookie=self.sid).status, 404)

    def test_stimme_liefert_wav_oder_hinweis(self):
        self.send("Hallo")
        jid = [m for m in self.app.chat.store.history(self.app.chat.store.latest()) if m["role"] == "jarvis"][0]["id"]
        with mock.patch("jarvis.voice_fx.jarvis_voice", return_value=b"RIFFtest"):
            r = self.req("GET", f"/chat/stimme?id={jid}", cookie=self.sid)
        self.assertEqual((r.status, r.header("Content-Type")), (200, "audio/wav"))
        with mock.patch("jarvis.voice_fx.jarvis_voice", side_effect=VoiceUnavailable("kein Mac")):
            self.assertEqual(self.req("GET", f"/chat/stimme?id={jid}", cookie=self.sid).status, 501)

    def test_notaus_stoppt_stimme(self):
        self.send("Hallo")
        jid = [m for m in self.app.chat.store.history(self.app.chat.store.latest()) if m["role"] == "jarvis"][0]["id"]
        self.jarvis.kill.activate("test")
        self.assertEqual(self.req("GET", f"/chat/stimme?id={jid}", cookie=self.sid).status, 423)
