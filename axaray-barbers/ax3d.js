/* Gemeinsame 3D-Bausteine (Three.js r128) + Startszene */
window.AX3D = (() => {
  if (!window.THREE) return null;

  const glowTex = (() => {
    const c = document.createElement("canvas"); c.width = 4; c.height = 64;
    const g = c.getContext("2d"), grd = g.createLinearGradient(0, 0, 0, 64);
    grd.addColorStop(0, "rgba(255,255,255,0)"); grd.addColorStop(.5, "rgba(255,248,230,1)"); grd.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = grd; g.fillRect(0, 0, 4, 64); return new THREE.CanvasTexture(c);
  })();

  // Waben-Lichtdecke wie im Salon. Fläche: x in [-w/2, w/2], z in [z0, z1]
  function hexCeiling({ w = 18, z0 = -9, z1 = 9, R = 1.1, round = true } = {}) {
    const edges = new Map();
    const key = (a, b) => [a, b].map((p) => `${p.x.toFixed(2)},${p.z.toFixed(2)}`).sort().join("|");
    const qMax = Math.ceil(w / (R * 1.5)), cz = (z0 + z1) / 2, depth = z1 - z0;
    const rMax = Math.ceil(depth / (R * Math.sqrt(3))) + qMax;
    for (let q = -qMax; q <= qMax; q++) for (let r = -rMax; r <= rMax; r++) {
      const x = R * 1.5 * q, z = cz + R * Math.sqrt(3) * (r + q / 2);
      if (Math.abs(x) > w / 2 || z < z0 || z > z1) continue;
      if (round && Math.hypot(x / (w / 2), (z - cz) / (depth / 2)) > 1) continue;
      const v = [...Array(6)].map((_, i) => new THREE.Vector3(x + R * Math.cos(i * Math.PI / 3), 0, z + R * Math.sin(i * Math.PI / 3)));
      for (let i = 0; i < 6; i++) edges.set(key(v[i], v[(i + 1) % 6]), [v[i], v[(i + 1) % 6]]);
    }
    const group = new THREE.Group();
    const bars = new THREE.InstancedMesh(new THREE.BoxGeometry(1, .05, .05), new THREE.MeshBasicMaterial({ color: 0xfffaf0 }), edges.size);
    const glows = new THREE.InstancedMesh(new THREE.PlaneGeometry(1, .35),
      new THREE.MeshBasicMaterial({ map: glowTex, transparent: true, opacity: .35, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }), edges.size);
    const m4 = new THREE.Matrix4(), quat = new THREE.Quaternion(), qFlat = new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2, 0, 0));
    [...edges.values()].forEach(([a, b], i) => {
      const mid = a.clone().add(b).multiplyScalar(.5), len = a.distanceTo(b) * .96;
      quat.setFromAxisAngle(new THREE.Vector3(0, 1, 0), -Math.atan2(b.z - a.z, b.x - a.x));
      m4.compose(mid, quat, new THREE.Vector3(len, 1, 1)); bars.setMatrixAt(i, m4);
      m4.compose(mid, quat.clone().multiply(qFlat), new THREE.Vector3(len, 1, 1)); glows.setMatrixAt(i, m4);
    });
    group.add(bars, glows);
    return group;
  }

  function barberPole() {
    const c = document.createElement("canvas"); c.width = 256; c.height = 256;
    const g = c.getContext("2d"); g.fillStyle = "#f5f2ea"; g.fillRect(0, 0, 256, 256); g.lineWidth = 34;
    [["#c8102e", 0], ["#1f3a93", 128]].forEach(([col, off]) => {
      g.strokeStyle = col;
      for (let k = -2; k < 3; k++) { g.beginPath(); g.moveTo(-40, off + k * 256 + 296); g.lineTo(296, off + k * 256 - 40); g.stroke(); }
    });
    const tex = new THREE.CanvasTexture(c); tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.repeat.set(1, 2);
    const gold = new THREE.MeshStandardMaterial({ color: 0xd4af37, metalness: .9, roughness: .25 });
    const pole = new THREE.Group();
    pole.add(new THREE.Mesh(new THREE.CylinderGeometry(.32, .32, 2.6, 48, 1, true), new THREE.MeshStandardMaterial({ map: tex, roughness: .4, emissive: 0x222222 })));
    pole.add(new THREE.Mesh(new THREE.CylinderGeometry(.38, .38, 2.6, 48, 1, true), new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: .12, roughness: 0 })));
    const cap = new THREE.Mesh(new THREE.SphereGeometry(.42, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), gold);
    const ring = new THREE.Mesh(new THREE.CylinderGeometry(.44, .44, .18, 48), gold);
    const ring2 = ring.clone(), cap2 = cap.clone();
    ring.position.y = 1.38; cap.position.y = 1.47; ring2.position.y = -1.38; cap2.position.y = -1.47; cap2.rotation.x = Math.PI;
    pole.add(ring, cap, ring2, cap2);
    pole.userData.tex = tex;
    return pole;
  }

  function goldDust(n = 260, spread = [18, 10, 10], zOff = -2) {
    const pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { pos[i * 3] = (Math.random() - .5) * spread[0]; pos[i * 3 + 1] = (Math.random() - .5) * spread[1]; pos[i * 3 + 2] = (Math.random() - .5) * spread[2] + zOff; }
    const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    return new THREE.Points(geo, new THREE.PointsMaterial({ color: 0xd4af37, size: .035, transparent: true, opacity: .8 }));
  }

  // Rendert nur, solange das Element sichtbar ist
  function whenVisible(el) {
    const s = { visible: true };
    new IntersectionObserver(([e]) => (s.visible = e.isIntersecting), { rootMargin: "100px" }).observe(el);
    return s;
  }

  function makeRenderer(canvas, opts = {}) {
    try {
      const r = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, ...opts });
      r.setPixelRatio(Math.min(devicePixelRatio, 2));
      return r;
    } catch { return null; }
  }

  return { hexCeiling, barberPole, goldDust, whenVisible, makeRenderer };
})();

/* ---------------- Startszene ---------------- */
(function heroScene() {
  const canvas = document.getElementById("scene");
  if (!window.AX3D || !canvas) return;
  const renderer = AX3D.makeRenderer(canvas);
  if (!renderer) return;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x0b0b0d, 6, 26);
  const camera = new THREE.PerspectiveCamera(60, 1, .1, 100);
  camera.position.set(0, 0, 7);

  const ceiling = AX3D.hexCeiling();
  ceiling.position.set(0, 3.2, -4);
  const pole = AX3D.barberPole();
  const dust = AX3D.goldDust();
  scene.add(ceiling, pole, dust, new THREE.AmbientLight(0xffffff, .55));
  const key = new THREE.PointLight(0xfff3d6, 1.4, 20); key.position.set(0, 3, 2);
  const rim = new THREE.PointLight(0xd4af37, 1.2, 15); rim.position.set(-3, -1, 3);
  scene.add(key, rim);

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    const mobile = w < 760;
    pole.position.set(mobile ? 2.3 : 4.2, mobile ? 3.0 : -.3, 0);
    pole.scale.setScalar(mobile ? .45 : 1);
  }
  addEventListener("resize", resize); resize();

  const target = { x: 0, y: 0 };
  addEventListener("pointermove", (e) => { target.x = e.clientX / innerWidth - .5; target.y = e.clientY / innerHeight - .5; });
  addEventListener("deviceorientation", (e) => {
    if (e.gamma == null) return;
    target.x = Math.max(-.5, Math.min(.5, e.gamma / 60)); target.y = Math.max(-.5, Math.min(.5, (e.beta - 45) / 60));
  });

  const vis = AX3D.whenVisible(canvas), clock = new THREE.Clock();
  (function loop() {
    requestAnimationFrame(loop);
    if (!vis.visible) return;
    const t = reduce ? 0 : clock.getElapsedTime();
    pole.userData.tex.offset.y = -t * .25;
    pole.rotation.z = Math.sin(t * .6) * .05;
    ceiling.rotation.y = t * .04;
    ceiling.rotation.x = .18 + Math.sin(t * .3) * .03;
    dust.rotation.y = t * .02; dust.position.y = Math.sin(t * .4) * .2;
    camera.position.x += (target.x * 1.6 - camera.position.x) * .05;
    camera.position.y += (-target.y * 1.0 - camera.position.y) * .05;
    camera.lookAt(0, .6, -3);
    renderer.render(scene, camera);
  })();
})();
