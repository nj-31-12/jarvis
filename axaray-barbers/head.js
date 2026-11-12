/* 3D Style-Studio mit realistischem Kopf.
 * Basis: 3D-Scan "Lee Perry-Smith" (Infinite-Realities, CC BY 3.0).
 * Haare und Bart: viele dünne Schichten über der Haut ("Shell-Fur"). Jede Schicht zeigt nur
 * die Haarspitzen, die so lang sind – so entstehen echte Fades, Konturen und Bartlinien.
 */
window.HEAD = (() => {
  const STYLES = [
    { id: "buzz",      name: "Buzz Cut",    fade: "none",  svc: "cut",  tip: "Pflegeleicht und kantig – betont starke Gesichtszüge." },
    { id: "crop",      name: "French Crop", fade: "skin",  svc: "fade", tip: "Kurzer Pony, Struktur oben – kaschiert eine hohe Stirn." },
    { id: "quiff",     name: "Quiff",       fade: "low",   svc: "fade", tip: "Volumen vorne streckt das Gesicht optisch." },
    { id: "pompadour", name: "Pompadour",   fade: "mid",   svc: "fade", tip: "Viel Höhe – ideal für runde Gesichter." },
    { id: "sidepart",  name: "Side Part",   fade: "taper", svc: "cut",  tip: "Der Klassiker – passt immer, ob Büro oder Hochzeit." },
    { id: "curly",     name: "Curly Top",   fade: "mid",   svc: "fade", tip: "Locken oben, kurze Seiten – lässig und modern." },
    { id: "slick",     name: "Slick Back",  fade: "low",   svc: "cut",  tip: "Nach hinten gestylt – edel, braucht etwas Länge." },
    { id: "flow",      name: "Mittellang",  fade: "none",  svc: "cut",  tip: "Natürlich fallend – wir formen Konturen und Nacken." },
  ];
  const FADES = [
    { id: "none", name: "Kein" }, { id: "taper", name: "Taper" }, { id: "low", name: "Low" },
    { id: "mid", name: "Mid" }, { id: "high", name: "High" }, { id: "skin", name: "Skin" },
  ];
  const BEARDS = [
    { id: "none", name: "Glatt" }, { id: "stubble", name: "3-Tage" }, { id: "short", name: "Kurzbart" },
    { id: "full", name: "Vollbart" }, { id: "goatee", name: "Goatee" }, { id: "mustache", name: "Schnurrbart" },
  ];
  const SHAPES = [{ id: "oval", name: "Oval" }, { id: "round", name: "Rund" }, { id: "square", name: "Eckig" }, { id: "long", name: "Länglich" }];
  // Hautton als Faktor auf die Scan-Textur
  const SKINS = [{ m: "#ffffff", s: "#e6c2a6" }, { m: "#e3c7b0", s: "#cfa283" }, { m: "#bf987a", s: "#a87a5a" }, { m: "#8f6a52", s: "#7a553e" }, { m: "#5f4334", s: "#4e3427" }];
  const HAIR_COLORS = [
    { c: "#1a1512", n: "Schwarz" }, { c: "#3b2718", n: "Dunkelbraun" }, { c: "#6e4a2e", n: "Braun" },
    { c: "#b89262", n: "Blond" }, { c: "#9a9590", n: "Grau" },
  ];
  const RECO = {
    oval:   { hair: ["quiff", "pompadour", "sidepart", "crop"], beard: ["short", "stubble", "full"] },
    round:  { hair: ["pompadour", "quiff", "crop"], beard: ["goatee", "short"] },
    square: { hair: ["crop", "buzz", "sidepart", "curly"], beard: ["stubble", "short"] },
    long:   { hair: ["crop", "curly", "sidepart", "flow"], beard: ["full", "short"] },
  };
  const state = { shape: "oval", skin: SKINS[1].m, style: "quiff", fade: "low", hair: HAIR_COLORS[0].c, beard: "short", beardColor: HAIR_COLORS[0].c };

  let ready = false;
  const waiting = [];
  const canvas = document.getElementById("headCanvas");
  if (!window.AX3D || !canvas || !THREE.GLTFLoader) return publicApi();
  const renderer = AX3D.makeRenderer(canvas);
  if (!renderer) return publicApi();

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, .1, 50);
  camera.position.set(0, .1, 8.2);
  scene.add(new THREE.HemisphereLight(0xfff4e8, 0x1a1a1f, .7));
  const key = new THREE.DirectionalLight(0xfff2e6, 1.0); key.position.set(3, 4, 5); scene.add(key);
  const rim = new THREE.DirectionalLight(0xd4af37, .8); rim.position.set(-4, 2, -3); scene.add(rim);
  const fill = new THREE.DirectionalLight(0xffffff, .3); fill.position.set(-3, 0, 4); scene.add(fill);
  const root = new THREE.Group(); root.scale.setScalar(.5); root.position.y = -.85; scene.add(root);

  /* ---------- Maße des Scans (Modell-Einheiten) ---------- */
  // Scheitel 4.0 · Haaransatz ~3.05 · Augen 1.85 · Nasenspitze 1.1 · Mund 0.45 · Kinn -0.6
  const ZC = .07;
  const lerpT = (t, x) => {
    if (x <= t[0][0]) return t[0][1];
    for (let i = 1; i < t.length; i++) if (x <= t[i][0]) { const [x0, y0] = t[i - 1], [x1, y1] = t[i]; return y0 + (y1 - y0) * (x - x0) / (x1 - x0); }
    return t[t.length - 1][1];
  };
  const ss = (e0, e1, x) => { const t = Math.max(0, Math.min(1, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t); };
  const HAIRLINE = [[0, 3.05], [.5, 3.0], [.95, 2.72], [1.12, 2.45], [1.2, 1.55], [1.34, 1.42], [1.42, 2.15], [1.75, 2.15], [2.0, 1.3], [2.4, .78], [Math.PI, .68]];
  const FADE_TOP = { none: null, taper: 1.75, low: 2.25, mid: 2.6, high: 2.95, skin: 3.05 };
  const CHEEK = [[0, .9], [.4, .9], [.6, 1.05], [.95, 1.25], [1.2, 1.5], [1.34, 1.5]];
  const NECK = [[0, -.8], [.8, -.55], [1.34, .35]];

  // Haar: Länge (Modell-Einheiten, 1 ≈ 5 cm) oben/vorne/Seite und Kämmrichtung
  const HAIR = {
    buzz:      { top: .05, side: .04, front: 0 },
    crop:      { top: .28, side: .14, front: .1 },
    quiff:     { top: .32, side: .14, front: .3 },
    pompadour: { top: .42, side: .15, front: .36 },
    sidepart:  { top: .42, side: .16, front: .05 },
    curly:     { top: .5,  side: .14, front: .05 },
    slick:     { top: .5,  side: .16, front: .05 },
    flow:      { top: .55, side: .42, front: .1 },
  };
  function comb(style, x, y, z, d) {
    const top = ss(2.6, 3.4, y), front = (1 - ss(.3, 1.0, d)) * ss(2.75, 3.3, y);
    const v = new THREE.Vector3();
    switch (style) {
      case "crop": v.set(0, -.25, 1).multiplyScalar(top).add(new THREE.Vector3(0, -.6, 0).multiplyScalar(1 - top)); break;
      case "quiff": v.set(0, .2, -.5).multiplyScalar(top * (1 - front)).add(new THREE.Vector3(0, 1.1, .5).multiplyScalar(front)); break;
      case "pompadour": v.set(0, .25, -1).multiplyScalar(top * (1 - front)).add(new THREE.Vector3(0, 1, .15).multiplyScalar(front)); break;
      case "sidepart": { const s = x > -.55 ? 1 : -1; v.set(s, .1, .15).multiplyScalar(top); v.y -= .4 * (1 - top); break; }
      case "slick": v.set(0, .05, -1).multiplyScalar(top + .3); break;
      case "curly": v.set(Math.sin(x * 9 + z * 7) * .7, .45, Math.cos(z * 9 - x * 5) * .7).multiplyScalar(top); break;
      case "flow": v.set(x * .15, -1, z * .15); break;
      default: break;
    }
    return v;
  }
  function hairAt(x, y, z) {
    const a = Math.atan2(x, z - ZC), d = Math.abs(a), st = state.style, H = HAIR[st];
    const line = lerpT(HAIRLINE, d) - (st === "flow" ? (d > 1.3 ? .5 : 0) : 0);
    if (y < line - .05) return [0, 0];
    let cov = ss(line - .05, line + .08, y);
    const top = FADE_TOP[state.fade];
    if (top != null) {
      const side = ss(.8, 1.15, d) * (1 - ss(3.0, 3.3, y));
      const minC = state.fade === "skin" ? 0 : state.fade === "taper" ? .5 : .12;
      const f = minC + (1 - minC) * ss(top - .8, top, y);
      cov *= 1 - side + side * f;
    }
    const tW = ss(2.55, 3.35, y), fW = (1 - ss(.3, 1.0, d)) * ss(2.75, 3.25, y);
    let len = H.side + (H.top - H.side) * tW + H.front * fW;
    if (top != null) len *= .25 + .75 * Math.min(1, cov + (1 - ss(.8, 1.15, d)));
    if (st === "sidepart" && Math.abs(x + .55) < .04 && y > 3.0) cov *= .15; // Scheitel
    return [len, cov];
  }
  function beardAt(x, y, z) {
    const st = state.beard; if (st === "none") return [0, 0];
    const a = Math.atan2(x, z - ZC), d = Math.abs(a);
    if (d > 1.36) return [0, 0];
    const cheek = lerpT(CHEEK, d), neck = lerpT(NECK, d);
    const mouth = d < .34 && y > .3 && y < .64;
    const must = d < .5 && y >= .62 && y < .92;
    const chin = d < .46 && y < .3 && y > -.7;
    const inFull = y < cheek && y > neck;
    const edge = ss(cheek + .02, cheek - .1, y) * ss(neck - .05, neck + .15, y) * ss(1.36, 1.25, d);
    if (st === "mustache") return must ? [.12, 1] : [0, 0];
    if (st === "goatee") return (must || chin) && !mouth ? [chin ? .2 : .12, 1] : [0, 0];
    if (mouth || !inFull) return [0, 0];
    if (st === "stubble") return [.035, .6 * edge];
    if (st === "short") return [.13, .95 * edge];
    return [.28 + (chin || y < 0 ? .2 : 0), edge]; // Vollbart, am Kinn länger
  }

  /* ---------- Shader für Haar-Schichten ---------- */
  const VERT = `
    attribute vec4 aHair; attribute vec3 aComb;
    uniform float uH; uniform float uKind;
    varying vec3 vRest; varying float vCov; varying float vLen; varying vec3 vN;
    void main() {
      float len = uKind < .5 ? aHair.x : aHair.z;
      float cov = uKind < .5 ? aHair.y : aHair.w;
      vec3 dir = uKind < .5 ? aComb : vec3(0., -1., .25);
      vec3 p = position + normal * len * uH * (1. - .35 * uH) + dir * len * uH * uH * 1.1;
      vRest = position; vCov = cov; vLen = len;
      vN = normalize(normalMatrix * normalize(normal + dir * uH * .6));
      gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.);
    }`;
  const FRAG = `
    uniform float uH; uniform vec3 uColor; uniform float uDensity; uniform float uCurl;
    varying vec3 vRest; varying float vCov; varying float vLen; varying vec3 vN;
    float hash(vec3 p) { p = fract(p * .3183099 + .1); p *= 17.; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
    void main() {
      if (vLen < .004 || vCov < .01) discard;
      vec3 q = vRest * uDensity;
      vec3 id = floor(q); vec3 f = fract(q) - .5;
      float r = hash(id);
      if (r > vCov) discard;
      float h = uH * (.65 + .7 * hash(id + 7.3));           // jedes Haar etwas anders lang
      if (h > 1.) discard;
      if (length(f) > .55 * (1. - h) + .04) discard;
      vec3 L = normalize(vec3(.45, .65, .6));
      float diff = .35 + .65 * max(dot(vN, L), 0.);
      float spec = pow(max(dot(reflect(-L, vN), vec3(0., 0., 1.)), 0.), 18.) * .18;
      float rimL = pow(1. - max(vN.z, 0.), 3.) * .3;
      vec3 c = uColor * (.32 + .8 * uH) * diff * (.82 + .36 * hash(id + 3.1));
      c += spec + rimL * vec3(.83, .69, .22) * uH;
      gl_FragColor = vec4(c, 1.);
    }`;

  let geo = null, base = null, headMesh = null;
  const hairLayers = [], beardLayers = [];
  const HAIR_L = 22, BEARD_L = 14;
  const colorU = { hair: { value: new THREE.Color(state.hair) }, beard: { value: new THREE.Color(state.beardColor) } };
  function layer(kind, h) {
    const m = new THREE.ShaderMaterial({
      vertexShader: VERT, fragmentShader: FRAG,
      uniforms: { uH: { value: h }, uKind: { value: kind }, uColor: kind ? colorU.beard : colorU.hair, uDensity: { value: kind ? 60 : 54 }, uCurl: { value: 0 } },
    });
    const mesh = new THREE.Mesh(geo, m); mesh.renderOrder = 1 + h; mesh.frustumCulled = false;
    return mesh;
  }

  // Gesichtsform: sanfte Verformung des Scans (bleibt realistisch)
  function deform() {
    const p = geo.attributes.position, sh = state.shape;
    for (let i = 0; i < p.count; i++) {
      let x = base[i * 3], y = base[i * 3 + 1], z = base[i * 3 + 2];
      if (sh === "round") { const w = 1 - Math.min(1, Math.abs(y - 1.2) / 2.2); x *= 1 + .07 * w; y = 1.85 + (y - 1.85) * .96; }
      if (sh === "square") { const jaw = ss(1.2, -.2, y) * (y > -.9 ? 1 : 0); x *= 1 + .1 * jaw; if (y > 3.2) y = 3.2 + (y - 3.2) * .9; }
      if (sh === "long") { if (y > -1) y = 1.85 + (y - 1.85) * 1.06; x *= .96; }
      p.setXYZ(i, x, y, z);
    }
    p.needsUpdate = true;
  }
  function updateHairAttrs() {
    const p = geo.attributes.position, aH = geo.attributes.aHair, aC = geo.attributes.aComb, col = geo.attributes.color;
    const hc = new THREE.Color(state.hair), bc = new THREE.Color(state.beardColor);
    for (let i = 0; i < p.count; i++) {
      const x = base[i * 3], y = base[i * 3 + 1], z = base[i * 3 + 2];
      const [hl, hcv] = hairAt(x, y, z), [bl, bcv] = beardAt(x, y, z);
      aH.setXYZW(i, hl, hcv, bl, bcv);
      const c = comb(state.style, x, y, z, Math.abs(Math.atan2(x, z - ZC))); aC.setXYZ(i, c.x, c.y, c.z);
      // Kopfhaut unter dichtem Haar abdunkeln (Haaransatz wirkt echt)
      const k = Math.min(1, hcv * Math.min(1, hl * 6)) * .9, kb = Math.min(1, bcv * Math.min(1, bl * 8)) * .8;
      const r = 1 - k + k * Math.min(1, hc.r * 1.4), g = 1 - k + k * Math.min(1, hc.g * 1.4), b = 1 - k + k * Math.min(1, hc.b * 1.4);
      col.setXYZ(i, r * (1 - kb + kb * Math.min(1, bc.r * 1.4)), g * (1 - kb + kb * Math.min(1, bc.g * 1.4)), b * (1 - kb + kb * Math.min(1, bc.b * 1.4)));
    }
    aH.needsUpdate = aC.needsUpdate = col.needsUpdate = true;
  }

  let lastShape = null;
  function apply() {
    if (!geo) return;
    if (lastShape !== state.shape) { deform(); lastShape = state.shape; }
    headMesh.material.color.set(state.skin);
    colorU.hair.value.set(state.hair); colorU.beard.value.set(state.beardColor);
    updateHairAttrs();
  }

  // Modell laden
  const tl = new THREE.TextureLoader();
  new THREE.GLTFLoader().load("model/head.glb", (g) => {
    const src = g.scene.children[0];
    geo = src.geometry;
    base = Float32Array.from(geo.attributes.position.array);
    const n = geo.attributes.position.count;
    geo.setAttribute("aHair", new THREE.BufferAttribute(new Float32Array(n * 4), 4));
    geo.setAttribute("aComb", new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    geo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(n * 3).fill(1), 3));
    const skin = tl.load("model/skin.jpg");
    headMesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ map: skin, vertexColors: true, roughness: .62, metalness: 0 }));
    root.add(headMesh);
    // goldener Barber-Umhang über den Schultern
    const cape = new THREE.Mesh(new THREE.CylinderGeometry(1.6, 4.6, 2.6, 64, 1, true), new THREE.MeshStandardMaterial({ color: 0x8a6d1d, roughness: .35, metalness: .55, side: THREE.DoubleSide }));
    cape.position.set(0, -2.75, -.1); root.add(cape);
    for (let i = 0; i < HAIR_L; i++) { const m = layer(0, (i + 1) / HAIR_L); hairLayers.push(m); root.add(m); }
    for (let i = 0; i < BEARD_L; i++) { const m = layer(1, (i + 1) / BEARD_L); beardLayers.push(m); root.add(m); }
    apply(); ready = true; resize();
    waiting.splice(0).forEach((f) => f());
  });

  /* ---------- Steuerung ---------- */
  let rotY = .45, target = .45, dragging = false, lastX = 0, idle = 0;
  canvas.addEventListener("pointerdown", (e) => { dragging = true; lastX = e.clientX; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener("pointermove", (e) => { if (!dragging) return; target += (e.clientX - lastX) * .012; lastX = e.clientX; idle = 0; });
  canvas.addEventListener("pointerup", () => (dragging = false));
  canvas.addEventListener("pointercancel", () => (dragging = false));
  canvas.style.touchAction = "pan-y";

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    camera.position.z = w / h < .8 ? 9.4 : 8.0;
  }
  addEventListener("resize", resize); resize();

  const vis = AX3D.whenVisible(canvas), clock = new THREE.Clock();
  (function loop() {
    requestAnimationFrame(loop);
    if (!vis.visible || !ready) return;
    const dt = clock.getDelta(); idle += dt;
    if (!dragging && idle > 2.5) target += dt * .3;
    rotY += (target - rotY) * .12;
    root.rotation.y = rotY;
    renderer.render(scene, camera);
  })();

  function snapshot(cfg, angle = .55) {
    const saved = { ...state }, savedRot = root.rotation.y;
    Object.assign(state, cfg); apply();
    root.rotation.y = angle;
    scene.background = new THREE.Color(0x17171b);
    renderer.render(scene, camera);
    const url = canvas.toDataURL("image/jpeg", .85);
    scene.background = null;
    Object.assign(state, saved); apply(); root.rotation.y = savedRot;
    return url;
  }

  return publicApi();

  function publicApi() {
    return {
      STYLES, FADES, BEARDS, SHAPES, SKINS, HAIR_COLORS, RECO, state,
      get ready() { return ready; },
      whenReady(f) { if (ready) f(); else waiting.push(f); },
      set(patch) { Object.assign(state, patch); if (ready) apply(); },
      snapshot: (cfg, angle) => (ready ? snapshot(cfg, angle) : null),
    };
  }
})();
