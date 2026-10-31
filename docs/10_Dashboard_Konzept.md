# 10 – Konzept: futuristisches, aber leichtes JARVIS-Dashboard

## Leitlinie
**Futuristisch durch Gestaltung, nicht durch Rechenlast.** Ein MacBook von 2012 schafft keine dauerhaften 3D-Effekte im Browser. Das Dashboard wirkt deshalb durch Typografie, Raster, feine Linien und gezielte Akzente. Aufwendige Effekte bleiben ein **optionaler Schalter**.

## Gestaltung
- Dunkles „HUD“-Thema: fast schwarzes Blaugrau, feine Rasterlinien, ein kühler Akzent (Cyan) für Interaktion, Bernstein für „braucht Aufmerksamkeit“, Rot nur für Notaus und Fehler.
- Zahlen in einer Monospace-Schrift mit gleichbreiten Ziffern, wirkt wie ein Instrument.
- Statusanzeigen als kleine „Pills“ (Nachtruhe, Notaus, Budget, offene Freigaben), sofort erfassbar.
- **Eine** dezente Bewegung: ein langsam pulsierender Statusring beim Start. Keine Dauer-Animationen. `prefers-reduced-motion` wird respektiert.

## Seiten und Bausteine

| Bereich | Inhalt | Schritt |
|---|---|---|
| Übersicht | Status, Budget, offene Freigaben, letzte Meldungen, Morgenbriefing-Auszug | 3 |
| Wissen | Inbox, Suche, Notiz lesen (sichere Anzeige) | 3 |
| Morgenbriefing | das aktuelle Briefing, gut lesbar auf dem Handy | 3 |
| Chat | Befehle und Fragen an JARVIS, Verlauf aus dem Nachrichtenprotokoll | 4 |
| Freigabezentrale | offene Aktionen mit genauem Inhalt, Ablaufzeit und Risiko; Freigeben nur mit Code (falls aktiviert) | 5 |
| Projekte & Aufgaben | Projekte aus `02_Projekte`, Aufgaben aus Checklisten `- [ ]` (nur lesen; Änderungen über Freigabe) | 6 |
| Geschäftsanalyse | Bewertungsmatrix der Ideen, Abdeckung der 12 Bereiche | 6 |
| Status & Notaus | Systemzustand, Protokollprüfung, großer Notaus-Knopf | 6 |
| Sprache | Mikrofon- und Vorlese-Knopf (erst mit Server) | später |
| 3D-Wissensnetz | Notizen als Netz; zuerst 2D, 3D nur per Schalter | später |

## Leistungsbudget (verbindlich)
- Kein Framework und keine Einbindungen aus dem Internet, nur ein kleines eigenes CSS und JavaScript.
- Ziel: unter 150 KB pro Seite, Seitenaufbau in unter 1 Sekunde auf dem MacBook.
- Keine Dauerabfragen. Neue Meldungen werden höchstens alle 15 Sekunden geholt, und nur, solange der Tab sichtbar ist.
- Nur bewährte CSS- und JavaScript-Funktionen, damit es auch mit älteren Firefox-Versionen läuft. Deine Version siehst du unter *Firefox → Über Firefox*.

## 3D als optionale Erweiterung
1. **Stufe 1 (2D):** Das Wissensnetz wird einmal berechnet und als Bild gezeichnet (Canvas). Das ist für den alten Mac geeignet.
2. **Stufe 2 (3D, Schalter „Effekte“):** Erst nach einem Leistungstest auf dem Gerät und standardmäßig aus. Dafür käme eine 3D-Bibliothek ins Projekt. Sie wird mitgeliefert, nicht aus dem Internet geladen.
3. 3D läuft nie automatisch auf dem Handy oder bei aktivem Energiesparmodus.

## Sicherheit der Oberfläche
Es gilt das Konzept aus `docs/03`, Abschnitt Phase 2:
- nur `127.0.0.1`
- Passwort-Anmeldung
- sichere Cookies und Prüfzeichen gegen gefälschte Anfragen
- strenge Sicherheits-Header
- Notaus im Browser ja, Aufheben nur am Rechner
