# 07 – Obsidian als Wissensbasis

Obsidian speichert alles als normale Markdown-Dateien in einem Ordner (dem „Vault“). Dadurch können JARVIS, Hermes, Claude Code und du auf denselben Bestand zugreifen, ohne an einen Anbieter gebunden zu sein.

## Ordnerstruktur
| Ordner | Inhalt | JARVIS darf … |
|---|---|---|
| `00_Inbox/JARVIS` | Alles, was JARVIS erzeugt: Analysen, Recherchen, Entwürfe | **nur neue Notizen anlegen** |
| `01_Ziele` | Deine Jahres-/Quartalsziele als Checklisten `- [ ]` | lesen |
| `02_Projekte` | Eine Notiz pro Projekt (Shop, Coaching, …) | lesen, Änderung nur mit Freigabe |
| `03_Geschäftsideen` | Bewertete Ideen (aus der Inbox übernommen) | lesen |
| `04_Entscheidungen` | Wichtige Entscheidungen mit Begründung | lesen |
| `05_Lernen` | Kurse, Bücher, Erkenntnisse, Lernfortschritt | lesen |
| `06_Content` | Freigegebene Posts, Content-Plan | lesen |
| `07_Recherchen` | Übernommene Recherchen | lesen |
| `08_Tagebuch` | Tagesnotizen und Briefings | lesen |
| `99_Vorlagen` | Vorlagen (siehe `vault-vorlage/`) | lesen |

## Bestätigte Regel (29.10.2026)
> JARVIS darf ohne Rückfrage **nur neue Notizen** im Ordner `00_Inbox/JARVIS` erstellen.
> **Bestehende Dateien darf er nicht verändern oder löschen**, auch nicht in der Inbox.
> Für alle anderen Dateiänderungen ist deine ausdrückliche Freigabe erforderlich.

Umsetzung: Notizen werden im Modus „nur neu anlegen“ geschrieben. Gibt es den Namen schon, entsteht eine neue Datei mit Zusatz „(2)“. Der Vault-Baustein hat keine Funktion zum Bearbeiten oder Löschen. Beides ist durch Tests abgesichert.

**Prinzip:** JARVIS schlägt vor, du entscheidest. Du verschiebst gute Entwürfe aus der Inbox in den passenden Ordner. Damit bleibt dein Wissen sauber, und kein Modell überschreibt deine Notizen.

## Technische Durchsetzung
- Im Prototyp: `obsidian.py` erlaubt Schreiben nur in `vault_auto_write_dirs`, inklusive Schutz vor `../`-Tricks (getestet).
- Auf dem Server: Der Linux-Benutzer `hermes` bekommt Schreibrechte **nur** auf `00_Inbox/JARVIS`. Den Rest des Vaults kann er nur lesen. Zusätzlich wird die Inbox so eingerichtet, dass `hermes` dort keine fremden oder älteren Dateien ändern oder löschen kann (Details bei der Server-Einrichtung in Woche 3). Das setzt das Betriebssystem durch, nicht das Modell.

## Metadaten (Frontmatter) jeder JARVIS-Notiz
```yaml
---
erstellt: 2026-10-29T07:00
quelle: JARVIS
status: entwurf        # entwurf → geprüft → übernommen
tags: [jarvis, entwurf, geschäftsidee]
---
```

## Synchronisation (kostenlos)
- Vault auf dem Server ist ein **privates Git-Repository** (z. B. auf GitHub).
- Auf dem MacBook: Obsidian-Community-Plugin **„Git“** zieht Änderungen automatisch.
- Handy: Obsidian-App + Git-Plugin oder vorerst nur Telegram.
- Kostenpflichtiges „Obsidian Sync“ ist nicht nötig.

## Empfohlene Plugins (kostenlos, später)
Git, Dataview (Übersichten z. B. „alle Ideen mit Bewertung ≥ 4“), Templater, Calendar.
