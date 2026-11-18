"""Inhalts-Werkzeuge: Hooks, 60-Sekunden-Skripte, Untertitel (SRT), Captions, Hashtags und Postingplan.

Alles regelbasiert und offline. Für bessere Formulierungen baut `ai_prompt` einen fertigen Auftrag,
den du in Claude (oder ein anderes Modell) einfügst – so brauchst du keinen API-Schlüssel.
"""
from __future__ import annotations

import random
import re
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------- Hook-Formeln
# {thema} wird durch das Thema ersetzt. Jede Formel hat eine Kennung, damit die Analyse später
# zeigen kann, welcher Hook-Typ bei DEINEM Publikum funktioniert.
HOOKS = {
    "keiner_bemerkt": ("Das hat in GTA 6 fast niemand bemerkt: {thema}", "Neugier"),
    "stopp_scroll": ("Stopp. Bevor du GTA 6 startest, musst du das über {thema} wissen.", "Dringlichkeit"),
    "zahl": ("3 Dinge über {thema}, die dir Rockstar nicht erzählt.", "Liste"),
    "fakt_fake": ("Fakt oder Fake: {thema}?", "Interaktion"),
    "fehler": ("Mach diesen Fehler nicht in GTA 6: {thema}.", "Verlustangst"),
    "vergleich": ("GTA 5 gegen GTA 6: {thema}. Der Unterschied ist krass.", "Vergleich"),
    "geheimnis": ("Rockstar hat {thema} versteckt, und so findest du es.", "Neugier"),
    "zeit": ("{thema} in 60 Sekunden erklärt.", "Versprechen"),
    "frage": ("Wusstest du das über {thema}?", "Neugier"),
    "leak_realitaet": ("Der Leak von 2022 gegen das fertige Spiel: {thema}.", "Vergleich"),
    "unpopular": ("Unpopuläre Meinung: {thema}.", "Reibung"),
    "pov": ("POV: Du entdeckst als Erster {thema}.", "Identifikation"),
    "warnung": ("Lösch nicht deinen Spielstand, bevor du {thema} gesehen hast.", "Verlustangst"),
    "rang": ("Ich habe {thema} gerankt. Platz 1 überrascht dich.", "Liste"),
    "detail_zoom": ("Schau genau hin. Bei {thema} steckt ein Detail, das alles verändert.", "Neugier"),
    "challenge": ("Ich habe {thema} getestet, damit du es nicht musst.", "Versprechen"),
}

# ---------------------------------------------------------------------------- Serien
SERIES = {
    "Was keiner weiß": "Ein überprüfter, wenig bekannter Fakt pro Video. Kern-Serie für Insider-Ruf.",
    "Leak vs. Realität": "Vergleich: Was 2022 geleakt wurde und was im fertigen Spiel steckt.",
    "Easter Eggs": "Versteckte Details, Anspielungen, Geheimnisse. Ab Release jeden Tag neues Material.",
    "Leonida-Guide": "Orte, Regionen, Routen: Vice City, Keys, Grassrivers, Port Gellhorn, Ambrosia, Mount Kalaga.",
    "Fakt oder Fake": "Gerüchte prüfen. Zuschauer stimmen in den Kommentaren ab.",
    "Einsteiger-Tipps": "Konkrete Tipps für die ersten Stunden. Sehr speicherbar (Saves).",
    "Lucia & Jason": "Story, Figuren, Nebenfiguren, Theorien (ohne Spoiler-Hook, Spoiler mit Warnung).",
    "GTA 6 News": "Schnelle Nachrichten: Updates, Patches, Online-Modus, PC-Version.",
}

CTAS = [
    "Folg mir, morgen kommt Teil {n}.",
    "Schreib in die Kommentare, ob du das wusstest.",
    "Speicher das Video, damit du es im Spiel findest.",
    "Schick das deinem GTA-Kumpel.",
    "Fakt oder Fake? Stimm in den Kommentaren ab.",
]

BASE_TAGS = ["#gta6", "#gtavi", "#gta"]
SERIES_TAGS = {
    "Was keiner weiß": ["#gta6facts", "#gaming"],
    "Leak vs. Realität": ["#gta6leak", "#rockstargames"],
    "Easter Eggs": ["#eastereggs", "#gta6secrets"],
    "Leonida-Guide": ["#vicecity", "#leonida"],
    "Fakt oder Fake": ["#gta6theory", "#gaming"],
    "Einsteiger-Tipps": ["#gta6tips", "#gamingtipps"],
    "Lucia & Jason": ["#lucia", "#jason"],
    "GTA 6 News": ["#gta6news", "#gamingnews"],
}

STATUS_LABEL = {
    "bestaetigt": "offiziell bestätigt",
    "geruecht": "Gerücht",
    "leak": "Leak (nicht offiziell)",
    "spekulation": "Spekulation",
    "widerlegt": "widerlegt",
}

CAUTION = {
    "geruecht": " Wichtig: Das ist bisher nur ein Gerücht, nicht offiziell bestätigt.",
    "leak": " Wichtig: Das stammt aus einem Leak und ist nicht offiziell bestätigt.",
    "spekulation": " Wichtig: Das ist Spekulation, nicht offiziell bestätigt.",
}

WORD_RE = re.compile(r"\S+")


# ---------------------------------------------------------------------------- Hilfen
def words(text: str) -> list[str]:
    return WORD_RE.findall(text or "")


def speech_seconds(text: str, wpm: int = 150) -> float:
    """Geschätzte Sprechdauer. 150 Wörter/Minute ist ein zügiges, gut verständliches TikTok-Tempo."""
    wpm = max(60, min(260, int(wpm or 150)))
    return round(len(words(text)) / wpm * 60, 1)


def words_for_seconds(seconds: int, wpm: int = 150) -> int:
    return int(round(seconds * max(60, min(260, int(wpm or 150))) / 60))


def hook_options(topic: str, limit: int = 8, seed: int | None = None) -> list[dict]:
    topic = (topic or "").strip().rstrip(".?!") or "dieses Detail"
    keys = list(HOOKS)
    if seed is not None:
        random.Random(seed).shuffle(keys)
    out = []
    for key in keys[:max(1, limit)]:
        template, trigger = HOOKS[key]
        out.append({"type": key, "trigger": trigger, "text": _cap(template.format(thema=topic))})
    return out


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text



# ---------------------------------------------------------------------------- Skript
def build_script(topic: str, facts: list[dict] | None = None, hook_type: str = "keiner_bemerkt",
                 series: str = "Was keiner weiß", target_seconds: int = 60, part: int = 1,
                 wpm: int = 150) -> dict:
    """Baut ein Skript mit Zeitplan (Beats). Fakten liefern den Inhalt, ihr Status wird ehrlich benannt."""
    facts = [f for f in (facts or []) if f.get("status") != "widerlegt"]
    topic = (topic or "").strip() or (facts[0]["title"] if facts else "GTA 6")
    template, _trigger = HOOKS.get(hook_type, HOOKS["keiner_bemerkt"])
    hook = _cap(template.format(thema=topic.rstrip(".?!")))
    target_seconds = max(15, min(180, int(target_seconds or 60)))

    beats: list[dict] = [{"label": "Hook", "text": hook, "onscreen": _short(hook, 6)}]
    beats.append({"label": "Kontext", "text": "Ich bin heute in Leonida unterwegs und zeig dir, was die meisten übersehen.",
                  "onscreen": "Pass auf 👀"})

    if facts:
        for i, fact in enumerate(facts[:3], start=1):
            caution = CAUTION.get(fact.get("status", ""), "")
            detail = fact.get("detail") or fact.get("title", "")
            beats.append({"label": f"Punkt {i}", "text": f"{_ordinal(i)}: {detail}{caution}",
                          "onscreen": _short(fact.get("title", detail), 7)})
    else:
        for i in range(1, 4):
            beats.append({"label": f"Punkt {i}", "text": f"{_ordinal(i)}: [Hier kommt dein {i}. überprüfter Fakt zu {topic}]",
                          "onscreen": f"Punkt {i}"})

    beats.append({"label": "Payoff", "text": "Und genau deshalb lohnt es sich, in GTA 6 öfter mal anzuhalten und genau hinzuschauen.",
                  "onscreen": "Das ändert alles"})
    cta = CTAS[(part - 1) % len(CTAS)].format(n=part + 1)
    beats.append({"label": "CTA", "text": cta, "onscreen": "Folgen für Teil %d" % (part + 1)})

    _time_beats(beats, wpm)
    script = "\n\n".join(b["text"] for b in beats)
    seconds = speech_seconds(script, wpm)
    sources = [{"title": f.get("title"), "status": STATUS_LABEL.get(f.get("status", ""), ""),
                "source_name": f.get("source_name", ""), "source_url": f.get("source_url", "")} for f in facts[:3]]
    warnings = _script_warnings(script, seconds, target_seconds, facts)
    return {
        "title": f"{series}: {topic}"[:120],
        "series": series,
        "hook_type": hook_type,
        "hook": hook,
        "script": script,
        "onscreen": "\n".join(f"[{b['start']:.0f}s] {b['onscreen']}" for b in beats),
        "beats": beats,
        "seconds": seconds,
        "target_seconds": target_seconds,
        "target_words": words_for_seconds(target_seconds, wpm),
        "word_count": len(words(script)),
        "caption": build_caption(topic, series, hook),
        "hashtags": " ".join(build_hashtags(series, topic)),
        "sources": sources,
        "warnings": warnings,
    }


def _time_beats(beats: list[dict], wpm: int) -> None:
    t = 0.0
    for b in beats:
        dur = max(1.5, speech_seconds(b["text"], wpm))
        b["start"], b["end"] = round(t, 1), round(t + dur, 1)
        t += dur


def _script_warnings(script: str, seconds: float, target: int, facts: list[dict]) -> list[str]:
    out = []
    if seconds > target * 1.1:
        out.append(f"Zu lang: ca. {seconds:.0f}s gesprochen, Ziel {target}s. Kürze einen Punkt.")
    elif seconds < target * 0.6:
        out.append(f"Eher kurz: ca. {seconds:.0f}s. Kurz ist okay, wenn die Wiedergabequote dadurch steigt.")
    if not facts:
        out.append("Keine Fakten ausgewählt: Platzhalter durch geprüfte Infos ersetzen.")
    if any(f.get("status") in ("leak", "geruecht", "spekulation") for f in facts):
        out.append("Enthält unbestätigte Infos. Im Video und in der Caption klar als Gerücht/Leak kennzeichnen.")
    if any(not (f.get("source_url") or f.get("source_name")) for f in facts):
        out.append("Mindestens ein Fakt hat keine Quelle. Insider-Ruf hängt an belegbaren Infos.")
    if "—" in script:
        out.append("Gedankenstriche entfernen, das klingt beim Vorlesen nach KI.")
    return out


def _short(text: str, max_words: int) -> str:
    w = words(text)
    return " ".join(w[:max_words]) + ("…" if len(w) > max_words else "")


def _ordinal(i: int) -> str:
    return {1: "Erstens", 2: "Zweitens", 3: "Drittens"}.get(i, f"{i}.")


# ---------------------------------------------------------------------------- Caption & Hashtags
def build_hashtags(series: str, topic: str = "", limit: int = 5) -> list[str]:
    tags = list(BASE_TAGS) + SERIES_TAGS.get(series, ["#gaming"])
    t = topic.lower()
    if "vice" in t:
        tags.append("#vicecity")
    if "lucia" in t:
        tags.append("#lucia")
    if "online" in t:
        tags.append("#gtaonline")
    seen, out = set(), []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out[:limit]


def build_caption(topic: str, series: str, hook: str) -> str:
    first = _short(hook, 12)
    return (f"{first}\n\n{series} | GTA 6 {topic}\n"
            "Welches Detail kanntest du noch nicht? 👇")


# ---------------------------------------------------------------------------- Untertitel
def to_srt(script: str, wpm: int = 150, words_per_cue: int = 4) -> str:
    """Untertitel im SRT-Format (für CapCut, Premiere usw.). Kurze Blöcke wie bei TikTok üblich."""
    w = words(script)
    if not w:
        return ""
    sec_per_word = 60 / max(60, min(260, int(wpm or 150)))
    cues, t = [], 0.0
    for i in range(0, len(w), max(1, words_per_cue)):
        chunk = w[i:i + words_per_cue]
        dur = len(chunk) * sec_per_word
        cues.append((t, t + dur, " ".join(chunk)))
        t += dur
    lines = []
    for n, (a, b, text) in enumerate(cues, start=1):
        lines += [str(n), f"{_srt_time(a)} --> {_srt_time(b)}", text, ""]
    return "\n".join(lines)


def _srt_time(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


# ---------------------------------------------------------------------------- Postingplan
LAUNCH_THEMES = [
    ("GTA 6 News", "Countdown: Was du vor dem Start wissen musst", "stopp_scroll"),
    ("Einsteiger-Tipps", "Die ersten 10 Minuten in GTA 6", "fehler"),
    ("Was keiner weiß", "Details aus dem Intro", "keiner_bemerkt"),
    ("Leak vs. Realität", "Was vom Leak 2022 übrig geblieben ist", "leak_realitaet"),
    ("Easter Eggs", "Das erste Easter Egg in Vice City", "geheimnis"),
    ("Leonida-Guide", "Die Karte im Überblick", "zeit"),
    ("Fakt oder Fake", "Das größte Gerücht vor Release", "fakt_fake"),
    ("Lucia & Jason", "Wer ist wirklich Lucia?", "frage"),
    ("Einsteiger-Tipps", "Schnell Geld verdienen am Anfang", "challenge"),
    ("Easter Eggs", "Anspielungen auf GTA Vice City", "detail_zoom"),
    ("Vergleich", "GTA 5 gegen GTA 6: Physik und Details", "vergleich"),
    ("Was keiner weiß", "Kleine Details, die Rockstar versteckt hat", "zahl"),
]


def posting_plan(start: str, days: int = 7, posts_per_day: int = 2, times: str = "12:30,18:00,21:00",
                 series_weights: dict | None = None) -> list[dict]:
    """Erstellt Slots. Rotiert Serien, damit jeden Tag verschiedene Formate laufen."""
    try:
        d0 = date.fromisoformat(start)
    except (TypeError, ValueError):
        d0 = date.today()
    days = max(1, min(60, int(days)))
    posts_per_day = max(1, min(6, int(posts_per_day)))
    slot_times = [t.strip() for t in (times or "").split(",") if re.fullmatch(r"\d{1,2}:\d{2}", t.strip())]
    if not slot_times:
        slot_times = ["18:00"]
    while len(slot_times) < posts_per_day:
        slot_times.append(slot_times[-1])
    slots, n = [], 0
    for d in range(days):
        day = d0 + timedelta(days=d)
        for p in range(posts_per_day):
            series, topic, hook = LAUNCH_THEMES[n % len(LAUNCH_THEMES)]
            if series == "Vergleich":
                series = "Was keiner weiß"
            n += 1
            slots.append({
                "date": day.isoformat(),
                "time": slot_times[p],
                "planned_at": f"{day.isoformat()}T{slot_times[p]}",
                "series": series,
                "topic": topic,
                "hook_type": hook,
                "hook": _cap(HOOKS[hook][0].format(thema=topic)),
                "weekday": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][day.weekday()],
            })
    return slots


def countdown(release: str, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    try:
        target = datetime.fromisoformat(release)
    except (TypeError, ValueError):
        target = datetime(2026, 11, 19)
    delta = target - now
    secs = delta.total_seconds()
    if secs <= 0:
        days_since = (now.date() - target.date()).days
        return {"released": True, "days_since": days_since, "label": f"Tag {days_since + 1} nach Release"}
    return {"released": False, "days": int(secs // 86400), "hours": int(secs % 86400 // 3600),
            "label": f"Noch {int(secs // 86400)} Tage, {int(secs % 86400 // 3600)} Std."}


# ---------------------------------------------------------------------------- Checkliste & KI-Auftrag
PRE_POST_CHECKLIST = [
    "Hook in den ersten 1–2 Sekunden gesprochen UND als Text eingeblendet",
    "Bewegung oder Schnitt in den ersten 3 Sekunden",
    "Untertitel eingebrannt (viele schauen ohne Ton)",
    "Gerüchte/Leaks im Video als solche gekennzeichnet",
    "Keine Spoiler im Hook, Titelbild oder in den ersten Sekunden",
    "Eigenes Gameplay oder eigener Kommentar (nicht nur fremde Clips)",
    "Hochkant 9:16, 1080×1920, kein Wasserzeichen anderer Apps",
    "Caption: Hook-Zeile + Frage für Kommentare + 3–5 Hashtags",
    "Loop: Ende führt zurück zum Anfang oder kündigt Teil 2 an",
    "Nach 1 h, 24 h und 7 Tagen Zahlen ins Studio eintragen",
]


def ai_prompt(topic: str, facts: list[dict], series: str, target_seconds: int = 60, handle: str = "") -> str:
    lines = [
        f"Du schreibst ein TikTok-Skript (Deutsch, Du-Form) für den GTA-6-Account {handle or 'meines Kanals'}.",
        f"Serie: {series}. Thema: {topic}. Länge: {target_seconds} Sekunden gesprochen (ca. {words_for_seconds(target_seconds)} Wörter).",
        "Aufbau: Hook (max. 2 s), Kontext, 3 Punkte, Payoff, Call-to-Action, das Ende soll zum Anfang loopen.",
        "Regeln: Nur die Fakten unten verwenden. Gerüchte und Leaks klar als solche benennen. Nichts erfinden.",
        "Keine Spoiler im Hook. Kurze Sätze zum Vorlesen, keine Gedankenstriche, keine Emojis im Sprechtext.",
        "Gib zurück: 5 Hook-Varianten, das Skript, die Einblendungen pro Abschnitt, eine Caption und 4 Hashtags.",
        "",
        "Fakten:",
    ]
    if not facts:
        lines.append("- (keine ausgewählt)")
    for f in facts:
        src = f.get("source_name") or f.get("source_url") or "keine Quelle"
        lines.append(f"- [{STATUS_LABEL.get(f.get('status', ''), '?')}] {f.get('title')}: {f.get('detail', '')} (Quelle: {src})")
    return "\n".join(lines)


def ideas_from_facts(facts: list[dict], limit: int = 10) -> list[dict]:
    """Schlägt zu jedem noch ungenutzten Fakt eine passende Serie und einen Hook vor."""
    by_cat = {
        "leak": ("Leak vs. Realität", "leak_realitaet"),
        "karte": ("Leonida-Guide", "zeit"),
        "story": ("Lucia & Jason", "frage"),
        "easter-egg": ("Easter Eggs", "geheimnis"),
        "gameplay": ("Einsteiger-Tipps", "fehler"),
        "release": ("GTA 6 News", "stopp_scroll"),
    }
    out = []
    pool = sorted((f for f in facts if f.get("status") != "widerlegt"), key=lambda f: f.get("used_count", 0))
    for f in pool[:limit]:
        series, hook = by_cat.get(f.get("category", ""), ("Was keiner weiß", "keiner_bemerkt"))
        if f.get("status") in ("geruecht", "spekulation"):
            series, hook = "Fakt oder Fake", "fakt_fake"
        out.append({"fact_id": f["id"], "series": series, "hook_type": hook,
                    "hook": _cap(HOOKS[hook][0].format(thema=f["title"].rstrip(".?!"))), "topic": f["title"]})
    return out


def estimate_reach_score(hook: str, seconds: float, has_sources: bool) -> int:
    """Grobe Qualitätspunktzahl 0–100 fürs Skript. Keine Vorhersage der Aufrufe, nur eine Checkliste in Zahlen."""
    score = 50
    n = len(words(hook))
    score += 15 if 5 <= n <= 12 else (5 if n <= 16 else -10)
    if 20 <= seconds <= 65:
        score += 15
    elif seconds > 90:
        score -= 15
    if has_sources:
        score += 10
    if "?" in hook or any(k in hook.lower() for k in ("niemand", "keiner", "stopp", "fehler", "versteckt")):
        score += 10
    return max(0, min(100, score))

