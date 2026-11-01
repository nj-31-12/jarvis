/* JARVIS-Kern (Stand 23) – das 3D-Objekt der Sprach-Ansicht und der Auftrags-Zentrale.
 * Anders als die Ziffern-Kugel: ein flüssiger Plasma-Kern aus Lichtpunkten, der sich mit der Stimme verformt,
 * umkreist von drei Kreisel-Ringen und Funken. Farbe je nach Zustand:
 *   ruhe = Eisblau · zuhoeren = Türkis · denken = Violett (dreht schneller) · sprechen = Gold-Weiß (pulsiert zur Stimme)
 * Eigene Canvas-Darstellung, keine Bibliothek. Spart Rechenzeit: 30 Bilder/s, pausiert unsichtbar, reduziert bei Ruckeln.
 * Benutzung: var orb = JarvisOrb(canvas); orb.mode('sprechen'); orb.level(0..1);
 */
(function () {
  'use strict';
  var COLORS = { ruhe: [110, 180, 255], zuhoeren: [70, 240, 205], denken: [175, 125, 255], sprechen: [255, 205, 125] };

  function JarvisOrb(canvas) {
    var ctx = canvas.getContext && canvas.getContext('2d');
    if (!ctx) { return { mode: function () {}, level: function () {} }; }
    var w = 0, h = 0, dpr = 1, low = false, N = 900, pts = [], sparks = [], i;
    var state = 'ruhe', target = 0, lvl = 0, col = COLORS.ruhe.slice(), spin = 0, visible = true, last = 0, slow = 0;
    for (i = 0; i < N; i++) {                                   // gleichmäßig verteilte Punkte (Fibonacci-Kugel)
      var y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(1 - y * y), a = i * 2.399963;
      pts.push([Math.cos(a) * r, y, Math.sin(a) * r, Math.random() * 6.28]);
    }
    var glow = document.createElement('canvas'); glow.width = glow.height = 32;
    function makeGlow() {
      var g = glow.getContext('2d'), grd = g.createRadialGradient(16, 16, 0, 16, 16, 16);
      grd.addColorStop(0, 'rgba(255,255,255,1)'); grd.addColorStop(0.25, 'rgba(' + col.map(Math.round).join(',') + ',0.85)');
      grd.addColorStop(1, 'rgba(0,0,0,0)'); g.clearRect(0, 0, 32, 32); g.fillStyle = grd; g.fillRect(0, 0, 32, 32);
    }
    makeGlow();
    function resize() {
      dpr = low ? 1 : Math.min(window.devicePixelRatio || 1, 1.5);
      w = canvas.clientWidth; h = canvas.clientHeight;
      canvas.width = Math.max(1, Math.round(w * dpr)); canvas.height = Math.max(1, Math.round(h * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize(); window.addEventListener('resize', resize);
    if (window.IntersectionObserver) { new IntersectionObserver(function (e) { visible = e[0].isIntersecting; }).observe(canvas); }

    function ring(cx, cy, R, tiltX, tiltZ, rot, alpha, dash) {
      ctx.beginPath();
      for (var k = 0; k <= 72; k++) {
        var t = k / 72 * Math.PI * 2 + rot, x = Math.cos(t) * R, y = 0, z = Math.sin(t) * R;
        var y2 = y * Math.cos(tiltX) - z * Math.sin(tiltX), z2 = y * Math.sin(tiltX) + z * Math.cos(tiltX);
        var x3 = x * Math.cos(tiltZ) - y2 * Math.sin(tiltZ), y3 = x * Math.sin(tiltZ) + y2 * Math.cos(tiltZ);
        var f = 3 / (3 + z2 / R * 0.6);
        if (dash && k % 6 > 3) { ctx.moveTo(cx + x3 * f, cy + y3 * f); } else if (k === 0) { ctx.moveTo(cx + x3 * f, cy + y3 * f); } else { ctx.lineTo(cx + x3 * f, cy + y3 * f); }
      }
      ctx.strokeStyle = 'rgba(' + col.map(Math.round).join(',') + ',' + alpha + ')';
      ctx.stroke();
    }

    function frame(t) {
      requestAnimationFrame(frame);
      if (document.hidden || !visible) { last = 0; return; }
      if (canvas.clientWidth !== w || canvas.clientHeight !== h) { resize(); }
      if (!w || !h) { return; }
      if (last && t - last < 31) { return; }
      var dt = Math.min(0.05, (t - (last || t)) / 1000);
      if (last) { slow = dt > 0.045 ? slow + 1 : Math.max(0, slow - 1); if (slow > 40 && !low) { low = true; N = 520; resize(); } }
      last = t;
      var goal = COLORS[state] || COLORS.ruhe, changed = false;
      for (var c = 0; c < 3; c++) { var d = goal[c] - col[c]; if (Math.abs(d) > 0.5) { col[c] += d * 0.08; changed = true; } }
      if (changed) { makeGlow(); }
      var idle = state === 'ruhe' ? 0.06 + Math.sin(t / 900) * 0.04 : state === 'denken' ? 0.25 + Math.sin(t / 160) * 0.1 : 0.08;
      lvl += (Math.max(target, idle) - lvl) * (target > lvl ? 0.5 : 0.12);
      spin += dt * (state === 'denken' ? 1.6 : 0.35 + lvl * 1.2);
      var cx = w / 2, cy = h / 2, R = Math.min(w, h) * 0.26, time = t / 1000, rgb = col.map(Math.round).join(',');
      ctx.clearRect(0, 0, w, h);
      // Hof um den Kern
      var halo = ctx.createRadialGradient(cx, cy, R * 0.2, cx, cy, R * (1.9 + lvl));
      halo.addColorStop(0, 'rgba(' + rgb + ',' + (0.22 + lvl * 0.35).toFixed(3) + ')'); halo.addColorStop(1, 'rgba(' + rgb + ',0)');
      ctx.fillStyle = halo; ctx.fillRect(0, 0, w, h);
      ctx.globalCompositeOperation = 'lighter';
      var cyS = Math.cos(spin), syS = Math.sin(spin), tilt = 0.4 + Math.sin(time * 0.3) * 0.15, ct = Math.cos(tilt), st = Math.sin(tilt);
      var amp = 0.05 + lvl * 0.32, size = low ? 6 : 8;
      for (i = 0; i < N; i++) {
        var p = pts[i];
        // Verformung: überlagerte Wellen (wirkt wie flüssiges Plasma), stärker bei lauter Stimme
        var n = Math.sin(p[0] * 3.1 + time * 2.2) * Math.cos(p[1] * 2.7 - time * 1.7) + Math.sin(p[2] * 3.7 + time * 1.3 + p[3]) * 0.5;
        var k = 1 + n * amp, x = p[0] * k, y = p[1] * k, z = p[2] * k;
        var x2 = x * cyS - z * syS, z2 = x * syS + z * cyS, y2 = y * ct - z2 * st; z2 = y * st + z2 * ct;
        var f = 2.4 / (2.4 + z2), px = cx + x2 * R * f, py = cy + y2 * R * f, depth = (1.2 - z2) / 2.2;
        ctx.globalAlpha = Math.max(0.06, Math.min(1, depth * (0.55 + lvl * 0.6)));
        var s = size * f * (0.6 + Math.max(0, n) * lvl);
        ctx.drawImage(glow, px - s / 2, py - s / 2, s, s);
      }
      ctx.globalAlpha = 1;
      // Kern
      var core = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * (0.55 + lvl * 0.25));
      core.addColorStop(0, 'rgba(255,255,255,' + (0.55 + lvl * 0.4).toFixed(3) + ')'); core.addColorStop(0.35, 'rgba(' + rgb + ',0.35)'); core.addColorStop(1, 'rgba(' + rgb + ',0)');
      ctx.fillStyle = core; ctx.beginPath(); ctx.arc(cx, cy, R * (0.6 + lvl * 0.3), 0, Math.PI * 2); ctx.fill();
      // Kreisel-Ringe
      ctx.lineWidth = 1.2;
      ring(cx, cy, R * 1.45, 1.2, 0.3, spin * 0.7, 0.35 + lvl * 0.3, false);
      ring(cx, cy, R * 1.62, 1.35, -0.6, -spin * 0.5, 0.22 + lvl * 0.25, true);
      ring(cx, cy, R * 1.25, 0.25 + Math.sin(time * 0.4) * 0.2, 1.1, spin, 0.18 + lvl * 0.3, true);
      // Funken beim Sprechen
      if (!low && lvl > 0.25 && sparks.length < 60 && Math.random() < lvl) {
        var ang = Math.random() * 6.283; sparks.push({ x: Math.cos(ang), y: Math.sin(ang), v: 0.6 + Math.random() * 0.8, life: 1 });
      }
      for (i = sparks.length - 1; i >= 0; i--) {
        var sp = sparks[i]; sp.life -= dt * 1.2;
        if (sp.life <= 0) { sparks.splice(i, 1); continue; }
        var dist = R * (1 + (1 - sp.life) * 1.3 * sp.v);
        ctx.globalAlpha = sp.life * 0.9; ctx.drawImage(glow, cx + sp.x * dist - 4, cy + sp.y * dist - 4, 8, 8);
      }
      ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    }
    canvas.parentNode.classList.add('orb-on');
    requestAnimationFrame(frame);
    return {
      mode: function (m) { if (COLORS[m]) { state = m; canvas.setAttribute('data-mode', m); } },
      level: function (v) { target = Math.max(0, Math.min(1, +v || 0)); }
    };
  }
  window.JarvisOrb = JarvisOrb;

  // Gemeinsamer Sprecher: Mac-Stimme (WAV vom JARVIS-Server) → Lautstärke steuert den Kern.
  // Geht das nicht (kein Mac, Ton blockiert), liest der Browser selbst vor und der Kern pulsiert gleichmäßig.
  var actx = null, current = null, fakeTimer = null;
  function browserVoice(text, orb, done) {
    if (!window.speechSynthesis || !window.SpeechSynthesisUtterance || !text) { done(); return; }
    var u = new SpeechSynthesisUtterance(text), pick = null;
    u.lang = 'de-DE'; u.rate = 0.95; u.pitch = 0.5;
    window.speechSynthesis.getVoices().forEach(function (v) { if (!pick && v.lang && v.lang.indexOf('de') === 0) { pick = v; } });
    if (pick) { u.voice = pick; }
    var ph = 0;
    fakeTimer = setInterval(function () { ph += 0.7; orb.level(0.35 + Math.abs(Math.sin(ph)) * 0.45 * Math.random()); }, 90);
    u.onend = u.onerror = function () { clearInterval(fakeTimer); orb.level(0); done(); };
    window.speechSynthesis.speak(u);
  }
  function stopSpeaking() {
    if (current) { try { current.pause(); } catch (e) { /* egal */ } current = null; }
    if (fakeTimer) { clearInterval(fakeTimer); fakeTimer = null; }
    if (window.speechSynthesis) { window.speechSynthesis.cancel(); }
  }
  function speak(url, text, orb, done) {
    done = done || function () {};
    stopSpeaking();
    orb.mode('sprechen');
    var finished = false, fell = false, a = new Audio(url);
    function end() { if (finished) { return; } finished = true; current = null; orb.level(0); orb.mode('ruhe'); done(); }
    current = a;
    try {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (AC) {
        actx = actx || new AC();
        if (actx.state === 'suspended' && actx.resume) { actx.resume(); }
        var src = actx.createMediaElementSource(a), an = actx.createAnalyser(), buf;
        an.fftSize = 512; buf = new Uint8Array(an.fftSize);
        src.connect(an); an.connect(actx.destination);
        (function meter() {
          if (finished) { return; }
          an.getByteTimeDomainData(buf);
          var sum = 0; for (var i = 0; i < buf.length; i++) { var v = (buf[i] - 128) / 128; sum += v * v; }
          orb.level(Math.min(1, Math.sqrt(sum / buf.length) * 4.5));
          requestAnimationFrame(meter);
        })();
      }
    } catch (e) { /* ohne Messung: Kern pulsiert trotzdem */ }
    a.onended = end;
    a.onerror = function () { if (finished || fell) { return; } fell = true; current = null; browserVoice(text, orb, function () { finished = true; orb.mode('ruhe'); done(); }); };
    var p = a.play();
    if (p && p.catch) { p.catch(function () { a.onerror(); }); }
  }
  window.JarvisSpeak = { speak: speak, stop: stopSpeaking };
})();
