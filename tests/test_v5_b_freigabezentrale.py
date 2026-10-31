"""Version 5 · Phase B: Freigabezentrale im Dashboard.

Geprüft wird über dieselbe Schnittstelle wie der Browser (WebApp.handle), ohne Netzwerk.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode

from jarvis import approval as ap
from jarvis import policy
from jarvis import web_auth as wa
from jarvis.audit import AuditLog
from jarvis.config import DEFAULTS, PROJECT_ROOT
from jarvis.core import Jarvis
from jarvis.web import WebApp

HOST = "127.0.0.1:8765"
PW = "Kaffee-Hantel-Duft-Motor-42"
META = {"beschreibung": "Produktpreis von Protein-Guide auf 19 € ändern", "konten": ["Shopify-Shop (Test)"],
        "daten": ["Produkt: Protein-Guide", "Preis alt 24 €, neu 19 €"], "kosten_eur": 0,
        "kosten_hinweis": "keine", "quelle": "Test"}


class Clock:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t


class Base(unittest.TestCase):
    approvals_enabled = False

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.clock = Clock()
        audit = AuditLog(self.tmp / "d" / "audit.jsonl")
        self.store = wa.AuthStore(self.tmp / "d", audit, clock=self.clock, iterations=1000)
        self.store.set_password("inhaber", PW)
        self.cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                        telegram={"allowed_user_ids": [1], "approval_chat_id": 1},
                        web=dict(DEFAULTS["web"], approvals_enabled=self.approvals_enabled))
        self.j = Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": "z" * 48}, channel=lambda *a: None)
        self.app = WebApp(self.cfg, self.store, self.j, clock=self.clock)
        self.addCleanup(self.app.close)
        self.sid = self.login()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def req(self, method, path, body=None, sid=None, **headers):
        h = {"Host": HOST, "Origin": f"http://{HOST}"}
        if sid:
            h["Cookie"] = f"jarvis_session={sid}"
        h.update({k.replace("_", "-"): v for k, v in headers.items()})
        return self.app.handle(method, path, h, urlencode(body).encode() if body is not None else b"")

    def login(self):
        nonce = re.search(r'name="nonce" value="([^"]+)"', self.req("GET", "/login").body.decode()).group(1)
        r = self.req("POST", "/login", {"username": "inhaber", "password": PW, "nonce": nonce})
        return r.header("Set-Cookie").split(";")[0].split("=", 1)[1]

    def page(self, path, sid=None):
        return self.req("GET", path, sid=sid or self.sid).body.decode()

    def propose(self, meta=META, payload=None):
        return self.j.gate.propose("shopify_update_product", payload or {"produkt": "Protein-Guide", "preis": 19},
                                   "Test", meta=meta)

    def form(self, action_id, decision, sid=None):
        """Liest die Formularfelder genau so aus der Seite, wie der Browser sie absenden würde."""
        body = self.page(f"/freigaben/aktion?id={action_id}", sid)
        forms = re.findall(r'<form[^>]*action="/freigaben/entscheiden">(.*?)</form>', body, re.S)
        for f in forms:
            # nur versteckte Felder: Häkchen und Passwort trägt der Mensch selbst ein
            fields = dict(re.findall(r'type="hidden" name="(\w+)" value="([^"]*)"', f))
            if fields.get("d") == decision:
                return fields
        return None

    def decide(self, fields, sid=None, **extra):
        data = dict(fields)
        data.update(extra)
        return self.req("POST", "/freigaben/entscheiden", data, sid=sid or self.sid)

    def outbox(self):
        return sorted((self.tmp / "d" / "sandbox" / "outbox").glob("*.json"))


class OverviewAndDetails(Base):
    def test_b1_requires_login_and_is_in_navigation(self):
        self.assertEqual(self.req("GET", "/freigaben").status, 303)
        self.assertIn('href="/freigaben"', self.page("/"))

    def test_b1_overview_lists_open_actions_with_description_and_cost(self):
        a = self.propose()
        body = self.page("/freigaben")
        self.assertIn("Protein-Guide auf 19", body)
        self.assertIn(a.id, body)
        self.assertIn("0,00 €", body)
        self.assertIn("Notaus auslösen", body)               # Notabschaltung direkt erreichbar
        self.assertIn("/freigaben/protokoll", body)          # Sicherheitsprotokoll verlinkt

    def test_b2_detail_shows_accounts_data_costs_and_exact_content(self):
        a = self.propose(dict(META, kosten_eur=2.5, kosten_hinweis="geschätzte Gebühr"))
        body = self.page(f"/freigaben/aktion?id={a.id}")
        for text in ("Shopify-Shop (Test)", "Preis alt 24 €, neu 19 €", "2,50 €", "geschätzte Gebühr", "preis", a.payload_hash[:16]):
            self.assertIn(text, body)
        self.assertIn("Ablehnen", body)
        self.assertIn("Genehmigen", body)

    def test_b2_content_is_escaped(self):
        a = self.propose(dict(META, beschreibung="<script>alert(1)</script>"), {"text": "<img src=x onerror=1>"})
        body = self.page(f"/freigaben/aktion?id={a.id}")
        self.assertNotIn("<script>alert", body)
        self.assertNotIn("<img src=x", body)

    def test_b2_unknown_or_malformed_id(self):
        self.assertEqual(self.req("GET", "/freigaben/aktion?id=../../etc", sid=self.sid).status, 404)
        self.assertEqual(self.req("GET", "/freigaben/aktion?id=0123456789", sid=self.sid).status, 404)


class DefaultApproveOffRejectOn(Base):
    def test_b3_approve_disabled_by_default_but_reject_works(self):
        a = self.propose()
        body = self.page(f"/freigaben/aktion?id={a.id}")
        self.assertIn("ausgeschaltet", body)
        self.assertIsNone(self.form(a.id, "ok"))          # kein Genehmigen-Formular
        fields = self.form(a.id, "no")
        self.assertEqual(self.decide(fields).status, 303)
        self.assertEqual(self.j.gate.get(a.id).status, ap.REJECTED)
        self.assertEqual(self.outbox(), [])

    def test_b3_forged_approve_post_refused_when_disabled(self):
        a = self.propose()
        fields = dict(self.form(a.id, "no"), d="ok", t=self.j.gate.web_token("ok", a.id, "x"))
        self.decide(fields, password=PW, geprueft="ja")
        self.assertEqual(self.j.gate.get(a.id).status, ap.PENDING)


class Approving(Base):
    approvals_enabled = True

    def test_b4_needs_checkbox_and_password(self):
        a = self.propose()
        fields = self.form(a.id, "ok")
        self.decide(fields, password=PW)                       # Häkchen fehlt
        self.assertEqual(self.j.gate.get(a.id).status, ap.PENDING)
        self.decide(fields, password="falsch", geprueft="ja")  # Passwort falsch
        self.assertEqual(self.j.gate.get(a.id).status, ap.PENDING)
        self.assertEqual(self.outbox(), [])

    def test_b4_correct_approval_executes_exactly_this_action(self):
        a = self.propose()
        r = self.decide(self.form(a.id, "ok"), password=PW, geprueft="ja")
        self.assertEqual(r.header("Location"), "/freigaben")
        self.assertEqual(self.j.gate.get(a.id).status, ap.EXECUTED)
        files = self.outbox()
        self.assertEqual(len(files), 1)
        stored = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertTrue(stored["simuliert"])
        self.assertEqual(stored["preis"], 19)
        log = self.j.audit.path.read_text(encoding="utf-8")
        self.assertIn('"approved"', log)
        self.assertIn('"executed"', log)
        self.assertNotIn(PW, log)

    def test_b5_change_after_display_needs_new_approval(self):
        a = self.propose()
        shown = self.form(a.id, "ok")                       # du siehst Fassung 1 …
        b = self.j.gate.revise(a.id, {"produkt": "Protein-Guide", "preis": 9}, "geändert", META)  # … JARVIS ändert
        self.decide(shown, password=PW, geprueft="ja")
        self.assertEqual(self.j.gate.get(a.id).status, ap.SUPERSEDED)
        self.assertEqual(self.j.gate.get(b.id).status, ap.PENDING)
        self.assertEqual(self.outbox(), [])
        self.assertIn("ersetzt", self.page(f"/freigaben/aktion?id={a.id}"))
        self.assertIn(a.id, self.page(f"/freigaben/aktion?id={b.id}"))      # Verweis auf alte Fassung

    def test_b5_shown_hash_must_match_current_content(self):
        a = self.propose()
        fields = dict(self.form(a.id, "ok"), h="0" * 64)
        self.decide(fields, password=PW, geprueft="ja")
        self.assertEqual(self.j.gate.get(a.id).status, ap.PENDING)
        self.assertIn("angezeigte Fassung veraltet", self.j.audit.path.read_text(encoding="utf-8"))

    def test_b6_database_manipulation_blocks_approval(self):
        a = self.propose()
        fields = self.form(a.id, "ok")
        self.j.gate.db.execute("UPDATE actions SET payload=? WHERE id=?",
                               (json.dumps({"produkt": "Protein-Guide", "preis": 0}), a.id))
        self.decide(fields, password=PW, geprueft="ja")
        self.assertEqual(self.j.gate.get(a.id).status, ap.PENDING)
        self.assertIn("tamper_detected", self.j.audit.path.read_text(encoding="utf-8"))
        self.assertIn("Achtung", self.page(f"/freigaben/aktion?id={a.id}"))

    def test_b6_manipulated_meta_also_detected(self):
        a = self.propose()
        self.j.gate.db.execute("UPDATE action_meta SET meta=? WHERE id=?",
                               (json.dumps(dict(META, kosten_eur=0.0, konten=["anderes Konto"])), a.id))
        self.assertFalse(self.j.gate.intact(self.j.gate.get(a.id)))

    def test_b7_token_bound_to_session_and_csrf_required(self):
        a = self.propose()
        fields = self.form(a.id, "ok")
        other = self.login()                               # neue Anmeldung beendet alte Sitzung
        self.decide(dict(fields, csrf=re.search(r'name="csrf" value="([^"]+)"', self.page("/", other)).group(1)),
                    sid=other, password=PW, geprueft="ja")
        self.assertEqual(self.j.gate.get(a.id).status, ap.PENDING)
        r = self.decide(dict(fields, csrf="falsch"), password=PW, geprueft="ja")
        self.assertIn(r.status, (303, 403))
        self.assertEqual(self.j.gate.get(a.id).status, ap.PENDING)

    def test_b7_cross_site_post_rejected(self):
        a = self.propose()
        r = self.req("POST", "/freigaben/entscheiden", self.form(a.id, "ok"), sid=self.sid,
                     Origin="https://boese.example")
        self.assertEqual(r.status, 403)

    def test_b8_replay_and_parallel_approvals_execute_once(self):
        a = self.propose()
        fields = self.form(a.id, "ok")
        results = []

        def go():
            results.append(self.j.on_web_decision("ok", a.id, fields["t"], "inhaber", self.sid, True,
                                                  shown_hash=fields["h"]))
        threads = [threading.Thread(target=go) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sum(r.startswith("✅") for r in results), 1)
        self.assertEqual(len(self.outbox()), 1)

    def test_b9_killswitch_blocks_approval(self):
        a = self.propose()
        fields = self.form(a.id, "ok")
        csrf = re.search(r'name="csrf" value="([^"]+)"', self.page("/")).group(1)
        self.req("POST", "/notaus", {"csrf": csrf}, sid=self.sid)
        self.assertIsNone(self.form(a.id, "ok"))            # Genehmigen nicht mehr angeboten
        self.decide(fields, password=PW, geprueft="ja")
        self.assertNotEqual(self.j.gate.get(a.id).status, ap.EXECUTED)
        self.assertEqual(self.outbox(), [])

    def test_b16_foreign_web_user_cannot_decide(self):
        a = self.propose()
        fields = self.form(a.id, "ok")
        msg = self.j.on_web_decision("ok", a.id, fields["t"], "angreifer", self.sid, True, shown_hash=fields["h"])
        self.assertTrue(msg.startswith("⛔"))

    def test_b17_expired_action_cannot_be_approved(self):
        a = self.propose()
        fields = self.form(a.id, "ok")
        self.j.gate.db.execute("UPDATE actions SET expires=0 WHERE id=?", (a.id,))
        self.decide(fields, password=PW, geprueft="ja")
        self.assertEqual(self.j.gate.get(a.id).status, ap.EXPIRED)


class SecurityLog(Base):
    def test_b10_log_page_shows_events_but_no_content(self):
        self.j.handle_text("/mail coach@example.com | Vertrag | Geheimer Vertragstext 9876")
        a = self.j.gate.pending()[0]
        self.decide(self.form(a.id, "no"))
        body = self.page("/freigaben/protokoll")
        self.assertIn("Aktion vorgeschlagen", body)
        self.assertIn("Abgelehnt", body)
        self.assertIn("Protokoll ist unverändert", body)
        self.assertNotIn("Vertragstext", body)
        self.assertNotIn("9876", body)


class NoAutomaticApproval(unittest.TestCase):
    def test_b11_only_apply_decision_sets_approved(self):
        src = (PROJECT_ROOT / "jarvis" / "approval.py").read_text(encoding="utf-8")
        uses = [m.start() for m in re.finditer(r"\bAPPROVED\b", src)]
        body = src[src.index("def _apply_decision"):src.index("def execute")]
        sets = re.findall(r"UPDATE actions SET status=\?[^\"]*\", \((\w+)", src)
        self.assertNotIn("APPROVED", sets)       # kein direktes Setzen auf APPROVED …
        self.assertIn("new_status = APPROVED", body)   # … nur hier, nach geprüfter Entscheidung
        for other in (PROJECT_ROOT / "jarvis").glob("*.py"):
            if other.name != "approval.py":
                with self.subTest(other.name):
                    self.assertNotRegex(other.read_text(encoding="utf-8"), r"status\s*=\s*['\"]approved['\"]|APPROVED\b")
        self.assertTrue(uses)

    def test_b12_orders_and_payments_cannot_even_be_proposed(self):
        for t in ("place_order", "purchase", "payment", "spend_money", "bank_access", "irgendwas_neues"):
            self.assertEqual(policy.classify(t), policy.FORBIDDEN)

    def test_b12_new_action_types_need_approval(self):
        for t in ("send_email", "publish_post", "shopify_update_product", "delete_file", "modify_file",
                  "install_skill", "enable_skill", "grant_permission"):
            self.assertEqual(policy.classify(t), policy.APPROVAL)


class MetaRules(Base):
    def test_b13_meta_is_validated(self):
        for bad in ({"unbekannt": 1}, {"kosten_eur": -1}, {"kosten_eur": "5"}, {"kosten_eur": True},
                    {"konten": "kein-liste"}, {"daten": list(range(20))}):
            with self.subTest(bad):
                with self.assertRaises(ValueError):
                    self.propose(bad)

    def test_b13_forbidden_terms_in_meta_blocked(self):
        with self.assertRaises(policy.PolicyViolation):
            self.propose(dict(META, daten=["IBAN des Kunden"]))

    def test_b14_old_actions_without_meta_keep_working(self):
        a = self.j.gate.propose("send_email", {"an": "a@b.de"}, "alt")     # wie bis Version 4.2
        self.assertIsNone(a.meta)
        self.assertEqual(a.payload_hash, ap._hash_payload("send_email", {"an": "a@b.de"}))
        ok, _ = self.j.gate.handle_callback(self.j.gate.callback_data("ok", a.id), 1, 1)
        self.assertTrue(ok)
        self.assertIn("SIMULIERT", self.j.gate.execute(a.id))

    def test_b15_telegram_summary_shows_accounts_and_cost(self):
        text = self.propose().summary()
        self.assertIn("Konten: Shopify-Shop (Test)", text)
        self.assertIn("Kosten: 0,00 €", text)

    def test_b15_mail_and_post_commands_fill_details(self):
        self.j.handle_text("/mail coach@example.com | Hallo | Text")
        a = self.j.gate.pending()[0]
        self.assertIn("coach@example.com", a.meta["beschreibung"])
        self.assertTrue(any("nur simuliert" in k for k in a.meta["konten"]))

    def test_b5_revise_only_for_open_actions(self):
        a = self.propose()
        self.j.gate.handle_callback(self.j.gate.callback_data("no", a.id), 1, 1)
        with self.assertRaises(ap.ApprovalError):
            self.j.gate.revise(a.id, {"preis": 1}, "x", META)


if __name__ == "__main__":
    unittest.main()
