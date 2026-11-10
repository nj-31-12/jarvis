/* Film-Rundgang: der Salon als begehbarer 3D-Raum (Grundriss wie im Laden).
 * Grundriss (Blick von oben, vorne = Schaufenster/Straße):
 *   hinten:  [Waschplatz]  ……  [TV]  ……  [Kasse]
 *   links:   Platz 3 · Platz 2 · Platz 1 · Produktregal     rechts: Fenster + Lounge
 *   vorne:   [Eingang links]  ……  Schaufenster
 * Scrollen (oder „Film abspielen“) fliegt die Kamera durch den Raum. An den Stationen blendet
 * das echte Foto bildfüllend ein. window.ROOM.renderAt() wird für den Video-Export genutzt.
 */
(function room() {
  const C = window.CONFIG, sec = document.getElementById("rundgang"), canvas = document.getElementById("tourCanvas");
  const names = C.barbers.map((b) => b.name);
  // Kamera-Stationen: Position, Blickziel, optionales Foto
  const KEYS = [
    { pos: [0.9, 1.65, 6.2],  look: [-0.2, 1.4, -3],   img: "img/schaufenster.jpg", title: "Hauptstraße 118, Hösbach", text: "Nur ca. 10 Minuten von Aschaffenburg. Parkplätze direkt gegenüber – 2 Stunden für 1,50 €." },
    { pos: [-1.75, 1.6, 1.1], look: [-1.2, 1.45, -4],  title: "Eingang vorne links", text: "Komm rein – ohne Termin oder mit Online-Buchung." },
    { pos: [-0.9, 1.5, -0.9], look: [-2.6, 1.25, -0.9], img: "img/produkte.jpg", title: "Profi-Produkte", text: "Wachs, Powder, Barber-Cologne – alles, was wir benutzen, gibt’s auch für zu Hause." },
    { pos: [-0.3, 1.62, -0.7], look: [0.2, 1.3, -7.5], img: "img/empfang.jpg", title: "Der Raum", text: "Hinten links der Waschplatz, hinten rechts die Kasse, rechts am Fenster die Lounge." },
    { pos: [0.6, 1.45, -1.5], look: [2.6, 0.65, -3.1], title: "Lounge am Fenster", text: "Auf dem Chesterfield wartest du entspannt – Kaffee geht aufs Haus." },
    { pos: [0.9, 1.7, -0.9],  look: [-2.4, 1.15, -4.6], img: "img/stuehle.jpg", title: "Die drei Plätze", text: "Drei goldene Barber-Stühle, drei Spiegel, ein Anspruch: präzise." },
    { pos: [0.15, 1.6, -2.2], look: [-2.6, 1.3, -2.2], img: C.barbers[0].img, title: `Platz 1 · ${names[0]}`, text: C.barbers[0].specialty },
    { pos: [0.15, 1.6, -3.8], look: [-2.6, 1.3, -3.8], img: C.barbers[1].img, title: `Platz 2 · ${names[1]}`, text: C.barbers[1].specialty },
    { pos: [0.15, 1.6, -5.4], look: [-2.6, 1.3, -5.4], img: C.barbers[2].img, title: `Platz 3 · ${names[2]}`, text: C.barbers[2].specialty },
    { pos: [0.1, 2.25, -3.2], look: [0.1, 2.95, -5.6], img: "img/decke.jpg", title: "Die Waben-Lichtdecke", text: "Schattenfreies Licht von oben – perfekt für saubere Übergänge." },
    { pos: [-0.3, 1.5, -4.8], look: [-1.9, 0.8, -7.4], title: "Hinten links: Waschplatz", text: "Haare waschen, Hot Towel, Kopfmassage." },
    { pos: [0.2, 1.55, -4.4],  look: [1.5, 0.95, -7.0],  title: "Hinten rechts: Kasse", text: "Bar oder Karte – oder schon online bezahlt mit PayPal, Apple Pay & Co." },
    { pos: [2.1, 2.55, -0.5], look: [-1.1, 0.6, -4.6], title: "Willkommen bei Axaray", text: "Jetzt Barber wählen und Termin sichern ↓", final: true },
  ];
  const K = KEYS.length;
  let exporting = false, showPhoto = true;

  const fallback = () => {
    sec.classList.add("no-3d");
    const fb = document.getElementById("tourFallback"); fb.hidden = false;
    fb.innerHTML = KEYS.filter((k) => k.img).map((k) => `<figure><img src="${k.img}" alt="${k.title}" loading="lazy"><figcaption><b>${k.title}</b>${k.text}</figcaption></figure>`).join("");
  };
  if (!window.AX3D || !canvas) return fallback();
  const renderer = AX3D.makeRenderer(canvas, { preserveDrawingBuffer: false });
  if (!renderer) return fallback();
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = .95;

  sec.style.height = `${K * 75 + 40}vh`;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x07070a);
  scene.fog = new THREE.Fog(0x07070a, 9, 30);
  const camera = new THREE.PerspectiveCamera(60, 1, .05, 80);
  scene.add(camera);
  const tl = new THREE.TextureLoader();
  let pending = 0, resolveReady; const ready = new Promise((r) => (resolveReady = r));
  const load = (src, cb) => { pending++; return tl.load(src, (t) => { cb && cb(t); if (--pending === 0) setTimeout(resolveReady, 50); }, undefined, () => { if (--pending === 0) resolveReady(); }); };

  /* ---------- Texturen aus Canvas ---------- */
  const canvasTex = (w, h, draw, rep) => { const c = document.createElement("canvas"); c.width = w; c.height = h; draw(c.getContext("2d"), w, h); const t = new THREE.CanvasTexture(c); if (rep) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(...rep); } return t; };
  const hexPath = (g, x, y, r) => { g.beginPath(); for (let i = 0; i < 6; i++) { const a = Math.PI / 3 * i + Math.PI / 6; g.lineTo(x + r * Math.cos(a), y + r * Math.sin(a)); } g.closePath(); };
  const tiles = canvasTex(512, 256, (g, w, h) => {
    g.fillStyle = "#2a2b30"; g.fillRect(0, 0, w, h);
    for (let i = 0; i < 2500; i++) { g.fillStyle = `rgba(${Math.random() > .5 ? 255 : 0},${Math.random() > .5 ? 255 : 0},255,${Math.random() * .035})`; g.fillRect(Math.random() * w, Math.random() * h, 3, 3); }
    g.strokeStyle = "#1c1c1f"; g.lineWidth = 5; g.strokeRect(0, 0, w, h);
  }, [8, 25]);
  const marble = canvasTex(256, 256, (g, w, h) => {
    g.fillStyle = "#0c0c0e"; g.fillRect(0, 0, w, h); g.strokeStyle = "rgba(220,220,230,.35)"; g.lineWidth = 1.2;
    for (let i = 0; i < 7; i++) { g.beginPath(); let x = Math.random() * w, y = 0; g.moveTo(x, y); while (y < h) { x += (Math.random() - .5) * 40; y += 20; g.lineTo(x, y); } g.stroke(); }
  });
  const hexDoor = canvasTex(256, 512, (g, w, h) => {
    g.fillStyle = "#0b0b0d"; g.fillRect(0, 0, w, h); g.strokeStyle = "#c9a43a"; g.lineWidth = 3;
    for (let y = 20; y < h; y += 26) for (let x = (y / 26) % 2 ? 14 : 0; x < w; x += 30) { hexPath(g, x, y, 12); g.stroke(); }
    g.lineWidth = 10; g.strokeRect(5, 5, w - 10, h - 10);
  });
  const leather = canvasTex(256, 256, (g, w, h) => {
    g.fillStyle = "#161618"; g.fillRect(0, 0, w, h);
    for (let y = 16; y < h; y += 32) for (let x = (y / 32) % 2 ? 32 : 0; x <= w; x += 64) {
      const grd = g.createRadialGradient(x, y, 1, x, y, 26); grd.addColorStop(0, "rgba(0,0,0,.9)"); grd.addColorStop(.25, "rgba(60,60,66,.5)"); grd.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = grd; g.fillRect(x - 32, y - 32, 64, 64);
    }
  }, [3, 1]);
  const blinds = canvasTex(64, 256, (g, w, h) => { for (let y = 0; y < h; y += 8) { g.fillStyle = "#cfcfd2"; g.fillRect(0, y, w, 6); g.fillStyle = "#77777b"; g.fillRect(0, y + 6, w, 2); } }, [6, 4]);
  const brick = canvasTex(256, 128, (g, w, h) => {
    g.fillStyle = "#2a1712"; g.fillRect(0, 0, w, h);
    for (let y = 0; y < h; y += 32) for (let x = (y / 32) % 2 ? -32 : 0; x < w; x += 64) { g.fillStyle = `hsl(12,${35 + Math.random() * 15}%,${22 + Math.random() * 8}%)`; g.fillRect(x + 2, y + 2, 60, 28); }
  }, [10, 6]);
  const goldText = (lines, w = 1024, h = 512, opts = {}) => canvasTex(w, h, (g) => {
    g.textAlign = "center"; g.fillStyle = opts.color || "#d4af37";
    lines.forEach(([txt, size, y, font]) => { g.font = `${font || 700} ${size}px Cinzel, Georgia, serif`; g.fillText(txt, w / 2, y); });
  });
  const tvTex = canvasTex(512, 288, (g, w, h) => {
    const grd = g.createLinearGradient(0, 0, w, h); grd.addColorStop(0, "#14110a"); grd.addColorStop(1, "#2a2110"); g.fillStyle = grd; g.fillRect(0, 0, w, h);
    g.strokeStyle = "rgba(212,175,55,.25)"; g.lineWidth = 2; for (let y = 0; y < h + 40; y += 46) for (let x = (y / 46) % 2 ? 26 : 0; x < w + 40; x += 52) { hexPath(g, x, y, 24); g.stroke(); }
    g.textAlign = "center"; g.fillStyle = "#e8c65a"; g.font = "700 64px Cinzel, Georgia, serif"; g.fillText("AXARAY", w / 2, 150); g.font = "600 24px Cinzel, Georgia, serif"; g.fillText("B A R B E R S", w / 2, 192);
  });

  /* ---------- Materialien ---------- */
  const M = {
    wall: new THREE.MeshStandardMaterial({ color: 0x1e1f24, roughness: .95 }),
    ceil: new THREE.MeshStandardMaterial({ color: 0x1c1c21, roughness: 1 }),
    floor: new THREE.MeshStandardMaterial({ map: tiles, roughness: .32, metalness: .15 }),
    black: new THREE.MeshStandardMaterial({ color: 0x111114, roughness: .45, metalness: .1 }),
    gloss: new THREE.MeshStandardMaterial({ color: 0x08080a, roughness: .12, metalness: .3 }),
    gold: new THREE.MeshStandardMaterial({ color: 0xd8b13c, roughness: .22, metalness: 1 }),
    marble: new THREE.MeshStandardMaterial({ map: marble, roughness: .1, metalness: .1 }),
    mirror: new THREE.MeshStandardMaterial({ color: 0xe8e8ee, roughness: .02, metalness: 1 }),
    leather: new THREE.MeshStandardMaterial({ color: 0x18181b, roughness: .38, metalness: .05 }),
    tufted: new THREE.MeshStandardMaterial({ map: leather, roughness: .35, metalness: .05 }),
    hexDoor: new THREE.MeshStandardMaterial({ map: hexDoor, roughness: .3, metalness: .4 }),
    glass: new THREE.MeshPhysicalMaterial({ color: 0xaab4c0, transparent: true, opacity: .1, roughness: .02, metalness: 0, depthWrite: false }),
    blinds: new THREE.MeshStandardMaterial({ map: blinds, color: 0x6c6c72, roughness: .8, emissive: 0x0c0c0e }),
    white: new THREE.MeshStandardMaterial({ color: 0xeeeeee, roughness: .4 }),
    towel: new THREE.MeshStandardMaterial({ color: 0x55565c, roughness: 1 }),
  };

  const world = new THREE.Group(); scene.add(world);
  const add = (geo, mat, x, y, z, parent = world) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); parent.add(m); return m; };
  const box = (w, h, d, mat, x, y, z, parent) => add(new THREE.BoxGeometry(w, h, d), mat, x, y + h / 2, z, parent); // y = Unterkante
  const cyl = (r, h, mat, x, y, z, parent, seg = 32) => add(new THREE.CylinderGeometry(r, r, h, seg), mat, x, y + h / 2, z, parent);

  /* ---------- Raum: 5 m breit, 7,5 m tief, 2,8 m hoch ---------- */
  const X0 = -2.5, X1 = 2.5, Z0 = 0, Z1 = -7.5, H = 2.8;
  const floor = add(new THREE.PlaneGeometry(5, 7.5), M.floor, 0, 0, -3.75); floor.rotation.x = -Math.PI / 2;
  const ceil = add(new THREE.PlaneGeometry(5, 7.5), M.ceil, 0, H, -3.75); ceil.rotation.x = Math.PI / 2;
  const lw = add(new THREE.PlaneGeometry(7.5, H), M.wall, X0, H / 2, -3.75); lw.rotation.y = Math.PI / 2;
  const rw = add(new THREE.PlaneGeometry(7.5, H), M.wall, X1, H / 2, -3.75); rw.rotation.y = -Math.PI / 2;
  add(new THREE.PlaneGeometry(5, H), M.wall, 0, H / 2, Z1);
  const hex = AX3D.hexCeiling({ w: 4.7, z0: -7.25, z1: -.25, R: .62, round: false }); hex.position.y = H - .03; world.add(hex);
  // Sockelleisten
  box(.02, .08, 7.5, M.black, X0 + .01, 0, -3.75); box(.02, .08, 7.5, M.black, X1 - .01, 0, -3.75); box(5, .08, .02, M.black, 0, 0, Z1 + .01);

  /* ---------- Barber-Stuhl (Blickrichtung +z) ---------- */
  function chair() {
    const g = new THREE.Group();
    cyl(.3, .04, M.gold, 0, 0, 0, g, 40);
    cyl(.07, .34, M.gloss, 0, .04, 0, g);
    cyl(.12, .06, M.gold, 0, .34, 0, g);
    box(.62, .1, .58, M.gold, 0, .38, 0, g);
    box(.56, .14, .52, M.leather, 0, .48, .02, g);
    const back = box(.54, .72, .1, M.tufted, 0, .6, -.27, g); back.rotation.x = -.12;
    const ring = add(new THREE.TorusGeometry(.33, .022, 10, 40), M.gold, 0, .98, -.31, g); ring.scale.set(1, 1.22, 1); ring.rotation.x = -.12;
    box(.3, .12, .09, M.leather, 0, 1.36, -.34, g);
    [-1, 1].forEach((s) => { box(.07, .06, .46, M.leather, s * .32, .72, .02, g); box(.05, .22, .05, M.gold, s * .32, .5, .16, g); });
    const foot = box(.42, .03, .2, M.gold, 0, .16, .44, g); foot.rotation.x = -.35;
    box(.04, .2, .04, M.gold, 0, .22, .3, g);
    return g;
  }
  /* ---------- Spiegel in Kapselform ---------- */
  function capsule(w, h) {
    const r = w / 2, s = new THREE.Shape();
    s.moveTo(-r, -h / 2 + r); s.lineTo(-r, h / 2 - r); s.absarc(0, h / 2 - r, r, Math.PI, 0, true); s.lineTo(r, -h / 2 + r); s.absarc(0, -h / 2 + r, r, 0, Math.PI, true);
    return s;
  }
  const productColors = [0x3ddc84, 0xe23b3b, 0xf28c28, 0x2f62d8, 0xf2f2f2, 0x7a3cc8, 0xf3d24a];
  /* ---------- Platz an der linken Wand ---------- */
  function station(z) {
    const g = new THREE.Group(); world.add(g);
    box(.04, 1.6, 1.5, M.gloss, X0 + .03, .86, z, g); // Rückwand
    // Spiegel + Goldrahmen
    const shape = capsule(.56, 1.0);
    const mirror = add(new THREE.ShapeGeometry(shape, 24), M.mirror, X0 + .07, 1.62, z, g); mirror.rotation.y = Math.PI / 2;
    const outer = capsule(.64, 1.08); outer.holes.push(capsule(.56, 1.0));
    const rim = add(new THREE.ExtrudeGeometry(outer, { depth: .03, bevelEnabled: false, curveSegments: 24 }), M.gold, X0 + .06, 1.62, z, g); rim.rotation.y = Math.PI / 2;
    // Regale links und rechts vom Spiegel
    [-1, 1].forEach((s) => {
      const zz = z + s * .53;
      [1.22, 1.62, 2.02].forEach((y, k) => {
        box(.2, .025, .34, M.gloss, X0 + .14, y, zz, g);
        for (let i = 0; i < 3; i++) cyl(.045, .05 + (k === 2 ? .06 : 0), new THREE.MeshStandardMaterial({ color: productColors[(i + k * 2 + (z * 10 | 0)) % productColors.length], roughness: .4 }), X0 + .14, y + .025, zz - .1 + i * .1, g, 16);
      });
      box(.015, 1.5, .015, M.gold, X0 + .07, .9, z + s * .72, g);
      box(.015, 1.5, .015, M.gold, X0 + .07, .9, z + s * .34, g);
    });
    box(.05, .03, 1.5, M.gold, X0 + .06, 2.42, z, g);
    // Unterschrank mit Marmorplatte und Waben-Türen
    box(.5, .8, 1.46, M.black, X0 + .27, 0, z, g);
    box(.56, .04, 1.52, M.marble, X0 + .29, .8, z, g);
    [-1, 1].forEach((s) => { const d = add(new THREE.PlaneGeometry(.34, .66), M.hexDoor, X0 + .525, .4, z + s * .5, g); d.rotation.y = Math.PI / 2; });
    box(.01, .66, .02, M.gold, X0 + .525, .07, z, g);
    // Kleinkram auf der Platte
    cyl(.035, .2, M.gold, X0 + .32, .84, z - .25, g, 12);
    cyl(.05, .14, new THREE.MeshStandardMaterial({ color: 0x1f5ad8, roughness: .2 }), X0 + .3, .84, z + .2, g, 16);
    // Stuhl mit Blick zum Spiegel
    const c = chair(); c.position.set(X0 + 1.05, 0, z); c.rotation.y = -Math.PI / 2; g.add(c);
  }
  [-2.2, -3.8, -5.4].forEach(station);

  /* ---------- Produktregal vorne links (Foto als Front) ---------- */
  (function shelf() {
    const z = -.95, w = .78, h = 1.38;
    box(.45, .5, w, M.black, X0 + .23, 0, z);
    box(.45, h, w, M.black, X0 + .23, .5, z);
    const front = add(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: 0x222222 }), X0 + .455, .5 + h / 2, z); front.rotation.y = Math.PI / 2;
    load("img/produkte.jpg", (t) => { front.material = new THREE.MeshBasicMaterial({ map: t, color: 0xbbbbbb }); });
    // Uhr darüber
    const clock = add(new THREE.CylinderGeometry(.2, .2, .03, 40), M.gloss, X0 + .03, 2.25, z); clock.rotation.z = Math.PI / 2;
    const face = add(new THREE.TorusGeometry(.17, .012, 8, 40), M.gold, X0 + .05, 2.25, z); face.rotation.y = Math.PI / 2;
    const gear = add(new THREE.TorusGeometry(.06, .02, 6, 10), M.gold, X0 + .05, 2.25, z); gear.rotation.y = Math.PI / 2;
  })();

  /* ---------- Hinten links: Waschplatz ---------- */
  (function wash() {
    const x = -1.65, z = -6.85;
    box(.9, .78, .55, M.black, x, 0, Z1 + .3);
    const basin = add(new THREE.SphereGeometry(.3, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), M.gloss, x, 1.02, Z1 + .32); basin.rotation.x = Math.PI;
    box(.62, .03, .45, M.gloss, x, .98, Z1 + .32);
    // Liegestuhl
    box(.7, .42, 1.2, M.leather, x, 0, z + .45);
    const back = box(.62, .1, .7, M.tufted, x, .5, z - .12); back.rotation.x = .5;
    [-1, 1].forEach((s) => box(.06, .08, 1.0, M.gold, x + s * .37, .42, z + .45));
    // Handtuchschrank + Kaffeemaschine
    box(.5, 2.0, .5, M.black, -2.2, 0, Z1 + .3 + 1.0 - 1.0);
    for (let i = 0; i < 6; i++) { const t = add(new THREE.CylinderGeometry(.06, .06, .38, 12), M.towel, -2.2 + (i % 3 - 1) * .13, 1.35 + (i / 3 | 0) * .16, Z1 + .3); t.rotation.z = Math.PI / 2; }
    box(1.0, .9, .5, M.black, -.55, 0, Z1 + .28);
    box(1.04, .04, .54, M.marble, -.55, .9, Z1 + .28);
    box(.25, .32, .3, M.white, -.3, .94, Z1 + .3);
  })();

  /* ---------- Rückwand: TV ---------- */
  box(1.3, .76, .05, M.gloss, .45, 1.5, Z1 + .03);
  add(new THREE.PlaneGeometry(1.24, .7), new THREE.MeshBasicMaterial({ map: tvTex }), .45, 1.88, Z1 + .06);

  /* ---------- Hinten rechts: Kasse ---------- */
  (function counter() {
    const x = 1.45, z = -6.6;
    box(1.5, 1.08, .62, M.black, x, 0, z);
    const front = add(new THREE.PlaneGeometry(1.4, .98), new THREE.MeshStandardMaterial({ map: canvasTex(512, 360, (g, w, h) => {
      g.fillStyle = "#0b0b0d"; g.fillRect(0, 0, w, h); g.strokeStyle = "#c9a43a"; g.lineWidth = 6;
      hexPath(g, w / 2, h / 2, 140); g.stroke(); hexPath(g, w / 2, h / 2, 100); g.stroke();
      g.beginPath(); g.moveTo(0, h / 2); g.lineTo(w / 2 - 121, h / 2); g.moveTo(w / 2 + 121, h / 2); g.lineTo(w, h / 2); g.stroke();
    }), roughness: .3, metalness: .4 }), x, .54, z + .315);
    box(1.6, .04, .7, M.gloss, x, 1.08, z);
    const basket = add(new THREE.TorusGeometry(.13, .02, 8, 24), M.gold, x + .4, 1.22, z); basket.rotation.x = Math.PI / 2;
    cyl(.02, .1, M.gold, x + .4, 1.12, z);
    box(.12, .18, .02, M.white, x - .1, 1.12, z + .1);
    [-.45, -.3].forEach((dx) => { add(new THREE.SphereGeometry(.05, 16, 12), M.white, x + dx, 1.17, z + .1); });
    // Kassen-Terminal
    box(.18, .04, .25, M.gloss, x - .55, 1.12, z);
  })();

  /* ---------- Rechts: Fenster mit Jalousie + Chesterfield-Lounge ---------- */
  (function lounge() {
    const win = add(new THREE.PlaneGeometry(4.4, 1.7), M.blinds, X1 - .02, 1.65, -2.9); win.rotation.y = -Math.PI / 2;
    [-.7, -2.9, -5.1].forEach((z) => box(.04, 1.8, .05, M.black, X1 - .03, .8, z));
    box(.04, .05, 4.4, M.black, X1 - .03, .8, -2.9); box(.04, .05, 4.4, M.black, X1 - .03, 2.5, -2.9);
    const z0 = -1.25, len = 3.0, zc = z0 - len / 2;
    box(.78, .42, len, M.tufted, X1 - .45, 0, zc);
    const back = box(.24, .42, len, M.tufted, X1 - .13, .42, zc);
    [z0, z0 - len].forEach((z) => box(.85, .62, .22, M.tufted, X1 - .45, 0, z));
    [0, 1, 2].forEach((i) => box(.7, .07, .96, M.leather, X1 - .47, .42, zc - 1 + i));
    void back;
    // Garderobe
    cyl(.02, 1.7, M.white, X1 - .35, 0, -5.6); cyl(.18, .03, M.white, X1 - .35, 0, -5.6);
  })();

  /* ---------- Vorne: Schaufenster + Eingang links ---------- */
  (function front() {
    const glass = add(new THREE.PlaneGeometry(5, H), M.glass, 0, H / 2, Z0); glass.renderOrder = 2;
    [-2.48, -1.25, .6, 2.48].forEach((x) => box(.07, H, .07, M.black, x, 0, Z0));
    box(5, .08, .08, M.black, 0, H - .08, Z0); box(5, .06, .08, M.black, 0, 0, Z0);
    box(.03, 1.0, .05, M.gold, -1.32, .8, Z0 + .05); // Türgriff
    const logo = add(new THREE.PlaneGeometry(1.7, .85), new THREE.MeshBasicMaterial({ map: goldText([["AXARAY", 150, 210], ["BARBERS", 64, 300, 600], ["OHNE TERMIN", 56, 400, 600]]), transparent: true, depthWrite: false }), 1.55, 1.55, Z0 + .01); logo.renderOrder = 3;
    const neu = add(new THREE.PlaneGeometry(1.4, .35), new THREE.MeshBasicMaterial({ map: goldText([["Neueröffnung", 150, 300, "italic 700"]], 1024, 512), transparent: true, depthWrite: false }), .1, .55, Z0 + .01); neu.renderOrder = 3;
    // Fassade + Gehweg + Straße
    const facade = add(new THREE.PlaneGeometry(9, 2.6), new THREE.MeshStandardMaterial({ color: 0x3a2a1c, roughness: .9 }), 0, H + 1.3, Z0 + .02); void facade;
    box(5.2, .5, .12, M.black, 0, H + .1, Z0 + .08);
    add(new THREE.PlaneGeometry(4, .45), new THREE.MeshBasicMaterial({ map: goldText([["AXARAY BARBERS", 120, 300]], 1024, 512), transparent: true }), .3, H + .35, Z0 + .15);
    [[-4.5, -2.5], [2.5, 4.5]].forEach(([a, b]) => add(new THREE.PlaneGeometry(b - a, H), new THREE.MeshStandardMaterial({ color: 0x2e2218, roughness: .9 }), (a + b) / 2, H / 2, Z0 + .02));
    const walk = add(new THREE.PlaneGeometry(14, 3.2), new THREE.MeshStandardMaterial({ map: brick, roughness: .7 }), 0, .01, 1.6); walk.rotation.x = -Math.PI / 2;
    const street = add(new THREE.PlaneGeometry(30, 12), new THREE.MeshStandardMaterial({ color: 0x141416, roughness: .5, metalness: .2 }), 0, -.02, 9); street.rotation.x = -Math.PI / 2;
    box(14, .12, .25, new THREE.MeshStandardMaterial({ color: 0x555559 }), 0, -.02, 3.2);
    const pole = AX3D.barberPole(); pole.scale.setScalar(.22); pole.position.set(2.85, 2.25, .25); world.add(pole); world.userData.pole = pole;
    // Flagge "Barber Shop"
    box(1.0, .03, .03, M.white, 3.3, 3.25, .45);
    const flag = add(new THREE.PlaneGeometry(.7, .55), new THREE.MeshBasicMaterial({ map: canvasTex(256, 200, (g, w, h) => {
      g.fillStyle = "#fff"; g.fillRect(0, 0, w, h); g.lineWidth = 26;
      [["#c8102e", 0], ["#1f3a93", 60]].forEach(([c, o]) => { g.strokeStyle = c; for (let k = -2; k < 4; k++) { g.beginPath(); g.moveTo(-50 + k * 120 + o, h + 20); g.lineTo(70 + k * 120 + o, -20); g.stroke(); } });
      g.fillStyle = "#fff"; g.strokeStyle = "#1f3a93"; g.lineWidth = 5; g.font = "900 62px Impact, Arial Black, sans-serif"; g.textAlign = "center";
      g.strokeText("BARBER", w / 2, 92); g.fillText("BARBER", w / 2, 92); g.strokeText("SHOP", w / 2, 160); g.fillText("SHOP", w / 2, 160);
    }), side: THREE.DoubleSide }), 3.55, 2.92, .45); flag.rotation.y = .5;
    const lamp = new THREE.PointLight(0xffb27a, 1.2, 12); lamp.position.set(-3, 4, 4); world.add(lamp);
  })();

  /* ---------- Licht ---------- */
  world.add(new THREE.AmbientLight(0xffffff, .18));
  world.add(new THREE.HemisphereLight(0xf4f2ff, 0x2a2420, .35));
  [[-1, -1.8, .42], [1, -1.8, .42], [-1, -4.6, .42], [1, -4.6, .42], [-1.4, -6.5, .7], [1.3, -6.0, .7]].forEach(([x, z, i]) => { const l = new THREE.PointLight(0xfff8ee, i, 7, 1.6); l.position.set(x, 2.5, z); world.add(l); });
  // Spiegelungen: Umgebung einmal aus der Raummitte aufnehmen
  ready.then(() => {
    const rt = new THREE.WebGLCubeRenderTarget(256, { generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter });
    const cc = new THREE.CubeCamera(.05, 30, rt); cc.position.set(0, 1.5, -3.7); world.add(cc);
    cc.update(renderer, scene);
    [M.mirror, M.gold, M.gloss, M.marble, M.floor].forEach((m) => { m.envMap = rt.texture; m.envMapIntensity = m === M.mirror ? 1 : .6; m.needsUpdate = true; });
  });
  pending++; setTimeout(() => { if (--pending === 0) resolveReady(); }, 0); // falls keine Texturen

  /* ---------- Foto-Ebene vor der Kamera ---------- */
  const photoMat = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthTest: false, depthWrite: false, toneMapped: false });
  const photo = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), photoMat); photo.position.z = -1; photo.renderOrder = 999; camera.add(photo);
  const photoTex = KEYS.map((k) => (k.img ? load(k.img) : null));

  /* ---------- Kamerapfad ---------- */
  const posCurve = new THREE.CatmullRomCurve3(KEYS.map((k) => new THREE.Vector3(...k.pos)), false, "centripetal");
  const lookCurve = new THREE.CatmullRomCurve3(KEYS.map((k) => new THREE.Vector3(...k.look)), false, "centripetal");
  const ease = (t) => t * t * (3 - 2 * t);
  const tmpL = new THREE.Vector3();
  function place(p) {
    const f = p * (K - 1), i = Math.min(K - 2, Math.floor(f)), t = ease(f - i), u = (i + t) / (K - 1);
    posCurve.getPoint(u, camera.position);
    lookCurve.getPoint(u, tmpL);
    // "Fliegen-Effekt": leichtes Schweben
    const s = p * 60;
    camera.position.x += Math.sin(s * 1.3) * .025; camera.position.y += Math.sin(s * 2.1) * .02;
    tmpL.x += Math.sin(s * .9) * .05;
    camera.lookAt(tmpL);
    camera.rotateZ(Math.sin(s * .7) * .01);
    // Foto an der nächsten Station einblenden (Ken-Burns-Zoom)
    const a = Math.round(f), d = Math.abs(f - a), tex = photoTex[a];
    const op = showPhoto && tex && tex.image ? Math.max(0, Math.min(1, (0.36 - d) / 0.22)) : 0;
    photoMat.opacity = op * .97;
    if (op > 0) {
      if (photoMat.map !== tex) { photoMat.map = tex; photoMat.needsUpdate = true; }
      const vh = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)), vw = vh * camera.aspect, ia = tex.image.width / tex.image.height;
      const kb = 1.04 + (f - a + .4) * .08;
      if (ia > camera.aspect) photo.scale.set(vh * ia * kb, vh * kb, 1); else photo.scale.set(vw * kb, vw / ia * kb, 1);
      photo.position.x = (f - a) * .04;
    }
    return { f, a };
  }

  /* ---------- Overlay: Bildunterschrift, Punkte, Grundriss ---------- */
  const capEl = document.getElementById("tourCaption"), numEl = document.getElementById("tourNum"), titleEl = document.getElementById("tourTitle"), textEl = document.getElementById("tourText");
  const barEl = document.getElementById("tourBar"), hintEl = document.getElementById("tourHint"), dotsEl = document.getElementById("tourDots");
  const mapEl = document.getElementById("tourMap"), mapCtx = mapEl.getContext("2d");
  dotsEl.innerHTML = KEYS.map((k, i) => `<button type="button" aria-label="${k.title}" data-i="${i}"></button>`).join("");
  const range = () => sec.offsetHeight - innerHeight;
  const scrollToStop = (i, smooth = true) => scrollTo({ top: sec.offsetTop + (i / (K - 1)) * range(), behavior: smooth ? "smooth" : "auto" });
  dotsEl.addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { stopFilm(); scrollToStop(+b.dataset.i); } });

  // Grundriss von oben mit Position und Blickrichtung
  function drawMap(ctx, W, Hh) {
    const pad = 6, sx = (W - pad * 2) / 5, sz = (Hh - pad * 2 - 14) / 7.5;
    const X = (x) => pad + (x + 2.5) * sx, Z = (z) => pad + (-z) * sz;
    ctx.clearRect(0, 0, W, Hh);
    ctx.fillStyle = "rgba(11,11,13,.78)"; ctx.fillRect(0, 0, W, Hh);
    ctx.strokeStyle = "#d4af37"; ctx.lineWidth = 1.5; ctx.strokeRect(X(-2.5), Z(-7.5), 5 * sx, 7.5 * sz);
    ctx.fillStyle = "rgba(212,175,55,.35)";
    [-2.2, -3.8, -5.4].forEach((z) => ctx.fillRect(X(-2.5), Z(z) - .7 * sz, .55 * sx, 1.4 * sz));
    ctx.fillStyle = "rgba(255,255,255,.25)"; ctx.fillRect(X(-2.1), Z(-6.4), .9 * sx, .9 * sz); // Waschplatz
    ctx.fillRect(X(.7), Z(-6.3), 1.5 * sx, .6 * sz); // Kasse
    ctx.fillRect(X(1.75), Z(-1.2), .75 * sx, 3 * sz); // Lounge
    ctx.clearRect(X(-2.4), Z(0) - 1.5, 1.1 * sx, 3); // Eingang
    if (W >= 80) { ctx.fillStyle = "#9b978e"; ctx.font = "600 8px Inter, sans-serif"; ctx.textAlign = "center"; ctx.fillText("EINGANG", X(-1.85), Hh - 3); }
    const cx = camera.position.x, cz = camera.position.z;
    if (cz < .4) {
      const dir = new THREE.Vector3(); camera.getWorldDirection(dir);
      const ang = Math.atan2(dir.x, -dir.z), px = X(cx), pz = Z(Math.min(cz, 0));
      ctx.fillStyle = "rgba(243,215,122,.28)"; ctx.beginPath(); ctx.moveTo(px, pz);
      ctx.arc(px, pz, 26, ang - Math.PI / 2 - .5, ang - Math.PI / 2 + .5); ctx.closePath(); ctx.fill();
      ctx.fillStyle = "#f3d77a"; ctx.beginPath(); ctx.arc(px, pz, 3.5, 0, Math.PI * 2); ctx.fill();
    } else { ctx.fillStyle = "#f3d77a"; ctx.beginPath(); ctx.arc(X(cx), Hh - 12, 3.5, 0, Math.PI * 2); ctx.fill(); }
  }

  let mobile = null;
  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false); camera.aspect = w / h;
    mobile = w < 760; camera.fov = camera.aspect < .8 ? 74 : 56; camera.updateProjectionMatrix();
  }
  addEventListener("resize", resize); resize();

  /* ---------- Film abspielen ---------- */
  const playBtn = document.getElementById("tourPlay");
  let film = null;
  function stopFilm() { if (film) { cancelAnimationFrame(film.raf); film = null; playBtn.classList.remove("playing"); playBtn.querySelector("span").textContent = "Film abspielen"; } }
  playBtn.addEventListener("click", () => {
    if (film) return stopFilm();
    const startP = Math.max(0, Math.min(1, (scrollY - sec.offsetTop) / range()));
    const from = startP > .97 ? 0 : startP, dur = 48000 * (1 - from);
    if (startP > .97) scrollToStop(0, false);
    const t0 = performance.now();
    film = {};
    playBtn.classList.add("playing"); playBtn.querySelector("span").textContent = "Pause";
    (function step(now) {
      const k = Math.min(1, (now - t0) / dur), p = from + (1 - from) * k;
      scrollTo(0, sec.offsetTop + p * range());
      if (k < 1 && film) film.raf = requestAnimationFrame(step); else stopFilm();
    })(t0);
  });
  ["wheel", "touchstart", "keydown"].forEach((ev) => addEventListener(ev, () => film && stopFilm(), { passive: true }));

  /* ---------- Render-Schleife ---------- */
  let active = -1;
  const vis = AX3D.whenVisible(sec), clock = new THREE.Clock();
  function animate(p) {
    const poleTex = world.userData.pole?.userData.tex; if (poleTex) poleTex.offset.y = -clock.getElapsedTime() * .25;
    return place(p);
  }
  (function loop() {
    requestAnimationFrame(loop);
    if (!vis.visible || exporting) return;
    const p = Math.max(0, Math.min(1, (scrollY - sec.offsetTop) / range()));
    const { f } = animate(p);
    renderer.render(scene, camera);
    drawMap(mapCtx, mapEl.width, mapEl.height);
    const a = Math.round(f);
    if (a !== active) {
      active = a; const k = KEYS[a];
      capEl.classList.remove("show"); void capEl.offsetWidth; capEl.classList.add("show");
      numEl.textContent = `${String(a + 1).padStart(2, "0")} / ${String(K).padStart(2, "0")}`;
      titleEl.textContent = k.title; textEl.textContent = k.text;
      capEl.classList.toggle("final", !!k.final);
      [...dotsEl.children].forEach((d, i) => d.classList.toggle("on", i === a));
    }
    barEl.style.width = `${p * 100}%`;
    hintEl.style.opacity = p > .02 ? 0 : 1;
  })();

  /* ---------- Video-Export (Einzelbilder mit Untertitel) ---------- */
  const comp = document.createElement("canvas"), cctx = comp.getContext("2d"), mapC = document.createElement("canvas");
  function renderAt(p, W, Hh, opts = {}) {
    exporting = true; showPhoto = opts.photo !== false;
    renderer.setPixelRatio(1); renderer.setSize(W, Hh, false); camera.aspect = W / Hh; camera.fov = W / Hh < .8 ? 74 : 56; camera.updateProjectionMatrix();
    const { f } = animate(p); renderer.render(scene, camera);
    comp.width = W; comp.height = Hh;
    cctx.drawImage(renderer.domElement, 0, 0, W, Hh);
    // Kino-Balken + Vignette
    const bar = Math.round(Hh * .055); cctx.fillStyle = "#000"; cctx.fillRect(0, 0, W, bar); cctx.fillRect(0, Hh - bar, W, bar);
    const vg = cctx.createRadialGradient(W / 2, Hh / 2, Math.min(W, Hh) * .35, W / 2, Hh / 2, Math.max(W, Hh) * .75); vg.addColorStop(0, "rgba(0,0,0,0)"); vg.addColorStop(1, "rgba(0,0,0,.55)");
    cctx.fillStyle = vg; cctx.fillRect(0, 0, W, Hh);
    // Grundriss
    const mw = Math.round(Math.min(W, Hh) * .16), mh = Math.round(mw * 1.5); mapC.width = mw; mapC.height = mh; drawMap(mapC.getContext("2d"), mw, mh);
    cctx.drawImage(mapC, W - mw - bar * .6, bar + bar * .5);
    // Logo
    const u = Math.min(W, Hh) / 720;
    cctx.textAlign = "left"; cctx.fillStyle = "#d4af37"; cctx.font = `700 ${26 * u}px Cinzel, Georgia, serif`; cctx.fillText("AXARAY", bar * .7, bar + 40 * u);
    cctx.font = `600 ${11 * u}px Cinzel, Georgia, serif`; cctx.fillText("B A R B E R S", bar * .7 + 2, bar + 58 * u);
    // Untertitel der aktuellen Station
    const a = Math.round(f), d = Math.abs(f - a), alpha = Math.max(0, Math.min(1, (0.42 - d) / 0.2)), k = KEYS[a];
    if (alpha > 0) {
      cctx.globalAlpha = alpha;
      const tx = bar * .7, ty = Hh - bar - 30 * u;
      cctx.fillStyle = "rgba(0,0,0,.55)"; const bw = Math.min(W - tx * 2, 620 * u); cctx.fillRect(tx - 12 * u, ty - 72 * u, bw, 96 * u);
      cctx.fillStyle = "#d4af37"; cctx.fillRect(tx - 12 * u, ty - 72 * u, 4 * u, 96 * u);
      cctx.fillStyle = "#f3d77a"; cctx.font = `700 ${30 * u}px Cinzel, Georgia, serif`; cctx.fillText(k.title, tx + 4 * u, ty - 32 * u);
      cctx.fillStyle = "#e8e4da"; cctx.font = `400 ${17 * u}px Inter, sans-serif`;
      wrap(cctx, k.text, tx + 4 * u, ty - 4 * u, bw - 30 * u, 22 * u);
      cctx.globalAlpha = 1;
    }
    return comp.toDataURL("image/jpeg", .9);
  }
  function wrap(ctx, text, x, y, maxW, lh) {
    const words = text.split(" "); let line = "", yy = y, lines = 0;
    for (const w of words) { const t = line ? line + " " + w : w; if (ctx.measureText(t).width > maxW && line) { ctx.fillText(line, x, yy); line = w; yy += lh; if (++lines > 1) break; } else line = t; }
    if (lines < 2) ctx.fillText(line, x, yy);
  }
  window.ROOM = { ready, renderAt, keys: KEYS.length, endExport() { exporting = false; renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); resize(); } };
})();
