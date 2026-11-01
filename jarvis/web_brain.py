"""Second Brain (Version 5.3): Noahs Wissen als 3D-Karte, offene Aufgaben, Ziele und Schnell-Erfassung.

Regeln:
- Nur LESEN aus dem Vault, Vertrauliches erscheint nie (auch nicht als Titel). Zahlen über vertrauliche Notizen
  werden nur als Anzahl gezeigt.
- Schreiben nur über den bestehenden Befehl /notiz (neue Datei in 00_Inbox/JARVIS, Notaus wird beachtet).
- Das 3D-Gehirn zeichnet /static/brain.js (eigene Datei, kein Inline-Skript, kein CDN – strenge CSP bleibt).
  Ohne JavaScript bleibt die SVG-Karte sichtbar. Die Daten kommen aus /gehirn/daten (nur nicht Vertrauliches).
"""
from __future__ import annotations

import html
import math
import re
from urllib.parse import quote

from .chat import AREA_KEYWORDS
from .lessons import LESSON_TYPE, MAX_LESSON_CHARS, add_lesson, lessons
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


WIKILINK = re.compile(r"\[\[([^\]|#]{1,120})(?:[#|][^\]]*)?\]\]")
MAX_GRAPH_NOTES = 400
MAX_TOPICS = 8


def _topic_of(note) -> str:
    """Lebensthema aus dem Ordner (z. B. 05_Lernen → Lernen). Nicht festgelegt: wächst mit Noahs Vault."""
    top = (note.folder or "").split("/")[0]
    if top.startswith("00_Inbox") or not top:
        tags = [t.strip(" []") for t in str(note.meta.get("tags", "") if isinstance(note.meta, dict) else "").split(",")]
        tags = [t for t in tags if t and t not in ("jarvis", "entwurf", "notiz")]
        return tags[0].capitalize()[:30] if tags else "Eingang"
    name = re.sub(r"^\d+[_\- ]*", "", top).replace("_", " ").strip()
    return (name or "Allgemein")[:30]


def _area_of(note, projects_words) -> str:
    tag = str(note.meta.get("bereich", "")).strip().lower() if isinstance(note.meta, dict) else ""
    if tag:
        return tag if any(slug == tag for slug, _ in projects_words) else ""
    low = (note.title + "\n" + note.text[:4000]).lower()
    for slug, words in projects_words:
        if _matches(low, words):
            return slug
    return ""


def _kind(note) -> str:
    meta = note.meta if isinstance(note.meta, dict) else {}
    if str(meta.get("typ", "")).lower() == LESSON_TYPE:
        return "lektion"
    if note.title.lower().startswith("recherche") or "recherche" in str(meta.get("tags", "")).lower():
        return "recherche"
    if "- [ ]" in note.text:
        return "aufgabe"
    return "notiz"


def brain_data(kb) -> dict:
    """Daten für das 3D-Gehirn. NUR nicht vertrauliche Notizen, ohne Vorlagen, ohne Inhalte (nur Titel)."""
    notes = [n for n in kb.notes(include_confidential=False) if not _is_template(n)]
    notes = sorted(notes, key=lambda n: -n.mtime)[:MAX_GRAPH_NOTES]
    projects_words = [(p["slug"], _keywords(p)) for p in PROJECTS]
    by_title = {n.title.strip().lower(): i for i, n in enumerate(notes)}
    items, links, topics = [], [], {}
    for i, n in enumerate(notes):
        area = _area_of(n, projects_words)
        if not area:                                  # kein Geschäftsbereich → eigenes Lebensthema aus dem Ordner
            name = _topic_of(n)
            area = "thema:" + name.lower()
            topics.setdefault(area, {"slug": area, "name": name, "status": "Thema", "count": 0, "search": name})
            topics[area]["count"] += 1
        items.append({"id": n.id, "title": n.title[:120], "area": area, "kind": _kind(n)})
        for target in WIKILINK.findall(n.text[:20000]):
            j = by_title.get(target.strip().lower())
            if j is not None and j != i:
                links.append([i, j])
    extra = sorted(topics.values(), key=lambda t: -t["count"])[:MAX_TOPICS]
    keep = {t["slug"] for t in extra}
    for it in items:                                  # zu kleine Themen hängen am Kern
        if it["area"].startswith("thema:") and it["area"] not in keep:
            it["area"] = ""
    return {"areas": area_counts(kb) + extra, "notes": items, "links": links[:1500]}


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
        learned = lessons(kb)
        lesson_html = li([f'<li><a href="/wissen/notiz?id={html.escape(x["id"])}">{html.escape(x["text"])}</a></li>'
                          for x in learned], "Noch keine Lektionen.")
        lflash = session.data.pop("lesson_flash", "")
        lesson_flash = (f'<p class="{"success" if lflash.startswith("🧠") else "error"}" role="status">'
                        f'{html.escape(lflash)}</p>') if lflash else ""
        research = [n for n in kb.recent(limit=60) if _kind(n) == "recherche"][:6]
        research_html = li([f'<li><a href="/wissen/notiz?id={html.escape(n.id)}">{html.escape(n.title)}</a></li>'
                            for n in research], "Noch keine Recherchen.")
        return f"""<header class="top brain-top"><div><p class="eyebrow"><span class="live"></span>JARVIS · Second Brain</p>
<h1>Dein zweites Gehirn</h1></div>
<div class="brain-kpis"><div><b>{stats.get('visible', 0)}</b><span>Notizen</span></div>
<div><b>{len(tasks)}</b><span>offene Aufgaben</span></div><div><b>{len(goals)}</b><span>Ziele</span></div>
<div><b>{len(learned)}</b><span>Lektionen</span></div>
<div><b>{hidden}</b><span>vertraulich (verborgen)</span></div></div></header>
<section class="panel brain-stage" aria-label="Dein Gehirn in 3D">
<div class="view-switch" role="group" aria-label="Ansicht" hidden><button type="button" data-view="brain" aria-pressed="true">🧠 Gehirn</button><button type="button" data-view="tunnel" aria-pressed="false">⟶ Datentunnel</button></div>
<div class="brain-tunnel"><canvas data-hud="tunnel" data-src="/gehirn/daten" aria-label="Datentunnel: Notizen an den Wänden, mit dem Touchpad hindurchfliegen"></canvas><div class="b3-tip" hidden></div>
<div class="b3-help"><b>Datentunnel</b> · Klicken, dann hoch/runter wischen: vor/zurück fliegen · Seitwärts: umsehen · Klick auf Licht: Notiz öffnen</div></div>
<div class="brain3d" id="brain3d" data-src="/gehirn/daten"><canvas aria-label="3D-Gehirn: Bereiche und Notizen als Neuronen"></canvas>
<div class="b3-tip" hidden></div>
<div class="b3-help"><b>Steuerung</b> · Zwei Finger wischen: drehen · Zwei Finger auf/zu: hineinfliegen · Shift + wischen: hindurchfliegen · Klick: öffnen · Doppelklick: zurück</div>
<div class="b3-legend"><span class="k-area">Bereich</span><span class="k-notiz">Notiz</span><span class="k-aufgabe">Aufgabe</span><span class="k-lektion">Lektion</span><span class="k-recherche">Recherche</span><span class="k-thema">Lebensthema</span></div></div>
<div class="brain-fallback">{brain_map(areas, stats.get('visible', 0))}</div>
<p class="hint">Jeder leuchtende Knoten ist ein Geschäftsbereich, die kleinen Lichter sind deine Notizen, Lichtimpulse zeigen Verbindungen. Vertrauliche Notizen (z. B. aus 90_Privat) werden nie gezeigt.</p></section>
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
<section class="panel lessons"><h2>Lektionen – damit Fehler nicht wieder passieren</h2>{lesson_flash}
<form class="capture" method="post" action="/gehirn/lektion"><input type="hidden" name="csrf" value="{csrf}">
<label for="lektion">Was soll JARVIS sich dauerhaft merken?</label>
<textarea id="lektion" name="text" rows="2" maxlength="{MAX_LESSON_CHARS}" required placeholder="z. B. Beim Update immer den Zweig version5-3 herunterladen, nicht main."></textarea>
<button type="submit" {'disabled' if kill else ''}>Lektion merken</button></form>
<ul class="list">{lesson_html}</ul>
<p class="hint">Gemerkte Lektionen beachtet JARVIS bei jeder Antwort. Entfernen: die Notiz in Obsidian löschen. Sicherheitsregeln können Lektionen nicht aufheben.</p></section>
<section class="panel"><h2>Denken &amp; Forschen</h2><ul class="list hits">{research_html}</ul>
<p class="hint">Recherche-Ergebnisse der Nachtarbeit erscheinen hier und im Gehirn als orange Neuronen. Neue Recherchen: Befehl <code>/nacht</code> im Chat (nutzt die KI nur, wenn „research“ freigegeben ist).</p></section>
</div>
<script src="/static/brain.js" defer></script><script src="/static/hud.js" defer></script>"""

    def _brain_lesson(self, session, text: str) -> None:
        session.data["lesson_flash"] = add_lesson(self.jarvis, text)

    def _brain_capture(self, session, text: str) -> None:
        text = (text or "").replace("\r\n", "\n").strip()[:MAX_CAPTURE_CHARS]
        if not text:
            session.data["brain_flash"] = "Bitte etwas eingeben."
            return
        reply = self.jarvis.handle_text("/notiz " + text)        # gleiche Regeln wie im Chat (Notaus, Inbox)
        self.audit.write("brain_capture", length=len(text))
        session.data["brain_flash"] = reply.splitlines()[0][:200]
