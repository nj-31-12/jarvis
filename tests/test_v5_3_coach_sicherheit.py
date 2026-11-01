"""Stand 18: Daten-Wächter, Coach-Check mit Lektions-Vorschlägen, Sprach-Bedienelemente."""
from __future__ import annotations

import re
import unittest
from urllib.parse import urlencode

from jarvis import web_auth as wa
from jarvis.chat import ChatService, ChatStore
from jarvis.coach import offline_report, proposals, run_coach, save_report
from jarvis.data_guard import banner, check
from jarvis.lessons import lessons
from jarvis.web import WebApp
from tests.test_knowledge import HOST, PW, JarvisBase, write

PHISH = ("Ihr Konto wurde gesperrt! Bestätigen Sie innerhalb von 24 Stunden Ihr Passwort und den SMS-Code "
         "unter https://sparkasse-sicher.example.com")


class DatenWaechter(unittest.TestCase):
    def test_phishing_wird_hoch_eingestuft(self):
        r = check(PHISH)
        self.assertEqual(r["level"], "hoch")
        for s in ("Passwort oder PIN", "Code oder TAN", "Link", "Zeitdruck"):
            self.assertIn(s, r["signals"])
        self.assertIn("Gib nichts weiter", banner(r))

    def test_harmlose_nachricht_bleibt_ruhig(self):
        for t in ("Was soll ich heute trainieren?", "Erstelle mir einen Plan für die Berufsschule.",
                  "Schick mir Ideen für Instagram-Posts"):
            self.assertEqual(check(t)["level"], "", t)
            self.assertEqual(banner(check(t)), "")

    def test_eigene_frage_zu_passwort_ist_mittel(self):
        self.assertEqual(check("Wie merke ich mir mein Passwort besser?")["level"], "mittel")

    def test_bankdaten_anfrage(self):
        self.assertEqual(check("Bitte senden Sie uns Ihre IBAN und eine Ausweiskopie.")["level"], "hoch")


class ChatMitWaechter(JarvisBase):
    def test_warnung_steht_ueber_der_antwort_und_inhalt_nicht_im_protokoll(self):
        svc = ChatService(self.jarvis, ChatStore(self.tmp / "c.db"))
        out = svc.send(svc.store.new_conversation(), PHISH, "t")
        self.assertTrue(out["text"].startswith("🛡"))
        log = (self.tmp / "d" / "audit.jsonl").read_text(encoding="utf-8") if (self.tmp / "d" / "audit.jsonl").exists() \
            else self.jarvis.audit.path.read_text(encoding="utf-8")
        self.assertIn("data_request_flagged", log)
        self.assertNotIn("sparkasse-sicher", log)


class Coach(JarvisBase):
    def test_offline_bericht_mit_vorschlaegen(self):
        data = {"ziele": [], "aufgaben": [f"A{i}" for i in range(15)], "strategien": ["Strategie X"],
                "lektionen": [], "zuletzt": []}
        text = offline_report(data)
        self.assertIn("- [ ] A0", text)
        self.assertIn("LEKTION: Pro Woche höchstens drei Hauptaufgaben", text)

    def test_bericht_speichern_vorschlag_erst_nach_bestaetigung_aktiv(self):
        for i in range(14):
            write(self.vault, f"02_Projekte/T{i}.md", f"# T{i}\n- [ ] Aufgabe {i}")
        self.jarvis.kb.invalidate()
        _, text = run_coach(self.jarvis)
        save_report(self.jarvis, text)
        props = proposals(self.jarvis.kb)
        self.assertTrue(props)
        self.assertEqual(lessons(self.jarvis.kb), [])                       # Vorschlag ist NICHT aktiv
        from jarvis.lessons import add_lesson
        add_lesson(self.jarvis, props[0])                                  # Noahs ✓
        self.assertEqual(len(lessons(self.jarvis.kb)), 1)
        self.assertNotIn(props[0], proposals(self.jarvis.kb))              # übernommen → kein Vorschlag mehr

    def test_coach_liest_nichts_vertrauliches(self):
        write(self.vault, "90_Privat/Geheim.md", "# Geheim\n- [ ] GEHEIME-AUFGABE")
        self.jarvis.kb.invalidate()
        _, text = run_coach(self.jarvis)
        self.assertNotIn("GEHEIME-AUFGABE", text)


class WebCoachUndSprache(JarvisBase):
    def setUp(self):
        super().setUp()
        auth = wa.AuthStore(self.tmp / "d", self.jarvis.audit, clock=self.clock, iterations=1000)
        auth.set_password("nj", PW)
        self.app = WebApp(self.cfg, auth, self.jarvis, clock=self.clock)
        nonce = re.search(r'name="nonce" value="([^"]+)"', self.req("GET", "/login").body.decode()).group(1)
        r = self.req("POST", "/login", {"username": "nj", "password": PW, "nonce": nonce})
        self.sid = r.header("Set-Cookie").split(";")[0].split("=", 1)[1]

    def req(self, method, path, body=None, sid=None):
        h = {"Host": HOST}
        if sid:
            h["Cookie"] = f"jarvis_session={sid}"
        return self.app.handle(method, path, h, urlencode(body).encode() if body is not None else b"")

    def test_coach_knopf_legt_bericht_an(self):
        page = self.req("GET", "/gehirn", sid=self.sid).body.decode()
        self.assertIn("Coach-Check jetzt", page)
        csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
        self.assertEqual(self.req("POST", "/gehirn/coach", {"csrf": "x"}, sid=self.sid).status, 403)
        r = self.req("POST", "/gehirn/coach", {"csrf": csrf}, sid=self.sid)
        self.assertTrue(r.header("Location").startswith("/wissen/notiz?id="))

    def test_chat_hat_sprachbedienung_versteckt_bis_skript_laeuft(self):
        page = self.req("GET", "/chat", sid=self.sid).body.decode()
        self.assertIn('<div class="voice-ctl" hidden>', page)
        self.assertIn('id="wake"', page)
        self.assertNotIn('id="wake" checked', page)                         # Wake-Word standardmäßig AUS
