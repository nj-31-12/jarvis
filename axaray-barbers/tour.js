/* Virtueller Rundgang: Scrollen = durch den Salon laufen.
 * Die Fotos hängen als Bilder links/rechts im Gang, am Ende stehen die drei Plätze der Barber.
 */
(function tour() {
  const C = window.CONFIG, sec = document.getElementById("rundgang"), canvas = document.getElementById("tourCanvas");
  const stops = [
    { title: "Willkommen bei Axaray", text: "Hauptstraße 118 in Hösbach – nur ca. 10 Minuten von Aschaffenburg. Komm rein!" },
    ...C.tour.map((t) => ({ title: t.title, text: t.text })),
    { title: "Die drei Plätze", text: "Jeder Platz hat seinen Barber. Weiter scrollen, um sie kennenzulernen.", final: true },
  ];
  const K = stops.length;

  const fallback = () => {
    sec.classList.add("no-3d");
    const fb = document.getElementById("tourFallback"); fb.hidden = false;
    fb.innerHTML = C.tour.map((t) => `<figure><img src="${t.img}" alt="${t.title}" loading="lazy"><figcaption><b>${t.title}</b>${t.text}</figcaption></figure>`).join("") +
      `<figure class="fb-plaetze">${C.barbers.map((b) => `<img src="${b.img}" alt="${b.name}" loading="lazy">`).join("")}<figcaption><b>Die drei Plätze</b>Jeder Platz hat seinen Barber.</figcaption></figure>`;
  };
  if (!window.AX3D || !canvas) return fallback();
  const renderer = AX3D.makeRenderer(canvas);
  if (!renderer) return fallback();

  sec.style.height = `${K * 85 + 30}vh`;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0b0d);
  scene.fog = new THREE.Fog(0x0b0b0d, 7, 24);
  const camera = new THREE.PerspectiveCamera(62, 1, .1, 80);
  const loader = new THREE.TextureLoader();
  const world = new THREE.Group(); scene.add(world);
  let keys = [];

  // Text als Textur (für Schilder im Raum)
  function label(text, w = 512, h = 128, size = 64) {
    const c = document.createElement("canvas"); c.width = w; c.height = h;
    const g = c.getContext("2d"); g.fillStyle = "#d4af37"; g.font = `700 ${size}px Cinzel, Georgia, serif`;
    g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(text, w / 2, h / 2);
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w / h, 1), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), transparent: true }));
    return m;
  }
  const gold = new THREE.MeshStandardMaterial({ color: 0xd4af37, metalness: .85, roughness: .3 });
  function photo(src, height) {
    const g = new THREE.Group();
    const frame = new THREE.Mesh(new THREE.BoxGeometry(1, 1, .06), gold);
    const pic = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ color: 0x222222 }));
    pic.position.z = .035; g.add(frame, pic);
    const setAspect = (a) => { pic.scale.set(height * a, height, 1); frame.scale.set(height * a + .1, height + .1, 1); };
    setAspect(.75);
    loader.load(src, (t) => { t.minFilter = THREE.LinearFilter; pic.material = new THREE.MeshBasicMaterial({ map: t }); setAspect(t.image.width / t.image.height); });
    return g;
  }
  const floorTex = (() => {
    const c = document.createElement("canvas"); c.width = 256; c.height = 128; const g = c.getContext("2d");
    g.fillStyle = "#2a2a2e"; g.fillRect(0, 0, 256, 128);
    g.strokeStyle = "#151517"; g.lineWidth = 4; g.strokeRect(0, 0, 256, 128);
    for (let i = 0; i < 400; i++) { g.fillStyle = `rgba(255,255,255,${Math.random() * .03})`; g.fillRect(Math.random() * 256, Math.random() * 128, 2, 2); }
    const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
  })();

  function build(mobile) {
    world.clear();
    const Wx = mobile ? 1.2 : 2.3, ph = mobile ? 1.65 : 2.3, gap = mobile ? 6.5 : 7.5, D = mobile ? 3.2 : 3.6;
    const halfW = Wx + (mobile ? 1.1 : 1.7);
    const zWall = -6 - C.tour.length * gap - 4;
    const len = 12 - zWall;
    const floorY = -1.6, ceilY = 2.7;

    const floor = new THREE.Mesh(new THREE.PlaneGeometry(halfW * 2, len), new THREE.MeshStandardMaterial({ map: floorTex, roughness: .45, metalness: .25 }));
    floorTex.repeat.set(halfW * 2 / 1.2, len / .6);
    floor.rotation.x = -Math.PI / 2; floor.position.set(0, floorY, 6 - len / 2); world.add(floor);
    const wallMat = new THREE.MeshStandardMaterial({ color: 0x1b1b20, roughness: .9 });
    [-1, 1].forEach((s) => {
      const w = new THREE.Mesh(new THREE.PlaneGeometry(len, ceilY - floorY), wallMat);
      w.rotation.y = -s * Math.PI / 2; w.position.set(s * halfW, (ceilY + floorY) / 2, 6 - len / 2); world.add(w);
      // goldene Sockelleiste
      const strip = new THREE.Mesh(new THREE.BoxGeometry(.03, .04, len), gold); strip.position.set(s * (halfW - .02), floorY + .35, 6 - len / 2); world.add(strip);
    });
    const ceil = new THREE.Mesh(new THREE.PlaneGeometry(halfW * 2, len), new THREE.MeshBasicMaterial({ color: 0x0e0e11 }));
    ceil.rotation.x = Math.PI / 2; ceil.position.set(0, ceilY + .05, 6 - len / 2); world.add(ceil);
    const hex = AX3D.hexCeiling({ w: halfW * 2 - .3, z0: zWall + .5, z1: 6, R: mobile ? .8 : 1.0, round: false });
    hex.position.y = ceilY; world.add(hex);

    // Eingang: Schriftzug über der Tür
    const sign = label("AXARAY BARBERS", 1024, 128, 76); sign.scale.setScalar(mobile ? .5 : .7); sign.position.set(0, ceilY - .45, 2); world.add(sign);
    const poleL = AX3D.barberPole(); poleL.scale.setScalar(.45); poleL.position.set(-halfW + .35, .6, 2.2); world.add(poleL);
    world.userData.pole = poleL;

    keys = [{ cam: new THREE.Vector3(0, .25, 7.5), look: new THREE.Vector3(0, .3, -6) }];
    C.tour.forEach((t, i) => {
      const s = i % 2 ? 1 : -1, z = -4 - i * gap, x = s * Wx;
      const p = photo(t.img, ph); p.position.set(x, .35, z); p.rotation.y = -s * (mobile ? .5 : .62); world.add(p);
      const lbl = label(String(i + 1).padStart(2, "0"), 256, 128, 72); lbl.scale.setScalar(.35); lbl.position.set(x, .35 + ph / 2 + .32, z); lbl.rotation.y = p.rotation.y; world.add(lbl);
      const lamp = new THREE.PointLight(0xfff3d6, .7, 9); lamp.position.set(x * .5, ceilY - .4, z + 1); world.add(lamp);
      keys.push({ cam: new THREE.Vector3(x * .15, .3, z + D), look: new THREE.Vector3(x * .92, .35, z) });
    });

    // Rückwand mit den drei Plätzen
    const back = new THREE.Mesh(new THREE.PlaneGeometry(halfW * 2, ceilY - floorY), wallMat);
    back.position.set(0, (ceilY + floorY) / 2, zWall - .1); world.add(back);
    const sp = mobile ? .78 : 1.55, sh = mobile ? 1.25 : 2.2;
    C.barbers.forEach((b, i) => {
      const x = (i - 1) * sp;
      const p = photo(b.img, sh); p.position.set(x, .2, zWall); world.add(p);
      const l = label(`PLATZ ${i + 1}`, 512, 128, 64); l.scale.setScalar(mobile ? .2 : .3); l.position.set(x, .2 + sh / 2 + .22, zWall + .02); world.add(l);
    });
    const spot = new THREE.PointLight(0xfff3d6, 1.1, 10); spot.position.set(0, 1.8, zWall + 3); world.add(spot);
    keys.push({ cam: new THREE.Vector3(0, .25, zWall + (mobile ? 4.8 : 3.9)), look: new THREE.Vector3(0, .2, zWall) });

    world.add(new THREE.AmbientLight(0xffffff, .42));
    const dust = AX3D.goldDust(220, [halfW * 2, 4, len], 6 - len / 2); world.add(dust);
  }

  const capEl = document.getElementById("tourCaption"), numEl = document.getElementById("tourNum"),
    titleEl = document.getElementById("tourTitle"), textEl = document.getElementById("tourText"),
    barEl = document.getElementById("tourBar"), hintEl = document.getElementById("tourHint"), dotsEl = document.getElementById("tourDots");
  dotsEl.innerHTML = stops.map((s, i) => `<button type="button" aria-label="${s.title}" data-i="${i}"></button>`).join("");
  const range = () => sec.offsetHeight - innerHeight;
  dotsEl.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    scrollTo({ top: sec.offsetTop + (+b.dataset.i / (K - 1)) * range(), behavior: "smooth" });
  });

  let mobile = null;
  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    const m = w < 760; if (m !== mobile) { mobile = m; build(m); }
  }
  addEventListener("resize", resize); resize();

  const ease = (t) => { t = Math.max(0, Math.min(1, (t - .12) / .76)); return t * t * (3 - 2 * t); };
  let active = -1;
  const cam = new THREE.Vector3(), look = new THREE.Vector3(), tmpL = new THREE.Vector3();
  const sway = { x: 0, y: 0 };
  addEventListener("pointermove", (e) => { sway.x = e.clientX / innerWidth - .5; sway.y = e.clientY / innerHeight - .5; });

  const vis = AX3D.whenVisible(sec), clock = new THREE.Clock();
  (function loop() {
    requestAnimationFrame(loop);
    if (!vis.visible) return;
    const p = Math.max(0, Math.min(1, (scrollY - sec.offsetTop) / range()));
    const f = p * (K - 1), i = Math.min(K - 2, Math.floor(f)), t = ease(f - i);
    cam.lerpVectors(keys[i].cam, keys[i + 1].cam, t);
    tmpL.lerpVectors(keys[i].look, keys[i + 1].look, t);
    const tt = clock.getElapsedTime();
    camera.position.set(cam.x + sway.x * .25, cam.y - sway.y * .15 + Math.sin(tt * 1.4) * .015, cam.z);
    look.lerp(tmpL, .2); camera.lookAt(look);
    const poleTex = world.userData.pole?.userData.tex; if (poleTex) poleTex.offset.y = -tt * .25;
    renderer.render(scene, camera);

    const a = Math.round(f);
    if (a !== active) {
      active = a; const s = stops[a];
      capEl.classList.remove("show"); void capEl.offsetWidth; capEl.classList.add("show");
      numEl.textContent = `${String(a + 1).padStart(2, "0")} / ${String(K).padStart(2, "0")}`;
      titleEl.textContent = s.title; textEl.textContent = s.text;
      capEl.classList.toggle("final", !!s.final);
      [...dotsEl.children].forEach((d, k) => d.classList.toggle("on", k === a));
    }
    barEl.style.width = `${p * 100}%`;
    hintEl.style.opacity = p > .02 ? 0 : 1;
  })();
  look.copy(keys[0].look);
})();
