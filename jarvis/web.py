"""Lokale Browseroberfläche – Phase 2, Schritt 2: sichere Anmeldung.

Start:  python3 -m jarvis web     →  Firefox: http://127.0.0.1:8765

Schutzmaßnahmen bei JEDER Anfrage:
  1. Host-Prüfung (nur 127.0.0.1/localhost mit richtigem Port) – gegen DNS-Rebinding
  2. Größenlimit für Anfragen
  3. Bei Formularen (POST): Herkunft muss diese Seite sein (Origin / Sec-Fetch-Site)
  4. Geschützte Seiten nur mit gültiger Sitzung, Aktionen nur mit gültigem CSRF-Token
  5. Strenge Sicherheits-Header (kein fremdes JavaScript, keine Einbettung, kein Zwischenspeichern)
Es gibt bewusst KEIN JavaScript in Schritt 2 – das schont das MacBook und verkleinert die Angriffsfläche.
"""
from __future__ import annotations

import html
import json
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlsplit

from .web_brain import BrainPages

from . import web_auth as wa
from .chat import MAX_MESSAGE_CHARS, ROLE_JARVIS, ROLE_SYSTEM, ROLE_USER, ChatError, ChatService, ChatStore
from .markdown_safe import render as render_markdown
from .profiles import create_missing_drafts, profile_status

STATIC_DIR = Path(__file__).resolve().parent / "web_static"
SAFE_RETURN = re.compile(r"/wissen(/notiz\?id=[0-9a-f]{16})?|/chat\?g=[0-9a-f]{12}")
UNLOCK_SECONDS = 10 * 60   # so lange bleiben vertrauliche Notizen nach Passworteingabe sichtbar
MAX_BODY = 32 * 1024   # reicht für 4.000 Zeichen Chat-Text mit Umlauten (je bis zu 6 Byte kodiert)
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")
CURRENT = ' aria-current="page"'   # als Konstante: Python 3.8 erlaubt keine \ in f-String-Ausdrücken



# ---------------------------------------------------------------------- HUD-Grafiken (Version 5.3)
# Reines SVG, animiert nur über jarvis.css (kein JavaScript, keine externen Dateien – passt zur strengen CSP).
def hud_globe(css_class: str = "globe", label: str = "Drehende Weltkugel") -> str:
    lats = "".join(f'<ellipse class="g-lat" cx="0" cy="{y}" rx="{rx}" ry="{ry}"/>'
                   for y, rx, ry in ((0, 80, 7), (-40, 69, 6), (40, 69, 6), (-69, 40, 3.5), (69, 40, 3.5)))
    mers = "".join(f'<ellipse class="g-mer m{i}" cx="0" cy="0" rx="80" ry="80"/>' for i in range(1, 7))
    return (f'<svg class="{html.escape(css_class)}" viewBox="-120 -120 240 240" role="img" aria-label="{html.escape(label)}">'
            '<circle class="g-glow" r="86"/>'
            '<g class="g-ring g-ring-a"><circle class="g-dash" r="110"/></g>'
            '<g class="g-ring g-ring-b"><circle class="g-dash2" r="100"/></g>'
            '<g class="g-ticks"><circle class="g-tick" r="116"/></g>'
            '<circle class="g-sphere" r="80"/>' + lats + mers +
            '<g class="g-orbit"><circle class="g-path" r="100"/><circle class="g-dot" cx="0" cy="-100" r="3"/></g>'
            '<g class="g-orbit g-orbit-b"><circle class="g-path" r="110"/><circle class="g-dot" cx="0" cy="110" r="2.2"/></g>'
            '<line class="g-scan" x1="-80" y1="0" x2="80" y2="0"/>'
            '</svg>')


# Portal beim Betreten des Chats: liegt AUSSERHALB von <main>, damit es den ganzen Bildschirm füllt
PORTAL = ('<div class="portal" aria-hidden="true"><div class="p-rays"></div><div class="p-ring a"></div>'
          '<div class="p-ring b"></div><div class="p-ring c"></div><div class="p-core"></div></div>')


def _lv(pct: float) -> int:
    """Füllstand in 5er-Stufen (CSS-Klassen lv0…lv100), weil die strenge CSP Inline-Styles verbietet."""
    return int(max(0, min(100, round(float(pct) / 5) * 5)))


def hud_reactor() -> str:
    return ('<svg class="reactor" viewBox="-12 -12 24 24" aria-hidden="true">'
            '<circle class="r-core" r="4"/><g class="r-spin"><circle class="r-ring" r="9"/></g></svg>')

class Response:
    def __init__(self, status: int, body: str | bytes = b"", content_type: str = "text/html; charset=utf-8",
                 headers: list | None = None):
        self.status = status
        self.body = body.encode("utf-8") if isinstance(body, str) else body
        self.headers = [("Content-Type", content_type)] + list(headers or [])

    def header(self, name: str) -> str | None:
        return next((v for k, v in self.headers if k.lower() == name.lower()), None)


def redirect(location: str, extra: list | None = None) -> Response:
    # Grundschutz: nur Adressen dieser Seite, keine Zeilenumbrüche (sonst könnten Header eingeschleust werden)
    if not location.startswith("/") or location.startswith("//") or any(c in location for c in "\r\n\\"):
        location = "/"
    return Response(303, b"", headers=[("Location", location)] + list(extra or []))


class LoginNonces:
    """Einmal-Token für das Anmeldeformular (Schutz gegen untergeschobene Anmeldungen)."""

    def __init__(self, ttl: int = 600, clock: Callable[[], float] = time.time):
        self.ttl, self.clock = ttl, clock
        self._items: dict[str, float] = {}
        self._lock = threading.Lock()

    def issue(self) -> str:
        token = secrets.token_urlsafe(24)
        with self._lock:
            now = self.clock()
            self._items = {k: v for k, v in self._items.items() if v > now}   # Abgelaufene aufräumen
            if len(self._items) > 200:
                self._items.clear()
            self._items[token] = now + self.ttl
        return token

    def consume(self, token: str | None) -> bool:
        with self._lock:
            expires = self._items.pop(token or "", None)
        return expires is not None and expires > self.clock()


# ---------------------------------------------------------------------- Freigabezentrale (Version 5)
SECURITY_EVENTS = {
    "proposed": "Aktion vorgeschlagen", "approved": "Freigegeben", "rejected": "Abgelehnt", "executed": "Ausgeführt",
    "failed": "Fehlgeschlagen", "superseded": "Ersetzt (geändert)", "blocked": "Gesperrte Aktion verhindert",
    "callback_rejected": "Entscheidung abgewiesen", "tamper_detected": "MANIPULATION erkannt",
    "killswitch_on": "Notabschaltung ausgelöst", "killswitch_off": "Notabschaltung aufgehoben",
    "external_ai_blocked": "KI-Zugriff gesperrt", "ai_access": "KI-Zugriff erlaubt",
    "web_login_failed": "Anmeldung fehlgeschlagen", "web_login": "Angemeldet", "web_locked": "Anmeldung gesperrt",
    "skill_blocked": "Skill blockiert", "skill_run": "Skill ausgeführt", "skill_state": "Skill-Status geändert",
    "task_run": "Aufgabe ausgeführt", "task_failed": "Aufgabe fehlgeschlagen", "task_state": "Aufgabe geändert",
}
# Nur diese Angaben erscheinen im Browser – keine Inhalte, keine Geheimnisse
SECURITY_DETAIL_KEYS = ("id", "action_type", "user", "username", "channel", "reason", "status", "model", "task",
                        "decision", "source", "skill", "stage", "replaces", "kosten_eur", "state", "task_id")


class ApprovalPages:
    """Mixin: Seiten der Freigabezentrale. Getrennt, damit web.py übersichtlich bleibt."""

    def _web_approvals_ready(self) -> tuple:
        gate = self.jarvis.gate
        if not gate.web_approvals_enabled:
            return False, ("Genehmigen im Browser ist ausgeschaltet (web.approvals_enabled = false). Ablehnen geht "
                           "immer. Zum Einschalten siehe docs/18.")
        if self.jarvis.kill.is_active():
            return False, "Notabschaltung aktiv: Es kann nichts genehmigt werden."
        return True, ""

    @staticmethod
    def _status_pill(status: str) -> str:
        from .approval import STATUS_LABEL
        cls = {"pending": "warn", "executed": "ok", "approved": "ok", "failed": "alert"}.get(status, "")
        return f"<span class=\"pill {cls}\"><b>{html.escape(STATUS_LABEL.get(status, status))}</b></span>"

    def _action_row(self, a) -> str:
        from .approval import format_eur
        from . import policy
        meta = a.meta or {}
        what = meta.get("beschreibung") or a.reason
        cost = format_eur(meta.get("kosten_eur", 0)) if a.meta is not None else "nicht angegeben"
        risk = policy.RISK_LABEL[policy.classify(a.action_type)]
        return (f"<li><a href=\"/freigaben/aktion?id={html.escape(a.id)}\">{html.escape(what[:140])}</a>"
                f"<span class=\"mono\">#{html.escape(a.id)} · {html.escape(a.action_type)} · Risiko {risk} · "
                f"Kosten {html.escape(cost)}</span> {self._status_pill(a.status)}</li>")

    def _approvals_page(self, session) -> Response:
        gate, kill = self.jarvis.gate, self.jarvis.kill.is_active()
        pend = gate.pending()
        flash, ok = session.data.pop("flash", ""), session.data.pop("flash_ok", "")
        msg = (f"<p class=\"error\" role=\"alert\">{html.escape(flash)}</p>" if flash else "") + \
              (f"<p class=\"success\" role=\"status\">{html.escape(ok)}</p>" if ok else "")
        ready, why = self._web_approvals_ready()
        mode = ("" if ready else f"<p class=\"notice\">{html.escape(why)}</p>")
        rows = "".join(self._action_row(a) for a in pend) or "<li>Keine offenen Aktionen. JARVIS wartet.</li>"
        done = "".join(self._action_row(a) for a in gate.recent(10)) or "<li>Noch nichts entschieden.</li>"
        csrf = html.escape(session.csrf)
        inner = f"""<header class="top"><div><p class="eyebrow">JARVIS · Freigabezentrale</p><h1>Freigaben</h1></div>
<a class="button" href="/freigaben/protokoll">Sicherheitsprotokoll</a></header>
{msg}
<section class="pills" aria-label="Status"><span class="pill {'alert' if kill else 'ok'}">Notaus <b>{'AKTIV' if kill else 'aus'}</b></span>
<span class="pill {'warn' if pend else ''}">Offen <b>{len(pend)}</b></span>
<span class="pill">Genehmigen im Browser <b>{'an' if self.jarvis.gate.web_approvals_enabled else 'aus'}</b></span></section>
{mode}
<section class="panel"><h2>Offene Aktionen</h2><ul class="list hits">{rows}</ul>
<p class="hint">Jede Aktion läuft nach {int(self.cfg.get('approval_ttl_minutes', 60))} Minuten ab. Eine Freigabe gilt nur für genau die angezeigte Fassung.</p></section>
<section class="panel"><h2>Zuletzt entschieden</h2><ul class="list hits">{done}</ul></section>
<section class="panel danger"><h2>Notabschaltung</h2><p>Stoppt sofort alle Aktionen und KI-Aufrufe. Aufheben nur im Terminal mit <code>python3 -m jarvis resume</code>.</p>
<form method="post" action="/notaus"><input type="hidden" name="csrf" value="{csrf}"><button class="stop" type="submit" {'disabled' if kill else ''}>Notaus auslösen</button></form></section>"""
        return Response(200, self._page("Freigaben", inner, body_class="wide", session=session, active="freigaben"))

    def _action_page(self, session, action_id: str) -> Response:
        from .approval import PENDING, format_eur
        from . import policy
        gate = self.jarvis.gate
        a = gate.get(action_id) if re.fullmatch(r"[0-9a-f]{10}", action_id or "") else None
        if a is None:
            return Response(404, self._page("Freigaben", "<section class=\"panel\"><h2>Nicht gefunden</h2><p>Diese "
                                            "Aktion gibt es nicht.</p><p><a href=\"/freigaben\">Zur Übersicht</a></p>"
                                            "</section>", session=session, active="freigaben"))
        gate.pending()          # abgelaufene Aktionen markieren
        a = gate.get(a.id)
        meta = a.meta or {}
        flash = session.data.pop("flash", "")
        err = f"<p class=\"error\" role=\"alert\">{html.escape(flash)}</p>" if flash else ""
        lst = lambda items: "".join(f"<li>{html.escape(str(i))}</li>" for i in items) or "<li>nicht angegeben</li>"  # noqa: E731
        payload_rows = "".join(f"<tr><th>{html.escape(str(k))}</th><td><pre>{html.escape(str(v))}</pre></td></tr>"
                               for k, v in a.payload.items()) or "<tr><td>leer</td></tr>"
        intact = gate.intact(a)
        warn = "" if intact else "<p class=\"error\" role=\"alert\"><b>Achtung:</b> Der gespeicherte Inhalt stimmt nicht mit der Erstellung überein. Freigabe ist gesperrt.</p>"
        replaced = (f"<p class=\"hint\">Ersetzt die frühere Fassung #{html.escape(a.replaces)}.</p>" if a.replaces else "")
        cost = format_eur(meta.get("kosten_eur", 0)) if a.meta is not None else "nicht angegeben (ältere Aktion)"
        cost_note = f" · {html.escape(meta['kosten_hinweis'])}" if meta.get("kosten_hinweis") else ""
        risk = policy.RISK_LABEL[policy.classify(a.action_type)]
        left = max(0, int((a.expires - time.time()) // 60))
        forms = ""
        if a.status == PENDING and intact:
            csrf, sid = html.escape(session.csrf), session.id
            ready, why = self._web_approvals_ready()
            t_ok, t_no = gate.web_token("ok", a.id, sid), gate.web_token("no", a.id, sid)
            common = (f"<input type=\"hidden\" name=\"csrf\" value=\"{csrf}\"><input type=\"hidden\" name=\"id\" "
                      f"value=\"{html.escape(a.id)}\"><input type=\"hidden\" name=\"h\" value=\"{html.escape(a.payload_hash)}\">")
            if ready:
                approve = (f"<form class=\"redact\" method=\"post\" action=\"/freigaben/entscheiden\">{common}"
                           f"<input type=\"hidden\" name=\"d\" value=\"ok\"><input type=\"hidden\" name=\"t\" value=\"{t_ok}\">"
                           f"<label><input type=\"checkbox\" name=\"geprueft\" value=\"ja\" required> Ich habe Beschreibung, "
                           f"Konten, Daten und Kosten geprüft. Die Freigabe gilt nur für genau diese Fassung.</label>"
                           f"<label for=\"pw\">Passwort zur Bestätigung</label>"
                           f"<input id=\"pw\" name=\"password\" type=\"password\" autocomplete=\"current-password\" required maxlength=\"256\">"
                           f"<button type=\"submit\">Genehmigen</button></form>")
            else:
                approve = f"<p class=\"notice\">{html.escape(why)}</p><button type=\"button\" disabled>Genehmigen</button>"
            reject = (f"<form method=\"post\" action=\"/freigaben/entscheiden\">{common}"
                      f"<input type=\"hidden\" name=\"d\" value=\"no\"><input type=\"hidden\" name=\"t\" value=\"{t_no}\">"
                      f"<button class=\"stop\" type=\"submit\">Ablehnen</button></form>")
            forms = f"<section class=\"panel\"><h2>Deine Entscheidung</h2>{approve}{reject}</section>"
        inner = f"""<p class="crumb"><a href="/freigaben">Freigaben</a> / <span class="mono">#{html.escape(a.id)}</span></p>
{err}{warn}
<section class="panel"><h2>Geplante Aktion</h2>
<p><b>{html.escape(meta.get('beschreibung') or a.reason)}</b></p>
<p>{self._status_pill(a.status)} <span class="mono">{html.escape(a.action_type)} · Risiko {risk} · gültig noch {left} Min.</span></p>
<p class="hint">Grund: {html.escape(a.reason)} · Herkunft: {html.escape(meta.get('quelle', 'nicht angegeben'))}</p>{replaced}</section>
<section class="panel"><h2>Betroffene Konten</h2><ul class="list">{lst(meta.get('konten', []))}</ul></section>
<section class="panel"><h2>Betroffene Daten</h2><ul class="list">{lst(meta.get('daten', []))}</ul></section>
<section class="panel"><h2>Mögliche Kosten</h2><p><b>{html.escape(cost)}</b>{cost_note}</p></section>
<section class="panel"><h2>Genauer Inhalt</h2><div class="md-table"><table><tbody>{payload_rows}</tbody></table></div>
<p class="hint">Prüfsumme dieser Fassung: <span class="mono">{html.escape(a.payload_hash[:16])}…</span></p></section>
{forms}"""
        return Response(200, self._page(f"Aktion {a.id}", inner, body_class="wide", session=session, active="freigaben"))

    def _decide(self, session, action_id: str, decision: str, token: str, shown_hash: str, password: str,
                checked: str) -> Response:
        target = f"/freigaben/aktion?id={action_id}" if re.fullmatch(r"[0-9a-f]{10}", action_id or "") else "/freigaben"
        if decision not in ("ok", "no"):
            session.data["flash"] = "Ungültige Entscheidung."
            return redirect(target)
        second_factor = False
        if decision == "ok":
            if checked != "ja":
                session.data["flash"] = "Nicht genehmigt: Das Prüf-Häkchen fehlte."
                return redirect(target)
            try:
                second_factor = bool(password) and self.auth.login(session.username, password)
            except wa.AuthError as exc:
                session.data["flash"] = str(exc)
                return redirect(target)
            if not second_factor:
                session.data["flash"] = "Passwort falsch. Nichts wurde genehmigt."
                return redirect(target)
        result = self.jarvis.on_web_decision(decision, action_id, token, session.username, session.id,
                                             second_factor, shown_hash=shown_hash)
        if result.startswith("⛔") or result.startswith("⚠️"):
            session.data["flash"] = result
            return redirect(target)
        session.data["flash_ok"] = result
        return redirect("/freigaben")

    def _security_log_page(self, session) -> Response:
        audit = self.jarvis.audit
        ok, msg = audit.verify()
        rows = []
        for e in reversed(audit.tail(400)):
            ev = e.get("event", "")
            if ev not in SECURITY_EVENTS:
                continue
            d = e.get("details") or {}
            info = " · ".join(f"{k}: {str(d[k])[:80]}" for k in SECURITY_DETAIL_KEYS if k in d and d[k] not in (None, ""))
            cls = " class=\"alert\"" if ev in ("tamper_detected", "killswitch_on") else ""
            rows.append(f"<li{cls}><span class=\"mono\">{html.escape(str(e.get('ts', ''))[:19])}</span> "
                        f"<b>{html.escape(SECURITY_EVENTS[ev])}</b> <span class=\"mono\">{html.escape(info)}</span></li>")
            if len(rows) >= 60:
                break
        inner = f"""<p class="crumb"><a href="/freigaben">Freigaben</a> / Sicherheitsprotokoll</p>
<section class="pills"><span class="pill {'ok' if ok else 'alert'}">Protokoll <b>{html.escape(msg)}</b></span></section>
<section class="panel"><h2>Letzte sicherheitsrelevante Ereignisse</h2><ul class="list">{''.join(rows) or '<li>Noch keine Einträge.</li>'}</ul>
<p class="hint">Angezeigt werden nur Art, Zeitpunkt und Kennungen – nie Inhalte von Nachrichten oder Schlüssel. Vollständig im Terminal: <code>python3 -m jarvis audit</code></p></section>"""
        return Response(200, self._page("Sicherheitsprotokoll", inner, body_class="wide", session=session,
                                        active="freigaben"))


class SkillPages:
    """Mixin: Skill-Verwaltung (Version 5, Phase C). Einschalten nur über die Freigabezentrale."""

    def _skills_page(self, session) -> Response:
        from .skills import PERMISSIONS
        runner = self.jarvis.skills
        flash, ok = session.data.pop("flash", ""), session.data.pop("flash_ok", "")
        result = session.data.pop("skill_result", "")
        msg = (f"<p class=\"error\" role=\"alert\">{html.escape(flash)}</p>" if flash else "") + \
              (f"<p class=\"success\" role=\"status\">{html.escape(ok)}</p>" if ok else "")
        if result:
            msg += f"<section class=\"panel\"><h2>Ergebnis des Testlaufs</h2><pre>{html.escape(result)}</pre></section>"
        csrf = html.escape(session.csrf)
        open_requests = {a.payload.get("skill") for a in self.jarvis.gate.pending() if a.action_type == "enable_skill"}
        cards = []
        for row in runner.overview():
            spec = row["spec"]
            sid = html.escape(spec.id)
            adapter = runner._adapter(spec)
            if row["blocked"]:
                state = "<span class=\"pill alert\"><b>gesperrt</b></span>"
            elif row["enabled"]:
                state = "<span class=\"pill ok\"><b>an</b></span>"
            else:
                state = "<span class=\"pill\"><b>aus</b></span>"
            perms = "".join(
                f"<li><span class=\"mono\">{html.escape(pid)}</span> {html.escape(PERMISSIONS[pid][0])} · Risiko "
                f"{html.escape(PERMISSIONS[pid][1])}{' · <b>erteilt</b>' if pid in row['granted'] else ''}</li>"
                for pid in spec.permissions if pid in PERMISSIONS)
            checks = "".join(f"<li>{'✅' if lvl == 'ok' else '⛔'} {html.escape(text)}</li>"
                             for lvl, text in runner.security_check(spec.id))
            hidden = f"<input type=\"hidden\" name=\"csrf\" value=\"{csrf}\"><input type=\"hidden\" name=\"skill\" value=\"{sid}\">"
            if row["enabled"]:
                tests = "".join(
                    f"<form class=\"inline\" method=\"post\" action=\"/skills/test\">{hidden}"
                    f"<input type=\"hidden\" name=\"op\" value=\"{html.escape(name)}\">"
                    f"<button class=\"ghost\" type=\"submit\">Testlauf: {html.escape(op.description)}</button></form>"
                    for name, op in spec.operations.items() if op.kind == "lesen" and not op.params)
                buttons = (tests + f"<form class=\"inline\" method=\"post\" action=\"/skills/aus\">{hidden}"
                           f"<button class=\"stop\" type=\"submit\">Ausschalten</button></form>")
            elif spec.id in open_requests:
                buttons = "<p class=\"hint\">Aktivierung beantragt – wartet unter <a href=\"/freigaben\">Freigaben</a>.</p>"
            elif row["blocked"]:
                buttons = "<p class=\"hint\">Gesperrt, weil die Sicherheitsprüfung nicht bestanden ist.</p>"
            else:
                buttons = (f"<form method=\"post\" action=\"/skills/beantragen\">{hidden}"
                           f"<button type=\"submit\">Aktivierung beantragen</button></form>")
            note = f"<p class=\"hint\">{html.escape(spec.notes)}</p>" if spec.notes else ""
            cards.append(f"""<section class="panel" id="skill-{sid}"><h2>{html.escape(spec.name)}</h2>
<p>{state} <span class="mono">{sid}</span></p><p>{html.escape(spec.description)}</p>
<p class="hint">Adapter: {html.escape(getattr(adapter, 'label', '?'))}</p>
<h3 class="eyebrow">Berechtigungen</h3><ul class="list">{perms}</ul>
<h3 class="eyebrow">Sicherheitsprüfung</h3><ul class="list">{checks}</ul>{note}{buttons}</section>""")
        inner = f"""<header class="top"><div><p class="eyebrow">JARVIS · Fähigkeiten</p><h1>Skills</h1></div></header>
{msg}
<p class="notice">Alle Skills sind anfangs <b>aus</b>. Einschalten geht nur über die Freigabezentrale; Ausschalten jederzeit sofort. Zurzeit arbeiten alle Skills mit Testadaptern: keine Kontoverbindung, kein Internet.</p>
{''.join(cards)}"""
        return Response(200, self._page("Skills", inner, body_class="wide", session=session, active="skills"))

    def _skill_action(self, session, what: str, skill_id: str, op: str) -> Response:
        from .skills import SkillBlocked, SkillError
        runner = self.jarvis.skills
        if skill_id not in runner.catalog:
            session.data["flash"] = "Unbekannter Skill."
            return redirect("/skills")
        try:
            if what == "beantragen":
                a = runner.request_enable(skill_id, self.jarvis.gate)
                session.data["flash_ok"] = f"Aktivierung beantragt (#{a.id}). Bitte unter Freigaben prüfen."
            elif what == "aus":
                runner.disable(skill_id, via=f"web:{session.username}")
                session.data["flash_ok"] = "Skill ausgeschaltet. Alle Berechtigungen wurden entzogen."
            else:
                spec = runner.catalog[skill_id]
                operation = spec.operations.get(op)
                if operation is None or operation.kind != "lesen" or operation.params:
                    raise SkillBlocked("Testlauf nur für lesende Operationen ohne Angaben.")
                session.data["skill_result"] = runner.run(skill_id, op).text[:6000]
        except (SkillBlocked, SkillError, PermissionError, ValueError) as exc:
            session.data["flash"] = str(exc)
        return redirect(f"/skills#skill-{skill_id}")


class TaskPages:
    """Mixin: Aufgabenplaner (Version 5, Phase E)."""

    def _tasks_page(self, session) -> Response:
        sch = self.jarvis.scheduler
        flash, ok = session.data.pop("flash", ""), session.data.pop("flash_ok", "")
        result = session.data.pop("task_result", "")
        msg = (f"<p class=\"error\" role=\"alert\">{html.escape(flash)}</p>" if flash else "") + \
              (f"<p class=\"success\" role=\"status\">{html.escape(ok)}</p>" if ok else "")
        if result:
            msg += f"<section class=\"panel\"><h2>Ergebnis des Testlaufs</h2><article class=\"note\">{render_markdown(result)}</article></section>"
        csrf = html.escape(session.csrf)
        rows = []
        for r in sch.overview():
            t, last = r["task"], r["last"]
            hidden = f"<input type=\"hidden\" name=\"csrf\" value=\"{csrf}\"><input type=\"hidden\" name=\"task\" value=\"{html.escape(t.id)}\">"
            toggle = ("fortsetzen", "Fortsetzen") if r["status"] == "pausiert" else ("pause", "Pausieren")
            nxt = r["next"].strftime("%d.%m. %H:%M") if r["next"] else "–"
            last_txt = (f"{html.escape(last['slot'])}: <b>{html.escape(last['status'] or '')}</b>" if last else "noch nie")
            note = f"<p class=\"hint\">{html.escape(r['note'])}</p>" if r["note"] else ""
            pill = "warn" if r["status"] == "pausiert" else "ok"
            rows.append(f"""<section class="panel"><h2>{html.escape(t.name)}</h2>
<p><span class="pill {pill}"><b>{r['status']}</b></span> <span class="mono">{html.escape(t.id)} · {html.escape(r['plan'])} · nächster Lauf {nxt}</span></p>
<p>{html.escape(t.description)}</p><p class="hint">Letzter Lauf: {last_txt}</p>{note}
<form class="inline" method="post" action="/aufgaben/test">{hidden}<button class="ghost" type="submit">Jetzt im Testmodus ausführen</button></form>
<form class="inline" method="post" action="/aufgaben/{toggle[0]}">{hidden}<button class="ghost" type="submit">{toggle[1]}</button></form></section>""")
        runs = "".join(f"<li><span class=\"mono\">{html.escape(x['slot'])}</span> {html.escape(x['task'])} · "
                       f"<b>{html.escape(x['status'] or '')}</b> · {html.escape((x['message'] or '')[:120])}</li>"
                       for x in sch.last_runs(15)) or "<li>Noch keine Läufe.</li>"
        mode = ("<p class=\"notice\"><b>Testmodus:</b> Ergebnisse landen nur in <code>data/aufgaben-test/</code>. "
                "Keine Meldungen, keine Notizen, keine externen Aktionen. Umschalten auf „aktiv“ siehe docs/20.</p>"
                if sch.mode == "test" else
                "<p class=\"notice\"><b>Aktiv:</b> Ergebnisse werden als neue Notizen in 00_Inbox/JARVIS abgelegt. "
                "Externe Aktionen gibt es trotzdem nur über die Freigabezentrale.</p>")
        inner = f"""<header class="top"><div><p class="eyebrow">JARVIS · Automatisierung</p><h1>Aufgaben</h1></div></header>
{msg}{mode}
<p class="hint">Der Planer läuft nur, wenn <code>python3 -m jarvis aufgaben</code> gestartet ist (auf dem Server als Dienst). Notaus stoppt ihn sofort.</p>
{''.join(rows)}
<section class="panel"><h2>Letzte Läufe</h2><ul class="list">{runs}</ul></section>"""
        return Response(200, self._page("Aufgaben", inner, body_class="wide", session=session, active="aufgaben"))

    def _task_action(self, session, what: str, task_id: str) -> Response:
        from .scheduler import TaskError
        sch = self.jarvis.scheduler
        try:
            if what == "pause":
                sch.pause(task_id, via=f"web:{session.username}")
                session.data["flash_ok"] = "Aufgabe pausiert."
            elif what == "fortsetzen":
                sch.resume(task_id, via=f"web:{session.username}")
                session.data["flash_ok"] = "Aufgabe läuft wieder nach Plan."
            else:
                if self.jarvis.kill.is_active():
                    raise TaskError("Notabschaltung aktiv.")
                r = sch.run_now(task_id)
                if r["status"] == "erledigt":
                    session.data["task_result"] = r.get("text", "")[:8000]
                    session.data["flash_ok"] = f"Testlauf erledigt ({r['message']})."
                else:
                    session.data["flash"] = f"Testlauf fehlgeschlagen: {r['message']}"
        except TaskError as exc:
            session.data["flash"] = str(exc)
        return redirect("/aufgaben")


class WebApp(ApprovalPages, SkillPages, TaskPages, BrainPages):
    def __init__(self, cfg: dict, auth: wa.AuthStore, jarvis=None, clock: Callable[[], float] = time.time):
        self.cfg = cfg
        self.port = int(cfg["web"]["port"])
        self.auth = auth
        self.jarvis = jarvis
        self.sessions = wa.SessionManager(idle_minutes=int(cfg["web"].get("session_minutes", 30)), clock=clock)
        self.nonces = LoginNonces(clock=clock)
        self.audit = auth.audit
        self.chat = None
        if jarvis is not None and not jarvis.gate.allowed_web_users and auth.is_configured():
            # Es gibt genau ein Browser-Konto: nur dieses darf im Browser entscheiden.
            jarvis.gate.allowed_web_users = {auth.username()}
        if jarvis is not None:
            self.chat = ChatService(jarvis, ChatStore(Path(cfg["data_dir"]) / "chat.db", clock=clock), clock=clock)

    def close(self) -> None:
        """Beim Beenden: alle Datenbanken sauber schließen."""
        self.auth.close()
        if self.chat is not None:
            self.chat.store.close()
        if self.jarvis is not None:
            self.jarvis.close()

    @staticmethod
    def error(status: int, text: str) -> Response:
        """Einfache Fehlerantwort, ebenfalls mit allen Sicherheits-Headern."""
        resp = Response(status, text, "text/plain; charset=utf-8")
        for k, v in wa.SECURITY_HEADERS.items():
            resp.headers.append((k, v))
        return resp

    # ------------------------------------------------------------------ Einstieg
    def handle(self, method: str, target: str, headers: dict, body: bytes = b"") -> Response:
        try:
            resp = self._handle(method.upper(), target, {k.lower(): v for k, v in headers.items()}, body)
        except Exception as exc:  # noqa: BLE001 – nie interne Details an den Browser geben
            try:
                self.audit.write("web_error", error=type(exc).__name__)
            except Exception:  # noqa: BLE001 – auch ein Protokollfehler darf den Server nicht stoppen
                pass
            resp = Response(500, "Interner Fehler. Details stehen im Protokoll.", "text/plain; charset=utf-8")
        for k, v in wa.SECURITY_HEADERS.items():
            resp.headers.append((k, v))
        return resp

    def _handle(self, method: str, target: str, headers: dict, body: bytes) -> Response:
        if not wa.host_allowed(headers.get("host"), self.port):
            self.audit.write("web_rejected", reason="host", host=str(headers.get("host"))[:80])
            return Response(400, "Ungültiger Host.", "text/plain; charset=utf-8")
        if len(body) > MAX_BODY:
            return Response(413, "Anfrage zu groß.", "text/plain; charset=utf-8")
        path = urlsplit(target).path
        if method == "POST" and not self._same_origin(headers):
            self.audit.write("web_rejected", reason="fremde Herkunft", origin=str(headers.get("origin"))[:80])
            return Response(403, "Anfrage von fremder Seite abgelehnt.", "text/plain; charset=utf-8")
        session = self.sessions.get(wa.read_cookie(headers.get("cookie")))
        try:
            form = parse_qs(body.decode("utf-8", "replace"), max_num_fields=10) if method == "POST" else {}
            parse_qs(urlsplit(target).query, max_num_fields=5)
        except ValueError:
            return Response(400, "Ungültige Anfrage (zu viele Felder).", "text/plain; charset=utf-8")
        field = lambda name: (form.get(name) or [""])[0]  # noqa: E731

        if method == "GET" and path.startswith("/static/"):
            return self._static(path[len("/static/"):])
        if path == "/login":
            if method == "GET":
                return redirect("/") if session else self._login_page()
            if method == "POST":
                return self._do_login(field("username"), field("password"), field("nonce"))
        if path == "/logout" and method == "POST":
            if not wa.check_csrf(session, field("csrf")):
                return Response(403, "Ungültiges Prüfzeichen.", "text/plain; charset=utf-8")
            self.sessions.destroy(session.id)
            self.audit.write("web_logout", username=session.username)
            return redirect("/login", [("Set-Cookie", wa.clear_cookie())])
        if path == "/notaus" and method == "POST":
            if not wa.check_csrf(session, field("csrf")):
                return Response(403, "Ungültiges Prüfzeichen.", "text/plain; charset=utf-8")
            if self.jarvis:
                self.jarvis.kill.activate("Browser")
                self.audit.write("killswitch_on", source="web", username=session.username)
            return redirect("/")
        if path == "/" and method == "GET":
            if not session:
                return redirect("/login")
            return self._home(session)
        if path in ("/gehirn", "/gehirn/notiz", "/gehirn/lektion", "/gehirn/daten"):
            if not session:
                return redirect("/login")
            if self.jarvis is None:
                return Response(503, self._page("Second Brain", "<p>Nicht verfügbar.</p>", session=session))
            if path == "/gehirn" and method == "GET":
                inner = self._brain_page(session, html.escape(session.csrf))
                return Response(200, self._page("Second Brain", inner, body_class="wide", session=session,
                                                active="gehirn"))
            if path == "/gehirn/daten" and method == "GET":
                from .web_brain import brain_data
                return Response(200, json.dumps(brain_data(self.jarvis.kb), ensure_ascii=False),
                                "application/json; charset=utf-8")
            if path == "/gehirn/lektion" and method == "POST":
                if not wa.check_csrf(session, field("csrf")):
                    return Response(403, "Ungültiges Prüfzeichen.", "text/plain; charset=utf-8")
                self._brain_lesson(session, field("text"))
                return redirect("/gehirn#lektion")
            if path == "/gehirn/notiz" and method == "POST":
                if not wa.check_csrf(session, field("csrf")):
                    return Response(403, "Ungültiges Prüfzeichen.", "text/plain; charset=utf-8")
                self._brain_capture(session, field("text"))
                return redirect("/gehirn")
            return Response(405, "Methode nicht erlaubt.", "text/plain; charset=utf-8")
        if path.startswith("/wissen"):
            if not session:
                return redirect("/login")
            if self.jarvis is None:
                return Response(503, self._page("Wissen", "<p>Nicht verfügbar.</p>", session=session))
            query = parse_qs(urlsplit(target).query, max_num_fields=5)
            q = lambda name: (query.get(name) or [""])[0]  # noqa: E731
            if path == "/wissen" and method == "GET":
                return self._knowledge_page(session, q("q"))
            if path == "/wissen/notiz" and method == "GET":
                return self._note_page(session, q("id"))
            if method == "POST":
                if not wa.check_csrf(session, field("csrf")):
                    return Response(403, "Ungültiges Prüfzeichen.", "text/plain; charset=utf-8")
                if path == "/wissen/entsperren":
                    return self._unlock(session, field("password"), field("weiter"))
                if path == "/wissen/sperren":
                    session.data.pop("private_until", None)
                    self.audit.write("knowledge_locked", username=session.username)
                    return redirect("/wissen")
                if path == "/wissen/profile":
                    created = create_missing_drafts(self.jarvis.vault, self.jarvis.kb)
                    self.audit.write("profiles_created", count=len(created))
                    session.data["flash_ok"] = (f"{len(created)} Profil-Entwürfe in 00_Inbox/JARVIS angelegt."
                                                if created else "Alle Bereiche haben bereits ein Profil.")
                    return redirect("/wissen#profile")
            return Response(404, self._page("Nicht gefunden", "<p>Diese Seite gibt es nicht.</p>", session=session))
        if path == "/chat/stimme" and method == "GET":
            if not session:
                return redirect("/login")
            query = parse_qs(urlsplit(target).query, max_num_fields=3)
            return self._chat_voice((query.get("id") or [""])[0])
        if path in ("/chat", "/chat/neu", "/chat/schwaerzen"):
            if not session:
                return redirect("/login")
            if self.chat is None:
                return Response(503, self._page("Chat", "<p>Der Chat ist nicht verfügbar.</p>", session=session))
            query = parse_qs(urlsplit(target).query, max_num_fields=5)
            if path == "/chat" and method == "GET":
                return self._chat_page(session, (query.get("g") or [""])[0],
                                       portal=(query.get("portal") or [""])[0] == "1")
            if method == "POST":
                if not wa.check_csrf(session, field("csrf")):
                    return Response(403, "Ungültiges Prüfzeichen.", "text/plain; charset=utf-8")
                if path == "/chat/schwaerzen":
                    return self._redact(session, field("id"), field("bestaetigt"))
                if path == "/chat/neu":
                    conv = self.chat.store.new_conversation()
                    session.data["conv"] = conv
                    return redirect(f"/chat?g={conv}")
                return self._chat_send(session, field("g"), field("text"))
        if path.startswith("/aufgaben"):
            if not session:
                return redirect("/login")
            if self.jarvis is None:
                return Response(503, self._page("Aufgaben", "<p>Nicht verfügbar.</p>", session=session))
            if path == "/aufgaben" and method == "GET":
                return self._tasks_page(session)
            if method == "POST" and path in ("/aufgaben/pause", "/aufgaben/fortsetzen", "/aufgaben/test"):
                if not wa.check_csrf(session, field("csrf")):
                    return Response(403, "Ungültiges Prüfzeichen.", "text/plain; charset=utf-8")
                return self._task_action(session, path.rsplit("/", 1)[1], field("task"))
            return Response(404, self._page("Nicht gefunden", "<p>Diese Seite gibt es nicht.</p>", session=session))
        if path.startswith("/skills"):
            if not session:
                return redirect("/login")
            if self.jarvis is None:
                return Response(503, self._page("Skills", "<p>Nicht verfügbar.</p>", session=session))
            if path == "/skills" and method == "GET":
                return self._skills_page(session)
            if method == "POST" and path in ("/skills/beantragen", "/skills/aus", "/skills/test"):
                if not wa.check_csrf(session, field("csrf")):
                    return Response(403, "Ungültiges Prüfzeichen.", "text/plain; charset=utf-8")
                return self._skill_action(session, path.rsplit("/", 1)[1], field("skill"), field("op"))
            return Response(404, self._page("Nicht gefunden", "<p>Diese Seite gibt es nicht.</p>", session=session))
        if path.startswith("/freigaben"):
            if not session:
                return redirect("/login")
            if self.jarvis is None:
                return Response(503, self._page("Freigaben", "<p>Nicht verfügbar.</p>", session=session))
            query = parse_qs(urlsplit(target).query, max_num_fields=5)
            if path == "/freigaben" and method == "GET":
                return self._approvals_page(session)
            if path == "/freigaben/aktion" and method == "GET":
                return self._action_page(session, (query.get("id") or [""])[0])
            if path == "/freigaben/protokoll" and method == "GET":
                return self._security_log_page(session)
            if path == "/freigaben/entscheiden" and method == "POST":
                if not wa.check_csrf(session, field("csrf")):
                    return Response(403, "Ungültiges Prüfzeichen.", "text/plain; charset=utf-8")
                return self._decide(session, field("id"), field("d"), field("t"), field("h"),
                                    field("password"), field("geprueft"))
            return Response(404, self._page("Nicht gefunden", "<p>Diese Seite gibt es nicht.</p>", session=session))
        if method not in ("GET", "POST"):
            return Response(405, "Methode nicht erlaubt.", "text/plain; charset=utf-8", [("Allow", "GET, POST")])
        return Response(404, self._page("Nicht gefunden", "<p>Diese Seite gibt es nicht.</p>"))

    def _same_origin(self, headers: dict) -> bool:
        if headers.get("sec-fetch-site") not in (None, "same-origin", "none"):
            return False
        origin = headers.get("origin")
        if origin is None:     # ältere Browser senden manchmal keinen Origin; Host ist bereits geprüft
            return True
        return origin.lower() in {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}",
                                  f"http://[::1]:{self.port}"}

    # ------------------------------------------------------------------ Seiten
    def _static(self, name: str) -> Response:
        allowed = {"jarvis.css": "text/css; charset=utf-8", "brain.js": "text/javascript; charset=utf-8",
                   "chat.js": "text/javascript; charset=utf-8",
                   "hud.js": "text/javascript; charset=utf-8"}
        if name not in allowed:
            return Response(404, "Nicht gefunden.", "text/plain; charset=utf-8")
        resp = Response(200, (STATIC_DIR / name).read_bytes(), allowed[name])
        return resp

    def _page(self, title: str, inner: str, body_class: str = "", session: wa.Session | None = None,
              active: str = "") -> str:
        nav = ""
        if session is not None:
            links = [("/", "Übersicht", "home"), ("/chat?portal=1", "Chat", "chat"), ("/gehirn", "Second Brain", "gehirn"),
                     ("/wissen", "Wissen", "wissen"),
                     ("/freigaben", "Freigaben", "freigaben"), ("/skills", "Skills", "skills"),
                     ("/aufgaben", "Aufgaben", "aufgaben")]
            nav = ("<nav class=\"nav\" aria-label=\"Hauptmenü\"><span class=\"brand\">" + hud_reactor() + "JARVIS</span>"
                   + "".join(f"<a href=\"{href}\"{CURRENT if key == active else ''}>{label}</a>"
                             for href, label, key in links)
                   + f"<form method=\"post\" action=\"/logout\"><input type=\"hidden\" name=\"csrf\" "
                     f"value=\"{html.escape(session.csrf)}\"><button class=\"ghost\" type=\"submit\">Abmelden</button></form></nav>")
        return (f"<!doctype html><html lang=\"de\"><head><meta charset=\"utf-8\">"
                f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                f"<title>{html.escape(title)} · JARVIS</title><link rel=\"stylesheet\" href=\"/static/jarvis.css\">"
                f"</head><body class=\"{body_class}\">{PORTAL if 'portal-on' in body_class.split() else ''}"
                f"{nav}<main class=\"wrap\">{inner}</main></body></html>")

    def _login_page(self, error: str = "") -> Response:
        if not self.auth.is_configured():
            inner = ("<section class=\"panel login\"><p class=\"eyebrow\">JARVIS · Zugang</p><h1>Noch kein Passwort</h1>"
                     "<p>Lege zuerst im Terminal ein Passwort fest:</p><pre>python3 -m jarvis web-passwort</pre></section>")
            return Response(200, self._page("Einrichtung", inner, "center"))
        err = f"<p class=\"error\" role=\"alert\">{html.escape(error)}</p>" if error else ""
        inner = f"""<section class="panel login">
<p class="eyebrow"><span class="dot"></span>JARVIS · Gesicherter Zugang</p>
<h1>Anmelden</h1>
{err}
<form method="post" action="/login" autocomplete="on">
<input type="hidden" name="nonce" value="{self.nonces.issue()}">
<label for="username">Benutzername</label>
<input id="username" name="username" autocomplete="username" required maxlength="64" autofocus>
<label for="password">Passwort</label>
<input id="password" name="password" type="password" autocomplete="current-password" required maxlength="256">
<button type="submit">Anmelden</button>
</form>
<p class="hint">Nur auf diesem Rechner erreichbar · Abmeldung nach {int(self.cfg['web'].get('session_minutes', 30))} Min. ohne Aktivität</p>
</section>"""
        return Response(200 if not error else 401, self._page("Anmelden", inner, "center"))

    def _do_login(self, username: str, password: str, nonce: str) -> Response:
        if not self.nonces.consume(nonce):
            return self._login_page("Das Formular ist abgelaufen. Bitte erneut anmelden.")
        try:
            ok = self.auth.login(username, password)
        except wa.AuthError as exc:
            return self._login_page(str(exc))
        if not ok:
            # Absichtlich allgemein: verrät nicht, ob Name oder Passwort falsch war
            return self._login_page("Benutzername oder Passwort ist falsch.")
        s = self.sessions.create(username)
        return redirect("/", [("Set-Cookie", wa.session_cookie(s.id, self.sessions.idle))])

    def _home(self, session: wa.Session) -> Response:
        j = self.jarvis
        kill = j.kill.is_active() if j else False
        pending = len(j.gate.pending()) if j else 0
        budget = html.escape(j.budget.status()) if j else "–"
        msgs = j.notifier.history(limit=5) if j else []
        items = "".join(f"<li><span class=\"mono\">{time.strftime('%d.%m. %H:%M', time.localtime(m['ts']))}</span> "
                        f"{html.escape(m['text'].splitlines()[0][:140])}</li>" for m in msgs) or "<li>Noch keine Meldungen.</li>"
        csrf = html.escape(session.csrf)
        n_withheld = len(self.chat.affected_messages()) if self.chat else 0
        withheld_pill = (f"<a class=\"pill warn\" href=\"/chat\">Zurückgehaltene Chat-Antworten <b>{n_withheld}</b></a>"
                         if n_withheld else "")
        model = getattr(j.llm, "model", None) if j else None
        core = ("Testmodus (kein echtes Modell)" if model is None or getattr(model, "is_test_mode", True)
                else str(getattr(model, "name", "?")))
        notes = j.kb.stats().get("visible", 0) if j else 0
        tasks = len(j.kb.open_checkboxes(limit=99)) if j else 0
        hour = time.localtime().tm_hour
        greet = "Guten Morgen" if 5 <= hour < 11 else "Guten Tag" if hour < 18 else "Guten Abend"
        lessons_n = 0
        if j:
            from .lessons import lessons as _lessons
            lessons_n = len(_lessons(j.kb))
        month_pct = 0
        if j and j.budget.monthly > 0:
            month_pct = max(0, min(100, int(round(100 * j.budget.spent_month() / j.budget.monthly))))
        bars = [("Notizen", notes), ("Aufgaben", tasks), ("Lektionen", lessons_n), ("Freigaben", pending)]
        top = max([v for _, v in bars] + [1])
        bars_html = "".join(f'<div class="bar"><i class="lv{_lv(max(6, 100 * v / top))}"></i><span>{html.escape(n)}</span>'
                            f'<b>{v}</b></div>' for n, v in bars)
        inner = f"""<section class="poster" aria-label="JARVIS Systemübersicht">
<p class="poster-kicker">Deine Welt · Deine Stimme · Eine Intelligenz</p>
<h1 class="poster-title" aria-label="JARVIS">JARVIS</h1>
<p class="poster-sub">Dein persönlicher KI-Assistent</p>
<p class="poster-tag">Denkt · Versteht · Hilft — <b>{greet}. Willkommen zurück.</b></p>
<div class="poster-grid">
<aside class="poster-side">
<div class="hud-card"><span class="hc-t">Systemstatus</span><div class="wave" aria-hidden="true">{'<i></i>' * 18}</div><b class="{'alert' if kill else 'ok'}">{'NOTAUS AKTIV' if kill else 'ONLINE'}</b></div>
<div class="hud-card"><span class="hc-t">KI-Kern</span><b>{html.escape(core)}</b></div>
<div class="hud-card"><span class="hc-t">Budget diesen Monat</span><div class="meter"><i class="lv{_lv(month_pct)}"></i></div><b>{month_pct} %</b><small>{budget}</small></div>
</aside>
<div class="poster-core hud-globe orb"><div class="orb-ring r1"></div><div class="orb-ring r2"></div><div class="orb-ring r3"></div>
<canvas class="hud-canvas" data-hud="sphere" data-label="JARVIS" aria-label="Datenkugel – mit dem Touchpad drehen und zoomen"></canvas>
<div class="hud-fallback">{hud_globe()}</div>
<p class="core-hint">Wischen: drehen · Pinch: zoomen · Klick: Steuerung halten</p></div>
<aside class="poster-side">
<div class="hud-card"><span class="hc-t">Aktiv</span><div class="ring-ico" aria-hidden="true"><i></i><i></i></div><b>{'gesperrt' if kill else 'bereit'}</b></div>
<div class="hud-card"><span class="hc-t">Alle Systeme</span><div class="bars">{bars_html}</div></div>
<a class="button" href="/chat?portal=1">Chat öffnen</a>
</aside></div>
<blockquote class="poster-quote">„Die Zukunft kommt nicht von allein. <b>Du baust sie.</b>“</blockquote>
</section>
<section class="features" aria-label="Fähigkeiten">
<div><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg><b>Sprache</b><span>Diktieren mit fn fn · JARVIS spricht</span></div>
<div><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 3 5 3 3 0 0 0 5 1V4.5A2.5 2.5 0 0 0 9 4zM15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-3 5 3 3 0 0 1-5 1"/></svg><b>Intelligenz</b><span>Claude · geprüfte Antworten</span></div>
<div><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 11l8-7 8 7v9H4z"/><path d="M10 20v-5h4v5"/></svg><b>Automatisieren</b><span>Aufgabenplaner · Briefings</span></div>
<div><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><rect x="9" y="11" width="6" height="5" rx="1"/><path d="M10 11V9a2 2 0 0 1 4 0v2"/></svg><b>Sicher &amp; privat</b><span>Freigaben · Notaus · Kostenbremse</span></div>
<div><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4c3 0 6 3 6 6l-6 6-4-4z"/><path d="M10 12l-4 1-2 4 4-1M12 14l-1 4 4-2 1-4"/></svg><b>Lernt dazu</b><span>Lektionen · Second Brain</span></div>
</section>
<section class="tiles" aria-label="Schnellzugriff">
<a class="tile" href="/gehirn"><span class="t-icon">◎</span><b>Second Brain</b><span>{notes} Notizen · {tasks} Aufgaben</span></a>
<a class="tile" href="/chat?portal=1"><span class="t-icon">◈</span><b>Chat</b><span>Mit JARVIS sprechen</span></a>
<a class="tile {'warn' if pending else ''}" href="/freigaben"><span class="t-icon">◆</span><b>Freigaben</b><span>{pending} offen</span></a>
<a class="tile" href="/aufgaben"><span class="t-icon">◇</span><b>Aufgaben</b><span>Planer &amp; Läufe</span></a>
</section>
{('<section class="pills">' + withheld_pill + '</section>') if withheld_pill else ''}
<section class="flow" aria-label="So arbeitet JARVIS"><h2>So arbeitet JARVIS</h2><ol>
<li><b>Deine Frage</b><span>Tippen oder diktieren</span></li><li><b>KI-Gehirn</b><span>Claude mit deinem Wissen</span></li>
<li><b>Prüfung</b><span>Antwort + Referenzen</span></li><li><b>Freigabe</b><span>nur bei Aktionen nach außen</span></li>
<li><b>Stimme</b><span>JARVIS spricht</span></li></ol></section>
<section class="panel"><h2>Letzte Meldungen</h2><ul class="list">{items}</ul></section>
<section class="panel muted"><h2>Freigabezentrale</h2><p>Alles, was JARVIS nach außen tun oder verändern möchte, wartet unter <a href="/freigaben">Freigaben</a> auf deine Entscheidung. Nichts wird automatisch genehmigt.</p></section>
<section class="panel danger"><h2>Notabschaltung</h2><p>Stoppt sofort alle Aktionen. Aufheben nur im Terminal mit <code>python3 -m jarvis resume</code>.</p>
<form method="post" action="/notaus"><input type="hidden" name="csrf" value="{csrf}"><button class="stop" type="submit" {'disabled' if kill else ''}>Notaus auslösen</button></form></section>"""
        inner += '<script src="/static/hud.js" defer></script>'
        return Response(200, self._page("Übersicht", inner, body_class="wide", session=session, active="home"))

    # ------------------------------------------------------------------ Chat
    def _chat_send(self, session: wa.Session, conv: str, text: str) -> Response:
        if not self.chat.store.exists(conv):
            return Response(404, self._page("Chat", "<p>Dieses Gespräch gibt es nicht.</p>", session=session))
        try:
            self.chat.send(conv, text, rate_key=session.username)
        except ChatError as exc:
            session.data["flash"] = str(exc)
            session.data["draft"] = text[:MAX_MESSAGE_CHARS]
        session.data["conv"] = conv
        return redirect(f"/chat?g={conv}#ende")

    def _sources_html(self, sources: list) -> str:
        """Quellen unter einer Antwort. Wird bei JEDER Anzeige neu geprüft: Ist eine Notiz inzwischen
        vertraulich oder gelöscht, erscheint sie nicht mehr als Link."""
        if not sources:
            return ""
        items = []
        for s in sources:
            sid = str(s.get("id", ""))
            if self.jarvis is not None and self.jarvis.kb.is_shareable(sid):
                note = self.jarvis.kb.get(sid)
                items.append(f"<li><a href=\"/wissen/notiz?id={sid}\">{html.escape(note.title)}</a></li>")
            else:
                items.append("<li class=\"muted\">Quelle nicht mehr verfügbar</li>")
        return f"<div class=\"sources\"><p>Quellen</p><ul>{''.join(items)}</ul></div>"

    # ------------------------------------------------------------------ Wissen
    def _private_unlocked(self, session: wa.Session) -> bool:
        until = session.data.get("private_until", 0)
        return bool(until) and self.sessions.clock() < until

    def _unlock(self, session: wa.Session, password: str, weiter: str) -> Response:
        # Nur exakt diese Ziele erlaubt: verhindert Umleitung auf fremde Seiten und eingeschleuste Header (\r\n)
        target = weiter if SAFE_RETURN.fullmatch(weiter or "") else "/wissen"
        try:
            ok = self.auth.login(session.username, password)    # zählt auch für die Sperre nach Fehlversuchen
        except wa.AuthError as exc:
            session.data["flash"] = str(exc)
            return redirect(target)
        if not ok:
            session.data["flash"] = "Passwort falsch. Vertrauliche Notizen bleiben ausgeblendet."
            return redirect(target)
        session.data["private_until"] = self.sessions.clock() + UNLOCK_SECONDS
        self.audit.write("knowledge_unlocked", username=session.username, minutes=UNLOCK_SECONDS // 60)
        return redirect(target)

    def _unlock_box(self, session: wa.Session, weiter: str = "/wissen") -> str:
        csrf = html.escape(session.csrf)
        if self._private_unlocked(session):
            left = int((session.data["private_until"] - self.sessions.clock()) // 60) + 1
            return (f"<form class=\"inline\" method=\"post\" action=\"/wissen/sperren\"><input type=\"hidden\" "
                    f"name=\"csrf\" value=\"{csrf}\"><span class=\"pill warn\">Vertrauliche sichtbar <b>noch {left} Min.</b>"
                    f"</span> <button class=\"ghost\" type=\"submit\">Wieder ausblenden</button></form>")
        return (f"<details class=\"unlock\"><summary>Vertrauliche Notizen einblenden</summary>"
                f"<form method=\"post\" action=\"/wissen/entsperren\"><input type=\"hidden\" name=\"csrf\" value=\"{csrf}\">"
                f"<input type=\"hidden\" name=\"weiter\" value=\"{html.escape(weiter)}\">"
                f"<label for=\"pw\">Passwort zur Bestätigung (gilt {UNLOCK_SECONDS // 60} Minuten)</label>"
                f"<input id=\"pw\" name=\"password\" type=\"password\" autocomplete=\"current-password\" required maxlength=\"256\">"
                f"<button type=\"submit\">Einblenden</button></form></details>")

    @staticmethod
    def _highlight(snippet: str, query: str) -> str:
        from .knowledge import tokens
        out = html.escape(snippet)
        for t in sorted(set(tokens(query)), key=len, reverse=True)[:8]:
            out = re.sub("(" + re.escape(html.escape(t)) + ")", r"<mark>\1</mark>", out, flags=re.I)
        return out

    def _knowledge_page(self, session: wa.Session, query: str) -> Response:
        kb = self.jarvis.kb
        query = query[:200]
        unlocked = self._private_unlocked(session)
        st = kb.stats()
        flash = session.data.pop("flash", "")
        ok = session.data.pop("flash_ok", "")
        csrf = html.escape(session.csrf)
        msg = (f"<p class=\"error\" role=\"alert\">{html.escape(flash)}</p>" if flash else "") + \
              (f"<p class=\"success\" role=\"status\">{html.escape(ok)}</p>" if ok else "")
        if query:
            hits = kb.search(query, include_confidential=unlocked, limit=30)
            rows = "".join(
                f"<li><a href=\"/wissen/notiz?id={h['note'].id}\">{html.escape(h['note'].title)}</a>"
                f"{' <span class=badge>VERTRAULICH</span>' if h['note'].confidential else ''}"
                f"<span class=\"mono\">{html.escape(h['note'].relpath)}</span>"
                f"<p>{self._highlight(h['snippet'], query)}</p></li>" for h in hits) or "<li>Keine Treffer.</li>"
            results = f"<section class=\"panel\"><h2>Treffer für „{html.escape(query)}“</h2><ul class=\"list hits\">{rows}</ul></section>"
        else:
            recent = kb.recent(10, include_confidential=unlocked)   # jede Notiz auf aktuellem Stand geprüft
            rows = "".join(
                f"<li><a href=\"/wissen/notiz?id={n.id}\">{html.escape(n.title)}</a>"
                f"{' <span class=badge>VERTRAULICH</span>' if n.confidential else ''}"
                f"<span class=\"mono\">{html.escape(n.relpath)} · {time.strftime('%d.%m.%Y', time.localtime(n.mtime))}</span></li>"
                for n in recent) or "<li>Noch keine Notizen.</li>"
            results = f"<section class=\"panel\"><h2>Zuletzt geändert</h2><ul class=\"list hits\">{rows}</ul></section>"
        folders = "".join(f"<li><span>{html.escape(f)}</span><span class=\"mono\">{c}</span></li>"
                          for f, c in st["folders"].items()) or "<li>Leer</li>"
        states = {"fehlt": ("○", ""), "Entwurf": ("◐", "warn"), "übernommen": ("●", "ok")}
        prof_rows = ""
        for e in profile_status(kb):
            p, (icon, cls) = e["project"], states[e["state"]]
            link = (f"<a href=\"/wissen/notiz?id={e['note'].id}\">{icon} {e['state']}</a>"
                    if e["note"] is not None and kb.is_shareable(e["note"].id) else f"{icon} {e['state']}")
            prof_rows += (f"<tr><td>{html.escape(p['name'])}</td><td><span class=\"pill {('ok' if p['status'] == 'aktiv' else '')}\">"
                          f"<b>{html.escape(p['status'])}</b></span></td><td class=\"{cls}\">{link}</td></tr>")
        hidden = st["confidential"]
        hidden_note = (f"<p class=\"hint\">{hidden} vertrauliche Notiz(en) ausgeblendet.</p>" if hidden and not unlocked else "")
        skipped = sum(st["skipped"].values())
        skipped_note = (f"<p class=\"hint\">{skipped} Datei(en) übersprungen (zu groß, Verknüpfung oder Limit).</p>"
                        if skipped else "")
        inner = f"""<header class="top"><div><p class="eyebrow">JARVIS · Business-Gedächtnis</p><h1>Wissen</h1></div>
{self._unlock_box(session)}</header>
{msg}
<form class="search" method="get" action="/wissen" role="search">
<label for="q" class="sr">Suche</label>
<input id="q" name="q" value="{html.escape(query)}" maxlength="200" placeholder="Notizen durchsuchen, z. B. Scent Edit Instagram">
<button type="submit">Suchen</button></form>
<section class="pills" aria-label="Wissensstand"><span class="pill">Notizen <b>{st['visible']}</b></span>
<span class="pill {'warn' if hidden else ''}">Vertraulich <b>{hidden}</b></span>
<span class="pill">Nur lesen <b>data/vault</b></span></section>
{hidden_note}{skipped_note}
<div class="chat-layout"><div class="stack">{results}
<section class="panel" id="profile"><h2>Geschäftsbereiche</h2>
<div class="md-table"><table><thead><tr><th>Bereich</th><th>Status</th><th>Profil</th></tr></thead><tbody>{prof_rows}</tbody></table></div>
<p class="hint">Status laut deinem Profil. ● übernommen · ◐ Entwurf in der Inbox · ○ fehlt</p>
<form method="post" action="/wissen/profile"><input type="hidden" name="csrf" value="{csrf}">
<button class="ghost" type="submit">Fehlende Profil-Entwürfe anlegen</button></form>
<p class="hint">Legt nur neue Dateien in 00_Inbox/JARVIS an. Du prüfst sie und verschiebst sie selbst nach 02_Projekte.</p></section>
</div><aside class="panel convs"><h2>Ordner</h2><ul class="list folders">{folders}</ul></aside></div>"""
        return Response(200, self._page("Wissen", inner, body_class="wide", session=session, active="wissen"))

    def _note_page(self, session: wa.Session, note_id: str) -> Response:
        kb = self.jarvis.kb
        unlocked = self._private_unlocked(session)
        note = kb.get(note_id, include_confidential=True)
        if note is None:
            return Response(404, self._page("Wissen", "<section class=\"panel\"><h2>Nicht gefunden</h2><p>Diese Notiz "
                                            "gibt es nicht.</p><p><a href=\"/wissen\">Zur Übersicht</a></p></section>",
                                            session=session, active="wissen"))
        if note.confidential and not unlocked:
            self.audit.write("knowledge_blocked", id=note.id)
            inner = (f"<section class=\"panel\"><h2>Vertrauliche Notiz</h2><p>Diese Notiz ist als vertraulich "
                     f"eingestuft. Zum Anzeigen bitte mit deinem Passwort bestätigen.</p>"
                     f"{self._unlock_box(session, '/wissen/notiz?id=' + note.id)}</section>")
            return Response(403, self._page("Vertraulich", inner, session=session, active="wissen"))
        flash = session.data.pop("flash", "")
        badge = ""
        if note.confidential:
            badge = ("<p class=\"notice\"><b>Vertraulich:</b> " + html.escape(", ".join(note.reasons)) +
                     ". Wird nie als Chat-Kontext oder Quelle verwendet.</p>")
            self.audit.write("knowledge_view_confidential", id=note.id)
        err = f"<p class=\"error\" role=\"alert\">{html.escape(flash)}</p>" if flash else ""
        inner = f"""<p class="crumb"><a href="/wissen">Wissen</a> / <span class="mono">{html.escape(note.relpath)}</span></p>
{err}{badge}
<article class="panel note">{render_markdown(note.text)}</article>
<p class="hint">Nur lesen. Änderungen machst du in Obsidian. Zuletzt geändert: {time.strftime('%d.%m.%Y %H:%M', time.localtime(note.mtime))}</p>"""
        return Response(200, self._page(note.title, inner, body_class="wide", session=session, active="wissen"))

    def _redact_form(self, session: wa.Session, msg_id: int) -> str:
        return (f"<form class=\"redact\" method=\"post\" action=\"/chat/schwaerzen\">"
                f"<input type=\"hidden\" name=\"csrf\" value=\"{html.escape(session.csrf)}\">"
                f"<input type=\"hidden\" name=\"id\" value=\"{int(msg_id)}\">"
                f"<label><input type=\"checkbox\" name=\"bestaetigt\" value=\"ja\" required> Ich möchte den Text dieser "
                f"Antwort endgültig schwärzen. Das kann nicht rückgängig gemacht werden.</label>"
                f"<button class=\"stop\" type=\"submit\">Endgültig schwärzen</button></form>")

    def _redact(self, session: wa.Session, msg_id: str, confirmed: str) -> Response:
        """Schwärzen NUR auf ausdrücklichen Wunsch: entsperrt (Passwort ≤ 10 Min.), Häkchen gesetzt,
        Antwort tatsächlich betroffen. Alles andere wird abgelehnt."""
        msg = self.chat.store.get_message(int(msg_id)) if msg_id.isdigit() else None
        target = f"/chat?g={msg['conv']}" if msg else "/chat"
        if msg is None:
            return Response(404, self._page("Chat", "<p>Diese Nachricht gibt es nicht.</p>", session=session))
        if not self._private_unlocked(session):
            session.data["flash"] = "Zum Schwärzen bitte zuerst mit deinem Passwort bestätigen."
            return redirect(target)
        if confirmed != "ja":
            session.data["flash"] = "Nicht geschwärzt: Das Bestätigungs-Häkchen fehlte."
            return redirect(target)
        if not self.chat.withheld_reason(msg):
            session.data["flash"] = "Diese Antwort ist nicht betroffen und wurde nicht verändert."
            return redirect(target)
        if self.chat.store.redact(msg["id"], self.sessions.clock()):
            self.audit.write("chat_redacted", msg_id=msg["id"], conv=msg["conv"], username=session.username)
            session.data["flash_ok"] = "Antwort endgültig geschwärzt."
        return redirect(target)

    def _chat_voice(self, msg_id: str) -> Response:
        """Version 5.3: JARVIS-Antwort als Sprache (Mac-Stimme + Effekt, lokal). Nur eigene, sichtbare Antworten."""
        from .chat import strip_check
        from .speech import speakable
        from .voice_fx import VoiceUnavailable, jarvis_voice
        if self.chat is None or self.jarvis is None or not str(msg_id).isdigit() or len(str(msg_id)) > 9:
            return Response(404, "Nicht gefunden.", "text/plain; charset=utf-8")
        if self.jarvis.kill.is_active():
            return Response(423, "Notabschaltung aktiv.", "text/plain; charset=utf-8")
        m = self.chat.store.get_message(int(msg_id))
        if not m or m["role"] != ROLE_JARVIS or self.chat.withheld_reason(m) is not None:
            return Response(404, "Nicht gefunden.", "text/plain; charset=utf-8")
        try:
            audio = jarvis_voice(speakable(strip_check(m["text"]), max_chars=2500))
        except VoiceUnavailable as exc:
            return Response(501, str(exc), "text/plain; charset=utf-8")
        self.audit.write("voice_spoken", msg=int(msg_id), bytes=len(audio))
        return Response(200, audio, "audio/wav")

    def _chat_page(self, session: wa.Session, requested: str, portal: bool = False) -> Response:
        store = self.chat.store
        if requested:
            if not store.exists(requested):     # auch Schutz gegen ../-Tricks: nur 12 Hex-Zeichen erlaubt
                return Response(404, self._page("Chat", "<section class=\"panel\"><h2>Nicht gefunden</h2>"
                                                "<p>Dieses Gespräch gibt es nicht.</p><p><a href=\"/chat\">Zum Chat</a></p>"
                                                "</section>", session=session, active="chat"))
            conv = requested
        else:
            conv = session.data.get("conv") if store.exists(session.data.get("conv")) else store.latest()
            if not conv:
                conv = store.new_conversation()
        session.data["conv"] = conv
        flash = session.data.pop("flash", "")
        draft = session.data.pop("draft", "")
        csrf = html.escape(session.csrf)
        msgs = store.history(conv, 200)
        labels = {ROLE_USER: "Du", ROLE_JARVIS: "JARVIS", ROLE_SYSTEM: "System"}
        parts = []
        withheld = 0
        for m in msgs:
            when = time.strftime("%d.%m. %H:%M", time.localtime(m["ts"]))
            badge = "<span class=\"badge\">TESTMODUS</span>" if m["mode"] == "test" else ""
            reason = self.chat.withheld_reason(m) if m["role"] != ROLE_USER else None
            if m["role"] == ROLE_USER:
                body = "<p>" + html.escape(m["text"]).replace("\n", "<br>") + "</p>"
            elif reason and not self._private_unlocked(session):
                withheld += 1
                body = (f"<p class=\"withheld\"><b>Antwort zurückgehalten:</b> {html.escape(reason)}. Sie wird nicht "
                        f"angezeigt und nicht mehr an die KI weitergegeben. Nichts wurde gelöscht.</p>")
            else:
                body = render_markdown(m["text"])
                if reason:
                    withheld += 1
                    body = (f"<p class=\"withheld\"><b>Zurückgehalten</b> ({html.escape(reason)}). Nur für dich sichtbar, "
                            f"weil du entsperrt hast.</p>" + body + self._redact_form(session, m["id"]))
            body += self._sources_html(m.get("sources") or [])
            fresh = (m is msgs[-1] and m["role"] == ROLE_JARVIS and time.time() - m["ts"] < 120)
            speak = (f"<button class=\"speak ghost\" type=\"button\" data-id=\"{int(m['id'])}\" hidden "
                     f"aria-label=\"Antwort vorlesen\">🔊 Vorlesen</button>"
                     if m["role"] == ROLE_JARVIS and not (reason and not self._private_unlocked(session)) else "")
            label = {ROLE_USER: "Frage", ROLE_JARVIS: "JARVIS · Antwort"}.get(m["role"], labels.get(m["role"], "System"))
            parts.append(f"<article class=\"msg msg-{html.escape(m['role'])}{' fresh' if fresh else ''}\" "
                         f"data-id=\"{int(m['id'])}\"><p class=\"meta\">"
                         f"<b>{label}</b> <span class=\"mono\">{when}</span>{badge}{speak}</p>"
                         f"<div class=\"body\">{body}</div></article>")
        if not parts:
            parts.append("<p class=\"empty\">Noch keine Nachrichten. Schreib JARVIS etwas, zum Beispiel "
                         "<code>/hilfe</code> oder eine Frage zu einem deiner Geschäftsbereiche.</p>")
        convs = store.conversations(8)
        side = "".join(
            f"<li><a href=\"/chat?g={c['id']}\"{CURRENT if c['id'] == conv else ''}>"
            f"{html.escape(c['title'][:48])}{'…' if len(c['title']) > 48 else ''}</a>"
            f"<span class=\"mono\">{c['count']} Nachr.</span></li>" for c in convs)
        banner = ""
        if self.chat.test_mode:
            banner = ("<p class=\"notice\"><b>Testmodus:</b> Es ist noch kein KI-Zugang eingerichtet. JARVIS antwortet "
                      "mit Platzhaltern, Befehle wie <code>/idee</code> oder <code>/suche</code> funktionieren aber schon. "
                      "Es entstehen keine Kosten.</p>")
        err = f"<p class=\"error\" role=\"alert\">{html.escape(flash)}</p>" if flash else ""
        ok_msg = session.data.pop("flash_ok", "")
        if ok_msg:
            err += f"<p class=\"success\" role=\"status\">{html.escape(ok_msg)}</p>"
        if withheld:
            banner += (f"<div class=\"notice\"><p><b>{withheld} Antwort(en) zurückgehalten</b>, weil sich ihre Quellen geändert "
                       f"haben. Zum Ansehen oder endgültigen Schwärzen mit Passwort bestätigen.</p>"
                       f"{self._unlock_box(session, '/chat?g=' + conv)}</div>")
        inner = f"""<header class="top hud-chat"><div class="hud-mini">{hud_globe("globe mini", "JARVIS aktiv")}</div><div class="hud-title"><p class="eyebrow"><span class="live"></span>JARVIS · Live</p><h1>Frag JARVIS</h1>
<div class="voicebar" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div></div>
<label class="autovoice" hidden><input type="checkbox" id="autovoice"> Antworten automatisch sprechen</label>
<form method="post" action="/chat/neu"><input type="hidden" name="csrf" value="{csrf}"><button class="ghost" type="submit">Neues Gespräch</button></form></header>
{banner}
<div class="chat-layout">
<section class="chat" aria-label="Gesprächsverlauf">{''.join(parts)}<div id="ende"></div>
{err}
<form class="composer" method="post" action="/chat">
<input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="g" value="{conv}">
<label for="text">Deine Nachricht</label>
<textarea id="text" name="text" rows="3" maxlength="{MAX_MESSAGE_CHARS}" required autofocus placeholder="Frag JARVIS etwas … oder /hilfe">{html.escape(draft)}</textarea>
<button type="submit">Senden</button>
</form></section>
<aside class="panel convs" aria-label="Letzte Gespräche"><h2>Letzte Gespräche</h2><ul class="list">{side}</ul></aside>
</div>"""
        inner += ('<div class="thinking" aria-live="polite" hidden><div class="t-orb"><i></i><i></i><i></i></div>'
                  '<canvas class="t-swirl" data-hud="swirl" aria-hidden="true"></canvas>'
                  '<p>JARVIS denkt nach <span>· Antwort wird geprüft</span></p></div>'
                  '<script src="/static/hud.js" defer></script><script src="/static/chat.js" defer></script>')
        return Response(200, self._page("Chat", inner, body_class="wide chat-doc" + (" portal-on" if portal else ""),
                                        session=session, active="chat"))


# ---------------------------------------------------------------------- Server
def make_handler(app: WebApp):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        timeout = 30          # Verbindungen ohne Aktivität werden nach 30 s geschlossen (Schutz vor „Hängern“)

        def version_string(self):  # keine Python- oder Versionsangaben nach außen
            return "JARVIS"

        def _serve(self, method: str) -> None:
            raw = (self.headers.get("Content-Length") or "0").strip()
            if not raw.isdigit() or self.headers.get("Transfer-Encoding"):
                # nicht-numerisch, negativ oder „chunked“: ablehnen statt abzustürzen oder ewig zu warten
                self.close_connection = True
                resp = app.error(400, "Ungültige Anfrage.")
            else:
                length = int(raw)
                if length > MAX_BODY:
                    body = b"x" * (MAX_BODY + 1)      # führt zu 413, ohne den Rest zu lesen
                    self.close_connection = True
                else:
                    body = self.rfile.read(length) if length else b""
                resp = app.handle(method, self.path, dict(self.headers.items()), body)
            self.send_response(resp.status)
            for k, v in resp.headers:
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(resp.body)))
            self.end_headers()
            self.wfile.write(resp.body)

        def do_GET(self):  # noqa: N802
            self._serve("GET")

        def do_POST(self):  # noqa: N802
            self._serve("POST")

        def log_message(self, fmt, *args):  # nur Methode, Pfad ohne Parameter, Status
            if getattr(app, "quiet", False):
                return
            print(f"[web] {self.command} {urlsplit(self.path).path} → {args[1] if len(args) > 1 else ''}")

    return Handler


def serve(app: WebApp, host: str) -> None:
    if host not in LOCAL_HOSTS:
        raise SystemExit("Die Oberfläche darf in Phase 2 nur lokal (127.0.0.1) laufen.")
    httpd = ThreadingHTTPServer((host, app.port), make_handler(app))
    httpd.daemon_threads = True
    from .server import install_stop_handler
    install_stop_handler(httpd.shutdown)     # Version 5: systemd-Stopp (SIGTERM) beendet geordnet
    # flush: Meldung sofort ausgeben, auch wenn die Ausgabe in eine Datei oder Pipe geht (systemd, Tests)
    print(f"JARVIS läuft. Öffne in Firefox:  http://127.0.0.1:{app.port}", flush=True)
    print("Beenden mit Strg+C (ctrl + C).", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        app.close()
        print("\nJARVIS-Oberfläche beendet. Alle Sitzungen sind abgemeldet, Datenbanken geschlossen.", flush=True)
