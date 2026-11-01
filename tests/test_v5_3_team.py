"""Stand 20: KI-Mitarbeiter-Team – Auswahl, echter Austausch, Ergebnis im Second Brain, Sicherheit, Webseite."""
from __future__ import annotations

import json
import re
from unittest import mock
from urllib.parse import urlencode

from jarvis import web_auth as wa
from jarvis.team import CATEGORIES, MEMBERS, pick_members, platform_data, run_round, safe_category
from jarvis.web import WebApp
from tests.test_knowledge import HOST, PW, JarvisBase, write

AUFGABE = "Wie gewinne ich die ersten 3 Restaurants für die QR-Stempelkarte und was darf es kosten?"


class Auswahl(JarvisBase):
    def test_kategorien_und_skills(self):
        self.assertEqual(len(CATEGORIES), 5)
        self.assertEqual({m["kategorie"] for m in MEMBERS}, {c[0] for c in CATEGORIES})
        for m in MEMBERS:
            self.assertTrue(m["skills"])

    def test_passende_mitarbeiter_nach_stichwoertern(self):
        ids = [m["id"] for m in pick_members(AUFGABE)]
        self.assertLessEqual(len(ids), 4)
        self.assertIn("lena", ids)                                    # „kosten“
        self.assertIn("kai", ids)                                     # „restaurant“

    def test_kategorie_waehlt_genau_diese_gruppe(self):
        self.assertEqual({m["kategorie"] for m in pick_members("irgendwas", "technik")}, {"technik"})
        self.assertEqual(safe_category("../technik"), "technik")
        self.assertEqual(safe_category("unsinn"), "")

    def test_ohne_treffer_grundbesetzung(self):
        self.assertGreaterEqual(len(pick_members("Hallo zusammen, bitte helfen")), 2)


class Runde(JarvisBase):
    def test_testmodus_speichert_runde_im_second_brain(self):
        res = run_round(self.jarvis, AUFGABE)
        self.assertTrue(res["ok"])
        text = res["pfad"].read_text(encoding="utf-8")
        self.assertIn("typ: team-runde", text)
        for name, _, _ in res["beitraege"]:
            self.assertIn(f"### {name}", text)
        self.jarvis.kb.invalidate()
        data = platform_data(self.jarvis.kb)
        self.assertEqual(len(data["rounds"]), 1)
        self.assertTrue(data["links"])                                 # wer zusammengearbeitet hat

    def test_echter_austausch_jeder_liest_die_vorherigen(self):
        class Real:
            name, is_test_mode = "claude-test", False
        self.jarvis.llm.model = Real()
        seen = []

        def fake_chat(system, history, text, **kw):
            seen.append(text)
            return "Beitrag von " + system.split(",")[0].replace("Du bist ", "")
        with mock.patch.object(self.jarvis.llm, "chat", side_effect=fake_chat):
            res = run_round(self.jarvis, AUFGABE)
        n = len(res["beitraege"])
        self.assertEqual(len(seen), n + 1)                             # Mitarbeiter + Zusammenfassung
        first = res["beitraege"][0][0]
        self.assertIn(f"Beitrag von {first}", seen[1])                 # der zweite sieht den ersten
        self.assertIn("<<<TEAM", seen[0])                             # Daten gerahmt

    def test_sicherheit(self):
        self.assertFalse(run_round(self.jarvis, "kurz")["ok"])
        self.assertFalse(run_round(self.jarvis, AUFGABE + " IBAN DE89 3704 0044 0532 0130 00")["ok"])
        self.jarvis.kill.activate("test")
        self.assertFalse(run_round(self.jarvis, AUFGABE)["ok"])

    def test_mitarbeiter_koennen_nichts_ausfuehren(self):
        with mock.patch.object(self.jarvis.gate, "execute", side_effect=AssertionError("Ausführung versucht")):
            self.assertTrue(run_round(self.jarvis, AUFGABE)["ok"])


class Web(JarvisBase):
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

    def test_seite_daten_und_runde(self):
        self.assertEqual(self.req("GET", "/team").header("Location"), "/login")
        page = self.req("GET", "/team", sid=self.sid).body.decode()
        self.assertIn("Dein KI-Team", page)
        for m in MEMBERS:
            self.assertIn(f'id="m-{m["id"]}"', page)
        self.assertEqual(re.findall(r"<script[^>]*>", page), ['<script src="/static/hud.js" defer>'])
        data = json.loads(self.req("GET", "/team/daten", sid=self.sid).body.decode())
        self.assertEqual(len(data["members"]), len(MEMBERS))
        csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
        self.assertEqual(self.req("POST", "/team/runde", {"csrf": "x", "text": AUFGABE}, sid=self.sid).status, 403)
        r = self.req("POST", "/team/runde", {"csrf": csrf, "text": AUFGABE, "kategorie": "finanzen"}, sid=self.sid)
        self.assertTrue(r.header("Location").startswith("/wissen/notiz?id="))

    def test_glas_design_ueberall_ausser_chat(self):
        self.assertIn("theme-glass", self.req("GET", "/", sid=self.sid).body.decode())
        self.assertIn("theme-glass", self.req("GET", "/team", sid=self.sid).body.decode())
        chat = self.req("GET", "/chat", sid=self.sid).body.decode()
        self.assertIn("theme-red", chat)
        self.assertNotIn("theme-glass", chat)
