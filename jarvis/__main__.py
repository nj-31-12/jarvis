"""Startpunkt:  python3 -m jarvis <befehl>

  demo        Kompletter Durchlauf mit simulierten Aktionen (empfohlen zum Start)
  chat        Telegram-Simulator im Terminal (ohne Internet, ohne Konto)
  briefing    Morgenbriefing anzeigen
  nacht       Nachtrecherche simulieren
  status      Systemstatus
  stop        Notabschaltung aktivieren
  resume      Notabschaltung aufheben (nur lokal möglich)
  audit       Protokoll prüfen und letzte Einträge zeigen
  secret      Neues Freigabe-Geheimnis erzeugen (für .env)
  telegram    Echten Telegram-Testbot starten (erst nach Einrichtung, siehe docs)
  web         Browseroberfläche starten (nur lokal: http://127.0.0.1:8765)
  web-passwort  Passwort für die Browseroberfläche festlegen (Phase 2, Schritt 2)
  web-status    Zeigt, ob ein Passwort gesetzt ist und ob die Anmeldung gesperrt ist
  daten-pruefen [Ordner]  Prüfsummen aller Dateien in data/ anzeigen (nur lesen) – für Backup-Vergleiche
  sicherheitscheck  Prüft Einstellungen und Dateirechte (nur lesen)
  ki-status     Welche KI-Modelle dürfen arbeiten und warum (nur lesen, Version 5)
  aufgaben      Aufgabenplaner starten (läuft dauerhaft; Standard: Testmodus, beenden mit ctrl + C)
  aufgaben-status            Alle geplanten Aufgaben mit Status und nächstem Termin (nur lesen)
  aufgabe-test <id>          Eine Aufgabe sofort im Testmodus ausführen
  aufgabe-pause <id> · aufgabe-fortsetzen <id>
  gesundheit    Gesundheitsprüfung (nur lesen). Rückgabe 0 = gut, 1 = Warnung, 2 = Fehler
  sicherung [Ordner]          Neue Sicherung des Datenordners anlegen (überschreibt nie etwas)
  sicherung-pruefen <Datei>   Sicherung vollständig prüfen (nur lesen)
  wiederherstellen <Datei> <neuer Ordner>  Sicherung in einen LEEREN Ordner auspacken
  chat-pruefen  Zeigt Chat-Antworten, deren Quellen inzwischen vertraulich/unauffindbar sind (nur lesen)
  vorlesen      Text mit der Mac-Stimme im Erzähler-Stil vorlesen (nur macOS, offline)
  wissen-import <Ordner|.zip>  Wissenspaket (Markdown-Notizen) ins Second Brain übernehmen (nur neue Dateien)
"""
from __future__ import annotations

import secrets
import sys

from .config import load_config, load_secrets
from .core import Jarvis

SIM_USER = 111111111      # simulierte "eigene" Telegram-ID
SIM_ATTACKER = 999999999  # simulierte fremde Telegram-ID


def _sim_jarvis() -> tuple[Jarvis, list]:
    cfg, sec = load_config(), load_secrets()
    cfg["telegram"]["allowed_user_ids"] = [SIM_USER]
    cfg["telegram"]["approval_chat_id"] = SIM_USER
    last_buttons: list = []

    def channel(text, silent, buttons):
        tag = "🔕 stumm" if silent else "🔔"
        print(f"\n┌─[{tag} Nachricht von JARVIS]\n" + "\n".join("│ " + l for l in text.splitlines()))
        if buttons:
            last_buttons.clear()
            for row in buttons:
                last_buttons.extend(row)
                print("│ " + "   ".join(f"[{label}]" for label, _ in row))
        print("└─")
    return Jarvis(cfg, sec, channel=channel), last_buttons


def demo() -> None:
    j, buttons = _sim_jarvis()
    def step(title, text):
        print(f"\n\n===== {title} =====\n> {text}")
        print(j.handle_text(text))

    step("1. Hilfe", "/hilfe")
    step("2. Geschäftsidee analysieren", "/idee Fitness-Meal-Prep-Guides als digitales Produkt über Shopify")
    step("3. Post vorbereiten (braucht Freigabe)", "/post 5 Fehler beim Muskelaufbau")
    ok_data = next(d for label, d in buttons if "Freigeben" in label)
    action_id = ok_data.split(":")[1]

    print("\n\n===== 4. Angriffstests =====")
    print("Fremder Benutzer drückt 'Freigeben':  ", j.on_button(ok_data, SIM_ATTACKER, SIM_ATTACKER))
    forged = f"ok:{action_id}:AAAAAAAAAAAAAAAAAAAA"
    print("Gefälschte Signatur:                  ", j.on_button(forged, SIM_USER, SIM_USER))
    try:
        j.gate.execute(action_id)
    except Exception as exc:  # noqa: BLE001
        print("Direkte Ausführung ohne Freigabe:     ", f"⛔ {exc}")
    print("Verbotene Aktion (Kauf):              ", end=" ")
    try:
        j.gate.propose("purchase", {"artikel": "Kurs"}, "Test")
    except Exception as exc:  # noqa: BLE001
        print(f"⛔ {exc}")

    print("\n\n===== 5. Du drückst 'Freigeben' =====")
    print(j.on_button(ok_data, SIM_USER, SIM_USER))
    print("Gleicher Button nochmal (Replay):     ", j.on_button(ok_data, SIM_USER, SIM_USER))

    step("6. E-Mail vorbereiten und ablehnen", "/mail coach@beispiel.de | Kooperation | Hallo, ich hätte Interesse …")
    no_data = next(d for label, d in buttons if "Ablehnen" in label)
    print(j.on_button(no_data, SIM_USER, SIM_USER))

    step("7. Nachtrecherche (Meldungen landen nachts in der Warteschlange)", "/nacht")
    step("8. Morgenbriefing", "/briefing")
    step("9. Notabschaltung", "/stop")
    step("10. Nach Notabschaltung", "/idee Test")
    j.kill.release()
    print("\n(Notabschaltung lokal wieder aufgehoben.)")
    step("11. Status", "/status")
    print("\nFertig. Ergebnisse: data/vault (Obsidian), data/sandbox/outbox (simulierte Aktionen), data/audit.jsonl")


def chat() -> None:
    j, buttons = _sim_jarvis()
    print("JARVIS Telegram-Simulator. Tippe wie in Telegram (z. B. /hilfe).")
    print("Buttons: 'ok' = Freigeben, 'nein' = Ablehnen, 'fremd' = fremder Nutzer drückt Freigeben, 'sprach' = Sprachnachricht, 'exit' = Ende.\n")
    while True:
        try:
            text = input("Du > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text in ("exit", "quit"):
            break
        if text in ("ok", "nein", "fremd"):
            want = "Ablehnen" if text == "nein" else "Freigeben"
            data = next((d for label, d in buttons if want in label), None)
            if not data:
                print("Kein Button vorhanden.")
                continue
            user = SIM_ATTACKER if text == "fremd" else SIM_USER
            print(j.on_button(data, user, user))
            continue
        if text == "sprach":
            print(j.handle_voice(12))
            continue
        print(j.handle_text(text))


def _auth_store():
    from .audit import AuditLog
    from .web_auth import AuthStore
    cfg = load_config()
    from pathlib import Path
    data = Path(cfg["data_dir"])
    return AuthStore(data, AuditLog(data / "audit.jsonl"))


def web_password() -> None:
    import getpass
    from .web_auth import MIN_PASSWORD_LENGTH, AuthError, check_password_rules
    store = _auth_store()
    replace = False
    if store.is_configured():
        answer = input("Es ist bereits ein Passwort gesetzt. Wirklich ersetzen? (ja/nein) ").strip().lower()
        if answer != "ja":
            print("Nichts geändert.")
            return
        replace = True
    username = input("Benutzername [inhaber]: ").strip() or "inhaber"
    print(f"Wähle ein Passwort mit mindestens {MIN_PASSWORD_LENGTH} Zeichen, z. B. vier zufällige Wörter.")
    print("Beim Tippen wird nichts angezeigt – das ist normal.")
    while True:
        pw1 = getpass.getpass("Passwort: ")
        problems = check_password_rules(pw1, username)
        if problems:
            print("Bitte ein anderes Passwort: " + ", ".join(problems))
            continue
        if getpass.getpass("Passwort wiederholen: ") != pw1:
            print("Die Eingaben stimmen nicht überein. Noch einmal.")
            continue
        break
    print("Speichere (dauert etwa eine Sekunde) …")
    try:
        store.set_password(username, pw1, replace=replace)
    except AuthError as exc:
        print(f"⛔ {exc}")
        return
    print(f"✅ Passwort für '{username}' gespeichert (nur als Hash, Datei: data/web_auth.json, Rechte 600).")


def start_web() -> None:
    from pathlib import Path
    from .server import apply_upgrades, instance_lock, make_backup, pending_upgrades, preflight
    from .chat import pending_migration
    cfg = load_config()
    chat_db = Path(cfg["data_dir"]) / "chat.db"
    missing = pending_migration(chat_db)
    upgrades = pending_upgrades(cfg)
    if upgrades:
        # Keine stille Umstellung (seit 4.2): erst zeigen, dann fragen, dann vollständig sichern
        print("Deine Daten stammen aus einer älteren JARVIS-Version. Version 5 würde Folgendes ERGÄNZEN:")
        for u in upgrades:
            print("  - " + u)
        print("Gelöscht oder überschrieben wird nichts. Neu angelegt werden außerdem data/skills.db und data/tasks.db.")
        print("Vorher wird automatisch eine vollständige Sicherung angelegt (Ordner sicherungen/).")
        if input("Jetzt umstellen und starten? (ja/nein) ").strip().lower() != "ja":
            print("Abgebrochen. Es wurde nichts verändert.")
            return
        print(f"✅ Sicherung vor der Umstellung: {make_backup(cfg)}")
        apply_upgrades(cfg)                       # sofort ergänzen, damit die Frage nur einmal kommt
    if not _auth_store().is_configured():
        print("Bevor die Oberfläche startet, legen wir ein Passwort fest.\n")
        web_password()
        if not _auth_store().is_configured():
            return
    problems = [t for lvl, t in preflight(cfg) if lvl == "fehler"]
    for lvl, text in preflight(cfg):
        if lvl != "ok":
            print(("⛔ " if lvl == "fehler" else "⚠️  ") + text)
    if problems and cfg["server"]["mode"] == "server":
        print("Start abgebrochen (Server-Modus). Bitte die Punkte oben beheben.")
        raise SystemExit(2)
    with instance_lock(cfg["data_dir"], "web"):
        _run_web(cfg, missing)


def _run_web(cfg: dict, missing: list) -> None:
    from pathlib import Path
    from .web import WebApp, serve
    from .web_auth import AuthStore
    jarvis = Jarvis(cfg, load_secrets())
    # Ein gemeinsames Protokoll für Anmeldung und JARVIS, damit die Prüfkette konsistent bleibt
    store = AuthStore(Path(cfg["data_dir"]), jarvis.audit)
    app = WebApp(cfg, store, jarvis)
    if app.chat is not None and app.chat.store.migration_backup:
        jarvis.audit.write("chat_db_migrated", backup=app.chat.store.migration_backup.name, added=missing)
        print(f"✅ Chatverlauf umgestellt. Sicherung: data/{app.chat.store.migration_backup.name}")
    serve(app, cfg["web"]["host"])


def web_status() -> None:
    store = _auth_store()
    if not store.is_configured():
        print("Noch kein Passwort gesetzt. Befehl: python3 -m jarvis web-passwort")
        return
    user = store.username()
    locked = store.locked_seconds(user)
    print(f"Benutzer: {user}")
    print(f"Anmeldung: {'gesperrt, noch ' + str(locked // 60 + 1) + ' Min.' if locked else 'frei'}")
    print("Browseroberfläche: noch nicht gebaut (Schritt 3).")


def data_fingerprint(folder) -> tuple:
    """Prüfsummen aller Dateien (nur lesen). Gibt (Liste, Gesamt-Prüfsumme) zurück."""
    import hashlib
    import os
    from pathlib import Path
    root = Path(folder)
    rows = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames.sort()
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if p.is_symlink():
                continue
            h = hashlib.sha256()
            with p.open("rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            rows.append((p.relative_to(root).as_posix(), p.stat().st_size, h.hexdigest()))
    total = hashlib.sha256("\n".join(f"{r}|{s}|{d}" for r, s, d in rows).encode()).hexdigest()
    return rows, total


def check_data(folder=None) -> None:
    from pathlib import Path
    folder = Path(folder) if folder else Path(load_config()["data_dir"])
    if not folder.is_dir():
        print(f"Ordner nicht gefunden: {folder}")
        return
    rows, total = data_fingerprint(folder)
    for rel, size, digest in rows:
        print(f"{digest[:16]}  {size:>9}  {rel}")
    print(f"\n{len(rows)} Dateien · Gesamt-Prüfsumme: {total}")
    print("Gleiche Gesamt-Prüfsumme in zwei Ordnern = identische Daten.")
    wal = [r for r, size, _ in rows if r.endswith("-wal") and size > 0]
    if wal:
        print("\n⚠️ Hinweis: " + ", ".join(wal) + " enthält noch nicht abgeschlossene Änderungen. Läuft JARVIS gerade?")
        print("   Vor dem Kopieren JARVIS beenden (ctrl + C) und immer den GANZEN data-Ordner kopieren.")


def check_chat() -> None:
    """Nur lesen: listet zurückgehaltene Chat-Antworten. Ändert und löscht nichts."""
    from pathlib import Path
    import time as _t
    from .chat import ChatService, ChatStore, pending_migration
    cfg = load_config()
    db = Path(cfg["data_dir"]) / "chat.db"
    if not db.exists():
        print("Noch kein Chatverlauf vorhanden.")
        return
    if pending_migration(db):
        print("Der Chatverlauf stammt aus einer älteren Version. Er enthält noch keine Quellenangaben, also auch "
              "keine zurückzuhaltenden Antworten. Es wurde nichts verändert.")
        return
    jarvis = Jarvis(cfg, load_secrets())
    store = ChatStore(db, allow_migration=False)
    try:
        affected = ChatService(jarvis, store).affected_messages()
        if not affected:
            print("✅ Keine zurückgehaltenen Antworten. Alle Quellen sind weiterhin teilbar.")
            return
        print(f"⚠️ {len(affected)} Antwort(en) zurückgehalten (werden nicht angezeigt und nicht an die KI gegeben):\n")
        for m in affected:
            print(f"  Nachricht {m['id']} · Gespräch {m['conv']} · {_t.strftime('%d.%m.%Y %H:%M', _t.localtime(m['ts']))}")
            print(f"    Grund: {m['reason']}")
        print("\nEs wurde nichts gelöscht. Endgültiges Schwärzen nur im Browser-Chat nach Passwort-Bestätigung.")
    finally:
        store.close()
        jarvis.close()


def security_report(cfg: dict) -> list[tuple[str, str]]:
    """NUR LESEN: prüft Einstellungen und Dateirechte. Gibt (Stufe, Text) zurück; Stufe: ok · warnung · fehler."""
    import stat as _stat
    from pathlib import Path
    from .config import PROJECT_ROOT
    out = []
    data = Path(cfg["data_dir"])
    env = PROJECT_ROOT / ".env"
    if env.exists() and env.stat().st_mode & (_stat.S_IRGRP | _stat.S_IROTH):
        out.append(("fehler", ".env ist für andere Benutzer lesbar → im Terminal: chmod 600 .env"))
    for name in ("web_auth.json", ".approval_secret"):
        f = data / name
        if f.exists() and f.stat().st_mode & (_stat.S_IRGRP | _stat.S_IROTH):
            out.append(("fehler", f"data/{name} ist für andere Benutzer lesbar → chmod 600 data/{name}"))
    if data.exists() and data.stat().st_mode & _stat.S_IROTH:
        out.append(("warnung", "Der data-Ordner ist für andere Benutzer dieses Macs lesbar → chmod 700 data"))
    if cfg["web"].get("host") not in ("127.0.0.1", "localhost", "::1"):
        out.append(("fehler", "Die Browseroberfläche ist nicht auf diesen Rechner beschränkt (web.host)."))
    if cfg["web"].get("approvals_enabled"):
        out.append(("warnung", "Freigaben im Browser sind eingeschaltet. Nur mit Bestätigungscode nutzen."))
    if cfg.get("privacy", {}).get("external_ai_allowed"):
        out.append(("warnung", "Externe KI ist erlaubt. Prüfe, ob das gewollt ist (privacy.external_ai_allowed)."))
    else:
        out.append(("ok", "Keine Übertragung an externe KI-Dienste erlaubt (privacy.external_ai_allowed = false)."))
    from .ai_models import ModelPolicy
    for name, kind, state, why in ModelPolicy(cfg, None, load_secrets()).overview():
        if name != "mock" and state == "erlaubt":
            out.append(("warnung", f"Externes KI-Modell '{name}' ist freigegeben. Anfragen verlassen deinen Rechner "
                                   f"(sensible Daten werden vorher entfernt)."))
    if cfg.get("ai", {}).get("active_model", "mock") != "mock":
        out.append(("warnung", f"Aktives KI-Modell ist '{cfg['ai']['active_model']}' (nicht das Testmodell)."))
    else:
        out.append(("ok", "Aktives KI-Modell: eingebautes Testmodell (offline, kostenlos)."))
    if not cfg.get("knowledge", {}).get("confidential_terms"):
        out.append(("warnung", "Keine eigenen geschützten Begriffe eingetragen (knowledge.confidential_terms), "
                               "z. B. der Name deines Ausbildungsbetriebs."))
    if not any(level == "fehler" for level, _ in out):
        out.append(("ok", "Keine kritischen Einstellungen gefunden."))
    return out


def security_check() -> None:
    icons = {"ok": "✅", "warnung": "⚠️ ", "fehler": "⛔"}
    for level, text in security_report(load_config()):
        print(f"{icons[level]} {text}")
    print("\nDiese Prüfung liest nur. Sie ersetzt keine Datenschutzgarantie.")


def ai_status() -> None:
    """NUR LESEN: Erlaubnisliste der KI-Modelle anzeigen. Schlüssel werden nie angezeigt."""
    from .ai_models import ModelPolicy
    cfg = load_config()
    print(f"Aktives Modell: {cfg.get('ai', {}).get('active_model', 'mock')}")
    print(f"Externe KI grundsätzlich erlaubt: {'ja' if cfg.get('privacy', {}).get('external_ai_allowed') is True else 'nein'}\n")
    for name, kind, state, why in ModelPolicy(cfg, None, load_secrets()).overview():
        print(f"{'✅' if state == 'erlaubt' else '⛔'} {name} · {kind} · {state}\n   {why}")
    print("\nDiese Anzeige liest nur. Unbekannte Modelle sind immer gesperrt.")


def tasks_status(j) -> None:
    print(f"Modus: {j.scheduler.mode} ({'Ergebnisse nur in data/aufgaben-test/' if j.scheduler.mode == 'test' else 'neue Notizen in 00_Inbox/JARVIS'})\n")
    for row in j.scheduler.overview():
        t, last = row["task"], row["last"]
        nxt = row["next"].strftime("%d.%m. %H:%M") if row["next"] else "–"
        print(f"{'⏸' if row['status'] == 'pausiert' else '▶'} {t.id:<16} {t.name} · {row['plan']} · nächster Lauf {nxt}")
        if row["note"]:
            print(f"   Hinweis: {row['note']}")
        if last:
            print(f"   Letzter Lauf {last['slot']}: {last['status']} {('– ' + last['message']) if last['message'] else ''}")


def tasks_loop(cfg: dict) -> None:
    from .scheduler import run_forever
    from .server import install_stop_handler, instance_lock
    stopped = []
    with instance_lock(cfg["data_dir"], "aufgaben"):
        j = Jarvis(cfg, load_secrets())
        try:
            install_stop_handler(lambda: stopped.append(True))
            print(f"Aufgabenplaner läuft (Modus: {j.scheduler.mode}). Beenden mit ctrl + C.", flush=True)
            try:
                run_forever(j, j.scheduler, stop=lambda: bool(stopped))
            except KeyboardInterrupt:
                pass
        finally:
            j.close()
            print("Aufgabenplaner beendet.", flush=True)


def health() -> int:
    from .server import health_exit_code, health_report
    icons = {"ok": "✅", "warnung": "⚠️ ", "fehler": "⛔"}
    report = health_report(load_config())
    for level, area, text in report:
        print(f"{icons[level]} {area}: {text}")
    code = health_exit_code(report)
    print(["\nAlles in Ordnung.", "\nLäuft, aber bitte die Warnungen ansehen.", "\nFEHLER – bitte beheben."][code])
    return code


def backup(target=None) -> None:
    from .server import make_backup, verify_backup
    path = make_backup(load_config(), target)
    manifest = verify_backup(path)
    print(f"✅ Sicherung angelegt und geprüft: {path}")
    print(f"   {len(manifest['dateien'])} Dateien. Enthält Passwort-Hashes – nur verschlüsselt auf andere Geräte kopieren.")
    print("   Alte Sicherungen werden NICHT automatisch gelöscht.")


def backup_check(archive) -> None:
    from .server import verify_backup
    manifest = verify_backup(archive)
    print(f"✅ Sicherung vollständig und unverändert ({len(manifest['dateien'])} Dateien, erstellt {manifest['erstellt']}).")


def restore(archive, target) -> None:
    from .server import restore_backup
    path = restore_backup(archive, target)
    print(f"✅ Wiederhergestellt nach {path}")
    print("   Es wurde nichts überschrieben. Zum Benutzen in config/jarvis.json \"data_dir\" auf diesen Ordner setzen")
    print("   oder JARVIS mit JARVIS_DATA_DIR=<Ordner> starten (siehe docs/19).")


def read_aloud(text: str) -> None:
    from .speech import NARRATOR, mac_say
    text = text or "Guten Morgen. Während du geschlafen hast, habe ich drei Möglichkeiten gefunden. Eine davon könnte alles verändern."
    print(mac_say(text, NARRATOR))


def main(argv: list[str]) -> None:
    cmd = argv[1] if len(argv) > 1 else "hilfe"
    if cmd == "demo":
        return demo()
    if cmd == "chat":
        return chat()
    if cmd == "telegram":
        from .telegram_bot import run
        return run()
    if cmd == "web":
        return start_web()
    if cmd == "sicherheitscheck":
        return security_check()
    if cmd == "gesundheit":
        raise SystemExit(health())
    if cmd == "sicherung":
        return backup(argv[2] if len(argv) > 2 else None)
    if cmd == "sicherung-pruefen" and len(argv) > 2:
        return backup_check(argv[2])
    if cmd == "wiederherstellen":
        if len(argv) < 4:
            print("Bitte so: python3 -m jarvis wiederherstellen <Sicherung.tar.gz> <neuer leerer Ordner>")
            return None
        return restore(argv[2], argv[3])
    if cmd == "ki-status":
        return ai_status()
    if cmd == "web-passwort":
        return web_password()
    if cmd == "web-status":
        return web_status()
    if cmd == "daten-pruefen":
        return check_data(argv[2] if len(argv) > 2 else None)
    if cmd == "chat-pruefen":
        return check_chat()
    if cmd == "wissen-import":
        if len(argv) < 3:
            print("Bitte so: python3 -m jarvis wissen-import ~/Downloads/JARVIS-Wissenspaket.zip")
            return
        from .knowledge_import import TARGET, import_pack
        j = Jarvis(load_config(), load_secrets())
        if j.kill.is_active():
            print("🛑 Notabschaltung aktiv. Es wurde nichts importiert.")
            return
        res = import_pack(j.vault, argv[2])
        j.audit.write("knowledge_import", neu=len(res["neu"]), vorhanden=len(res["vorhanden"]),
                      abgelehnt=len(res["abgelehnt"]))
        print(f"✅ {len(res['neu'])} Notizen übernommen nach {TARGET}")
        for n in res["neu"]:
            print("   + " + n)
        if res["vorhanden"]:
            print(f"ℹ️  {len(res['vorhanden'])} schon vorhanden (nicht überschrieben): " + ", ".join(res["vorhanden"]))
        for name, why in res["abgelehnt"]:
            print(f"⛔ abgelehnt: {name} – {why}")
        print("Öffne jetzt im Browser das Second Brain: http://127.0.0.1:8765/gehirn")
        return
    if cmd == "vorlesen":
        return read_aloud(" ".join(argv[2:]))
    if cmd == "secret":
        print("Füge diese Zeile in deine .env ein (niemals teilen!):")
        print(f"JARVIS_APPROVAL_SECRET={secrets.token_urlsafe(48)}")
        return None
    if cmd == "aufgaben":
        return tasks_loop(load_config())
    j = Jarvis(load_config(), load_secrets())
    if cmd.startswith("aufgabe"):
        from .scheduler import TaskError
        try:
            if cmd == "aufgaben-status":
                tasks_status(j)
            elif cmd in ("aufgabe-test", "aufgabe-pause", "aufgabe-fortsetzen") and len(argv) > 2:
                if cmd == "aufgabe-test":
                    r = j.scheduler.run_now(argv[2])
                    print(f"{'✅' if r['status'] == 'erledigt' else '⛔'} {r['status']}: {r['message']}")
                    if r.get("text"):
                        print("\n" + r["text"])
                elif cmd == "aufgabe-pause":
                    j.scheduler.pause(argv[2], via="Terminal")
                    print("⏸ pausiert.")
                else:
                    j.scheduler.resume(argv[2], via="Terminal")
                    print("▶ fortgesetzt.")
            else:
                print("Bitte so: python3 -m jarvis aufgabe-test briefing   (IDs: python3 -m jarvis aufgaben-status)")
        except TaskError as exc:
            print(f"⛔ {exc}")
        finally:
            j.close()
        return None
    if cmd == "briefing":
        print(j.morning_briefing())
    elif cmd == "nacht":
        print(j.night_research())
    elif cmd == "status":
        print(j.status())
    elif cmd == "stop":
        j.kill.activate("lokal")
        j.audit.write("killswitch_on", source="local")
        print("🛑 Notabschaltung aktiv.")
    elif cmd == "resume":
        j.kill.release()
        j.audit.write("killswitch_off", source="local")
        print("✅ Notabschaltung aufgehoben.")
    elif cmd == "audit":
        ok, msg = j.audit.verify()
        print(("✅ " if ok else "❌ ") + msg)
        for e in j.audit.tail(15):
            print(e["ts"], e["event"], e["details"])
    else:
        print(__doc__)
    return None


def _friendly(argv) -> None:
    from .chat import MigrationPending
    from .db import DatabaseUnavailable
    from .server import AlreadyRunning, BackupError
    from .web_auth import AuthError
    try:
        main(argv)
    except (DatabaseUnavailable, MigrationPending, AuthError, ValueError, AlreadyRunning, BackupError) as exc:
        print(f"⛔ {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    _friendly(sys.argv)
