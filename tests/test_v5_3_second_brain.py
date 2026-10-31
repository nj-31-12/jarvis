"""Version 5.3: Second Brain – Wissenskarte, Aufgaben, Schnell-Erfassung. Vertrauliches erscheint nie."""
from __future__ import annotations

import re
from urllib.parse import urlencode

from jarvis import web_auth as wa
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

    def test_keine_externen_quellen_und_kein_script(self):
        body = self.page()
        self.assertNotIn("<script", body)
        self.assertNotRegex(body, r"https?://(?!127\.0\.0\.1)")
