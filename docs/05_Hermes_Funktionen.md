# 05 – Vorhandene Hermes-Funktionen (geprüft im offiziellen Repo)

Quelle: https://github.com/NousResearch/hermes-agent (README + Doku unter `website/docs`, Stand Oktober 2026, MIT-Lizenz).

| Deine Anforderung | Hermes-Funktion | Status | Eigenbau nötig? |
|---|---|---|---|
| 1. Rund um die Uhr | Gateway-Prozess auf VPS; Terminal-Backends local/Docker/SSH/Modal/Daytona | ✅ vorhanden | nein |
| 2. Nachts recherchieren | **Cron-Scheduler** (`hermes cron`, natürliche Sprache), Websuche-Tool, Skills pro Job, Modell pro Job festlegbar | ✅ | nur Prompts/Skills |
| 3./12. Nachts nicht stören | Cron-Zustellung an Plattform oder **lokale Dateien** | ⚠️ teilweise | **ja:** Nachtruhe-Logik (stumme Nachrichten, Warteschlange) → `notify.py` |
| 4. Morgenbriefing per Telegram | Cron-Job mit Zustellung an Telegram | ✅ | nur Prompt |
| 5./6. Ideen & Content | Skills (offener Standard agentskills.io), Subagenten, Gedächtnis | ✅ | eigene Skills (Prompts) |
| 7. E-Mail & Termine | E-Mail-Plattform, MCP-Server für Kalender | ✅ | **Freigabe davor schalten** |
| 8. Sprachnachrichten | Telegram-Sprachmemos werden automatisch transkribiert (STT, z. B. Whisper); Antwort auch als Sprachblase (TTS) | ✅ | nein |
| 9. Projekte dokumentieren | Gebündelter **Obsidian-Skill** (lesen, suchen, anlegen, bearbeiten); Gedächtnis + FTS5-Sitzungssuche | ✅ | Ordnerkonzept + Schreibschutz |
| 10. Weiterbildung | Gedächtnis, Benutzermodell (Honcho), Skills, die mitlernen | ✅ | nein |
| 11. Weitere Agenten koordinieren | Subagenten/Delegation, Kanban, Mixture-of-Agents | ✅ | später |
| Telegram | Integriert, `TELEGRAM_ALLOWED_USERS` als Whitelist, QR-Einrichtung | ✅ | nein |
| WhatsApp | Integriert (Phase 2) | ✅ | nein |
| Freigaben | Eigenes System für **gefährliche Befehle** (Terminal/Code), Freigabe auch per Gateway, „Hardline“-Sperren, YOLO-Modus nur beim Start | ⚠️ für Terminal gedacht | **ja:** fachliche Freigaben (Mail, Posts, Konten) mit Signatur → JARVIS-Guard |
| Kostenkontrolle | `/usage`, `/insights`, günstiges Modell pro Cron-Job | ⚠️ Anzeige, kein hartes Limit | **ja:** harte Kostenbremse → `budget.py` + Anbieterlimit |
| Notabschaltung | `/stop` beendet die laufende Antwort, `hermes gateway stop` | ⚠️ | **ja:** globaler Notaus → `killswitch.py` |
| Protokollierung | Logs, Sitzungsdatenbank | ✅ | ergänzend: manipulationssicheres Audit-Log |
| Hooks | Gateway-, Plugin- und Shell-Hooks (`pre_tool_call` kann blockieren) | ✅ | nutzen wir als 2. Schutzschicht |
| Erweiterung | **MCP** (Model Context Protocol) | ✅ | JARVIS-Guard wird MCP-Server |

## Fazit
Etwa **80 % der Funktionen sind fertig in Hermes vorhanden.** Eigenbau brauchen wir nur für:
1. die **signierte Freigabeschicht** für fachliche Aktionen (Herzstück, im Prototyp fertig),
2. **Nachtruhe** mit stummen Nachrichten und Warteschlange,
3. eine **harte Kostenbremse** und einen **Notaus**,
4. **Skills/Prompts** für Briefing, Ideenanalyse und Content.

## Wichtige Hermes-Hinweise
- Den **YOLO-Modus** (`HERMES_YOLO_MODE`, `--yolo`) **nie** aktivieren. Er schaltet die Freigaben ab.
- Cron-Jobs können keine neuen Cron-Jobs anlegen. Das ist ein guter eingebauter Schutz gegen Endlosschleifen.
- Gateway-Hooks in `~/.hermes/hooks/` laufen ohne Sandbox. Dort nur geprüften Code ablegen.
