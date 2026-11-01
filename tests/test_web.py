"""Sicherheitstests Phase 2, Schritt 2 (Anmeldung + lokale Weboberfläche) – python3 -m unittest -v"""
import http.client
import json
import os
import re
import shutil
import stat
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode

from jarvis import web_auth as wa
from jarvis.audit import AuditLog
from jarvis.config import DEFAULTS
from jarvis.core import Jarvis
from jarvis.speech import NARRATOR, narrate_markup
from jarvis.web import WebApp, make_handler

PORT = 8765
HOST = f"127.0.0.1:{PORT}"
GOOD_PW = "Kaffee-Hantel-Duft-Motor-42"
FAST = 1000  # wenige PBKDF2-Runden, damit Tests schnell sind (echt: 600.000)


class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.clock = Clock()
        self.audit = AuditLog(self.tmp / "audit.jsonl")
        self.store = wa.AuthStore(self.tmp, self.audit, clock=self.clock, iterations=FAST)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def configured(self):
        self.store.set_password("inhaber", GOOD_PW)
        return self.store


# ------------------------------------------------------------------ Passwörter
class PasswordTests(Base):
    def test_hash_roundtrip_and_salt(self):
        a, b = wa.hash_password("x" * 12, FAST), wa.hash_password("x" * 12, FAST)
        self.assertNotEqual(a["hash"], b["hash"])          # eigenes Salz pro Speicherung
        self.assertTrue(wa.verify_password("x" * 12, a))
        self.assertFalse(wa.verify_password("y" * 12, a))

    def test_default_iterations_strong(self):
        self.assertGreaterEqual(wa.PBKDF2_ITERATIONS, 600_000)

    def test_weak_passwords_rejected(self):
        for pw in ("kurz", "aaaaaaaaaaaaaaa", "passwort1234", "inhaber-ist-toll-2026"):
            with self.subTest(pw=pw), self.assertRaises(wa.AuthError):
                wa.AuthStore(self.tmp / pw.replace("/", "_"), self.audit, iterations=FAST).set_password("inhaber", pw)

    def test_file_has_no_plaintext_and_mode_600(self):
        self.configured()
        raw = self.store.path.read_text()
        self.assertNotIn(GOOD_PW, raw)
        self.assertEqual(stat.S_IMODE(os.stat(self.store.path).st_mode), 0o600)
        self.assertNotIn(GOOD_PW, self.audit.path.read_text())

    def test_no_silent_overwrite(self):
        self.configured()
        with self.assertRaises(wa.AuthError):
            self.store.set_password("inhaber", "Ganz-Anderes-Passwort-99")
        self.store.set_password("inhaber", "Ganz-Anderes-Passwort-99", replace=True)
        self.assertTrue(self.store.login("inhaber", "Ganz-Anderes-Passwort-99"))


# ------------------------------------------------------------------ Anmeldung + Sperre
class LoginTests(Base):
    def test_login_ok_and_wrong(self):
        self.configured()
        self.assertTrue(self.store.login("inhaber", GOOD_PW))
        self.assertFalse(self.store.login("inhaber", "falsch-falsch-falsch"))
        self.assertFalse(self.store.login("fremder", GOOD_PW))

    def test_not_configured_never_logs_in(self):
        self.assertFalse(self.store.login("inhaber", GOOD_PW))

    def test_lockout_after_five_failures_even_with_right_password(self):
        self.configured()
        for _ in range(wa.MAX_FAILED_ATTEMPTS):
            self.assertFalse(self.store.login("inhaber", "falsch-falsch-falsch"))
        with self.assertRaises(wa.AuthError):
            self.store.login("inhaber", GOOD_PW)

    def test_lock_survives_restart_and_expires(self):
        self.configured()
        for _ in range(wa.MAX_FAILED_ATTEMPTS):
            self.store.login("inhaber", "falsch-falsch-falsch")
        restarted = wa.AuthStore(self.tmp, self.audit, clock=self.clock, iterations=FAST)
        with self.assertRaises(wa.AuthError):
            restarted.login("inhaber", GOOD_PW)
        self.clock.t += wa.LOCK_SECONDS + 1
        self.assertTrue(restarted.login("inhaber", GOOD_PW))

    def test_failed_logins_are_audited_without_password(self):
        self.configured()
        self.store.login("inhaber", "geheimer-falscher-versuch")
        text = self.audit.path.read_text()
        self.assertIn("web_login_failed", text)
        self.assertNotIn("geheimer-falscher-versuch", text)
        self.assertTrue(self.audit.verify()[0])


# ------------------------------------------------------------------ Sitzungen + CSRF
class SessionTests(Base):
    def test_ids_random_and_long(self):
        sm = wa.SessionManager(clock=self.clock)
        ids = {sm.create(f"u{i}").id for i in range(50)}
        self.assertEqual(len(ids), 50)
        self.assertTrue(all(len(i) >= 40 for i in ids))

    def test_idle_timeout_and_max_age(self):
        sm = wa.SessionManager(idle_minutes=30, max_hours=12, clock=self.clock)
        s = sm.create("inhaber")
        self.clock.t += 29 * 60
        self.assertIsNotNone(sm.get(s.id))
        self.clock.t += 31 * 60
        self.assertIsNone(sm.get(s.id))
        s2 = sm.create("inhaber")
        for _ in range(30):                    # aktiv, aber länger als 12 Stunden
            self.clock.t += 25 * 60
            sm.get(s2.id)
        self.assertIsNone(sm.get(s2.id))

    def test_new_login_ends_old_session(self):
        sm = wa.SessionManager(clock=self.clock)
        old = sm.create("inhaber")
        sm.create("inhaber")
        self.assertIsNone(sm.get(old.id))

    def test_csrf(self):
        sm = wa.SessionManager(clock=self.clock)
        s = sm.create("inhaber")
        self.assertTrue(wa.check_csrf(s, s.csrf))
        self.assertFalse(wa.check_csrf(s, "falsch"))
        self.assertFalse(wa.check_csrf(s, ""))
        self.assertFalse(wa.check_csrf(None, s.csrf))

    def test_cookie_flags(self):
        c = wa.session_cookie("abc", 1800)
        for flag in ("HttpOnly", "SameSite=Strict", "Path=/", "Max-Age=1800"):
            self.assertIn(flag, c)
        self.assertIn("Secure", wa.session_cookie("abc", 1800, secure=True))
        self.assertEqual(wa.read_cookie("a=1; jarvis_session=xyz; b=2"), "xyz")


# ------------------------------------------------------------------ TOTP (vorbereitet)
class TotpTests(unittest.TestCase):
    def test_rfc6238_vectors(self):
        secret = __import__("base64").b32encode(b"12345678901234567890").decode()
        self.assertEqual(wa.totp_code(secret, 59, digits=8), "94287082")
        self.assertEqual(wa.totp_code(secret, 1111111109, digits=8), "07081804")
        self.assertEqual(wa.totp_code(secret, 2000000000, digits=8), "69279037")

    def test_verify_window(self):
        sec = wa.new_totp_secret()
        code = wa.totp_code(sec, 1_000_000)
        self.assertTrue(wa.verify_totp(sec, code, 1_000_000 + 25))
        self.assertFalse(wa.verify_totp(sec, code, 1_000_000 + 400))
        self.assertFalse(wa.verify_totp(sec, "abcdef", 1_000_000))


# ------------------------------------------------------------------ Web-App (ohne Netzwerk)
class WebAppTests(Base):
    def setUp(self):
        super().setUp()
        self.configured()
        self.cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                        telegram={"allowed_user_ids": [1], "approval_chat_id": 1})
        self.jarvis = Jarvis(self.cfg, {"JARVIS_APPROVAL_SECRET": "z" * 48}, channel=lambda *a: None)
        self.app = WebApp(self.cfg, self.store, self.jarvis, clock=self.clock)

    def req(self, method, path, body=None, cookie=None, **headers):
        h = {"Host": HOST}
        if cookie:
            h["Cookie"] = f"jarvis_session={cookie}"
        h.update({k.replace("_", "-"): v for k, v in headers.items()})
        data = urlencode(body).encode() if body is not None else b""
        return self.app.handle(method, path, h, data)

    def nonce(self):
        return re.search(r'name="nonce" value="([^"]+)"', self.req("GET", "/login").body.decode()).group(1)

    def login(self, pw=GOOD_PW):
        r = self.req("POST", "/login", {"username": "inhaber", "password": pw, "nonce": self.nonce()},
                     Origin=f"http://{HOST}")
        cookie = r.header("Set-Cookie")
        return r, (cookie.split(";")[0].split("=", 1)[1] if cookie else None)

    def csrf(self, sid):
        return re.search(r'name="csrf" value="([^"]+)"', self.req("GET", "/", cookie=sid).body.decode()).group(1)

    def test_home_requires_login(self):
        r = self.req("GET", "/")
        self.assertEqual(r.status, 303)
        self.assertEqual(r.header("Location"), "/login")

    def test_login_flow(self):
        r, sid = self.login()
        self.assertEqual(r.status, 303)
        self.assertIn("HttpOnly", r.header("Set-Cookie"))
        home = self.req("GET", "/", cookie=sid)
        self.assertEqual(home.status, 200)
        self.assertIn("Willkommen", home.body.decode())

    def test_wrong_password_generic_message(self):
        r, sid = self.login("falsch-falsch-falsch")
        self.assertIsNone(sid)
        self.assertEqual(r.status, 401)
        self.assertIn("Benutzername oder Passwort ist falsch", r.body.decode())

    def test_login_nonce_single_use(self):
        n = self.nonce()
        body = {"username": "inhaber", "password": GOOD_PW, "nonce": n}
        self.assertEqual(self.req("POST", "/login", body).status, 303)
        self.assertNotEqual(self.req("POST", "/login", body).status, 303)

    def test_bad_host_rejected(self):
        for host in ("evil.example", "127.0.0.1:9999", "jarvis.attacker.com:8765", ""):
            r = self.app.handle("GET", "/login", {"Host": host})
            with self.subTest(host=host):
                self.assertEqual(r.status, 400)

    def test_cross_site_post_rejected(self):
        _, sid = self.login()
        token = self.csrf(sid)
        r = self.req("POST", "/notaus", {"csrf": token}, cookie=sid, Origin="https://evil.example")
        self.assertEqual(r.status, 403)
        r = self.req("POST", "/notaus", {"csrf": token}, cookie=sid, Sec_Fetch_Site="cross-site")
        self.assertEqual(r.status, 403)
        self.assertFalse(self.jarvis.kill.is_active())

    def test_origin_null_rejected_and_referrer_policy(self):
        _, sid = self.login()
        r = self.req("POST", "/notaus", {"csrf": self.csrf(sid)}, cookie=sid, Origin="null")
        self.assertEqual(r.status, 403)
        self.assertEqual(self.req("GET", "/login").header("Referrer-Policy"), "same-origin")

    def test_actions_need_csrf(self):
        _, sid = self.login()
        self.assertEqual(self.req("POST", "/notaus", {"csrf": "falsch"}, cookie=sid).status, 403)
        self.assertEqual(self.req("POST", "/logout", {}, cookie=sid).status, 403)
        self.assertFalse(self.jarvis.kill.is_active())

    def test_killswitch_via_browser(self):
        _, sid = self.login()
        r = self.req("POST", "/notaus", {"csrf": self.csrf(sid)}, cookie=sid, Origin=f"http://{HOST}")
        self.assertEqual(r.status, 303)
        self.assertTrue(self.jarvis.kill.is_active())
        self.assertIn("AKTIV", self.req("GET", "/", cookie=sid).body.decode())

    def test_logout_invalidates_session(self):
        _, sid = self.login()
        r = self.req("POST", "/logout", {"csrf": self.csrf(sid)}, cookie=sid)
        self.assertIn("Max-Age=0", r.header("Set-Cookie"))
        self.assertEqual(self.req("GET", "/", cookie=sid).status, 303)

    def test_forged_session_cookie_rejected(self):
        self.assertEqual(self.req("GET", "/", cookie="ausgedacht123").status, 303)

    def test_session_expires_after_idle(self):
        _, sid = self.login()
        self.clock.t += 31 * 60
        self.assertEqual(self.req("GET", "/", cookie=sid).status, 303)

    def test_security_headers_on_every_response(self):
        for r in (self.req("GET", "/login"), self.req("GET", "/"), self.req("GET", "/gibtsnicht"),
                  self.app.handle("GET", "/", {"Host": "evil"})):
            for name in ("Content-Security-Policy", "X-Frame-Options", "X-Content-Type-Options", "Cache-Control"):
                self.assertIsNotNone(r.header(name), name)
        csp = self.req("GET", "/login").header("Content-Security-Policy")
        self.assertIn("script-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)

    def test_message_text_is_escaped(self):
        self.jarvis.notifier.notify("<script>alert(1)</script>", "urgent")
        _, sid = self.login()
        body = self.req("GET", "/", cookie=sid).body.decode()
        self.assertNotIn("<script>alert", body)
        self.assertIn("&lt;script&gt;", body)

    def test_static_only_whitelisted(self):
        self.assertEqual(self.req("GET", "/static/jarvis.css").status, 200)
        for p in ("/static/../web_auth.py", "/static/web_auth.py", "/static/%2e%2e/config.py"):
            self.assertEqual(self.req("GET", p).status, 404, p)

    def test_no_external_resources_in_pages(self):
        _, sid = self.login()
        login = self.req("GET", "/login").body.decode()
        home = self.req("GET", "/", cookie=sid).body.decode()
        static = Path(__file__).resolve().parent.parent / "jarvis/web_static"
        for body in (login, home, (static / "jarvis.css").read_text(), (static / "hud.js").read_text()):
            self.assertNotRegex(body, r"https?://(?!127\.0\.0\.1)")
        self.assertNotIn("<script", login)                                   # Anmeldung: gar kein Skript
        # Stand 16: Startseite lädt genau ein eigenes Skript (Datenkugel), kein Inline-Code, keine Inline-Styles
        self.assertEqual(re.findall(r"<script[^>]*>", home), ['<script src="/static/hud.js" defer>'])
        self.assertNotIn(' style="', home)
        self.assertNotIn("innerHTML", (static / "hud.js").read_text())

    def test_unicode_attacks_do_not_crash(self):
        _, sid = self.login()
        for bad in ("ä" * 40, "💥", "\x00"):
            r = self.req("POST", "/notaus", {"csrf": bad}, cookie=sid)
            self.assertEqual(r.status, 403, bad)
        r = self.req("POST", "/login", {"username": "jürgen", "password": "ö" * 20, "nonce": self.nonce()})
        self.assertEqual(r.status, 401)
        self.assertFalse(self.jarvis.kill.is_active())

    def test_umlaut_username_and_password_work(self):
        store = wa.AuthStore(self.tmp / "u", self.audit, iterations=FAST)
        store.set_password("Jürgen", "Grüße-aus-Köln-2026!")
        self.assertTrue(store.login("Jürgen", "Grüße-aus-Köln-2026!"))
        self.assertFalse(wa.verify_totp(wa.new_totp_secret(), "１２３４５６", 0))   # Vollbreite-Ziffern

    def test_oversized_body_rejected(self):
        from jarvis.web import MAX_BODY
        r = self.app.handle("POST", "/login", {"Host": HOST}, b"x" * (MAX_BODY + 1))
        self.assertEqual(r.status, 413)


# ------------------------------------------------------------------ Echter Server auf 127.0.0.1
class LiveServerTests(Base):
    def test_real_http_roundtrip(self):
        self.configured()
        cfg = dict(DEFAULTS, data_dir=str(self.tmp / "d"), vault_dir=str(self.tmp / "v"),
                   web=dict(DEFAULTS["web"], port=0))
        app = WebApp(cfg, self.store, None)
        app.quiet = True
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
        app.port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            host = f"127.0.0.1:{app.port}"
            c = http.client.HTTPConnection("127.0.0.1", app.port, timeout=5)
            c.request("GET", "/login", headers={"Host": host})
            r = c.getresponse()
            page = r.read().decode()
            self.assertEqual(r.status, 200)
            self.assertEqual(r.getheader("Server"), "JARVIS")              # keine Versionsangaben
            nonce = re.search(r'name="nonce" value="([^"]+)"', page).group(1)
            body = urlencode({"username": "inhaber", "password": GOOD_PW, "nonce": nonce})
            c.request("POST", "/login", body=body, headers={
                "Host": host, "Origin": f"http://{host}", "Content-Type": "application/x-www-form-urlencoded"})
            r = c.getresponse()
            r.read()
            self.assertEqual(r.status, 303)
            sid = r.getheader("Set-Cookie").split(";")[0]
            c.request("GET", "/", headers={"Host": host, "Cookie": sid})
            r = c.getresponse()
            self.assertIn("Willkommen", r.read().decode())
            c.close()
        finally:
            httpd.shutdown()
            httpd.server_close()


class VoiceTests(unittest.TestCase):
    def test_narrator_markup_adds_pauses_and_blocks_injection(self):
        out = narrate_markup("Guten Morgen. Ich habe etwas gefunden! [[volm 9]] Ende.", NARRATOR)
        self.assertTrue(out.startswith(f"[[rate {NARRATOR.words_per_minute}]]"))
        self.assertIn(f"[[slnc {NARRATOR.sentence_pause_ms}]]", out)
        self.assertNotIn("[[volm", out)

    def test_narrator_is_style_not_person(self):
        self.assertIn("Erzähler", NARRATOR.style_instruction)


class ConfigTests(unittest.TestCase):
    def test_young_living_area_present(self):
        self.assertIn("Young Living Network-Marketing", DEFAULTS["business_areas"])
        self.assertEqual(len(DEFAULTS["business_areas"]), 13)


if __name__ == "__main__":
    unittest.main()
