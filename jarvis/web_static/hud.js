/* JARVIS HUD-Effekte (Version 5.3, Stand 16) – eigene Canvas-Darstellung, keine Bibliothek, kein CDN.
 * Komponenten (über data-hud="…" eingebunden, kein Inline-Skript wegen CSP):
 *   sphere  – Datenkugel aus Ziffern (Startseite), Touchpad: drehen, Pinch = zoomen
 *   portal  – Galaxie-Strudel + Datentunnel beim Betreten des Chats (Klick überspringt)
 *   swirl   – kleiner Strudel in „JARVIS denkt nach“
 *   tunnel  – Datentunnel im Second Brain: Notizen an den Wänden, Touchpad = vor/zurück fliegen
 * Steuerung ohne Konflikt mit dem Seiten-Scrollen: Vor dem ersten Klick reagieren nur Seitwärts-Wischen und
 * Pinch. Nach einem Klick auf die Fläche steuert auch Hoch/Runter, bis die Maus die Fläche verlässt.
 * Texte (Notiztitel) werden nur gezeichnet bzw. per textContent gesetzt.
 */
(function () {
  'use strict';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var CYAN = '79,227,255', ORANGE = '255,159,67';

  function setup(canvas) {
    var ctx = canvas.getContext && canvas.getContext('2d');
    if (!ctx) { return null; }
    var s = { canvas: canvas, ctx: ctx, w: 0, h: 0, dpr: 1 };
    s.resize = function () {
      s.dpr = s.low ? 1 : Math.min(window.devicePixelRatio || 1, 1.5);
      s.w = canvas.clientWidth; s.h = canvas.clientHeight;
      canvas.width = Math.max(1, Math.round(s.w * s.dpr)); canvas.height = Math.max(1, Math.round(s.h * s.dpr));
      ctx.setTransform(s.dpr, 0, 0, s.dpr, 0, 0);
    };
    s.resize();
    window.addEventListener('resize', s.resize);
    // Größe bei jedem Bild prüfen: Zeichenflächen, die beim Start versteckt waren (Größe 0), passen sich so an
    s.check = function () { if (canvas.clientWidth !== s.w || canvas.clientHeight !== s.h) { s.resize(); } return s.w > 0 && s.h > 0; };
    return s;
  }

  function animate(step, s, maxFps) {
    var last = 0, alive = true, visible = true, slow = 0, minGap = maxFps ? 1000 / maxFps - 2 : 0;
    // Stand 17: Nicht sichtbare Flächen (weggescrollt) rechnen nicht. Ist der Rechner zu langsam,
    // schaltet die Darstellung automatisch eine Stufe herunter (s.low = true).
    if (s && window.IntersectionObserver) {
      new IntersectionObserver(function (en) { visible = en[0].isIntersecting; }).observe(s.canvas);
    }
    function frame(t) {
      if (!alive) { return; }
      requestAnimationFrame(frame);
      if (document.hidden || !visible) { last = 0; return; }
      if (s && !s.check()) { return; }                                  // unsichtbar: nichts zeichnen
      if (minGap && last && t - last < minGap) { return; }               // Hintergrund-Effekt: 30 Bilder/s reichen
      var dt = Math.min(0.05, (t - (last || t)) / 1000);
      if (s && last) {
        slow = dt > (minGap ? 0.045 : 0.03) ? slow + 1 : Math.max(0, slow - 1);
        if (slow > 45 && !s.low) { s.low = true; s.resize(); }           // ca. 1,5 s ruckelig → leichter zeichnen
      }
      last = t;
      step(dt, t);
    }
    requestAnimationFrame(frame);
    return function () { alive = false; };
  }

  // Touchpad/Maus: gemeinsame Steuerung mit Trägheit
  function controls(canvas, cam, opt) {
    var active = false, drag = null, idleSince = 0;
    canvas.tabIndex = 0;
    function poke() { idleSince = performance.now(); }
    canvas.addEventListener('pointerdown', function (e) { active = true; drag = [e.clientX, e.clientY, 0]; poke(); canvas.classList.add('hud-active'); });
    canvas.addEventListener('pointermove', function (e) {
      if (!drag) { return; }
      var dx = e.clientX - drag[0], dy = e.clientY - drag[1]; drag[0] = e.clientX; drag[1] = e.clientY; drag[2] += Math.abs(dx) + Math.abs(dy);
      opt.drag(dx, dy); poke();
    });
    window.addEventListener('pointerup', function (e) {
      if (drag && drag[2] < 6 && opt.click && e.target === canvas) { var r = canvas.getBoundingClientRect(); opt.click(e.clientX - r.left, e.clientY - r.top); }
      drag = null;
    });
    canvas.addEventListener('pointerleave', function () { active = false; canvas.classList.remove('hud-active'); });
    canvas.addEventListener('wheel', function (e) {
      var k = e.deltaMode === 1 ? 16 : 1, dx = e.deltaX * k, dy = e.deltaY * k;
      if (e.ctrlKey) { e.preventDefault(); opt.pinch(dy); poke(); return; }
      if (!active && Math.abs(dy) > Math.abs(dx)) { return; }          // Seite normal scrollen lassen
      e.preventDefault(); opt.wheel(dx, dy); poke();
    }, { passive: false });
    canvas.addEventListener('keydown', function (e) {
      var m = { ArrowLeft: [-30, 0], ArrowRight: [30, 0], ArrowUp: [0, -30], ArrowDown: [0, 30] }[e.key];
      if (m) { e.preventDefault(); opt.wheel(m[0], m[1]); poke(); }
      if (e.key === '+' || e.key === '=') { opt.pinch(-40); } if (e.key === '-') { opt.pinch(40); }
    });
    return { idle: function () { return performance.now() - idleSince > 3000; } };
  }

  // ------------------------------------------------------------------ 1. Datenkugel
  function sphere(canvas) {
    var s = setup(canvas); if (!s) { return; }
    var N = 340, pts = [], gold = Math.PI * (3 - Math.sqrt(5));
    for (var i = 0; i < N; i++) {
      var y = 1 - 2 * (i + 0.5) / N, r = Math.sqrt(1 - y * y), a = i * gold;
      pts.push({ x: Math.cos(a) * r, y: y, z: Math.sin(a) * r, d: String(Math.floor(Math.random() * 10)) });
    }
    var cam = { yaw: 0, pitch: 0.25, vy: 0.004, vp: 0, zoom: 1 };
    var c = controls(canvas, cam, {
      drag: function (dx, dy) { cam.vy = dx * 0.002; cam.vp = dy * 0.002; },
      wheel: function (dx, dy) { cam.vy += dx * 0.0004; cam.vp += dy * 0.0003; },
      pinch: function (d) { cam.zoom = Math.max(0.6, Math.min(2.2, cam.zoom * Math.exp(-d * 0.01))); }
    });
    var label = canvas.getAttribute('data-label') || 'JARVIS';
    // Ziffern einmal vorzeichnen (Sprites): drawImage ist viel schneller als fillText bei jedem Bild
    var SPR = 32, sprites = { c: [], w: [] };
    ['c', 'w'].forEach(function (k) {
      for (var d = 0; d < 10; d++) {
        var o = document.createElement('canvas'); o.width = o.height = SPR;
        var x = o.getContext('2d'); x.font = '26px Menlo, Monaco, monospace'; x.textAlign = 'center'; x.textBaseline = 'middle';
        x.fillStyle = k === 'c' ? 'rgb(' + CYAN + ')' : '#e8fbff'; x.fillText(String(d), SPR / 2, SPR / 2 + 1);
        sprites[k].push(o);
      }
    });
    var deco = null;
    function makeDeco(R) {                                             // einmal zeichnen, danach nur kopieren
      var out = { R: Math.round(R) };
      var fs = Math.max(12, Math.round(R * 0.16)), lb = document.createElement('canvas');
      lb.width = Math.ceil(fs * label.length * 0.9 + 60); lb.height = Math.ceil(fs * 2.4);
      var y = lb.getContext('2d');
      y.font = '600 ' + fs + 'px -apple-system, Helvetica, Arial, sans-serif'; y.textAlign = 'center'; y.textBaseline = 'middle';
      y.fillStyle = 'rgba(232,251,255,0.95)'; y.shadowColor = 'rgba(' + CYAN + ',0.9)'; y.shadowBlur = 18;
      y.fillText(label, lb.width / 2, lb.height / 2);
      out.label = lb;
      return out;
    }
    animate(function (dt, t) {
      var ctx = s.ctx, w = s.w, h = s.h, R = Math.min(w, h) * 0.36 * cam.zoom;
      cam.yaw += cam.vy; cam.pitch += cam.vp; cam.vy *= 0.96; cam.vp *= 0.9;
      if (!reduce && c.idle()) { cam.vy += (0.004 - cam.vy) * 0.02; }
      cam.pitch = Math.max(-1.2, Math.min(1.2, cam.pitch));
      if (!reduce && Math.random() < 0.6) { pts[Math.floor(Math.random() * N)].d = String(Math.floor(Math.random() * 10)); }
      ctx.clearRect(0, 0, w, h);                                       // Leuchten dahinter kommt aus CSS (statisch)
      if (!deco || deco.R !== Math.round(R)) { deco = makeDeco(R); }
      var cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw), cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      var step = s.low ? 2 : 1;
      for (var i = 0; i < N; i += step) {
        var p = pts[i], x1 = p.x * cy + p.z * sy, z1 = -p.x * sy + p.z * cy, y2 = p.y * cp - z1 * sp, z2 = p.y * sp + z1 * cp;
        var depth = (z2 + 1) / 2;                                     // 0 hinten … 1 vorne
        var size = (7 + 9 * depth) * 1.25;
        ctx.globalAlpha = 0.15 + 0.85 * depth * depth;
        ctx.drawImage(sprites[depth > 0.85 ? 'w' : 'c'][+p.d], w / 2 + x1 * R - size / 2, h / 2 - y2 * R - size / 2, size, size);
      }
      ctx.globalAlpha = 1;
      // Ringe direkt zeichnen (gemessen schneller als gedrehte Bilder), Schriftzug vorgezeichnet mit Leuchten
      ctx.lineWidth = 1.2;
      for (var k = 0; k < 3; k++) {
        var a0 = (t / (2000 + k * 900)) * (k === 1 ? -1 : 1);
        ctx.strokeStyle = 'rgba(' + (k === 1 ? ORANGE : CYAN) + ',' + (0.5 - k * 0.12) + ')';
        ctx.setLineDash(k === 0 ? [40, 12, 6, 12] : k === 1 ? [3, 9] : [1, 7]);
        ctx.beginPath(); ctx.arc(w / 2, h / 2, R * (1.15 + k * 0.1), a0, a0 + Math.PI * 2); ctx.stroke();
      }
      ctx.setLineDash([]);
      ctx.drawImage(deco.label, w / 2 - deco.label.width / 2, h / 2 - deco.label.height / 2);
    }, s, 30);
  }

  // ------------------------------------------------------------------ 2. Galaxie-Strudel (Portal + Denken)
  function makeStars(n, spread) {
    var a = [];
    for (var i = 0; i < n; i++) { a.push({ ang: Math.random() * Math.PI * 2, r: spread * (0.15 + Math.pow(Math.random(), 0.7)), sp: 0.6 + Math.random() * 1.4, tail: [] }); }
    return a;
  }
  function drawSwirl(s, stars, speed, inward, tilt, alpha) {
    var ctx = s.ctx, w = s.w, h = s.h, cx = w / 2, cy = h / 2;
    ctx.lineCap = 'round';
    var inc = s.low ? 2 : 1;
    for (var i = 0; i < stars.length; i += inc) {
      var st = stars[i], x0 = cx + Math.cos(st.ang) * st.r, y0 = cy + Math.sin(st.ang) * st.r * tilt;
      st.ang += speed * st.sp / Math.max(0.25, st.r / (Math.min(w, h) * 0.5));
      st.r *= (1 - inward);
      if (st.r < 3) { st.r = Math.min(w, h) * (0.5 + Math.random() * 0.4); }
      var x1 = cx + Math.cos(st.ang) * st.r, y1 = cy + Math.sin(st.ang) * st.r * tilt;
      var near = 1 - Math.min(1, st.r / (Math.min(w, h) * 0.6));
      ctx.strokeStyle = 'rgba(' + (i % 7 === 0 ? ORANGE : (near > 0.6 ? '232,251,255' : CYAN)) + ',' + (alpha * (0.35 + 0.65 * near)).toFixed(2) + ')';
      ctx.lineWidth = 0.6 + 1.6 * near;
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
    }
  }
  function swirl(canvas) {
    var s = setup(canvas); if (!s) { return; }
    var stars = makeStars(70, 16);
    animate(function () { s.ctx.clearRect(0, 0, s.w, s.h); drawSwirl(s, stars, reduce ? 0 : 0.09, 0.01, 1, 1); }, s, 30);
  }

  function portal(holder) {
    var css = document.querySelector('.portal');
    if (reduce) { return; }
    var canvas = document.createElement('canvas'); canvas.className = 'portal-canvas'; canvas.setAttribute('aria-hidden', 'true');
    document.body.appendChild(canvas);
    if (css) { css.style.display = 'none'; }
    var s = setup(canvas); if (!s) { return; }
    var stars = makeStars(520, Math.max(s.w, s.h) * 0.75), start = performance.now(), lines = [];
    for (var i = 0; i < 160; i++) { lines.push({ x: (Math.random() - 0.5) * 6, y: (Math.random() - 0.5) * 4, z: Math.random() * 12 + 1 }); }
    var finished = false;
    function end() { if (finished) { return; } finished = true; canvas.classList.add('portal-out'); setTimeout(function () { stop(); canvas.remove(); }, 450); }
    canvas.addEventListener('click', end);
    var stop = animate(function (dt) {
      var t = (performance.now() - start) / 1000, ctx = s.ctx, w = s.w, h = s.h;
      ctx.fillStyle = 'rgba(3,8,14,0.35)'; ctx.fillRect(0, 0, w, h);          // Nachleuchten = Lichtschweife
      if (t < 1.0) {                                                            // Phase 1: Galaxie zieht sich zusammen
        drawSwirl(s, stars, 0.02 + t * 0.06, 0.004 + t * 0.03, 0.55 + t * 0.45, Math.min(1, t * 2.5));
      } else {                                                                  // Phase 2: Durchflug Datentunnel
        var f = Math.min(w, h) * 0.6, sp = 14 + (t - 1) * 30;
        ctx.lineWidth = 1.2;
        for (var i = 0; i < lines.length; i++) {
          var L = lines[i], z0 = L.z; L.z -= sp * dt;
          if (L.z < 0.2) { L.z += 12; continue; }
          var xa = w / 2 + L.x * f / z0, ya = h / 2 + L.y * f / z0, xb = w / 2 + L.x * f / L.z, yb = h / 2 + L.y * f / L.z;
          ctx.strokeStyle = 'rgba(' + (i % 9 === 0 ? ORANGE : CYAN) + ',' + Math.min(1, 1.6 / L.z).toFixed(2) + ')';
          ctx.beginPath(); ctx.moveTo(xa, ya); ctx.lineTo(xb, yb); ctx.stroke();
          if (i % 4 === 0) { ctx.fillStyle = '#e8fbff'; ctx.fillRect(xb - 1.5, yb - 1.5, 3, 3); }
        }
      }
      if (t > 1.7) { end(); }
    }, s);
  }

  // ------------------------------------------------------------------ 3. Datentunnel (Second Brain)
  var KIND = { notiz: '159,220,255', aufgabe: '255,209,102', lektion: '199,146,234', recherche: ORANGE, strategie: '255,107,203' };
  function tunnel(canvas) {
    var s = setup(canvas); if (!s) { return; }
    var tip = canvas.parentNode.querySelector('.b3-tip');
    var W2 = 1.6, H2 = 1.0, SEG = 1.4, segs = 60, traces = [], items = [], camZ = 0, vz = 0.6, look = { x: 0, y: 0 }, hover = null, shown = [];
    for (var i = 0; i < segs; i++) {                              // Leiterbahnen an den Wänden
      var z = i * SEG, wall = i % 4, n = 2 + (i % 3);
      for (var k = 0; k < n; k++) {
        var u = (Math.random() - 0.5) * 1.8, len = 0.3 + Math.random() * 1.2, pts = [];
        var a = wall < 2 ? [wall ? W2 : -W2, u * H2, z] : [u * W2, wall === 2 ? H2 : -H2, z];
        pts.push(a.slice());
        a[2] += len; pts.push(a.slice());
        if (wall < 2) { a[1] += (Math.random() - 0.5) * 0.6; } else { a[0] += (Math.random() - 0.5) * 0.8; }
        pts.push(a.slice());
        traces.push(pts);
      }
    }
    function proj(x, y, z) {
      var d = z - camZ; if (d < 0.08) { return null; }
      var f = Math.min(s.w, s.h) * 0.75;
      return { x: s.w / 2 + (x - look.x) * f / d, y: s.h / 2 - (y - look.y) * f / d, d: d, k: f / d };
    }
    var c = controls(canvas, null, {
      drag: function (dx, dy) { look.x = Math.max(-0.8, Math.min(0.8, look.x - dx * 0.003)); look.y = Math.max(-0.5, Math.min(0.5, look.y + dy * 0.003)); },
      wheel: function (dx, dy) { vz += dy * 0.0025; look.x = Math.max(-0.8, Math.min(0.8, look.x + dx * 0.002)); },
      pinch: function (d) { vz -= d * 0.004; },
      click: function (mx, my) { var hit = pick(mx, my); if (hit && hit.url) { window.location.href = hit.url; } }
    });
    function pick(mx, my) {
      for (var i = shown.length - 1; i >= 0; i--) { var p = shown[i]; if (Math.abs(p.x - mx) < p.r + 6 && Math.abs(p.y - my) < p.r + 6) { return p.item; } }
      return null;
    }
    canvas.addEventListener('mousemove', function (e) {
      var r = canvas.getBoundingClientRect(), hit = pick(e.clientX - r.left, e.clientY - r.top);
      hover = hit; canvas.style.cursor = hit ? 'pointer' : 'grab';
      if (!tip) { return; }
      if (!hit) { tip.hidden = true; return; }
      tip.textContent = ''; var b = document.createElement('b'); b.textContent = hit.title; tip.appendChild(b);
      var sp = document.createElement('span'); sp.textContent = hit.sub; tip.appendChild(sp);
      tip.style.left = Math.min(s.w - 220, e.clientX - r.left + 14) + 'px'; tip.style.top = (e.clientY - r.top - 10) + 'px'; tip.hidden = false;
    });
    var LEN = segs * SEG;
    fetch(canvas.getAttribute('data-src'), { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) { return r.ok ? r.json() : { notes: [] }; })
      .then(function (data) {
        (data.notes || []).slice(0, 120).forEach(function (n, i) {
          var wall = i % 4, z = 3 + i * (LEN - 6) / Math.max(1, Math.min(120, data.notes.length)), u = ((i * 37) % 10) / 10 - 0.45;
          var pos = wall < 2 ? [wall ? W2 * 0.92 : -W2 * 0.92, u * H2 * 1.4, z] : [u * W2 * 1.4, wall === 2 ? H2 * 0.9 : -H2 * 0.9, z];
          items.push({ p: pos, title: n.title, sub: ({ notiz: 'Notiz', aufgabe: 'Aufgabe', lektion: 'Lektion', recherche: 'Recherche', strategie: 'Strategie' })[n.kind] || 'Notiz',
            color: KIND[n.kind] || KIND.notiz, url: '/wissen/notiz?id=' + encodeURIComponent(n.id) });
        });
      });
    animate(function (dt, t) {
      var ctx = s.ctx, w = s.w, h = s.h;
      if (!reduce && c.idle()) { vz += (0.6 - vz) * 0.02; }
      vz = Math.max(-6, Math.min(8, vz)) * 0.985;
      camZ += vz * dt * (reduce ? 0 : 1);
      if (camZ > LEN - 8) { camZ = 0; } if (camZ < 0) { camZ = LEN - 8; }
      ctx.fillStyle = 'rgba(3,8,14,0.55)'; ctx.fillRect(0, 0, w, h);
      // Rahmen der Tunnelsegmente
      for (var i = 0; i < segs; i++) {
        var z = i * SEG; if (z < camZ || z > camZ + 24) { continue; }
        var a = proj(-W2, H2, z), b = proj(W2, -H2, z); if (!a || !b) { continue; }
        ctx.strokeStyle = 'rgba(' + CYAN + ',' + Math.min(0.35, 2.5 / (z - camZ + 1)).toFixed(2) + ')'; ctx.lineWidth = 1;
        ctx.strokeRect(a.x, a.y, b.x - a.x, b.y - a.y);
      }
      // Leiterbahnen
      ctx.lineWidth = 1;
      for (i = 0; i < traces.length; i += (s.low ? 2 : 1)) {
        var tr = traces[i]; if (tr[0][2] < camZ - 1 || tr[0][2] > camZ + 22) { continue; }
        var p0 = proj(tr[0][0], tr[0][1], tr[0][2]), p1 = proj(tr[1][0], tr[1][1], tr[1][2]), p2 = proj(tr[2][0], tr[2][1], tr[2][2]);
        if (!p0 || !p1 || !p2) { continue; }
        var al = Math.min(0.85, 3 / p0.d);
        ctx.strokeStyle = 'rgba(' + (i % 11 === 0 ? ORANGE : CYAN) + ',' + al.toFixed(2) + ')';
        ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.lineTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
        ctx.fillStyle = 'rgba(232,251,255,' + al.toFixed(2) + ')'; ctx.beginPath(); ctx.arc(p2.x, p2.y, Math.max(1, 0.02 * p2.k), 0, 6.283); ctx.fill();
      }
      // Notizen an den Wänden
      shown = [];
      for (i = items.length - 1; i >= 0; i--) {
        var it = items[i], q = proj(it.p[0], it.p[1], it.p[2]); if (!q || q.d > 20) { continue; }
        var r = Math.max(2, Math.min(14, 0.05 * q.k)), A = Math.min(1, 4 / q.d);
        ctx.fillStyle = 'rgba(' + it.color + ',' + (A * 0.25).toFixed(2) + ')'; ctx.beginPath(); ctx.arc(q.x, q.y, r * 2.4, 0, 6.283); ctx.fill();
        ctx.fillStyle = 'rgba(' + it.color + ',' + A.toFixed(2) + ')'; ctx.beginPath(); ctx.arc(q.x, q.y, r, 0, 6.283); ctx.fill();
        if (q.d < 7 || hover === it) {
          ctx.font = Math.round(Math.max(10, Math.min(16, r * 1.3))) + 'px -apple-system, Helvetica, Arial, sans-serif';
          ctx.textAlign = 'center'; ctx.fillStyle = 'rgba(232,251,255,' + Math.min(1, A * 1.2).toFixed(2) + ')';
          ctx.fillText(it.title.length > 40 ? it.title.slice(0, 39) + '…' : it.title, q.x, q.y + r + 14);
        }
        if (hover === it) { ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(q.x, q.y, r + 5, 0, 6.283); ctx.stroke(); }
        shown.push({ x: q.x, y: q.y, r: r, item: it });
      }
      // Fluchtpunkt-Leuchten
      var g = ctx.createRadialGradient(w / 2, h / 2, 2, w / 2, h / 2, Math.min(w, h) * 0.25);
      g.addColorStop(0, 'rgba(' + CYAN + ',0.18)'); g.addColorStop(1, 'rgba(' + CYAN + ',0)'); ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
    }, s);
  }

  // ------------------------------------------------------------------ Start
  function boot() {
    Array.prototype.forEach.call(document.querySelectorAll('canvas[data-hud]'), function (c) {
      var kind = c.getAttribute('data-hud');
      c.parentNode.classList.add('hud-on');
      try {
        if (kind === 'sphere') { sphere(c); } else if (kind === 'swirl') { swirl(c); } else if (kind === 'tunnel') { tunnel(c); }
      } catch (e) { c.parentNode.classList.remove('hud-on'); /* bei Fehlern bleibt die einfache Ansicht */ }
    });
    if (document.body.classList.contains('portal-on')) { try { portal(); } catch (e) { /* CSS-Portal bleibt */ } }
    // Second Brain: Ansicht Gehirn / Datentunnel
    var sw = document.querySelector('.view-switch');
    if (sw) {
      sw.hidden = false;
      var stage = sw.parentNode;
      Array.prototype.forEach.call(sw.querySelectorAll('button[data-view]'), function (b) {
        b.addEventListener('click', function () {
          var tunnelView = b.getAttribute('data-view') === 'tunnel';
          stage.classList.toggle('show-tunnel', tunnelView);
          Array.prototype.forEach.call(sw.querySelectorAll('button'), function (x) { x.setAttribute('aria-pressed', String(x === b)); });
          window.dispatchEvent(new Event('resize'));          // Zeichenfläche an die neue Größe anpassen
        });
      });
    }
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', boot); } else { boot(); }
})();
