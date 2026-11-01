"""Stand 24: Bauen im Gespräch, kostenlose Bilder, aktuelles Wissen per Websuche."""
from __future__ import annotations

import base64
import io
import json
import time
from pathlib import Path
from unittest import mock

from jarvis.ai_providers.anthropic import AnthropicModel
from jarvis.chat import ChatService, ChatStore
from jarvis.markdown_safe import render
from jarvis.media import MediaError, generate_image
from jarvis.missions import MissionRunner, extract_html, get_runner
from tests.test_knowledge import JarvisBase

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 50


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Opener:
    def __init__(self, payload):
        self.payload, self.reqs = payload, []

    def open(self, req, timeout=0):
        self.reqs.append(req)
        return FakeResp(json.dumps(self.payload).encode())


class Base(JarvisBase):
    def setUp(self):
        super().setUp()
        self.jarvis.cfg["werkstatt"] = {"output_dir": str(self.tmp / "web"), "projekte_dir": str(self.tmp / "proj"),
                                        "bilder_dir": str(self.tmp / "img"), "web_research_allowed": True}
        self.opened = []
        self.runner = MissionRunner(self.jarvis, opener=self.opened.append)

    def real(self):
        return mock.patch.object(type(self.jarvis.llm.model), "is_test_mode", False)


class Projekte(Base):
    def test_baut_und_oeffnet(self):
        html = "Hier ist es:\n```html\n<!doctype html><html><body><h1>Rechner</h1></body></html>\n```"
        with self.real(), mock.patch.object(self.jarvis.llm, "build", return_value=html) as b:
            m = self.runner.start("projekt", {"beschreibung": "Bau mir einen Kalorienrechner"}, background=False)
        self.assertEqual(m.status, "fertig", [s["text"] for s in m.steps])
        self.assertEqual(b.call_args.kwargs["cap_eur"], 0.30)
        page = Path(m.result["seite"])
        self.assertTrue(page.read_text().startswith("<!doctype html>"))
        self.assertEqual(self.opened, [page.resolve()])                    # automatisch geöffnet

    def test_testmodus_und_unbrauchbar(self):
        m = self.runner.start("projekt", {"beschreibung": "Bau mir ein Spiel"}, background=False)
        self.assertEqual(m.status, "gestoppt")
        with self.real(), mock.patch.object(self.jarvis.llm, "build", return_value="Leider nein"):
            m = self.runner.start("projekt", {"beschreibung": "Bau mir ein Spiel"}, background=False)
        self.assertEqual(m.status, "fehler")
        with self.assertRaises(ValueError):
            self.runner.start("projekt", {"beschreibung": "x"})

    def test_freigabe_hinweis(self):
        from jarvis.ai_models import ModelBlocked
        with self.real(), mock.patch.object(self.jarvis.llm, "build", side_effect=ModelBlocked("ist für die Aufgabe 'projekt' nicht freigegeben")):
            m = self.runner.start("projekt", {"beschreibung": "Bau mir ein Spiel"}, background=False)
        self.assertIn("werkstatt-an", m.steps[-1]["detail"])

    def test_html_herausloesen(self):
        self.assertEqual(extract_html("a <!DOCTYPE html><html></html> b"), "<!DOCTYPE html><html></html>\n")
        self.assertEqual(extract_html("kein html"), "")

    def test_router_build_kostenlimit(self):
        m = AnthropicModel("claude-sonnet-5-5")
        from jarvis.ai_models import Decision, ModelBlocked
        r = self.jarvis.llm
        with mock.patch.object(r, "_admit", return_value=(m, Decision(m.name, "extern", 0.05, "JARVIS_X"))), \
                mock.patch.object(r, "_guard") as g, mock.patch.object(m, "_send", side_effect=AssertionError("gesendet")):
            g.return_value.prepare.return_value = ("", [], "x")
            with self.assertRaises(ModelBlocked):
                r.build("x", cap_eur=0.05)                                 # Sonnet-Höchstkosten > 5 Cent


class Bilder(Base):
    def test_ohne_zugang_klare_anleitung(self):
        m = self.runner.start("bild", {"beschreibung": "Ein Löwe im Weltall"}, background=False)
        self.assertEqual(m.status, "gestoppt")
        self.assertIn("bilder-einrichten", " ".join(s["detail"] for s in m.steps))

    def test_bild_wird_gespeichert_und_gezeigt(self):
        self.jarvis.llm.policy._secrets.update({"JARVIS_CLOUDFLARE_ACCOUNT": "a" * 32, "JARVIS_CLOUDFLARE_TOKEN": "t" * 40})
        with mock.patch("jarvis.media.generate_image", return_value=PNG) as gen:
            m = self.runner.start("bild", {"beschreibung": "Ein Logo in Gold"}, background=False)
        self.assertEqual(m.status, "fertig", [s["text"] for s in m.steps])
        self.assertEqual(gen.call_args[0][1:], ("a" * 32, "t" * 40))
        self.assertEqual(self.runner.image_path(m.result["bild"]).read_bytes(), PNG)
        self.assertIsNone(self.runner.image_path("../../etc/passwd"))

    def test_tageslimit(self):
        self.jarvis.llm.policy._secrets.update({"JARVIS_CLOUDFLARE_ACCOUNT": "a" * 32, "JARVIS_CLOUDFLARE_TOKEN": "t" * 40})
        self.jarvis.cfg["werkstatt"]["max_bilder_pro_tag"] = 1
        with mock.patch("jarvis.media.generate_image", return_value=PNG):
            self.runner.start("bild", {"beschreibung": "Bild Nummer eins"}, background=False)
            m = self.runner.start("bild", {"beschreibung": "Bild Nummer zwei"}, background=False)
        self.assertEqual(m.status, "fehler")
        self.assertIn("Tageslimit", m.steps[-1]["text"])

    def test_cloudflare_anfrage(self):
        op = Opener({"success": True, "result": {"image": base64.b64encode(PNG).decode()}})
        self.assertEqual(generate_image("lion", "b" * 32, "tok", opener=op), PNG)
        req = op.reqs[0]
        self.assertTrue(req.full_url.startswith("https://api.cloudflare.com/client/v4/accounts/" + "b" * 32))
        self.assertEqual(req.get_header("Authorization"), "Bearer tok")
        with self.assertRaises(MediaError):
            generate_image("x", "../evil", "tok", opener=op)
        with self.assertRaises(MediaError):
            generate_image("x", "b" * 32, "tok", opener=Opener({"result": {"image": base64.b64encode(b"<html>").decode()}}))

    def test_einrichten_schreibt_env(self):
        from jarvis.__main__ import media_setup
        env = self.tmp / ".env"
        env.write_text("JARVIS_ANTHROPIC_KEY=abc\nJARVIS_CLOUDFLARE_TOKEN=alt\n")
        with mock.patch("builtins.print"):
            media_setup(env, ask=lambda _: "C" * 32, ask_secret=lambda _: "x" * 40)
        lines = env.read_text().splitlines()
        self.assertIn("JARVIS_ANTHROPIC_KEY=abc", lines)
        self.assertIn("JARVIS_CLOUDFLARE_ACCOUNT=" + "c" * 32, lines)
        self.assertEqual([l for l in lines if l.startswith("JARVIS_CLOUDFLARE_TOKEN")], ["JARVIS_CLOUDFLARE_TOKEN=" + "x" * 40])
        self.assertEqual(env.stat().st_mode & 0o077, 0)
        with self.assertRaises(ValueError), mock.patch("builtins.print"):
            media_setup(env, ask=lambda _: "keine-id", ask_secret=lambda _: "x" * 40)


class ChatImGespraech(Base):
    def setUp(self):
        super().setUp()
        self.svc = ChatService(self.jarvis, ChatStore(self.tmp / "d" / "chat.db"))
        self.conv = self.svc.store.new_conversation()

    def test_bau_auftrag_aus_dem_chat(self):
        r = self.svc.send(self.conv, "Jarvis, bau mir eine Landingpage für mein Kosmetikstudio", "nj")
        self.assertEqual(r["mode"], "auftrag")
        self.assertIn("/auftraege?id=", r["text"])
        self.assertIn('href="/auftraege?id=', render(r["text"]))
        for _ in range(100):
            if not get_runner(self.jarvis).running():
                break
            time.sleep(0.02)

    def test_normale_frage_mit_websuche(self):
        seen = {}

        def fake(system, history, text, **kw):
            seen.update(kw, system=system)
            return "Antwort"
        with mock.patch.object(self.jarvis.llm, "chat", side_effect=fake):
            self.svc.send(self.conv, "Was gibt es Neues bei Tesla?", "nj")
        self.assertEqual(seen["search"], 0)                               # Testmodell: keine Websuche
        self.assertIn("KEINE Websuche", seen["system"])
        self.assertIn("werkstatt-an", seen["system"])


class Quellen(JarvisBase):
    def test_zitate_werden_zu_quellen(self):
        m = AnthropicModel("claude-haiku-5-5")
        msg = {"stop_reason": "end_turn", "usage": {"input_tokens": 10, "output_tokens": 5, "server_tool_use": {"web_search_requests": 1}},
               "content": [{"type": "server_tool_use", "id": "x"}, {"type": "text", "text": "Laut Bericht "},
                           {"type": "text", "text": "stieg der Preis.", "citations": [{"url": "https://news.de/a", "title": "News [1]"},
                                                                                     {"url": "javascript:alert(1)", "title": "x"}]}]}
        text, cost = m._parse(msg)
        self.assertTrue(text.startswith("Laut Bericht stieg der Preis."))
        self.assertIn("[News  1 ](https://news.de/a)", text)
        self.assertNotIn("javascript", text)
        self.assertGreater(cost, 0.01)

    def test_chat_anfrage_mit_suchwerkzeug(self):
        m = AnthropicModel("claude-haiku-5-5")
        with mock.patch.object(m, "_send", return_value=("ok", 0.0)) as send:
            m.chat_billed("s", [], "Frage", "k", search=2)
        self.assertEqual(send.call_args[0][0]["tools"][0]["max_uses"], 2)
        with mock.patch.object(m, "_send", return_value=("ok", 0.0)) as send:
            m.chat_billed("s", [], "Frage", "k")
        self.assertNotIn("tools", send.call_args[0][0])
