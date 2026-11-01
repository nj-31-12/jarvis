"""Stand 23: Sprach-Ansicht (/stimme) und Auftrags-Zentrale (/auftraege).

/stimme     Knopf drücken → sprechen → JARVIS antwortet mit Stimme über einen 3D-Plasma-Kern, der zur Stimme pulsiert.
            Erkennt Aufträge („Such Restaurants in Bremen mit schlechten Webseiten“) und schlägt sie vor –
            gestartet wird erst, wenn Noah „ja“ sagt oder auf „Starten“ drückt.
/auftraege  Aufträge starten, live mitverfolgen (Schnellablauf mit Erzählerstimme), stoppen, Ergebnis öffnen.
Alle Aktionen: Sitzung + CSRF + gleiche Herkunft (prüft web.py). Texte nur maskiert bzw. per textContent.
"""
from __future__ import annotations

import html
import json
import re
import secrets
from urllib.parse import urlencode

from .missions import KINDS, MissionRunner, detect_intent, get_runner, settings  # noqa: F401

E = html.escape
YES = re.compile(r"(?i)^\s*(ja|jap|jo|okay|ok|starte?|los|leg los|mach das|ja bitte|ja,? starte?)\b")


class MissionPages:
    """Wird in WebApp eingemischt. Erwartet self.jarvis, self.chat, self._page, self.audit."""

    def _runner(self) -> MissionRunner:
        return get_runner(self.jarvis)

    # ------------------------------------------------------------------ Sprach-Ansicht
    def _voice_page(self, session, csrf: str) -> str:
        return f"""<section class="voice-stage" aria-label="Sprechen mit JARVIS">
<canvas id="orb" class="orb" data-orb aria-label="JARVIS-Kern: pulsiert, wenn JARVIS zuhört oder spricht"></canvas>
<div class="voice-hud"><p class="eyebrow"><span class="live"></span>JARVIS · Stimme</p>
<p id="v-status" class="v-status" role="status" aria-live="polite">Drück auf den Knopf und sprich.</p>
<p id="v-live" class="v-live"></p></div>
<div class="voice-controls" data-csrf="{csrf}">
<button id="v-talk" class="v-talk" type="button" aria-pressed="false"><span>🎙</span> Sprechen</button>
<label class="v-opt"><input id="v-dauer" type="checkbox" checked> Dauergespräch</label>
<label class="v-opt">Stimme <select id="v-fx"><option value="film">Film</option><option value="jarvis">JARVIS</option><option value="natuerlich">Natürlich</option></select></label>
</div>
<form id="v-form" class="v-form" autocomplete="off"><label for="v-text" class="sr">Oder schreiben</label>
<input id="v-text" maxlength="1000" placeholder="Oder hier schreiben (Firefox: zweimal fn drücken zum Diktieren)">
<button type="submit">Senden</button></form>
<div id="v-propose" class="v-propose" hidden></div>
<ol id="v-log" class="v-log" aria-label="Gesprächsverlauf"></ol>
<p class="hint v-hint">Spracherkennung direkt im Browser gibt es in Chrome und Safari. In Firefox: Text-Feld + Mac-Diktat (2× fn).
JARVIS startet Aufträge nur, wenn du „ja“ sagst oder auf Starten drückst.</p>
</section>
<script src="/static/orb.js" defer></script><script src="/static/voice.js" defer></script>"""

    def _voice_ask(self, session, text: str) -> dict:
        from .chat import ChatError, strip_check
        text = (text or "").strip()[:1000]
        if not text:
            return {"ok": False, "text": "Ich habe nichts verstanden."}
        pending = session.data.get("voice_proposal")
        if pending and YES.match(text):
            session.data.pop("voice_proposal", None)
            try:
                m = self._runner().start(pending["art"], pending)
            except Exception as exc:  # noqa: BLE001
                return self._local_say(session, f"Das konnte ich nicht starten: {str(exc)[:160]}")
            self.audit.write("mission_voice_start", mission=m.id)
            res = self._local_say(session, "Alles klar, ich lege los. Du kannst live zuschauen.")
            res["weiter"] = f"/auftraege?id={m.id}"
            return res
        intent = detect_intent(text)
        if intent:
            session.data["voice_proposal"] = intent
            if intent["art"] == "akquise":
                say = (f"Verstanden. Ich soll {intent['branche']} in {intent['ort']} suchen, deren Webseiten prüfen und "
                       f"für die schwächste eine neue Webseite bauen. Gesendet wird nichts. Soll ich starten? Sag ja.")
            elif intent["art"] == "bild":
                say = "Verstanden, ich erzeuge dazu ein Bild. Soll ich starten? Sag ja."
            else:
                say = "Verstanden, ich baue das für dich und zeige dir jeden Schritt. Soll ich starten? Sag ja."
            res = self._local_say(session, say)
            res["vorschlag"] = dict(intent, link="/auftraege?" + urlencode({k: v for k, v in intent.items()}))
            return res
        session.data.pop("voice_proposal", None)
        if self.chat is None:
            return {"ok": False, "text": "Der Chat ist nicht verfügbar."}
        conv = session.data.get("voice_conv")
        if not conv or not self.chat.store.exists(conv):
            conv = self.chat.store.new_conversation()
            session.data["voice_conv"] = conv
        try:
            r = self.chat.send(conv, text, rate_key=session.username, voice=True)
        except ChatError as exc:
            return {"ok": False, "text": str(exc)}
        shown = strip_check(r["text"])
        out = {"ok": True, "text": shown, "rolle": r["role"]}
        if r["role"] == "jarvis":
            out["audio"] = f"/chat/stimme?id={int(r['id'])}"
        return out

    def _local_say(self, session, text: str) -> dict:
        """Eigene Sätze von JARVIS (ohne KI, ohne Kosten). Ton über ein Einmal-Zeichen, nie über freien Text in der URL."""
        says = session.data.setdefault("voice_says", {})
        if len(says) > 8:
            says.clear()
        k = secrets.token_hex(8)
        says[k] = text
        return {"ok": True, "text": text, "rolle": "jarvis", "audio": f"/stimme/ton?k={k}"}

    def _voice_tone(self, session, key: str, fx: str):
        text = (session.data.get("voice_says") or {}).get(key or "")
        return self._wav(text, fx)

    def _wav(self, text, fx: str):
        from .voice_fx import VoiceUnavailable, jarvis_voice
        from .web import Response
        if not text:
            return Response(404, "Nicht gefunden.", "text/plain; charset=utf-8")
        if self.jarvis.kill.is_active():
            return Response(423, "Notabschaltung aktiv.", "text/plain; charset=utf-8")
        try:
            audio = jarvis_voice(text, preset=fx if fx in ("film", "jarvis", "natuerlich") else "film")
        except VoiceUnavailable as exc:
            return Response(501, str(exc), "text/plain; charset=utf-8")
        return Response(200, audio, "audio/wav")

    # ------------------------------------------------------------------ Auftrags-Zentrale
    def _missions_page(self, session, csrf: str, query: dict) -> str:
        q = lambda k: (query.get(k) or [""])[0][:120]  # noqa: E731
        runner = self._runner()
        w = settings(self.jarvis.cfg)
        kill = self.jarvis.kill.is_active()
        flash = session.data.pop("mission_flash", "")
        flash_html = f'<p class="error" role="status">{E(flash)}</p>' if flash else ""
        on = w["web_research_allowed"]
        state = ('<p class="success">🌐 Websuche und Webseiten-Check: <b>an</b>. JARVIS liest nur öffentliche Seiten und sendet nichts.</p>'
                 if on else '<p class="warn-box">🌐 Websuche und Webseiten-Check sind <b>aus</b>. Webseiten bauen geht trotzdem. '
                 'Einschalten im Terminal: <code>python3 -m jarvis werkstatt-an</code></p>')
        mid = q("id")
        live = ""
        m = runner.get(mid) if mid else None
        if m:
            steps = "".join(self._step_html(s) for s in m.to_dict()["schritte"])
            result = ""
            if m.result.get("seite"):
                result = (f'<div class="m-result"><p>✅ Fertig: <b>{E(m.result.get("name", ""))}</b></p>'
                          f'<p class="mono">{E(m.result["ordner"])}</p>'
                          f'<form method="post" action="/auftraege/oeffnen"><input type="hidden" name="csrf" value="{csrf}">'
                          f'<input type="hidden" name="id" value="{E(m.id)}"><button type="submit">🌐 Webseite im Browser öffnen</button></form></div>')
            if m.result.get("bild"):
                result += (f'<figure class="m-bild"><img src="/medien/bild?f={E(m.result["bild"])}" alt="{E(m.result.get("name", "Bild"))}">'
                           f'<figcaption class="mono">{E(m.result["ordner"])}/{E(m.result["bild"])}</figcaption></figure>')
            if m.result.get("betriebe"):
                rows = "".join(f'<li><b>{E(b["name"])}</b> <span class="m-score {"hoch" if b["punkte"] >= 75 else "mittel" if b["punkte"] >= 50 else "tief"}">'
                               f'{int(b["punkte"])}/100</span> <span class="muted">{E(b["urteil"])}</span></li>'
                               for b in m.result["betriebe"])
                result += f'<div class="m-rank"><h3>Geprüfte Betriebe</h3><ul class="list">{rows}</ul></div>'
            stop = (f'<form method="post" action="/auftraege/stop"><input type="hidden" name="csrf" value="{csrf}">'
                    f'<input type="hidden" name="id" value="{E(m.id)}"><button class="ghost" type="submit">⏹ Stopp</button></form>'
                    if m.status == "läuft" else
                    '<button class="ghost" type="button" id="m-replay">▶ Schnellablauf abspielen</button>')
            live = f"""<section class="panel m-live" id="m-live" data-id="{E(m.id)}" data-status="{E(m.status)}">
<div class="m-head"><canvas class="m-orb" data-orb aria-hidden="true"></canvas><div><p class="eyebrow">Auftrag · {E(KINDS[m.kind])}</p>
<h2>{E(m.title())}</h2><p class="m-state">Status: <b id="m-status">{E(m.status)}</b> · gestartet {E(m.started)}</p></div>
<div class="m-ctl"><label class="v-opt"><input id="m-speak" type="checkbox" checked> JARVIS erzählt</label>{stop}</div></div>
<ol class="m-steps" id="m-steps">{steps}</ol>{result}</section>"""
        rows = "".join(f'<li><a href="/auftraege?id={E(x.id)}">{E(x.title())}</a><span class="mono">{E(x.started)} · {E(x.status)}</span></li>'
                       for x in runner.recent()) or '<li class="muted">Noch keine Aufträge.</li>'
        dis = "disabled" if kill else ""
        return f"""<header class="top"><div><p class="eyebrow"><span class="live"></span>JARVIS · Auftrags-Zentrale</p>
<h1>Aufträge</h1></div><p class="hint team-intro">JARVIS arbeitet selbstständig und zeigt dir jeden Schritt live – mit Stimme. Du startest, du stoppst. Gesendet wird nie etwas ohne dich.</p></header>
{flash_html}{state}{live}
<div class="brain-grid">
<section class="panel"><h2>🚀 Projekt bauen</h2>
<form class="capture" method="post" action="/auftraege/start"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="art" value="projekt">
<label for="p-b">Was soll JARVIS bauen?</label><textarea id="p-b" name="beschreibung" rows="4" maxlength="1500" required placeholder="z. B. Eine Landingpage für mein Kosmetikstudio mit 3D-Animation · Ein Kalorienrechner · Ein Quiz über Autos">{E(q('beschreibung')) if q('art') == 'projekt' else ''}</textarea>
<button type="submit" {dis}>Bauen</button></form>
<p class="hint">Claude programmiert eine fertige Datei, JARVIS öffnet sie im Browser. Ordner: ~/JARVIS/projekte. Kosten: ca. 1–25 Cent.</p></section>
<section class="panel"><h2>🖼 Bild erzeugen</h2>
<form class="capture" method="post" action="/auftraege/start"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="art" value="bild">
<label for="i-b">Was soll auf dem Bild sein?</label><textarea id="i-b" name="beschreibung" rows="4" maxlength="1000" required placeholder="z. B. Ein Logo für ein Kosmetikstudio in Gold und Schwarz">{E(q('beschreibung')) if q('art') == 'bild' else ''}</textarea>
<button type="submit" {dis}>Bild erzeugen</button></form>
<p class="hint">Kostenlos über Cloudflare (ca. 200 Bilder/Tag frei, JARVIS-Limit {w['max_bilder_pro_tag']}). Ordner: ~/JARVIS/bilder.</p></section>
<section class="panel"><h2>🔎 Betriebe mit schwachen Webseiten finden</h2>
<form class="capture" method="post" action="/auftraege/start"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="art" value="akquise">
<label for="a-b">Branche</label><input id="a-b" name="branche" maxlength="60" required value="{E(q('branche'))}" placeholder="z. B. Restaurants, Friseure, Autowerkstätten">
<label for="a-o">Ort</label><input id="a-o" name="ort" maxlength="60" required value="{E(q('ort'))}" placeholder="z. B. Bremen">
<label for="a-w">Wünsche für die neue Webseite (optional)</label><input id="a-w" name="wuensche" maxlength="300">
<button type="submit" {dis}>Auftrag starten</button></form>
<p class="hint">Ablauf: Websuche (höchstens {w['max_suchen']} Suchen) → Webseiten prüfen → für die schwächste eine neue Webseite → Brief + Besuchs-Leitfaden als Entwurf. Kosten: ca. 5–15 Cent.</p></section>
<section class="panel"><h2>🛠 Webseite für einen Betrieb bauen</h2>
<form class="capture" method="post" action="/auftraege/start"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="art" value="webseite">
<label for="w-n">Name des Betriebs</label><input id="w-n" name="name" maxlength="80" required value="{E(q('name'))}">
<label for="w-b">Branche</label><input id="w-b" name="branche" maxlength="60" value="{E(q('branche'))}">
<label for="w-o">Ort</label><input id="w-o" name="ort" maxlength="60" value="{E(q('ort'))}">
<label for="w-u">Alte Webseite (optional)</label><input id="w-u" name="url" maxlength="200" placeholder="https://…">
<label for="w-w">Wünsche (optional)</label><input id="w-w" name="wuensche" maxlength="300" placeholder="z. B. edel, dunkel, mit Reservierung">
<button type="submit" {dis}>Webseite bauen</button></form>
<p class="hint">Ergebnis: Ordner in ~/JARVIS/websites mit Webseite (3D-Animation, Handy-Ansicht, Dunkelmodus), Brief-Entwurf und Leitfaden. Kosten: unter 1 Cent.</p></section>
</div>
<section class="panel"><h2>Letzte Aufträge</h2><ul class="list hits">{rows}</ul></section>
<script src="/static/orb.js" defer></script><script src="/static/missions.js" defer></script>"""

    @staticmethod
    def _step_html(s: dict) -> str:
        icon = {"start": "◆", "ok": "✓", "warn": "!", "fehler": "✕", "fertig": "★"}.get(s["art"], "•")
        detail = f'<small>{E(s["detail"])}</small>' if s.get("detail") else ""
        return (f'<li class="m-step art-{E(s["art"])}" data-n="{int(s["n"])}"><i>{icon}</i><span class="mono">{E(s["zeit"])}</span>'
                f'<p>{E(s["text"])}{detail}</p></li>')

    def _missions_start(self, session, form_get) -> str:
        art = form_get("art")
        params = {k: form_get(k) for k in ("branche", "ort", "name", "url", "wuensche", "beschreibung")}
        try:
            m = self._runner().start(art, params)
        except Exception as exc:  # noqa: BLE001 – Eingabefehler, Notaus, zu viele Aufträge
            session.data["mission_flash"] = str(exc)[:200]
            return "/auftraege?" + urlencode(dict({k: v[:300] for k, v in params.items() if v and k != "url"}, art=art))
        return f"/auftraege?id={m.id}"

    def _media_image(self, name: str):
        from .web import Response
        p = self._runner().image_path(name)
        if p is None:
            return Response(404, "Nicht gefunden.", "text/plain; charset=utf-8")
        return Response(200, p.read_bytes(), "image/png" if p.suffix == ".png" else "image/jpeg")

    def _missions_data(self, mid: str, since: str) -> str:
        m = self._runner().get(mid)
        if not m:
            return json.dumps({"fehler": "unbekannt"})
        return json.dumps(m.to_dict(int(since) if since.isdigit() and len(since) < 5 else 0), ensure_ascii=False)

    def _missions_voice(self, mid: str, n: str, fx: str):
        m = self._runner().get(mid)
        steps = m.to_dict()["schritte"] if m else []
        text = steps[int(n)]["text"] if n.isdigit() and int(n) < len(steps) else ""
        return self._wav(text, fx)
