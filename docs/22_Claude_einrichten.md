# JARVIS 5.3 – Claude als Gehirn einrichten

**Für:** Noah · **Stand:** 31.10.2026 · **Kosten:** ca. 1 € im Monat bei normaler Nutzung (Schätzung)

Diese Anleitung macht aus dem Testmodell ein echtes Gehirn. Es gibt vier Teile:

- **A:** Konto bei Anthropic (im Browser)
- **B:** JARVIS 5.3 auf den Mac holen
- **C:** Schlüssel und Einstellungen eintragen
- **D:** Erster Test

**Regel:** Jeder Befehl wird einzeln ausgeführt. Danach wartest du auf das Ergebnis und meldest es Claude, wenn etwas komisch aussieht.

**Wichtig:** Den API-Schlüssel gibst du **niemandem**, auch nicht Claude oder ChatGPT. Er gehört nur in die Datei `.env` auf deinem Mac.

---

## A. Konto bei Anthropic (Browser, ca. 10 Minuten)

1. Öffne **https://console.anthropic.com** und lege ein Konto an.
2. Öffne **Billing**, kaufe **5 $ Guthaben** und lass **Auto-Reload AUS**.
   Damit können höchstens diese 5 $ verbraucht werden. Das ist dein Anbieterlimit.
3. Öffne **API Keys** → **Create Key** und gib den Namen `jarvis-mac` ein.
4. Kopiere den Schlüssel. Er beginnt mit `sk-ant-…` und wird nur **einmal** angezeigt.
   Lass das Fenster offen, bis Teil C erledigt ist.

### Datenschutzprüfung (vor dem ersten Einsatz)
Prüfe auf den Seiten von Anthropic folgende Punkte und notiere das Datum. Dieses Datum trägst du in Teil C ein (`privacy_reviewed_on`).
- Werden API-Daten zum Training verwendet? Nach unserem Stand standardmäßig nicht. **Selbst prüfen.**
- Wie lange werden Anfragen gespeichert?
- In JARVIS gilt zusätzlich: Notizen aus `90_Privat` werden nie gesendet. Telefonnummern, E-Mail-Adressen, IBAN und Passwörter werden vor dem Senden entfernt.
- **Empfehlung:** Trag den Namen deines Ausbildungsbetriebs unter `confidential_terms` ein (Teil C). Dann werden Notizen mit diesem Namen nie gesendet.

---

## B. JARVIS 5.3 auf den Mac holen

1. Öffne **https://github.com/nj-31-12/jarvis**.
2. Wähle oben links den Zweig **`version5-3`**.
3. Klicke auf **Code** → **Download ZIP**.
4. Entpacke die ZIP in `Downloads` und benenne den Ordner in **`jarvis-v5-3`** um.

Kopiere deine Daten aus 5.2. Sie werden nur **kopiert**, nicht verschoben, damit 5.2 unverändert bleibt.

Befehl 1 (Terminal):
```bash
cp -a ~/Downloads/jarvis-v5-2/data ~/Downloads/jarvis-v5-3/
```

Befehl 2 (nur falls du in 5.2 eine eigene Einstellungsdatei hast; sonst überspringen):
```bash
cp -a ~/Downloads/jarvis-v5-2/config/jarvis.json ~/Downloads/jarvis-v5-3/config/
```

Befehl 3 (nur falls du in 5.2 eine `.env` hast):
```bash
cp -a ~/Downloads/jarvis-v5-2/.env ~/Downloads/jarvis-v5-3/
```

Befehl 4 (in den neuen Ordner wechseln):
```bash
cd ~/Downloads/jarvis-v5-3
```

Befehl 5 (Selbsttest, alle Tests müssen „OK“ zeigen):
```bash
python3 -m unittest discover -s tests -t .
```

---

## C. Schlüssel und Einstellungen eintragen

Befehl 6 (öffnet die geschützte Datei `.env` in TextEdit):
```bash
touch .env && chmod 600 .env && open -e .env
```
Füge in TextEdit eine neue Zeile ein, mit **deinem** Schlüssel statt des Platzhalters, und speichere:
```
JARVIS_ANTHROPIC_KEY=sk-ant-HIER-DEIN-SCHLUESSEL
```

Befehl 7 (öffnet die Einstellungen; falls die Datei noch fehlt, wird sie aus der Vorlage erstellt):
```bash
test -f config/jarvis.json || cp config/jarvis.example.json config/jarvis.json; open -e config/jarvis.json
```
Ändere in TextEdit diese zwei Abschnitte (alles andere bleibt):
```json
  "privacy": {
    "external_ai_allowed": true,
    "max_chars_external": 12000
  },
  "ai": {
    "active_model": "claude-haiku-5-5",
    "models": {
      "claude-haiku-5-5": {
        "kind": "external",
        "provider": "anthropic",
        "approved": true,
        "privacy_reviewed_on": "JJJJ-MM-TT",
        "key_env": "JARVIS_ANTHROPIC_KEY",
        "cost_per_call_eur": 0.01,
        "tasks": ["chat"],
        "description": "Claude Haiku 5.5 – Alltags-Gehirn"
      }
    }
  },
```
- Bei `privacy_reviewed_on` trägst du das Datum deiner Datenschutzprüfung ein, z. B. `2026-11-01`.
- `cost_per_call_eur: 0.01` ist die **Reservierung** pro Anfrage. Abgerechnet werden danach die tatsächlichen Kosten, meist unter 0,1 Cent.
- Optional, im Abschnitt `"budget"`: `"daily_eur": 0.50, "monthly_eur": 5.00`
- Optional, im Abschnitt `"knowledge"`: `"confidential_terms": ["Name deines Ausbildungsbetriebs"]`

Befehl 8 (prüft, ob alles stimmt; das kostet nichts):
```bash
python3 -m jarvis ki-status
```
Erwartet: In der Zeile `claude-haiku-5-5` steht **erlaubt**. Steht dort „gesperrt“, nennt die Zeile den Grund.

---

## D. Erster Test

Befehl 9:
```bash
python3 -m jarvis web
```
Öffne dann in Firefox **http://127.0.0.1:8765** → **Chat** und schreib: *„Jarvis, was weißt du über meine Projekte?“*

Unter der Antwort stehen die Kosten als Schätzung. Maßgeblich ist die Abrechnung bei Anthropic.

---

## Wenn etwas nicht klappt

| Meldung | Bedeutung | Lösung |
|---|---|---|
| „Schlüssel … ist nicht in .env gesetzt“ | `.env` fehlt oder der Name stimmt nicht | Befehl 6 wiederholen, Name genau `JARVIS_ANTHROPIC_KEY` |
| „…den Schlüssel abgelehnt (401)“ | Schlüssel falsch kopiert | neuen Schlüssel anlegen (A3) |
| „Claude ist gerade nicht erreichbar (keine Verbindung)“ | Internet fehlt, oder die Zertifikate deines älteren macOS sind veraltet | Fehlermeldung an Claude schicken (ohne Schlüssel!) |
| „Kostenbremse …“ | Tages- oder Monatslimit erreicht | so gewollt; Limit in `budget` anpassen |
| „Datenschutzprüfung ist älter als 180 Tage“ | Prüfung erneuern | Datum aktualisieren |

## Zurück zu 5.2
Einfach JARVIS beenden (`ctrl + c`) und wieder im alten Ordner starten:
```bash
cd ~/Downloads/jarvis-v5-2 && python3 -m jarvis web
```
Deine Daten in 5.2 wurden nicht verändert, weil 5.3 mit einer Kopie arbeitet.

## Wichtig zu Sicherungen ab 5.3
Neue Sicherungen enthalten **kein** Passwort und kein Freigabe-Geheimnis mehr. Nach einer Wiederherstellung setzt du dein Browser-Passwort einmal neu:
```bash
python3 -m jarvis web-passwort
```
Alte Sicherungen aus 5.0–5.2 enthalten diese Dateien noch. Bewahre sie nur auf dem Mac auf und lade sie nirgends hoch.
