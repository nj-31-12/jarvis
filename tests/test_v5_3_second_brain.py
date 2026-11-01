"""Version 5.3: Second Brain – Wissenskarte, Aufgaben, Schnell-Erfassung. Vertrauliches erscheint nie."""
from __future__ import annotations

import json
import re
from urllib.parse import urlencode

from jarvis import web_auth as wa
from jarvis.chat import ChatService, ChatStore
from jarvis.web import WebApp
from jarvis.web_brain import area_counts, brain_map
from tests.test_knowledge import HOST, PW, JarvisBase, write


class SecondBrainTests(JarvisBase):
    def setUp(self):
        super().setUp()
        write(self.vault, "02_Projekte/Aufgaben.md", "# Coaching Plan\n- [ ] Preise für Coaching-Paket festlegen\n- [x] erledigt")
        write(self.vault, "90_Privat/Geheimes Projekt.md", "# Streng geheim\n- [ ] GEHEIME-AUFGABE")
        self.jarvis.kb.invalidate()
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

    def page(self):
        return self.req("GET", "/gehirn", cookie=self.sid).body.decode()

    def csrf(self):
        return re.search(r'name="csrf" value="([^"]+)"', self.page()).group(1)

    def inbox(self):
        folder = self.vault / "00_Inbox" / "JARVIS"
        return sorted(p.name for p in folder.glob("*.md")) if folder.exists() else []

    def test_braucht_anmeldung(self):
        self.assertEqual(self.req("GET", "/gehirn").header("Location"), "/login")
        self.assertEqual(self.req("POST", "/gehirn/notiz", {"text": "x"}).header("Location"), "/login")

    def test_seite_zeigt_karte_bereiche_und_aufgaben(self):
        body = self.page()
        self.assertIn("Dein zweites Gehirn", body)
        self.assertIn("brain-map", body)
        self.assertIn("NJ Coaching", body)
        self.assertIn("Preise für Coaching-Paket festlegen", body)
        self.assertNotIn("erledigt", body.split("Offene Aufgaben")[1].split("</section>")[0])

    def test_vertrauliches_erscheint_nie(self):
        body = self.page()
        for secret in ("Streng geheim", "GEHEIME-AUFGABE", "Geheimes Projekt", "Tagebuch"):
            self.assertNotIn(secret, body)

    def test_karte_zaehlt_keine_vertraulichen_notizen(self):
        counts = {a["slug"]: a["count"] for a in area_counts(self.jarvis.kb)}
        visible_scent = sum(1 for n in self.jarvis.kb.notes() if "scent" in (n.title + n.text).lower())
        self.assertLessEqual(counts["scent-edit"], visible_scent)

    def test_erfassen_legt_neue_notiz_in_der_inbox_an(self):
        before = self.inbox()
        r = self.req("POST", "/gehirn/notiz", {"csrf": self.csrf(), "text": "- [ ] Neue Idee testen"}, cookie=self.sid)
        self.assertEqual(r.status, 303)
        self.assertEqual(len(self.inbox()), len(before) + 1)
        self.assertIn("Gespeichert", self.page())

    def test_erfassen_ohne_pruefzeichen_wird_abgelehnt(self):
        before = self.inbox()
        r = self.req("POST", "/gehirn/notiz", {"csrf": "falsch", "text": "x"}, cookie=self.sid)
        self.assertEqual(r.status, 403)
        self.assertEqual(self.inbox(), before)

    def test_notaus_verhindert_erfassen(self):
        token = self.csrf()
        self.jarvis.kill.activate("test")
        before = self.inbox()
        self.req("POST", "/gehirn/notiz", {"csrf": token, "text": "nicht speichern"}, cookie=self.sid)
        self.assertEqual(self.inbox(), before)
        self.assertIn("Notabschaltung", self.page())

    def test_karte_ist_sicher_maskiert(self):
        svg = brain_map([{"slug": "x", "name": "<script>", "status": "aktiv", "count": 3, "search": "a&b"}], 3)
        self.assertNotIn("<script>", svg)
        self.assertIn("&lt;script&gt;", svg)
        self.assertIn("a%26b", svg)

    def test_vorlagen_erscheinen_nicht(self):
        write(self.vault, "99_Vorlagen/Leer.md", "# {{Titel}} VORLAGE-XYZ")
        self.jarvis.kb.invalidate()
        self.assertNotIn("VORLAGE-XYZ", self.page())

    def test_nur_eigenes_lokales_skript_keine_externen_quellen(self):
        body = self.page()
        self.assertEqual(re.findall(r"<script[^>]*>", body),
                         ['<script src="/static/brain.js" defer>', '<script src="/static/hud.js" defer>'])
        self.assertIn('<script src="/static/brain.js" defer></script>', body)        # leer, kein Inline-Code
        self.assertNotRegex(body, r"https?://(?!127\.0\.0\.1)")
        js = self.req("GET", "/static/brain.js")
        self.assertEqual(js.status, 200)
        code = js.body.decode() if isinstance(js.body, bytes) else js.body
        self.assertNotRegex(code, r"https?://")                                     # kein CDN, kein fremder Server
        self.assertNotIn("innerHTML", code)                                         # Titel nur als Text
        self.assertNotIn("eval(", code)

    # ------------------------------------------------------------- 3D-Daten
    def data(self):
        r = self.req("GET", "/gehirn/daten", cookie=self.sid)
        self.assertEqual(r.status, 200)
        return json.loads(r.body.decode() if isinstance(r.body, bytes) else r.body)

    def test_daten_brauchen_anmeldung(self):
        self.assertEqual(self.req("GET", "/gehirn/daten").header("Location"), "/login")

    def test_daten_ohne_vertrauliches_und_ohne_inhalte(self):
        raw = json.dumps(self.data(), ensure_ascii=False)
        for secret in ("Streng geheim", "GEHEIME-AUFGABE", "Geheimes Projekt", "Tagebuch", "Geheim123", "DE89"):
            self.assertNotIn(secret, raw)
        self.assertNotIn("Preise für Coaching-Paket", raw)                          # nur Titel, keine Inhalte
        self.assertIn("Coaching Plan", raw)

    def test_lebensthemen_entstehen_aus_dem_vault(self):
        write(self.vault, "08_Auto/Ölwechsel.md", "# Ölwechsel A5\nTermin machen")
        write(self.vault, "08_Auto/Reifen.md", "# Winterreifen\nPreise vergleichen")
        self.jarvis.kb.invalidate()
        d = self.data()
        names = [a["name"] for a in d["areas"]]
        self.assertTrue(any(n == "Auto" for n in names), names)
        topic = [a for a in d["areas"] if a["name"] == "Auto"][0]
        self.assertEqual(topic["status"], "Thema")

    def test_verlinkungen_zwischen_notizen(self):
        write(self.vault, "02_Projekte/A.md", "# Alpha\nsiehe [[Beta]]")
        write(self.vault, "02_Projekte/B.md", "# Beta\nText")
        self.jarvis.kb.invalidate()
        d = self.data()
        titles = [n["title"] for n in d["notes"]]
        self.assertIn([titles.index("Alpha"), titles.index("Beta")], d["links"])

    # ------------------------------------------------------------- Lektionen
    def test_lektion_merken_und_in_jeder_antwort(self):
        r = self.req("POST", "/gehirn/lektion", {"csrf": self.csrf(), "text": "Immer den Zweig version5-3 laden"},
                     cookie=self.sid)
        self.assertEqual(r.status, 303)
        self.assertIn("Lektion gespeichert", self.page())
        self.assertIn("Immer den Zweig version5-3 laden", self.page())
        prompt = ChatService(self.jarvis, ChatStore(self.tmp / "c.db"))._prompt_with_knowledge([])
        self.assertIn("Immer den Zweig version5-3 laden", prompt)
        self.assertIn("LEKTION-", prompt)

    def test_lektion_mit_bankdaten_wird_abgelehnt(self):
        before = self.inbox()
        self.req("POST", "/gehirn/lektion", {"csrf": self.csrf(), "text": "IBAN DE89 3704 0044 0532 0130 00"},
                 cookie=self.sid)
        self.assertEqual(self.inbox(), before)
        self.assertIn("sensible Daten", self.page())

    def test_lektion_ohne_pruefzeichen_und_bei_notaus(self):
        before = self.inbox()
        self.assertEqual(self.req("POST", "/gehirn/lektion", {"csrf": "x", "text": "a"}, cookie=self.sid).status, 403)
        token = self.csrf()
        self.jarvis.kill.activate("test")
        self.req("POST", "/gehirn/lektion", {"csrf": token, "text": "nicht speichern"}, cookie=self.sid)
        self.assertEqual(self.inbox(), before)

    def test_vertrauliche_lektion_geht_nie_ans_modell(self):
        write(self.vault, "90_Privat/L.md", "---\ntyp: lektion\n---\n# Lektion\nGEHEIME-LEKTION")
        self.jarvis.kb.invalidate()
        prompt = ChatService(self.jarvis, ChatStore(self.tmp / "c2.db"))._prompt_with_knowledge([])
        self.assertNotIn("GEHEIME-LEKTION", prompt)

    def test_ohne_lektionen_bleibt_systemanweisung_unveraendert(self):
        svc = ChatService(self.jarvis, ChatStore(self.tmp / "c3.db"))
        self.assertEqual(svc._prompt_with_knowledge([]), svc.system_prompt)


class PersonaTests(JarvisBase):
    def test_jarvis_ist_fuer_das_ganze_leben_da_und_variiert(self):
        from jarvis.persona import build_system_prompt
        prompt = build_system_prompt(self.cfg)
        self.assertIn("ganzes Leben", prompt)
        self.assertIn("Variiere Form und Länge", prompt)
        self.assertIn("keine Diagnosen", prompt)
        self.assertIn("Freigabeschicht", prompt)                                    # Grenzen bleiben
