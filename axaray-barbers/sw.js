/* Offline-Speicher: Seite, Fotos und 3D-Modell bleiben auf dem Handy gespeichert. */
const CACHE = "axaray-v1";
const CORE = ["./", "index.html", "styles.css", "config.js", "ax3d.js", "head.js", "app.js", "tour.js", "manifest.webmanifest",
  "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png", "model/head.glb", "model/skin.jpg",
  "img/aussen.jpg", "img/eingang.jpg", "img/schaufenster.jpg", "img/empfang.jpg", "img/produkte.jpg", "img/decke.jpg",
  "img/stuehle.jpg", "img/goldstuhl.jpg", "img/platz-2.jpg", "img/platz-3.jpg"];
self.addEventListener("install", (e) => { e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting())); });
self.addEventListener("activate", (e) => { e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // Karten und Zahlungsseiten nie zwischenspeichern
  if (/google\.com|maps|stripe|paypal/.test(url.hostname)) return;
  e.respondWith(caches.open(CACHE).then(async (c) => {
    const hit = await c.match(req, { ignoreSearch: req.mode === "navigate" });
    const net = fetch(req).then((res) => { if (res && (res.ok || res.type === "opaque")) c.put(req, res.clone()); return res; }).catch(() => null);
    if (hit) { e.waitUntil(net); return hit; }       // sofort aus dem Speicher, im Hintergrund aktualisieren
    const res = await net;
    return res || (req.mode === "navigate" ? c.match("index.html") : Response.error());
  }));
});
