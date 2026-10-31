# 01 – Systemarchitektur JARVIS

## Grundidee in einem Satz
**Hermes ist das Gehirn, JARVIS-Guard ist der Türsteher, Telegram ist die Fernbedienung, Obsidian ist das Gedächtnis zum Nachlesen.**

Wir bauen nur, was Hermes nicht schon kann: vor allem die **technisch erzwungene Freigabeschicht**.

## Gesamtbild (Zielzustand ab Woche 3)

```
                ┌──────────────────────── Dein Smartphone ────────────────────────┐
                │  Telegram-Chat "JARVIS"            Telegram-Chat "JARVIS Freigabe" │
                └──────────┬───────────────────────────────────────┬─────────────────┘
                           │ Text, Sprachnachrichten               │ ✅/❌ Buttons (signiert)
                           ▼                                       ▼
┌───────────────────── Cloud-Server (VPS, läuft 24/7) ────────────────────────────────────┐
│                                                                                         │
│  Linux-Benutzer "hermes"                    │  Linux-Benutzer "guard" (getrennt!)       │
│  ┌──────────────────────────────────────┐   │  ┌─────────────────────────────────────┐  │
│  │ Hermes Agent                         │   │  │ JARVIS-Guard (dieses Projekt)       │  │
│  │ • Gateway (Telegram-Bot 1)           │   │  │ • Policy: erlaubt/Freigabe/verboten │  │
│  │ • Gedächtnis, Skills, Sitzungssuche  │──►│  │ • Freigabe-DB + HMAC-Geheimnis      │  │
│  │ • Cron: Nachtrecherche, Briefing     │MCP│  │ • Telegram-Bot 2 (nur Freigaben)    │  │
│  │ • Sprach-zu-Text (Whisper)           │nur│  │ • Executor (Phase 1: Simulation)    │  │
│  │ • Websuche                           │Vor-│ │ • Kostenbremse, Audit-Log, Notaus   │  │
│  │ • KEIN Terminal, KEIN Mail-Versand   │schl│ └─────────────────────────────────────┘  │
│  └───────────────┬──────────────────────┘ äge│                                          │
│                  │ schreibt NUR in 00_Inbox/JARVIS (Dateirechte des Betriebssystems)    │
│                  ▼                                                                      │
│  Obsidian-Vault (Markdown-Ordner) ──── Git (privates Repo) ────► MacBook / Handy        │
└─────────────────────────────────────────────────────────────────────────────────────────┘
        ▲ KI-Modelle per API (OpenRouter u. a.)      ▲ ChatGPT: Zweitmeinung (anfangs manuell)
```

## Komponenten und Rollen

| Komponente | Rolle | Eigenbau? |
|---|---|---|
| **Hermes Agent** | Agentensteuerung, Gedächtnis, Cron, Telegram/WhatsApp-Gateway, Sprachnachrichten, Websuche, Obsidian-Skill, Subagenten | Nein – vorhanden |
| **JARVIS-Guard** | Freigabeschicht, Policy, Audit, Kostenbremse, Notaus, simulierte Ausführung | **Ja** (dieser Prototyp) |
| **Telegram-Bot 1** | Gespräche mit JARVIS (gehört Hermes) | Konfiguration |
| **Telegram-Bot 2** | Nur Freigaben. Token kennt NUR der Guard | Ja (vorhanden im Prototyp) |
| **Obsidian** | Langfristige, für dich lesbare Wissensbasis | Ordnerstruktur + Vorlagen |
| **Claude Code** | Entwicklung, Tests, Wartung des Guards und der Skills | – |
| **ChatGPT** | Zweitmeinung zu Strategien (zuerst manuell per Copy & Paste, später optional API) | – |
| **WhatsApp** | Zweiter Kanal (Phase 2, über Hermes-Gateway) | Konfiguration |

## Warum die Freigabe nicht vom Sprachmodell umgangen werden kann

Die Sicherheit hängt **nicht** davon ab, dass das Modell sich „an Regeln hält“. Sie ist technisch erzwungen:

1. **Getrennte Benutzer:** Hermes läuft als Linux-Benutzer `hermes`, der Guard als `guard`. `hermes` kann Geheimnis, Datenbank und Bot-2-Token des Guards nicht lesen (Dateirechte `600`).
2. **Nur Vorschläge:** Der Guard bietet Hermes über MCP ausschließlich `propose_action` und `list_pending` an. Eine Funktion „approve“ existiert für Hermes schlicht nicht.
3. **Freigabe nur über Bot 2:** Freigaben kommen ausschließlich als Telegram-Button-Klick bei Bot 2 an. Telegram bestätigt die Absender-ID; der Guard prüft zusätzlich Whitelist, Chat, HMAC-Signatur, Ablaufzeit und Einmaligkeit.
4. **Inhalt eingefroren:** Die Signatur enthält einen Hash des genauen Inhalts. Ändert jemand nach der Freigabe die Empfängeradresse, wird die Ausführung gestoppt.
5. **Deny by default:** Unbekannte Aktionstypen sind verboten. Käufe, Zahlungen und Bankzugriffe sind auch mit Freigabe gesperrt.
6. **Hermes ohne gefährliche Werkzeuge:** Terminal, Code-Ausführung und direkter Mail-Versand sind in Hermes deaktiviert. Hermes' eigenes Freigabesystem bleibt als zweite Schutzschicht aktiv.
7. **Notaus:** `/stop` stoppt alles sofort; Wiedereinschalten geht nur lokal am Server.

## Datenflüsse – Beispiel „Post veröffentlichen“
1. Du: „Mach mir einen Post zu Muskelaufbau-Fehlern“ (Bot 1).
2. Hermes erstellt den Entwurf, speichert ihn in `00_Inbox/JARVIS` und ruft `propose_action("publish_post", …)` auf.
3. Der Guard prüft die Policy, speichert die Aktion und schickt dir über Bot 2 eine Nachricht mit signierten Buttons.
4. Du drückst ✅. Der Guard prüft alles und führt aus (Phase 1: nur simuliert in `data/sandbox/outbox`).
5. Das Ergebnis landet im Audit-Log und im Tagesbriefing.

## Projektstruktur

```
jarvis/
├── README.md                ← Start hier
├── config/jarvis.example.json
├── .env.example             ← Vorlage für Geheimnisse (echte .env nie teilen)
├── jarvis/                  ← Python-Code (nur Standardbibliothek)
│   ├── approval.py          ← Freigabeschicht (Herzstück)
│   ├── policy.py            ← erlaubt / Freigabe / verboten
│   ├── audit.py             ← Protokoll mit Hash-Kette
│   ├── budget.py            ← Kostenbremse
│   ├── killswitch.py        ← Notabschaltung
│   ├── notify.py            ← Nachtruhe & stumme Nachrichten
│   ├── obsidian.py          ← Vault-Zugriff (nur Inbox ohne Freigabe)
│   ├── llm.py               ← simuliertes Modell (Phase 1)
│   ├── actions_sim.py       ← simulierte Ausführer
│   ├── core.py              ← JARVIS-Logik & Befehle
│   ├── telegram_bot.py      ← echter Telegram-Testbot
│   └── __main__.py          ← Kommandozeile (demo, chat, …)
├── tests/test_security.py   ← 21 Sicherheitstests
├── vault-vorlage/           ← Obsidian-Vorlagen
└── docs/                    ← diese Dokumente
```
