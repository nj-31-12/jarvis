# Axaray Barbers – Webseite (Entwurf v1)

Barbershop in Hösbach, Hauptstraße 118. Statische Seite, läuft ohne Server.

## Dateien
- `index.html`, `styles.css`, `app.js`, `img/` – die Webseite
- `vorschau.html` – alles in einer Datei (zum schnellen Ansehen/Teilen)

Lokal ansehen: `python3 -m http.server` im Ordner, dann http://localhost:8000

## Was drin ist
- **3D-Hero** (Three.js): Waben-Lichtdecke wie im Salon, drehende Barber-Pole, Goldstaub, reagiert auf Maus und Handy-Neigung
- **Google-Bewertungen als Laufband** – Antippen hält an, nochmal antippen läuft weiter (Desktop: Hover hält an)
- **Live-Status** „Jetzt geöffnet / schließt bald / öffnet morgen um …“
- **Terminanfrage** in 4 Schritten (Leistung → Tag → Uhrzeit → Daten), mit Kalender-Download (.ics)
- **Sprachassistent** (Mikrofon-Button): versteht z. B. „Skin Fade morgen um 15 Uhr“ und füllt das Formular aus; beantwortet Preise, Öffnungszeiten, Parken, Adresse
- Mobile Leiste „Anrufen / Termin“, Google-Maps erst nach Klick (DSGVO), SEO-Daten (schema.org HairSalon)

## Vor dem Livegang ausfüllen (oben in `app.js` → `CONFIG`)
| Feld | Wofür |
|---|---|
| `services` | Echte Preise und Dauer (aktuell Platzhalter) |
| `reviews` | Echte Google-Rezensionen (aktuell Platzhalter) |
| `whatsapp` / `email` | Wohin Terminanfragen gehen |
| `bookingWebhook` | Automatik: z. B. n8n/Make → Google Kalender + SMS-Bestätigung |
| `reviewUrl` | Direkter Google-Bewertungslink (aus dem Google-Unternehmensprofil) |
| `draft: false` | Entwurf-Hinweis ausblenden |

Außerdem: Impressum und Datenschutz verlinken (Pflicht in Deutschland).

## Nächste Schritte (Stufe 2)
- Echter Telefon-Voice-Agent (z. B. Vapi oder Retell), der Anrufe annimmt und Termine einträgt – der Web-Assistent ist die Vorstufe
- Buchungen in einen Kalender mit echten Verfügbarkeiten (Cal.com oder eigener Webhook)
- Nach dem Besuch automatische SMS/WhatsApp mit Bitte um Google-Bewertung – an **alle** Kunden, nicht nur zufriedene (Google verbietet das Filtern)
