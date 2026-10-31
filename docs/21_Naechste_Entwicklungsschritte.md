# 21 – Nächste Entwicklungsschritte (nach Version 5)

Reihenfolge nach Nutzen und Risiko. **Jeder Schritt mit ★ braucht vorher deine ausdrückliche Freigabe** (Kosten, Konto, Installation oder Datenübertragung).

| # | Schritt | Warum | Freigabe nötig | Kosten (Schätzung) |
|---|---|---|---|---|
| 1 | **Version 5 auf dem Mac testen** (Python 3.8.2) | Bisher nur unter Python 3.11–3.13 getestet | Installation von Version 5 (nur entpacken) | 0 € |
| 2 | **Erste echte KI anbinden**: ein Adapter für genau ein Modell | Chat, Ideen und Recherche werden wirklich nützlich | ★ Konto, ★ API-Kosten, ★ Datenschutzprüfung | ca. 2–10 €/Monat bei deinem Budgetlimit |
| 3 | **Telegram-Freigaben einrichten** | Freigeben vom Handy, ohne Browser | ★ Telegram-Bot anlegen | 0 € |
| 4 | **Kalender lesend** (Google Kalender, nur Leserecht) | Echtes Tagesbriefing | ★ Kontoverbindung (OAuth) | 0 € |
| 5 | **Gmail lesend + Entwürfe** (kein Senden) | E-Mail-Zusammenfassung im Briefing | ★ Kontoverbindung, nur nötigste Rechte | 0 € |
| 6 | **Verschlüsselte Sicherungen** mit `age` | Sicherungen sicher außer Haus lagern | ★ Installation eines kleinen Werkzeugs | 0 € |
| 7 | **Server-Testbetrieb** nach docs/19 | JARVIS läuft rund um die Uhr | ★ Server bestellen, ★ Datenübertragung | ca. 4–7 €/Monat |
| 8 | **Shopify lesend** | Umsatz und Bestand im Briefing | ★ Shopify-App mit Leserecht | 0 € |
| 9 | **Echte Websuche** für die Nachtrecherche | Quellen statt Testdaten | ★ ggf. kostenpflichtige Such-API | 0–5 €/Monat |
| 10 | **Sprache** (Vorlesen am Mac besteht schon; später Spracheingabe) | Bequemer im Alltag | ★ ggf. Installation | 0 € (lokal) |

**Langfristig (nur geplant, siehe docs/16):** Mentor- und Forschungsmodus, Lernpartner für die Ausbildung, Haushaltsassistent. Diese Funktionen werden erst gebaut, wenn die Schritte 1–5 stabil laufen.

**Architektur-Grundsätze für alle nächsten Schritte:**
1. Neue Fähigkeiten kommen nur als **Skill** mit eigener Berechtigung, Testadapter und Tests.
2. Neue Modelle nur über die **Erlaubnisliste** (`ai.models`).
3. Alles, was nach außen geht oder etwas verändert, läuft über die **Freigabezentrale**.
4. Jede Version entsteht in einer **eigenen Kopie**, mit Prüfbericht, unabhängiger Prüfung durch ChatGPT und Rückfallplan.
