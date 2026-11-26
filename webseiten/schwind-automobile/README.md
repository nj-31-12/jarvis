# Schwind Automobile – neue Webseite (Entwurf)

Eine Datei: `index.html`. Im Browser öffnen, fertig. Kein Build nötig.

## Neu in Version 2: Originalfotos & Markenauftritt
- **Hintergrund oben:** Fotos der Lamborghinis (Huracán EVO, Revuelto) und des Autohauses wechseln sich mit Überblendung und Zoom ab. Eine Beschriftung zeigt, dass es Originalfotos sind.
- **Galerie „Echte Fahrzeuge. Echtes Autohaus.“** direkt unter dem Hero, mit Vollbild-Ansicht (Pfeiltasten).
- **Team mit Fotos** (Yannick Schwind, Marc Sauer). Für Kathrin Schwind und Marius Buchta fehlen noch Fotos.
- **Markenfarben** Gold/Anthrazit und Logo mit Gold-Schwung wie auf Schild, Theke und Instagram.
- **Echte Fahrzeuge mit Foto:** Audi A3 Cabriolet S line im Bestand, Lamborghinis als Showroom-Highlights. Umschalter Foto / 3D in der Fahrzeugansicht.
- **Reifenwechsel ohne Termin ab 29 € · Einlagerung möglich** oben in der Leiste, bei den Leistungen und in den FAQ.
- **Firmengeschichte:** Aus der BUYA Trading GmbH wird die Schwind Automobile GmbH.
- Bilder liegen in `bilder/`. Sie sind aus Instagram-Screenshots ausgeschnitten und daher nur etwa 900 px breit. **Für den Livegang die Originaldateien in voller Auflösung einsetzen** (gleiche Dateinamen).

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
3. **Impressum:** Laut Instagram heißt die BUYA Trading GmbH jetzt offiziell Schwind Automobile GmbH. Das ist im Entwurf so eingetragen. Bitte prüfen, ob die Anschrift (bisher Kleinostheim) und HRB-Nummer nach der Umfirmierung noch stimmen. Der mailto-Link im alten Impressum zeigt außerdem auf eine fremde Adresse (info@fa-auto.de). Im Entwurf ist § 5 DDG statt TMG angegeben.
4. **Leistungen prüfen:** Werkstattleistungen (Inspektion, Bremsen, HU/AU-Vorbereitung …), Finanzierung und Inzahlungnahme sind übliche Angebote, stehen aber nicht ausdrücklich auf der alten Seite.
5. **Logo:** Das Logo ist nachgebaut (SVG). Am besten die Original-Vektordatei einsetzen.
6. **Datenschutz:** three.js lokal hosten statt über das CDN (cdn.jsdelivr.net). Die Datenschutzerklärung ist ein Entwurf und sollte geprüft werden (z. B. Generator oder Anwalt).
7. **Social Media:** Instagram führt jetzt auf @schwind_automobile_gmbh. LinkedIn zeigt noch auf das Konto der BUYA Trading GmbH.
9. **Daten der echten Fahrzeuge:** Für Audi A3 Cabriolet, Huracán EVO und Revuelto fehlen Preis, Erstzulassung und Kilometer (stehen als „auf Anfrage“). Bitte ergänzen und prüfen, welche Autos noch verfügbar sind.
8. **Formulare** öffnen derzeit das E-Mail-Programm. Für echten Versand ein Formular-Backend anbinden.

## 3D-Modelle
Die Autos werden im Browser aus Karosserie-Profilen berechnet (Limousine, Kombi, Kompakt, SUV, Sportwagen). Es sind also keine lizenzpflichtigen Modelle nötig. Wer fotorealistische Modelle einzelner Fahrzeuge will, kann später GLB-Dateien laden, z. B. aus einem 360°-Fotoshooting.
