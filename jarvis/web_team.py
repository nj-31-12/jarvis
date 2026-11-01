"""Team-Seite (Stand 20): KI-Mitarbeiter auf einer 3D-Plattform, nach Skill-Kategorien sortiert."""
from __future__ import annotations

import html

from .team import CATEGORIES, MEMBERS, platform_data, run_round, safe_category


class TeamPages:
    """Wird in WebApp eingemischt. Erwartet self.jarvis, self._page."""

    def _team_page(self, session, csrf: str) -> str:
        kb = self.jarvis.kb
        data = platform_data(kb)
        kill = self.jarvis.kill.is_active()
        flash = session.data.pop("team_flash", "")
        flash_html = (f'<p class="{"success" if flash.startswith("👥") else "error"}" role="status">'
                      f'{html.escape(flash)}</p>') if flash else ""
        options = "".join(f'<option value="{c}">{html.escape(n)}</option>' for c, n, _ in CATEGORIES)
        rounds = "".join(f'<li><a href="/wissen/notiz?id={html.escape(r["id"])}">{html.escape(r["title"])}</a>'
                         f'<span class="mono">{html.escape(", ".join(r["team"]))}</span></li>' for r in data["rounds"]) \
            or '<li class="muted">Noch keine Team-Runden.</li>'
        counts = {m["id"]: m["runden"] for m in data["members"]}
        groups = []
        for cid, cname, rgb in CATEGORIES:
            cards = "".join(
                f'<article class="member" id="m-{m["id"]}" data-cat="{cid}"><div class="avatar cat-{cid}" aria-hidden="true">'
                f'{html.escape(m["name"][0])}</div><div><b>{html.escape(m["name"])}</b><span>{html.escape(m["rolle"])}</span>'
                f'<p class="chips">{"".join(f"<i>{html.escape(s)}</i>" for s in m["skills"])}</p>'
                f'<small>{counts[m["id"]]} Team-Runden</small></div></article>'
                for m in MEMBERS if m["kategorie"] == cid)
            groups.append(f'<section class="panel team-cat cat-{cid}"><h2>{html.escape(cname)}</h2>'
                          f'<div class="members">{cards}</div></section>')
        return f"""<header class="top"><div><p class="eyebrow"><span class="live"></span>JARVIS · Team</p>
<h1>Dein KI-Team</h1></div><p class="hint team-intro">{len(MEMBERS)} Mitarbeiter in {len(CATEGORIES)} Kategorien. Sie arbeiten zusammen, tauschen sich aus und legen ihr Ergebnis als Wissen ins Second Brain.</p></header>
<section class="panel platform-stage" aria-label="Team-Plattform">
<div class="platform"><canvas data-hud="platform" data-src="/team/daten" aria-label="3D-Plattform mit deinen KI-Mitarbeitern – mit dem Touchpad drehbar"></canvas><div class="b3-tip" hidden></div>
<div class="b3-help"><b>Plattform</b> · Wischen: drehen · Pinch: zoomen · Klick auf eine Figur: Profil · Lichtbahnen: wer zusammengearbeitet hat</div></div></section>
<div class="brain-grid">
<section class="panel team-task"><h2>👥 Aufgabe an das Team</h2>{flash_html}
<form class="capture" method="post" action="/team/runde"><input type="hidden" name="csrf" value="{csrf}">
<label for="aufgabe">Was soll dein Team erarbeiten?</label>
<textarea id="aufgabe" name="text" rows="4" maxlength="2000" required placeholder="z. B. Wie gewinne ich die ersten 3 Restaurants für die QR-Stempelkarte?"></textarea>
<label for="kat">Wer arbeitet mit?</label>
<select id="kat" name="kategorie"><option value="">Automatisch (passende Mitarbeiter)</option>{options}</select>
<button type="submit" {'disabled' if kill else ''}>Team-Runde starten</button></form>
<p class="hint">Höchstens 4 Mitarbeiter, jeder liest die Beiträge der anderen. JARVIS fasst zusammen. Niemand kann etwas ausführen oder senden. Kosten mit echter KI: unter 1 Cent pro Runde (Schätzung).</p></section>
<section class="panel"><h2>Letzte Team-Runden</h2><ul class="list hits">{rounds}</ul></section>
</div>
{''.join(groups)}
<script src="/static/hud.js" defer></script>"""

    def _team_round(self, session, text: str, category: str) -> str:
        from .knowledge import note_id_for
        try:
            res = run_round(self.jarvis, text, safe_category(category))
        except Exception as exc:  # noqa: BLE001 – z. B. Kostenbremse: verständlich melden
            res = {"ok": False, "meldung": f"⚠️ {str(exc)[:200]}", "pfad": None}
        session.data["team_flash"] = res["meldung"]
        if not res.get("pfad"):
            return "/team"
        return "/wissen/notiz?id=" + note_id_for(res["pfad"].resolve().relative_to(self.jarvis.vault.root).as_posix())

    def _team_data(self) -> dict:
        return platform_data(self.jarvis.kb)
