"""Auftrags-Zentrale (Stand 23): JARVIS arbeitet selbstständig – Schritt für Schritt sichtbar und hörbar.

Aufträge:
- "akquise":  Betriebe einer Branche in einem Ort suchen (Websuche) → ihre Webseiten prüfen → für den Betrieb mit
              der schwächsten Seite eine moderne Demo-Webseite bauen → Anschreiben und Besuchs-Leitfaden als ENTWURF.
- "webseite": Für einen genannten Betrieb (optional mit alter Webseite) direkt eine Demo-Webseite bauen.

Steuerung durch Noah:
- Jeder Auftrag startet nur auf Knopfdruck. „Stopp“ hält ihn nach dem laufenden Schritt an. Notaus stoppt alles.
- JARVIS SENDET NICHTS: keine E-Mails, keine Formulare, keine Anfragen an Betriebe. Kalt-E-Mails an Firmen sind in
  Deutschland ohne Einwilligung meist unzulässig (UWG § 7). Deshalb entstehen nur Entwürfe (Brief, Besuch, Anruf
  nach eigener Entscheidung).
- Websuche und Webseiten-Check sind erst nach `python3 -m jarvis werkstatt-an` erlaubt (Standard: aus).
- Ergebnisse liegen außerhalb von GitHub in ~/JARVIS/websites. Der Auftragsverlauf liegt in data/auftraege.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import secrets
import threading
import time
from pathlib import Path

from .site_builder import build_site, clean_content, content_prompt, demo_content, parse_json_object
from .site_check import check_site

KINDS = {"akquise": "Betriebe mit schwachen Webseiten finden", "webseite": "Webseite für einen Betrieb bauen",
         "projekt": "Projekt bauen", "bild": "Bild erzeugen"}
MAX_STEPS = 200
MAX_PARALLEL = 2
DEFAULTS = {"web_research_allowed": False, "output_dir": "~/JARVIS/websites", "max_betriebe": 5,
            "max_suchen": 4, "max_eur_pro_suche": 0.15, "chat_websuche": True, "projekte_dir": "~/JARVIS/projekte",
            "bilder_dir": "~/JARVIS/bilder", "max_eur_pro_projekt": 0.30, "max_bilder_pro_tag": 30}
FREIGABE_HINWEIS = "Freischalten im Terminal: python3 -m jarvis werkstatt-an (danach JARVIS neu starten)"
IMG_NAME = re.compile(r"\d{4}-\d{2}-\d{2}_[a-z0-9-]{1,48}(_\d{1,3})?\.(jpg|png)")

# Stand 24: Aufträge im Gespräch erkennen (Chat und Stimme)
_VERB = r"(?:bau|baue|erstell|erstelle|programmier|programmiere|entwickel|entwickle|mach|mache|generier|generiere|mal|male|zeichne|design|designe)"
BUILD_RE = re.compile(r"(?i)^\s*(?:hey\s+)?(?:jarvis[,!:]?\s*)?(?:kannst du\s+(?:mir\s+)?|bitte\s+)?" + _VERB + r"\b")
ASK_RE = re.compile(r"(?i)\b(kannst|könntest|würdest)\s+du\b.*\b(bauen|programmieren|erstellen|entwickeln|generieren|"
                    r"malen|zeichnen|designen|machen)\b")
EXPLAIN_RE = re.compile(r"(?i)\b(wie man|erklär|was ist|was sind|warum)\b")
BUILD_WORDS = re.compile(r"(?i)(\b(webseite|website|homepage|landingpage|landing page|app|spiel|game|tool|dashboard|"
                         r"animation|programm|anwendung|onepager|portfolio|quiz|timer|planer|3d-?szene)\b|rechner\b|spiel\b|app\b)")
IMAGE_WORDS = re.compile(r"(?i)\b(bild|bilder|foto|logo|illustration|grafik|poster|wallpaper|zeichnung|gemälde|cover|thumbnail)\b")
SEARCH_RE = re.compile(r"(?i)\b(such|find|recherchier)\w*\b(?:\s+(?:mir|bitte|mal|nach))*\s+(?P<branche>[\wäöüÄÖÜß&-]+(?:\s+[\wäöüÄÖÜß&-]+)?)"
                       r"\s+in\s+(?P<ort>[\wäöüÄÖÜß.-]+(?:\s+[\wäöüÄÖÜß.-]+)?)")
_STOP = {"mit", "die", "den", "der", "schlechten", "schlechte", "alten", "webseiten", "webseite"}


def detect_intent(text: str):
    """Erkennt einen Auftrag in natürlicher Sprache. Gibt einen Vorschlag zurück oder None."""
    t = (text or "").strip()
    if len(t) > 1500:
        return None
    m = SEARCH_RE.search(t)
    if m and re.search(r"(?i)(webseite|website|homepage|internetseite)", t) and re.search(r"(?i)(schlecht|alt|schwach|veraltet)", t):
        branche = " ".join(w for w in m.group("branche").split() if w.lower() not in _STOP) or m.group("branche")
        ort = " ".join(w for w in m.group("ort").split() if w.lower() not in _STOP).strip(" .")
        if ort:
            return {"art": "akquise", "branche": branche[:60], "ort": ort[:60]}
    if (BUILD_RE.search(t) or ASK_RE.search(t)) and not EXPLAIN_RE.search(t):
        if IMAGE_WORDS.search(t) and not BUILD_WORDS.search(t):
            return {"art": "bild", "beschreibung": t[:1000]}
        if BUILD_WORDS.search(t):
            return {"art": "projekt", "beschreibung": t[:1500]}
    return None


def get_runner(jarvis) -> "MissionRunner":
    """Ein gemeinsamer Auftrags-Dienst je JARVIS (Chat, Stimme und Auftrags-Seite sehen dieselben Aufträge)."""
    if getattr(jarvis, "_mission_runner", None) is None:
        jarvis._mission_runner = MissionRunner(jarvis)
    return jarvis._mission_runner
ID_RE = re.compile(r"[a-f0-9]{12}")


def settings(cfg: dict) -> dict:
    w = dict(DEFAULTS)
    if isinstance(cfg.get("werkstatt"), dict):
        w.update({k: v for k, v in cfg["werkstatt"].items() if k in DEFAULTS})
    w["web_research_allowed"] = w["web_research_allowed"] is True
    w["max_betriebe"] = max(1, min(int(w["max_betriebe"]), 8))
    w["max_suchen"] = max(1, min(int(w["max_suchen"]), 6))
    w["max_eur_pro_suche"] = max(0.01, min(float(w["max_eur_pro_suche"]), 0.5))
    w["max_eur_pro_projekt"] = max(0.01, min(float(w["max_eur_pro_projekt"]), 1.0))
    w["max_bilder_pro_tag"] = max(0, min(int(w["max_bilder_pro_tag"]), 150))
    w["chat_websuche"] = w["chat_websuche"] is True
    return w


def _clean(text: str, limit: int) -> str:
    return re.sub(r"[\x00-\x1f<>]", " ", str(text or "")).strip()[:limit]


class MissionStopped(Exception):
    pass


class Mission:
    def __init__(self, kind: str, params: dict):
        self.id = secrets.token_hex(6)
        self.kind = kind
        self.params = params
        self.status = "läuft"            # läuft | fertig | gestoppt | fehler
        self.steps: list = []
        self.started = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
        self.result: dict = {}
        self.stop_flag = threading.Event()
        self.done = threading.Event()        # gesetzt, wenn der Auftrag komplett beendet und gespeichert ist
        self.lock = threading.Lock()

    def say(self, text: str, art: str = "info", detail: str = "") -> None:
        with self.lock:
            if len(self.steps) < MAX_STEPS:
                self.steps.append({"n": len(self.steps), "zeit": time.strftime("%H:%M:%S"), "art": art,
                                   "text": _clean(text, 300), "detail": _clean(detail, 600)})

    def to_dict(self, since: int = 0) -> dict:
        with self.lock:
            return {"id": self.id, "art": self.kind, "titel": self.title(), "status": self.status,
                    "start": self.started, "schritte": [s for s in self.steps if s["n"] >= since],
                    "anzahl": len(self.steps), "ergebnis": self.result}

    def title(self) -> str:
        p = self.params
        if self.kind == "akquise":
            return f"{p.get('branche', '')} in {p.get('ort', '')}"
        if self.kind in ("projekt", "bild"):
            b = p.get("beschreibung", "")
            return b[:70] + ("…" if len(b) > 70 else "")
        return p.get("name", "Webseite")


class MissionRunner:
    def __init__(self, jarvis, folder: Path | None = None, opener=None, fetch_check=check_site):
        self.j = jarvis
        self.folder = Path(folder or Path(jarvis.cfg["data_dir"]) / "auftraege")
        self.missions: dict = {}
        self.check = fetch_check
        self.opener = opener
        self._lock = threading.Lock()
        self._load_history()

    # ------------------------------------------------------------------ Verwaltung
    def _load_history(self) -> None:
        if not self.folder.exists():
            return
        for f in sorted(self.folder.glob("*.json"))[-20:]:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                m = Mission(d["art"], d.get("params", {}))
                m.id, m.status, m.steps, m.started, m.result = d["id"], d["status"], d["schritte"], d["start"], d.get("ergebnis", {})
                if m.status == "läuft":
                    m.status = "gestoppt"         # nach einem Neustart läuft nichts von allein weiter
                m.done.set()
                if ID_RE.fullmatch(m.id):
                    self.missions[m.id] = m
            except (OSError, ValueError, KeyError, TypeError):
                continue

    def _save(self, m: Mission) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        d = m.to_dict()
        d["params"] = m.params
        (self.folder / f"{m.id}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    def get(self, mid: str):
        return self.missions.get(mid) if isinstance(mid, str) and ID_RE.fullmatch(mid) else None

    def recent(self) -> list:
        return sorted(self.missions.values(), key=lambda m: m.started, reverse=True)[:12]

    def running(self) -> int:
        return sum(1 for m in self.missions.values() if not m.done.is_set())

    def start(self, kind: str, params: dict, background: bool = True) -> Mission:
        if kind not in KINDS:
            raise ValueError("Unbekannter Auftrag.")
        self.j.kill.check()
        params = {k: _clean(v, 1500 if k == "beschreibung" else 400 if k == "wuensche" else 120) for k, v in params.items()
                  if k in ("branche", "ort", "name", "url", "wuensche", "beschreibung")}
        if kind in ("projekt", "bild") and len(params.get("beschreibung", "")) < 8:
            raise ValueError("Bitte beschreibe kurz, was ich bauen bzw. zeigen soll.")
        if kind == "akquise" and not (params.get("branche") and params.get("ort")):
            raise ValueError("Bitte Branche und Ort angeben (z. B. Restaurants · Bremen).")
        if kind == "webseite" and not params.get("name"):
            raise ValueError("Bitte den Namen des Betriebs angeben.")
        with self._lock:
            if self.running() >= MAX_PARALLEL:
                raise ValueError("Es laufen schon zwei Aufträge. Bitte warten oder einen stoppen.")
            m = Mission(kind, params)
            self.missions[m.id] = m
        self.j.audit.write("mission_start", mission=m.id, art=kind)
        if background:
            threading.Thread(target=self._run, args=(m,), daemon=True, name=f"auftrag-{m.id}").start()
        else:
            self._run(m)
        return m

    def stop(self, mid: str) -> bool:
        m = self.get(mid)
        if not m or m.status != "läuft":
            return False
        m.stop_flag.set()
        m.say("Stopp angefordert – ich halte nach diesem Schritt an.", "warn")
        return True

    # ------------------------------------------------------------------ Ablauf
    def _gate(self, m: Mission) -> None:
        if m.stop_flag.is_set():
            raise MissionStopped()
        if self.j.kill.is_active():
            raise MissionStopped("Notabschaltung")

    def _run(self, m: Mission) -> None:
        try:
            {"akquise": self._akquise, "webseite": self._webseite, "projekt": self._projekt, "bild": self._bild}[m.kind](m)
            m.status = "fertig"
        except MissionStopped:
            m.status = "gestoppt"
            m.say("Auftrag angehalten. Bis hierhin ist alles gespeichert.", "warn")
        except Exception as exc:  # noqa: BLE001 – verständlich melden, nie abstürzen
            m.status = "fehler"
            msg = str(exc)[:200]
            m.say(f"Das hat nicht geklappt: {msg}", "fehler", FREIGABE_HINWEIS if "nicht freigegeben" in msg else "")
            self.j.audit.write("mission_error", mission=m.id, error=type(exc).__name__)
        finally:
            try:
                self._save(m)
                self.j.audit.write("mission_end", mission=m.id, status=m.status, steps=len(m.steps))
            finally:
                m.done.set()

    def _test_mode(self) -> bool:
        return bool(getattr(self.j.llm.model, "is_test_mode", False))

    def _akquise(self, m: Mission) -> None:
        w = settings(self.j.cfg)
        b, o = m.params["branche"], m.params["ort"]
        m.say(f"Auftrag angenommen: Ich suche {b} in {o} mit schwachen Webseiten.", "start")
        if not w["web_research_allowed"]:
            m.say("Die Websuche ist noch ausgeschaltet. Ich habe nichts im Internet gesucht.", "warn",
                  "Einschalten mit einem Befehl im Terminal: python3 -m jarvis werkstatt-an")
            raise MissionStopped()
        if self._test_mode():
            m.say("Testmodus: Ohne echte KI kann ich nicht im Internet suchen.", "warn")
            raise MissionStopped()
        self._gate(m)
        m.say(f"Ich starte die Websuche nach {b} in {o}. Das dauert etwa 20 bis 60 Sekunden.", "info",
              f"Höchstens {w['max_suchen']} Suchen, Kostenlimit {w['max_eur_pro_suche']:.2f} €.")
        prompt = (f"Finde bis zu {w['max_betriebe']} echte, aktuell geöffnete Betriebe der Branche „{b}“ in {o} "
                  f"(Deutschland), die eine EIGENE Webseite haben. Bevorzuge kleine, inhabergeführte Betriebe, deren "
                  f"Webseite älter oder einfach wirkt. Keine Ketten, keine Plattform-Profile (Facebook, Instagram, "
                  f"Lieferando, Google Maps).\nAntworte am Ende NUR mit JSON: "
                  f'[{{"name": "…", "webseite": "https://…", "ort": "…", "hinweis": "kurz, warum"}}]')
        answer = self.j.llm.web_search(prompt, w["max_suchen"], w["max_eur_pro_suche"])
        cost = self.j.llm.last_cost_eur()
        found = _parse_businesses(answer, w["max_betriebe"])
        m.say(f"Websuche fertig: {len(found)} Betriebe mit eigener Webseite gefunden.", "ok",
              f"Kosten etwa {cost:.3f} €.")
        if not found:
            raise RuntimeError("Ich habe keine passenden Betriebe gefunden. Versuch eine andere Branche oder einen größeren Ort.")
        checked = []
        for biz in found:
            self._gate(m)
            m.say(f"Ich prüfe die Webseite von {biz['name']}.", "info", biz["webseite"])
            res = self.check(biz["webseite"])
            biz["check"] = res
            if res["punkte"] is None:
                m.say(f"{biz['name']}: nicht prüfbar – {res['befunde'][0]}", "warn")
                continue
            m.say(f"{biz['name']}: {res['punkte']} von 100 Punkten, {res['urteil']}.",
                  "ok" if res["punkte"] >= 75 else "warn", " · ".join(res["befunde"][:4]))
            checked.append(biz)
        if not checked:
            raise RuntimeError("Keine der Webseiten ließ sich prüfen.")
        checked.sort(key=lambda x: x["check"]["punkte"])
        target = checked[0]
        if target["check"]["punkte"] >= 75:
            m.say("Alle geprüften Webseiten sind schon ziemlich modern. Ich baue trotzdem einen Vorschlag für die schwächste.", "info")
        m.say(f"Größte Chance: {target['name']} mit {target['check']['punkte']} Punkten. Ich baue jetzt eine neue Webseite.", "start")
        m.result["betriebe"] = [{"name": x["name"], "webseite": x["webseite"], "punkte": x["check"]["punkte"],
                                 "urteil": x["check"]["urteil"]} for x in checked]
        self._build(m, target["name"], b, target.get("ort") or o, m.params.get("wuensche", ""), target["check"],
                    ranking=m.result["betriebe"])

    def _webseite(self, m: Mission) -> None:
        w = settings(self.j.cfg)
        p = m.params
        m.say(f"Auftrag angenommen: neue Webseite für {p['name']}.", "start")
        check = {"befunde": [], "titel": "", "punkte": None, "url": p.get("url", "")}
        if p.get("url"):
            if w["web_research_allowed"]:
                self._gate(m)
                m.say("Ich prüfe zuerst die alte Webseite.", "info", p["url"])
                check = self.check(p["url"])
                if check["punkte"] is None:
                    m.say(f"Alte Seite nicht prüfbar: {check['befunde'][0]}", "warn")
                else:
                    m.say(f"Alte Seite: {check['punkte']} von 100 Punkten, {check['urteil']}.", "warn" if check["punkte"] < 75 else "ok",
                          " · ".join(check["befunde"][:5]))
            else:
                m.say("Webseiten-Check ist ausgeschaltet – ich baue ohne Prüfung der alten Seite.", "info",
                      "Einschalten: python3 -m jarvis werkstatt-an")
        self._build(m, p["name"], p.get("branche", ""), p.get("ort", ""), p.get("wuensche", ""), check)

    def _build(self, m: Mission, name: str, branche: str, ort: str, wuensche: str, check: dict, ranking=None) -> None:
        self._gate(m)
        if self._test_mode():
            m.say("Testmodus: Ich nutze Standardtexte statt KI-Texten.", "info")
            content = demo_content(name, branche, ort)
        else:
            m.say("Ich schreibe Texte, Slogan und Farbkonzept mit Claude.", "info")
            raw = self.j.llm.complete("webseite", content_prompt(name, branche, ort, wuensche,
                                                                 [b for b in check.get("befunde", [])][:6], check.get("titel", "")))
            content = parse_json_object(raw)
            if not content:
                m.say("Die KI-Texte waren unbrauchbar – ich nehme Standardtexte.", "warn")
                content = demo_content(name, branche, ort)
            else:
                m.say(f"Texte fertig: „{_clean(content.get('slogan'), 90)}“", "ok",
                      f"Kosten etwa {self.j.llm.last_cost_eur():.3f} €.")
        self._gate(m)
        c = clean_content(content, name, branche, ort)
        m.say(f"Ich setze das Design zusammen: Stil {c['stil']}, 3D-Animation, Handy-Ansicht, Dunkelmodus.", "info")
        extra = {"Anschreiben-Entwurf.md": letter(c, check), "Besuchs-Leitfaden.md": visit_guide(c, check)}
        if ranking:
            extra["Vergleich.md"] = "# Geprüfte Betriebe\n\n" + "\n".join(
                f"- {r['name']}: {r['punkte']}/100 ({r['urteil']}) – {r['webseite']}" for r in ranking) + "\n"
        folder = build_site(c, Path(settings(self.j.cfg)["output_dir"]), extra)
        m.result.update({"ordner": str(folder), "name": c["name"], "seite": str(folder / "index.html")})
        m.say(f"Fertig! Die Webseite für {c['name']} liegt bereit.", "fertig", str(folder))
        m.say("Anschreiben und Besuchs-Leitfaden habe ich als Entwurf dazugelegt. Gesendet wurde nichts.", "ok",
              "Hinweis: Werbe-E-Mails an Firmen ohne Einwilligung sind meist unzulässig (UWG § 7). "
              "Besser: vorbeigehen, anrufen oder einen Brief schicken.")

    # ------------------------------------------------------------------ Stand 24: Projekte und Bilder
    def _projekt(self, m: Mission) -> None:
        from .ai_models import ModelBlocked
        from .strategy import strategy_model
        w = settings(self.j.cfg)
        idea = m.params["beschreibung"]
        m.say("Verstanden. Ich baue: " + idea[:160], "start")
        if self._test_mode():
            m.say("Testmodus: Ohne echte KI kann ich nicht programmieren.", "warn")
            raise MissionStopped()
        strong = strategy_model(self.j.cfg)
        m.say(f"Ich plane Aufbau, Design und Funktionen. {'Claude Sonnet' if strong else 'Claude'} schreibt jetzt den Code – "
              f"das dauert ein bis drei Minuten.", "info", f"Kostenlimit {w['max_eur_pro_projekt']:.2f} €.")
        self._gate(m)
        prompt = ("Aufgabe von Noah:\n" + idea + "\n\nBaue das als eine einzige, vollständige HTML-Datei.")
        try:
            raw = self.j.llm.build(prompt, model=strong, cap_eur=w["max_eur_pro_projekt"])
        except ModelBlocked:
            if strong is None:
                raise
            m.say("Sonnet ist nicht freigegeben – ich baue mit dem Standard-Modell.", "warn")
            raw = self.j.llm.build(prompt, cap_eur=w["max_eur_pro_projekt"])
        page = extract_html(raw)
        if not page:
            raise RuntimeError("Die KI hat keine vollständige HTML-Datei geliefert. Beschreib es bitte etwas genauer.")
        m.say(f"Code fertig: {len(page) // 1000} KB, Kosten etwa {self.j.llm.last_cost_eur():.3f} €.", "ok")
        self._gate(m)
        from .site_builder import slugify
        folder = _new_folder(Path(w["projekte_dir"]).expanduser(), slugify(idea[:40]))
        (folder / "index.html").write_text(page, encoding="utf-8")
        (folder / "AUFTRAG.txt").write_text(idea + "\n", encoding="utf-8")
        m.result.update({"ordner": str(folder), "name": idea[:60], "seite": str(folder / "index.html")})
        m.say("Fertig! Ich öffne es jetzt in deinem Browser.", "fertig", str(folder))
        self.open_result(m.id)

    def _bild(self, m: Mission) -> None:
        from .ai_models import ModelBlocked
        from .media import MediaError, credentials, generate_image
        w = settings(self.j.cfg)
        idea = m.params["beschreibung"]
        m.say("Verstanden. Ich erzeuge ein Bild: " + idea[:160], "start")
        account, token = credentials(self.j.llm.policy)
        if not (account and token):
            m.say("Für Bilder fehlt noch der kostenlose Cloudflare-Zugang.", "warn",
                  "Einrichten im Terminal: python3 -m jarvis bilder-einrichten (Anleitung: docs/27_Bilder_und_Bauen.md)")
            raise MissionStopped()
        folder = Path(w["bilder_dir"]).expanduser()
        today = dt.date.today().isoformat()
        used = len(list(folder.glob(today + "_*"))) if folder.exists() else 0
        if used >= w["max_bilder_pro_tag"]:
            raise RuntimeError(f"Tageslimit erreicht ({w['max_bilder_pro_tag']} Bilder). Morgen geht es weiter.")
        prompt = idea
        if not self._test_mode():
            try:
                m.say("Ich formuliere die Bildidee für das Bildmodell.", "info")
                better = self.j.llm.complete("bild", idea).strip()
                if 10 < len(better) < 1200:
                    prompt = better
            except ModelBlocked:
                pass
        prompt = self.j.llm._guard().prepare("", [], prompt)[2] if not self._test_mode() else prompt
        self._gate(m)
        m.say("Das Bildmodell FLUX malt jetzt (kostenlos über Cloudflare).", "info", prompt[:300])
        try:
            img = generate_image(prompt, account, token)
        except MediaError as exc:
            raise RuntimeError(str(exc)) from None
        from .site_builder import slugify
        folder.mkdir(parents=True, exist_ok=True)
        ext = "png" if img.startswith(b"\x89PNG") else "jpg"
        base, n = f"{today}_{slugify(idea[:40])}", 1
        path = folder / f"{base}.{ext}"
        while path.exists():
            n += 1
            path = folder / f"{base}_{n}.{ext}"
        path.write_bytes(img)
        m.result.update({"bild": path.name, "ordner": str(folder), "name": idea[:60]})
        m.say("Fertig! Hier ist dein Bild.", "fertig", str(path))

    def image_path(self, name: str):
        """Nur Bilder aus dem eigenen Bilder-Ordner, nur mit festem Namensmuster."""
        if not isinstance(name, str) or not IMG_NAME.fullmatch(name):
            return None
        p = Path(settings(self.j.cfg)["bilder_dir"]).expanduser() / name
        return p if p.is_file() else None

    def open_result(self, mid: str) -> str:
        """Öffnet die fertige Webseite im Standardbrowser (nur auf dem Mac, nur Ordner aus dieser Werkstatt)."""
        import subprocess
        import sys
        m = self.get(mid)
        if not m or not m.result.get("seite"):
            return "Für diesen Auftrag gibt es noch keine Webseite."
        page = Path(m.result["seite"]).resolve()
        w = settings(self.j.cfg)
        roots = [Path(w[k]).expanduser().resolve() for k in ("output_dir", "projekte_dir")]
        if not any(r in page.parents for r in roots) or not page.is_file():
            return "Die Datei liegt nicht in der Werkstatt und wird nicht geöffnet."
        if self.opener:
            self.opener(page)
            return "Geöffnet."
        if sys.platform != "darwin":
            return f"Bitte selbst öffnen: {page}"
        subprocess.run(["open", str(page)], timeout=10, check=False)       # Liste, keine Shell
        return "Die Webseite ist im Browser geöffnet."


def extract_html(text: str) -> str:
    """Holt die HTML-Datei aus der Antwort (mit oder ohne ```html-Rahmen)."""
    text = text or ""
    m = re.search(r"(?is)(<!doctype html.*?</html>)", text) or re.search(r"(?is)(<html.*?</html>)", text)
    return m.group(1).strip() + "\n" if m else ""


def _new_folder(root: Path, slug: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    base = f"{dt.date.today():%Y-%m-%d}_{slug}"
    folder, n = root / base, 2
    while folder.exists():
        folder, n = root / f"{base}_{n}", n + 1
    folder.mkdir()
    return folder


def _parse_businesses(text: str, limit: int) -> list:
    text = text or ""
    start, end = text.find("["), text.rfind("]")
    items = []
    if start != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            items = data if isinstance(data, list) else []
        except ValueError:
            items = []
    out, seen = [], set()
    for it in items:
        if not isinstance(it, dict):
            continue
        name, url = _clean(it.get("name"), 80), _clean(it.get("webseite") or it.get("website"), 200)
        if not name or not re.match(r"https?://[^\s/]+\.[^\s]+", url):
            continue
        host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()
        if host in seen or any(x in host for x in ("facebook.", "instagram.", "lieferando.", "google.", "tripadvisor.", "yelp.")):
            continue
        seen.add(host)
        out.append({"name": name, "webseite": url, "ort": _clean(it.get("ort"), 60), "hinweis": _clean(it.get("hinweis"), 160)})
        if len(out) >= limit:
            break
    return out


def letter(c: dict, check: dict) -> str:
    points = "\n".join(f"- {b}" for b in (check.get("befunde") or [])[:4]) or "- (keine Prüfung der alten Seite)"
    return f"""# ENTWURF – Brief an {c['name']} (nicht gesendet)

> Nur ein Entwurf. Vor dem Versand selbst prüfen und anpassen. Werbe-E-Mails an Firmen ohne vorherige Einwilligung
> sind in Deutschland meist unzulässig (UWG § 7). Empfehlung: persönlich vorbeigehen oder per Brief.

Sehr geehrte Damen und Herren,

ich bin auf {c['name']} aufmerksam geworden und habe mir Ihre Webseite angesehen. Dabei sind mir ein paar Punkte
aufgefallen, mit denen Sie online mehr Gäste bzw. Kunden gewinnen könnten:

{points}

Ich habe dazu unverbindlich einen modernen Entwurf gestaltet – mit Handy-Ansicht, schneller Ladezeit und einem
klaren Weg zu Kontakt bzw. Reservierung. Gern zeige ich Ihnen den Entwurf in 10 Minuten bei Ihnen vor Ort.

Mit freundlichen Grüßen

[Dein Name]
[Kontakt]
"""


def visit_guide(c: dict, check: dict) -> str:
    worst = (check.get("befunde") or ["Die Seite wirkt nicht mehr ganz aktuell."])[0]
    return f"""# Besuchs-Leitfaden: {c['name']}

1. **Ruhige Uhrzeit wählen** (z. B. 14–16 Uhr, nicht zur Stoßzeit). Nach der Inhaberin / dem Inhaber fragen.
2. **Einstieg (1 Satz):** „Ich mache moderne Webseiten für Betriebe hier in {c['ort'] or 'der Gegend'} und habe mir Ihre angeschaut.“
3. **Ein konkreter Punkt:** „{worst}“
4. **Zeigen statt erzählen:** Demo-Webseite auf dem Handy oder Laptop zeigen (offline möglich).
5. **Frage stellen:** „Wie kommen neue Gäste/Kunden heute zu Ihnen?“ – zuhören, nicht verkaufen.
6. **Nächster Schritt:** Kurzer Termin oder Visitenkarte dalassen. Kein Druck.

Notizen nach dem Gespräch: ______________________
"""
