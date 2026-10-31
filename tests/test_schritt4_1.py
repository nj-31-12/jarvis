"""Regressionstests Schritt 4.1 (Hinweise aus der Prüfung durch ChatGPT) – python3 -m unittest -v

1. Keine Lücke während der Index-Verzögerung: frisch vertrauliche Notizen nie als KI-Kontext/Quelle/Treffer
2. Gespeicherte Antworten mit nachträglich vertraulichen Quellen: zurückhalten, nie an die KI, nichts automatisch löschen;
   endgültiges Schwärzen nur nach Passwort + Häkchen
3. SQLite-Verbindungen werden sicher geschlossen (keine ResourceWarnings)
"""
import contextlib
import gc
import io
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
import warnings
from pathlib import Path
from urllib.parse import urlencode

from jarvis import web_auth as wa
from jarvis.chat import ChatService, ChatStore
from jarvis.config import DEFAULTS
from jarvis.core import Jarvis
from jarvis.db import LockedDB
from jarvis.knowledge import KnowledgeBase
from jarvis.web import SAFE_RETURN, WebApp

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
        self.prompts, self.histories = [], []

    def chat(self, system_prompt, history, text):
        self.prompts.append(system_prompt)
        self.histories.append(history)
        return "Antwort ohne Inhalt"

    def complete(self, task, text):
        return "x"


# ------------------------------------------------------------------ 1. Index-Verzögerung
class IndexDelayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault = self.tmp / "vault"
        self.note = write(self.vault, "02_Projekte/Plan.md", "# Scent Plan\nPinterest Strategie öffentlich.")
        write(self.vault, "01_Ziele/Ziele.md", "# Ziele\n- [ ] Pinterest Ziel")
        # sehr lange Verzögerung: der Index würde Änderungen 60 s lang NICHT bemerken
        self.kb = KnowledgeBase(self.vault, min_interval=60)
        self.kb.refresh(force=True)
        self.note_id = self.kb.search("Pinterest Strategie")[0]["note"].id

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def make_confidential(self):
        write(self.vault, "02_Projekte/Plan.md", "---\nvertraulich: ja\n---\n# Scent Plan\nPinterest GEHEIM 4711.")

    def assert_nothing_leaks(self):
        ctx = self.kb.context_for("Pinterest Strategie Plan", k=5)
        self.assertNotIn("GEHEIM", " ".join(c["excerpt"] for c in ctx))
        self.assertNotIn(self.note_id, [c["id"] for c in ctx])
        self.assertNotIn(self.note_id, [h["note"].id for h in self.kb.search("Pinterest")])
        self.assertIsNone(self.kb.get(self.note_id))
        self.assertFalse(self.kb.is_shareable(self.note_id))

    def test_newly_marked_confidential_is_excluded_immediately(self):
        self.make_confidential()                      # KEIN invalidate(): simuliert Änderung in Obsidian
        self.assert_nothing_leaks()

    def test_newly_added_secret_pattern_is_excluded_immediately(self):
        write(self.vault, "02_Projekte/Plan.md", "# Scent Plan\nPinterest Strategie\nPasswort: GEHEIM-Shop-123")
        self.assert_nothing_leaks()

    def test_moved_into_private_folder_is_excluded_immediately(self):
        target = self.vault / "90_Privat"
        target.mkdir()
        os.rename(str(self.note), str(target / "Plan.md"))
        ctx = self.kb.context_for("Pinterest Strategie", k=5)
        self.assertNotIn(self.note_id, [c["id"] for c in ctx])
        self.assertNotIn("Strategie", " ".join(c["excerpt"] for c in ctx))
        self.assertFalse(self.kb.is_shareable(self.note_id))

    def test_replaced_by_symlink_is_excluded(self):
        outside = write(self.tmp, "aussen.md", "# Fremd\nPinterest Strategie fremd")
        os.remove(str(self.note))
        os.symlink(str(outside), str(self.note))
        ctx = self.kb.context_for("Pinterest Strategie", k=5)
        self.assertNotIn(self.note_id, [c["id"] for c in ctx])
        self.assertNotIn("fremd", " ".join(c["excerpt"] for c in ctx))

    def test_snippets_and_excerpts_use_current_content(self):
        write(self.vault, "02_Projekte/Plan.md", "# Scent Plan\nPinterest Strategie NEU überarbeitet.")
        self.assertIn("NEU", self.kb.search("Pinterest Strategie")[0]["snippet"])
        self.assertIn("NEU", self.kb.context_for("Pinterest Strategie")[0]["excerpt"])

    def test_goals_respect_fresh_state(self):
        self.assertEqual(self.kb.open_goals(), ["Pinterest Ziel"])
        write(self.vault, "01_Ziele/Ziele.md", "---\nvertraulich: ja\n---\n# Ziele\n- [ ] Pinterest Ziel")
        self.assertEqual(self.kb.open_goals(), [])

    def test_chat_never_receives_freshly_confidential_text(self):
        cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.vault),
                   telegram={"allowed_user_ids": [1], "approval_chat_id": 1})
        j = Jarvis(cfg, {"JARVIS_APPROVAL_SECRET": "z" * 48}, channel=lambda *a: None)
        j.kb.min_interval = 60
        j.kb.refresh(force=True)
        model = CapturingModel()
        j.llm.allow_test_double(model)
        store = ChatStore(self.tmp / "d" / "chat.db")
        self.make_confidential()
        reply = ChatService(j, store).send(store.new_conversation(), "Wie läuft die Pinterest Strategie?", "nj")
        self.assertNotIn("GEHEIM", model.prompts[-1])
        self.assertEqual(reply["sources"], [])
        store.close()
        j.close()


# ------------------------------------------------------------------ 2. Gespeicherte Antworten
class StoredAnswerBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.clock = Clock()
        self.cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                        telegram={"allowed_user_ids": [1], "approval_chat_id": 1})
        self.jarvis = Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": "z" * 48}, channel=lambda *a: None)
        self.vault = Path(self.cfg["vault_dir"])
        self.note = write(self.vault, "02_Projekte/Plan.md", "# Scent Plan\nPinterest Umsatzziel 4711 Euro.")
        self.jarvis.kb.invalidate()
        self.store = ChatStore(self.tmp / "d" / "chat.db", clock=self.clock)
        self.svc = ChatService(self.jarvis, self.store, clock=self.clock)
        self.conv = self.store.new_conversation()
        # Testmodus-Antwort enthält einen Auszug der Notiz und speichert sie als Quelle
        self.reply = self.svc.send(self.conv, "Pinterest Umsatzziel?", "nj")
        self.assertIn("4711", self.reply["text"])
        self.assertEqual(len(self.reply["sources"]), 1)

    def tearDown(self):
        self.store.close()
        self.jarvis.close()
        shutil.rmtree(self.tmp)

    def make_confidential(self):
        write(self.vault, "02_Projekte/Plan.md", "---\nvertraulich: ja\n---\n# Scent Plan\nPinterest Umsatzziel 4711 Euro.")
        self.jarvis.kb.invalidate()

    def stored_text(self, msg_id):
        con = sqlite3.connect(str(self.tmp / "d" / "chat.db"))
        try:
            return con.execute("SELECT text FROM messages WHERE id=?", (msg_id,)).fetchone()[0]
        finally:
            con.close()


class StoredAnswerTests(StoredAnswerBase):
    def test_not_withheld_while_sources_are_shareable(self):
        self.assertIsNone(self.svc.withheld_reason(self.store.get_message(self.reply["id"])))
        self.assertEqual(self.svc.affected_messages(), [])

    def test_withheld_after_source_becomes_confidential_but_not_deleted(self):
        before = self.stored_text(self.reply["id"])
        self.make_confidential()
        msg = self.store.get_message(self.reply["id"])
        self.assertIn("vertraulich", self.svc.withheld_reason(msg))
        self.assertEqual([m["id"] for m in self.svc.affected_messages()], [self.reply["id"]])
        self.assertEqual(self.stored_text(self.reply["id"]), before)        # nichts gelöscht oder verändert

    def test_withheld_when_source_moved_or_deleted(self):
        (self.vault / "90_Privat").mkdir(exist_ok=True)
        os.rename(str(self.note), str(self.vault / "90_Privat" / "Plan.md"))
        self.jarvis.kb.invalidate()
        self.assertIn("nicht mehr auffindbar", self.svc.withheld_reason(self.store.get_message(self.reply["id"])))

    def test_withheld_answers_never_go_to_the_model(self):
        model = CapturingModel()
        self.jarvis.llm.allow_test_double(model)
        self.make_confidential()
        self.svc.send(self.conv, "Und weiter?", "nj")
        texts = " ".join(m["text"] for m in model.histories[-1])
        self.assertNotIn("4711", texts)
        self.assertIn("Pinterest Umsatzziel?", texts)       # deine eigene Frage bleibt im Verlauf

    def test_redact_replaces_text_and_titles_only_for_jarvis_answers(self):
        self.make_confidential()
        user_msg = self.store.history(self.conv)[0]
        self.assertFalse(self.store.redact(user_msg["id"], self.clock()))     # eigene Nachrichten nicht
        self.assertTrue(self.store.redact(self.reply["id"], self.clock()))
        msg = self.store.get_message(self.reply["id"])
        self.assertNotIn("4711", msg["text"])
        self.assertIn("geschwärzt", msg["text"])
        self.assertEqual([s["title"] for s in msg["sources"]], [""])
        self.assertIsNone(self.svc.withheld_reason(msg))                      # geschwärzt = nichts mehr zu verbergen
        self.assertFalse(self.store.redact(self.reply["id"], self.clock()))  # nicht doppelt

    def test_step4_database_is_migrated_without_loss(self):
        path = self.tmp / "alt4" / "chat.db"
        path.parent.mkdir()
        con = sqlite3.connect(str(path))
        con.execute("CREATE TABLE conversations (id TEXT PRIMARY KEY, created REAL)")
        con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, conv TEXT, ts REAL, role TEXT, "
                    "text TEXT, mode TEXT, cost_eur REAL, sources TEXT)")
        con.execute("INSERT INTO conversations VALUES ('bbbbbbbbbbbb', 1)")
        con.execute("INSERT INTO messages (conv, ts, role, text, mode, cost_eur, sources) VALUES "
                    "('bbbbbbbbbbbb', 1, 'jarvis', 'Alte Antwort', 'test', 0, '[{\"id\": \"0123456789abcdef\", \"title\": \"T\"}]')")
        con.commit()
        con.close()
        store = ChatStore(path)
        m = store.history("bbbbbbbbbbbb")[0]
        self.assertEqual(m["text"], "Alte Antwort")
        self.assertIsNone(m["redacted_at"])
        self.assertEqual(m["sources"][0]["title"], "T")
        store.close()

    def dump_chat_db(self):
        con = sqlite3.connect(str(self.tmp / "d" / "chat.db"))
        try:
            return list(con.iterdump())
        finally:
            con.close()

    def test_report_command_is_read_only(self):
        import jarvis.__main__ as main
        self.make_confidential()
        before = self.dump_chat_db()
        original = main.load_config
        main.load_config = lambda *a, **k: dict(self.cfg)
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                main.check_chat()
        finally:
            main.load_config = original
        self.assertIn("1 Antwort(en) zurückgehalten", out.getvalue())
        self.assertIn("nichts gelöscht", out.getvalue())
        self.assertEqual(before, self.dump_chat_db())          # Datenbankinhalt Zeile für Zeile identisch


class WebStoredAnswerTests(StoredAnswerBase):
    def setUp(self):
        super().setUp()
        self.auth = wa.AuthStore(self.tmp / "d", self.jarvis.audit, clock=self.clock, iterations=1000)
        self.auth.set_password("nj", PW)
        self.app = WebApp(self.cfg, self.auth, self.jarvis, clock=self.clock)
        self.app.chat.store.close()
        self.app.chat = ChatService(self.jarvis, self.store, clock=self.clock)   # dieselbe Datenbank wie oben
        page = self.req("GET", "/login").body.decode()
        nonce = re.search(r'name="nonce" value="([^"]+)"', page).group(1)
        r = self.req("POST", "/login", {"username": "nj", "password": PW, "nonce": nonce})
        self.sid = r.header("Set-Cookie").split(";")[0].split("=", 1)[1]

    def tearDown(self):
        self.auth.close()
        super().tearDown()

    def req(self, method, path, body=None, cookie=None):
        h = {"Host": HOST}
        if cookie:
            h["Cookie"] = f"jarvis_session={cookie}"
        return self.app.handle(method, path, h, urlencode(body).encode() if body is not None else b"")

    def page(self):
        return self.req("GET", f"/chat?g={self.conv}", cookie=self.sid).body.decode()

    def csrf(self):
        return re.search(r'name="csrf" value="([^"]+)"', self.page()).group(1)

    def unlock(self):
        self.req("POST", "/wissen/entsperren", {"csrf": self.csrf(), "password": PW}, cookie=self.sid)

    def redact(self, **extra):
        body = {"csrf": self.csrf(), "id": str(self.reply["id"]), "bestaetigt": "ja"}
        body.update(extra)
        return self.req("POST", "/chat/schwaerzen", body, cookie=self.sid)

    def test_withheld_answer_hidden_until_unlocked(self):
        self.assertIn("4711", self.page())
        self.make_confidential()
        body = self.page()
        self.assertNotIn("4711", body)
        self.assertIn("Antwort zurückgehalten", body)
        self.assertIn("Zurückgehaltene Chat-Antworten <b>1</b>", self.req("GET", "/", cookie=self.sid).body.decode())
        self.unlock()
        body = self.page()
        self.assertIn("4711", body)
        self.assertIn("Endgültig schwärzen", body)

    def test_redaction_requires_unlock_checkbox_and_csrf(self):
        self.make_confidential()
        self.redact()                                               # nicht entsperrt
        self.assertIn("4711", self.stored_text(self.reply["id"]))
        self.unlock()
        self.redact(bestaetigt="")                                  # Häkchen fehlt
        self.assertIn("4711", self.stored_text(self.reply["id"]))
        r = self.req("POST", "/chat/schwaerzen", {"csrf": "falsch", "id": str(self.reply["id"]), "bestaetigt": "ja"},
                     cookie=self.sid)
        self.assertEqual(r.status, 403)
        self.assertIn("4711", self.stored_text(self.reply["id"]))
        self.redact()
        self.assertNotIn("4711", self.stored_text(self.reply["id"]))
        self.assertIn("chat_redacted", self.jarvis.audit.path.read_text())

    def test_unaffected_answer_cannot_be_redacted(self):
        self.unlock()
        self.redact()
        self.assertIn("4711", self.stored_text(self.reply["id"]))

    def test_bad_ids_and_login(self):
        self.unlock()
        for bad in ("999999", "abc", "-1", "1 OR 1=1"):
            r = self.req("POST", "/chat/schwaerzen", {"csrf": self.csrf(), "id": bad, "bestaetigt": "ja"}, cookie=self.sid)
            self.assertEqual(r.status, 404, bad)
        self.assertEqual(self.req("POST", "/chat/schwaerzen", {"id": "1"}).header("Location"), "/login")

    def test_return_targets(self):
        self.assertTrue(SAFE_RETURN.fullmatch(f"/chat?g={self.conv}"))
        for bad in ("/chat?g=../x", "/chat?g=" + "a" * 13, "/chat", "https://evil/chat?g=" + self.conv):
            self.assertIsNone(SAFE_RETURN.fullmatch(bad), bad)


# ------------------------------------------------------------------ 3. Datenbankverbindungen
class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_close_is_explicit_idempotent_and_final(self):
        db = LockedDB(self.tmp / "x.db")
        db.execute("CREATE TABLE t (a)")
        db.close()
        db.close()
        self.assertTrue(db.closed)
        with self.assertRaises(sqlite3.ProgrammingError):
            db.execute("SELECT 1")

    def test_no_resource_warnings_when_objects_are_dropped(self):
        cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                   telegram={"allowed_user_ids": [1], "approval_chat_id": 1})
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            for _ in range(3):
                j = Jarvis(cfg, {"JARVIS_APPROVAL_SECRET": "z" * 48}, channel=lambda *a: None)
                s = ChatStore(self.tmp / "d" / "chat.db")
                del j, s
            gc.collect()
        unclosed = [w for w in caught if issubclass(w.category, ResourceWarning) and "database" in str(w.message)]
        self.assertEqual(unclosed, [])

    def test_jarvis_and_webapp_close_everything(self):
        cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                   telegram={"allowed_user_ids": [1], "approval_chat_id": 1})
        j = Jarvis(cfg, {"JARVIS_APPROVAL_SECRET": "z" * 48}, channel=lambda *a: None)
        auth = wa.AuthStore(self.tmp / "d", j.audit, iterations=1000)
        app = WebApp(cfg, auth, j)
        app.close()
        for db in (j.gate.db, j.budget.db, j.notifier.db, j.rotation.db, auth.db, app.chat.store.db):
            self.assertTrue(db.closed)


if __name__ == "__main__":
    unittest.main()
