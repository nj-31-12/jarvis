# 06 – Sichere Telegram-Testintegration

> ⚠️ Für die folgenden Schritte brauchst du einen Telegram-Bot. Das Anlegen ist kostenlos, ist aber eine Kontoaktion. **Mach das erst, wenn du es mir ausdrücklich freigibst.** Bis dahin nutzt du den Simulator: `python3 -m jarvis chat`.

## Sicherheitsmerkmale (im Code umgesetzt und getestet)
| Schutz | Wie | Datei |
|---|---|---|
| Nur du darfst schreiben | Whitelist `allowed_user_ids`; ohne Whitelist startet der Bot nicht | `telegram_bot.py` |
| Nur private Chats | Gruppen werden ignoriert | `telegram_bot.py` |
| Freigabe gehört zu genau einer Aktion | HMAC-Signatur über Entscheidung + Aktions-ID + Inhalts-Hash + Zufallswert | `approval.py` |
| Kein Wiederverwenden | Freigabe ist einmalig (atomare Datenbank-Änderung) | `approval.py` |
| Ablaufzeit | Standard 60 Minuten | `config/jarvis.json` |
| Inhalt nachträglich geändert? | Hash-Vergleich direkt vor der Ausführung | `approval.py` |
| „Ablehnen“-Button kann nicht zu „Freigeben“ umgebaut werden | Entscheidung ist Teil der Signatur | `approval.py` |
| Token geheim | nur in `.env` (Rechte 600), wird nie ausgegeben | `config.py` |
| Nachts stumm | Freigabe-Anfragen nachts ohne Ton | `notify.py` |
| Gestohlenes Handy | `/stop` schaltet ab, Wiedereinschalten nur lokal | `killswitch.py` |

Zusätzlich solltest du in Telegram die **Zwei-Schritt-Bestätigung** aktivieren: Einstellungen → Datenschutz und Sicherheit → Zweistufige Bestätigung.

## Einrichtung (erst nach deiner Freigabe)
1. In Telegram **@BotFather** öffnen → `/newbot` → Name z. B. „JARVIS Test“ → Benutzername z. B. `deinname_jarvis_test_bot`.
2. Den angezeigten **Token** kopieren. Er ist wie ein Passwort, also niemandem zeigen und nirgends posten.
3. Deine **Telegram-Benutzer-ID** herausfinden, z. B. über den Bot **@userinfobot** (zeigt eine Zahl wie `123456789`).
4. Im Projektordner:
   ```bash
   cp .env.example .env
   chmod 600 .env
   python3 -m jarvis secret
   ```
   Die ausgegebene Zeile `JARVIS_APPROVAL_SECRET=…` und den Token in `.env` eintragen.
5. `cp config/jarvis.example.json config/jarvis.json` und bei `allowed_user_ids` deine Zahl eintragen.
6. Starten:
   ```bash
   python3 -m jarvis telegram
   ```
7. In Telegram deinem Bot `/hilfe` schreiben und `/post Testpost` ausprobieren. Danach auf ✅ tippen; es wird nur simuliert.

## Später mit Hermes: zwei Bots
- **Bot 1 „JARVIS“** gehört Hermes (Gespräche, Sprachnachrichten, Briefing).
- **Bot 2 „JARVIS Freigabe“** gehört nur dem Guard. Hermes kennt dessen Token nicht und kann deshalb nichts freigeben.
