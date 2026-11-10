/* Axaray Barbers – alles, was der Salon selbst anpassen kann. */
window.CONFIG = {
  draft: true, // Hinweis "Entwurf" oben anzeigen

  phone: "+4960216246351",
  phoneDisplay: "06021 6246351",
  address: "Hauptstraße 118, 63768 Hösbach",
  mapsQuery: "Axaray Barbers, Hauptstraße 118, 63768 Hösbach",
  reviewUrl: "https://www.google.com/maps/search/?api=1&query=Axaray+Barbers+Hauptstra%C3%9Fe+118+H%C3%B6sbach",
  reviewWriteUrl: "", // direkter Link "Rezension schreiben" aus dem Google-Unternehmensprofil (g.page/r/…/review)

  whatsapp: "",       // z. B. "4917612345678"
  email: "",          // z. B. "termin@axaray-barbers.de"
  bookingWebhook: "", // n8n/Make/Zapier-URL: Buchung → Google Kalender, SMS-Bestätigung, Bewertungs-Erinnerung

  // Online-Zahlung. Live z. B. mit Stripe (PayPal, Apple Pay, Google Pay, Karte, Klarna in einem Konto).
  // Pro Leistung einen Stripe-Payment-Link eintragen – oder checkoutEndpoint für ein eigenes Backend.
  payment: {
    demo: true,
    checkoutEndpoint: "",   // POST {booking} → {url} (Stripe Checkout Session)
    paymentLinks: {},       // z. B. { fade: "https://buy.stripe.com/…" }
    methods: [
      { id: "paypal",  name: "PayPal" },
      { id: "applepay", name: "Apple Pay" },
      { id: "googlepay", name: "Google Pay" },
      { id: "card",    name: "Kredit-/Debitkarte" },
      { id: "klarna",  name: "Klarna" },
    ],
  },

  // 0 = Sonntag … 6 = Samstag; [öffnet, schließt] in Minuten ab Mitternacht
  hours: { 0: null, 1: [540, 1110], 2: [540, 1110], 3: [540, 1110], 4: [540, 1110], 5: [540, 1110], 6: [540, 990] },
  slotMinutes: 30,

  // PLATZHALTER-PREISE – bitte ersetzen
  services: [
    { id: "cut",   name: "Haarschnitt",            price: 20, dur: 30, desc: "Waschen, Schneiden, Styling" },
    { id: "fade",  name: "Fade-Haarschnitt",       price: 25, dur: 40, desc: "Low, Mid, High oder Skin Fade" },
    { id: "beard", name: "Bart trimmen & Konturen", price: 15, dur: 20, desc: "Konturen mit der Klinge, Hot Towel" },
    { id: "combo", name: "Haarschnitt + Bart",     price: 32, dur: 50, desc: "Das Komplettpaket" },
    { id: "kids",  name: "Kinderhaarschnitt",      price: 15, dur: 25, desc: "Bis 12 Jahre" },
    { id: "wax",   name: "Gesichtspflege & Wachs", price: 10, dur: 15, desc: "Nase, Ohren, Hot Towel" },
  ],

  // PLATZHALTER-NAMEN – bitte echte Namen und Fotos eintragen.
  // cuts = Beispiel-Looks, die als 3D-Vorschau gezeigt werden (Stile siehe head.js).
  barbers: [
    { id: "b1", name: "Barber Platz 1", tag: "Name folgt", img: "img/goldstuhl.jpg",
      specialty: "Skin Fades & Crops", text: "Saubere Übergänge bis auf die Haut, kantige Konturen.",
      cuts: [ { style: "crop", fade: "skin", beard: "none", label: "French Crop + Skin Fade" },
              { style: "buzz", fade: "high", beard: "stubble", label: "Buzz Cut + High Fade" },
              { style: "curly", fade: "mid", beard: "none", label: "Curly Top + Mid Fade" } ] },
    { id: "b2", name: "Barber Platz 2", tag: "Name folgt", img: "img/platz-2.jpg",
      specialty: "Bart & Klassiker", text: "Bartformung mit Hot Towel und Klinge, klassische Schnitte.",
      cuts: [ { style: "sidepart", fade: "taper", beard: "full", label: "Side Part + Vollbart" },
              { style: "slick", fade: "low", beard: "short", label: "Slick Back + Kurzbart" },
              { style: "quiff", fade: "low", beard: "goatee", label: "Quiff + Goatee" } ] },
    { id: "b3", name: "Barber Platz 3", tag: "Name folgt", img: "img/platz-3.jpg",
      specialty: "Volumen & Styling", text: "Pompadour, Quiff und lange Styles – mit Styling-Tipps.",
      cuts: [ { style: "pompadour", fade: "mid", beard: "short", label: "Pompadour + Mid Fade" },
              { style: "flow", fade: "none", beard: "full", label: "Mittellang + Vollbart" },
              { style: "quiff", fade: "high", beard: "none", label: "Quiff + High Fade" } ] },
  ],

  // Stationen des Rundgangs (Reihenfolge = Laufweg). Die letzten 3 = die Plätze der Barber.
  tour: [
    { img: "img/schaufenster.jpg", title: "Hauptstraße 118", text: "Das Schaufenster mit der Waben-Lichtdecke – schon von der Straße zu sehen. Parkplätze direkt gegenüber." },
    { img: "img/empfang.jpg",      title: "Empfang & Lounge", text: "Kurz Platz nehmen auf dem Chesterfield, Kaffee aus der Maschine. Ohne Termin? Hier wartest du gemütlich." },
    { img: "img/produkte.jpg",     title: "Profi-Produkte",   text: "Wachs, Powder, Barber-Cologne – alles, was wir benutzen, kannst du auch für zu Hause mitnehmen." },
    { img: "img/decke.jpg",        title: "Unter dem Licht",  text: "Die Waben-Decke sorgt für schattenfreies Licht – perfekt für präzise Fades." },
    { img: "img/stuehle.jpg",      title: "Die Plätze",       text: "Goldene Barber-Stühle, ovale Spiegel, schwarzer Marmor. Gleich lernst du die Barber kennen." },
  ],

  // PLATZHALTER-BEWERTUNGEN – bitte echte Google-Rezensionen eintragen (Vorname + Initial, mit Erlaubnis)
  reviews: [
    { name: "Platzhalter A", when: "Beispieltext", stars: 5, text: "Hier kommt eine echte Google-Rezension hin – z. B. über den Fade und die Atmosphäre im Laden." },
    { name: "Platzhalter B", when: "Beispieltext", stars: 5, text: "Zweite echte Rezension: Freundlichkeit, kurze Wartezeit ohne Termin, Sauberkeit." },
    { name: "Platzhalter C", when: "Beispieltext", stars: 5, text: "Dritte echte Rezension: Bartpflege, Hot Towel, Preis-Leistung." },
    { name: "Platzhalter D", when: "Beispieltext", stars: 5, text: "Vierte echte Rezension: Einrichtung, Licht, Lounge." },
    { name: "Platzhalter E", when: "Beispieltext", stars: 5, text: "Fünfte echte Rezension: Parken gegenüber, schnell drangekommen." },
    { name: "Platzhalter F", when: "Beispieltext", stars: 5, text: "Sechste echte Rezension: Styling-Tipps und Produkte." },
    { name: "Platzhalter G", when: "Beispieltext", stars: 5, text: "Siebte echte Rezension: Online gebucht und pünktlich drangekommen." },
    { name: "Platzhalter H", when: "Beispieltext", stars: 5, text: "Achte echte Rezension: Kinderhaarschnitt, geduldig und schnell." },
  ],
};
