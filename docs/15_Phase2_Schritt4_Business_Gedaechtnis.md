# 15 – Phase 2, Schritt 4: Business-Gedächtnis

**Stand:** 30.10.2026 · **Version 4.1** · Ordner `jarvis-phase2-schritt4-1` · **176 Tests bestanden, 0 fehlgeschlagen**

> **Neu in 4.1** (nach der Prüfung durch ChatGPT): Vertraulichkeit wird jetzt immer auf dem aktuellen Dateistand geprüft (keine 2-Sekunden-Lücke). Chat-Antworten, deren Quelle inzwischen vertraulich ist, werden zurückgehalten und nie an die KI gegeben; endgültiges Schwärzen nur auf deinen Wunsch. Datenbankverbindungen werden sauber geschlossen. Young Living ist als aktiver Bereich mit eigenem Profil dabei.

## Was neu ist
- **Wissen** (neuer Menüpunkt): Ordnerübersicht, Suche mit hervorgehobenen Treffern, Notizen lesen. **Nur lesen.** Änderungen machst du in Obsidian.
- **Chat mit Gedächtnis:** JARVIS sucht zu deiner Frage die passendsten Notizen und zeigt sie unter der Antwort als **Quellen** mit Link.
- **Neue Befehle:** `/wissen <Thema>` und `/profile`.
- **Profile deiner Geschäftsbereiche:**
  - **aktiv:** NJ Coaching / NYoung.Coaching, Scent Edit / WYLD NOTES, Social Media & Content
  - **Ausbildung:** Automobilbranche
  - **Idee:** Ideen-Pool
  - **laufend:** Lernen & Organisation

  Per Knopf entstehen fehlende Profile als **Entwürfe** in `00_Inbox/JARVIS`. Du prüfst sie und verschiebst sie selbst nach `02_Projekte`.
- **Vertraulichkeit:** Private Notizen tauchen nie in Chat-Kontext, Quellen, `/suche` oder Briefing auf. In der Wissensansicht siehst du sie nur nach erneuter Passworteingabe, für 10 Minuten.
- **`daten-pruefen`:** zeigt Prüfsummen deiner Daten. So prüfst du schwarz auf weiß, dass bei der Übernahme nichts verloren geht.

## So markierst du eine Notiz als vertraulich
Eine der beiden Möglichkeiten genügt:
- Die Notiz in den Ordner **`90_Privat`** legen.
- Ganz oben in die Notiz schreiben:
  ```
  ---
  vertraulich: ja
  ---
  ```

Notizen, die wie Zugangsdaten oder Bankdaten aussehen (z. B. `Passwort: …` oder eine IBAN), stuft JARVIS **automatisch** als vertraulich ein. **Zugangsdaten gehören trotzdem nicht in Obsidian.** Nutze dafür einen Passwort-Manager.

Optional kannst du in deiner `config/jarvis.json` unter `knowledge` → `confidential_terms` Begriffe eintragen, die immer vertraulich sein sollen, z. B. den Namen deines Ausbildungsbetriebs. **Schick mir diesen Namen nicht.** Trag ihn nur lokal ein.

## Übernahme auf dein MacBook, Schritt für Schritt
Es wird nichts installiert. Mach nach jedem Schritt erst weiter, wenn er geklappt hat.

**Schritt 1 – Sicherung anlegen.** Kopiere im Finder deinen Ordner `jarvis-phase2-schritt3` und nenne die Kopie `SICHERUNG-schritt3-2026-10-30`. Diese Kopie rührst du nicht mehr an.

**Schritt 2 – ZIP entpacken.** Doppelklick auf `jarvis-phase2-schritt4-1.zip` im Downloads-Ordner. Es entsteht `jarvis-phase2-schritt4-1`.

**Schritt 3 – Terminal öffnen und in den neuen Ordner wechseln:**
```bash
cd ~/Downloads/jarvis-phase2-schritt4-1
```

**Schritt 4 – Prüfsumme deiner bisherigen Daten anzeigen** (nur lesen). Notiere dir die letzte Zeile mit der Gesamt-Prüfsumme.
```bash
python3 -m jarvis daten-pruefen ../jarvis-phase2-schritt3/data
```

**Schritt 5 – Daten kopieren** (nicht verschieben):
```bash
cp -R ../jarvis-phase2-schritt3/data ./data
```

**Schritt 6 – Kopie prüfen.** Die Gesamt-Prüfsumme muss **genau gleich** sein wie in Schritt 4.
```bash
python3 -m jarvis daten-pruefen data
```

**Schritt 7 – Tests ausführen.** Erwartet: `Ran 176 tests` und darunter `OK`.
```bash
python3 -m unittest
```

**Schritt 8 – JARVIS starten:**
```bash
python3 -m jarvis web
```
Öffne in Firefox `http://127.0.0.1:8765` und melde dich als `nj` an.

Nach dem ersten Start ändert sich die Prüfsumme deines **neuen** Datenordners. Das ist erwartet:
- `chat.db` bekommt eine Spalte für Quellen; deine alten Nachrichten bleiben erhalten.
- Der leere Ordner `90_Privat` kommt dazu.
- Das Protokoll wird fortgeschrieben.

Dein Schritt-3-Ordner bleibt unverändert.

## Erster Test
1. **Wissen** öffnen und `Fitness` suchen. Treffer erscheinen mit Ausschnitt.
2. Auf **„Fehlende Profil-Entwürfe anlegen“** klicken. Die Tabelle zeigt danach siebenmal „◐ Entwurf“.
3. Einen Entwurf öffnen und lesen.
4. Im **Chat** fragen: `Was weiß ich über Scent Edit?` Unter der Antwort erscheinen „Quellen“ mit Links.
5. Optional eine Testnotiz in `data/vault/90_Privat/` anlegen und prüfen, dass sie in Suche und Chat **nicht** auftaucht.

## Neu in 4.1: zurückgehaltene Chat-Antworten
- Wird eine Notiz vertraulich, verschoben oder gelöscht, zeigt der Chat Antworten, die sich auf sie gestützt haben, nur noch als **„Antwort zurückgehalten“** an. Sie gehen nie mehr an die KI. **Nichts wird gelöscht.**
- Ansehen: über „Vertrauliche Notizen einblenden“ mit deinem Passwort (10 Minuten).
- Endgültig schwärzen: nur nach dem Entsperren, mit Häkchen „Ich möchte … endgültig schwärzen“. Das kann nicht rückgängig gemacht werden.
- Überblick nur zum Lesen im Terminal:
  ```bash
  python3 -m jarvis chat-pruefen
  ```

## Was ChatGPT prüfen soll
Lade `jarvis-phase2-schritt4-1.zip` und `PRUEFBERICHT.md` (liegt im Hauptordner) bei ChatGPT hoch. Gib die Hinweise anschließend an mich weiter. Ich prüfe jeden Hinweis mit einem Test und behebe berechtigte Fehler in einer neuen Kopie.
