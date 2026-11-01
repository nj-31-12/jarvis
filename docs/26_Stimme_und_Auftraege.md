# Stand 23: Stimme, Auftrags-Zentrale und Webseiten-Werkstatt

## 1. Stimme (Menü „Stimme“)
- Großer Knopf **Sprechen** (oder Leertaste) → sprechen → JARVIS antwortet mit Stimme.
- Der **Plasma-Kern** zeigt, was JARVIS tut: Eisblau = Ruhe · Türkis = hört zu · Violett = denkt · Gold = spricht (pulsiert zur Stimme).
- **Dauergespräch** an: Nach jeder Antwort hört JARVIS automatisch wieder zu.
- Spracherkennung im Browser gibt es in **Chrome und Safari**. In Firefox: ins Textfeld schreiben oder mit **2× fn** diktieren.
- Sagst du einen Auftrag („Such mir Restaurants in Bremen mit schlechten Webseiten“ oder „Bau eine Webseite für Café Sonne“),
  schlägt JARVIS ihn vor. **Gestartet wird erst, wenn du „Ja“ sagst oder auf Starten drückst.**

## 2. Auftrags-Zentrale (Menü „Aufträge“)
- Zwei Auftragsarten:
  1. **Betriebe mit schwachen Webseiten finden**: Websuche → Webseiten prüfen (Punkte 0–100) → für die schwächste eine neue Webseite → Brief-Entwurf + Besuchs-Leitfaden.
  2. **Webseite für einen Betrieb bauen**: Name, Branche, Ort, Wünsche → fertige Demo-Webseite.
- Jeder Schritt erscheint **live**, JARVIS **erzählt** dabei (Häkchen „JARVIS erzählt“). Fertige Aufträge: **Schnellablauf abspielen**.
- **Stopp** hält den Auftrag nach dem laufenden Schritt an. Notaus stoppt alles.
- Ergebnisse liegen in `~/JARVIS/websites/<Datum>_<Name>/` (nicht in GitHub). Knopf **Webseite im Browser öffnen**.

## 3. Websuche einschalten (einmalig)
Standard: aus. Webseiten bauen geht auch ohne. Für die Suche nach Betrieben im Terminal:

```
python3 -m jarvis werkstatt-an
```

Danach JARVIS neu starten. Ausschalten: `python3 -m jarvis werkstatt-aus`.
Kosten: pro Such-Auftrag ca. 5–15 Cent (höchstens 4 Suchen, Limit 0,15 €). Webseiten-Texte: unter 1 Cent.

## 4. Was JARVIS bewusst NICHT tut
- **Nichts senden**: keine E-Mails, keine Kontaktformulare, keine Anrufe. Werbe-E-Mails an Firmen ohne Einwilligung
  sind in Deutschland meist unzulässig (UWG § 7). Besser: vorbeigehen, anrufen oder Brief – mit dem Leitfaden.
- **Keine Kontaktdaten erfinden**: Adresse, Telefon, Impressum und Datenschutz sind rot markierte Platzhalter.
- **Deinen eigenen Browser fernsteuern** (eingeloggte Konten): bewusst noch nicht – zu riskant. JARVIS liest nur
  öffentliche Webseiten, und zwar ohne Cookies, ohne Formulare, nie Geräte im Heimnetz.
