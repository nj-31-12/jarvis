# 14 – Phase 2, Schritt 3: der JARVIS-Chat

**Stand:** 30.10.2026 · separate Projektkopie (Git-Zweig `schritt3`) · **111 Tests bestanden, 0 fehlgeschlagen**

## Was neu ist
- **Chat-Seite** unter `http://127.0.0.1:8765/chat`, erreichbar über die neue Navigation oben (Übersicht · Chat · Abmelden).
- **Gesprächsverlauf:**
  - Jede Nachricht und jede Antwort wird mit Uhrzeit gespeichert, in `data/chat.db`, nur auf deinem Rechner.
  - „Neues Gespräch“ startet einen frischen Verlauf. Rechts (am Handy oben) stehen die letzten 8 Gespräche.
- **Persönlichkeit und Geschäftsbereiche:**
  - Jede Anfrage an das Modell enthält die JARVIS-Systemanweisung (`config/persona.md`), alle 13 Geschäftsbereiche und die letzten 12 Nachrichten als Kontext.
  - Der Testmodus zeigt die erkannten Bereiche schon an.
- **Befehle im Chat:** `/hilfe`, `/idee`, `/post`, `/mail`, `/notiz`, `/ziel`, `/suche`, `/offen`, `/status`, `/bereiche`, `/stop`.
  - `/briefing` und `/nacht` folgen im Browser später; im Terminal funktionieren sie schon.
- **Testmodus, klar gekennzeichnet:** ein gelber Hinweis oben und ein Abzeichen „TESTMODUS“ an jeder Antwort. Kosten: 0 €.

## Warum Testmodus?
Es ist **kein KI-Zugang eingerichtet**: keine `.env` mit Schlüssel, kein Anbieter, kein Guthaben. Laut deinen Regeln richte ich das nicht ohne Zustimmung ein.

**Was für echte KI-Antworten fehlt** (jeweils 🔐 deine Entscheidung):
1. **Anbieter wählen**, z. B. OpenRouter (viele Modelle, Prepaid) oder die Anthropic- bzw. OpenAI-API. Dein Claude-Pro- und ChatGPT-Abo zählt nicht als API-Zugang.
2. **Prepaid-Guthaben aufladen** (z. B. 5–10 €) und beim Anbieter ein **Ausgabenlimit** setzen.
3. **API-Schlüssel** in die Datei `.env` eintragen (nie in den Chat und nie in Git).
4. Ich baue dann den Anbieter-Baustein ein, mit Kostenschätzung pro Anfrage und Begrenzung der Antwortlänge, und teste ihn mit dir.

**Datenschutz-Hinweis:** Mit echter KI verlassen deine Chat-Nachrichten den Rechner und gehen an den Anbieter. Daten deines Ausbildungsbetriebs gehören nicht in den Chat.

## Was weiterhin gilt
| Regel | Im Chat |
|---|---|
| Freigabepflicht | `/mail` und `/post` erzeugen nur einen **Vorschlag**. Nichts wird gesendet, nicht einmal simuliert, bevor du freigibst. |
| Gesperrte Aktionen | Bank, Zahlungen, Geld ausgeben bleiben gesperrt; verbotene Begriffe (z. B. IBAN) werden blockiert. |
| Obsidian-Regel | `/notiz` und `/idee` legen nur **neue** Dateien in `00_Inbox/JARVIS` an. Pfad-Tricks wie `../` wirken nicht. |
| Kostenbremse | Wird **vor** jedem Modellaufruf geprüft. Ist das Limit erreicht, wird keine Anfrage gesendet, und du siehst einen Hinweis. |
| Notaus | Sperrt Chat-Antworten und Befehle sofort. |
| Schutz vor Überlastung | Höchstens 20 Nachrichten pro Minute |
| Schutz vor Schadcode | Deine Texte werden als reiner Text angezeigt, JARVIS-Antworten über die sichere Markdown-Anzeige |
| Zugriff | Nur angemeldet, mit Prüfzeichen, nur von dieser Seite, nur über `127.0.0.1` |
| Gesprächs-Adressen | Nur 12-stellige Kennungen; alles andere (z. B. `../../etc/passwd`) führt zu „nicht gefunden“ |

## Tests (111 bestanden, 0 fehlgeschlagen)

| Bereich | Anzahl | Datei |
|---|---|---|
| Phase 1: Freigaben, Protokoll, Budget, Nachtruhe, Obsidian | 23 | `tests/test_security.py` |
| Phase 2, Schritt 1: gleichzeitige Zugriffe, Browser-Freigaben, sichere Anzeige, Regeln | 22 | `tests/test_phase2.py` |
| Phase 2, Schritt 2: Passwort, Sperre, Sitzungen, Header, Server | 39 | `tests/test_web.py` |
| **Phase 2, Schritt 3: Chat** | **27** | `tests/test_chat.py` |

Die neuen Chat-Tests prüfen:
- **Verlauf:** Reihenfolge, Speicherung über einen Neustart hinaus, getrennte Gespräche, Kontext mit Persönlichkeit und Geschäftsbereichen für das Modell.
- **Eingaben:** leere, zu lange und Steuerzeichen-Nachrichten, ungültige Gesprächs-Kennungen, Überlastschutz.
- **Kosten:** Nach dem Erreichen des Limits findet **kein** Modellaufruf mehr statt (geprüft mit einem simulierten Bezahlmodell).
- **Sicherheit:**
  - Notaus, `/mail` schlägt nur vor, verbotene Begriffe, Notizen nur neu und nur in der Inbox.
  - Angriffe mit Schadcode im Chat, fehlendes Prüfzeichen, fremde Herkunft, abgelaufene Sitzung.
- **Fehler:** Modell nicht erreichbar führt zu einer freundlichen Meldung, und dabei gelangen keine geheimen Details in Chat oder Protokoll. Dazu lange Nachrichten mit Umlauten.

Zusätzlich geprüft:
- 5 Durchläufe hintereinander ohne Ausfall.
- Python 3.11, 3.12 und 3.13. Mit Python 3.11 lässt sich ein Fehler finden, der auch Python 3.8 betrifft, und genau so ein Fehler wurde gefunden und behoben (siehe unten).
- Ein echter Browser in Laptop- und Handybreite.

### Beim Entwickeln gefunden und behoben
1. **Python-3.8-Fehler:** Zwei Zeilen hätten auf deinem Mac einen Syntaxfehler ausgelöst (`\` innerhalb eines f-Strings). Python 3.13 erlaubt das, 3.8 nicht. Die Zeilen sind behoben, und ab jetzt wird jede Änderung auch mit Python 3.11 kompiliert.
2. **Zu kleine Anfragegrenze:** 4.000 Zeichen mit Umlauten passten nicht in die alten 8 KB. Die Grenze liegt jetzt bei 32 KB.
3. **Ältere Firefox-Versionen:** Die CSS-Funktion `:has()` wurde durch eine einfache Klasse ersetzt.
4. **Abgeschnittene Ideen-Analysen** enden jetzt an einer Zeilengrenze statt mitten im Wort.

## Starten auf dem MacBook

Entpacke `jarvis-phase2-schritt3.zip` per Doppelklick in deinen Downloads-Ordner. Es entsteht der neue Ordner `jarvis-phase2-schritt3`. Dein Ordner `jarvis-phase2-schritt2` bleibt unverändert.

Damit du dich wieder als `nj` anmelden kannst, kopierst du deinen Datenordner aus Schritt 2. Mit `cp -R` wird nur kopiert, nicht verschoben, und dein Original bleibt unangetastet:

```bash
cd ~/Downloads/jarvis-phase2-schritt3
```

```bash
cp -R ../jarvis-phase2-schritt2/data ./data
```

Wenn die Meldung „No such file or directory“ erscheint, ist der Ordner nicht da. Dann überspring den Befehl; beim Start fragt JARVIS dann einfach nach einem neuen Passwort.

Tests ausführen:

```bash
python3 -m unittest
```

Erwartet: `Ran 111 tests` und darunter `OK`.

Starten:

```bash
python3 -m jarvis web
```

Öffne in Firefox `http://127.0.0.1:8765` und melde dich als `nj` an. Beenden im Terminal mit `ctrl` + `C`.

## Dein erster Chat-Test
1. Oben in der Navigation auf **Chat** klicken.
2. Diese drei Nachrichten nacheinander senden:
   - `Hallo JARVIS, wie kann ich Scent Edit über Instagram bekannter machen?` Erwartet: eine Testmodus-Antwort mit den erkannten Bereichen.
   - `/idee Duft-Guide als digitales Produkt im Shopify-Shop` Erwartet: eine Analyse, außerdem eine **neue** Notiz in `data/vault/00_Inbox/JARVIS`.
   - `/mail test@beispiel.de | Test | Hallo` Erwartet: der Hinweis, dass eine Freigabe-Anfrage erstellt wurde. Es wird **nichts** gesendet. Auf der Übersicht steht danach „Offene Freigaben 1“.
3. Optional: **Neues Gespräch** klicken und prüfen, dass das alte rechts in der Liste bleibt.

## Offene Fragen und Freigaben

| # | Entscheidung | Kosten |
|---|---|---|
| 1 | **Echter KI-Zugang:** welcher Anbieter, wie viel Prepaid-Guthaben, welches Tageslimit? | ca. 5–10 € |
| 2 | **Freigaben im Browser:** mit 6-stelligem Code (TOTP), oder nur Anzeige und Freigabe über Telegram? | 0 € |
| 3 | **Nächster Schritt 4:** Wissensdatenbank im Browser (Notizen suchen und lesen) | 0 € |
| 4 | **Telegram-Testbot** anlegen (Kontoaktion) | 0 € |
| 5 | **Handy-Zugriff** (Tailscale prüfen) | 0 € |

## Deine Daten
- In dieser Umgebung sind der Originalordner `jarvis`, die Kopien von Schritt 1 und Schritt 2 sowie die Sicherungs-ZIPs unverändert (geprüft per Git-Status und Prüfsumme).
- Deine Daten auf dem MacBook habe ich nie gesehen und nie verändert. Die ZIP-Datei enthält **keinen** `data/`-Ordner und kann deshalb nichts überschreiben.
