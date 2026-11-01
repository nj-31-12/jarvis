# JARVIS vollständig benutzen (Stand 21)

**Ein Link für alles:** http://127.0.0.1:8765 (nur solange JARVIS läuft)

## Starten
```bash
lsof -ti tcp:8765 | xargs kill 2>/dev/null; sleep 2; cd ~/JARVIS/jarvis-nj && (sleep 4; open http://127.0.0.1:8765) & python3 -m jarvis web
```
Stoppt einen eventuell noch laufenden alten JARVIS, startet den neuen und öffnet den Browser.

## Die Bereiche
| Menü | Wofür |
|---|---|
| Übersicht | Datenkugel, Status, Budget, Schnellzugriff |
| Chat | Mit JARVIS schreiben oder sprechen (rotes Reaktor-Design) |
| Second Brain | Dein Wissen als Kopf → Gehirn → Innenansicht, Aufgaben, Ziele, Lektionen, Strategie-Werkstatt, Coach |
| Team | 9 KI-Mitarbeiter, Team-Runden zu deinen Aufgaben |
| Wissen | Suche in allen Notizen |
| Freigaben | Alles, was nach außen wirken würde, wartet hier auf dein OK |

## Sprechen und Hören
- **Sprechen:** ⌥ (Option) halten oder 🎙-Knopf halten (Chrome/Safari). In Firefox: zweimal `fn` (Mac-Diktat).
- **„Jarvis“ rufen:** Schalter „Auf ‚Jarvis' hören“ (nur Chrome/Safari, Ton geht zur Erkennung an Google/Apple).
- **JARVIS hören:** 🔊 an einer Antwort oder „Antworten automatisch sprechen“. Stimme: 🎬 Film · JARVIS · Natürlich.
- Beste Mac-Stimme: Systemeinstellungen → Bedienungshilfen → Gesprochene Inhalte → Systemstimme → Anpassen → „Markus“.

## Wichtige Chat-Befehle
`/strategie <Idee>` · `/idee <Text>` · `/notiz <Text>` · `/ziel <Text>` · `/suche <Begriff>` · `/briefing` · `/status` · `/hilfe`

## Update
1. https://github.com/nj-31-12/jarvis/archive/refs/heads/aktuell.zip herunterladen
2. `sh ~/JARVIS/jarvis-nj/werkzeuge/update-mac.sh`
3. JARVIS mit dem Start-Befehl oben neu starten, im Browser `cmd + shift + R`
