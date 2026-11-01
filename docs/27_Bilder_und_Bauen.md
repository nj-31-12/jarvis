# Stand 24: JARVIS baut, malt und weiß, was heute passiert

## Was neu ist
| Du sagst (Chat oder Stimme) | JARVIS macht | Kosten |
|---|---|---|
| eine normale Frage, z. B. „Was gibt es Neues bei Tesla?“ | sucht selbst im Internet, wenn nötig, und nennt Quellen | ca. 1–3 Cent mit Suche |
| „Bau mir eine Landingpage für mein Kosmetikstudio mit 3D“ · „Programmier mir einen Kalorienrechner“ · „Bau mir ein Spiel“ | Claude programmiert eine fertige Datei, JARVIS öffnet sie im Browser (Ordner `~/JARVIS/projekte`) | ca. 1–25 Cent |
| „Mal mir ein Bild von …“ · „Erstell mir ein Logo für …“ | erzeugt ein Bild (Ordner `~/JARVIS/bilder`) | **kostenlos** (Cloudflare) |
| „Such mir Friseure in Hamburg mit schlechten Webseiten“ | Akquise-Auftrag wie in Stand 23 | ca. 5–15 Cent |

Im Chat startet ein Auftrag sofort, und du bekommst den Link „Auftrag live ansehen“. Über die Stimme fragt JARVIS erst: „Soll ich starten? Sag ja.“

## Einmal freischalten
```
python3 -m jarvis werkstatt-an
```

## Kostenlose Bilder einrichten (ca. 5 Minuten)
1. Kostenloses Konto anlegen: https://dash.cloudflare.com/sign-up (E-Mail + Passwort, keine Kreditkarte nötig).
2. Links im Menü: **AI** → **Workers AI** → **Use REST API**.
3. Dort steht die **Account ID** (32 Zeichen) → kopieren.
4. Auf derselben Seite **Create a Workers AI API Token** → **Create API Token** → den Token kopieren.
5. Im Terminal (JARVIS vorher mit ctrl + C stoppen):
   ```
   python3 -m jarvis bilder-einrichten
   ```
   Erst die Account ID einfügen, Enter. Dann den Token einfügen (er wird absichtlich **nicht** angezeigt), Enter.
6. JARVIS neu starten.

Der Token gehört nur in deine `.env`. **Nie** in den Chat, in E-Mails oder auf GitHub.
Gratis-Kontingent: ca. 200 Bilder pro Tag. JARVIS stoppt selbst bei 30 pro Tag.

## Videos
Kommen in einem späteren Stand: kostenlos (aber langsam) über Hugging Face oder in guter Qualität über die Higgsfield-API (ca. 1 € pro 10-Sekunden-Clip, nur mit deiner Freigabe pro Video).

## Warum JARVIS deinen eigenen Browser nicht fernsteuert
Dein Browser ist mit Bank, E-Mail und Konten eingeloggt. Ein Programm, das dort selbst klickt, könnte durch eine einzige
manipulierte Webseite Dinge in deinem Namen tun. JARVIS öffnet deshalb nur seine eigenen Ergebnisse und liest öffentliche Seiten.
Wenn du so etwas trotzdem willst: Anthropic bietet dafür die Browser-Erweiterung **Claude in Chrome** (nur Google Chrome)
mit eigenen Schutzfunktionen an.
