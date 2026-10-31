"""Technisch erzwungene Freigabeschicht.

Ablauf:
  1. Das Sprachmodell darf Aktionen nur VORSCHLAGEN (propose). Es bekommt keinen Zugriff
     auf execute(), das Geheimnis oder die Datenbank.
  2. Jeder Vorschlag bekommt eine zufällige ID, einen Hash des genauen Inhalts (payload)
     und ein Ablaufdatum.
  3. Telegram-Buttons tragen eine HMAC-Signatur über (Entscheidung, ID, Inhalts-Hash, Nonce).
     Das Geheimnis kennt nur dieser Dienst – nicht das Sprachmodell.
  4. Eine Freigabe zählt nur, wenn: Telegram-Benutzer-ID erlaubt, Chat stimmt, Signatur stimmt,
     Aktion noch offen, nicht abgelaufen, Notabschaltung aus. Jede Freigabe ist einmalig.
  5. execute() prüft ALLES erneut (Status, Inhalts-Hash, Policy) direkt vor der Ausführung.

Version 5 (Freigabezentrale):
  6. Beschreibung, betroffene Konten, betroffene Daten und mögliche Kosten (meta) sind TEIL des signierten
     Inhalts. Eine Freigabe gilt nur für genau die angezeigte Fassung.
  7. Eine Aktion wird nie verändert. Eine Änderung erzeugt eine NEUE Aktion (revise); die alte wird „ersetzt“
     und kann nicht mehr freigegeben werden.
  8. Vor jeder Freigabe wird der gespeicherte Inhalt erneut gegen seinen Hash geprüft (Manipulation der Datenbank).
  9. Es gibt keine automatische Genehmigung: Den Status „approved“ setzt ausschließlich _apply_decision nach
     geprüfter Signatur eines berechtigten Menschen.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import policy
from .audit import AuditLog
from .db import LockedDB
from .killswitch import KillSwitch

PENDING, APPROVED, REJECTED, EXECUTED, EXPIRED, FAILED, SUPERSEDED = (
    "pending", "approved", "rejected", "executed", "expired", "failed", "superseded")
STATUS_LABEL = {PENDING: "wartet auf dich", APPROVED: "freigegeben", REJECTED: "abgelehnt", EXECUTED: "ausgeführt",
                EXPIRED: "abgelaufen", FAILED: "fehlgeschlagen", SUPERSEDED: "ersetzt (geändert)"}

META_FIELDS = {"beschreibung": str, "konten": list, "daten": list, "kosten_eur": (int, float),
               "kosten_hinweis": str, "quelle": str}
META_TEXT_MAX = 500
META_LIST_MAX = 10


class ApprovalError(PermissionError):
    pass


@dataclass
class Action:
    id: str
    action_type: str
    payload: dict
    reason: str
    status: str
    created: float
    expires: float
    payload_hash: str
    approver: str | None = None
    meta: dict | None = None
    replaces: str | None = None

    def summary(self) -> str:
        lines = [f"Aktion #{self.id} – {self.action_type}", f"Grund: {self.reason}"]
        m = self.meta or {}
        if m.get("beschreibung"):
            lines.append(f"Was: {m['beschreibung']}")
        if m.get("konten"):
            lines.append("Konten: " + ", ".join(m["konten"]))
        if m.get("daten"):
            lines.append("Daten: " + ", ".join(m["daten"]))
        if self.meta is not None:
            lines.append(f"Kosten: {format_eur(m.get('kosten_eur', 0))}"
                         + (f" ({m['kosten_hinweis']})" if m.get("kosten_hinweis") else ""))
        for k, v in self.payload.items():
            v = str(v)
            lines.append(f"• {k}: {v[:300]}{'…' if len(v) > 300 else ''}")
        mins = max(0, int((self.expires - time.time()) // 60))
        lines.append(f"Risiko: {policy.RISK_LABEL[policy.classify(self.action_type)]} · gültig noch {mins} Min.")
        return "\n".join(lines)


def format_eur(value) -> str:
    return f"{float(value or 0):.2f} €".replace(".", ",")


def _hash_payload(action_type: str, payload: dict, meta: dict | None = None) -> str:
    # Ohne meta exakt wie bis Version 4.2: ältere offene Aktionen behalten ihren gültigen Hash.
    body = {"t": action_type, "p": payload} if meta is None else {"t": action_type, "p": payload, "m": meta}
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def clean_meta(meta: dict | None) -> dict | None:
    """Prüft die Angaben zur Anzeige. Unbekannte Felder oder falsche Typen werden abgelehnt (nicht still verworfen)."""
    if meta is None:
        return None
    if not isinstance(meta, dict):
        raise ValueError("meta muss ein Objekt sein.")
    out = {}
    for key, value in meta.items():
        kind = META_FIELDS.get(key)
        if kind is None:
            raise ValueError(f"Unbekannte Angabe '{key}'.")
        if key == "kosten_eur":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value != value:
                raise ValueError("kosten_eur muss eine Zahl ≥ 0 sein.")
            out[key] = round(float(value), 2)
        elif kind is list:
            if not isinstance(value, list) or len(value) > META_LIST_MAX:
                raise ValueError(f"{key} muss eine Liste mit höchstens {META_LIST_MAX} Einträgen sein.")
            out[key] = [str(v)[:META_TEXT_MAX] for v in value]
        else:
            out[key] = str(value)[:META_TEXT_MAX]
    out.setdefault("kosten_eur", 0.0)
    return out


class ApprovalGate:
    def __init__(self, db_path: str | Path, secret: str, audit: AuditLog, kill: KillSwitch,
                 allowed_user_ids: list[int], approval_chat_id: int | None = None,
                 ttl_minutes: int = 60, forbidden_terms: list[str] | None = None,
                 web_approvals_enabled: bool = False, allowed_web_users: list[str] | None = None):
        if not secret or len(secret) < 32:
            raise ValueError("JARVIS_APPROVAL_SECRET fehlt oder ist zu kurz (mind. 32 Zeichen).")
        self._secret = secret.encode()
        self.audit = audit
        self.kill = kill
        self.allowed = {int(u) for u in allowed_user_ids}
        self.chat_id = int(approval_chat_id) if approval_chat_id is not None else None
        self.ttl = ttl_minutes * 60
        self.forbidden_terms = forbidden_terms or []
        self.web_approvals_enabled = bool(web_approvals_enabled)
        self.allowed_web_users = set(allowed_web_users or [])
        self._handlers: dict[str, Callable[[dict], str]] = {}
        self.db = LockedDB(db_path)
        existed = self._has_table("actions")
        self.db.execute("""CREATE TABLE IF NOT EXISTS actions (
            id TEXT PRIMARY KEY, action_type TEXT, payload TEXT, reason TEXT, status TEXT,
            created REAL, expires REAL, payload_hash TEXT, nonce TEXT, approver TEXT, result TEXT)""")
        # Version 5: Anzeige-Angaben in einer NEUEN Tabelle. Die bestehende Tabelle bleibt unverändert,
        # ältere JARVIS-Versionen können die Datei weiter lesen (sie ignorieren die neue Tabelle).
        # Bei einer BESTEHENDEN älteren Datenbank wird die Tabelle erst angelegt, wenn wirklich eine Aktion mit
        # Angaben gespeichert wird (nach deiner Zustimmung beim Start). Lesende Befehle verändern die Datei nicht.
        if not existed:
            self._ensure_meta_table()

    def _has_table(self, name: str) -> bool:
        return self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

    def _ensure_meta_table(self) -> None:
        self.db.execute("""CREATE TABLE IF NOT EXISTS action_meta (
            id TEXT PRIMARY KEY, meta TEXT, replaces TEXT)""")

    # ---------- Ausführende Funktionen registrieren (nur beim Start, nicht durch das LLM) ----------
    def register_handler(self, action_type: str, fn: Callable[[dict], str]) -> None:
        self._handlers[action_type] = fn

    # ---------- 1. Vorschlagen ----------
    def propose(self, action_type: str, payload: dict, reason: str, meta: dict | None = None,
                _replaces: str | None = None) -> Action:
        level = policy.classify(action_type)
        if level == policy.FORBIDDEN:
            self.audit.write("blocked", action_type=action_type, reason="Aktionstyp gesperrt")
            raise policy.PolicyViolation(f"Aktionstyp '{action_type}' ist gesperrt.")
        policy.check_payload(payload, self.forbidden_terms)
        meta = clean_meta(meta)
        if meta is not None:
            policy.check_payload(meta, self.forbidden_terms)
        action_id = secrets.token_hex(5)          # 10 Zeichen, nicht erratbar
        nonce = secrets.token_hex(8)
        now = time.time()
        p_hash = _hash_payload(action_type, payload, meta)
        if meta is not None or _replaces:
            self._ensure_meta_table()
        with self.db.transaction():
            self.db.execute("INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                action_id, action_type, json.dumps(payload, ensure_ascii=False), reason, PENDING,
                now, now + self.ttl, p_hash, nonce, None, None))
            if meta is not None or _replaces:
                self.db.execute("INSERT INTO action_meta VALUES (?,?,?)",
                                (action_id, json.dumps(meta, ensure_ascii=False) if meta is not None else None,
                                 _replaces))
        self.audit.write("proposed", id=action_id, action_type=action_type, payload_hash=p_hash, reason=reason,
                         replaces=_replaces, kosten_eur=(meta or {}).get("kosten_eur", 0.0))
        return self.get(action_id)

    def revise(self, action_id: str, payload: dict, reason: str, meta: dict | None = None) -> Action:
        """Änderung einer offenen Aktion = NEUE Aktion mit neuer Freigabe. Die alte gilt als „ersetzt“."""
        old = self.get(action_id)
        if old is None:
            raise ApprovalError("Unbekannte Aktion.")
        with self.db.lock:
            cur = self.db.execute("UPDATE actions SET status=? WHERE id=? AND status=?", (SUPERSEDED, action_id, PENDING))
            if cur.rowcount != 1:
                raise ApprovalError(f"Nur offene Aktionen können geändert werden (Status: {old.status}).")
        self.audit.write("superseded", id=action_id)
        return self.propose(old.action_type, payload, reason, meta, _replaces=action_id)

    def get(self, action_id: str) -> Action | None:
        if not self._has_table("action_meta"):          # ältere Datenbank, noch nicht ergänzt
            row = self.db.execute(
                "SELECT id, action_type, payload, reason, status, created, expires, payload_hash, approver "
                "FROM actions WHERE id=?", (action_id,)).fetchone()
            if not row:
                return None
            return Action(row[0], row[1], json.loads(row[2]), row[3], row[4], row[5], row[6], row[7], row[8])
        row = self.db.execute(
            "SELECT a.id, a.action_type, a.payload, a.reason, a.status, a.created, a.expires, a.payload_hash, "
            "a.approver, m.meta, m.replaces FROM actions a LEFT JOIN action_meta m ON m.id = a.id WHERE a.id=?",
            (action_id,)).fetchone()
        if not row:
            return None
        meta = json.loads(row[9]) if row[9] else None
        return Action(row[0], row[1], json.loads(row[2]), row[3], row[4], row[5], row[6], row[7], row[8],
                      meta, row[10])

    def intact(self, action: Action) -> bool:
        """Stimmt der gespeicherte Inhalt (inkl. Anzeige-Angaben) noch mit dem Hash bei der Erstellung überein?"""
        return hmac.compare_digest(_hash_payload(action.action_type, action.payload, action.meta),
                                   action.payload_hash)

    def recent(self, limit: int = 15) -> list[Action]:
        """Zuletzt entschiedene oder erledigte Aktionen (nur lesen)."""
        self._expire_old()
        ids = [r[0] for r in self.db.execute("SELECT id FROM actions WHERE status != ? ORDER BY created DESC LIMIT ?",
                                             (PENDING, max(1, min(int(limit), 100))))]
        return [self.get(i) for i in ids]

    def pending(self) -> list[Action]:
        self._expire_old()
        ids = [r[0] for r in self.db.execute("SELECT id FROM actions WHERE status=? ORDER BY created", (PENDING,))]
        return [self.get(i) for i in ids]

    def _expire_old(self) -> None:
        self.db.execute("UPDATE actions SET status=? WHERE status=? AND expires<?", (EXPIRED, PENDING, time.time()))

    # ---------- 2. Signierte Buttons erzeugen ----------
    def _sign(self, decision: str, action_id: str, bind: str = "") -> str:
        row = self.db.execute("SELECT payload_hash, nonce FROM actions WHERE id=?", (action_id,)).fetchone()
        if not row:
            raise ApprovalError("Unbekannte Aktion")
        msg = f"{decision}|{action_id}|{row[0]}|{row[1]}".encode()
        if bind:  # z. B. an eine Browser-Sitzung binden; Telegram-Signaturen bleiben unverändert
            msg += f"|{bind}".encode()
        mac = hmac.new(self._secret, msg, hashlib.sha256).digest()[:15]
        return base64.urlsafe_b64encode(mac).decode()   # 20 Zeichen

    def callback_data(self, decision: str, action_id: str) -> str:
        """Inhalt eines Telegram-Buttons (max. 64 Byte), z. B. 'ok:3fa9c1d2e4:Abc…'."""
        if decision not in ("ok", "no"):
            raise ValueError("decision muss 'ok' oder 'no' sein")
        return f"{decision}:{action_id}:{self._sign(decision, action_id)}"

    # ---------- 3a. Telegram: Button-Klick prüfen ----------
    def handle_callback(self, data: str, from_user_id: int, chat_id: int) -> tuple[bool, str]:
        try:
            decision, action_id, sig = data.split(":", 2)
        except ValueError:
            self.audit.write("callback_rejected", channel="telegram", reason="Format", user=from_user_id)
            return False, "Ungültige Anfrage."
        if int(from_user_id) not in self.allowed:
            self.audit.write("callback_rejected", channel="telegram", reason="fremder Benutzer",
                             user=from_user_id, id=action_id)
            return False, "Nicht berechtigt."
        if self.chat_id is not None and int(chat_id) != self.chat_id:
            self.audit.write("callback_rejected", channel="telegram", reason="falscher Chat",
                             user=from_user_id, id=action_id)
            return False, "Falscher Chat."
        ok, msg = self._verify_signature(decision, action_id, sig, "", "telegram", from_user_id)
        if not ok:
            return False, msg
        return self._apply_decision(decision, action_id, f"telegram:{from_user_id}")

    # ---------- 3b. Browser: Entscheidung prüfen (Phase 2) ----------
    def web_token(self, decision: str, action_id: str, session_id: str) -> str:
        """Signatur für einen Browser-Button. Gilt nur für genau diese Sitzung."""
        if decision not in ("ok", "no"):
            raise ValueError("decision muss 'ok' oder 'no' sein")
        return self._sign(decision, action_id, bind=f"web|{session_id}")

    def handle_web_decision(self, decision: str, action_id: str, token: str, web_user: str,
                            session_id: str, second_factor_ok: bool, shown_hash: str | None = None) -> tuple[bool, str]:
        """Freigabe aus dem Browser. Standardmäßig AUS (nur Anzeige).

        Wenn eingeschaltet, gilt zusätzlich zu allen Telegram-Prüfungen:
          - Benutzer steht auf der Web-Whitelist,
          - Signatur ist an die aktuelle Sitzung gebunden,
          - für eine FREIGABE ist ein frisch geprüfter zweiter Faktor (Code) nötig.
        """
        if not self.web_approvals_enabled and decision == "ok":
            # Version 5: ABLEHNEN geht im Browser immer (dabei passiert nichts). Genehmigen nur, wenn eingeschaltet.
            self.audit.write("callback_rejected", channel="web", reason="Web-Freigaben deaktiviert", id=action_id)
            return False, "Genehmigen im Browser ist ausgeschaltet. Ablehnen ist möglich."
        if web_user not in self.allowed_web_users or not session_id:
            self.audit.write("callback_rejected", channel="web", reason="fremder Benutzer", user=web_user, id=action_id)
            return False, "Nicht berechtigt."
        if decision == "ok" and not second_factor_ok:
            self.audit.write("callback_rejected", channel="web", reason="zweiter Faktor fehlt", user=web_user, id=action_id)
            return False, "Für eine Freigabe ist der Bestätigungscode nötig."
        ok, msg = self._verify_signature(decision, action_id, token, f"web|{session_id}", "web", web_user)
        if not ok:
            return False, msg
        if shown_hash is not None:
            action = self.get(action_id)
            if action is None or not hmac.compare_digest(str(shown_hash).encode("utf-8"),
                                                         action.payload_hash.encode()):
                self.audit.write("callback_rejected", channel="web", reason="angezeigte Fassung veraltet", id=action_id)
                return False, "Die Aktion wurde seit der Anzeige geändert. Bitte die neue Fassung prüfen."
        return self._apply_decision(decision, action_id, f"web:{web_user}")

    # ---------- gemeinsame Prüfung für alle Kanäle ----------
    def _verify_signature(self, decision: str, action_id: str, sig: str, bind: str,
                          channel: str, user) -> tuple[bool, str]:
        if decision not in ("ok", "no"):
            return False, "Ungültige Entscheidung."
        try:
            expected = self._sign(decision, action_id, bind=bind)
        except ApprovalError:
            self.audit.write("callback_rejected", channel=channel, reason="unbekannte ID", user=user, id=action_id)
            return False, "Unbekannte Aktion."
        # Als Bytes vergleichen: compare_digest stürzt bei Sonderzeichen in Texten sonst ab
        if not hmac.compare_digest(expected.encode(), str(sig).encode("utf-8")):
            self.audit.write("callback_rejected", channel=channel, reason="Signatur falsch", user=user, id=action_id)
            return False, "Signatur ungültig."
        return True, ""

    def _apply_decision(self, decision: str, action_id: str, approver: str) -> tuple[bool, str]:
        if decision == "ok" and self.kill.is_active():
            return False, "Notabschaltung aktiv – Freigabe nicht möglich."
        self._expire_old()
        if decision == "ok":
            action = self.get(action_id)
            if action is None or not self.intact(action):
                self.audit.write("tamper_detected", id=action_id, stage="vor Freigabe")
                return False, "Inhalt der Aktion stimmt nicht mit der Erstellung überein – Freigabe verweigert."
        new_status = APPROVED if decision == "ok" else REJECTED
        # Atomar und einmalig: nur wenn die Aktion noch 'pending' ist.
        cur = self.db.execute("UPDATE actions SET status=?, approver=? WHERE id=? AND status=?",
                              (new_status, approver, action_id, PENDING))
        if cur.rowcount != 1:
            action = self.get(action_id)
            self.audit.write("callback_rejected", reason="nicht mehr offen", id=action_id,
                             status=action.status if action else None)
            return False, f"Aktion ist nicht mehr offen ({action.status if action else '?'})."
        self.audit.write(new_status, id=action_id, user=approver)
        return True, "Freigegeben." if decision == "ok" else "Abgelehnt."

    # ---------- 4. Ausführen (nur nach Freigabe) ----------
    def execute(self, action_id: str) -> str:
        self.kill.check()
        action = self.get(action_id)
        if action is None:
            raise ApprovalError("Unbekannte Aktion.")
        if action.status != APPROVED:
            raise ApprovalError(f"Aktion #{action_id} ist nicht freigegeben (Status: {action.status}).")
        if not self.intact(action):
            self.audit.write("tamper_detected", id=action_id)
            raise ApprovalError("Inhalt wurde nach der Freigabe verändert – Ausführung gestoppt.")
        if policy.classify(action.action_type) == policy.FORBIDDEN:
            raise policy.PolicyViolation("Aktionstyp gesperrt.")
        handler = self._handlers.get(action.action_type)
        if handler is None:
            raise ApprovalError(f"Kein Ausführer für '{action.action_type}' registriert.")
        # Atomar auf 'executed' setzen, damit nichts doppelt ausgeführt wird.
        cur = self.db.execute("UPDATE actions SET status=? WHERE id=? AND status=?", (EXECUTED, action_id, APPROVED))
        if cur.rowcount != 1:
            raise ApprovalError("Aktion wurde bereits ausgeführt.")
        try:
            result = handler(action.payload)
        except Exception as exc:  # noqa: BLE001
            self.db.execute("UPDATE actions SET status=?, result=? WHERE id=?", (FAILED, str(exc), action_id))
            self.audit.write("failed", id=action_id, error=str(exc))
            raise
        self.db.execute("UPDATE actions SET result=? WHERE id=?", (result, action_id))
        self.audit.write("executed", id=action_id, action_type=action.action_type, result=result)
        return result

    def close(self) -> None:
        """Datenbankverbindung schließen."""
        self.db.close()
