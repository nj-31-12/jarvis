# 20 – Version 5.2: Installation, Aufgabenplaner und sichere Rückkehr

> **Wichtig:** Installiere Version 5 erst, wenn ChatGPT sie geprüft hat **und** du dich bewusst dafür entscheidest. Bis dahin bleibt deine laufende Version (`jarvis-phase2-schritt3`) unverändert in Betrieb.

## A. Installation, Schritt für Schritt (MacBook)
Mach erst weiter, wenn der vorherige Schritt geklappt hat. **Es wird nichts installiert**, nur entpackt und kopiert.

**Schritt 1 – JARVIS beenden.** Läuft JARVIS gerade in einem Terminalfenster, dort `ctrl` + `C` drücken.

**Schritt 2 – Sicherung anlegen.** Kopiere im Finder den Ordner `jarvis-phase2-schritt3` und nenne die Kopie `SICHERUNG-vor-5`. Diese Kopie rührst du nicht mehr an.

**Schritt 3 – ZIP entpacken.** Doppelklick auf `jarvis-v5-2.zip` im Downloads-Ordner. Es entsteht der Ordner `jarvis-v5-2`.

**Schritt 4 – Terminal öffnen und in den neuen Ordner wechseln:**
```bash
cd ~/Downloads/jarvis-v5-2
```

**Schritt 5 – Tests ausführen** (noch ohne deine Daten). Erwartet: `Ran 400 tests` und darunter `OK`. Das dauert etwa 30–60 Sekunden; kein Test wartet länger als 20 Sekunden auf einen Unterprozess. Bei einem anderen Ergebnis hier aufhören und mir die Ausgabe schicken.
```bash
python3 -m unittest
```

**Schritt 5b – Mac-Diagnose (optional, berührt deine Daten nicht).** Erwartet: „Hilfsdateien nach dem Schließen: … persistentes WAL“ und „✅ … nichts verändert“.
```bash
python3 werkzeuge/mac_diagnose.py
```

**Schritt 6 – Prüfsumme deiner bisherigen Daten anzeigen** (liest nur). Notiere dir die Zeile „Gesamt-Prüfsumme“.
```bash
python3 -m jarvis daten-pruefen ../jarvis-phase2-schritt3/data
```

**Schritt 7 – Daten kopieren**, nur kopieren, nicht verschieben:
```bash
cp -R ../jarvis-phase2-schritt3/data ./data
```

**Schritt 8 – Kopie prüfen.** Die Gesamt-Prüfsumme muss **genau gleich** sein wie in Schritt 6.
```bash
python3 -m jarvis daten-pruefen data
```

**Schritt 9 – Sicherheitsprüfung** (liest nur). Ein ⛔ bedeutet: bitte melden, bevor du weitermachst. Die ⚠️-Hinweise aus Version 4.2 (Ordnerrechte, geschützte Begriffe) sind normal.
```bash
python3 -m jarvis sicherheitscheck
```

**Schritt 10 – KI-Status ansehen** (liest nur). Erwartet: nur `mock` ist erlaubt.
```bash
python3 -m jarvis ki-status
```

**Schritt 11 – Starten:**
```bash
python3 -m jarvis web
```
Weil deine Daten aus Schritt 3 stammen, zeigt JARVIS, was ergänzt würde: zwei Spalten in `chat.db` und eine neue Tabelle in `actions.db`. Dann fragt JARVIS „Jetzt umstellen und starten? (ja/nein)“.
- Bei **„ja“** legt JARVIS zuerst eine vollständige Sicherung im Ordner `sicherungen/` an, danach eine zusätzliche Sicherung von `chat.db`. Es wird nichts gelöscht.
- Bei **„nein“** passiert nichts, und JARVIS startet nicht.

Danach Firefox öffnen: `http://127.0.0.1:8765`, als `nj` anmelden.

## B. Erster Test nach dem Start (etwa 10 Minuten)
1. **Übersicht:** Oben gibt es die neuen Menüpunkte **Freigaben**, **Skills** und **Aufgaben**.
2. **Chat:** `/mail test@example.com | Test | Hallo` senden.
3. **Freigaben:**
   - Die Test-Mail anklicken. Du siehst Beschreibung, Konten, Daten und Kosten (0,00 €).
   - **Ablehnen** klicken. Die Aktion steht danach unter „Zuletzt entschieden“.
4. **Skills:**
   - Beim Kalender „Aktivierung beantragen“ klicken.
   - Unter **Freigaben** siehst du den Antrag. Genehmigen ist im Browser noch aus (Standard), deshalb lehnst du ihn zum Test ab. Der Skill bleibt aus.
5. **Aufgaben:** Bei der Lernaufgabe „Jetzt im Testmodus ausführen“ klicken. Das Ergebnis erscheint oben und liegt zusätzlich in `data/aufgaben-test/`.
6. **Sicherheitsprotokoll:** Unter **Freigaben → Sicherheitsprotokoll** stehen deine Schritte, ohne Inhalte.
7. **Im zweiten Terminalfenster** (im selben Ordner) die Gesundheit prüfen. Erwartet: ✅ überall, höchstens Warnungen.
   ```bash
   python3 -m jarvis gesundheit
   ```

## C. Aufgabenplaner (Phase E)
Der Planer läuft **nur**, wenn du ihn startest (zweites Terminalfenster):
```bash
python3 -m jarvis aufgaben
```

| Aufgabe | Wann | Was |
|---|---|---|
| `briefing` | täglich 07:00 | Tagesbriefing |
| `offene_aufgaben` | täglich 18:00 | Alle `- [ ]` aus nicht vertraulichen Notizen |
| `projekte` | montags 08:00 | Stand aller Geschäftsbereiche |
| `lernen` | Mo–Fr 19:00 | Lernthema für die Ausbildung mit Übungsfragen |
| `ideen` | samstags 10:00 | Neueste Idee aus der Inbox bewerten |
| `muster` | sonntags 11:00 | Häufige Befehle zählen, Vorschläge machen |

- **Testmodus (Standard):** Ergebnisse landen nur in `data/aufgaben-test/`. Es gibt keine Meldungen und keine Notizen.
- **Modus „aktiv“:** Trage in `config/jarvis.json` `"scheduler": {"mode": "aktiv"}` ein. Dann legt der Planer neue Notizen in `00_Inbox/JARVIS` an und meldet sich. Externe Aktionen gibt es trotzdem nie.
- **Doppelte Ausführung** ist ausgeschlossen. Läuft der Planer zweimal, verweigert der zweite Start.
- **Verpasste Termine:** War der Mac aus, holt der Planer einen Termin bis zu 6 Stunden später nach. Danach steht er als „verpasst“ in der Liste.
- **Nach 3 Fehlern in Folge** pausiert sich eine Aufgabe selbst.
- **Status, Testlauf, Pause und Fortsetzen:** jeweils mit einem dieser Befehle (oder im Browser unter **Aufgaben**):
  ```bash
  python3 -m jarvis aufgaben-status
  ```
  ```bash
  python3 -m jarvis aufgabe-test lernen
  ```
  ```bash
  python3 -m jarvis aufgabe-pause lernen
  ```
  ```bash
  python3 -m jarvis aufgabe-fortsetzen lernen
  ```

## D. Sicherung
Eine neue Sicherung legst du so an. Sie überschreibt nie etwas:
```bash
python3 -m jarvis sicherung
```
Details zu Sicherung und Wiederherstellung: `docs/19_Cloud_Server_Linux.md`, Abschnitte 4 und 5.

## E. Sichere Rückkehr zur bisherigen Version
Deine bisherige Version und ihre Daten bleiben **unverändert**, weil du in Schritt 7 nur kopiert hast.

**Vorher (wichtig):** Entscheide in Version 5 alle offenen Freigaben, genehmigen oder ablehnen. Ältere Versionen verweigern offene Freigaben aus Version 5 sicherheitshalber. Sie halten die neuen Angaben (Konten, Daten, Kosten) für eine Veränderung. Es wird dann nichts ausgeführt, aber die Aktion bleibt hängen.

**Zurück zu Schritt 3:**
1. Im Terminal mit Version 5 `ctrl` + `C` drücken (auch beim Aufgabenplaner, falls er läuft).
2. In den alten Ordner wechseln:
   ```bash
   cd ~/Downloads/jarvis-phase2-schritt3
   ```
3. Wie gewohnt starten:
   ```bash
   python3 -m jarvis web
   ```

**Was dabei geprüft wurde** (mit dem echten Code von Schritt 3 und Version 4.2):
- Beide Versionen öffnen die Daten von Version 5.
- Der Chatverlauf ist lesbar und neue Nachrichten funktionieren.
- Die Prüfkette des Protokolls bleibt gültig.
- Die neuen Dateien `skills.db` und `tasks.db` ignorieren die alten Versionen einfach.

**Falls etwas schiefgeht:** Im Finder ist `SICHERUNG-vor-5` dein vollständiger Stand von vorher. Zusätzlich liegt die Sicherung aus Schritt 11 in `jarvis-v5-2/sicherungen/`. Nichts löschen, schick mir die Fehlermeldung.
