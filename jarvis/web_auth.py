"""Sichere Anmeldung für die lokale Browseroberfläche (Phase 2, Schritt 2).

Nur Python-Standardbibliothek. Enthält:
  - Passwort-Speicherung als PBKDF2-SHA256-Hash mit Salz (niemals Klartext)
  - Sperre nach 5 Fehlversuchen für 15 Minuten (überlebt einen Neustart)
  - Sitzungen mit zufälliger ID, Leerlauf-Abmeldung und Höchstdauer
  - Prüfzeichen gegen gefälschte Anfragen (CSRF-Token) pro Sitzung
  - Sichere Cookie-Einstellungen und Sicherheits-Header
  - Host-Prüfung gegen DNS-Rebinding (nur 127.0.0.1 / localhost)
  - TOTP (6-stellige Codes wie Authenticator-Apps) – vorbereitet, standardmäßig AUS

Es wird hier noch KEIN Webserver gestartet. Das kommt in Schritt 3.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .audit import AuditLog
from .db import LockedDB

PBKDF2_ITERATIONS = 600_000      # ca. 1 Sekunde auf einem MacBook von 2012 – bremst Rateversuche
MIN_PASSWORD_LENGTH = 12
MAX_FAILED_ATTEMPTS = 5
LOCK_SECONDS = 15 * 60
COOKIE_NAME = "jarvis_session"

# Sehr häufige Passwörter werden abgelehnt (kleine Auswahl; Länge ist der Hauptschutz).
_COMMON = {"passwort1234", "password1234", "123456789012", "qwertzuiop12", "jarvisjarvis",
           "iloveyou1234", "passwort12345", "hallohallo12"}


class AuthError(Exception):
    pass


def safe_equal(a: str, b: str) -> bool:
    """Zeitkonstanter Vergleich, der auch bei Umlauten/Sonderzeichen nicht abstürzt."""
    return hmac.compare_digest(str(a).encode("utf-8"), str(b).encode("utf-8"))


# --------------------------------------------------------------------------- Passwörter
def check_password_rules(password: str, username: str = "") -> list[str]:
    """Gibt eine Liste von Problemen zurück (leer = in Ordnung)."""
    problems = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"mindestens {MIN_PASSWORD_LENGTH} Zeichen")
    if password.lower() in _COMMON:
        problems.append("zu häufig verwendetes Passwort")
    if username and username.lower() in password.lower():
        problems.append("darf den Benutzernamen nicht enthalten")
    if len(set(password)) < 6:
        problems.append("zu wenige verschiedene Zeichen")
    return problems


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS, salt: bytes | None = None) -> dict:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return {"algo": "pbkdf2_sha256", "iterations": iterations, "salt": salt.hex(), "hash": digest.hex()}


def verify_password(password: str, record: dict) -> bool:
    if record.get("algo") != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(record["salt"]),
                                 int(record["iterations"]))
    return safe_equal(digest.hex(), record["hash"])


# --------------------------------------------------------------------------- TOTP (vorbereitet)
def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp_code(secret_b32: str, for_time: float, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8), casefold=True)
    counter = struct.pack(">Q", int(for_time // step))
    mac = hmac.new(key, counter, hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10 ** digits)).zfill(digits)


def verify_totp(secret_b32: str, code: str, now: float, window: int = 1) -> bool:
    code = (code or "").strip().replace(" ", "")
    if not (code.isascii() if hasattr(code, "isascii") else all(ord(c) < 128 for c in code)) or not code.isdigit():
        return False
    return any(safe_equal(totp_code(secret_b32, now + d * 30), code) for d in range(-window, window + 1))


# --------------------------------------------------------------------------- Benutzer + Sperre
class AuthStore:
    """Speichert den (einzigen) Benutzer in data/web_auth.json mit Dateirechten 600."""

    def __init__(self, data_dir: str | Path, audit: AuditLog, clock: Callable[[], float] = time.time,
                 iterations: int = PBKDF2_ITERATIONS):
        self.path = Path(data_dir) / "web_auth.json"
        self.audit = audit
        self.clock = clock
        self.iterations = iterations
        self.db = LockedDB(Path(data_dir) / "web_auth.db")
        self.db.execute("CREATE TABLE IF NOT EXISTS attempts (username TEXT PRIMARY KEY, failed INTEGER, locked_until REAL)")

    def is_configured(self) -> bool:
        return self.path.exists()

    def _load(self) -> dict:
        try:
            rec = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(rec, dict) or "password" not in rec or "username" not in rec:
                raise ValueError("unvollständig")
            return rec
        except (OSError, ValueError) as exc:
            raise AuthError("Die Passwortdatei data/web_auth.json ist beschädigt oder unlesbar. Bitte aus der "
                            "Sicherung wiederherstellen oder mit 'python3 -m jarvis web-passwort' neu setzen.") from exc

    def _log_name(self, username: str) -> str:
        """Für das Protokoll: echter Name nur, wenn er dem eingerichteten Benutzer entspricht.
        Sonst könnte ein versehentlich ins Namensfeld getipptes Passwort im Klartext im Protokoll landen."""
        try:
            if self.is_configured() and safe_equal(username, self._load()["username"]):
                return username
        except AuthError:
            pass
        return f"(unbekannt, {len(username)} Zeichen)"

    def username(self) -> str | None:
        return self._load().get("username") if self.is_configured() else None

    def set_password(self, username: str, password: str, replace: bool = False) -> None:
        problems = check_password_rules(password, username)
        if problems:
            raise AuthError("Passwort ungeeignet: " + ", ".join(problems))
        if self.is_configured() and not replace:
            raise AuthError("Es ist bereits ein Passwort gesetzt.")
        record = {"username": username, "password": hash_password(password, self.iterations),
                  "totp_secret": None, "created": int(self.clock())}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        # Datei von Anfang an nur für dich lesbar anlegen (Rechte 600)
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(record, fh)
        os.replace(str(tmp), str(self.path))
        self.audit.write("web_password_set", username=username, replaced=bool(replace))

    def _attempts(self, username: str) -> tuple[int, float]:
        row = self.db.execute("SELECT failed, locked_until FROM attempts WHERE username=?", (username,)).fetchone()
        return (int(row[0]), float(row[1])) if row else (0, 0.0)

    def locked_seconds(self, username: str) -> int:
        _, until = self._attempts(username)
        return max(0, int(until - self.clock()))

    def login(self, username: str, password: str) -> bool:
        """True bei Erfolg. Bei Sperre AuthError (mit Restzeit)."""
        username = (username or "").strip()[:64]      # Länge begrenzen (Tabelle wächst nicht unbegrenzt)
        password = (password or "")[:256]
        with self.db.lock:
            remaining = self.locked_seconds(username)
            if remaining:
                self.audit.write("web_login_blocked", username=self._log_name(username), remaining_s=remaining)
                raise AuthError(f"Zu viele Fehlversuche. Bitte in {remaining // 60 + 1} Minuten erneut versuchen.")
            ok = False
            if self.is_configured():
                rec = self._load()
                # Hash immer berechnen, auch bei falschem Namen: gleiche Dauer verrät nichts.
                ok_pw = verify_password(password or "", rec["password"])
                ok = ok_pw and safe_equal(username, rec["username"])
            if ok:
                self.db.execute("DELETE FROM attempts WHERE username=?", (username,))
                self.audit.write("web_login_ok", username=username)
                return True
            failed, _ = self._attempts(username)
            failed += 1
            locked_until = self.clock() + LOCK_SECONDS if failed >= MAX_FAILED_ATTEMPTS else 0.0
            self.db.execute("INSERT OR REPLACE INTO attempts VALUES (?,?,?)",
                            (username, 0 if locked_until else failed, locked_until))
            self.audit.write("web_login_failed", username=self._log_name(username), attempt=failed,
                             locked=bool(locked_until))
            return False

    def close(self) -> None:
        """Datenbankverbindung schließen."""
        self.db.close()

# --------------------------------------------------------------------------- Sitzungen
@dataclass
class Session:
    id: str
    username: str
    csrf: str
    created: float
    last_seen: float
    second_factor_at: float = 0.0
    data: dict = field(default_factory=dict)


class SessionManager:
    """Sitzungen nur im Arbeitsspeicher: Nach einem Neustart ist jeder abgemeldet (gewollt)."""

    def __init__(self, idle_minutes: int = 30, max_hours: int = 12, clock: Callable[[], float] = time.time):
        self.idle = idle_minutes * 60
        self.max_age = max_hours * 3600
        self.clock = clock
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, username: str) -> Session:
        now = self.clock()
        s = Session(id=secrets.token_urlsafe(32), username=username, csrf=secrets.token_urlsafe(32),
                    created=now, last_seen=now)
        with self._lock:
            # Nur eine Sitzung pro Benutzer: neue Anmeldung beendet alte Sitzungen
            for sid in [k for k, v in self._sessions.items() if v.username == username]:
                del self._sessions[sid]
            self._sessions[s.id] = s
        return s

    def get(self, session_id: str | None) -> Session | None:
        if not session_id:
            return None
        now = self.clock()
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None:
                return None
            if now - s.last_seen > self.idle or now - s.created > self.max_age:
                del self._sessions[session_id]
                return None
            s.last_seen = now
            return s

    def destroy(self, session_id: str | None) -> None:
        with self._lock:
            self._sessions.pop(session_id or "", None)

    def destroy_all(self) -> None:
        with self._lock:
            self._sessions.clear()

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)


def check_csrf(session: Session | None, token: str | None) -> bool:
    return bool(session and token) and safe_equal(session.csrf, token)


# --------------------------------------------------------------------------- HTTP-Hilfen
def session_cookie(session_id: str, max_age: int, secure: bool = False) -> str:
    """Cookie: für JavaScript unsichtbar (HttpOnly), nur von eigenen Seiten (SameSite=Strict).

    'Secure' (nur über HTTPS) wird gesetzt, sobald JARVIS über HTTPS läuft (Server/Tunnel).
    Lokal auf 127.0.0.1 läuft die Verbindung nicht über das Netzwerk.
    """
    parts = [f"{COOKIE_NAME}={session_id}", "HttpOnly", "SameSite=Strict", "Path=/", f"Max-Age={int(max_age)}"]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def clear_cookie() -> str:
    return f"{COOKIE_NAME}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"


def read_cookie(header: str | None) -> str | None:
    for part in (header or "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE_NAME and value:
            return value
    return None


SECURITY_HEADERS = {
    # Nur eigene Dateien; kein Inline-JavaScript; keine Einbettung in fremde Seiten
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                                "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
                                "form-action 'self'; frame-ancestors 'none'"),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    # "same-origin": Browser melden bei eigenen Formularen die echte Herkunft (bei "no-referrer" senden
    # Firefox/Chrome "Origin: null" und die Herkunftsprüfung würde die Anmeldung blockieren). Fremde Seiten
    # erfahren weiterhin nichts.
    "Referrer-Policy": "same-origin",
    "Cache-Control": "no-store",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}


def host_allowed(host_header: str | None, port: int) -> bool:
    """Schutz gegen DNS-Rebinding: Nur Anfragen an 127.0.0.1/localhost mit dem richtigen Port."""
    return (host_header or "").strip().lower() in {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
