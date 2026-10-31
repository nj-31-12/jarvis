"""Second Brain (Version 5.3): Noahs Wissen als 3D-Karte, offene Aufgaben, Ziele und Schnell-Erfassung.

Regeln:
- Nur LESEN aus dem Vault, Vertrauliches erscheint nie (auch nicht als Titel). Zahlen über vertrauliche Notizen
  werden nur als Anzahl gezeigt.
- Schreiben nur über den bestehenden Befehl /notiz (neue Datei in 00_Inbox/JARVIS, Notaus wird beachtet).
- Reines HTML/SVG, animiert über jarvis.css. Kein JavaScript (strenge CSP).
"""
from __future__ import annotations

import html
import math
import re
from urllib.parse import quote

from .chat import AREA_KEYWORDS
from .profiles import PROJECTS

MAX_CAPTURE_CHARS = 2000
STATUS_CLASS = {"aktiv": "s-aktiv", "laufend": "s-aktiv", "Ausbildung": "s-ausb", "Idee": "s-idee",
                "im Aufbau": "s-idee"}


def _is_template(note) -> bool:
    """Leere Vorlagen (99_Vorlagen) sind kein Wissen und erscheinen nicht im Second Brain."""
    return (note.folder or "").split("/")[0] == "99_Vorlagen"


def _keywords(project: dict) -> list:
    words = []
    for theme in project.get("themen", []):
        words.append(theme.lower())
        words += AREA_KEYWORDS.get(theme, [])
    return sorted(set(w for w in words if w))


def _matches(text: str, words: list) -> bool:
    return any(re.search(r"(?<![a-zäöüß])" + re.escape(w) + (r"s?(?![a-zäöüß])" if len(w) <= 4 else ""), text)
               for w in words)


def area_counts(kb) -> list:
    """Je Bereich: Anzahl NICHT vertraulicher Notizen, die dazu passen (Frontmatter `bereich` hat Vorrang)."""
    notes = [n for n in kb.notes(include_confidential=False) if not _is_template(n)]
    out = []
    for p in PROJECTS:
        words = _keywords(p)
        n = 0
        for note in notes:
            tag = str(note.meta.get("bereich", "")).strip().lower() if isinstance(note.meta, dict) else ""
            if tag:
                n += tag == p["slug"]
            elif _matches((note.title + "\n" + note.text[:4000]).lower(), words):
                n += 1
        short = p["name"].split(" / ")[0]
        out.append({"slug": p["slug"], "name": short, "status": p.get("status", ""), "count": n,
                    "search": (AREA_KEYWORDS.get(p.get("themen", [""])[0]) or [short])[0]})
    return out


def brain_map(areas: list, total: int) -> str:
    """3D-Karte: JARVIS-Kern in der Mitte, Bereiche auf einer geneigten Umlaufbahn (Perspektive)."""
    n = max(len(areas), 1)
    rx, ry = 235, 92
    nodes = []
    for i, a in enumerate(areas):
        ang = -math.pi / 2 + i * 2 * math.pi / n + 0.35
        x, y = rx * math.cos(ang), ry * math.sin(ang)
        depth = 0.72 + 0.28 * (y + ry) / (2 * ry)               # hinten klein, vorne groß
        r = (11 + 3.2 * math.sqrt(a["count"])) * depth
        r = min(r, 30)
        nodes.append((y, x, r, depth, a, i))
    lines, dots = [], []
    for y, x, r, depth, a, i in sorted(nodes):
        cls = STATUS_CLASS.get(a["status"], "s-idee")
        lines.append(f'<line class="b-link" x1="0" y1="0" x2="{x:.1f}" y2="{y:.1f}"/>')
        label = html.escape(a["name"])
        href = "/wissen?q=" + quote(a["search"])
        dots.append(
            f'<a href="{href}" class="b-node {cls} d{i % 4}" aria-label="{label}: {a["count"]} Notizen">'
            f'<g class="b-float"><circle class="b-halo" cx="{x:.1f}" cy="{y:.1f}" r="{r + 7:.1f}"/>'
            f'<circle class="b-dot" cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" opacity="{depth:.2f}"/>'
            f'<text class="b-count" x="{x:.1f}" y="{y + 4:.1f}">{a["count"]}</text>'
            f'<text class="b-label" x="{x:.1f}" y="{y + r + 16:.1f}">{label}</text></g></a>')
    return ('<svg class="brain-map" viewBox="-310 -150 620 320" role="img" '
            f'aria-label="Wissenskarte: {len(areas)} Bereiche, {total} Notizen">'
            '<ellipse class="b-orbit" rx="235" ry="92"/><ellipse class="b-orbit o2" rx="150" ry="58"/>'
            '<ellipse class="b-orbit o3" rx="290" ry="118"/>'
            + "".join(lines) +
            '<g class="b-core"><circle class="b-core-glow" r="38"/><circle class="b-core-ring" r="30"/>'
            '<circle class="b-core-in" r="18"/><text class="b-core-t" y="4">JARVIS</text></g>'
            + "".join(dots) + '</svg>')


class BrainPages:
    """Wird in WebApp eingemischt. Erwartet self.jarvis, self._page, self.audit."""

    def _brain_page(self, session, csrf: str) -> str:
        kb = self.jarvis.kb
        stats = kb.stats()
        areas = area_counts(kb)
        recent = [n for n in kb.recent(limit=30) if not _is_template(n)][:8]
        tasks = kb.open_checkboxes(limit=12)
        goals = kb.open_goals()[:8]
        flash = session.data.pop("brain_flash", "")
        ok = flash.startswith("📝")
        flash_html = (f'<p class="{"success" if ok else "error"}" role="status">{html.escape(flash)}</p>'
                      if flash else "")
        kill = self.jarvis.kill.is_active()

        def li(items, empty):
            return "".join(items) or f'<li class="muted">{empty}</li>'

        recent_html = li([f'<li><a href="/wissen/notiz?id={html.escape(n.id)}">{html.escape(n.title)}</a>'
                          f'<span class="mono">{html.escape(n.folder or "Hauptordner")}</span></li>' for n in recent],
                         "Noch keine Notizen.")
        task_html = li([f'<li><b>{html.escape(t)}</b><span class="mono">{html.escape(src)}</span></li>'
                        for src, t in tasks], "Keine offenen Aufgaben (Zeilen mit „- [ ]“ in deinen Notizen).")
        goal_html = li([f"<li>{html.escape(g)}</li>" for g in goals], "Noch keine Ziele in 01_Ziele.")
        hidden = stats.get("confidential", 0)
        return f"""<header class="top brain-top"><div><p class="eyebrow"><span class="live"></span>JARVIS · Second Brain</p>
<h1>Dein zweites Gehirn</h1></div>
<div class="brain-kpis"><div><b>{stats.get('visible', 0)}</b><span>Notizen</span></div>
<div><b>{len(tasks)}</b><span>offene Aufgaben</span></div><div><b>{len(goals)}</b><span>Ziele</span></div>
<div><b>{hidden}</b><span>vertraulich (verborgen)</span></div></div></header>
<section class="panel brain-stage" aria-label="Wissenskarte">{brain_map(areas, stats.get('visible', 0))}
<p class="hint">Jeder Punkt ist ein Geschäftsbereich, die Zahl zeigt passende Notizen. Klick öffnet die Suche. Vertrauliche Notizen (z. B. aus 90_Privat) werden nie gezeigt.</p></section>
<div class="brain-grid">
<section class="panel"><h2>Schnell festhalten</h2>{flash_html}
<form class="capture" method="post" action="/gehirn/notiz"><input type="hidden" name="csrf" value="{csrf}">
<label for="merk">Gedanke, Idee oder Aufgabe</label>
<textarea id="merk" name="text" rows="3" maxlength="{MAX_CAPTURE_CHARS}" required placeholder="z. B. - [ ] Preise für Coaching-Paket festlegen"></textarea>
<button type="submit" {'disabled' if kill else ''}>Im Gehirn ablegen</button></form>
<p class="hint">Wird als neue Notiz in Obsidian unter 00_Inbox/JARVIS gespeichert. Nichts wird überschrieben. Beginnt eine Zeile mit „- [ ]“, erscheint sie als Aufgabe.</p></section>
<section class="panel"><h2>Offene Aufgaben</h2><ul class="list hits">{task_html}</ul></section>
<section class="panel"><h2>Zuletzt im Gedächtnis</h2><ul class="list hits">{recent_html}</ul></section>
<section class="panel"><h2>Ziele</h2><ul class="list">{goal_html}</ul></section>
</div>"""

    def _brain_capture(self, session, text: str) -> None:
        text = (text or "").replace("\r\n", "\n").strip()[:MAX_CAPTURE_CHARS]
        if not text:
            session.data["brain_flash"] = "Bitte etwas eingeben."
            return
        reply = self.jarvis.handle_text("/notiz " + text)        # gleiche Regeln wie im Chat (Notaus, Inbox)
        self.audit.write("brain_capture", length=len(text))
        session.data["brain_flash"] = reply.splitlines()[0][:200]
