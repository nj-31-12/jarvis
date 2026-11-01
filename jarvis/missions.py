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

KINDS = {"akquise": "Betriebe mit schwachen Webseiten finden", "webseite": "Webseite für einen Betrieb bauen"}
MAX_STEPS = 200
MAX_PARALLEL = 2
DEFAULTS = {"web_research_allowed": False, "output_dir": "~/JARVIS/websites", "max_betriebe": 5,
            "max_suchen": 4, "max_eur_pro_suche": 0.15}
ID_RE = re.compile(r"[a-f0-9]{12}")


def settings(cfg: dict) -> dict:
    w = dict(DEFAULTS)
    if isinstance(cfg.get("werkstatt"), dict):
        w.update({k: v for k, v in cfg["werkstatt"].items() if k in DEFAULTS})
    w["web_research_allowed"] = w["web_research_allowed"] is True
    w["max_betriebe"] = max(1, min(int(w["max_betriebe"]), 8))
    w["max_suchen"] = max(1, min(int(w["max_suchen"]), 6))
    w["max_eur_pro_suche"] = max(0.01, min(float(w["max_eur_pro_suche"]), 0.5))
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
        return sum(1 for m in self.missions.values() if m.status == "läuft")

    def start(self, kind: str, params: dict, background: bool = True) -> Mission:
        if kind not in KINDS:
            raise ValueError("Unbekannter Auftrag.")
        self.j.kill.check()
        params = {k: _clean(v, 400 if k == "wuensche" else 120) for k, v in params.items()
                  if k in ("branche", "ort", "name", "url", "wuensche")}
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
            if m.kind == "akquise":
                self._akquise(m)
            else:
                self._webseite(m)
            m.status = "fertig"
        except MissionStopped:
            m.status = "gestoppt"
            m.say("Auftrag angehalten. Bis hierhin ist alles gespeichert.", "warn")
        except Exception as exc:  # noqa: BLE001 – verständlich melden, nie abstürzen
            m.status = "fehler"
            m.say(f"Das hat nicht geklappt: {str(exc)[:200]}", "fehler")
            self.j.audit.write("mission_error", mission=m.id, error=type(exc).__name__)
        finally:
            self._save(m)
            self.j.audit.write("mission_end", mission=m.id, status=m.status, steps=len(m.steps))

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

    def open_result(self, mid: str) -> str:
        """Öffnet die fertige Webseite im Standardbrowser (nur auf dem Mac, nur Ordner aus dieser Werkstatt)."""
        import subprocess
        import sys
        m = self.get(mid)
        if not m or not m.result.get("seite"):
            return "Für diesen Auftrag gibt es noch keine Webseite."
        page = Path(m.result["seite"]).resolve()
        root = Path(settings(self.j.cfg)["output_dir"]).expanduser().resolve()
        if root not in page.parents or not page.is_file():
            return "Die Datei liegt nicht in der Werkstatt und wird nicht geöffnet."
        if self.opener:
            self.opener(page)
            return "Geöffnet."
        if sys.platform != "darwin":
            return f"Bitte selbst öffnen: {page}"
        subprocess.run(["open", str(page)], timeout=10, check=False)       # Liste, keine Shell
        return "Die Webseite ist im Browser geöffnet."


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
