# 04 – Erwartete laufende Kosten

Festgelegte Grenze (von dir bestätigt): **maximal 20 € zusätzlich pro Monat**, technisch abgesichert durch die Kostenbremse (Tageslimit 1 €, Monatslimit 15 € für KI-Aufrufe). Die Werte stehen in `config/jarvis.json`.

> Wichtig: **Claude Pro und ChatGPT Plus enthalten keinen API-Zugang.** Für einen Agenten, der allein nachts arbeitet, brauchst du API-Guthaben (Prepaid). Deine Abos nutzt du weiter für Entwicklung (Claude Code) und Zweitmeinungen (ChatGPT im Browser).

| Posten | Phase 1 (lokal, Woche 1–2) | Phase 2 (Server, ab Woche 3) | Bemerkung |
|---|---|---|---|
| Server (VPS, 2 vCPU/4 GB) | 0 € | ca. 4–7 € | Preis vor Buchung prüfen |
| KI-API (z. B. OpenRouter, Prepaid) | 0 € (simuliert) | ca. 5–10 € | günstige Modelle für Nachtjobs, starke nur bei Bedarf |
| Sprach-zu-Text | 0 € | 0 € (lokales Whisper) bzw. < 1 € per API | |
| Websuche | 0 € | 0–2 € | viele Anbieter haben Gratis-Kontingente |
| Telegram | 0 € | 0 € | |
| Obsidian | 0 € | 0 € | Sync per Git statt kostenpflichtigem Obsidian Sync |
| Domain / Sonstiges | 0 € | 0 € | nicht nötig |
| **Summe** | **0 €** | **ca. 9–19 €** | |

## So bleiben die Kosten unter Kontrolle
- **Prepaid statt Abo:** Bei OpenRouter lädst du z. B. 10 € auf. Ist das Guthaben leer, passiert nichts weiter. Es gibt keine Überraschungsrechnung.
- **Ausgabenlimit pro API-Schlüssel** beim Anbieter setzen (zusätzlich zur JARVIS-Kostenbremse).
- **Nachtjobs mit günstigen Modellen**, kurze Recherchen, maximal 3 Themen pro Nacht.
- **Hermes `/usage` und `/insights`** zeigen den Verbrauch an. Das Budget steht auch im Morgenbriefing.
- WhatsApp kommt erst in Phase 2 und läuft über eine Bridge. Eine offizielle Business-API wäre kostenpflichtig.
