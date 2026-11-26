# Schwind Automobile – neue Webseite (Entwurf)

Eine Datei: `index.html`. Im Browser öffnen, fertig. Kein Build nötig.

## Was drin ist
- **3D-Showroom** (three.js) auf der Startseite: Fahrzeug drehen und zoomen, Kamera-Ansichten (3/4, Seite, Front, Heck, Oben), Tag/Nacht-Licht mit Scheinwerfern, Farbvorschau. Beim Fahrzeugwechsel fährt das alte Auto raus und das neue rein.
- **3D-Ansicht in jedem Fahrzeug** (Detailfenster) mit Fakten, Ausstattung, Ratenrechner, Probefahrt, WhatsApp, Anrufen, Merken.
- **Fahrzeugbestand** mit Suche, Filtern (Marke, Karosserie, Kraftstoff, Preis), Sortierung, Kachel- und Listenansicht, animierten Übergängen, Favoriten und Vergleich (bis 3 Fahrzeuge).
- **Leistungen** als Tabs mit Wechsel-Animation: Verkauf, Ankauf, Export, Werkstatt & Reifen, Wunschfahrzeug, Finanzierung.
- **Ankauf in 3 Schritten** („Angebot in 48 Stunden“) mit Prüfung der Pflichtfelder.
- **Anfrageformular**, das sich je nach Anliegen umbaut: Probefahrt, Werkstatt, Wunschfahrzeug, Export, Allgemein. Versand per E-Mail-Programm oder WhatsApp.
- Über uns, Team, FAQ, Kontakt, Karte (wird erst nach Klick geladen), Impressum, Datenschutz.
- Hell/Dunkel-Umschalter mit Kreis-Überblendung, Ladeanimation, Scroll-Effekte, Mobilmenü, WhatsApp-Button.
- SEO: Meta-Tags und `AutoDealer`-Daten (schema.org).

## Vor dem Livegang klären (wichtig)
1. **Fahrzeuge sind Beispieldaten.** Der echte Bestand von der alten Seite ließ sich nicht auslesen (er wird dort per Skript nachgeladen). Den echten Bestand am besten per mobile.de- oder AutoScout24-Schnittstelle einbinden. Bis dahin steht ein Hinweis über der Liste. Die Daten stehen in `VEHICLES` im Skript.
2. **Öffnungszeiten** stehen nirgends auf der alten Seite. Eintragen in `CONFIG.hours`. Dann erscheinen auch „Jetzt geöffnet“ und die Zeiten im Kontakt.
3. **Impressum:** Die alte Seite nennt im Impressum die BUYA Trading GmbH in Kleinostheim. Auf der Startseite steht dagegen „Schwind Automobile GmbH“ in Elsenfeld. Bitte klären, welche Firma die Seite betreibt. Der mailto-Link im alten Impressum zeigt außerdem auf eine fremde Adresse (info@fa-auto.de). Im Entwurf ist § 5 DDG statt TMG angegeben.
4. **Leistungen prüfen:** Werkstattleistungen (Inspektion, Bremsen, HU/AU-Vorbereitung …), Finanzierung und Inzahlungnahme sind übliche Angebote, stehen aber nicht ausdrücklich auf der alten Seite.
5. **Logo:** Das Logo ist im Entwurf nur als Schrift gesetzt. Original-Logo (`schwind-logo-neu.png`) einsetzen.
6. **Datenschutz:** three.js lokal hosten statt über das CDN (cdn.jsdelivr.net). Die Datenschutzerklärung ist ein Entwurf und sollte geprüft werden (z. B. Generator oder Anwalt).
7. **Social Media:** Instagram und LinkedIn führen auf die Konten der BUYA Trading GmbH.
8. **Formulare** öffnen derzeit das E-Mail-Programm. Für echten Versand ein Formular-Backend anbinden.

## 3D-Modelle
Die Autos werden im Browser aus Karosserie-Profilen berechnet (Limousine, Kombi, Kompakt, SUV, Sportwagen). Es sind also keine lizenzpflichtigen Modelle nötig. Wer fotorealistische Modelle einzelner Fahrzeuge will, kann später GLB-Dateien laden, z. B. aus einem 360°-Fotoshooting.
