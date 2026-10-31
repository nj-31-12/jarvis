"""Sichere Markdown-Anzeige für die Browseroberfläche.

Grundsatz: Erst ALLES maskieren (HTML-escape), dann nur eine kleine, bekannte
Auswahl an Formatierungen wieder erlauben. Dadurch kann Text aus Notizen oder
aus KI-Antworten niemals als HTML oder JavaScript im Browser ausgeführt werden.

Unterstützt: Überschriften, Absätze, Listen, Checklisten, Zitate, Trennlinien,
Tabellen, Codeblöcke, **fett**, *kursiv*, `code`, [Links](https://…), [[Wikilinks]].
Bewusst NICHT unterstützt: eingebettetes HTML, Bilder (werden als Text gezeigt),
Links mit anderen Schemata als http/https (z. B. javascript:, data:, file:).
"""
from __future__ import annotations

import html
import re

_SAFE_SCHEMES = ("http://", "https://")
_PH = "\x00"  # Platzhalter-Zeichen; wird vorher aus der Eingabe entfernt


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _safe_url(escaped_url: str) -> str | None:
    raw = html.unescape(escaped_url).strip()
    # Steuerzeichen und Leerzeichen innerhalb der URL ablehnen (Tricks wie "java\nscript:")
    if any(ord(c) < 33 for c in raw):
        return None
    if raw.lower().startswith(_SAFE_SCHEMES):
        return _esc(raw)
    return None


def render_inline(text: str) -> str:
    text = text.replace(_PH, "")
    stash: list[str] = []

    def keep(fragment: str) -> str:
        # Fertige HTML-Stücke parken, damit spätere Regeln (fett/kursiv) sie nicht verändern.
        stash.append(fragment)
        return f"{_PH}{len(stash) - 1}{_PH}"

    text = re.sub(r"`([^`]+)`", lambda m: keep(f"<code>{_esc(m.group(1))}</code>"), text)
    out = _esc(text)
    # Bilder nie laden – nur als Text anzeigen
    out = re.sub(r"!\[([^\]]*)\]\(([^)]*)\)",
                 lambda m: keep(f"<span class=\"md-img\">[Bild: {m.group(1)}]</span>"), out)

    def link(m: re.Match) -> str:
        url = _safe_url(m.group(2))
        if url is None:
            return keep(f"{m.group(1)} <span class=\"md-blocked\">(Link entfernt)</span>")
        return keep(f"<a href=\"{url}\" rel=\"noopener noreferrer nofollow\" target=\"_blank\">{m.group(1)}</a>")

    out = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, out)
    out = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]",
                 lambda m: keep(f"<span class=\"md-wiki\">{m.group(2) or m.group(1)}</span>"), out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", out)
    out = re.sub(r"(?<![\w])_(?!\s)(.+?)(?<!\s)_(?![\w])", r"<em>\1</em>", out)
    # Geparkte Stücke zurücksetzen (mehrfach, falls verschachtelt)
    for _ in range(3):
        out = re.sub(f"{_PH}(\\d+){_PH}", lambda m: stash[int(m.group(1))], out)
    return out


def _split_frontmatter(text: str) -> tuple[list[tuple[str, str]], str]:
    if not text.startswith("---\n"):
        return [], text
    end = text.find("\n---", 4)
    if end < 0:
        return [], text
    meta = []
    for line in text[4:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta.append((k.strip(), v.strip()))
    return meta, text[end + 4:].lstrip("\n")


def _table(rows: list[str]) -> str:
    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]
    head = cells(rows[0])
    body = [cells(r) for r in rows[2:]] if len(rows) > 1 and re.match(r"^\s*\|?[\s:\-|]+\|?\s*$", rows[1]) \
        else [cells(r) for r in rows[1:]]
    out = ["<div class=\"md-table\"><table><thead><tr>"]
    out += [f"<th>{render_inline(c)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for r in body:
        out.append("<tr>" + "".join(f"<td>{render_inline(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def render(text: str) -> str:
    """Wandelt Markdown in sicheres HTML um."""
    text = (text or "").replace("\r\n", "\n").replace(_PH, "")
    meta, text = _split_frontmatter(text)
    out: list[str] = []
    if meta:
        out.append("<dl class=\"md-meta\">" + "".join(
            f"<dt>{_esc(k)}</dt><dd>{_esc(v)}</dd>" for k, v in meta) + "</dl>")
    lines = text.split("\n")
    i, para, list_type = 0, [], None

    def flush_para():
        if para:
            out.append("<p>" + "<br>".join(render_inline(p) for p in para) + "</p>")
            para.clear()

    def close_list():
        nonlocal list_type
        if list_type:
            out.append(f"</{list_type}>")
            list_type = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_para(); close_list()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i]); i += 1
            out.append(f"<pre><code>{_esc(chr(10).join(code))}</code></pre>")
            i += 1
            continue
        if not stripped:
            flush_para(); close_list(); i += 1; continue
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_para(); close_list()
            n = len(m.group(1))
            out.append(f"<h{n}>{render_inline(m.group(2))}</h{n}>")
            i += 1; continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            flush_para(); close_list(); out.append("<hr>"); i += 1; continue
        if stripped.startswith("|"):
            flush_para(); close_list()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i]); i += 1
            out.append(_table(rows)); continue
        if stripped.startswith(">"):
            flush_para(); close_list()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip()); i += 1
            out.append("<blockquote>" + "<br>".join(render_inline(q) for q in quote) + "</blockquote>")
            continue
        m = re.match(r"^([-*+]|\d+[.)])\s+(.*)$", stripped)
        if m:
            flush_para()
            wanted = "ol" if m.group(1)[0].isdigit() else "ul"
            if list_type != wanted:
                close_list(); out.append(f"<{wanted}>"); list_type = wanted
            item = m.group(2)
            box = re.match(r"^\[([ xX])\]\s+(.*)$", item)
            if box:
                done = box.group(1).lower() == "x"
                mark = "☑" if done else "☐"
                out.append(f"<li class=\"md-task{' done' if done else ''}\"><span aria-hidden=\"true\">{mark}</span> "
                           f"{render_inline(box.group(2))}</li>")
            else:
                out.append(f"<li>{render_inline(item)}</li>")
            i += 1; continue
        close_list()
        para.append(stripped)
        i += 1
    flush_para(); close_list()
    return "\n".join(out)
