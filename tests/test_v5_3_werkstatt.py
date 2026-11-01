"""Stand 23: Webseiten-Werkstatt, Auftrags-Zentrale, Sprach-Ansicht – Funktion und Sicherheit."""
from __future__ import annotations

import json
import re
import socket
import time
from pathlib import Path
from unittest import mock
from urllib.parse import urlencode

from jarvis import web_auth as wa
from jarvis.ai_models import ModelBlocked
from jarvis.ai_providers.anthropic import WEB_SEARCH_TOOL, AnthropicModel
from jarvis.missions import MissionRunner, _parse_businesses, settings
from jarvis.site_builder import build_site, clean_content, parse_json_object, render
from jarvis.site_check import SiteCheckError, _public_host, analyze, check_site, fetch, normalize_url
from jarvis.web import WebApp
from jarvis.web_missions import detect_intent
from tests.test_knowledge import HOST, PW, JarvisBase

ALT = """<html><head><title>Pizzeria Alt</title></head><body><center><font face=arial>Willkommen</font></center>
<table><tr><td><table><tr><td>Menü</td></tr></table></td></tr></table><script src="jquery-1.4.2.js"></script>
<p>&copy; 2014 Pizzeria Alt</p></body></html>"""
NEU = """<html><head><meta name="viewport" content="width=device-width"><title>Café Neu</title>
<meta name="description" content="Frühstück in Bremen"><meta property="og:title" content="Café Neu"></head>
<body><a href="/reservieren">Tisch reservieren</a><footer>© 2026 · <a href="/impressum">Impressum</a> · <a href="/datenschutz">Datenschutz</a></footer></body></html>"""


def page(doc, https=True, url="https://beispiel.de/"):
    return {"url": url, "html": doc, "https": https, "bytes": len(doc), "sekunden": 0.4}


class WebseitenCheck(JarvisBase):
    def test_nur_oeffentliche_adressen(self):
        for bad in ("ftp://x.de", "http://localhost/", "http://router.local/", "https://user:pw@x.de/",
                    "https://x.de:8080/", "http://192.168.0.1/", "nurtext", ""):
            with self.assertRaises(SiteCheckError, msg=bad):
                normalize_url(bad)
                _public_host(normalize_url(bad).split("/")[2])
        self.assertEqual(normalize_url("Beispiel.DE/menu#oben"), "https://beispiel.de/menu")

    def test_name_zeigt_ins_heimnetz(self):
        fake = [(socket.AF_INET, 1, 6, "", ("192.168.178.1", 0))]
        with mock.patch("socket.getaddrinfo", return_value=fake):
            with self.assertRaises(SiteCheckError):
                _public_host("boese.example")
        with mock.patch("socket.getaddrinfo", return_value=[(socket.AF_INET, 1, 6, "", ("127.0.0.1", 0))]):
            res = check_site("https://boese.example/")
        self.assertIsNone(res["punkte"])
        self.assertIn("privat", res["befunde"][0])

    def test_kein_abruf_wenn_pruefung_scheitert(self):
        def resolver(host):
            raise SiteCheckError("gesperrt")
        with mock.patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("Abruf trotz Sperre")):
            with self.assertRaises(SiteCheckError):
                fetch("https://irgendwo.de/", resolver=resolver)

    def test_bewertung_alt_gegen_neu(self):
        alt = analyze(page(ALT, https=False), now_year=2026)
        neu = analyze(page(NEU), now_year=2026)
        self.assertLess(alt["punkte"], 50)
        self.assertEqual(alt["urteil"], "veraltet")
        text = " ".join(alt["befunde"])
        for wort in ("https", "Handys", "2014", "Tabellen", "jQuery 1.4"):
            self.assertIn(wort, text)
        self.assertGreaterEqual(neu["punkte"], 75)
        self.assertEqual(neu["titel"], "Café Neu")


class Baukasten(JarvisBase):
    def test_texte_werden_maskiert_und_begrenzt(self):
        c = clean_content({"name": "<script>alert(1)</script>Bistro", "slogan": "x" * 500,
                           "farben": {"primaer": "red;}</style><script>", "dunkel": "#123456"},
                           "leistungen": [{"titel": f"L{i}", "text": "t"} for i in range(20)], "stil": "böse"})
        self.assertEqual(len(c["slogan"]), 90)
        self.assertEqual(len(c["leistungen"]), 6)
        self.assertEqual(c["stil"], "elegant")
        self.assertEqual(c["dunkel"], "#123456")
        files = render(c)
        self.assertNotIn("<script>alert", files["index.html"])
        self.assertIn("&lt;script&gt;", files["index.html"])
        self.assertNotIn("</style>", files["style.css"])
        self.assertEqual(re.findall(r"<script[^>]*>", files["index.html"]), ['<script src="script.js">'])
        self.assertNotIn("http", files["script.js"].split("*/", 1)[1])     # kein Internet, kein CDN

    def test_ordner_nie_ueberschreiben_und_platzhalter(self):
        a = build_site({"name": "Café Sonne"}, self.tmp / "web")
        b = build_site({"name": "Café Sonne"}, self.tmp / "web", {"../boese.txt": "x", "Brief.md": "ok"})
        self.assertNotEqual(a, b)
        self.assertTrue((b / "Brief.md").exists())
        self.assertFalse((self.tmp / "boese.txt").exists())
        html = (a / "index.html").read_text(encoding="utf-8")
        self.assertIn("[bitte eintragen]", html)                          # keine erfundenen Kontaktdaten
        self.assertIn("Impressum", html)
        self.assertIn('name="viewport"', html)

    def test_json_aus_antwort(self):
        self.assertEqual(parse_json_object('Hier:\n```json\n{"name": "A", "x": {"y": 1}}\n```'), {"name": "A", "x": {"y": 1}})
        self.assertEqual(parse_json_object("kein json"), {})


class ClaudeWebsuche(JarvisBase):
    def test_kosten_mit_suche(self):
        m = AnthropicModel("claude-haiku-5-5")
        self.assertGreater(m.max_cost_eur("websuche", 2000, 4), m.max_cost_eur("websuche", 2000) + 0.04)
        cost = m.actual_cost_eur({"input_tokens": 1000, "output_tokens": 100, "server_tool_use": {"web_search_requests": 3}})
        self.assertAlmostEqual(cost, 0.03 + (1000 * 0.1 + 100 * 0.5) / 1e6)

    def test_anfrage_enthaelt_begrenztes_werkzeug(self):
        m = AnthropicModel("claude-haiku-5-5")
        with mock.patch.object(m, "_send", return_value=("[]", 0.0)) as send:
            m.search_billed("Suche", "k", max_uses=50)
        tool = send.call_args[0][0]["tools"][0]
        self.assertEqual(tool["type"], WEB_SEARCH_TOOL)
        self.assertEqual(tool["max_uses"], 10)
        self.assertEqual(tool["user_location"]["country"], "DE")

    def test_testmodell_sucht_nicht(self):
        with self.assertRaises(ModelBlocked):
            self.jarvis.llm.web_search("x", 2, 0.15)

    def test_limit_zu_klein_nichts_gesendet(self):
        m = AnthropicModel("claude-sonnet-5-5")
        r = self.jarvis.llm
        from jarvis.ai_models import Decision
        with mock.patch.object(r, "_admit", return_value=(m, Decision("claude-sonnet-5-5", "extern", 0.05, "JARVIS_X"))), \
                mock.patch.object(r, "_guard") as guard, mock.patch.object(m, "_send", side_effect=AssertionError("gesendet")):
            guard.return_value.prepare.return_value = ("", [], "x")
            with self.assertRaises(ModelBlocked):
                r.web_search("x", 6, 0.05)

    def test_pause_turn_ohne_text(self):
        m = AnthropicModel("claude-haiku-5-5")
        text, _ = m._parse({"stop_reason": "pause_turn", "content": [], "usage": {"input_tokens": 1, "output_tokens": 1}})
        self.assertIn("unvollständig", text)


class Auftraege(JarvisBase):
    def setUp(self):
        super().setUp()
        self.jarvis.cfg["werkstatt"] = {"output_dir": str(self.tmp / "web"), "web_research_allowed": False}
        self.opened = []
        self.runner = MissionRunner(self.jarvis, opener=self.opened.append,
                                    fetch_check=lambda url: analyze(page(ALT if "alt" in url else NEU, url=url), 2026))

    def test_webseite_im_testmodus(self):
        m = self.runner.start("webseite", {"name": "Bäckerei Korn", "branche": "Bäckerei", "ort": "Bremen",
                                           "url": "https://alt.de"}, background=False)
        self.assertEqual(m.status, "fertig")
        folder = Path(m.result["ordner"])
        for f in ("index.html", "style.css", "script.js", "Anschreiben-Entwurf.md", "Besuchs-Leitfaden.md"):
            self.assertTrue((folder / f).exists(), f)
        self.assertIn("nicht gesendet", (folder / "Anschreiben-Entwurf.md").read_text(encoding="utf-8"))
        texts = " ".join(s["text"] for s in m.steps)
        self.assertIn("Check ist ausgeschaltet", texts)                   # ohne Freigabe kein Abruf der alten Seite
        self.assertIn("Gesendet wurde nichts", texts)
        self.assertEqual(self.runner.open_result(m.id), "Geöffnet.")
        self.assertEqual(self.opened, [folder.resolve() / "index.html"])

    def test_akquise_braucht_freigabe(self):
        with mock.patch.object(self.jarvis.llm, "web_search", side_effect=AssertionError("gesucht")):
            m = self.runner.start("akquise", {"branche": "Restaurants", "ort": "Bremen"}, background=False)
        self.assertEqual(m.status, "gestoppt")
        self.assertIn("werkstatt-an", " ".join(s["detail"] for s in m.steps))

    def test_akquise_ablauf_waehlt_schwaechste_seite(self):
        self.jarvis.cfg["werkstatt"]["web_research_allowed"] = True
        answer = json.dumps([{"name": "Pizzeria Alt", "webseite": "https://alt-pizza.de"},
                             {"name": "Café Neu", "webseite": "https://cafe-neu.de"},
                             {"name": "Kette", "webseite": "https://www.facebook.com/kette"}])
        with mock.patch.object(type(self.jarvis.llm.model), "is_test_mode", False), \
                mock.patch.object(self.jarvis.llm, "web_search", return_value="Gefunden:\n" + answer), \
                mock.patch.object(self.jarvis.llm, "complete", return_value='{"name": "Pizzeria Alt", "slogan": "Echt italienisch"}'), \
                mock.patch.object(self.jarvis.gate, "execute", side_effect=AssertionError("Aktion ausgeführt")):
            m = self.runner.start("akquise", {"branche": "Restaurants", "ort": "Bremen"}, background=False)
        self.assertEqual(m.status, "fertig", [s["text"] for s in m.steps])
        self.assertEqual(m.result["name"], "Pizzeria Alt")
        self.assertEqual([b["name"] for b in m.result["betriebe"]], ["Pizzeria Alt", "Café Neu"])   # Facebook raus
        self.assertIn("Echt italienisch", (Path(m.result["ordner"]) / "index.html").read_text(encoding="utf-8"))

    def test_stopp_notaus_und_grenzen(self):
        with self.assertRaises(ValueError):
            self.runner.start("akquise", {"branche": "Restaurants"})
        with self.assertRaises(ValueError):
            self.runner.start("rm -rf", {"name": "x"})
        self.jarvis.kill.activate("test")
        with self.assertRaises(Exception):
            self.runner.start("webseite", {"name": "X"})
        self.jarvis.kill.release()
        m = self.runner.start("webseite", {"name": "X"}, background=False)
        self.assertFalse(self.runner.stop(m.id))                           # schon fertig
        self.assertIsNone(self.runner.get("../../etc"))

    def test_verlauf_bleibt_nach_neustart(self):
        m = self.runner.start("webseite", {"name": "Y"}, background=False)
        again = MissionRunner(self.jarvis)
        self.assertEqual(again.get(m.id).status, "fertig")

    def test_oeffnen_nur_aus_der_werkstatt(self):
        m = self.runner.start("webseite", {"name": "Z"}, background=False)
        m.result["seite"] = "/etc/passwd"
        self.assertIn("nicht in der Werkstatt", self.runner.open_result(m.id))
        self.assertEqual(self.opened, [])

    def test_betriebe_aus_antwort(self):
        out = _parse_businesses('[{"name":"A","webseite":"https://a.de"},{"name":"A2","webseite":"https://www.a.de/x"},'
                                '{"name":"B","webseite":"javascript:alert(1)"},{"name":"C","website":"http://c.de"}]', 5)
        self.assertEqual([b["name"] for b in out], ["A", "C"])

    def test_einstellungen_begrenzt(self):
        self.jarvis.cfg["werkstatt"] = {"max_betriebe": 999, "max_eur_pro_suche": 50, "web_research_allowed": "ja"}
        w = settings(self.jarvis.cfg)
        self.assertEqual(w["max_betriebe"], 8)
        self.assertEqual(w["max_eur_pro_suche"], 0.5)
        self.assertFalse(w["web_research_allowed"])                      # nur echtes true schaltet ein


class Absicht(JarvisBase):
    def test_erkennt_auftraege(self):
        self.assertEqual(detect_intent("Jarvis, such mir Restaurants in Bremen mit schlechten Webseiten"),
                         {"art": "akquise", "branche": "Restaurants", "ort": "Bremen"})
        self.assertEqual(detect_intent("Bau eine Webseite für Café Sonne")["name"], "Café Sonne")
        self.assertIsNone(detect_intent("Wie wird das Wetter in Bremen?"))


class WebSeiten(JarvisBase):
    def setUp(self):
        super().setUp()
        self.jarvis.cfg["werkstatt"] = {"output_dir": str(self.tmp / "web")}
        auth = wa.AuthStore(self.tmp / "d", self.jarvis.audit, clock=self.clock, iterations=1000)
        auth.set_password("nj", PW)
        self.app = WebApp(self.cfg, auth, self.jarvis, clock=self.clock)
        nonce = re.search(r'name="nonce" value="([^"]+)"', self.req("GET", "/login").body.decode()).group(1)
        r = self.req("POST", "/login", {"username": "nj", "password": PW, "nonce": nonce})
        self.sid = r.header("Set-Cookie").split(";")[0].split("=", 1)[1]
        self.csrf = re.search(r'name="csrf" value="([^"]+)"', self.req("GET", "/auftraege", sid=self.sid).body.decode()).group(1)

    def req(self, method, path, body=None, sid=None):
        h = {"Host": HOST}
        if sid:
            h["Cookie"] = f"jarvis_session={sid}"
        return self.app.handle(method, path, h, urlencode(body).encode() if body is not None else b"")

    def test_anmeldung_und_pruefzeichen(self):
        for p in ("/stimme", "/auftraege", "/auftraege/daten?id=abc"):
            self.assertEqual(self.req("GET", p).header("Location"), "/login")
        self.assertEqual(self.req("POST", "/stimme/frage", {"csrf": "x", "text": "hi"}, sid=self.sid).status, 403)
        self.assertEqual(self.req("POST", "/auftraege/start", {"csrf": "x", "art": "webseite", "name": "A"}, sid=self.sid).status, 403)

    def test_stimme_seite_und_antwort(self):
        page = self.req("GET", "/stimme", sid=self.sid).body.decode()
        self.assertIn('data-orb', page)
        self.assertEqual(re.findall(r"<script[^>]*>", page), ['<script src="/static/orb.js" defer>', '<script src="/static/voice.js" defer>'])
        r = json.loads(self.req("POST", "/stimme/frage", {"csrf": self.csrf, "text": "Hallo Jarvis"}, sid=self.sid).body)
        self.assertTrue(r["ok"])
        self.assertTrue(r["audio"].startswith("/chat/stimme?id="))

    def test_sprachauftrag_erst_nach_ja(self):
        r = json.loads(self.req("POST", "/stimme/frage", {"csrf": self.csrf, "text": "Bau eine Webseite für Eiscafé Venezia"}, sid=self.sid).body)
        self.assertEqual(r["vorschlag"]["art"], "webseite")
        self.assertEqual(self.app._runner().missions, {})                   # noch nichts gestartet
        tone = self.req("GET", r["audio"], sid=self.sid)
        self.assertIn(tone.status, (200, 501))                             # 501 = keine Mac-Stimme (Linux)
        self.assertEqual(self.req("GET", "/stimme/ton?k=erfunden", sid=self.sid).status, 404)
        r2 = json.loads(self.req("POST", "/stimme/frage", {"csrf": self.csrf, "text": "Ja, starte"}, sid=self.sid).body)
        self.assertTrue(r2["weiter"].startswith("/auftraege?id="))
        self.assertEqual(len(self.app._runner().missions), 1)
        for _ in range(100):                                              # Auftrag zu Ende laufen lassen
            if not self.app._runner().running():
                break
            time.sleep(0.05)

    def test_auftrag_live(self):
        r = self.req("POST", "/auftraege/start", {"csrf": self.csrf, "art": "webseite", "name": "Salon Schnitt"}, sid=self.sid)
        loc = r.header("Location")
        mid = loc.split("=")[1]
        for _ in range(100):
            d = json.loads(self.req("GET", f"/auftraege/daten?id={mid}&ab=0", sid=self.sid).body)
            if d["status"] != "läuft":
                break
            time.sleep(0.05)
        self.assertEqual(d["status"], "fertig")
        self.assertTrue(d["schritte"])
        page = self.req("GET", loc, sid=self.sid).body.decode()
        self.assertIn("Schnellablauf", page)
        self.assertIn("Salon Schnitt", page)
        later = json.loads(self.req("GET", f"/auftraege/daten?id={mid}&ab=2", sid=self.sid).body)
        self.assertTrue(all(s["n"] >= 2 for s in later["schritte"]))
        self.assertIn(self.req("GET", f"/auftraege/stimme?id={mid}&n=0", sid=self.sid).status, (200, 501))
        self.assertEqual(self.req("GET", f"/auftraege/stimme?id={mid}&n=999", sid=self.sid).status, 404)

    def test_statische_dateien_und_menue(self):
        for f in ("orb.js", "voice.js", "missions.js"):
            self.assertEqual(self.req("GET", "/static/" + f).status, 200)
        home = self.req("GET", "/", sid=self.sid).body.decode()
        self.assertIn('href="/stimme"', home)
        self.assertIn('href="/auftraege"', home)

    def test_fehleingabe_zurueck_zum_formular(self):
        r = self.req("POST", "/auftraege/start", {"csrf": self.csrf, "art": "akquise", "branche": "Friseure"}, sid=self.sid)
        self.assertTrue(r.header("Location").startswith("/auftraege?"))
        self.assertIn("Branche und Ort", self.req("GET", r.header("Location"), sid=self.sid).body.decode())


class Schalter(JarvisBase):
    def test_werkstatt_an_und_aus(self):
        from jarvis.__main__ import werkstatt
        p = self.tmp / "jarvis.json"
        p.write_text(json.dumps({"ai": {"models": {"claude-haiku-5-5": {"tasks": ["chat"]}, "b": {}}}}), encoding="utf-8")
        with mock.patch("builtins.print"):
            werkstatt(True, p)
        d = json.loads(p.read_text(encoding="utf-8"))
        self.assertTrue(d["werkstatt"]["web_research_allowed"])
        self.assertEqual(d["ai"]["models"]["claude-haiku-5-5"]["tasks"], ["chat", "websuche", "webseite"])
        self.assertEqual(d["ai"]["models"]["b"], {})
        with mock.patch("builtins.print"):
            werkstatt(False, p)
        self.assertFalse(json.loads(p.read_text(encoding="utf-8"))["werkstatt"]["web_research_allowed"])
