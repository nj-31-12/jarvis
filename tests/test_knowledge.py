"""Tests Phase 2, Schritt 4: Business-Gedächtnis – python3 -m unittest -v"""
import os
import re
import shutil
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import urlencode

from jarvis import web_auth as wa
from jarvis.__main__ import data_fingerprint
from jarvis.chat import ChatService, ChatStore
from jarvis.config import DEFAULTS
from jarvis.core import Jarvis
from jarvis.knowledge import KnowledgeBase
from jarvis.profiles import PROJECTS, create_missing_drafts, profile_status
from jarvis.web import WebApp, redirect

HOST = "127.0.0.1:8765"
PW = "Kaffee-Hantel-Duft-Motor-42"


def write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


class Clock:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t


class CapturingModel:
    name = "erfassend"
    is_test_mode = False
    cost_per_call_eur = 0.0

    def __init__(self):
        self.prompts = []

    def chat(self, system_prompt, history, text):
        self.prompts.append(system_prompt)
        return "ok"

    def complete(self, task, text):
        return "x"


class KBBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = self.tmp / "vault"
        self.vault.mkdir()
        write(self.vault, "02_Projekte/Scent Edit.md", "# Scent Edit Strategie\nPinterest-Pins für Duftnoten testen. Instagram Reels.")
        write(self.vault, "02_Projekte/Coaching.md", "# NJ Coaching\nYou vs. You Programm mit der Community. Muskelaufbau.")
        write(self.vault, "05_Lernen/Ernährung.md", "# Ernährung\nProtein und Kalorien für Muskelaufbau.")
        write(self.vault, "90_Privat/Tagebuch.md", "# Privat\nScent Edit Gedanken, ganz privat.")
        write(self.vault, "04_Entscheidungen/Geheim.md", "---\nvertraulich: ja\n---\n# Entscheidung\nScent Edit Budget geheim.")
        write(self.vault, "07_Recherchen/Zugang.md", "# Shop Zugang\nShopify Login: noah@example.com\nPasswort: Geheim123!")
        write(self.vault, "07_Recherchen/Bank.md", "# Konto\nScent Edit Auszahlung an DE89 3704 0044 0532 0130 00")
        write(self.vault, ".obsidian/workspace.md", "# intern Scent Edit")
        write(self.vault, "02_Projekte/bild.png", "keine Notiz")
        self.kb = KnowledgeBase(self.vault, min_interval=0)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def titles(self, items):
        return sorted(n.title for n in items)


# ------------------------------------------------------------------ Index und Pfade
class IndexTests(KBBase):
    def test_only_markdown_no_hidden_folders(self):
        rels = [n.relpath for n in self.kb.notes(include_confidential=True)]
        self.assertFalse(any(r.startswith(".obsidian") for r in rels))
        self.assertFalse(any(r.endswith(".png") for r in rels))
        self.assertEqual(len(rels), 7)

    def test_symlinks_outside_are_ignored(self):
        outside = self.tmp / "aussen"
        outside.mkdir()
        write(outside, "geheim.md", "# Außerhalb\nScent Edit Fremddaten")
        os.symlink(str(outside / "geheim.md"), str(self.vault / "02_Projekte" / "link.md"))
        os.symlink(str(outside), str(self.vault / "Linkordner"))
        self.kb.refresh(force=True)
        rels = [n.relpath for n in self.kb.notes(include_confidential=True)]
        self.assertFalse(any("link" in r.lower() for r in rels))
        self.assertNotIn("Außerhalb", [n.title for n in self.kb.notes(include_confidential=True)])
        self.assertGreaterEqual(self.kb.stats()["skipped"]["verknuepfung"], 1)

    def test_size_and_count_limits(self):
        write(self.vault, "06_Content/riesig.md", "# Riesig\n" + "x" * 2_000_000)
        kb = KnowledgeBase(self.vault, min_interval=0, max_notes=3)
        self.assertLessEqual(len(kb.notes(include_confidential=True)), 3)
        self.assertGreaterEqual(kb.stats()["skipped"]["zu_viele"], 1)
        kb2 = KnowledgeBase(self.vault, min_interval=0)
        self.assertNotIn("Riesig", [n.title for n in kb2.notes(include_confidential=True)])
        self.assertEqual(kb2.stats()["skipped"]["zu_gross"], 1)

    def test_get_only_by_valid_id(self):
        for bad in ("../02_Projekte/Coaching.md", "02_Projekte/Coaching.md", "ABCDEF0123456789", "", None,
                    "0" * 15, "0" * 17, "%2e%2e%2f"):
            self.assertIsNone(self.kb.get(bad), bad)
        some = self.kb.notes()[0]
        self.assertEqual(self.kb.get(some.id).id, some.id)

    def test_index_never_writes(self):
        before = data_fingerprint(self.vault)[1]
        self.kb.refresh(force=True)
        self.kb.search("Scent Edit", include_confidential=True)
        self.kb.context_for("Scent Edit")
        self.kb.stats()
        self.assertEqual(before, data_fingerprint(self.vault)[1])

    def test_performance_2000_notes(self):
        big = self.tmp / "gross"
        for i in range(2000):
            write(big, f"{i % 10:02d}_Ordner/Notiz {i}.md", f"# Notiz {i}\nInhalt über Fitness, Shopify und Thema {i}.\n" * 5)
        kb = KnowledgeBase(big, min_interval=0)
        t = time.time()
        self.assertEqual(kb.stats()["visible"], 2000)
        t_index = time.time() - t
        t = time.time()
        kb.search("Shopify Thema 1999")
        t_search = time.time() - t
        self.assertLess(t_index, 15, "Index zu langsam")
        self.assertLess(t_search, 3, "Suche zu langsam")


# ------------------------------------------------------------------ Vertraulichkeit
class ConfidentialTests(KBBase):
    def test_classification_reasons(self):
        conf = {n.relpath: n.reasons for n in self.kb.notes(include_confidential=True) if n.confidential}
        self.assertIn("privater Ordner", conf["90_Privat/Tagebuch.md"])
        self.assertIn("als vertraulich markiert", conf["04_Entscheidungen/Geheim.md"])
        self.assertTrue(any("Zugangsdaten" in r for r in conf["07_Recherchen/Zugang.md"]))
        self.assertTrue(any("IBAN" in r for r in conf["07_Recherchen/Bank.md"]))
        self.assertEqual(len(conf), 4)

    def test_frontmatter_variants(self):
        for i, value in enumerate(("true", "Yes", "JA", "privat")):
            write(self.vault, f"08_Tagebuch/v{i}.md", f"---\nvertraulich: {value}\n---\n# V{i}\nText")
        write(self.vault, "08_Tagebuch/offen.md", "---\nvertraulich: nein\n---\n# Offen\nText")
        self.kb.refresh(force=True)
        conf = {n.title for n in self.kb.notes(include_confidential=True) if n.confidential}
        self.assertTrue({"V0", "V1", "V2", "V3"} <= conf)
        self.assertNotIn("Offen", conf)

    def test_harmless_mentions_are_not_flagged(self):
        write(self.vault, "05_Lernen/Sicherheit.md", "# Sicherheit\nIch sollte mein Passwort regelmäßig ändern. Login über 2FA.")
        self.kb.refresh(force=True)
        note = [n for n in self.kb.notes(include_confidential=True) if n.title == "Sicherheit"][0]
        self.assertFalse(note.confidential, note.reasons)

    def test_private_folder_case_insensitive_and_nested(self):
        write(self.vault, "90_privat/Unterordner/tief.md", "# Tief\nScent Edit")
        self.kb.refresh(force=True)
        self.assertTrue([n for n in self.kb.notes(include_confidential=True) if n.title == "Tief"][0].confidential)

    def test_confidential_terms_and_placeholder(self):
        write(self.vault, "07_Recherchen/Betrieb.md", "# Betrieb\nAutohaus Mustermann Umsatzzahlen")
        kb = KnowledgeBase(self.vault, min_interval=0, confidential_terms=["Autohaus Mustermann", "NAME_DEINES_AUSBILDUNGSBETRIEBS"])
        self.assertTrue([n for n in kb.notes(include_confidential=True) if n.title == "Betrieb"][0].confidential)
        kb2 = KnowledgeBase(self.vault, min_interval=0, confidential_terms=["NAME_DEINES_AUSBILDUNGSBETRIEBS"])
        self.assertEqual(kb2.terms, [])

    def test_search_hides_confidential_by_default(self):
        default = self.titles(h["note"] for h in self.kb.search("Scent Edit"))
        self.assertEqual(default, ["Scent Edit Strategie"])
        allowed = self.titles(h["note"] for h in self.kb.search("Scent Edit", include_confidential=True))
        self.assertIn("Privat", allowed)
        self.assertIn("Entscheidung", allowed)

    def test_context_never_contains_confidential(self):
        ctx = self.kb.context_for("Scent Edit Budget geheim privat Auszahlung", k=10)
        joined = " ".join(c["excerpt"] + c["title"] for c in ctx)
        for secret in ("geheim", "ganz privat", "DE89", "Geheim123"):
            self.assertNotIn(secret, joined)

    def test_get_confidential_requires_flag(self):
        note = [n for n in self.kb.notes(include_confidential=True) if n.confidential][0]
        self.assertIsNone(self.kb.get(note.id))
        self.assertIsNotNone(self.kb.get(note.id, include_confidential=True))
        self.assertFalse(self.kb.is_shareable(note.id))

    def test_becoming_confidential_revokes_sharing(self):
        note = [n for n in self.kb.notes() if n.title == "NJ Coaching"][0]
        self.assertTrue(self.kb.is_shareable(note.id))
        write(self.vault, note.relpath, "---\nvertraulich: ja\n---\n# NJ Coaching\nJetzt privat.")
        self.kb.refresh(force=True)
        self.assertFalse(self.kb.is_shareable(note.id))

    def test_open_goals_skip_confidential(self):
        write(self.vault, "01_Ziele/Ziele.md", "# Ziele\n- [ ] 100 € Umsatz")
        write(self.vault, "01_Ziele/Privat.md", "---\nvertraulich: ja\n---\n# P\n- [ ] Geheimes Ziel")
        self.kb.refresh(force=True)
        self.assertEqual(self.kb.open_goals(), ["100 € Umsatz"])


# ------------------------------------------------------------------ Suche
class SearchTests(KBBase):
    def test_all_terms_required_and_title_boost(self):
        hits = self.kb.search("Muskelaufbau")
        self.assertEqual(len(hits), 2)
        self.assertEqual(self.kb.search("Muskelaufbau Protein")[0]["note"].title, "Ernährung")
        self.assertEqual(self.kb.search("Muskelaufbau Pinterest"), [])

    def test_umlauts_and_case(self):
        self.assertEqual(self.kb.search("ERNÄHRUNG")[0]["note"].title, "Ernährung")

    def test_odd_queries_do_not_crash(self):
        for q in ("", "   ", "a", ".*[(", "\\", "<script>", "ü" * 5000, "\x00\x01"):
            self.assertIsInstance(self.kb.search(q), list)

    def test_snippets_are_plain_text(self):
        write(self.vault, "06_Content/Tabelle.md", "# Tabelle\n## Zahlen\n| Kanal | Wert |\n|---|---|\n| Pinterest | 300 |")
        self.kb.refresh(force=True)
        snip = self.kb.search("Tabelle")[0]["snippet"]
        self.assertNotIn("##", snip)
        self.assertNotIn("|---", snip)
        self.assertIn("Pinterest", snip)
        from jarvis.knowledge import plain_text
        self.assertEqual(plain_text("**fett** _kursiv_ nach `02_Projekte` verschieben"),
                         "fett kursiv nach 02_Projekte verschieben")

    def test_own_notes_rank_above_inbox_drafts_at_equal_relevance(self):
        # gleiche Relevanz (ein Treffer im Text, keiner im Titel): deine eigene Notiz steht vorn
        write(self.vault, "00_Inbox/JARVIS/Entwurf.md", "# Entwurf von JARVIS\nIdeen zu Pinterest-Pins.")
        self.kb.refresh(force=True)
        self.assertEqual(self.kb.search("Pinterest")[0]["note"].title, "Scent Edit Strategie")

    def test_snippet_contains_term(self):
        self.assertIn("Pinterest", self.kb.search("Pinterest")[0]["snippet"])


# ------------------------------------------------------------------ Profile
class ProfileTests(KBBase):
    def setUp(self):
        super().setUp()
        from jarvis.obsidian import Vault
        self.v = Vault(self.vault, ["00_Inbox/JARVIS"])
        self.v.init()
        self.v.on_write = self.kb.invalidate

    def test_projects_match_profile(self):
        names = [p["name"] for p in PROJECTS]
        self.assertIn("NJ Coaching / NYoung.Coaching", names)
        self.assertIn("Scent Edit / WYLD NOTES", names)
        status = {p["slug"]: p["status"] for p in PROJECTS}
        self.assertEqual(status["nj-coaching"], "aktiv")
        self.assertEqual(status["automobil"], "Ausbildung")
        self.assertEqual(status["ideen"], "Idee")
        # Schritt 4.1: Noah hat bestätigt, dass Young Living aktiv ist (vorher: Status ungeklärt → kein Profil)
        self.assertEqual(status["young-living"], "aktiv")
        yl = [p for p in PROJECTS if p["slug"] == "young-living"][0]
        self.assertTrue(any("Heil" in h for h in yl["hinweise"]))
        self.assertTrue(any("NACH Kosten" in h for h in yl["hinweise"]))
        self.assertTrue(all("(Idee)" in a for a in [p for p in PROJECTS if p["slug"] == "ideen"][0]["angaben"]))

    def test_creates_only_new_drafts_once(self):
        before = data_fingerprint(self.vault)[0]
        created = create_missing_drafts(self.v, self.kb)
        self.assertEqual(len(created), len(PROJECTS))
        self.assertEqual(create_missing_drafts(self.v, self.kb), [])
        after = {r: d for r, _, d in data_fingerprint(self.vault)[0]}
        for rel, _, digest in before:                    # keine bestehende Datei verändert
            self.assertEqual(after[rel], digest, rel)
        new = [r for r in after if r not in {b[0] for b in before}]
        self.assertTrue(all(r.startswith("00_Inbox/JARVIS/") for r in new), new)

    def test_adopted_profile_is_recognized(self):
        write(self.vault, "02_Projekte/Mein Coaching.md",
              "---\ntyp: bereichsprofil\nbereich: nj-coaching\n---\n# NJ Coaching Profil\nText")
        self.kb.refresh(force=True)
        state = {e["project"]["slug"]: e["state"] for e in profile_status(self.kb)}
        self.assertEqual(state["nj-coaching"], "übernommen")
        created = create_missing_drafts(self.v, self.kb)
        self.assertEqual(len(created), len(PROJECTS) - 1)
        state = {e["project"]["slug"]: e["state"] for e in profile_status(self.kb)}
        self.assertEqual(state["scent-edit"], "Entwurf")

    def test_draft_content(self):
        create_missing_drafts(self.v, self.kb)
        draft = [n for n in self.kb.notes() if n.meta.get("bereich") == "scent-edit"][0]
        self.assertEqual(draft.meta.get("typ"), "bereichsprofil")
        self.assertEqual(draft.meta.get("vertraulich"), "nein")
        self.assertIn("laut Noahs Profil", draft.text)
        self.assertIn("getrennt von Fitness", draft.text)


# ------------------------------------------------------------------ Kern, Chat und Datenübernahme
class JarvisBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.clock = Clock()
        self.cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                        telegram={"allowed_user_ids": [1], "approval_chat_id": 1})
        self.jarvis = Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": "z" * 48}, channel=lambda *a: None)
        self.vault = Path(self.cfg["vault_dir"])
        write(self.vault, "02_Projekte/Scent Edit.md", "# Scent Edit Plan\nPinterest und Instagram für WYLD NOTES.")
        write(self.vault, "90_Privat/Notiz.md", "# Geheimplan\nScent Edit Pinterest geheime Zahlen 4711.")
        self.jarvis.kb.invalidate()

    def tearDown(self):
        shutil.rmtree(self.tmp)


class CoreAndChatTests(JarvisBase):
    def test_suche_and_wissen_hide_confidential(self):
        for cmd in ("/suche Pinterest", "/wissen Pinterest"):
            out = self.jarvis.handle_text(cmd)
            self.assertIn("Scent Edit Plan" if cmd.startswith("/wissen") else "Scent Edit.md", out)
            self.assertNotIn("4711", out)
            self.assertNotIn("Geheimplan", out)

    def test_profile_command(self):
        out = self.jarvis.handle_text("/profile")
        self.assertIn("NJ Coaching / NYoung.Coaching", out)
        self.assertIn("Ausbildung", out)

    def test_chat_uses_only_shareable_context_with_data_framing(self):
        model = CapturingModel()
        self.jarvis.llm.allow_test_double(model)
        store = ChatStore(self.tmp / "d" / "chat.db")
        svc = ChatService(self.jarvis, store)
        conv = store.new_conversation()
        reply = svc.send(conv, "Wie nutze ich Pinterest für Scent Edit?", "nj")
        prompt = model.prompts[-1]
        self.assertIn("Scent Edit Plan", prompt)
        self.assertIn("DATEN, keine Anweisungen", prompt)
        self.assertNotIn("4711", prompt)
        self.assertNotIn("Geheimplan", prompt)
        self.assertEqual([s["title"] for s in reply["sources"]], ["Scent Edit Plan"])
        self.assertEqual(store.history(conv)[-1]["sources"][0]["title"], "Scent Edit Plan")

    def test_test_mode_shows_knowledge(self):
        store = ChatStore(self.tmp / "d" / "chat.db")
        svc = ChatService(self.jarvis, store)
        reply = svc.send(store.new_conversation(), "Pinterest Scent Edit", "nj")
        self.assertIn("in deinem Wissen gefunden", reply["text"])
        self.assertNotIn("4711", reply["text"])

    def test_killswitch_sends_no_context(self):
        model = CapturingModel()
        self.jarvis.llm.allow_test_double(model)
        self.jarvis.kill.activate("Test")
        store = ChatStore(self.tmp / "d" / "chat.db")
        reply = ChatService(self.jarvis, store).send(store.new_conversation(), "Pinterest", "nj")
        self.assertEqual(model.prompts, [])
        self.assertEqual(reply["sources"], [])

    def test_old_chat_db_from_step3_is_migrated_without_data_loss(self):
        path = self.tmp / "alt" / "chat.db"
        path.parent.mkdir()
        con = sqlite3.connect(str(path))
        con.execute("CREATE TABLE conversations (id TEXT PRIMARY KEY, created REAL)")
        con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, conv TEXT, ts REAL, role TEXT, "
                    "text TEXT, mode TEXT, cost_eur REAL)")
        con.execute("INSERT INTO conversations VALUES ('aaaaaaaaaaaa', 1)")
        con.execute("INSERT INTO messages (conv, ts, role, text, mode, cost_eur) VALUES ('aaaaaaaaaaaa', 1, 'du', 'Alte Nachricht', '', 0)")
        con.commit()
        con.close()
        store = ChatStore(path)
        h = store.history("aaaaaaaaaaaa")
        self.assertEqual(h[0]["text"], "Alte Nachricht")
        self.assertEqual(h[0]["sources"], [])
        store.add("aaaaaaaaaaaa", "jarvis", "Neu", sources=[{"id": "0" * 16, "title": "T"}])
        self.assertEqual(store.history("aaaaaaaaaaaa")[-1]["sources"][0]["title"], "T")

    def test_fingerprint_detects_changes(self):
        d = self.tmp / "fp"
        write(d, "a.txt", "eins")
        first = data_fingerprint(d)[1]
        self.assertEqual(first, data_fingerprint(d)[1])
        write(d, "a.txt", "zwei")
        self.assertNotEqual(first, data_fingerprint(d)[1])


# ------------------------------------------------------------------ Browser
class WebKnowledgeTests(JarvisBase):
    def setUp(self):
        super().setUp()
        write(self.vault, "06_Content/xss.md", '# <img src=x onerror=alert(1)>Titel\n<script>alert(1)</script> Pinterest [x](javascript:alert(1))')
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

    def get(self, path):
        return self.req("GET", path, cookie=self.sid)

    def csrf(self):
        return re.search(r'name="csrf" value="([^"]+)"', self.get("/wissen").body.decode()).group(1)

    def secret_id(self):
        return [n for n in self.jarvis.kb.notes(include_confidential=True) if n.confidential][0].id

    def test_requires_login(self):
        for p in ("/wissen", "/wissen/notiz?id=" + "0" * 16, "/wissen?q=Scent"):
            self.assertEqual(self.req("GET", p).header("Location"), "/login", p)
        self.assertEqual(self.req("POST", "/wissen/profile", {}).header("Location"), "/login")

    def test_overview_and_search_hide_confidential(self):
        body = self.get("/wissen?q=Pinterest").body.decode()
        self.assertIn("Scent Edit Plan", body)
        self.assertNotIn("Geheimplan", body)
        self.assertIn("vertrauliche Notiz(en) ausgeblendet", body)

    def test_confidential_note_needs_password_and_expires(self):
        sid_url = "/wissen/notiz?id=" + self.secret_id()
        self.assertEqual(self.get(sid_url).status, 403)
        self.assertNotIn("4711", self.get(sid_url).body.decode())
        csrf = self.csrf()
        self.req("POST", "/wissen/entsperren", {"csrf": csrf, "password": "falsch-falsch-falsch", "weiter": sid_url}, cookie=self.sid)
        self.assertEqual(self.get(sid_url).status, 403)
        r = self.req("POST", "/wissen/entsperren", {"csrf": csrf, "password": PW, "weiter": sid_url}, cookie=self.sid)
        self.assertEqual(r.header("Location"), sid_url)
        page = self.get(sid_url)
        self.assertEqual(page.status, 200)
        self.assertIn("4711", page.body.decode())
        self.assertIn("Vertraulich:", page.body.decode())
        self.clock.t += 11 * 60
        self.app.sessions.get(self.sid)        # Sitzung bleibt aktiv (Leerlauf < 30 Min.)
        self.assertEqual(self.get(sid_url).status, 403)

    def test_unlock_needs_csrf_and_can_be_relocked(self):
        sid_url = "/wissen/notiz?id=" + self.secret_id()
        self.assertEqual(self.req("POST", "/wissen/entsperren", {"csrf": "x", "password": PW}, cookie=self.sid).status, 403)
        csrf = self.csrf()
        self.req("POST", "/wissen/entsperren", {"csrf": csrf, "password": PW}, cookie=self.sid)
        self.assertEqual(self.get(sid_url).status, 200)
        self.req("POST", "/wissen/sperren", {"csrf": csrf}, cookie=self.sid)
        self.assertEqual(self.get(sid_url).status, 403)

    def test_wrong_unlock_passwords_count_towards_lockout(self):
        csrf = self.csrf()
        for _ in range(wa.MAX_FAILED_ATTEMPTS):
            self.req("POST", "/wissen/entsperren", {"csrf": csrf, "password": "falsch-falsch-x"}, cookie=self.sid)
        self.assertGreater(self.auth.locked_seconds("nj"), 0)

    def test_redirect_targets_are_safe(self):
        csrf = self.csrf()
        for weiter in ("https://evil.example", "//evil.example", "/wissen\r\nSet-Cookie: x=1",
                       "/wissen/notiz?id=../../x", "/chat", "/wissen/notiz?id=" + "0" * 16 + "&x=1"):
            r = self.req("POST", "/wissen/entsperren", {"csrf": csrf, "password": PW, "weiter": weiter}, cookie=self.sid)
            self.assertEqual(r.header("Location"), "/wissen", weiter)
        for loc in ("https://evil.example", "//evil", "/a\r\nX: y", "/a\\b"):
            self.assertEqual(redirect(loc).header("Location"), "/")

    def test_note_ids_cannot_traverse(self):
        for bad in ("../../etc/passwd", "%2e%2e%2f%2e%2e%2f", "02_Projekte/Scent%20Edit.md", "ZZZZZZZZZZZZZZZZ", ""):
            self.assertEqual(self.get("/wissen/notiz?id=" + bad).status, 404, bad)

    def test_xss_in_notes_and_queries(self):
        xss = [n for n in self.jarvis.kb.notes() if "Titel" in n.title][0]
        pages = [self.get("/wissen").body.decode(), self.get("/wissen?q=Pinterest").body.decode(),
                 self.get("/wissen/notiz?id=" + xss.id).body.decode(),
                 self.get("/wissen?q=%3Cscript%3Ealert(1)%3C%2Fscript%3E").body.decode()]
        for body in pages:
            self.assertNotIn("<script>alert", body)
            self.assertNotRegex(body, r"<img[^>]*onerror")
            self.assertNotIn('href="javascript:', body)

    def test_profile_button(self):
        self.assertEqual(self.req("POST", "/wissen/profile", {"csrf": "x"}, cookie=self.sid).status, 403)
        r = self.req("POST", "/wissen/profile", {"csrf": self.csrf()}, cookie=self.sid)
        self.assertEqual(r.status, 303)
        body = self.get("/wissen").body.decode()
        self.assertIn("Profil-Entwürfe in 00_Inbox/JARVIS angelegt", body)
        self.assertIn("◐ Entwurf", body)

    def test_chat_sources_link_and_revocation(self):
        page = self.get("/chat").body.decode()
        csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
        conv = re.search(r'name="g" value="([0-9a-f]{12})"', page).group(1)
        self.req("POST", "/chat", {"csrf": csrf, "g": conv, "text": "Pinterest WYLD NOTES"}, cookie=self.sid)
        body = self.get(f"/chat?g={conv}").body.decode()
        self.assertIn("/wissen/notiz?id=", body)
        self.assertIn("Scent Edit Plan", body)
        write(self.vault, "02_Projekte/Scent Edit.md", "---\nvertraulich: ja\n---\n# Scent Edit Plan\nJetzt privat.")
        self.jarvis.kb.invalidate()
        body = self.get(f"/chat?g={conv}").body.decode()
        self.assertIn("Quelle nicht mehr verfügbar", body)
        self.assertNotIn("/wissen/notiz?id=", body)


if __name__ == "__main__":
    unittest.main()
