"""Webseiten-Werkstatt (Stand 23): baut aus Inhalten eine moderne Demo-Webseite mit 3D-Animation.

- Claude (oder im Testmodus JARVIS selbst) liefert NUR Texte und Farben als JSON. Das Design, das HTML, CSS und
  JavaScript kommen aus dieser Vorlage. So kann kein fremder Code in die Seite gelangen; alle Texte werden maskiert.
- Ergebnis: Ordner mit index.html, style.css, script.js, LIESMICH.txt – ohne Internet, ohne Bibliotheken, ohne CDN.
  Die Seite läuft per Doppelklick im Browser und lässt sich später bei jedem Webhoster hochladen.
- 3D: eigene Canvas-Animation (Partikel-Form, die zwischen Kugel, Ring und Welle wechselt und der Maus folgt),
  3D-Kippkarten, sanftes Einblenden beim Scrollen, Glas-Navigation, Dunkel-/Hellmodus, Handy-Ansicht,
  „reduzierte Bewegung“ wird respektiert.
- Kontaktdaten, Preise und Bewertungen werden NIE erfunden: dort stehen deutlich markierte Platzhalter.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
from pathlib import Path

HEX = re.compile(r"#[0-9a-fA-F]{6}")
STYLES = {
    "elegant": ("#c9a96e", "#1d1a24"),
    "warm": ("#e0743c", "#2a1b14"),
    "frisch": ("#2bb673", "#0f2a22"),
    "technisch": ("#4fb3ff", "#0c1726"),
}


def slugify(text: str) -> str:
    t = (text or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return (t or "webseite")[:48]


def _txt(value, limit: int) -> str:
    v = re.sub(r"\s+", " ", str(value or "")).strip()
    return v[:limit]


def clean_content(raw: dict, fallback_name: str = "", branche: str = "", ort: str = "") -> dict:
    """Bringt die KI-Antwort in eine sichere, feste Form (Längen, Anzahl, Farben)."""
    raw = raw if isinstance(raw, dict) else {}
    stil = raw.get("stil") if raw.get("stil") in STYLES else "elegant"
    farben = raw.get("farben") if isinstance(raw.get("farben"), dict) else {}
    prim = farben.get("primaer") if isinstance(farben.get("primaer"), str) and HEX.fullmatch(farben["primaer"]) else STYLES[stil][0]
    dunkel = farben.get("dunkel") if isinstance(farben.get("dunkel"), str) and HEX.fullmatch(farben["dunkel"]) else STYLES[stil][1]
    services = []
    for item in (raw.get("leistungen") if isinstance(raw.get("leistungen"), list) else [])[:6]:
        if isinstance(item, dict) and _txt(item.get("titel"), 60):
            services.append({"titel": _txt(item.get("titel"), 60), "text": _txt(item.get("text"), 260)})
    perks = [_txt(p, 90) for p in (raw.get("vorteile") if isinstance(raw.get("vorteile"), list) else [])[:5] if _txt(p, 90)]
    name = _txt(raw.get("name"), 80) or _txt(fallback_name, 80) or "Ihr Betrieb"
    return {
        "name": name, "branche": _txt(raw.get("branche") or branche, 60), "ort": _txt(raw.get("ort") or ort, 60),
        "slogan": _txt(raw.get("slogan"), 90) or f"Willkommen bei {name}",
        "untertitel": _txt(raw.get("untertitel"), 220),
        "leistungen": services or [{"titel": "Unser Angebot", "text": "Hier stellen Sie Ihr Angebot vor."}],
        "ueber_uns": _txt(raw.get("ueber_uns"), 900),
        "vorteile": perks,
        "aufruf": _txt(raw.get("aufruf"), 160) or "Wir freuen uns auf Sie.",
        "aufruf_knopf": _txt(raw.get("aufruf_knopf"), 30) or "Kontakt aufnehmen",
        "stil": stil, "primaer": prim, "dunkel": dunkel,
    }


def content_prompt(name: str, branche: str, ort: str, wuensche: str, befunde: list, titel: str = "") -> str:
    """Anfrage an Claude: nur Texte + Farben als JSON."""
    return (f"Erstelle die Texte für eine moderne Webseite.\nBetrieb: {name}\nBranche: {branche}\nOrt: {ort}\n"
            f"Bisheriger Seitentitel: {titel or 'unbekannt'}\nSchwächen der alten Seite: {'; '.join(befunde) or 'keine Angabe'}\n"
            f"Wünsche: {wuensche or 'keine'}\n\n"
            "Antworte NUR mit JSON in genau diesem Format:\n"
            '{"name": "...", "branche": "...", "ort": "...", "slogan": "kurz, stark, max. 8 Wörter", '
            '"untertitel": "1 Satz", "leistungen": [{"titel": "...", "text": "1-2 Sätze"}], '
            '"ueber_uns": "3-4 Sätze, ohne erfundene Fakten (keine Jahreszahlen, Preise, Auszeichnungen)", '
            '"vorteile": ["...", "..."], "aufruf": "1 Satz", "aufruf_knopf": "2-3 Wörter", '
            '"stil": "elegant|warm|frisch|technisch", "farben": {"primaer": "#rrggbb", "dunkel": "#rrggbb"}}\n'
            "3 bis 6 Leistungen, 3 bis 5 Vorteile. Deutsch, Sie-Form, warm und professionell.")


def parse_json_object(text: str) -> dict:
    """Findet das erste JSON-Objekt in einer Antwort (Claude setzt manchmal ```json davor)."""
    text = text or ""
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(text[start:i + 1])
                        if isinstance(value, dict):
                            return value
                    except ValueError:
                        break
                    break
        start = text.find("{", start + 1)
    return {}


def demo_content(name: str, branche: str, ort: str) -> dict:
    """Testmodus (ohne KI): sinnvolle, neutrale Standardtexte."""
    b = branche or "Betrieb"
    return {"name": name, "branche": b, "ort": ort, "slogan": f"{b} mit Herz in {ort}" if ort else f"{b} mit Herz",
            "untertitel": "Persönlich, zuverlässig und mit Liebe zum Detail – schauen Sie vorbei.",
            "leistungen": [{"titel": "Persönliche Beratung", "text": "Wir nehmen uns Zeit für Ihre Wünsche."},
                           {"titel": "Qualität", "text": "Ausgewählte Produkte und sorgfältige Arbeit."},
                           {"titel": "Einfach erreichbar", "text": "Kontakt, Anfahrt und Öffnungszeiten auf einen Blick."}],
            "ueber_uns": f"{name} steht für ehrliche Arbeit und freundlichen Service. Hier erzählen Sie Ihre Geschichte.",
            "vorteile": ["Schnelle Antwort", "Faire Beratung", "Mitten in " + (ort or "der Stadt")],
            "aufruf": "Wir freuen uns auf Ihren Besuch.", "aufruf_knopf": "Kontakt aufnehmen", "stil": "elegant"}


def _rgb(hexcolor: str) -> str:
    return ",".join(str(int(hexcolor[i:i + 2], 16)) for i in (1, 3, 5))


def render(c: dict) -> dict:
    """Gibt {dateiname: inhalt} zurück. Alle Texte sind maskiert."""
    e = lambda s: html.escape(str(s), quote=True)  # noqa: E731
    services = "".join(f'<article class="card tilt reveal"><span class="num">{i + 1:02d}</span><h3>{e(s["titel"])}</h3>'
                       f'<p>{e(s["text"])}</p></article>' for i, s in enumerate(c["leistungen"]))
    perks = "".join(f"<li class=\"reveal\">{e(p)}</li>" for p in c["vorteile"])
    year = dt.date.today().year
    sub = e(c["untertitel"]) if c["untertitel"] else e(f'{c["branche"]} · {c["ort"]}'.strip(" ·"))
    index = f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(c["name"])}{(" – " + e(c["branche"])) if c["branche"] else ""}{(" in " + e(c["ort"])) if c["ort"] else ""}</title>
<meta name="description" content="{e(c["untertitel"] or c["slogan"])}">
<meta property="og:title" content="{e(c["name"])}"><meta property="og:description" content="{e(c["slogan"])}">
<meta name="theme-color" content="{e(c["dunkel"])}">
<link rel="stylesheet" href="style.css"></head>
<body>
<div class="demo-flag">Entwurf · Demo-Webseite · noch nicht veröffentlicht</div>
<header class="nav"><a class="logo" href="#top">{e(c["name"])}</a>
<nav><a href="#angebot">Angebot</a><a href="#ueber">Über uns</a><a href="#kontakt" class="btn small">{e(c["aufruf_knopf"])}</a></nav></header>
<section class="hero" id="top"><canvas id="scene" aria-hidden="true"></canvas>
<div class="hero-text"><p class="eyebrow">{e(c["branche"])}{(" · " + e(c["ort"])) if c["ort"] else ""}</p>
<h1>{e(c["slogan"])}</h1><p class="lead">{sub}</p>
<div class="actions"><a class="btn" href="#kontakt">{e(c["aufruf_knopf"])}</a><a class="btn ghost" href="#angebot">Angebot ansehen</a></div></div>
<div class="scroll-hint" aria-hidden="true"></div></section>
<section id="angebot" class="section"><h2 class="reveal">Unser Angebot</h2><div class="cards">{services}</div></section>
<section id="ueber" class="section split"><div class="reveal"><h2>Über uns</h2><p>{e(c["ueber_uns"] or "Hier stellen Sie sich vor.")}</p></div>
<ul class="perks">{perks}</ul></section>
<section id="kontakt" class="section cta reveal"><h2>{e(c["aufruf"])}</h2>
<div class="contact"><p><b>Adresse:</b> <span class="todo">[bitte eintragen]</span></p><p><b>Telefon:</b> <span class="todo">[bitte eintragen]</span></p>
<p><b>Öffnungszeiten:</b> <span class="todo">[bitte eintragen]</span></p></div>
<a class="btn" href="#kontakt">{e(c["aufruf_knopf"])}</a></section>
<footer><span>© {year} {e(c["name"])}</span><a href="#kontakt">Impressum <span class="todo">[Pflicht – bitte ergänzen]</span></a><a href="#kontakt">Datenschutz <span class="todo">[Pflicht – bitte ergänzen]</span></a></footer>
<script src="script.js"></script></body></html>
"""
    css = CSS.replace("__PRIM__", _rgb(c["primaer"])).replace("__DARK__", c["dunkel"])
    readme = (f"Demo-Webseite für {c['name']} – erstellt von JARVIS am {dt.date.today():%d.%m.%Y}.\n\n"
              "Öffnen: index.html doppelklicken.\n"
              "Vor einer Veröffentlichung: Adresse, Telefon, Öffnungszeiten, Impressum und Datenschutzerklärung\n"
              "eintragen (Pflicht in Deutschland) und alle Texte mit dem Betrieb abstimmen.\n"
              "Die Seite nutzt kein Internet, keine Cookies und keine fremden Bibliotheken.\n")
    return {"index.html": index, "style.css": css, "script.js": JS, "LIESMICH.txt": readme}


def build_site(content: dict, out_root: Path, extra_files: dict | None = None) -> Path:
    """Schreibt die Webseite in einen NEUEN Ordner (nie überschreiben). Gibt den Ordner zurück."""
    c = clean_content(content)
    out_root = Path(out_root).expanduser()
    out_root.mkdir(parents=True, exist_ok=True)
    base = f"{dt.date.today():%Y-%m-%d}_{slugify(c['name'])}"
    folder, n = out_root / base, 2
    while folder.exists():
        folder, n = out_root / f"{base}_{n}", n + 1
    folder.mkdir()
    files = render(c)
    files.update(extra_files or {})
    for name, text in files.items():
        if "/" in name or "\\" in name or name.startswith("."):
            continue
        (folder / name).write_text(text, encoding="utf-8")
    return folder


CSS = """:root{--p:__PRIM__;--dark:__DARK__;--bg:#f7f6f3;--fg:#17151c;--muted:#5d5866;--card:rgba(255,255,255,.72);--line:rgba(20,20,30,.08)}
@media (prefers-color-scheme:dark){:root{--bg:#0d0c11;--fg:#f3f1f6;--muted:#a7a1b2;--card:rgba(255,255,255,.05);--line:rgba(255,255,255,.09)}}
*{box-sizing:border-box;margin:0}html{scroll-behavior:smooth}
body{font:17px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;background:var(--bg);color:var(--fg);-webkit-font-smoothing:antialiased;overflow-x:hidden}
a{color:inherit;text-decoration:none}
.demo-flag{position:fixed;bottom:14px;left:14px;z-index:50;font-size:12px;padding:6px 12px;border-radius:99px;background:rgba(var(--p),.92);color:#fff;letter-spacing:.02em}
.nav{position:fixed;inset:14px 14px auto;z-index:40;display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 20px;border-radius:18px;background:rgba(16,14,22,.58);color:#fff;backdrop-filter:blur(16px) saturate(1.4);-webkit-backdrop-filter:blur(16px) saturate(1.4);border:1px solid var(--line)}
.logo{font-weight:800;letter-spacing:-.02em;font-size:19px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.nav nav{display:flex;gap:22px;align-items:center}.nav nav a:not(.btn){color:rgba(255,255,255,.72);font-size:15px}.nav nav a:hover{color:#fff}.btn.small{white-space:nowrap}
.btn{display:inline-block;padding:14px 26px;border-radius:14px;background:rgb(var(--p));color:#fff;font-weight:650;box-shadow:0 10px 30px -10px rgba(var(--p),.7);transition:transform .25s,box-shadow .25s}
.btn:hover{transform:translateY(-2px);box-shadow:0 16px 40px -12px rgba(var(--p),.85)}.btn.small{padding:9px 16px;font-size:14px}
.btn.ghost{background:transparent;color:var(--fg);border:1px solid var(--line);box-shadow:none}
.hero{position:relative;min-height:100vh;display:grid;align-items:center;padding:120px 7vw 80px;overflow:hidden;background:radial-gradient(1200px 700px at 75% 40%,rgba(var(--p),.22),transparent 60%),var(--dark);color:#fff}
#scene{position:absolute;inset:0;width:100%;height:100%}
.hero-text{position:relative;max-width:640px}.eyebrow{text-transform:uppercase;letter-spacing:.18em;font-size:13px;color:rgba(var(--p),1);font-weight:700}
h1{font-size:clamp(40px,7vw,86px);line-height:1.02;letter-spacing:-.035em;margin:14px 0 18px;background:linear-gradient(180deg,#fff,rgba(255,255,255,.72));-webkit-background-clip:text;background-clip:text;color:transparent}
.lead{font-size:clamp(18px,2vw,22px);color:rgba(255,255,255,.78);max-width:520px}
.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:30px}.hero .btn.ghost{color:#fff;border-color:rgba(255,255,255,.25)}
.scroll-hint{position:absolute;bottom:30px;left:50%;width:24px;height:38px;border:2px solid rgba(255,255,255,.4);border-radius:14px;transform:translateX(-50%)}
.scroll-hint:after{content:"";position:absolute;left:50%;top:7px;width:4px;height:8px;margin-left:-2px;border-radius:2px;background:#fff;animation:sh 1.8s infinite}
@keyframes sh{0%{opacity:0;transform:translateY(0)}40%{opacity:1}100%{opacity:0;transform:translateY(12px)}}
.section{padding:110px 7vw;max-width:1240px;margin:0 auto}h2{font-size:clamp(30px,4vw,48px);letter-spacing:-.03em;line-height:1.1;margin-bottom:34px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:22px;perspective:1100px}
.card{position:relative;padding:34px 28px;border-radius:24px;background:var(--card);border:1px solid var(--line);backdrop-filter:blur(10px);transform-style:preserve-3d;transition:transform .2s ease-out,box-shadow .3s;box-shadow:0 30px 60px -40px rgba(0,0,0,.35)}
.card:hover{box-shadow:0 40px 80px -40px rgba(var(--p),.55)}.card h3{font-size:22px;margin:10px 0 8px;transform:translateZ(30px)}.card p{color:var(--muted);transform:translateZ(18px)}
.num{font-weight:800;font-size:14px;color:rgb(var(--p));letter-spacing:.1em}
.split{display:grid;grid-template-columns:1.3fr 1fr;gap:60px;align-items:center}.split p{color:var(--muted);font-size:19px}
.perks{list-style:none;padding:0;display:grid;gap:14px}.perks li{padding:18px 22px;border-radius:16px;background:var(--card);border:1px solid var(--line);font-weight:600}
.perks li:before{content:"";display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:12px;background:rgb(var(--p));box-shadow:0 0 0 5px rgba(var(--p),.18)}
.cta{text-align:center;border-radius:32px;background:linear-gradient(135deg,rgba(var(--p),.16),transparent),var(--card);border:1px solid var(--line);margin-bottom:80px}
.contact{display:flex;justify-content:center;gap:34px;flex-wrap:wrap;margin:0 0 30px;color:var(--muted)}.todo{color:#d9534f;font-weight:600}
footer{display:flex;gap:26px;justify-content:center;flex-wrap:wrap;padding:40px 7vw 70px;color:var(--muted);font-size:14px;border-top:1px solid var(--line)}
.reveal{opacity:0;transform:translateY(28px);transition:opacity .9s cubic-bezier(.2,.7,.2,1),transform .9s cubic-bezier(.2,.7,.2,1)}.reveal.in{opacity:1;transform:none}
@media (max-width:760px){.nav nav a:not(.btn){display:none}.split{grid-template-columns:1fr;gap:30px}.section{padding:80px 22px}.hero{padding:120px 22px 80px}}
@media (prefers-reduced-motion:reduce){.reveal{opacity:1;transform:none;transition:none}html{scroll-behavior:auto}.scroll-hint:after{animation:none}}
"""

JS = r"""/* Demo-Webseite von JARVIS: 3D-Partikelform (Canvas), Kippkarten, Einblenden. Keine Bibliothek, kein Internet. */
(function () {
  'use strict';
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var root = getComputedStyle(document.documentElement).getPropertyValue('--p').trim() || '201,169,110';
  // Einblenden beim Scrollen
  var items = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !reduce) {
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }); }, { threshold: 0.15 });
    items.forEach(function (el) { io.observe(el); });
  } else { items.forEach(function (el) { el.classList.add('in'); }); }
  // 3D-Kippkarten
  document.querySelectorAll('.tilt').forEach(function (card) {
    card.addEventListener('mousemove', function (ev) {
      if (reduce) { return; }
      var r = card.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width - 0.5, y = (ev.clientY - r.top) / r.height - 0.5;
      card.style.transform = 'rotateX(' + (-y * 12).toFixed(2) + 'deg) rotateY(' + (x * 14).toFixed(2) + 'deg) translateZ(8px)';
    });
    card.addEventListener('mouseleave', function () { card.style.transform = ''; });
  });
  // 3D-Szene: 1400 Punkte wechseln zwischen Kugel, Ring und Welle
  var c = document.getElementById('scene'); if (!c || !c.getContext) { return; }
  var ctx = c.getContext('2d'), w = 0, h = 0, dpr = Math.min(window.devicePixelRatio || 1, 1.5), N = 1400, P = [], mx = 0, my = 0;
  function size() { w = c.clientWidth; h = c.clientHeight; c.width = w * dpr; c.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); }
  size(); addEventListener('resize', size);
  addEventListener('mousemove', function (e) { mx = e.clientX / w - 0.5; my = e.clientY / h - 0.5; });
  function shape(k, i) {
    var u = i / N, a = u * Math.PI * 2 * 37, b = Math.acos(1 - 2 * ((i * 0.618034) % 1));
    if (k === 0) { return [Math.sin(b) * Math.cos(a), Math.cos(b), Math.sin(b) * Math.sin(a)]; }
    if (k === 1) { var R = 0.85, r = 0.32, t = u * Math.PI * 2, p = a; return [(R + r * Math.cos(p)) * Math.cos(t), r * Math.sin(p), (R + r * Math.cos(p)) * Math.sin(t)]; }
    var gx = (i % 40) / 20 - 1, gz = Math.floor(i / 40) / 17.5 - 1; return [gx * 1.3, 0, gz * 1.3];
  }
  for (var i = 0; i < N; i++) { var s = shape(0, i); P.push({ x: s[0], y: s[1], z: s[2] }); }
  var t0 = performance.now(), form = 0, nextSwitch = 6000;
  function frame(now) {
    if (!reduce) { requestAnimationFrame(frame); }
    if (document.hidden) { return; }
    var t = (now - t0) / 1000;
    if (now - t0 > nextSwitch) { form = (form + 1) % 3; nextSwitch += 6000; }
    ctx.clearRect(0, 0, w, h);
    var ry = t * 0.18 + mx * 0.8, rx = 0.35 + my * 0.5, cy = Math.cos(ry), sy = Math.sin(ry), cx = Math.cos(rx), sx = Math.sin(rx);
    var scale = Math.min(w, h) * 0.34, ox = w > 760 ? w * 0.68 : w * 0.5, oy = h * 0.5;
    for (var i = 0; i < N; i++) {
      var q = P[i], s = shape(form, i);
      if (form === 2) { s[1] = Math.sin(s[0] * 3 + t * 1.6) * 0.18 + Math.cos(s[2] * 3 + t) * 0.18; }
      q.x += (s[0] - q.x) * 0.035; q.y += (s[1] - q.y) * 0.035; q.z += (s[2] - q.z) * 0.035;
      var x = q.x * cy - q.z * sy, z = q.x * sy + q.z * cy, y = q.y * cx - z * sx; z = q.y * sx + z * cx;
      var f = 2.6 / (3.2 + z), px = ox + x * scale * f, py = oy + y * scale * f, a = Math.max(0.08, Math.min(1, (1.4 - z) / 2)) * (w > 760 ? 1 : 0.45);
      ctx.fillStyle = 'rgba(' + root + ',' + a.toFixed(2) + ')';
      ctx.fillRect(px, py, 2.2 * f, 2.2 * f);
    }
  }
  requestAnimationFrame(frame);
})();
"""
