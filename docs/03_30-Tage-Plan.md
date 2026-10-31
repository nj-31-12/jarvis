# 03 – 30-Tage-Entwicklungsplan

Zeitaufwand: ca. **30–45 Minuten pro Tag** neben der Ausbildung. 🔐 = braucht deine ausdrückliche Genehmigung (Installation, Konto, Kosten).

## Woche 1 – Grundlagen & Prototyp (lokal, 0 €)
| Tag | Aufgabe | Ergebnis |
|---|---|---|
| 1 | Projektordner aufs MacBook holen, `python3 --version` prüfen | Python läuft |
| 2 | `python3 -m jarvis demo` ausführen und Ausgabe lesen | Du verstehst den Ablauf |
| 3 | `python3 -m unittest -v`; `docs/01_Architektur.md` lesen | 21 Tests grün |
| 4 | Simulator `python3 -m jarvis chat`: Idee, Post, Mail, „fremd“ testen | Freigabe verstanden |
| 5 | 🔐 Obsidian installieren (kostenlos), `data/vault` als Vault öffnen | Wissensbasis sichtbar |
| 6 | 3 Ziele in `01_Ziele` als `- [ ]` eintragen, Briefing testen | persönliches Briefing |
| 7 | Rückblick: Was fehlt? Wünsche an mich notieren | Liste für Woche 2 |

## Woche 2 – Telegram-Test & eigene Funktionen (lokal, 0 €)
| Tag | Aufgabe | Ergebnis |
|---|---|---|
| 8 | 🔐 Telegram-Testbot bei @BotFather anlegen | Token in `.env` |
| 9 | `python3 -m jarvis telegram`, Freigabe per Handy testen | echte Buttons |
| 10 | Nachtruhe-Zeiten und Recherche-Themen in `config/jarvis.json` anpassen | deine Regeln |
| 11–12 | Mit Claude Code: Ideen-Bewertung verbessern (Scoring, Umsatzrechner) | bessere Analysen |
| 13 | Content-Vorlagen für Fitness-Posts erstellen | Skill-Entwurf |
| 14 | Sicherheits-Review: Angriffe im Simulator durchspielen | Vertrauen ins System |

## Woche 3 – Server & Hermes (ca. 5–7 € + API-Guthaben)
| Tag | Aufgabe | Ergebnis |
|---|---|---|
| 15 | 🔐 VPS buchen (Deutschland, Ubuntu 24.04), SSH-Schlüssel statt Passwort | Server läuft |
| 16 | Server absichern: Updates, Firewall (`ufw`), Benutzer `hermes` + `guard` | Grundschutz |
| 17 | 🔐 Hermes installieren (offizielles Install-Skript), `hermes doctor` | Hermes läuft |
| 18 | 🔐 API-Guthaben (z. B. 10 € Prepaid) + Ausgabenlimit beim Anbieter | Modelle nutzbar |
| 19 | `hermes tools`: Terminal/Code-Ausführung AUS, Websuche/Obsidian AN | sichere Werkzeuge |
| 20 | Guard auf Server; Guard als MCP-Server an Hermes anbinden | Freigabe-Pflicht aktiv |
| 21 | 🔐 Hermes-Telegram (Bot 1) + Freigabe-Bot (Bot 2) verbinden | 2-Bot-Setup |

## Woche 4 – Automatisierung & Alltag
| Tag | Aufgabe | Ergebnis |
|---|---|---|
| 22 | Cron: Nachtrecherche 02:00 (günstiges Modell, 3 Themen) | Nachtarbeit |
| 23 | Cron: Morgenbriefing 07:00 an Telegram | Tagesbriefing |
| 24 | Sprachnachrichten testen (STT) | Sprachsteuerung |
| 25 | Vault-Sync per Git (privates Repo) | Obsidian überall |
| 26 | Skills: Geschäftsideen-Analyse, Content-Planer | wiederverwendbar |
| 27 | Kosten prüfen (`/usage`), Limits anpassen | Budget im Griff |
| 28 | Notaus-Übung: `/stop` per Handy, `resume` am Server | Notfall geübt |
| 29 | Audit-Log prüfen, Backup einrichten | Nachvollziehbarkeit |
| 30 | Rückblick + Plan Phase 3 (E-Mail/Kalender lesend, WhatsApp, ChatGPT-API) | Roadmap |

## Danach (Phase 3+, jeweils 🔐)
- E-Mail/Kalender **nur lesend** über eigenes, separates Konto, kein Ausbildungs-Postfach.
- Echte Ausführer einzeln freischalten (erst Entwürfe, dann Versand).
- WhatsApp als zweiter Kanal.
- ChatGPT-API als automatische Zweitmeinung.
- Spezialisierte Subagenten (Content, Shop-Analyse, Lernen).
