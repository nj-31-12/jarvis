# 02 – Lokaler Betrieb vs. günstiges Cloud-Hosting

## Dein MacBook Pro 13" (2012) realistisch eingeschätzt
- Offiziell maximal **macOS 10.15 Catalina**, keine Sicherheitsupdates mehr.
- Hermes verlangt **Python 3.11+** und aktuelle Werkzeuge (Node.js, ffmpeg). Auf Catalina ist das mühsam; Homebrew unterstützt es nicht mehr offiziell.
- **Wichtigster Punkt:** Ist das MacBook aus oder zugeklappt, schläft JARVIS. Anforderung Nr. 1 („rund um die Uhr, auch bei ausgeschaltetem MacBook“) ist lokal **nicht erfüllbar**.

➡️ Das MacBook ist ideal als **Entwicklungs- und Testrechner** (dieser Prototyp läuft dort mit Python 3.8+) und für **Obsidian**. Der Dauerbetrieb gehört auf einen kleinen Server.

## Vergleich

| Kriterium | Lokal (MacBook 2012) | Kleiner VPS (z. B. Hetzner, Netcup) | Gratis-Cloud (Oracle Free Tier) |
|---|---|---|---|
| 24/7 bei ausgeschaltetem Mac | ❌ | ✅ | ✅ |
| Kosten/Monat | 0 € (+ Strom) | ca. 4–7 € | 0 € |
| Einrichtung für Anfänger | mittel (altes macOS) | mittel (Anleitung folgt) | schwer (Kapazitäts-Engpässe, Konto-Sperren kommen vor) |
| Hermes offiziell unterstützt | eingeschränkt | ✅ („Run it on a $5 VPS“) | ✅ (ARM) |
| Sicherheit | veraltetes OS | aktuelles Ubuntu, Firewall | gut |
| Datenstandort | zu Hause | Deutschland/EU wählbar | wählbar |
| Lokales Whisper (Sprache) | sehr langsam | okay bei kurzen Sprachnachrichten | okay |

## Empfehlung
1. **Woche 1–2:** Alles lokal auf dem MacBook testen (dieser Prototyp, Telegram-Testbot). Kosten: 0 €.
2. **Ab Woche 3:** Ein kleiner **VPS in Deutschland** (2 vCPU, 4 GB RAM, Ubuntu 24.04). Das passt ins Budget, und die Daten bleiben in der EU.
3. Serverless-Optionen von Hermes (Modal, Daytona) erst später prüfen. Sie sind günstig im Leerlauf, für Anfänger aber schwerer zu durchschauen.

> ⚠️ Preise ändern sich. Vor der Buchung den aktuellen Preis auf der Anbieterseite prüfen. **Eine Buchung erfolgt nur nach deiner ausdrücklichen Genehmigung.**
