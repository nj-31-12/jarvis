# Axaray Barbers – Webseite (Entwurf v3)

Barbershop in Hösbach, Hauptstraße 118 – ca. 10 Min. von Aschaffenburg. Statische Seite, läuft ohne Server.

## Dateien
| Datei | Inhalt |
|---|---|
| `index.html`, `styles.css` | Seite und Design |
| `config.js` | **Alles, was der Salon anpasst**: Preise, Barber, Rundgang, Bewertungen, Zahlung |
| `ax3d.js` | 3D-Bausteine (Waben-Lichtdecke, Barber-Pole) + Startszene |
| `tour.js` | Film-Rundgang: der Salon als 3D-Raum mit echtem Grundriss, Kameraflug + echte Fotos |
| `film/` | Der Rundgang als MP4 (16:9 und 9:16 fürs Handy/Instagram) |
| `head.js` | 3D Style-Studio mit realistischem Kopf, Haaren und Bart |
| `app.js` | Team, Bewertungen, Buchung, Bezahlung, Kundenkonto, Anfahrt, Sprachassistent |
| `img/`, `model/` | Salon-Fotos und 3D-Kopf |
| `vorschau.html` | Alles in einer Datei – neu bauen mit `python3 build-vorschau.py` |

Lokal ansehen: `python3 -m http.server` im Ordner, dann http://localhost:8000

## Bereiche
1. **Start** – 3D-Waben-Lichtdecke, Barber-Pole, Live-Öffnungsstatus
2. **Begehbarer Laden** (Ego-Perspektive) – der Laden als 3D-Raum (5 × 7,5 m) mit dem echten Grundriss:
   vorne links Eingang, links die 3 Plätze mit Spiegeln, hinten links Waschplatz, hinten rechts Kasse,
   rechts am Fenster die Lounge, Waben-Lichtdecke über allem. „Laden betreten“ fliegt von der Straße durch die Tür;
   danach: ziehen = umsehen, Boden antippen = hinlaufen, goldene Punkte = Infos (Kasse: Termin & Zahlung, Plätze: Barber & Haarschnitte, Fragen, Lounge, Waschplatz, Produkte, Eingang).
   Grundriss-Karte oben links zeigt, wo man gerade steht.
3. **Barber** – 3 Plätze mit Barber, Spezialgebiet und 3 Signature-Cuts (als 3D-Vorschau; antippen öffnet den Look im Studio)
4. **Style-Studio** – realistischer 3D-Kopf: Gesichtsform, Hautton, 8 Haarschnitte, 6 Fade-Stufen, 6 Bärte, Farben. ★ zeigt, was zur Gesichtsform passt. „Diesen Look buchen“ übernimmt alles in die Buchung
5. **Bewertungen** – Übersichtskarte (5,0 · 34), Laufband in 2 Reihen (antippen = anhalten), Umschalter auf Rasteransicht
6. **Buchung & Bezahlung** – Leistung, Barber, Tag, Uhrzeit, Daten, Zahlung (PayPal, Apple Pay, Google Pay, Karte, Klarna oder vor Ort), Kalender-Export
7. **Kundenkonto** – Swipe-Ansicht mit allen Vorteilen, digitale Stempelkarte (10 Stempel = Haarschnitt gratis + Getränk, 1. Stempel geschenkt), Gutscheine, Zahlungsart, gemerkter Look, Termine
9. **Standort-Concierge** – mit Erlaubnis des Kunden: in der Nähe des Ladens (250 m) meldet sich der Assistent (freier Stuhl, Nachschnitt fällig, Stempelstand, spontan vorbeikommen), im Laden (30 m) fragt er nach dem Aufenthalt und bietet Getränk, Stempel, Wunsch-Look, nächsten Termin, Google-Bewertung und Feedback an. Einstellungen: `geo` und `loyalty` in `config.js`. Ereignisse (Kunde in der Nähe, Getränk, Bewertung) gehen an `bookingWebhook`
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

## Film neu rendern
Server starten (`python3 -m http.server 8080`), dann im Browser `ROOM.renderAt(p, breite, höhe)` für p = 0…1
aufrufen und die Bilder mit ffmpeg zu einem MP4 zusammensetzen (so wurden die Dateien in `film/` erzeugt).
