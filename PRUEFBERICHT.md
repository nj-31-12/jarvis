# Prüfbericht JARVIS Version 5.2 – für die unabhängige Prüfung durch ChatGPT

## 00. Fehler auf Noahs MacBook → Version 5.2 (neu)

**Meldung:** Unter macOS Catalina mit Python 3.8.2 liefen 388 Tests, davon war 1 fehlgeschlagen: `test_d5_health_check_changes_nothing`. Der SHA-256-Fingerabdruck des Datenordners war nach der Gesundheitsprüfung anders.

**Reproduktion – was ich tun konnte und was nicht:**
- **Nicht möglich:** macOS Catalina mit Python 3.8.2 steht mir nicht zur Verfügung (Linux, Python 3.11–3.13, SQLite 3.45.1). Ich habe den Fehler deshalb **nicht auf Catalina** reproduziert.
- **Stattdessen nachgebildet:** das bekannte Verhalten des mit macOS ausgelieferten SQLite. Es lässt `-wal`/`-shm` nach dem Schließen einer WAL-Datenbank stehen („persistentes WAL“), während Linux sie löscht. Die Nachbildung zeigt Datei für Datei (Inhalt, Größe, Zeitstempel):

| Fall | Version 5.1 | Version 5.2 |
|---|---|---|
| Hilfsdateien werden gelöscht (Linux) | Zeitstempel des Datenordners geändert | keine Änderung |
| Leere `-wal` bleibt stehen | **6 neue Dateien `*.db-shm`** → anderer Fingerabdruck (= Fehlerbild) | keine Änderung |
| `-wal` und `-shm` bleiben stehen | `*.db-shm` beschrieben (Zeitstempel) | keine Änderung |

**Die konkreten Ursachen:**
1. **Hauptursache:** In 5.1 entschied `_ro_uri()` anhand einer vorhandenen `-wal`-Datei, dass JARVIS läuft, und öffnete die Datenbank dann normal mit `mode=ro`. Ein lesender Zugriff auf eine WAL-Datenbank legt die `-shm`-Datei aber an bzw. schreibt in sie. Auf macOS gibt es die `-wal`-Datei auch nach sauberem Beenden, deshalb trat das dort immer auf. Unter Linux wurde die `-wal`-Datei gelöscht, es griff der Modus `immutable=1`, und der Fehler blieb verborgen.
2. **Zweite Nebenwirkung (überall):** Die Prüfung „Datenordner beschreibbar“ legte eine Testdatei an und löschte sie wieder. Das verändert den Zeitstempel des Ordners. Der alte Test bemerkte das nicht, weil er keine Zeitstempel vergleicht.
3. **Gleiche Fehlerklasse an weiteren Stellen:** `pending_migration()` (läuft beim Start, auch bei „nein“), `pending_upgrades()` und die Sicherung öffneten Datenbanken ebenfalls so.

**Behebung im Programmcode (der Test wurde nicht abgeschwächt, sondern verschärft):**
- **Laufender Dienst** wird an den Sperrdateien `.lock-web` und `.lock-aufgaben` erkannt. Dafür wird die Sperrdatei nur lesend geöffnet und eine Sperre kurz versucht. Sie wird nie angelegt.
- **Läuft JARVIS nicht:** Datenbank und `-wal` (falls nicht leer) werden in einen temporären Ordner kopiert und dort geöffnet. Ändert sich die Datei während des Kopierens, wird bis zu dreimal wiederholt. Zusätzlich gilt:
  - Im Datenordner wird nichts angelegt oder beschrieben.
  - Einträge, die nach einem Absturz nur im `-wal` stehen, werden korrekt mitgelesen und mitgesichert. Mit `immutable=1` wären sie in 5.1 **ignoriert** worden, das war ein bisher unentdecktes Risiko für Sicherungen.
- **Läuft JARVIS:** Die Datenbank wird normal lesend geöffnet. Die Hilfsdateien gehören dann ohnehin zum laufenden Betrieb.
- **Beschreibbarkeit** wird nur abgefragt (`os.access`), es wird keine Datei mehr angelegt.

**Regressionstests** (`tests/test_v5_2_nur_lesen.py`, 12 Tests, unter jedem Betriebssystem wirksam): Sie bilden das macOS-Verhalten nach und vergleichen **Inhalt, Größe und Zeitstempel jeder Datei und des Ordners**.
- Geprüft werden Gesundheitsprüfung, `pending_upgrades`, `pending_migration`, `jarvis_running` und Sicherung.
- Ein Absturz-WAL bleibt in der Sicherung erhalten.
- Erkannt wird ein laufender Dienst nur an der Sperre, die Prüfung legt keine Sperrdatei an, sie funktioniert im laufenden Betrieb, und eine Kopie wird bei gleichzeitiger Änderung wiederholt.
- `test_d5_health_check_changes_nothing` vergleicht jetzt zusätzlich die Zeitstempel und **nennt im Fehlerfall die konkrete Datei**.

**Gegenproben:**
- Lese-Logik wie in 5.1 wiederhergestellt → 9 Tests schlagen an, darunter `test_d5`, nun auch unter Linux.
- Testdatei wieder eingebaut → 3 Tests schlagen an.

**Testergebnis 5.2 (selbst ausgeführt):** **400 Tests**, das sind 388 plus 12. Ohne `PYTHONUNBUFFERED`: zweimal Python 3.13 (ResourceWarning und DeprecationWarning als Fehler), außerdem Python 3.11 und 3.12, jedes Mal **400 OK**. Mit `PYTHONUNBUFFERED`: 400 OK. Die statische 3.8-Prüfung ist unverändert.

**Bitte auf dem Mac bestätigen:**
1. Die Diagnose zeigt unter „Hilfsdateien nach dem Schließen“, ob dein Mac persistentes WAL nutzt, und meldet hoffentlich „nichts verändert“. Sie arbeitet nur in einem temporären Ordner:
   ```bash
   python3 werkzeuge/mac_diagnose.py
   ```
2. Erwartet: `Ran 400 tests … OK`.
   ```bash
   python3 -m unittest
   ```
   Schlägt `test_d5` trotzdem fehl, steht in der Meldung jetzt die konkrete Datei. Bitte genau diese Ausgabe schicken.

**Ehrliche Einschränkung:** Dass die Ursache auf deinem Mac genau diese ist, ist eine **begründete Annahme**. Sie passt exakt zum Fehlerbild und wurde nachgebildet, aber nicht auf Catalina bewiesen. Den Beweis liefert dein Testlauf bzw. die Diagnose.

---


**Erstellt von:** Claude (Entwicklung) · **Prüfung durch:** ChatGPT · **Entscheidung:** Noah
**Stand:** 30.10.2026 · **Grundlage:** Version 4.2 (Commit `12036f8`) · **Ergebnis:** Commit auf Zweig `version5`

> **Bitte nicht ungeprüft übernehmen.** Eine bestandene Testsuite bedeutet nicht, dass das System fehlerfrei ist. Abschnitt 6 nennt, was **nicht** getestet wurde, Abschnitt 7 die verbleibenden Risiken.

---

## 0. Nachprüfung → Version 5.1

**Anlass:** In ChatGPTs unabhängigem Testlauf blieb `test_d7_sigterm_stops_web_server_cleanly` hängen.

**Ursache (bestätigt, nicht vermutet):**
- Die Startmeldung `JARVIS läuft …` wurde ohne `flush` ausgegeben. Geht die Ausgabe in eine Pipe, puffert Python sie. Der Test wartete mit `p.stdout.readline()` ohne Zeitlimit auf eine Zeile, die nie kam.
- In meiner Umgebung ist `PYTHONUNBUFFERED=1` gesetzt. Deshalb lief der Test bei mir durch und der Fehler blieb verborgen. Das war mein Fehler im ersten Bericht.
- **Nachstellung:** Mit `env -u PYTHONUNBUFFERED` hing der Test in Version 5 reproduzierbar, bis ein äußeres Zeitlimit ihn abbrach.

| # | Anforderung | Umsetzung | Nachweis |
|---|---|---|---|
| 1 | Nie unbegrenzt auf `readline()` warten | Hilfsklasse `Child`: Ausgabe in Dateien statt Pipes, `wait_for()` mit Zeitlimit (20 s), `wait_exit()` mit Zeitlimit. In der Testsuite gibt es kein `readline()` auf Pipes mehr. | `test_d7_helper_never_waits_forever`: Ein Unterprozess mit gepufferter Ausgabe führt nach 2 s zu einer klaren Meldung. |
| 2 | Klare Meldung bei fehlgeschlagenem Start | `wait_for()` erkennt das vorzeitige Ende und meldet Rückgabewert, Ausgabe und Fehlerausgabe | `test_d7_failed_server_start…`: Ein belegter Port führt zu „vor ‚JARVIS läuft‘ beendet … OSError …“ |
| 3 | Unterprozesse zuverlässig beenden | `Child.__exit__` beendet den Prozess **immer** (`kill`, dann `wait` mit Zeitlimit) und schließt die Dateien | Nach allen Läufen: 0 übrig gebliebene Prozesse |
| 4 | SIGTERM-Ablauf erneut prüfen | Startmeldungen jetzt mit `flush=True` (web, aufgaben). SIGTERM → `httpd.shutdown` in eigenem Thread → `server_close` → Datenbanken schließen → Meldung mit `flush` | `test_d7_sigterm…` besteht **ohne** `PYTHONUNBUFFERED`: Rückgabe 0, „Datenbanken geschlossen“, Prüfkette des Protokolls intakt. **Gegenprobe:** Ohne `flush` scheitert der Test nach 20 s mit „kam nicht innerhalb von 20 s (Startproblem oder gepufferte Ausgabe)“, statt zu hängen. |
| 5 | Archivgröße begrenzen | `BackupLimits.archive_bytes` (2 GiB) wird vor dem Öffnen geprüft. Symlinks und Nicht-Dateien als Archiv werden abgelehnt. | `test_archive_file_too_large`, `test_archive_must_be_regular_file` |
| 6 | Entpackte Gesamt- und Einzelgröße begrenzen | `total_bytes` (8 GiB), `file_bytes` (2 GiB), `entries` (50.000), `manifest_bytes` (16 MiB). Die Prüfung läuft **beim Lesen jedes Kopfeintrags**, ein Abbruch erfolgt also, bevor weitere Daten entpackt werden. Prüfsummen werden blockweise (1 MiB) gebildet. | `test_total_unpacked…`, `test_single_file…`, `test_compression_bomb_stops_early` (3 MiB Nullbytes in < 20 KB), `test_too_many_entries`, `test_manifest_size_limited` |
| 7 | Doppelte Einträge ablehnen | Im Archiv: doppelte Namen, auch ein zweites `MANIFEST.json`. Im Manifest: doppelte Pfade. **Vorher** fasste ein Wörterbuch gleiche Namen still zusammen, sodass geprüfte und entpackte Datei verschieden sein konnten. | 3 Tests (`Duplicates`) |
| 8 | Manifest-Pfade und Dateitypen vollständig prüfen | `valid_backup_path`: relativ, kein `/` am Anfang, kein `.`/`..`/leerer Teil, kein Backslash, keine Steuerzeichen (auch NUL, Zeilenumbruch), Teile ≤ 255 Byte. Archiv-Namen nur `MANIFEST.json` oder `data/<gültiger Pfad>`. Nur normale Dateien, keine Symlinks, Hardlinks, Ordner, Geräte oder FIFOs. Manifest-Struktur: `bytes` als Ganzzahl ≥ 0 (kein bool), `sha256` mit 64 Hex-Zeichen. Größe im Archiv = Größe im Manifest. | 13 schlechte Pfade × 2 Wege, 7 schlechte Archivnamen, 5 Dateitypen, 9 Fehler in der Manifest-Struktur |
| 9 | Gezielte Sicherheitstests | `tests/test_v5_1_sicherung.py` (31 Tests) | Jeder Test prüft zusätzlich: Ziel nicht angelegt, kein Zwischenordner übrig |

**Weitere Härtung, die mir dabei auffiel:**
- **Wiederherstellung über Zwischenordner:** Die Wiederherstellung packt zuerst in einen versteckten Zwischenordner aus und prüft dabei jede Datei **erneut** gegen das Manifest, denn das Archiv könnte zwischen Prüfung und Auspacken ausgetauscht werden (Test mit getauschtem Archiv). Erst danach wird in einem Schritt umbenannt. Bei einem Fehler wird nur der eigene Zwischenordner entfernt.
- **Dateien exklusiv anlegen:** Dateien entstehen mit `O_EXCL | O_NOFOLLOW` und den Rechten 600, der Ordner mit 700.
- **Sicherung prüft schon beim Erstellen:** `make_backup` lehnt unsichere Dateinamen (z. B. Backslash im Notiznamen) und Übergrößen mit klarer Meldung ab. Es entsteht keine halbe Datei. So kann keine Sicherung entstehen, die sich später nicht wiederherstellen lässt.

**Gegenproben (absichtlich eingebaute Fehler) für die Archivprüfung:** Ich habe nacheinander sieben Prüfungen entfernt: Doppelungen im Archiv, Eintragstyp, Gesamtgröße, Einzelgröße, Doppelungen im Manifest, erneute Prüfsumme beim Auspacken und Manifest-Pfade. Jede wird von mindestens einem Test erkannt. Die Manifest-Pfadprüfung war zunächst nur doppelt abgesichert (durch den Abgleich mit den Archivnamen). Ein direkter Test prüft sie jetzt auch für sich allein (13 Fehlschläge bei der Gegenprobe).

**Testergebnis 5.1 (selbst ausgeführt):**
- **388 Tests:** die bisherigen 355, davon `test_d7_sigterm…` umgebaut, plus 2 neue Starttests und 31 neue Archivtests.
- **Ohne `PYTHONUNBUFFERED`:** zweimal mit Python 3.13 (ResourceWarning und DeprecationWarning als Fehler), außerdem mit Python 3.11 und 3.12. Jedes Mal **388 OK**.
- **Mit `PYTHONUNBUFFERED`:** 388 OK.
- **Python-3.8-Prüfung (statisch):** unverändert, nur der bekannte abgesicherte `zoneinfo`-Fund.

**Bitte prüfe erneut:** Läuft `python3 -m unittest` bei dir jetzt durch (erwartet `Ran 388 tests … OK`, ohne Hängen)? Gibt es in `restore_backup` noch einen Weg, außerhalb des Zielordners zu schreiben?

---

## 1. Ausgangslage – was tatsächlich vorlag

| Punkt | Tatsache |
|---|---|
| ZIP von ChatGPT (4.2 + Skill-Katalog) | **Nicht erhalten.** Hochgeladen wurde nur `WEITERENTWICKLUNG_SKILLS.md`. Den dort beschriebenen Code (`jarvis/skill_registry.py`, `tests/test_skill_registry.py`, „220 Tests“) konnte ich deshalb **weder sehen noch prüfen**. |
| Vorgehen | Neue Kopie aus Version 4.2 (unverändert, 0 lokale Änderungen). Den Skill-Katalog habe ich in Phase C selbst entwickelt, nach der Beschreibung in `WEITERENTWICKLUNG_SKILLS.md` (sechs Skills, keine Aktivierung, kein Netzwerk). |
| Ausgangstest 4.2 (selbst ausgeführt) | `Ran 217 tests … OK` unter Python 3.13, ohne ResourceWarnings. |
| Frühere Versionen und Sicherungen | Unverändert: `jarvis`, `jarvis-phase2`, `…-schritt2`, `…-schritt3`, `…-schritt4`, `…-schritt4-1` und `…-schritt4-2`. |

**Zuordnung zu den Punkten in `WEITERENTWICKLUNG_SKILLS.md`:**
1. Zentral erzwungene, standardmäßig sperrende Erlaubnisliste → **Phase A, umgesetzt**. Test-Doubles brauchen eine ausdrückliche Zulassung, die nur im Test gilt.
2. Schutz historischer Chatantworten, auch ohne Quellenbezug → **Phase A, umgesetzt**. Alte Suchantworten werden zurückgehalten, Befehlsausgaben nie an ein Modell gegeben.
3. Genehmigungszentrale mit unveränderlichen Freigabeprotokollen, keine stille Aktivierung → **Phasen B und C, umgesetzt**.
4. Cloud-Architektur → **Phase D: Code und Vorlagen umgesetzt.** HTTPS ersetzt hier ein privater Tunnel, weil JARVIS nur auf 127.0.0.1 lauscht. Verschlüsselte Sicherungen sind nur geplant (Werkzeug `age`, Installation braucht Freigabe).
5. Test auf Python 3.8.2/macOS und Linux → **Linux ja (Python 3.11–3.13). Python 3.8.2 und macOS nein** (Abschnitt 6).
6. Keine Kosten, Konten, Installationen oder Übertragungen → **eingehalten**.

---

## 2. Ergebnisse je Phase

### Phase A – KI-Sicherheit (`jarvis/ai_models.py`, `jarvis/llm.py`)
**Prüfreihenfolge bei jedem Aufruf:** Notaus → Erlaubnisliste → Datenschutz-Schranke → Kostenbremse → Modell. Die Entscheidung fällt bei **jedem** Aufruf neu und betrifft genau das Objekt, das danach aufgerufen wird. `self.model` wird dafür einmal gelesen.

**Erlaubt ohne Datenschutzprüfung:**
- Nur `type(model) is MockLLM` mit dem Namen `mock`. Unterklassen und umbenannte Instanzen sind gesperrt.
- Test-Doubles nur nach `allow_test_double()`. Das gilt je Objekt, nur für Klassen aus dem Paket `tests`, nie für Modelle mit `is_external = True`, und jede Zulassung wird protokolliert.

**Alle anderen Modelle gelten als extern.** Sie brauchen:
- einen Eintrag unter `ai.models` mit `kind = "external"` und `approved is True`;
- `privacy_reviewed_on`: ein ISO-Datum, nicht in der Zukunft, höchstens 180 Tage alt;
- `cost_per_call_eur` zwischen 0 und 1 €;
- `key_env`: ein Name nach dem Muster `JARVIS_…`, dessen Wert in `.env` oder in der Umgebung gesetzt ist;
- `privacy.external_ai_allowed is True` (der Text `"true"` reicht nicht).

Unbekannte Felder oder eine nicht erlaubte Aufgabe führen zur Sperre.

**Fehlende oder kaputte Konfiguration** (Abschnitt fehlt, ist ein Text, ist eine Liste) → nur `mock` ist erlaubt. Ein aktives Modell ohne Anbindung führt zu `NotConnectedModel`, das immer sperrt.

**Schlüssel:**
- `validate_ai_config` bricht den Start ab, wenn der Abschnitt `ai` Felder wie `api_key`, `token`, `secret` oder `password` enthält oder schlüsselähnliche Werte (`sk-…`, `AKIA…`, Zeichenketten ab 40 Zeichen). Die Fehlermeldung nennt nur die Fundstelle, nicht den Wert.
- Ein Test durchsucht den Programmcode nach Schlüsselmustern.

**Protokoll:**
- Erlaubte Zugriffe: `ai_access`. Gesperrte Zugriffe: `external_ai_blocked`, mit Modellname (nur wenn er dem Namensmuster entspricht), Aufgabe, Grund und Zeichenzahl.
- Nie Inhalte, nie Schlüssel.

**Chatverlauf:**
- Antworten auf `/suche` und `/wissen` ohne Quellenangabe (Format vor 4.2) werden zurückgehalten, mit Ansehen und Schwärzen wie bisher.
- Als Verlauf gehen nur Freitext von Noah und echte Modellantworten an ein Modell. Befehle und ihre Ausgaben (z. B. `/offen` mit E-Mail-Texten) bleiben lokal.
- **Bewusste Verhaltensänderung:** `test_b10_when_allowed_sensitive_data_is_removed` braucht jetzt einen vollständigen Listeneintrag. Vorher reichte `external_ai_allowed`.

### Phase B – Freigabezentrale (`jarvis/approval.py`, `jarvis/web.py`)
**Inhalt der Seiten:**
- Übersicht, Detailseite (Beschreibung, Konten, Daten, Kosten, genauer Inhalt, Prüfsumme), Genehmigen, Ablehnen, Sicherheitsprotokoll und Notaus.
- Das Sicherheitsprotokoll zeigt nur Felder aus einer festen Liste, nie Inhalte.

**Bindung an die gezeigte Fassung:**
- `meta` geht in den Hash ein und damit in jede HMAC-Signatur.
- Das Formular enthält den angezeigten Hash `h`. Beim Absenden wird er mit dem gespeicherten Hash verglichen.
- Zusätzlich prüft `intact()` vor jeder Freigabe den gespeicherten Inhalt gegen den Hash. Erkannt wird damit auch eine direkte Änderung an der Datenbank, und zwar sowohl an `payload` als auch an `meta`.

**Änderungen:** `revise()` setzt die alte Aktion atomar von „pending“ auf „superseded“ und legt eine neue Aktion mit Verweis auf die alte an.

**Genehmigen im Browser** braucht alle diese Punkte:
- `web.approvals_enabled` (Standard: aus);
- einen erlaubten Benutzer (ist `web.users` leer, gilt das einzige Browser-Konto);
- ein an die Sitzung gebundenes Token und CSRF;
- das Prüf-Häkchen und das Passwort (zählt für die Sperre nach Fehlversuchen);
- die Fassungsprüfung.

**Ablehnen im Browser** ist jetzt auch bei ausgeschaltetem Genehmigen möglich (Signatur und Benutzer werden weiter geprüft). Begründung: Ablehnen kann nichts auslösen.

**Keine automatische Genehmigung:** Ein Test prüft im Code, dass nur `_apply_decision` den Status auf `approved` setzt. Bestellungen und Zahlungen (`place_order`, `purchase`, `payment` …) bleiben **gesperrt**, auch mit Freigabe. Das ist strenger als das Auftragsbeispiel, folgt aber Noahs Regel 8.

**Gleichzeitigkeit:** 6 Threads genehmigen dieselbe Aktion → sie wird genau einmal ausgeführt (getestet).

### Phase C – Skill-System (`jarvis/skills/`)
**Die sechs Skills:** `research`, `gmail`, `calendar`, `shopify`, `knowledge` und `briefing`. Jeder hat Kennung, Beschreibung, Operationen mit genau einer Berechtigung, eine Art (lesen, entwurf oder vorschlag) und erlaubte Parameter.

**Prüfreihenfolge beim Ausführen:** Notaus → Skill bekannt → Operation bekannt → Skill an → Berechtigung erteilt → Sicherheitsprüfung → Parameter (nur erlaubte, nur Text oder Zahl, höchstens 2.000 Zeichen) → Ratenbegrenzung (30 pro Minute) → Adapter.

**Fehler:** Adapterfehler werden zu `SkillError`. Ins Protokoll kommt nur die Fehlerart.

**Aktivierung:**
- Nur über die Aktion `enable_skill` in der Freigabezentrale. Der Ausführer prüft erneut, dass die Berechtigungen zum Skill gehören und der Adapter `test` ist.
- Weitere Rechte nur über `grant_permission`.
- Ausschalten wirkt sofort und entzieht alle Rechte.

**Vorschläge statt Handeln:** E-Mail senden, Termin eintragen und Preis ändern erzeugen nur Aktionen in der Freigabezentrale (mit `meta`). Verbotene Begriffe (IBAN, PIN …) blockieren den Vorschlag.

**Sicherheitsprüfung je Skill:** `connects_account` und `uses_network` müssen False sein, Berechtigungen müssen bekannt sein, Vorschläge brauchen `*.propose`, und die vorgeschlagenen Aktionsarten müssen freigabepflichtig sein. Ein Befund sperrt Antrag und Ausführung, auch wenn die Zustandsdatei manipuliert wurde.

**Kein Netzwerk:** Ein Test führt alle Operationen aller Skills aus, während `socket.connect`, `create_connection` und `getaddrinfo` einen Fehler auslösen. Ein zweiter Test prüft per AST, dass das Skill-Paket kein Netzwerkmodul importiert.

**Abgrenzung:** „knowledge“ ist kein Testadapter, sondern arbeitet lokal mit `data/vault` (nur nicht vertrauliche Notizen) und schreibt nur neue Dateien in `00_Inbox/JARVIS`. Das ist so gekennzeichnet.

### Phase D – Cloud-Vorbereitung (`jarvis/server.py`, `deploy/`, `docs/19`)
**Nicht öffentlich erreichbar:**
- `web.host` darf weiterhin nur ein Loopback-Wert sein, im Code an zwei Stellen erzwungen.
- Der Zugang ist als SSH-Tunnel oder Tailscale **geplant**, nichts davon ist eingerichtet.

**Pfade und Zugangsdaten:**
- Pfade per Umgebungsvariable: `JARVIS_CONFIG`, `JARVIS_DATA_DIR`, `JARVIS_VAULT_DIR`, `JARVIS_BACKUP_DIR` und `JARVIS_ENV_FILE`. Fehlt die ausdrücklich genannte Konfigurationsdatei, ist das ein Fehler. Es wird nicht still mit Standardwerten weitergearbeitet.
- Zugangsdaten zusätzlich aus systemd `CREDENTIALS_DIRECTORY` (nur Namen nach Muster) und aus `JARVIS_*_KEY`.

**Startprüfung:** Ein öffentlicher Host, eine lesbare `.env` oder lesbare Geheimnisdateien sind Fehler. Im Modus `server` bricht der Start ab.

**Start und Stopp:**
- `instance_lock` (flock): Ein zweiter Start derselben Rolle wird abgewiesen. Getestet auch prozessübergreifend und nach einem harten Abbruch per `kill`.
- SIGTERM beendet den Webserver geordnet (getestet per Unterprozess, Rückgabewert 0, Datenbanken geschlossen).

**Gesundheitsprüfung** (`gesundheit`, Rückgabe 0/1/2): Schreibbarkeit, freier Speicher, `PRAGMA quick_check` jeder Datenbank, Prüfkette des Protokolls, Notaus, Alter der Sicherung und die Startprüfung.

**Sicherung** (`.tar.gz` mit `MANIFEST.json` und SHA-256 je Datei, Rechte 600):
- Datenbanken über die SQLite-Backup-Schnittstelle mit `quick_check` der Kopie.
- Ohne `-wal`, `-shm` und Sperrdateien.
- Nie überschreiben: Die Datei wird exklusiv angelegt und per Hardlink veröffentlicht.
- Der Sicherungsordner darf nicht im Datenordner liegen.

**Wiederherstellung** nur in einen leeren Ordner, nach vollständiger Prüfung. Pfade wie `..` oder absolute Pfade werden abgewiesen.

**systemd-Vorlagen:** `Restart=on-failure`, Startbegrenzung, `ProtectSystem=strict`, `ReadWritePaths=/var/lib/jarvis`, `NoNewPrivileges`, `UMask=0077`, `LoadCredential`, `TZ=Europe/Berlin`.

### Phase E – Aufgabenplaner (`jarvis/scheduler.py`)
**Feste Aufgaben im Code:** briefing, offene_aufgaben, projekte, lernen, ideen und muster. Es gibt keinen Weg, zur Laufzeit Aufgaben anzulegen.

**Keine doppelte Ausführung:** `UNIQUE(task, slot)` in `runs`, der Lauf wird per INSERT beansprucht. Getestet mit zwei Planer-Objekten auf getrennten Verbindungen und 8 Threads → genau ein Lauf. Zusätzlich verhindert `instance_lock("aufgaben")` einen zweiten Prozess.

**Zeitplan:**
- Termine im lokalen Zeitformat.
- Nachholen bis 6 Stunden, danach Status „verpasst“.
- Ein Lauf, der länger als 30 Minuten auf „läuft“ steht, wird „abgebrochen“ und **nicht** wiederholt. Lieber einmal zu wenig als doppelt.

**Status:** Jede Aufgabe ist aktiv oder pausiert, jeder Lauf hat einen klaren Status. Nach 3 Fehlern in Folge pausiert sich eine Aufgabe selbst, ein Erfolg setzt den Zähler zurück. Ins Protokoll kommt nur die Fehlerart. Die Kurzmeldung steht lokal in `tasks.db`.

**Testmodus (Standard):** Ergebnisse nur nach `data/aufgaben-test/`, exklusiv angelegt. Manuelle Läufe sind immer Testmodus. Erst im Modus „aktiv“ entstehen neue Notizen in `00_Inbox/JARVIS` und Meldungen.

**Keine externen Aktionen:**
- Ein Test prüft, dass `scheduler.py` weder `gate.execute` noch `handle_callback` enthält.
- Alle Aufgaben laufen erfolgreich, während `gate.execute` einen Fehler auslöst.
- KI-Aufrufe aus Aufgaben gehen durch die Erlaubnisliste (getestet mit einem unbekannten Modell → gesperrt).

**Notaus:** Der Planer führt nichts mehr aus.

### Phase F – Qualitätssicherung
**Bei der Gesamtdurchsicht gefunden und behoben:** Version 5 hätte in einer bestehenden `actions.db` still die Tabelle `action_meta` angelegt, sogar bei lesenden Befehlen (`status`, `chat-pruefen`). Jetzt gilt:
- Bei älteren Datenbanken entsteht die Tabelle erst beim ersten Speichern einer Aktion mit Angaben.
- Der Webstart listet alle Ergänzungen auf, fragt „ja/nein“ und legt bei „ja“ **vorher** eine vollständige Sicherung an.

**Umstieg und Rückfall mit dem echten Code älterer Versionen** (Skript, siehe Abschnitt 4).

**Belastungstest:** 8 Threads gleichzeitig (Freigaben, Skills, Aufgaben, KI) → keine Fehler, Prüfkette des Protokolls intakt, genau 20 Ausführungen, 20 eigene Notizen, nichts überschrieben.

---

## 3. Fehler, die während der Entwicklung auffielen (vollständig)
| # | Was | Wie gefunden | Behebung |
|---|---|---|---|
| 1 | Die Hilfsfunktion im Test von Phase B schickte das Prüf-Häkchen immer mit, das Formular wirkte dadurch angekreuzt | Test schlug fehl | Testhilfe übernimmt nur versteckte Felder (der Programmcode war richtig) |
| 2 | Gegenproben in Phase C: Das Entfernen der Prüfungen „Skill aus“ und „Kontoverbindung“ fiel keinem Test auf (doppelte Absicherung) | Absichtlich eingebaute Fehler | Zwei gezielte Tests ergänzt, Gegenprobe danach erfolgreich |
| 3 | Die Gesundheitsprüfung (nur lesen) legte bei sauber beendetem JARVIS `-wal`- und `-shm`-Dateien neu an | Test „Prüfung verändert nichts“ | Öffnen mit `immutable=1`, wenn keine `-wal`-Datei existiert |
| 4 | Startet JARVIS genau während einer Sicherung, hätte die Datenbankkopie unbemerkt unvollständig sein können | Eigene Durchsicht | Lesen wird auf sicherem Weg wiederholt, `quick_check` der Kopie, sonst Abbruch |
| 5 | Eine Testhilfe hieß `test_outputs` und wurde als Test mitgezählt (Testanzahl zu hoch) | Durchsicht der Testanzahl | Umbenannt; alle Zahlen in diesem Bericht sind danach gezählt |
| 6 | Stille Ergänzung von `actions.db` (siehe Phase F) | Gesamtdurchsicht | Rückfrage und Sicherung, keine Änderung durch lesende Befehle |
| 7 | Die Uhr des Melde-Moduls liefert `datetime`, der Planer erwartet Sekunden | Durchsicht vor dem ersten Test | Der Planer nutzt eine eigene Uhr |

---

## 4. Testergebnisse (selbst ausgeführt)

| Testdatei | Bereich | Tests | Ergebnis |
|---|---|---|---|
| test_security.py | Phase 1 | 23 | ✅ |
| test_phase2.py | Schritt 1 | 21 | ✅ |
| test_web.py | Schritt 2 | 40 | ✅ |
| test_chat.py | Schritt 3 | 27 | ✅ |
| test_knowledge.py | Schritt 4 | 43 | ✅ |
| test_schritt4_1.py | 4.1 | 22 | ✅ |
| test_schritt4_2.py | 4.2 | 41 | ✅ |
| **test_v5_a_ki_sicherheit.py** | Phase A | **33** | ✅ |
| **test_v5_b_freigabezentrale.py** | Phase B | **29** | ✅ |
| **test_v5_c_skills.py** | Phase C | **26** | ✅ |
| **test_v5_d_server.py** | Phase D | **24** | ✅ |
| **test_v5_e_aufgaben.py** | Phase E | **20** | ✅ |
| **test_v5_f_qualitaet.py** | Phase F | **6** | ✅ |
| **Gesamt Version 5** | | **355** | **355 bestanden, 0 fehlgeschlagen** |
| test_v5_d_server.py (5.1: +2) und **test_v5_1_sicherung.py** | Nachprüfung | **+33** | ✅ |
| **Gesamt Version 5.1** | | **388** | **388 bestanden, 0 fehlgeschlagen** |

**Testläufe:**
- Python 3.13 dreimal hintereinander, mit `-W error::ResourceWarning -W error::DeprecationWarning -W error::SyntaxWarning`: jedes Mal 355 OK.
- Python 3.11 und 3.12: jeweils 355 OK (ResourceWarning als Fehler).

**Gegenproben (absichtlich eingebaute Fehler):**
- Router aus 4.2 statt Version 5: 31 von 33 Tests aus Phase A schlagen fehl.
- Skill-Prüfungen „aus“, „Berechtigung“, „Konto“ und „Netzwerk“ einzeln entfernt: jede Gegenprobe wird von mindestens einem Test erkannt.

**Python-3.8-Prüfung (statisch, ohne Python 3.8 auszuführen):**
- Ergebnis: `ast.parse(feature_version=(3, 8))` für alle Dateien bestanden. Es gibt keine Backslashes in f-String-Ausdrücken und alle neuen Dateien haben `from __future__ import annotations`.
- Fund: `zoneinfo` in notify.py, mit `try/except` abgesichert (wie in 4.2).
- Bewusst vermieden: SQLite-UPSERT (braucht 3.24). `immutable=1` gibt es seit SQLite 3.8, die Backup-Schnittstelle seit Python 3.7.

**Echter Browser (Chromium):** Die Bedienabläufe Genehmigen mit Passwort, Skill beantragen → genehmigen → Testlauf und Aufgaben-Testlauf auf Laptopbreite (1280 px). Die Seiten Freigaben, Aktion, Skills und Aufgaben zusätzlich auf Handybreite (390 px). Das Sicherheitsprotokoll nur auf Laptopbreite. Keine Fehler auf der Seite, kein seitliches Scrollen.

**Mit dem echten Code älterer Versionen** (Skript, kein Teil der Testsuite, weil die alten Ordner nicht in der ZIP liegen):

| Prüfung | Schritt 3 | 4.2 |
|---|---|---|
| Version 5 öffnet alte Daten nur lesend → `actions.db` unverändert | ✅ | ✅ |
| Ergänzungen werden erkannt | chat.db + actions.db | actions.db |
| Alte offene Freigabe in Version 5 ausführbar | ✅ | ✅ |
| Alte `/suche`-Antwort zurückgehalten | ✅ | – (hatte schon Quellen) |
| **Rückfall:** alte Version öffnet Daten aus Version 5, Chat, Status und Protokollkette | ✅ | ✅ |
| **Rückfall:** offene Freigabe *aus Version 5* in alter Version | ⚠️ sicher verweigert | ⚠️ sicher verweigert |

**CLI von Hand:** `gesundheit` (Rückgabe 1 ohne Sicherung, danach 0), `sicherung`, `sicherung-pruefen`, `wiederherstellen` (in vollen Ordner verweigert, in neuen Ordner erfolgreich), `ki-status` und `sicherheitscheck`. Ausgeführt in einem Testordner, der Projektordner blieb ohne `data/`.

---

## 5. Sicherheitseigenschaften auf einen Blick
- **Externe KI:** Keine Daten verlassen den Rechner. Externe KI ist doppelt gesperrt: durch den globalen Schalter und durch eine leere Erlaubnisliste.
- **Kein echtes Konto:** Alle Ausführer sind simuliert, alle Skill-Adapter sind Test- oder lokale Adapter.
- **Keine Genehmigung ohne Mensch:** Es gibt keinen Weg zu „approved“ ohne signierte Entscheidung eines berechtigten Menschen. Im Browser kommen Häkchen und Passwort dazu.
- **Bestehende Daten:** Keine stille Änderung (Rückfrage, Sicherung), lesende Befehle verändern nichts.
- **Vault:** Neue Notizen nur in `00_Inbox/JARVIS`, nie überschreiben (unverändert seit 4.2, erneut getestet über Skills und Planer).

---

## 6. Was NICHT getestet wurde
1. **Python 3.8.2 und macOS Catalina:** Es gab keine Ausführung, nur die statische Prüfung. Noahs Testlauf (`python3 -m unittest`, erwartet 355 OK) ist entscheidend.
   - Besonders zu beobachten: `fcntl.flock` auf APFS, der SIGTERM-Test mit Unterprozess, `os.link` beim Sichern.
2. **systemd-Vorlagen:** Inhaltlich geprüft, aber auf keinem echten Server gestartet.
3. **Echte Konten** (Gmail, Kalender, Shopify, Websuche, KI-Anbieter): bewusst nicht vorhanden.
4. **Dauerbetrieb** über Tage, Sommer- und Winterzeitwechsel im Planer.
5. **Der Code aus ChatGPTs ZIP:** Er wurde nicht erhalten, die behaupteten „220 Tests“ sind deshalb nicht überprüft.

## 7. Verbleibende Risiken (ehrlich)
| # | Risiko | Bewertung | Gegenmaßnahme |
|---|---|---|---|
| 1 | Mustererkennung für Schlüssel und Bankdaten ist keine Garantie | mittel | Verlässlich sind nur `90_Privat` und `vertraulich: ja`. Externe KI bleibt gesperrt. |
| 2 | `allow_test_double` prüft das Modul `tests.*`. Bösartiger Code im selben Prozess könnte das umgehen. | niedrig | Bedrohungsmodell ist Fehlkonfiguration, nicht Schadcode. Jede Zulassung wird protokolliert. |
| 3 | Rückfall mit offenen Freigaben aus Version 5 | niedrig | Sicher verweigert. Anleitung: vorher entscheiden. |
| 4 | Der Planer nutzt die Ortszeit des Rechners | niedrig | `TZ=Europe/Berlin` in den Server-Vorlagen. Bei Zeitumstellung kann ein Termin einmal ausfallen oder um eine Stunde verschoben laufen; doppelt laufen kann er nicht. |
| 5 | Sicherungen enthalten Passwort-Hashes und das Freigabe-Geheimnis | mittel | Rechte 600. Auslagerung nur verschlüsselt (`age` ist geplant und braucht eine Freigabe). |
| 6 | Genehmigen im Browser: Wer die laufende Sitzung **und** das Passwort hat, kann genehmigen | mittel | Standard aus. Telegram bleibt der empfohlene Weg. |
| 7 | Lernthemen für die Ausbildung sind Beispielthemen | niedrig | So gekennzeichnet. Bitte mit dem Ausbildungsrahmenplan abgleichen. |

## 8. Konkrete Prüffragen an ChatGPT
1. Ist die Ausnahme in `ModelPolicy._decide` für Test-Doubles (Modul `tests.*`, je Objekt) eng genug, oder sollte sie über eine Umgebungsvariable nur während `unittest` aktiv sein?
2. Reicht die Fassungsbindung über `h` plus Signatur plus `intact()`, oder fehlt ein Angriffsweg (z. B. zwei Browser-Tabs)?
3. Sollte `Ablehnen` im Browser ebenfalls das Passwort verlangen? (Bisher bewusst nicht, weil Ablehnen nichts auslöst.)
4. Ist „verpasst nach 6 Stunden“ und „abgebrochen wird nicht wiederholt“ für das Tagesbriefing die richtige Abwägung?
5. Erkennst du im Sicherungsformat (`tar.gz` + Manifest) einen Fall, in dem `restore_backup` außerhalb des Zielordners schreiben könnte?
6. Fehlen Sicherheitsprüfungen im Skill-Runner, bevor echte Adapter (OAuth) gebaut werden?

**Bitte prüfe den Code selbst** (`jarvis/ai_models.py`, `jarvis/approval.py`, `jarvis/skills/`, `jarvis/server.py`, `jarvis/scheduler.py`, `jarvis/web.py`) und führe `python3 -m unittest` aus. Vertraue diesem Bericht nicht ungeprüft.
