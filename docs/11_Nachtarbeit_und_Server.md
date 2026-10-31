# 11 – Echte Nachtarbeit: ehrlicher Stand und Plan

## Ehrlicher Stand (30.10.2026)
- **Claude Code** arbeitet nur, solange eine Aufgabe in der Sitzung läuft. Wenn du den Browser schließt, läuft die gerade begonnene Arbeit in der Cloud zu Ende. Danach passiert **nichts mehr**, bis du wieder schreibst.
- Die Recherche für das Morgenbriefing vom 30.10. ist deshalb **in der laufenden Sitzung** entstanden, nicht im Hintergrund.
- Der Befehl `/nacht` im Prototyp **simuliert** Nachtarbeit. Echte Recherche braucht ein echtes Sprachmodell und einen Dienst, der nachts läuft.

## Drei Wege zu echter Nachtarbeit

| Weg | Läuft bei ausgeschaltetem Mac | Kosten | Telegram | Zugriff auf deinen Vault | Aufwand |
|---|---|---|---|---|---|
| 1. Geplante Aufgabe in Claude Code (Cloud) | ja | keine Zusatzkosten, nutzt dein Claude-Abo (Nutzungslimits beachten) | nein | nur über ein Git-Repository | gering |
| 2. Eigener Server mit Hermes + JARVIS-Guard | ja | ca. 4–7 € Server + KI-Guthaben | ja | ja (Git-Synchronisation) | mittel |
| 3. Nur MacBook (z. B. zeitgesteuert) | **nein** | 0 € | ja | ja | gering, erfüllt aber dein Ziel nicht |

**Empfehlung:**
- **Übergang:** Weg 1. Eine geplante Aufgabe recherchiert z. B. werktags um 5:30 Uhr und legt das Briefing ab. Dafür braucht es deine Freigabe, und Ergebnisse landen in einer Claude-Code-Sitzung, nicht in Telegram.
- **Ziel:** Weg 2 ab Woche 3 des Plans.

## Zielarchitektur (Weg 2)
```
Server (Deutschland, Ubuntu)
├── Benutzer "hermes": Hermes Agent
│     ├── Cron 02:00  Nachtrecherche (günstiges Modell, 3 Bereiche aus der Rotation)
│     ├── Cron 06:45  Morgenbriefing erstellen → wartet bis 07:00
│     └── Telegram-Bot 1 (Gespräche, Sprachnachrichten)
├── Benutzer "guard": JARVIS-Guard
│     ├── Freigabeschicht + Telegram-Bot 2 (nur Freigaben)
│     ├── Nachtruhe 22–7 Uhr: nur stumme Meldungen, Rest ins Briefing
│     ├── Kostenbremse: Monatslimit KI 12 € (Server 4–7 € → Summe ≤ 20 €)
│     └── Notaus, Audit-Log
├── Vault (Git) → MacBook/Handy synchronisiert
└── Weboberfläche nur über privaten Tunnel (z. B. Tailscale), nie offen im Internet
```

## Sicherheitsmaßnahmen auf dem Server
- SSH nur mit Schlüssel und ohne Root-Login, Firewall (`ufw`), automatische Sicherheitsupdates.
- Getrennte Linux-Benutzer. Geheimnisse liegen mit Rechten `600` und nur beim jeweiligen Dienst.
- `hermes` darf im Vault nur in `00_Inbox/JARVIS` **neue** Dateien anlegen. Das wird über Dateirechte gesichert, nicht über das Sprachmodell.
- Hermes ohne Terminal- und Code-Werkzeuge. YOLO-Modus nie aktivieren.
- Tägliche Sicherung von Vault und Audit-Log.
- Ausgabenlimit zusätzlich direkt beim KI-Anbieter (Prepaid).

## Kosten im Überblick (Ziel ≤ 20 €/Monat)

| Posten | Betrag | Status |
|---|---|---|
| Server | ca. 4–7 € | nicht gebucht |
| KI-Guthaben (Prepaid, Limit) | max. 12 € | nicht aktiviert |
| Stimme (Piper), Sprach-zu-Text (Whisper lokal), Telegram, Tailscale | 0 € | nicht eingerichtet |
| **Summe** | **ca. 16–19 €** | |

## Reihenfolge (jeder Punkt mit 🔐 braucht deine Freigabe)
1. Phase 2 lokal fertigstellen (Browseroberfläche, 0 €).
2. 🔐 Übergangsweise eine geplante Claude-Code-Aufgabe für die Morgenrecherche.
3. 🔐 Server buchen und absichern.
4. 🔐 Hermes installieren und KI-Guthaben aufladen.
5. 🔐 Telegram-Bots verbinden.
6. Nachtjobs und Briefing umstellen. Danach zwei Wochen beobachten: Kosten, Qualität, Ruhe in der Nacht.
