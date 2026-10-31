# 19 – JARVIS auf einem eigenen Linux-Server (Vorbereitung)

> **Stand: nur Planung und vorbereiteter Code.** Es wurde **kein Server bestellt, nichts aktiviert, keine Daten übertragen.** Jeder Schritt unten braucht deine ausdrückliche Freigabe.

## 1. Ziel und Grundregel
JARVIS soll rund um die Uhr laufen, auch wenn dein MacBook aus ist.

**Grundregel:** JARVIS ist **nie** direkt aus dem Internet erreichbar.
- Die Oberfläche lauscht weiterhin nur auf `127.0.0.1` (im Code erzwungen, ein Test prüft das).
- Du erreichst sie nur über einen **privaten, verschlüsselten Tunnel**.
- Auf dem Server ist nur SSH offen, und zwar nur mit Schlüssel, nie mit Passwort.

```
 Handy / MacBook ──(privater Tunnel: Tailscale oder SSH)──► Server
                                                           ├─ JARVIS Web  (nur 127.0.0.1:8765)
                                                           ├─ JARVIS Aufgaben (Zeitplaner, Phase E)
                                                           ├─ Gesundheitsprüfung (stündlich)
                                                           └─ Sicherung (täglich 03:30)
 Internet ──X── kein offener Port außer SSH (Schlüssel)
```

## 2. Zugang: zwei Möglichkeiten

| | **A: SSH-Tunnel** (empfohlen zum Start) | **B: Tailscale** (später, bequemer fürs Handy) |
|---|---|---|
| Was ist das? | Verschlüsselte Leitung über SSH | Privates Netz nur deiner Geräte |
| Kosten | 0 € | 0 € im privaten Tarif *(Stand laut Anbieter; vor Einrichtung prüfen)* |
| Installation | Nichts zusätzlich (SSH ist auf Mac und Linux vorhanden) | App auf Mac, Handy und Server **(braucht deine Freigabe)** |
| Konto | Keins | Tailscale-Konto **(braucht deine Freigabe)** |

**A – SSH-Tunnel**, auf dem Mac im Terminal (nur ein Beispiel, erst wenn ein Server existiert):
```bash
ssh -N -L 8765:127.0.0.1:8765 jarvis-server
```
Dann im Browser `http://127.0.0.1:8765` öffnen. Die Anmeldung mit Passwort gilt wie gewohnt.

## 3. Was in Version 5 dafür schon gebaut ist

| Baustein | Befehl / Datei | Was es tut |
|---|---|---|
| Einstellbare Ordner | `JARVIS_CONFIG`, `JARVIS_DATA_DIR`, `JARVIS_VAULT_DIR`, `JARVIS_BACKUP_DIR` | Programm, Daten und Sicherungen liegen getrennt (z. B. `/opt/jarvis`, `/var/lib/jarvis`). |
| Zugangsdaten | `.env` (Rechte 600) **oder** systemd `LoadCredential` | Geheimnisse liegen nie im Code und nie in der Konfiguration. Im Server-Modus verhindert eine lesbare `.env` den Start. |
| Startprüfung | automatisch bei `python3 -m jarvis web` | Im Modus `"server"` bricht der Start bei Fehlern ab (öffentlicher Host, lesbare Geheimnisse, offener Datenordner). |
| Nur eine Instanz | automatisch | Ein zweiter Start desselben Dienstes wird verhindert. So wird nichts doppelt ausgeführt. |
| Geordnetes Beenden | `ctrl + C` oder `systemctl stop` (SIGTERM) | Datenbanken werden sauber geschlossen. |
| Neustart nach Absturz | `deploy/systemd/jarvis-web.service` | `Restart=on-failure`, höchstens 5 Starts in 10 Minuten. |
| Gesundheitsprüfung | `python3 -m jarvis gesundheit` | Prüft Ordner, Speicherplatz, Datenbanken, Protokollkette, Notaus, Alter der Sicherung. Ergebnis 0 = gut, 1 = Warnung, 2 = Fehler. Liest nur. |
| Sicherung | `python3 -m jarvis sicherung` | Neue `.tar.gz` mit Prüfsummen, Datenbanken konsistent auch im laufenden Betrieb. Überschreibt und löscht nie. |
| Sicherung prüfen | `python3 -m jarvis sicherung-pruefen <Datei>` | Prüft jede Datei gegen ihre Prüfsumme. |
| Wiederherstellung | `python3 -m jarvis wiederherstellen <Datei> <neuer Ordner>` | Nur in einen **leeren** Ordner. Bestehende Daten werden nie überschrieben. Seit 5.1: Erst wird alles in einen versteckten Zwischenordner ausgepackt und jede Datei erneut geprüft, dann wird in einem Schritt umbenannt. Bei einem Fehler bleibt das Ziel unberührt. |
| Grenzen (5.1) | fest im Code (`BackupLimits`) | Archiv höchstens 2 GiB, entpackt zusammen höchstens 8 GiB, eine Datei höchstens 2 GiB, höchstens 50.000 Einträge. Nur normale Dateien, keine Doppelungen, nur sichere Pfade. |
| Server-Vorlagen | `deploy/systemd/*`, `deploy/jarvis.server.example.json` | Dienste mit Härtung: eigener Benutzer, schreibt nur in `/var/lib/jarvis`. |

## 4. Sicherungskonzept (3-2-1)
1. **Täglich** um 03:30 eine neue Sicherung auf dem Server (`jarvis-backup.timer`).
2. **Wöchentlich** eine Kopie auf dein MacBook, über die gleiche verschlüsselte SSH-Verbindung (`scp`).
3. **Vor jedem Update** zusätzlich eine Sicherung von Hand.

Dabei gilt:
- **Wichtig:** Eine Sicherung enthält Passwort-Hashes und das Freigabe-Geheimnis. Außerhalb von Server und Mac darf sie nur **verschlüsselt** liegen. Python allein kann nicht sicher verschlüsseln. Geplant ist dafür das kleine Werkzeug `age` **(Installation braucht deine Freigabe)**.
- **Alte Sicherungen** löscht JARVIS nie automatisch. Das Aufräumen entscheidest du.
- **Ohne Prüfung ist eine Sicherung wertlos:** Einmal im Monat `sicherung-pruefen` ausführen und eine Wiederherstellung in einen Testordner durchspielen.

## 5. Wiederherstellung, Schritt für Schritt
1. JARVIS stoppen:
   ```bash
   sudo systemctl stop jarvis-web
   ```
2. Die letzte Sicherung prüfen. Den Dateinamen ersetzt du durch den deiner neuesten Sicherung:
   ```bash
   python3 -m jarvis sicherung-pruefen /var/lib/jarvis/sicherungen/jarvis-sicherung-2026-11-01_033000.tar.gz
   ```
3. Die Sicherung in einen **neuen** Ordner auspacken:
   ```bash
   python3 -m jarvis wiederherstellen /var/lib/jarvis/sicherungen/jarvis-sicherung-2026-11-01_033000.tar.gz /var/lib/jarvis/data-wiederhergestellt
   ```
4. In der Dienstdatei `JARVIS_DATA_DIR` auf den neuen Ordner setzen. Den alten Ordner **nicht löschen**, er bleibt als Rückfall.
5. Die Dienstdatei neu einlesen und JARVIS starten:
   ```bash
   sudo systemctl daemon-reload
   ```
   ```bash
   sudo systemctl start jarvis-web
   ```
6. Den Zustand prüfen:
   ```bash
   python3 -m jarvis gesundheit
   ```

## 6. Späterer Einrichtungsplan (jeder Schritt einzeln, nur mit deiner Freigabe)
| Schritt | Was | Freigabe nötig für |
|---|---|---|
| 1 | Anbieter auswählen (z. B. ein kleiner Server in Deutschland) | Kosten, Konto |
| 2 | Server mit Ubuntu LTS bestellen, nur SSH-Schlüssel | Kosten (Schätzung 4–7 €/Monat, vorher prüfen) |
| 3 | Firewall: nur SSH; automatische Sicherheitsupdates | Installation |
| 4 | Benutzer `jarvis`, Ordner `/opt/jarvis`, `/var/lib/jarvis`, `/etc/jarvis` | Server-Änderungen |
| 5 | JARVIS-Code kopieren, `python3 -m unittest` auf dem Server | Datenübertragung (nur Code) |
| 6 | Dienste aus `deploy/systemd` einrichten, `server.mode = "server"` | Server-Änderungen |
| 7 | Erst danach: Daten vom Mac übertragen (Sicherung → Wiederherstellung) | **Datenübertragung** |
| 8 | Optional: Tailscale fürs Handy | Konto, Installation |

## 7. Ehrliche Grenzen
- **Getestet** wurde hier unter Linux mit Python 3.11 bis 3.13: Startsperre, geordnetes Beenden per SIGTERM, Sicherung und Wiederherstellung, Gesundheitsprüfung. Die **systemd-Dateien sind Vorlagen.** Sie wurden auf Inhalt geprüft, aber nicht auf einem echten Server gestartet.
- **Rückfall auf Version 4.2:** Version 4.2 kennt die neuen Datenbanken `skills.db` und die Tabelle `action_meta` nicht. Sie ignoriert sie, es geht nichts verloren.
- **Gleichzeitige Prozesse:** Web und Aufgabenplaner können gleichzeitig laufen. SQLite (WAL-Modus) und die Dateisperre des Protokolls sind dafür ausgelegt. Getestet ist das mit mehreren Threads und Prozessen, nicht über Wochen im Dauerbetrieb.
- **Sicherung beim Start:** Startet JARVIS genau in dem Moment, in dem eine Sicherung eine Datenbank liest, liest die Sicherung diese Datenbank automatisch noch einmal auf dem sicheren Weg. Jede Datenbankkopie wird vor dem Einpacken auf Fehler geprüft. Klappt das nicht, bricht die Sicherung mit einer Meldung ab. Es geht dabei nichts verloren.
