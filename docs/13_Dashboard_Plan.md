# 13 – Plan: futuristisches JARVIS-Dashboard (Schritte 3–6 und danach)

Baut auf dem Konzept in `docs/10` auf. Die Anmeldeseite aus Schritt 2 zeigt bereits den Stil: dunkles HUD, feines Raster, Cyan als Akzent.

## Grundsätze
1. **Leicht vor schön:** Jede Seite ist sofort nutzbar, auch ohne JavaScript. JavaScript kommt nur dort hinzu, wo es echten Nutzen bringt (Chat, Mikrofon), und auch dann ohne Framework.
2. **Sicher vor bequem:** Jede Aktion läuft über Sitzung, Prüfzeichen und die bestehende Freigabeschicht.
3. **Handy zuerst denken:** Alle Seiten funktionieren ab 360 px Breite.

## Aufbau (Laptop)
```
┌──────────────────────────────────────────────────────────────────────┐
│ ● JARVIS        Übersicht  Chat  Wissen  Projekte  Freigaben  ⏻     │
├──────────────────────────────────────────────────────────────────────┤
│ [Notaus aus] [Freigaben 1] [Budget 0,40/15 €] [Nachtruhe 22–7]       │
├───────────────────────────────┬──────────────────────────────────────┤
│ MORGENBRIEFING                │ KI-CHAT                              │
│ A. 3 Chancen …                │ > /idee …                            │
│ E. Nächste Schritte …         │ JARVIS: …                            │
├───────────────────────────────┼──────────────────────────────────────┤
│ PROJEKTE                      │ FREIGABEZENTRALE                     │
│ NYoung.Coaching  ▮▮▮▯▯        │ #3fa9 publish_post · 42 Min.         │
│ Scent Edit       ▮▮▯▯▯        │ [Details] [Ablehnen] [Freigeben*]    │
├───────────────────────────────┴──────────────────────────────────────┤
│ GESCHÄFTSBEREICHE: Abdeckung der Nachtrecherche (13 Bereiche)         │
└──────────────────────────────────────────────────────────────────────┘
  * Freigeben im Browser nur, wenn du TOTP aktivierst (Entscheidung offen)
```
**Handy:** dieselben Kacheln untereinander. Die Navigation sitzt als Leiste unten, damit sie mit dem Daumen erreichbar ist.

## Bausteine und Datenquellen (alles schon im Code vorhanden)

| Kachel | Quelle | Schritt |
|---|---|---|
| Statusleiste | `kill`, `gate.pending()`, `budget.status()`, `notifier.quiet_now()` | ✅ (2) |
| Morgenbriefing | `morning_briefing()` + Notizen aus `00_Inbox/JARVIS` (sichere Anzeige) | 3 |
| Wissensdatenbank | `vault.search()`, `vault.read()`, `markdown_safe.render()`; nur lesen | 3 |
| KI-Chat | `handle_text()`, Verlauf aus `notifier.history()`; anfangs ein Formular, später mit kleinem Skript ohne Neuladen | 4 |
| Neue Notiz | `vault.write_draft()`, nur in `00_Inbox/JARVIS` | 4 |
| Freigabezentrale | `gate.pending()`, `web_token()`, `on_web_decision()` | 5 |
| Projektübersicht | Notizen in `02_Projekte` mit Frontmatter `status`, `fortschritt` | 6 |
| Aufgaben | Checklisten `- [ ]` aus Projekten und Zielen (nur lesen) | 6 |
| Geschäftsanalyse | Bewertungsmatrix der Ideen und `rotation.coverage()` | 6 |
| Protokoll | `audit.tail()` und `audit.verify()` | 6 |

## Sprachsteuerung (später, in zwei Stufen)
1. **Vorlesen im Browser:** ein Knopf „Vorlesen“ am Briefing. Der Text wird mit `speakable()` vorbereitet. Wiedergabe zuerst über die Mac-Stimme. Hochwertige Stimmen kommen erst mit Server und deiner Freigabe.
2. **Sprechen zu JARVIS:** Der Mikrofon-Knopf nimmt im Browser auf, Whisper auf dem Server wandelt in Text um, und es antwortet die Erzähler-Stimme. Dafür muss die Mikrofonsperre im Sicherheits-Header gezielt gelockert werden. Das kommt erst mit HTTPS über den Server.

## 3D-Wissensnetz (optional, ganz am Ende)
- Zuerst eine **2D-Ansicht** des Notiz-Netzes (Verknüpfungen über `[[Wikilinks]]`), einmal berechnet und gezeichnet.
- 3D nur hinter einem Schalter „Effekte“, standardmäßig aus und nie automatisch auf dem Handy.
- Die 3D-Bibliothek würde mitgeliefert, nicht aus dem Internet geladen (die Sicherheitsregeln bleiben).

## Leistungsbudget (MacBook 2012)
- Unter 150 KB pro Seite. Seitenaufbau unter 1 Sekunde.
- Keine Dauer-Animationen, kein fester Hintergrund, keine Unschärfe-Effekte (`backdrop-filter`).
- Neue Meldungen höchstens alle 15 Sekunden, und nur bei sichtbarem Tab.

## Reihenfolge
| Schritt | Inhalt | Kosten |
|---|---|---|
| 3 | Navigation, Morgenbriefing, Wissensdatenbank (nur lesen) | 0 € |
| 4 | KI-Chat (noch mit simuliertem Modell), neue Notizen | 0 € |
| 5 | Freigabezentrale (Anzeige; Freigeben nur mit TOTP, falls gewünscht) | 0 € |
| 6 | Projekte, Aufgaben, Geschäftsanalyse, Protokoll | 0 € |
| danach 🔐 | Handy über Tailscale, Server, echte KI, Stimme, 3D | innerhalb von 20 € |
