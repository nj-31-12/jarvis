/* Begehbarer Laden in Ego-Perspektive.
 * Der Kunde fliegt von der Straße durch die Tür (vorne links) hinein und läuft dann selbst durch den Salon:
 *   links die 3 Plätze mit Spiegeln · hinten links Waschplatz · hinten rechts Kasse · rechts am Fenster die Lounge.
 * Umsehen: ziehen · Laufen: auf den Boden tippen (oder WASD/Pfeiltasten) · Info-Punkte antippen.
 */
(function shop() {
  const C = window.CONFIG, sec = document.getElementById("rundgang"), canvas = document.getElementById("tourCanvas");
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fallback = () => {
    sec.classList.add("no-3d");
    const fb = document.getElementById("tourFallback"); fb.hidden = false;
    fb.innerHTML = C.tour.map((t) => `<figure><img src="${t.img}" alt="${t.title}" loading="lazy"><figcaption><b>${t.title}</b>${t.text}</figcaption></figure>`).join("");
  };
  if (!window.AX3D || !canvas) return fallback();
  const renderer = AX3D.makeRenderer(canvas);
  if (!renderer) return fallback();
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = .95;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x07070a);
  scene.fog = new THREE.Fog(0x07070a, 12, 34);
  const camera = new THREE.PerspectiveCamera(66, 1, .05, 80);
  camera.rotation.order = "YXZ";
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


  /* ======================= Ego-Steuerung ======================= */
  const now = () => (window.__tourClock ? window.__tourClock() : performance.now());
  const EYE = 1.62;
  const V = (a) => new THREE.Vector3(...a);
  const angles = (from, to) => { const d = new THREE.Vector3().subVectors(to, from); return { yaw: Math.atan2(-d.x, -d.z), pitch: Math.atan2(d.y, Math.hypot(d.x, d.z)) }; };
  const me = { pos: V([1.5, 2.6, 7.5]), yaw: 0, pitch: -.05 };
  const B = C.barbers, svc = (id) => C.services.find((s) => s.id === id);
  const go = (sel) => document.querySelector(sel)?.scrollIntoView({ behavior: "smooth" });

  // Info-Punkte im Laden: Ankerpunkt (wo der Pin schwebt), Standpunkt + Blickziel, Inhalt
  const SPOTS = [
    { id: "eingang", icon: "🚪", label: "Eingang & Zeiten", anchor: [-1.85, 2.35, 0], pos: [-0.75, EYE, -1.9], look: [-1.85, 1.45, 0],
      card: () => ({ title: "Eingang – vorne links", text: `${openState().text}. Mo–Fr 9–18:30 · Sa 9–16:30. Ohne Termin jederzeit willkommen – nur ca. 10 Min. von Aschaffenburg, Parken gegenüber (2 Std. 1,50 €).`,
        actions: [["🧭 Route planen", () => window.open(`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(C.mapsQuery)}`, "_blank", "noopener")], ["📞 Anrufen", () => (location.href = `tel:${C.phone}`)]] }) },
    { id: "produkte", icon: "🧴", label: "Produkte", anchor: [-2.2, 2.05, -0.95], pos: [-0.55, EYE, -1.0], look: [-2.5, 1.15, -0.95],
      card: () => ({ title: "Profi-Produkte", text: "Wachs, Powder, Barber-Cologne – genau das, was wir an den Plätzen benutzen. Frag deinen Barber, was zu deinen Haaren passt.",
        actions: [["💬 Frage stellen", () => askBot("Welches Produkt passt zu meinen Haaren?")]] }) },
    ...[-2.2, -3.8, -5.4].map((z, i) => ({ id: `platz${i + 1}`, icon: "✂", label: `Platz ${i + 1} · ${B[i].name}`, anchor: [-2.3, 2.6, z], pos: [-0.05, EYE, z + .25], look: [-2.5, 1.25, z],
      card: () => ({ title: `Platz ${i + 1} · ${B[i].name}`, img: B[i].img, text: `${B[i].specialty}. ${B[i].text}`, cuts: B[i].cuts,
        actions: [["📅 Bei " + B[i].name + " buchen", () => { booking.prefill({ barber: B[i].id }); booking.focus(); }], ["🧑 Haarschnitte ausprobieren", () => go("#studio")]] }) })),
    { id: "wasch", icon: "🚿", label: "Waschplatz", anchor: [-1.65, 1.75, -7.05], pos: [-0.5, EYE, -4.9], look: [-1.75, .8, -7.3],
      card: () => ({ title: "Waschplatz – hinten links", text: `Haare waschen, Hot Towel und Kopfmassage. ${svc("wax") ? `Gesichtspflege ab ${svc("wax").price} €.` : ""}`,
        actions: [["📅 Mit Pflege buchen", () => { booking.prefill({ service: "wax" }); booking.focus(); }]] }) },
    { id: "fragen", icon: "❓", label: "Fragen?", anchor: [.45, 2.5, -7.4], pos: [.3, EYE, -4.3], look: [.45, 1.8, -7.5],
      card: () => ({ title: "Fragen? Frag uns.", text: "Der Axaray-Assistent beantwortet Fragen zu Preisen, Fades, Bart und Terminen – per Sprache oder Text. Oder ruf direkt an.",
        actions: [["🎙 Assistent fragen", () => askBot()], ["📞 " + C.phoneDisplay, () => (location.href = `tel:${C.phone}`)]] }) },
    { id: "kasse", icon: "💳", label: "Kasse · Termin & Zahlung", anchor: [1.45, 1.75, -6.6], pos: [.45, EYE, -4.55], look: [1.5, 1.0, -6.8],
      card: () => ({ title: "Kasse – hinten rechts", text: "Hier buchst du deinen Termin und bezahlst: bar, Karte – oder schon online mit PayPal, Apple Pay, Google Pay oder Klarna. Und hier gibt’s deine Stempel: 10 Stempel = Haarschnitt gratis + Getränk.",
        prices: true, actions: [["📅 Termin buchen", () => booking.focus()], ["🎟 Stempelkarte", () => account.open()]] }) },
    { id: "lounge", icon: "🛋", label: "Lounge", anchor: [2.1, 1.35, -2.75], pos: [-.55, EYE, -4.1], look: [2.3, .6, -2.5],
      card: () => ({ title: "Lounge – rechts am Fenster", text: "Ohne Termin gekommen? Nimm auf dem Chesterfield Platz – Kaffee, Tee oder Wasser gehen aufs Haus.",
        actions: [["☕ Getränk bestellen", () => drinkBot()], ["⏱ Wartezeit anfragen", () => askBot("Wie lange ist die Wartezeit gerade?")]] }) },
  ];
  const ORDER = ["eingang", "produkte", "platz1", "platz2", "platz3", "wasch", "fragen", "kasse", "lounge"];
  const spotById = (id) => SPOTS.find((s) => s.id === id);

  function askBot(q) {
    window.concierge?.open();
    if (q) window.concierge?.say(`Gute Frage! ${/produkt/i.test(q) ? "Für Struktur nimm Matt-Wachs oder Powder, für Glanz und Halt Pomade. Dein Barber zeigt dir beim Termin, wie du’s stylst." : "Komm einfach vorbei – oder buch dir online einen festen Termin, dann gibt’s keine Wartezeit."}`);
  }
  function drinkBot() {
    if (!window.concierge) return;
    window.concierge.open();
    window.concierge.ask("Was darf’s sein? Geht aufs Haus. ☕", ["☕ Kaffee", "🍵 Tee", "💧 Wasser", "🥤 Cola"].map((d) => ({ label: d, run: () => window.concierge.say(`${d} kommt gleich zu dir!${C.draft ? " (Demo – live landet die Bestellung auf dem Tablet am Empfang.)" : ""}`) })));
  }

  /* ---------- Bewegung ---------- */
  let mode = "idle", walk = null, intro = null, activeSpot = null;
  const lerpAng = (a, b, t) => { let d = ((b - a + Math.PI) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2) - Math.PI; return a + d * t; };
  const ease = (t) => t * t * (3 - 2 * t);
  const BOUNDS = { x0: -1.0, x1: 1.55, z0: -6.1, z1: -.35 };
  const clampPos = (p) => { p.x = Math.max(BOUNDS.x0, Math.min(BOUNDS.x1, p.x)); p.z = Math.max(BOUNDS.z0, Math.min(BOUNDS.z1, p.z)); return p; };
  function walkTo(pos, look, onArrive) {
    const to = V(pos), ang = look ? angles(to, V(look)) : { yaw: me.yaw, pitch: me.pitch };
    const dist = me.pos.distanceTo(to);
    walk = { from: me.pos.clone(), to, fy: me.yaw, ty: ang.yaw, fp: me.pitch, tp: ang.pitch, t0: now(), dur: Math.max(700, Math.min(2600, dist * 650)), onArrive };
  }
  function visit(id) {
    const s = spotById(id); if (!s) return;
    activeSpot = id; hideCard();
    if (mode !== "explore") startExplore();
    // Hochkant: etwas tiefer blicken, damit der Ort oberhalb der Info-Karte zu sehen ist
    const look = camera.aspect < .8 ? [s.look[0], s.look[1] - .75, s.look[2]] : s.look;
    walkTo(s.pos, look, () => showCard(s));
  }

  // Einflug von der Straße durch die Tür ("Fliegen-Effekt")
  const introPos = new THREE.CatmullRomCurve3([V([3.4, 4.8, 11]), V([1.6, 3.1, 6]), V([-1.2, 2.1, 2.6]), V([-1.85, EYE + .05, .7]), V([-1.75, EYE, -.4]), V([-.75, EYE, -1.9])], false, "centripetal");
  const introLook = new THREE.CatmullRomCurve3([V([0, 1.4, -3]), V([-.8, 1.5, -2]), V([-1.8, 1.5, -1]), V([-1.6, 1.5, -4]), V([-.2, 1.4, -6]), V([.4, 1.35, -7.2])], false, "centripetal");
  const introLines = [[0, "Hauptstraße 118, Hösbach – die Barber-Pole dreht sich schon."], [.38, "Vorne links geht’s rein …"], [.7, "Willkommen bei Axaray Barbers!"]];
  function startIntro() {
    sec.scrollIntoView({ behavior: "smooth" });
    hideCard(); mode = "intro"; intro = { t0: now(), dur: 7500 };
    sec.classList.add("in-intro"); $("#tourStart").hidden = true;
  }
  function startExplore() {
    mode = "explore"; intro = null; sec.classList.remove("in-intro"); sec.classList.add("exploring");
    $("#tourStart").hidden = true; $("#tourNav").hidden = false;
    hint("Ziehen zum Umsehen · auf den Boden tippen zum Laufen · goldene Punkte antippen", 5000);
  }
  let hintTimer = null;
  function hint(t, ms = 0) { const h = $("#tourHint"); h.textContent = t; h.style.opacity = t ? 1 : 0; clearTimeout(hintTimer); if (ms) hintTimer = setTimeout(() => (h.style.opacity = 0), ms); }

  /* ---------- Eingaben ---------- */
  let drag = null;
  canvas.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY, moved: 0, type: e.pointerType }; });
  addEventListener("pointermove", (e) => {
    if (!drag || mode !== "explore") return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y; drag.x = e.clientX; drag.y = e.clientY; drag.moved += Math.abs(dx) + Math.abs(dy);
    if (walk) return;
    me.yaw += dx * .0055;
    if (drag.type === "mouse") me.pitch = Math.max(-.7, Math.min(.6, me.pitch + dy * .004));
  });
  addEventListener("pointerup", (e) => {
    if (!drag) return;
    const click = drag.moved < 8; drag = null;
    if (!click || e.target !== canvas) return;
    if (mode === "idle") return startIntro();
    if (mode !== "explore") return;
    // Auf den Boden getippt: dorthin laufen
    const r = canvas.getBoundingClientRect(), ndc = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    const ray = new THREE.Raycaster(); ray.setFromCamera(ndc, camera);
    const hit = new THREE.Vector3();
    if (ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), hit) && hit.z < 0) {
      const target = clampPos(new THREE.Vector3(hit.x, EYE, hit.z));
      const keepLook = target.clone().add(new THREE.Vector3(-Math.sin(me.yaw), Math.tan(me.pitch), -Math.cos(me.yaw)));
      activeSpot = null; hideCard(); walkTo(target.toArray(), keepLook.toArray());
    }
  });
  const keys = new Set();
  addEventListener("keydown", (e) => { if (mode === "explore" && /^(Arrow|Key[WASD])/.test(e.code) && inView()) { keys.add(e.code); e.preventDefault(); } });
  addEventListener("keyup", (e) => keys.delete(e.code));
  const inView = () => { const r = sec.getBoundingClientRect(); return r.top < innerHeight * .5 && r.bottom > innerHeight * .5; };

  $("#tourEnter").addEventListener("click", startIntro);
  document.addEventListener("click", (e) => { if (e.target.closest("[data-tour-play]")) { sec.scrollIntoView({ behavior: "smooth" }); setTimeout(() => (mode === "explore" ? visit("eingang") : startIntro()), 500); } });
  const step = (dir) => { const i = ORDER.indexOf(activeSpot); visit(ORDER[(i < 0 ? (dir > 0 ? 0 : ORDER.length - 1) : (i + dir + ORDER.length) % ORDER.length)]); };
  $("#spotPrev").addEventListener("click", () => step(-1));
  $("#spotNext").addEventListener("click", () => step(1));

  /* ---------- Info-Karte ---------- */
  const card = $("#spotCard");
  function showCard(s) {
    const c = s.card();
    card.innerHTML = `
      <button class="spot-close" type="button" aria-label="Schließen">×</button>
      <p class="spot-num">${ORDER.indexOf(s.id) + 1} / ${ORDER.length}</p>
      <div class="spot-head">${c.img ? `<img src="${c.img}" alt="">` : `<span class="spot-ico">${s.icon}</span>`}<h3>${esc(c.title)}</h3></div>
      <p>${esc(c.text)}</p>
      ${c.cuts ? `<div class="spot-cuts">${c.cuts.map((k, j) => `<button type="button" data-cut="${j}">✂ ${esc(k.label)}</button>`).join("")}</div>` : ""}
      ${c.prices ? `<div class="spot-prices">${C.services.slice(0, 4).map((x) => `<span>${esc(x.name)}<b>${x.price} €</b></span>`).join("")}</div>` : ""}
      <div class="spot-actions">${c.actions.map(([l], j) => `<button type="button" class="${j ? "btn btn-ghost btn-sm" : "btn btn-gold btn-sm"}" data-act="${j}">${esc(l)}</button>`).join("")}</div>`;
    card.hidden = false; card.classList.remove("show"); void card.offsetWidth; card.classList.add("show");
    $("#spotName").textContent = s.label;
    card.querySelector(".spot-close").onclick = hideCard;
    card.querySelectorAll("[data-act]").forEach((b) => (b.onclick = () => c.actions[+b.dataset.act][1]()));
    card.querySelectorAll("[data-cut]").forEach((b) => (b.onclick = () => { const k = c.cuts[+b.dataset.cut]; studio.set({ style: k.style, fade: k.fade, beard: k.beard }); go("#studio"); }));
  }
  function hideCard() { card.hidden = true; }

  /* ---------- Pins ---------- */
  const pinsEl = $("#tourPins");
  pinsEl.innerHTML = SPOTS.map((s) => `<button type="button" class="pin" data-spot="${s.id}"><span class="pin-dot">${s.icon}</span><span class="pin-label">${esc(s.label)}</span></button>`).join("");
  pinsEl.addEventListener("click", (e) => { const b = e.target.closest(".pin"); if (b) visit(b.dataset.spot); });
  const pinEls = [...pinsEl.children], tmpV = new THREE.Vector3();
  function placePins(w, h) {
    SPOTS.forEach((s, i) => {
      const el = pinEls[i];
      if (mode !== "explore") { el.style.display = "none"; return; }
      tmpV.set(...s.anchor).project(camera);
      const dist = camera.position.distanceTo(tmpV.set(...s.anchor)); tmpV.project(camera);
      const vis = tmpV.z < 1 && Math.abs(tmpV.x) < 1.05 && Math.abs(tmpV.y) < 1.05;
      el.style.display = vis ? "" : "none";
      if (!vis) return;
      el.style.transform = `translate(${((tmpV.x + 1) / 2) * w}px, ${((1 - tmpV.y) / 2) * h}px) translate(-50%, -50%) scale(${Math.max(.7, Math.min(1.15, 3.2 / dist))})`;
      el.classList.toggle("active", s.id === activeSpot);
      el.classList.toggle("far", dist > 4.5);
    });
  }

  /* ---------- Grundriss ---------- */
  const mapEl = $("#tourMap"), mapCtx = mapEl.getContext("2d");
  function drawMap() {
    const W = mapEl.width, Hh = mapEl.height, ctx = mapCtx, pad = 6, sx = (W - pad * 2) / 5, sz = (Hh - pad * 2 - 12) / 7.5;
    const X = (x) => pad + (x + 2.5) * sx, Z = (z) => pad + (-z) * sz;
    ctx.clearRect(0, 0, W, Hh); ctx.fillStyle = "rgba(11,11,13,.82)"; ctx.fillRect(0, 0, W, Hh);
    ctx.strokeStyle = "#d4af37"; ctx.lineWidth = 1.5; ctx.strokeRect(X(-2.5), Z(-7.5), 5 * sx, 7.5 * sz);
    ctx.clearRect(X(-2.35), Z(0) - 2, 1.0 * sx, 4);
    ctx.fillStyle = "rgba(212,175,55,.35)"; [-2.2, -3.8, -5.4].forEach((z) => ctx.fillRect(X(-2.5), Z(z) - .65 * sz, .55 * sx, 1.3 * sz));
    ctx.fillStyle = "rgba(255,255,255,.22)"; ctx.fillRect(X(-2.1), Z(-6.4), .9 * sx, .9 * sz); ctx.fillRect(X(.7), Z(-6.3), 1.5 * sx, .6 * sz); ctx.fillRect(X(1.75), Z(-1.2), .75 * sx, 3 * sz);
    ctx.fillStyle = "#9b978e"; ctx.font = "600 8px Inter, sans-serif"; ctx.textAlign = "center"; ctx.fillText("EINGANG", X(-1.85), Hh - 3);
    const cz = Math.min(me.pos.z, .2), px = X(me.pos.x), pz = Z(cz), ang = -me.yaw;
    ctx.fillStyle = "rgba(243,215,122,.28)"; ctx.beginPath(); ctx.moveTo(px, pz); ctx.arc(px, pz, 24, ang - Math.PI / 2 - .55, ang - Math.PI / 2 + .55); ctx.closePath(); ctx.fill();
    ctx.fillStyle = "#f3d77a"; ctx.beginPath(); ctx.arc(px, pz, 3.5, 0, Math.PI * 2); ctx.fill();
  }

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.fov = camera.aspect < .8 ? 78 : 64; camera.updateProjectionMatrix();
  }
  addEventListener("resize", resize); resize();

  /* ---------- Schleife ---------- */
  const vis = AX3D.whenVisible(sec), clock = new THREE.Clock();
  let bob = 0, lastLine = -1;
  function loop() {
    requestAnimationFrame(loop);
    const nowMs = now(), dt = Math.min(.05, (nowMs - (loop.last || nowMs)) / 1000), t = nowMs / 1000; loop.last = nowMs;
    if (!vis.visible) return;
    const poleTex = world.userData.pole?.userData.tex; if (poleTex) poleTex.offset.y = -t * .25;
    let moving = false;
    if (mode === "idle") {
      me.pos.set(1.4 + Math.sin(t * .25) * 1.2, 2.3 + Math.sin(t * .4) * .25, 7.2);
      const a = angles(me.pos, V([-.6, 1.4, -3])); me.yaw = a.yaw; me.pitch = a.pitch;
    } else if (mode === "intro") {
      const k = Math.min(1, (now() - intro.t0) / intro.dur), u = ease(k);
      introPos.getPoint(u, me.pos); const a = angles(me.pos, introLook.getPoint(u)); me.yaw = a.yaw; me.pitch = a.pitch;
      const line = introLines.filter(([s]) => k >= s).length - 1;
      if (line !== lastLine) { lastLine = line; hint(introLines[line][1]); }
      moving = me.pos.y < 2.2;
      if (k >= 1) { startExplore(); visit("eingang"); }
    } else if (walk) {
      const k = Math.min(1, (now() - walk.t0) / walk.dur), u = ease(k);
      me.pos.lerpVectors(walk.from, walk.to, u); me.yaw = lerpAng(walk.fy, walk.ty, u); me.pitch = walk.fp + (walk.tp - walk.fp) * u;
      moving = true;
      if (k >= 1) { const cb = walk.onArrive; walk = null; cb && cb(); }
    } else if (keys.size) {
      const f = (keys.has("KeyW") || keys.has("ArrowUp") ? 1 : 0) - (keys.has("KeyS") || keys.has("ArrowDown") ? 1 : 0);
      const s = (keys.has("KeyD") ? 1 : 0) - (keys.has("KeyA") ? 1 : 0);
      if (keys.has("ArrowLeft")) me.yaw += dt * 1.8; if (keys.has("ArrowRight")) me.yaw -= dt * 1.8;
      me.pos.x += (-Math.sin(me.yaw) * f + Math.cos(me.yaw) * s) * dt * 1.8;
      me.pos.z += (-Math.cos(me.yaw) * f - Math.sin(me.yaw) * s) * dt * 1.8;
      clampPos(me.pos); moving = !!(f || s);
      if (moving && activeSpot) { activeSpot = null; hideCard(); }
    }
    // Kopf-Wippen beim Gehen – wie mit eigenen Augen
    bob = moving ? bob + dt * 9 : bob * .9;
    camera.position.copy(me.pos); camera.position.y += moving ? Math.sin(bob) * .022 : 0;
    camera.rotation.set(me.pitch, me.yaw, moving ? Math.sin(bob * .5) * .006 : 0);
    renderer.render(scene, camera);
    placePins(canvas.clientWidth, canvas.clientHeight);
    drawMap();
  }
  loop();
  window.SHOP = { visit, startIntro, step, ready };
})();
