# 08 – Phase 2, Schritt 1: Grundlagen für die Browseroberfläche

**Stand:** 30.10.2026 · erledigt in einer separaten Projektkopie (Git-Zweig `phase2`) · 43 Sicherheitstests bestanden

Schritt 1 hat noch **keine sichtbare Oberfläche**. Er macht den vorhandenen Kern bereit dafür, dass ein Webserver gefahrlos darauf zugreifen kann.

## Was sich geändert hat

| Bereich | Vorher | Jetzt | Datei |
|---|---|---|---|
| Datenbank | nicht für gleichzeitige Zugriffe abgesichert | jeder Zugriff unter einer Sperre | `jarvis/db.py` (neu) |
| Kosten | Prüfen und Verbuchen getrennt | in einem Schritt: parallele Anfragen können das Limit nicht gemeinsam überschreiten | `jarvis/budget.py`, `jarvis/llm.py` |
| Meldungen | nach dem Senden weg | jede Meldung im Protokoll (`history()`); nachts gesammelte Meldungen gehen nicht mehr verloren | `jarvis/notify.py` |
| Freigaben | nur Telegram | zusätzlich ein Browser-Weg: **standardmäßig aus**, an die Sitzung gebunden, für „Freigeben“ ist ein zweiter Faktor Pflicht | `jarvis/approval.py`, `jarvis/core.py` |
| Notizen anzeigen | – | sichere Markdown-Anzeige: HTML und JavaScript aus Texten werden nie ausgeführt | `jarvis/markdown_safe.py` (neu) |
| Regeln | 6 Aktionen mit Freigabepflicht | zusätzlich Nachrichten, Konten verbinden, Installationen, Uploads, kostenpflichtige Dienste, Dateien ändern oder löschen; „Geld ausgeben“ gesperrt | `jarvis/policy.py` |
| Netzwerk | – | die Oberfläche darf nur auf `127.0.0.1` laufen; andere Werte verweigert das Programm | `jarvis/config.py` |
| Persönlichkeit | – | Systemanweisung zum Selbst-Anpassen | `config/persona.md`, `jarvis/persona.py` |
| Geschäftsbereiche | 3 Themen | 12 Bereiche; die Nachtrecherche rotiert, damit keiner zu kurz kommt (`/bereiche`) | `jarvis/rotation.py` |
| Stimme | – | Schnittstellen vorbereitet, Stimme noch stumm | `jarvis/speech.py` |

## Sicherheitstests (`tests/test_phase2.py`, 20 neue)
- 25 gleichzeitige Freigabe-Klicks: genau **einer** zählt.
- 25 gleichzeitige Ausführungsversuche: genau **eine** Ausführung.
- 40 gleichzeitige KI-Aufrufe: das Tageslimit wird **nie** überschritten.
- 60 Meldungen bei gleichzeitigem Abholen: **keine** geht verloren.
- Browser-Freigaben: standardmäßig aus; fremder Benutzer, fehlender zweiter Faktor und eine fremde Sitzung werden abgelehnt; Telegram- und Browser-Signaturen sind nicht austauschbar.
- 16 Angriffsmuster gegen die Anzeige werden geprüft: Script-Tags, Event-Handler, `javascript:`, `data:`, Tracking-Bilder, Anführungszeichen-Tricks und weitere.
- Die neuen Aktionen brauchen Freigabe, Geld und Bank bleiben gesperrt, die Oberfläche bleibt lokal, die Rotation deckt alle 12 Bereiche ab.

Ausführen:
```bash
python3 -m unittest -v
```

## Auf dein MacBook übernehmen, ohne Daten zu verlieren
Dein bisheriger Ordner `~/Downloads/jarvis 2` enthält deine Daten im Unterordner `data/`. Die neue ZIP-Datei enthält **keinen** `data/`-Ordner.

1. Die neue ZIP-Datei in einen **neuen** Ordner entpacken, z. B. `~/Downloads/jarvis-phase2`. Den alten Ordner nicht überschreiben.
2. Erst testen:
   ```bash
   cd ~/Downloads/jarvis-phase2
   ```
   ```bash
   python3 -m unittest
   ```
3. Wenn du deine bisherigen Daten mitnehmen willst: den Ordner `data` aus dem alten in den neuen Projektordner **kopieren** (nicht verschieben). Der alte Ordner bleibt als Sicherung.
4. Die Recherche-Notizen aus `lieferung/00_Inbox/JARVIS/` in deinen Obsidian-Vault in `00_Inbox/JARVIS/` kopieren. Es sind nur neue Dateien; nichts wird überschrieben.

## Nächster Schritt (wartet auf deine Freigabe)
**Schritt 2:** Anmeldung mit Passwort, Sitzungen, Sperre nach Fehlversuchen und Prüfzeichen gegen gefälschte Anfragen. Danach folgt die erste sichtbare Seite (Schritt 3).
