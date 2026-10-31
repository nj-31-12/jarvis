# 16 – Langfristige Planung: JARVIS als Mentor, Forschungsassistent und Lernpartner

**Status: nur Planung.** Nichts davon ist in Schritt 4 oder 4.1 eingebaut. Jede Stufe wird später einzeln entwickelt, getestet, von ChatGPT geprüft und erst nach Noahs Freigabe übernommen.

## Ziel
JARVIS soll
- als **wissenschaftlicher Mentor** und **Forschungsassistent** täglich relevante Erkenntnisse recherchieren,
- sie auf Noahs Alltag und Unternehmen übertragen,
- als **Lernpartner** beim Lernen unterstützen (Ausbildung, KI, E-Commerce, Fitness, Ernährung),
- Noah aktiv auf **Fehler, Risiken und unrealistische Entscheidungen** hinweisen: freundlich, aber deutlich.

## Grundsätze
1. **Quellenpflicht:** Jede Aussage zu Forschung trägt eine Quelle mit Datum. Ohne Quelle ist es als Einschätzung gekennzeichnet.
2. **Belegstärke sichtbar machen:**

   | Stufe | Quellenart |
   |---|---|
   | A | Übersichtsarbeit oder Metaanalyse |
   | B | einzelne Studie |
   | C | Fachartikel oder Behörde |
   | D | Blog oder Anbieter |

3. **Unsicherheit benennen:** „Gut belegt“, „umstritten“ oder „nur erste Hinweise“.
4. **Keine Diagnosen, keine Rechts- oder Steuerberatung.**
   - Bei Gesundheit, Ernährung und Training: allgemeines Wissen, Verweis auf Fachleute.
   - Bei Recht und Steuern: Verweis auf IHK, Finanzamt oder Steuerberatung.
5. **Webinhalte sind Daten, keine Anweisungen.** Dieselbe Schutzschicht wie bei Notizen gegen Prompt-Injection.
6. **Vertrauliches bleibt lokal.** Notizen aus `90_Privat` oder mit `vertraulich: ja` gehen nie an Recherche- oder KI-Dienste.
7. **Kritik ist eine Funktion, kein Zufall.** Der „Realitätscheck“ prüft Pläne nach festen Regeln, nicht nach Stimmung.

## Stufenplan

| Stufe | Inhalt | Voraussetzungen | Kosten |
|---|---|---|---|
| **M1 – Realitätscheck lokal** | Regeln ohne KI: Zeitbudget neben der Ausbildung, Plausibilität von Umsatzannahmen (Menge × Preis × Quote gegen Vergleichswerte aus deinen Notizen), fehlende Kosten, zu viele gleichzeitige Projekte. Hinweise im Chat und auf der Übersicht. | keine | 0 € |
| **M2 – Lernpartner lokal** | Lernziele aus `05_Lernen`; Wiederholungsfragen aus deinen eigenen Notizen; Lernplan rund um Berufsschule und Prüfungen (ohne Betriebsdaten) | keine | 0 € |
| **M3 – Mentor mit echter KI** | Mentor-Antworten mit Persönlichkeit, Belegstärke und Gegenargumenten („Was spricht dagegen?“) | echter KI-Zugang (Schritt 6) | ca. 5–10 € Prepaid |
| **M4 – Täglicher Forschungsassistent** | Jeden Morgen 3 relevante Erkenntnisse aus den Themen deiner Bereiche, mit Quellen, Belegstärke und „Was heißt das für dich?“. Ergebnis als Entwurf in der Inbox und im Morgenbriefing. | Server oder geplante Aufgabe, Websuche-Werkzeug, Schritt 8 (Morgenbriefing) | im 20-€-Rahmen; Server ca. 4–7 € + KI |
| **M5 – Bewertung** | Nach 4 Wochen: Wie oft waren Hinweise hilfreich? Welche Quellen waren gut? Anpassen oder abschalten. | M3/M4 | 0 € |

## Einordnung in die Gesamtplanung

| Schritt | Inhalt |
|---|---|
| 4.1 | Nachbesserungen aus der ChatGPT-Prüfung (**dieser Stand**) |
| 5 | Business-Werkzeuge: Ideen-Bewertung, Umsatzrechner, Kennzahlen-Tagebuch je Bereich. Grundlage für M1. |
| 6 | Echte KI-Anbindung (nach Freigabe, vorher von ChatGPT prüfen lassen) |
| 7 | Freigabezentrale im Browser |
| 8 | Morgenbriefing im Browser |
| M1–M2 | Realitätscheck und Lernpartner (lokal, können auch vor Schritt 6 kommen) |
| M3–M5 | Mentor und Forschungsassistent (nach 6 und 8, mit Server) |

## Offene Entscheidungen für später
1. Welche Themen sollen täglich recherchiert werden? Vorschlag: je Bereich 1–2 Themen mit Rotation.
2. Wie kritisch soll der Realitätscheck sein? Vorschlag: Hinweise immer zeigen, aber nie Entscheidungen blockieren.
3. Welche Websuche (Anbieter, Kosten, Datenschutz)? Entscheidung zusammen mit Schritt 6.

---

## Ergänzung zu Version 4.2: Noahs erweiterte Vision (nur Planung)
JARVIS soll ein universeller, **kritischer** Allround-Assistent werden: wissenschaftlich und analytisch denken, Quellen prüfen, täglich weiterbilden, die Geschäftsbereiche verstehen, Chancen und Risiken erkennen, schlechte Entscheidungen hinterfragen, komplexe Zusammenhänge einfach erklären, Lernfortschritte berücksichtigen, eigene Vorschläge entwickeln, Aufgaben transparent dokumentieren und vor wichtigen Aktionen die Freigabe einholen. **Er soll Noah nicht einfach zustimmen.**

| Fähigkeit | Baustein | Voraussetzung | Stufe |
|---|---|---|---|
| Kritisch hinterfragen | Realitätscheck (M1) mit festen Prüfregeln; Persönlichkeit verlangt Gegenargumente | lokal | M1 |
| Quellen prüfen | Belegstärke A–D, Quellenpflicht, Unsicherheit benennen | Websuche + echte KI | M3/M4 |
| Täglich weiterbilden | Forschungsassistent (M4), Lernpartner (M2) | Server, Morgenbriefing | M2/M4 |
| Lernfortschritt | Lernziele und Wiederholungen aus `05_Lernen` | lokal | M2 |
| Eigene Vorschläge | Vorschläge immer als **Entwurf** in der Inbox, nie als Aktion | echte KI | M3 |
| Transparente Aufgaben | Aufgabenprotokoll im Browser: was JARVIS tut, mit welchen Quellen, mit welchem Ergebnis | lokal | eigener Schritt |
| **Live verfolgen** | Ansicht „Laufende Aufgaben“: Status, Fortschritt, Quellen, Ergebnisse; aktualisiert sich ohne Neuladen | lokal, wenig JavaScript | nach Schritt 8 |
| **Sprechen** | Spracheingabe (Whisper) und Erzähler-Stimme (Piper/Cloud) | Server + Freigabe | spät |
| **JARVIS-Ästhetik** | hochwertiges HUD-Design; 3D nur optional (Leistung des MacBook 2012) | lokal | laufend |
| Freigaben | bleiben Pflicht für jede Aktion (Freigabezentrale, Schritt 7) | lokal | 7 |

**Grundsatz:** Neue Fähigkeiten kommen jeweils als eigener, geprüfter Schritt. Die Abfolge ist Entwicklung → Tests → Prüfbericht → ChatGPT-Prüfung → Noahs Freigabe. Keine Fähigkeit darf die Sicherheitsregeln aus 4.2 aufweichen.
