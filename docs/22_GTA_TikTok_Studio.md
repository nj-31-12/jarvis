# GTA TikTok Studio

Deine Zentrale für den GTA-6-TikTok-Account: Fakten sammeln, Skripte bauen, Voice-over, Postingplan, Zahlen auswerten und die Konkurrenz beobachten. Läuft lokal auf deinem Rechner, nur Python-Standardbibliothek, nichts zu installieren.

## Starten
```bash
cd ~/Downloads/jarvis      # dein Projektordner
python3 -m gta_studio
```
Dann im Browser öffnen: **http://127.0.0.1:8777** (Chrome, Edge oder Safari, wegen Vorlesen und Mikrofon).

Die Daten liegen in `data/gta_studio.db`. Unter *Einstellungen* kannst du jederzeit eine Sicherung als JSON herunterladen.

## Was die Bereiche können
| Bereich | Wofür |
|---|---|
| **Cockpit** | Countdown/Tag nach Release, was heute ansteht, überfällige Posts, welche Videos noch keine Zahlen haben, Checkliste vor jedem Post |
| **Faktenbank** | Jede Info mit Status (bestätigt, Gerücht, Leak, Spekulation, widerlegt) und Quelle. 18 Start-Fakten sind drin |
| **Skript-Studio** | Thema + bis zu 3 Fakten → 60-Sekunden-Skript mit Hook, Zeitplan, Einblendungen, Caption, Hashtags. 16 Hook-Formeln, Live-Dauer, Untertitel als `.srt` für CapCut, „KI-Auftrag kopieren“ für Claude |
| **Voice-over** | Probehören mit Computerstimme (Tempo/Tonhöhe), Teleprompter im Vollbild, Aufnahme übers Mikrofon mit Download |
| **Planung** | Postingplan für X Tage mit 1–6 Posts pro Tag, rotiert die Serien automatisch, Kalenderansicht |
| **Analyse** | Zahlen nach 1 h/24 h/7 Tagen eintragen oder CSV importieren. Interaktions-, Teilen-, Speicher- und Follow-Rate, Ausreißer gegenüber deinem Median, Vergleich nach Serie und Hook-Typ, konkrete Tipps |
| **Konkurrenz** | Accounts und deren Videos erfassen. Zeigt Ausreißer (Aufrufe ÷ Median des Accounts) und welche Formate überdurchschnittlich laufen. „Eigene Version“ übernimmt das Thema ins Skript-Studio |

## Täglicher Ablauf (ca. 2–3 Stunden für 2 Videos)
1. **Morgens 20 Min.:** Neue Infos in die Faktenbank (Rockstar Newswire, Patchnotes, eigene Entdeckungen im Spiel). Konkurrenz: die 3–5 stärksten Videos von gestern eintragen.
2. **Skript-Studio:** Fakt auswählen → Skript bauen → Hook-Varianten durchgehen → in eigene Worte bringen → speichern.
3. **Voice-over:** Probehören, dann mit Teleprompter selbst einsprechen.
4. **Aufnehmen und schneiden** (eigenes Gameplay!), `.srt` in CapCut laden.
5. **Checkliste im Cockpit** abhaken, hochladen, „Gepostet ✓“ klicken.
6. **Am nächsten Tag:** Zahlen eintragen. Einmal pro Woche in *Analyse* schauen, welche Serie und welcher Hook-Typ gewinnt.

## Launch-Strategie (ab 19.11.2026)
- **Die ersten 14 Tage sind das Zeitfenster.** Suchinteresse ist auf dem Höhepunkt. 2–3 Posts am Tag sind sinnvoll, sofern die Qualität stimmt.
- **Eigenes Gameplay schlägt alles.** Ab Release hast du Material, das vorher keiner hatte. Easter Eggs, Orte, kleine Details: das ist der echte „Insider“-Inhalt.
- **Tipps-Videos (Einsteiger-Tipps) sammeln Saves**, Easter Eggs und „Was keiner weiß“ sammeln Shares. Beides braucht der Algorithmus.
- **Spoiler-Regel:** Nie im Hook, Titelbild oder in den ersten Sekunden. Story-Videos mit Warnung am Anfang.
- **Serien mit Nummern** („Teil 4“) bringen Follower, weil Leute den nächsten Teil wollen.

## Ehrlich bleiben, auch langfristig
- „Insider-Infos, die keiner weiß“ funktionieren nur, solange sie stimmen. Ein erfundenes oder falsch verkauftes Gerücht kostet mehr Follower, als es bringt. Darum hat jeder Fakt einen Status, und das Skript kennzeichnet Leaks und Gerüchte automatisch.
- Fremde Clips (Trailer, andere Creator) nur kurz und mit eigenem Kommentar, sonst drohen Urheberrechts-Strikes. Rockstar-Logos und -Artwork nicht als eigenes Branding verwenden.
- Die Start-Fakten stammen aus meinem Wissen bis Mitte 2026 plus einer Recherche vom 18.11.2026. Vor dem Posten jede Quelle selbst öffnen.

## Was das Studio bewusst NICHT macht
- **Kein automatisches Posten.** Das ginge nur über TikToks *Content Posting API* mit eigenem Entwicklerkonto, App-Prüfung durch TikTok und Login-Verbindung. Bis dahin lädst du selbst hoch (in der TikTok-App kannst du Posts auch planen).
- **Kein automatisches Abrufen von Zahlen oder Konkurrenz-Daten.** TikTok erlaubt das Auslesen fremder Accounts nicht ohne offizielle API. Deshalb trägst du Zahlen ein oder importierst die CSV aus TikTok Studio.

## Tests
```bash
python3 -m unittest tests.test_gta_studio -v
```

## Online-Version (ohne Installation)
Die Datei `gta_studio/artifact/gta-tiktok-studio.html` ist dieselbe Plattform als Seite auf claude.ai. Sie läuft im Browser, auch am Handy, und speichert alles in der Datenbank der Seite. Lesen und ändern können nur du und Personen, die du als Bearbeiter freigibst.
Zusätzlich gibt es dort „Mit Claude schreiben“: Claude formuliert das Skript aus deinen Fakten. Das verbraucht dein normales Claude-Kontingent.
