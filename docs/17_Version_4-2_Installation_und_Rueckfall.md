# 17 – Version 4.2: Installation, Tests, Risiken und Rückkehr

> **Wichtig:** Installiere 4.2 erst, wenn ChatGPT die Version geprüft hat **und** du dich bewusst dafür entscheidest. Bis dahin bleibt deine laufende Version (`jarvis-phase2-schritt3`) unverändert in Betrieb.

## A. Was 4.2 bringt (kurz)
- **Mehr Datenschutz:**
  - Alte Chat-Antworten mit inzwischen privaten Inhalten werden zuverlässig zurückgehalten, auch nach Verschieben oder Umbenennen.
  - `/suche`-Antworten werden jetzt genauso geschützt.
  - Ein Passwort, das versehentlich ins Namensfeld getippt wird, landet nicht mehr im Protokoll.
- **Mehr Robustheit:**
  - Ein Absturz legt das Protokoll nicht mehr lahm und hinterlässt keine halben Notizen.
  - Beschädigte Dateien führen zu einer klaren Meldung statt zu einem Absturz.
- **Mehr Transparenz:** Eine Umstellung deines Chatverlaufs passiert **nur nach deinem „ja“** und mit Sicherungskopie.
- **Vorsorge:** Eine spätere externe KI ist technisch gesperrt, bis du sie freigibst.
- **Neu:** `python3 -m jarvis sicherheitscheck` prüft deine Einstellungen. Der Befehl liest nur und ändert nichts.

## B. Installation, Schritt für Schritt
Mach erst weiter, wenn der vorherige Schritt geklappt hat. **Es wird nichts installiert**, nur entpackt und kopiert.

**Schritt 1 – JARVIS beenden.** Läuft JARVIS gerade in einem Terminalfenster, dort `ctrl` + `C` drücken.

**Schritt 2 – Sicherung anlegen.** Kopiere im Finder den Ordner `jarvis-phase2-schritt3` und nenne die Kopie `SICHERUNG-vor-4-2`. Diese Kopie rührst du nicht mehr an.

**Schritt 3 – ZIP entpacken.** Doppelklick auf `jarvis-phase2-schritt4-2.zip` im Downloads-Ordner. Es entsteht der Ordner `jarvis-phase2-schritt4-2`.

**Schritt 4 – Terminal öffnen und in den neuen Ordner wechseln:**
```bash
cd ~/Downloads/jarvis-phase2-schritt4-2
```

**Schritt 5 – Prüfsumme deiner bisherigen Daten anzeigen.** Der Befehl liest nur. Notiere dir die Zeile „Gesamt-Prüfsumme“. Erscheint ein Hinweis auf eine `-wal`-Datei, ist das nach sauberem Beenden normal. Wichtig ist nur, dass du in Schritt 6 den **ganzen** Ordner kopierst.
```bash
python3 -m jarvis daten-pruefen ../jarvis-phase2-schritt3/data
```

**Schritt 6 – Daten kopieren**, nur kopieren, nicht verschieben:
```bash
cp -R ../jarvis-phase2-schritt3/data ./data
```

**Schritt 7 – Kopie prüfen.** Die Gesamt-Prüfsumme muss **genau gleich** sein wie in Schritt 5.
```bash
python3 -m jarvis daten-pruefen data
```

**Schritt 8 – Tests ausführen.** Erwartet: `Ran 217 tests` und darunter `OK`. Bei einem anderen Ergebnis hier aufhören und mir die Ausgabe schicken.
```bash
python3 -m unittest
```

**Schritt 9 – Sicherheitsprüfung** (liest nur). Ein ⛔ bedeutet: bitte melden, bevor du weitermachst.

Zu erwartende ⚠️-Hinweise (kein Hindernis):
- **„data-Ordner ist für andere Benutzer dieses Macs lesbar“:** Das betrifft nur andere Benutzerkonten auf deinem Mac. Optional kannst du später `chmod 700 data` ausführen. Das ändert nur Zugriffsrechte, keine Inhalte. Mach das nur, wenn du es möchtest.
- **„Keine eigenen geschützten Begriffe“:** Später kannst du den Namen deines Ausbildungsbetriebs in `config/jarvis.json` eintragen. Schick mir den Namen nicht.
```bash
python3 -m jarvis sicherheitscheck
```

**Schritt 10 – Starten:**
```bash
python3 -m jarvis web
```
Weil dein Chatverlauf aus Schritt 3 stammt, fragt JARVIS: „Jetzt umstellen und starten? (ja/nein)“.
- Bei **„ja“** legt JARVIS zuerst `data/chat.db.vor-umstellung-<Datum>.bak` an und ergänzt dann zwei Spalten. Es wird nichts gelöscht.
- Bei **„nein“** passiert nichts, und JARVIS startet nicht.

Danach Firefox öffnen: `http://127.0.0.1:8765`, als `nj` anmelden.

## C. Erster Test nach dem Start
1. **Übersicht:** Notaus „aus“, Budget sichtbar.
2. **Chat:** `/suche Fitness` senden. Unter der Antwort erscheinen jetzt „Quellen“.
3. **Wissen:** etwas suchen, eine Notiz öffnen.
4. Im Terminal (zweites Fenster, im selben Ordner) prüfen, ob das Protokoll unverändert ist. Erwartet: „Protokoll ist unverändert.“
   ```bash
   python3 -m jarvis audit
   ```

## D. Testergebnisse (Claudes Umgebung)

| Bereich | Tests | Ergebnis |
|---|---|---|
| Phase 1: Freigaben, Protokoll, Budget, Nachtruhe, Obsidian | 23 | ✅ |
| Schritt 1: gleichzeitige Zugriffe, Browser-Freigaben, sichere Anzeige | 21 | ✅ |
| Schritt 2: Anmeldung, Sitzungen, Server | 40 | ✅ |
| Schritt 3: Chat | 27 | ✅ |
| Schritt 4: Business-Gedächtnis | 43 | ✅ |
| Version 4.1: Prüfhinweise ChatGPT | 22 | ✅ |
| **Version 4.2: Code-Review (B1–B16)** | **41** | ✅ |
| **Gesamt** | **217** | **217 bestanden, 0 fehlgeschlagen** |

Getestet mit Python 3.11, 3.12 und 3.13. **Python 3.8.2 konnte nicht ausgeführt werden**, deshalb ist dein Testlauf in Schritt 8 entscheidend.

## E. Verbleibende Risiken (kurz)
1. **Automatische Erkennung** von Zugangs- und Bankdaten ist keine Garantie. Verlässlich sind nur `90_Privat` und `vertraulich: ja`.
2. **Was du selbst in den Chat tippst,** wird lokal gespeichert. Gib dort keine Zugangsdaten ein.
3. **Bearbeitest, verschiebst oder benennst** du eine zitierte Notiz um, werden alte Antworten vorsorglich zurückgehalten. Ansehen geht nach Passwort-Bestätigung.
4. **Daten nie kopieren, während JARVIS läuft.**
5. Der Test mit **Python 3.8.2** steht noch aus.

Alle Risiken mit Bewertung: `docs/archiv/PRUEFBERICHT-4.2.md`, Abschnitt 7.

## F. Sichere Rückkehr zur bisherigen Version
Deine bisherige Version und ihre Daten bleiben **unverändert**, weil du nur kopierst.

**Zurück zu Schritt 3:**
1. Im Terminal mit 4.2 `ctrl` + `C` drücken.
2. In den alten Ordner wechseln:
   ```bash
   cd ~/Downloads/jarvis-phase2-schritt3
   ```
3. Wie gewohnt starten:
   ```bash
   python3 -m jarvis web
   ```

Getestet: Der Schritt-3-Code kann auch einen von 4.2 umgestellten Chatverlauf lesen und beschreiben. Du kannst also auch die 4.2-Daten zurückkopieren. Empfohlen ist aber, einfach den unveränderten alten Ordner zu nutzen.

**Falls etwas schiefgeht:** Im Finder ist `SICHERUNG-vor-4-2` dein vollständiger Stand von vorher. Nichts löschen. Schick mir die Fehlermeldung.
