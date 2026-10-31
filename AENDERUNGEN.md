# Änderungen in Version 5.3 „Schnellspur“ (gegenüber 5.2)

Grundlage: unveränderte 5.2 (Commit `af23525`, Zweig `main`). Entwickelt auf Zweig `version5-3`.
Ziel: echtes KI-Gehirn (Claude) so schnell wie möglich – ohne die Sicherheitskette zu schwächen.
Anleitung für Noah: `docs/22_Claude_einrichten.md`.

## Neu
| Datei | Zweck |
|---|---|
| `jarvis/ai_providers/anthropic.py` | Anbindung an Claude. Nur Standardbibliothek (Python 3.8). Fester Endpunkt, TLS, Zeitlimit, keine Wiederholung, Antwort ≤ 1 MB, nur JSON. Preise je Modell; unbekanntes Modell → keine Anfrage. Meldungen ohne Inhalte. |
| `tests/test_v5_3_claude.py` | 31 Tests gegen lokalen Fake-Server: Erfolg, Format, Datenschutz, 400/401/429/500, Zeitlimit, Inhaltstyp, Übergröße, kaputtes JSON, fehlende Kosten, Ablehnung, Abschneiden, Sperren, Endpunkte, Kostenbremse mit 2 Prozessen, Sperre, Rollback, Sicherung ohne Geheimnisse |
| `docs/22_Claude_einrichten.md` | Schritt-für-Schritt-Anleitung (Konto, 5 $ ohne Auto-Reload, Schlüssel in .env, Konfiguration, Test, Rückfall) |

## Geändert
| Datei | Änderung |
|---|---|
| `jarvis/llm.py` | Externe Modelle: Höchstkosten prüfen → reservieren → senden → tatsächliche Kosten abrechnen. Ist die Reservierung kleiner als die Höchstkosten, wird nichts gesendet. 4xx/keine Verbindung → Reservierung wird freigegeben. Zeitüberschreitung/5xx → Reservierung bleibt. |
| `jarvis/budget.py` | Prüfen und Buchen in **einer** Transaktion (`BEGIN IMMEDIATE`) – sicher über Prozessgrenzen. Gesperrte Datenbank → Ablehnung nach Zeitlimit. Neu: `settle()`. |
| `jarvis/server.py` | Sicherungen enthalten `.approval_secret` und `web_auth.json` nicht mehr. |
| `jarvis/ai_models.py` | `make_model` wählt Claude, wenn `provider: "anthropic"` eingetragen ist. Alle Freigabe-Regeln unverändert. |
| `jarvis/chat.py`, `jarvis/core.py` | Verständliche Fehlermeldungen der KI, tatsächliche Kosten je Antwort |
| `.gitignore` | Datenbanken, Passwortdateien, Sicherungen, ZIPs, Protokolle nie in Git |
| `jarvis/__init__.py` | 5.3.0 |

## Nicht geändert / bewusst verschoben
- Datenbankschema unverändert (keine Umstellung beim Start).
- Standard bleibt das Testmodell: Ohne Noahs Einträge in `config/jarvis.json` und `.env` geht nichts nach außen.
- Verschoben auf später: `/bereich`, `/merke`, NJ Digital Solutions, Prüfpunkte 1–6 aus `PLAN-v5-3.md`.

## Tests
431/431 (400 aus 5.2 + 31 neu) unter Python 3.13. Gegenproben: Ausschluss der Geheimnisse entfernt → Test schlägt an;
Transaktion entfernt → Prozess-Test schlägt an. Python-3.8-Syntax statisch geprüft. **Nicht getestet:** echter Aufruf bei
Anthropic, Python 3.8.2 auf macOS Catalina (Zertifikate!), Browser.

---

# Änderungen in Version 5.2 (gegenüber Version 5.1)

Anlass: `test_d5_health_check_changes_nothing` schlug auf Noahs MacBook (macOS Catalina, Python 3.8.2) fehl.
Entwickelt in der separaten Kopie `jarvis-v5-2` (Zweig `version5-2`). Versionen 5 und 5.1 bleiben unverändert.

| Datei | Änderung |
|---|---|
| `jarvis/server.py` | Neu: `jarvis_running()` erkennt einen laufenden Dienst an den Sperrdateien (nur lesend geprüft), nicht mehr an einer `-wal`-Datei. Neu: `_readable_copy()` liest Datenbanken über eine temporäre Kopie (Datenbank plus `-wal`), wenn JARVIS nicht läuft, und lässt den Datenordner dabei unberührt. Gilt für Gesundheitsprüfung, Sicherung und `pending_upgrades`. Die Kopie wird wiederholt, wenn sich die Datei währenddessen ändert. Die Beschreibbarkeit wird mit `os.access` abgefragt, statt eine Testdatei anzulegen und zu löschen. Sicherungskopien werden als eigenständige Datei (`journal_mode=DELETE`) eingepackt. Die Funktion `_ro_uri` (`immutable=1`) ist entfernt. |
| `jarvis/chat.py` | `pending_migration()` liest ebenfalls über `_readable_copy()` und legt beim Start-„nein“ keine Hilfsdateien mehr an. |
| `jarvis/__init__.py` | Version 5.2.0 |
| `tests/test_v5_2_nur_lesen.py` | Neu: 12 Regressionstests mit nachgebildetem macOS-Verhalten (stehen gebliebene `-wal`/`-shm`) und Absturz-WAL |
| `tests/test_v5_d_server.py` | `test_d5_health_check_changes_nothing` **verschärft**: vergleicht zusätzlich Zeitstempel und nennt bei einem Fehler die betroffene Datei |
| `werkzeuge/mac_diagnose.py` | Neu: Diagnose für den Mac, arbeitet nur in einem temporären Ordner |
| `README.md`, `docs/20`, `PRUEFBERICHT.md` | Stand 5.2, 400 Tests, optionaler Diagnoseschritt |

---

# Änderungen in Version 5.1 (gegenüber Version 5)

Anlass: Nachprüfung durch ChatGPT. Entwickelt in der separaten Kopie `jarvis-v5-1` (Zweig `version5-1`). Version 5 bleibt unverändert.

| Datei | Änderung |
|---|---|
| `jarvis/web.py`, `jarvis/__main__.py`, `jarvis/scheduler.py` | Start- und Endmeldungen mit `flush=True`: Sie erscheinen sofort, auch wenn die Ausgabe in eine Pipe, eine Datei oder an systemd geht. |
| `jarvis/server.py` | Neu: `BackupLimits` begrenzt Archivgröße, Gesamtgröße, Dateigröße, Anzahl der Einträge und Manifestgröße. `valid_backup_path` prüft Pfade vollständig. Nur normale Dateien, keine doppelten Einträge (Archiv und Manifest), strenge Prüfung der Manifest-Struktur. Prüfsummen werden blockweise gebildet, nie die ganze Datei im Speicher. Die Wiederherstellung packt in einen Zwischenordner aus, prüft jede Datei erneut und benennt erst am Ende um. `make_backup` lehnt unsichere Dateinamen und Übergrößen mit klarer Meldung ab. |
| `jarvis/__init__.py` | Version 5.1.0 |
| `tests/test_v5_d_server.py` | Neue Hilfsklasse `Child`: Ausgabe in Dateien statt Pipes, Zeitlimit, klare Fehlermeldung, Prozess wird immer beendet. `test_d7_sigterm…` neu aufgebaut. Neu sind `test_d7_failed_server_start…` (Port belegt) und `test_d7_helper_never_waits_forever`. |
| `tests/test_v5_1_sicherung.py` | Neu: 31 Sicherheitstests für Sicherungsarchive |
| `README.md`, `docs/19`, `docs/20`, `PRUEFBERICHT.md` | Stand 5.1, 388 Tests, Grenzen für Sicherungen |

---

# Änderungen in Version 5 (gegenüber Version 4.2)

Grundlage: unveränderte Kopie von Version 4.2 (Commit `12036f8`). Entwickelt im Ordner `jarvis-v5`, Zweig `version5`.
Umfang (Programmcode, Tests, Vorlagen, ohne Dokumentation): 38 Dateien geändert oder neu, 4.544 Zeilen hinzugefügt, 78 entfernt.

## Neue Dateien
| Datei | Zweck |
|---|---|
| `jarvis/ai_models.py` | Erlaubnisliste für KI-Modelle, Datenschutzprüfung, Schlüssel nur aus `.env`/Umgebung, Protokoll jedes Zugriffs |
| `jarvis/skills/__init__.py`, `base.py`, `catalog.py` | Skill-System: Berechtigungen, Zustand, Ausführung mit Prüfreihenfolge, sechs Skills mit Testadaptern |
| `jarvis/server.py` | Sperre gegen Doppelstart, Startprüfung, Gesundheitsprüfung, Sicherung, Wiederherstellung, geordnetes Beenden |
| `jarvis/scheduler.py` | Aufgabenplaner mit sechs festen Aufgaben, Testmodus, „höchstens einmal je Termin“ |
| `deploy/systemd/*.service`, `*.timer` | Vorlagen für Web, Aufgabenplaner, Sicherung und Gesundheitsprüfung (mit Härtung) |
| `deploy/jarvis.server.example.json` | Beispielkonfiguration für den Server-Modus |
| `docs/18`–`docs/21` | Anleitungen zu Version 5, Server, Installation und Rückfall, nächste Schritte |
| `tests/test_v5_a_…` bis `test_v5_f_…` | 138 neue Tests |
| `AENDERUNGEN.md`, `PRUEFBERICHT.md` | Diese Liste und der Prüfbericht für ChatGPT |

## Geänderte Dateien
| Datei | Änderung |
|---|---|
| `jarvis/llm.py` | Router prüft bei **jedem** Aufruf die Erlaubnisliste. Die Selbstauskunft `is_external` zählt nicht mehr. Alles außer dem eingebauten Testmodell läuft durch die Datenschutz-Schranke. Die Kosten richten sich nach dem höheren Wert aus Konfiguration und Modellangabe. Neu ist `allow_test_double` (nur für Tests). |
| `jarvis/core.py` | Verbindet Modell-Richtlinie, Skills und Aufgabenplaner. `/mail` und `/post` liefern Beschreibung, Konten, Daten und Kosten mit. Neuer Befehl `/skills`. |
| `jarvis/approval.py` | Neu: Anzeige-Angaben (`meta`) sind Teil des signierten Inhalts. Dazu kommen `revise()` (Änderung = neue Aktion), die Prüfung `intact()` vor jeder Freigabe, `recent()` und der Status „ersetzt“. Ablehnen im Browser geht immer. Die neue Tabelle `action_meta` wird bei älteren Datenbanken erst bei Bedarf angelegt. |
| `jarvis/policy.py` | Neue Aktionsarten mit Freigabepflicht: `shopify_update_product`, `install_skill`, `enable_skill`, `grant_permission`, `calendar_write`. Neu gesperrt: `place_order`. |
| `jarvis/actions_sim.py` | Simulierte Ausführer für die neuen Aktionsarten |
| `jarvis/web.py` | Neue Seiten Freigaben, Aktion, Sicherheitsprotokoll, Skills und Aufgaben. SIGTERM beendet den Server geordnet. |
| `jarvis/web_static/jarvis.css` | Zwei kleine Gestaltungsregeln |
| `jarvis/chat.py` | Alte `/suche`-Antworten ohne Quelle werden zurückgehalten. Befehlsausgaben gehen nie als Verlauf an ein Modell. `/skills` ist erlaubt. |
| `jarvis/knowledge.py` | Neu: `open_checkboxes()` liest offene Aufgaben nur aus nicht vertraulichen Notizen |
| `jarvis/config.py` | Neue Abschnitte `ai`, `server`, `backup` und `scheduler`. Pfade lassen sich per Umgebungsvariable einstellen. Zugangsdaten kommen auch aus systemd-Credentials und `JARVIS_*_KEY`. Ein Schlüssel in der Konfiguration bricht den Start ab. |
| `jarvis/__main__.py` | Neue Befehle `ki-status`, `gesundheit`, `sicherung`, `sicherung-pruefen`, `wiederherstellen`, `aufgaben`, `aufgaben-status`, `aufgabe-test`, `aufgabe-pause` und `aufgabe-fortsetzen`. Der Start fragt vor jeder Ergänzung bestehender Daten und sichert vorher. Startprüfung und Sperre gegen Doppelstart sind eingebaut. |
| `jarvis/__init__.py` | Version 5.0.0 |
| `config/jarvis.example.json`, `.env.example`, `.gitignore` | Neue Abschnitte, Hinweis zu Schlüsseln, Ordner `sicherungen/` ausgeschlossen |
| `tests/test_chat.py`, `test_knowledge.py`, `test_schritt4_1.py`, `test_schritt4_2.py` | Ersatzmodelle werden jetzt **ausdrücklich** zugelassen (`allow_test_double`). Ein Test (`test_b10_when_allowed…`) bekam einen vollständigen Eintrag in der Erlaubnisliste. Die Prüfziele aller alten Tests sind unverändert. |
| `README.md` | Stand Version 5, neue Dokumente |
| `PRUEFBERICHT.md` (4.2) | verschoben nach `docs/archiv/PRUEFBERICHT-4.2.md` |

## Neue Dateien im Datenordner (entstehen beim ersten Start)
- `data/skills.db`: Ein/Aus und Berechtigungen der Skills
- `data/tasks.db`: Zustand und Läufe des Aufgabenplaners
- `data/aufgaben-test/`: Ergebnisse im Testmodus
- `data/.lock-web`, `data/.lock-aufgaben`: Sperren gegen Doppelstart (leer bis auf die Prozessnummer)
- Ordner `sicherungen/` neben `data/` (nur wenn du sicherst oder beim Umstieg „ja“ sagst)

## Ergänzungen an bestehenden Dateien (nur nach deinem „ja“ beim Start)
- `data/chat.db`: Spalten `sources` und `redacted_at`, wie schon in 4.2 (nur wenn deine Daten aus Schritt 3 stammen)
- `data/actions.db`: neue Tabelle `action_meta`. Bestehende Einträge bleiben unverändert.
