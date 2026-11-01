"""Lokaler Aufgabenplaner (Version 5, Phase E).

Regeln, die der Code erzwingt:
  1. Die Aufgaben stehen FEST im Code (TASKS). Weder die KI noch eine Notiz kann neue anlegen.
  2. Jeder Termin („Slot“, z. B. 2026-11-02 07:00) wird höchstens EINMAL ausgeführt. Das erzwingt die Datenbank
     (eindeutiger Eintrag je Aufgabe und Slot) – auch wenn zwei JARVIS-Prozesse gleichzeitig laufen.
  3. Standard ist der TESTMODUS: Ergebnisse landen nur in data/aufgaben-test/, keine Meldungen, keine Notizen.
     Erst mit scheduler.mode = "aktiv" schreiben Aufgaben neue Notizen in 00_Inbox/JARVIS und melden sich.
  4. Jede Aufgabe ist einzeln pausierbar. Nach 3 Fehlern in Folge pausiert sie sich selbst.
  5. Aufgaben führen NIE externe Aktionen aus. Sie dürfen höchstens etwas vorschlagen (Freigabezentrale).
  6. Notaus stoppt den Planer vollständig.
  7. Jeder Lauf hat einen klaren Status (läuft · erledigt · fehlgeschlagen · abgebrochen · verpasst) und wird
     protokolliert – nur Kennung, Status und Fehlerart, nie Inhalte.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .db import LockedDB

MODES = ("test", "aktiv")
CATCH_UP_HOURS = 6          # verpasster Termin (Rechner war aus) wird höchstens so lange nachgeholt
STALE_MINUTES = 30          # ein „läuft“ ohne Ende gilt danach als abgebrochen (Absturz)
MAX_FAILURES = 3
RUNNING, DONE, FAILED, ABORTED, MISSED = "läuft", "erledigt", "fehlgeschlagen", "abgebrochen", "verpasst"
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# Beispielthemen – bitte mit deinem Ausbildungsrahmenplan abgleichen (keine offizielle Liste)
LEARNING_TOPICS = [
    "Neuwagenverkauf: Ablauf vom Angebot bis zum Kaufvertrag",
    "Fahrzeugfinanzierung: Kredit, Leasing und Ballonfinanzierung vergleichen",
    "Gebrauchtwagen: Bewertung, Hereinnahme und Sachmängelhaftung",
    "Werkstattauftrag: vom Kundenwunsch bis zur Rechnung",
    "Teile und Zubehör: Bestellung, Lagerhaltung, Inventur",
    "Gewährleistung und Garantie: Unterschiede und Fristen",
    "Fahrzeugzulassung und Versicherung (eVB, Kennzeichen)",
    "Buchführung: Belege, Konten, Umsatzsteuer im Autohaus",
    "Kundengespräche: Bedarfsanalyse und Einwandbehandlung",
    "Marketing im Autohaus: Aktionen, Online-Präsenz, Kundenbindung",
]


class TaskError(RuntimeError):
    pass


@dataclass(frozen=True)
class Task:
    id: str
    name: str
    description: str
    time: str                      # HH:MM (Ortszeit des Rechners)
    weekdays: tuple                # 0 = Montag … 6 = Sonntag
    run: Callable                  # run(jarvis) -> (Titel, Text)


# ---------------------------------------------------------------------- Aufgaben (nur lesen / Entwürfe)
def _briefing(j) -> tuple:
    if j.skills.is_enabled("briefing"):
        text = j.skills.run("briefing", "compose").text
    else:
        text = j.morning_briefing()
    return "Tagesbriefing", text


def _open_tasks(j) -> tuple:
    items = j.kb.open_checkboxes(limit=40)
    if not items:
        return "Offene Aufgaben", "Keine offenen Aufgaben (- [ ]) in deinen nicht vertraulichen Notizen."
    lines = ["Offene Aufgaben aus deinen Notizen (vertrauliche ausgenommen):", ""]
    for note, item in items:
        lines.append(f"- [ ] {item}  _(aus: {note})_")
    pend = j.gate.pending()
    if pend:
        lines += ["", f"Außerdem warten {len(pend)} Aktion(en) in der Freigabezentrale auf dich."]
    return "Offene Aufgaben", "\n".join(lines)


def _project_progress(j) -> tuple:
    from .profiles import profile_status
    rows = profile_status(j.kb)
    lines = ["| Bereich | Status | Profil |", "|---|---|---|"]
    lines += [f"| {e['project']['name']} | {e['project']['status']} | {e['state']} |" for e in rows]
    missing = [e["project"]["name"] for e in rows if e["state"] == "fehlt"]
    tip = (f"\n\nNächster Schritt: Profil für **{missing[0]}** anlegen (Wissen → Fehlende Profil-Entwürfe)."
           if missing else "\n\nAlle Bereiche haben ein Profil. Nächster Schritt: Ziele je Bereich prüfen.")
    return "Projektfortschritt", "\n".join(lines) + tip


def _learning(j) -> tuple:
    day = dt.date.today()
    topic = LEARNING_TOPICS[day.toordinal() % len(LEARNING_TOPICS)]
    text = (f"**Thema heute:** {topic}\n\n"
            "1. Erkläre das Thema in 5 Sätzen, als würdest du es einem Kunden erklären.\n"
            "2. Schreibe 3 Fachbegriffe dazu auf und erkläre sie kurz.\n"
            "3. Wo begegnet dir das Thema diese Woche im Betrieb? (Keine vertraulichen Firmendaten notieren.)\n"
            "4. Erstelle 2 Prüfungsfragen mit Lösung.\n\n"
            "_Hinweis: Beispielthemen, bitte mit deinem Ausbildungsrahmenplan abgleichen._")
    return "Lernaufgabe Ausbildung", text


def _business_ideas(j) -> tuple:
    ideas = [p for p in j.vault.list_notes("00_Inbox/JARVIS") if " Idee " in f" {p.stem} "]
    if not ideas:
        return "Geschäftsideen", "Keine neuen Ideen in der Inbox. Neue Idee festhalten: /idee <Text>"
    latest = sorted(ideas)[-1]
    idea = latest.stem.split(" Idee ", 1)[-1]
    analysis = j.llm.complete("idea", idea)          # läuft durch Erlaubnisliste, Notaus und Kostenbremse
    return "Geschäftsideen-Prüfung", f"Neueste Idee: **{idea}** ({len(ideas)} Ideen insgesamt)\n\n{analysis}"


def _recurring(j) -> tuple:
    commands = Counter()
    for e in j.audit.tail(2000):
        if e.get("event") == "message_in" and (e.get("details") or {}).get("command"):
            commands[e["details"]["command"]] += 1
    if not commands:
        return "Wiederkehrende Aufgaben", "Noch zu wenig Nutzung, um Muster zu erkennen."
    lines = ["Diese Befehle nutzt du am häufigsten (nur Zählung, keine Inhalte):", ""]
    lines += [f"- {cmd}: {n}×" for cmd, n in commands.most_common(5)]
    top = commands.most_common(1)[0]
    if top[1] >= 5:
        lines += ["", f"Vorschlag: „{top[0]}“ könnte eine feste Aufgabe werden. Das entscheidest du – "
                      f"JARVIS legt keine Aufgaben selbst an."]
    return "Wiederkehrende Aufgaben", "\n".join(lines)


def _coach(j) -> tuple:
    from .coach import run_coach
    return run_coach(j)          # Bericht mit Verbesserungen; Lektionen nur als Vorschlag (Noah bestätigt)


ALL_DAYS, WORKDAYS = tuple(range(7)), tuple(range(5))
TASKS = {t.id: t for t in [
    Task("briefing", "Morgendliches Tagesbriefing", "Termine, E-Mails, Ziele, Freigaben", "07:00", ALL_DAYS, _briefing),
    Task("offene_aufgaben", "Offene Aufgaben zusammenfassen", "Alle - [ ] aus nicht vertraulichen Notizen",
         "18:00", ALL_DAYS, _open_tasks),
    Task("projekte", "Projektfortschritt prüfen", "Stand aller Geschäftsbereiche", "08:00", (0,), _project_progress),
    Task("lernen", "Lernaufgabe für die Ausbildung", "Täglich ein Thema mit Übungsfragen", "19:00", WORKDAYS,
         _learning),
    Task("ideen", "Geschäftsideen analysieren", "Neueste Idee aus der Inbox bewerten", "10:00", (5,), _business_ideas),
    Task("muster", "Wiederkehrende Aufgaben erkennen", "Häufige Befehle zählen, Vorschläge machen", "11:00", (6,),
         _recurring),
    Task("coach", "Coach-Check", "Ziele, Aufgaben und Strategien prüfen, Verbesserungen und Lektionen vorschlagen",
         "20:00", (6,), _coach),
]}


# ---------------------------------------------------------------------- Planer
class Scheduler:
    def __init__(self, jarvis, db_path: str | Path, mode: str = "test", clock: Callable = time.time,
                 tasks: dict | None = None):
        if mode not in MODES:
            raise ValueError('scheduler.mode muss "test" oder "aktiv" sein.')
        self.j = jarvis
        self.mode = mode
        self.clock = clock
        self.tasks = tasks if tasks is not None else TASKS
        self.out_dir = Path(jarvis.cfg["data_dir"]) / "aufgaben-test"
        self.db = LockedDB(db_path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS task_state (
            task TEXT PRIMARY KEY, paused INTEGER NOT NULL DEFAULT 0, failures INTEGER NOT NULL DEFAULT 0, note TEXT)""")
        # UNIQUE(task, slot): dieselbe Aufgabe kann für denselben Termin nur EINMAL eingetragen werden
        self.db.execute("""CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL, slot TEXT NOT NULL, mode TEXT,
            started REAL, finished REAL, status TEXT, message TEXT, UNIQUE(task, slot))""")

    # ------------------------------------------------------------------ Zeitplan
    def _now(self) -> dt.datetime:
        return dt.datetime.fromtimestamp(self.clock())

    def due_slot(self, task: Task, now: dt.datetime | None = None):
        """Letzter fälliger Termin (≤ jetzt) innerhalb der letzten 7 Tage, oder None."""
        now = now or self._now()
        hh, mm = (int(x) for x in task.time.split(":"))
        for back in range(8):
            day = (now - dt.timedelta(days=back)).date()
            when = dt.datetime.combine(day, dt.time(hh, mm))
            if day.weekday() in task.weekdays and when <= now:
                return when
        return None

    def next_run(self, task: Task, now: dt.datetime | None = None):
        now = now or self._now()
        hh, mm = (int(x) for x in task.time.split(":"))
        for ahead in range(8):
            day = (now + dt.timedelta(days=ahead)).date()
            when = dt.datetime.combine(day, dt.time(hh, mm))
            if day.weekday() in task.weekdays and when > now:
                return when
        return None

    # ------------------------------------------------------------------ Zustand
    def _state(self, task_id: str) -> tuple:
        row = self.db.execute("SELECT paused, failures, note FROM task_state WHERE task=?", (task_id,)).fetchone()
        return (bool(row[0]), int(row[1]), row[2]) if row else (False, 0, None)

    def _set_state(self, task_id: str, paused: bool, failures: int, note: str | None) -> None:
        with self.db.transaction():
            cur = self.db.execute("UPDATE task_state SET paused=?, failures=?, note=? WHERE task=?",
                                  (int(paused), failures, note, task_id))
            if cur.rowcount == 0:
                self.db.execute("INSERT INTO task_state (task, paused, failures, note) VALUES (?,?,?,?)",
                                (task_id, int(paused), failures, note))

    def pause(self, task_id: str, via: str = "du") -> None:
        self._known(task_id)
        _, failures, _ = self._state(task_id)
        self._set_state(task_id, True, failures, f"pausiert ({via})")
        self.j.audit.write("task_state", task_id=task_id, state="pausiert", source=via)

    def resume(self, task_id: str, via: str = "du") -> None:
        self._known(task_id)
        self._set_state(task_id, False, 0, None)
        self.j.audit.write("task_state", task_id=task_id, state="aktiv", source=via)

    def _known(self, task_id: str) -> Task:
        task = self.tasks.get(task_id)
        if task is None:
            raise TaskError("Unbekannte Aufgabe.")
        return task

    def last_runs(self, limit: int = 20) -> list:
        rows = self.db.execute("SELECT task, slot, mode, started, finished, status, message FROM runs "
                               "ORDER BY id DESC LIMIT ?", (max(1, min(int(limit), 200)),)).fetchall()
        keys = ("task", "slot", "mode", "started", "finished", "status", "message")
        return [dict(zip(keys, r)) for r in rows]

    def overview(self) -> list:
        out = []
        for t in self.tasks.values():
            paused, failures, note = self._state(t.id)
            last = self.db.execute("SELECT slot, status, message, finished FROM runs WHERE task=? ORDER BY id DESC "
                                   "LIMIT 1", (t.id,)).fetchone()
            days = "täglich" if t.weekdays == ALL_DAYS else ", ".join(WEEKDAYS[d] for d in t.weekdays)
            out.append({"task": t, "status": "pausiert" if paused else "aktiv", "note": note, "failures": failures,
                        "plan": f"{days} {t.time}", "next": None if paused else self.next_run(t),
                        "last": dict(zip(("slot", "status", "message", "finished"), last)) if last else None})
        return out

    # ------------------------------------------------------------------ Ausführen
    def tick(self) -> list:
        """Ein Durchgang: führt alle fälligen, nicht pausierten Aufgaben aus. Gibt die Ergebnisse zurück."""
        if self.j.kill.is_active():
            return []
        self._mark_stale()
        now = self._now()
        results = []
        for task in self.tasks.values():
            paused, _, _ = self._state(task.id)
            slot = self.due_slot(task, now)
            if paused or slot is None:
                continue
            key = slot.strftime("%Y-%m-%d %H:%M")
            if now - slot > dt.timedelta(hours=CATCH_UP_HOURS):
                if self._claim(task.id, key, MISSED, "Rechner war aus – nicht nachgeholt"):
                    self.j.audit.write("task_missed", task_id=task.id, slot=key)
                continue
            results.append(self._execute(task, key))
        return [r for r in results if r is not None]

    def run_now(self, task_id: str) -> dict:
        """Manueller Testlauf (immer im Testmodus, unabhängig von der Einstellung)."""
        task = self._known(task_id)
        key = "manuell " + self._now().strftime("%Y-%m-%d %H:%M:%S")
        n = 2
        base = key
        while self.db.execute("SELECT 1 FROM runs WHERE task=? AND slot=?", (task.id, key)).fetchone():
            key = f"{base} ({n})"
            n += 1
        return self._execute(task, key, force_test=True)

    def _claim(self, task_id: str, slot: str, status: str, message: str | None = None) -> bool:
        """Trägt den Lauf ein. Gibt es ihn schon (auch aus einem anderen Prozess), wird NICHT ausgeführt."""
        import sqlite3
        try:
            self.db.execute("INSERT INTO runs (task, slot, mode, started, status, message) VALUES (?,?,?,?,?,?)",
                            (task_id, slot, self.mode, self.clock(), status, message))
            return True
        except sqlite3.IntegrityError:
            return False

    def _execute(self, task: Task, slot: str, force_test: bool = False):
        if not self._claim(task.id, slot, RUNNING):
            return None                     # bereits erledigt oder läuft gerade woanders
        mode = "test" if force_test else self.mode
        self.j.audit.write("task_start", task_id=task.id, slot=slot, mode=mode)
        try:
            self.j.kill.check()
            title, text = task.run(self.j)
            where = self._deliver(task, title, text, mode)
        except Exception as exc:  # noqa: BLE001 – jeder Fehler wird festgehalten, nichts stürzt ab
            msg = f"{type(exc).__name__}: {str(exc)[:160]}"
            self._finish(task.id, slot, FAILED, msg)
            paused, failures, note = self._state(task.id)
            failures += 1
            auto = failures >= MAX_FAILURES
            if auto:
                note = f"automatisch pausiert nach {failures} Fehlern in Folge"
            self._set_state(task.id, paused or auto, failures, note)
            self.j.audit.write("task_failed", task_id=task.id, slot=slot, error=type(exc).__name__,
                               failures=failures, paused=paused or auto)
            return {"task": task.id, "slot": slot, "status": FAILED, "message": msg}
        self._finish(task.id, slot, DONE, where)
        paused, _, note = self._state(task.id)
        self._set_state(task.id, paused, 0, note)
        self.j.audit.write("task_run", task_id=task.id, slot=slot, mode=mode, status=DONE)
        return {"task": task.id, "slot": slot, "status": DONE, "message": where, "title": title, "text": text}

    def _finish(self, task_id: str, slot: str, status: str, message: str) -> None:
        self.db.execute("UPDATE runs SET finished=?, status=?, message=? WHERE task=? AND slot=?",
                        (self.clock(), status, message, task_id, slot))

    def _mark_stale(self) -> None:
        """Läufe, die nach einem Absturz auf „läuft“ stehen geblieben sind, als abgebrochen kennzeichnen.
        Sie werden NICHT automatisch wiederholt (lieber einmal zu wenig als doppelt)."""
        limit = self.clock() - STALE_MINUTES * 60
        self.db.execute("UPDATE runs SET status=?, message=? WHERE status=? AND started<?",
                        (ABORTED, "unterbrochen (Absturz oder Neustart) – nicht wiederholt", RUNNING, limit))

    def _deliver(self, task: Task, title: str, text: str, mode: str) -> str:
        if mode == "aktiv":
            path = self.j.vault.write_draft(f"{title}", text, ["aufgabe", task.id])   # nur 00_Inbox/JARVIS
            self.j.notifier.notify(f"🗓️ {title} ist fertig: {path.name}", "normal")
            return f"Notiz {path.name}"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d_%H%M%S", time.localtime(self.clock()))
        name = f"{stamp}_{task.id}"
        for n in range(1, 100):
            path = self.out_dir / (f"{name}.md" if n == 1 else f"{name}-{n}.md")
            try:
                fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(f"# {title} (TESTMODUS)\n\n{text}\n")
            return f"Testergebnis {path.name}"
        raise TaskError("Kein freier Dateiname für das Testergebnis.")

    def close(self) -> None:
        self.db.close()


def run_forever(jarvis, scheduler: Scheduler, interval: int = 60, stop=None) -> None:
    """Endlosschleife für den Dienst. stop() → True beendet geordnet."""
    while not (stop and stop()):
        try:
            for r in scheduler.tick():
                print(f"[aufgaben] {r['task']} {r['slot']} → {r['status']}", flush=True)
        except Exception as exc:  # noqa: BLE001 – der Planer selbst darf nie abstürzen
            jarvis.audit.write("scheduler_error", error=type(exc).__name__)
        for _ in range(interval):
            if stop and stop():
                break
            time.sleep(1)


def valid_task_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z_]{2,30}", value or ""))
