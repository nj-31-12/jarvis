"""Stand 17: Strategie-Werkstatt und Wissenspaket-Import."""
from __future__ import annotations

import re
import zipfile
from unittest import mock
from urllib.parse import urlencode

from jarvis import web_auth as wa
from jarvis.knowledge_import import TARGET, import_pack
from jarvis.strategy import LENSES, run_strategy, system_prompt
from jarvis.web import WebApp
from tests.test_knowledge import HOST, PW, JarvisBase, write

IDEE = ("QR-Code-Stempelkarten für Restaurants: Gäste sammeln bei jedem Besuch Stempel. Dazu biete ich "
        "Restaurants automatisierte Webseiten und Betreuung an.")


class Strategie(JarvisBase):
    def files(self):
        d = self.vault / "00_Inbox" / "JARVIS" / "Strategien"
        return sorted(d.glob("*.md")) if d.exists() else []

    def test_alle_elf_brillen_im_auftrag(self):
        sp = system_prompt()
        self.assertEqual(len(LENSES), 11)
        for name, _ in LENSES:
            self.assertIn(name, sp)
        self.assertIn("Schätzung", sp)
        self.assertIn("Ausbildung", sp)

    def test_testmodus_legt_vorlage_im_second_brain_an(self):
        msg, path, analysis = run_strategy(self.jarvis, IDEE)
        self.assertIn("Second Brain", msg)
        self.assertEqual(len(self.files()), 1)
        text = path.read_text(encoding="utf-8")
        self.assertIn("typ: strategie", text)
        self.assertIn("QR-Code-Stempelkarten", text)
        for name, _ in LENSES:
            self.assertIn(name, text)

    def test_echte_ki_wird_ueber_die_sicherheitskette_gefragt(self):
        class Real:
            name, is_test_mode = "claude-test", False
        self.jarvis.llm.model = Real()
        with mock.patch.object(self.jarvis.llm, "chat", return_value="## 🎯 Kern und Zielgruppe\nRestaurants …") as chat:
            _, path, analysis = run_strategy(self.jarvis, IDEE)
        self.assertEqual(chat.call_count, 1)
        self.assertIn("Strategie-Werkstatt", chat.call_args[0][0])
        self.assertIn("Restaurants …", path.read_text(encoding="utf-8"))

    def test_zu_kurz_notaus_und_bankdaten(self):
        self.assertIsNone(run_strategy(self.jarvis, "kurz")[1])
        self.assertIsNone(run_strategy(self.jarvis, IDEE + " IBAN DE89 3704 0044 0532 0130 00")[1])
        self.jarvis.kill.activate("test")
        self.assertIsNone(run_strategy(self.jarvis, IDEE)[1])
        self.assertEqual(self.files(), [])

    def test_chatbefehl(self):
        out = self.jarvis.handle_text("/strategie " + IDEE)
        self.assertIn("🧭", out)
        self.assertIn("90-Tage-Plan", out)

    def test_web_werkstatt_leitet_zur_neuen_notiz(self):
        auth = wa.AuthStore(self.tmp / "d", self.jarvis.audit, clock=self.clock, iterations=1000)
        auth.set_password("nj", PW)
        app = WebApp(self.cfg, auth, self.jarvis, clock=self.clock)

        def req(method, path, body=None, sid=None):
            h = {"Host": HOST}
            if sid:
                h["Cookie"] = f"jarvis_session={sid}"
            return app.handle(method, path, h, urlencode(body).encode() if body is not None else b"")
        nonce = re.search(r'name="nonce" value="([^"]+)"', req("GET", "/login").body.decode()).group(1)
        sid = req("POST", "/login", {"username": "nj", "password": PW, "nonce": nonce}).header("Set-Cookie").split(";")[0].split("=", 1)[1]
        page = req("GET", "/gehirn", sid=sid).body.decode()
        self.assertIn("Strategie-Werkstatt", page)
        csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
        self.assertEqual(req("POST", "/gehirn/strategie", {"csrf": "x", "text": IDEE}, sid=sid).status, 403)
        r = req("POST", "/gehirn/strategie", {"csrf": csrf, "text": IDEE}, sid=sid)
        self.assertEqual(r.status, 303)
        self.assertTrue(r.header("Location").startswith("/wissen/notiz?id="))
        note = req("GET", r.header("Location"), sid=sid).body.decode()
        self.assertIn("QR-Code-Stempelkarten", note)
        self.assertIn("Strategie ", req("GET", "/gehirn", sid=sid).body.decode())


class Wissenspaket(JarvisBase):
    def pack(self, files):
        d = self.tmp / "paket"
        d.mkdir(exist_ok=True)
        for name, text in files.items():
            (d / name).write_text(text, encoding="utf-8")
        return d

    def test_import_ordner_und_keine_ueberschreibung(self):
        src = self.pack({"Über mich.md": "# Über mich\nNoah", "Coaching.md": "---\nbereich: nj-coaching\n---\n# NYoung"})
        res = import_pack(self.jarvis.vault, src)
        self.assertEqual(sorted(res["neu"]), ["Coaching.md", "Über mich.md"])
        (src / "Über mich.md").write_text("# NEU", encoding="utf-8")
        res2 = import_pack(self.jarvis.vault, src)
        self.assertEqual(res2["neu"], [])
        self.assertEqual(sorted(res2["vorhanden"]), ["Coaching.md", "Über mich.md"])
        dest = self.vault / TARGET / "Über mich.md"
        self.assertIn("Noah", dest.read_text(encoding="utf-8"))           # nicht überschrieben

    def test_sensible_dateien_werden_abgelehnt(self):
        src = self.pack({"Bank.md": "Konto DE89 3704 0044 0532 0130 00", "Login.md": "Passwort: Geheim123!"})
        res = import_pack(self.jarvis.vault, src)
        self.assertEqual(res["neu"], [])
        self.assertEqual(len(res["abgelehnt"]), 2)

    def test_zip_mit_pfadtricks_bleibt_im_zielordner(self):
        z = self.tmp / "paket.zip"
        with zipfile.ZipFile(z, "w") as f:
            f.writestr("../../ausbruch.md", "# böse")
            f.writestr("/abs/pfad.md", "# absolut")
            f.writestr("ordner/ok.md", "# ok")
            f.writestr("skript.py", "print(1)")
        res = import_pack(self.jarvis.vault, z)
        self.assertEqual(sorted(res["neu"]), ["ausbruch.md", "ok.md", "pfad.md"])
        self.assertFalse((self.tmp / "ausbruch.md").exists())
        for name in res["neu"]:
            self.assertTrue((self.vault / TARGET / name).exists())

    def test_importierte_notizen_sind_im_second_brain(self):
        import_pack(self.jarvis.vault, self.pack({"Restaurant-Idee.md": "# Restaurant QR\nStempelkarte"}))
        self.jarvis.kb.invalidate()
        self.assertIn("Restaurant QR", [n.title for n in self.jarvis.kb.notes()])
