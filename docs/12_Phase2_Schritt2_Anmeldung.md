# 12 – Phase 2, Schritt 2: sichere lokale Anmeldung

**Stand:** 30.10.2026 · separate Projektkopie (Git-Zweig `schritt2`) · **84 Sicherheitstests bestanden** · Originalprojekt unverändert

## Was du jetzt hast
- Eine **Anmeldeseite** und eine erste **Systemübersicht** im Browser:
  - Status: Notaus, offene Freigaben, Budget
  - die letzten Meldungen
  - ein Notaus-Knopf
- Erreichbar **nur auf deinem MacBook** unter `http://127.0.0.1:8765`.
- Kein JavaScript, keine Schriften oder Dateien aus dem Internet. Das schont dein MacBook und bietet weniger Angriffsfläche.

## Befehle

| Befehl | Wirkung |
|---|---|
| `python3 -m jarvis web` | Startet die Oberfläche. Beim ersten Mal fragt sie zuerst nach einem Passwort. |
| `python3 -m jarvis web-passwort` | Passwort festlegen oder ändern (Ändern nur nach Rückfrage) |
| `python3 -m jarvis web-status` | Zeigt, ob ein Passwort gesetzt und die Anmeldung gesperrt ist |
| `python3 -m jarvis vorlesen "Text"` | Liest Text mit der Mac-Stimme im Erzähler-Stil vor (offline, kostenlos) |

Beenden der Oberfläche: im Terminal `ctrl` + `C`.

## Schutzmaßnahmen

| Schutz | Umsetzung |
|---|---|
| Passwort | Gespeichert nur als PBKDF2-SHA256-Hash mit 600.000 Runden und eigenem Salz. Die Datei `data/web_auth.json` ist nur für dich lesbar (Rechte 600). |
| Passwortregeln | Mindestens 12 Zeichen, nicht der Benutzername, keine sehr häufigen Passwörter |
| Raten verhindern | 5 Fehlversuche führen zu 15 Minuten Sperre. Die Sperre überlebt einen Neustart. |
| Fehlermeldung | Immer allgemein („Benutzername oder Passwort ist falsch“), sie verrät nichts |
| Sitzung | Zufällige, lange Kennung. Abmeldung nach 30 Minuten Leerlauf, spätestens nach 12 Stunden. Eine neue Anmeldung beendet die alte Sitzung. Nach einem Neustart ist jeder abgemeldet. |
| Cookie | `HttpOnly` (für Skripte unsichtbar), `SameSite=Strict` (wird nicht von fremden Seiten mitgeschickt) |
| Gefälschte Anfragen | Prüfzeichen (CSRF-Token) bei jeder Aktion. Fremde Herkunft wird abgelehnt, auch die Herkunft „null“. Das Anmeldeformular ist nur einmal verwendbar. |
| Fremde Adressen | Nur `127.0.0.1` oder `localhost` mit Port 8765, alles andere wird abgelehnt (Schutz gegen DNS-Rebinding) |
| Netzwerk | Der Server lauscht nur auf `127.0.0.1`. Andere Geräte im WLAN erreichen ihn nicht. |
| Header | Strenge Content-Security-Policy, kein Einbetten in fremde Seiten, kein Zwischenspeichern |
| Fehler | Keine internen Details im Browser, nur ein Eintrag im Protokoll |
| Protokoll | Anmeldungen, Fehlversuche, Sperren und Abmeldungen, ohne Passwörter |
| Notaus | Im Browser auslösbar, Aufheben nur im Terminal |

**Bewusst noch nicht drin:** Freigaben im Browser. Die Technik für 6-stellige Codes (TOTP) ist fertig und getestet, aber **aus**, bis du dich entscheidest.

## Beim Testen gefundene und behobene Fehler
1. **Abstürze durch Sonderzeichen:** Ein präpariertes Prüfzeichen mit Umlauten oder Emojis konnte einen Fehler auslösen. Das betraf auch die **Telegram-Freigabe aus Phase 1**. Jetzt wird überall byte-sicher verglichen; Tests sind ergänzt. Im Originalprojekt besteht die Lücke noch. Sie wirkt dort aber nur, wenn ein Telegram-Bot läuft, und der ist noch nicht eingerichtet.
2. **Anmeldung im echten Browser blockiert:** Der Header `no-referrer` ließ Browser „Origin: null“ senden. Deshalb steht er jetzt auf `same-origin`.
3. **Ruckeln auf alten Macs vermieden:** Der feste Hintergrund wurde entfernt.

## Firefox und MacBook 2012
- Einfaches HTML und CSS, nur bewährte Funktionen, Systemschriften, keine Animationen außer einem kurzen Statuspuls.
- Seitengröße: unter 10 KB plus 3 KB CSS.
- Firefox speichert das Passwort auf Wunsch; die Formularfelder sind dafür richtig gekennzeichnet.
- Firefox kann bei `http://127.0.0.1` einen Hinweis „Verbindung nicht sicher“ zeigen. Bei Adressen auf dem eigenen Rechner ist das in Ordnung, weil die Daten den Rechner nie verlassen. HTTPS kommt mit dem Server.

## Auf dem MacBook übernehmen
Die ZIP-Datei `jarvis-phase2-schritt2.zip` in einen **neuen** Ordner entpacken. Deine bisherigen Ordner bleiben unverändert. Deine Daten aus `data/` kannst du später kopieren; für den ersten Test ist das nicht nötig.
