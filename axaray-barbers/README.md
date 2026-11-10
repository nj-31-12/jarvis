# Axaray Barbers – Webseite (Entwurf v2)

Barbershop in Hösbach, Hauptstraße 118 – ca. 10 Min. von Aschaffenburg. Statische Seite, läuft ohne Server.

## Dateien
| Datei | Inhalt |
|---|---|
| `index.html`, `styles.css` | Seite und Design |
| `config.js` | **Alles, was der Salon anpasst**: Preise, Barber, Rundgang, Bewertungen, Zahlung |
| `ax3d.js` | 3D-Bausteine (Waben-Lichtdecke, Barber-Pole) + Startszene |
| `tour.js` | Virtueller Rundgang (Scrollen = durch den Salon laufen) |
| `head.js` | 3D Style-Studio mit realistischem Kopf, Haaren und Bart |
| `app.js` | Team, Bewertungen, Buchung, Bezahlung, Kundenkonto, Anfahrt, Sprachassistent |
| `img/`, `model/` | Salon-Fotos und 3D-Kopf |
| `vorschau.html` | Alles in einer Datei – neu bauen mit `python3 build-vorschau.py` |

Lokal ansehen: `python3 -m http.server` im Ordner, dann http://localhost:8000

## Bereiche
1. **Start** – 3D-Waben-Lichtdecke, Barber-Pole, Live-Öffnungsstatus
2. **Rundgang** – beim Scrollen läuft man durch einen 3D-Gang: Schaufenster → Empfang & Lounge → Produkte → Lichtdecke → Stühle → die **3 Plätze**
3. **Barber** – 3 Plätze mit Barber, Spezialgebiet und 3 Signature-Cuts (als 3D-Vorschau; antippen öffnet den Look im Studio)
4. **Style-Studio** – realistischer 3D-Kopf: Gesichtsform, Hautton, 8 Haarschnitte, 6 Fade-Stufen, 6 Bärte, Farben. ★ zeigt, was zur Gesichtsform passt. „Diesen Look buchen“ übernimmt alles in die Buchung
5. **Bewertungen** – Übersichtskarte (5,0 · 34), Laufband in 2 Reihen (antippen = anhalten), Umschalter auf Rasteransicht
6. **Buchung & Bezahlung** – Leistung, Barber, Tag, Uhrzeit, Daten, Zahlung (PayPal, Apple Pay, Google Pay, Karte, Klarna oder vor Ort), Kalender-Export
7. **Kundenkonto** – Daten, bevorzugte Zahlung, gemerkter Look, Terminliste
8. **Anfahrt** – Adler-Ansicht (Luftbild im Hochformat), Navi per Google Maps oder Apple Karten, „~10 Min. von Aschaffenburg“

## Vor dem Livegang (in `config.js`)
- `barbers` – echte Namen, Fotos, Spezialgebiete
- `services` – echte Preise
- `reviews` – echte Google-Rezensionen; `reviewWriteUrl` aus dem Google-Unternehmensprofil
- **Zahlung live schalten:** Stripe-Konto des Salons anlegen (deckt PayPal, Apple Pay, Google Pay, Karte, Klarna ab), pro Leistung einen Payment-Link in `payment.paymentLinks` eintragen, `payment.demo: false`
- **Automatik:** `bookingWebhook` (z. B. n8n/Make) → Google Kalender, SMS-Bestätigung, Bewertungsbitte nach dem Besuch
- Kundenkonto live: Login per E-Mail-Code (z. B. Supabase) – aktuell Demo, Daten bleiben auf dem Gerät
- Impressum, Datenschutz, AGB/Storno verlinken; `draft: false`

## Lizenz 3D-Kopf
„Lee Perry-Smith“ Head Scan von Infinite-Realities, CC BY 3.0 – Namensnennung steht im Footer.
