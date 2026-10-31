# JARVIS – Persönlicher KI-Assistent (Version 5.2)

**Stand:** Der Prototyp läuft lokal. **Alle Aktionen sind simuliert:** Es wird nichts gesendet, gekauft oder veröffentlicht, und es gibt keine Kontoverbindung. Es wird nichts installiert, weil nur die Python-Standardbibliothek genutzt wird.

## Was ist schon fertig?
- ✅ **Freigabeschicht**, die das Sprachmodell nicht umgehen kann (signiert, einmalig, mit Ablaufzeit und Inhaltsschutz)
- ✅ Regelwerk: erlaubt / braucht Freigabe / verboten (Käufe, Bank)
- ✅ Nachtruhe: nachts nur stumme Nachrichten, alles andere kommt ins Morgenbriefing
- ✅ Morgenbriefing, Ideen-Analyse, Post- und E-Mail-Entwürfe, simulierte Nachtrecherche
- ✅ Obsidian-Vault mit Ordnerstruktur und Vorlagen; JARVIS schreibt nur in die eigene Inbox
- ✅ Kostenbremse, Notabschaltung, manipulationssicheres Protokoll
- ✅ Telegram-Simulator im Terminal und ein echter Telegram-Testbot (erst nach deiner Freigabe nutzen)
- ✅ Browser-Anmeldung, nur lokal: `python3 -m jarvis web` → http://127.0.0.1:8765
- ✅ Chat mit Gesprächsverlauf (Testmodus ohne Kosten): http://127.0.0.1:8765/chat
- ✅ Business-Gedächtnis: Wissen durchsuchen, Quellen im Chat, Bereichsprofile, Vertraulichkeitsregeln
- ✅ Schritt 4.1: Vertraulichkeit immer auf aktuellem Dateistand, zurückgehaltene Chat-Antworten, sauber geschlossene Datenbanken
- ✅ Version 4.2: systematischer Code-Review, 16 Befunde behoben, Schranke für externe KI, Sicherheitscheck
- ✅ **Version 5:** KI-Modellverwaltung mit Erlaubnisliste, Freigabezentrale im Browser, Skill-System mit Testadaptern, Server-Vorbereitung (Gesundheitsprüfung, Sicherung, Wiederherstellung), Aufgabenplaner mit Testmodus
- ✅ Version 5.1: Nachprüfung durch ChatGPT umgesetzt (Starttest ohne Hängen, gehärtete Sicherungsarchive)
- ✅ Version 5.2: Gesundheitsprüfung und Sicherung verändern auch unter macOS nichts mehr im Datenordner
- ✅ 400 automatische Tests

## Dokumente
| Nr. | Thema |
|---|---|
| [01](docs/01_Architektur.md) | Systemarchitektur & Projektstruktur |
| [02](docs/02_Lokal_vs_Cloud.md) | Lokal vs. Cloud |
| [03](docs/03_30-Tage-Plan.md) | 30-Tage-Plan |
| [04](docs/04_Kosten.md) | Laufende Kosten |
| [05](docs/05_Hermes_Funktionen.md) | Vorhandene Hermes-Funktionen |
| [06](docs/06_Telegram_Sicherheit.md) | Sichere Telegram-Integration |
| [07](docs/07_Obsidian_Konzept.md) | Obsidian als Wissensbasis |
| [08](docs/08_Phase2_Schritt1.md) | **Phase 2, Schritt 1: was neu ist und wie du es übernimmst** |
| [09](docs/09_Persoenlichkeit_und_Stimme.md) | Persönlichkeit und Stimme |
| [10](docs/10_Dashboard_Konzept.md) | Konzept für das futuristische Dashboard |
| [11](docs/11_Nachtarbeit_und_Server.md) | Echte Nachtarbeit und Server |
| [12](docs/12_Phase2_Schritt2_Anmeldung.md) | **Phase 2, Schritt 2: sichere Anmeldung im Browser** |
| [13](docs/13_Dashboard_Plan.md) | Plan für das JARVIS-Dashboard |
| [14](docs/14_Phase2_Schritt3_Chat.md) | Phase 2, Schritt 3: der JARVIS-Chat |
| [15](docs/15_Phase2_Schritt4_Business_Gedaechtnis.md) | **Phase 2, Schritt 4: Business-Gedächtnis (Übernahme Schritt für Schritt)** |
| [16](docs/16_Langfristige_Planung_Mentor_Forschung.md) | Langfristige Planung: Mentor, Forschungsassistent, Lernpartner (nur Planung) |
| [17](docs/17_Version_4-2_Installation_und_Rueckfall.md) | Version 4.2: Installation, Tests, Risiken, Rückkehr |
| [18](docs/18_Version_5_KI_Freigaben_Skills.md) | **Version 5: KI-Modelle, Freigabezentrale, Skills** |
| [19](docs/19_Cloud_Server_Linux.md) | **Version 5: Vorbereitung für einen eigenen Linux-Server** |
| [20](docs/20_Version_5_Installation_Aufgaben_Rueckfall.md) | **Version 5: Installation, Aufgabenplaner, sichere Rückkehr** |
| [21](docs/21_Naechste_Entwicklungsschritte.md) | Nächste Entwicklungsschritte |
| [PRUEFBERICHT.md](PRUEFBERICHT.md) | **Prüfbericht Version 5 für ChatGPT** (frühere: `docs/archiv/`) |
| [AENDERUNGEN.md](AENDERUNGEN.md) | Liste aller Änderungen in Version 5 |

**Neu in Phase 2:** Recherche-Notizen und das Morgenbriefing liegen in `lieferung/00_Inbox/JARVIS/`. Kopiere sie in deinen Obsidian-Vault; es sind nur neue Dateien.

---

## Schritt für Schritt: JARVIS auf deinem MacBook starten

### Schritt 1 – Terminal öffnen
`Cmd + Leertaste` → „Terminal“ eintippen → Enter.

### Schritt 2 – Python prüfen
```bash
python3 --version
```
- Wird **Python 3.8 oder neuer** angezeigt, passt alles.
- Öffnet sich stattdessen ein Fenster „Entwicklertools installieren“: Das ist Apples kostenloses Paket. 🔐 Bitte nur nach deiner Entscheidung installieren; ich erkläre es dir gern vorher.

### Schritt 3 – In den Projektordner wechseln
```bash
cd ~/Downloads/jarvis-v5-2
```
(Pfad anpassen, falls du den Ordner woanders gespeichert hast.)

### Schritt 4 – Demo starten
```bash
python3 -m jarvis demo
```
Du siehst einen kompletten Durchlauf: Idee analysieren, Post zur Freigabe, abgewehrte Angriffe, deine Freigabe, Nachtrecherche, Morgenbriefing und Notaus.

### Schritt 5 – Selbst ausprobieren (Telegram-Simulator)
```bash
python3 -m jarvis chat
```
Tippe zum Beispiel:
- `/idee Online-Fitnesscoaching für Azubis`
- `/post 3 Tipps für mehr Protein`, dann `ok` (freigeben), `nein` (ablehnen) oder `fremd` (ein Fremder versucht es)
- `/briefing`, `/status`, `/stop`
- `exit` zum Beenden

### Schritt 6 – Sicherheitstests laufen lassen
```bash
python3 -m unittest -v
```
Am Ende muss `OK` stehen.

### Schritt 7 – Ergebnisse ansehen
- `data/vault/` → das ist dein Obsidian-Vault (in Obsidian: „Ordner als Vault öffnen“)
- `data/sandbox/outbox/` → was JARVIS „ausgeführt“ hätte (nur simuliert)
- `python3 -m jarvis audit` → Protokoll prüfen

### Notabschaltung
```bash
python3 -m jarvis stop
```
```bash
python3 -m jarvis resume
```

## Nächster Schritt
Siehe [30-Tage-Plan](docs/03_30-Tage-Plan.md), Woche 1. Alles, was mit 🔐 markiert ist (Installation, Konto, Kosten), mache ich **nur nach deiner ausdrücklichen Genehmigung**.
