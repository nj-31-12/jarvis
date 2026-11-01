/* JARVIS Second Brain – 3D-Gehirn (Version 5.3)
 * Eigene, kleine 3D-Darstellung auf <canvas>: keine Bibliothek, kein CDN, kein Inline-Skript (strenge CSP).
 * Daten: /gehirn/daten (nur nicht vertrauliche Titel). Texte werden nur gezeichnet bzw. per textContent gesetzt.
 * Steuerung: Trackpad (2 Finger drehen, Pinch = hineinfliegen), Maus ziehen, Pfeiltasten, +/-, Doppelklick = Start.
 */
(function () {
  'use strict';
  var root = document.getElementById('brain3d');
  if (!root || !window.fetch) { return; }
  var canvas = root.querySelector('canvas');
  var ctx = canvas && canvas.getContext ? canvas.getContext('2d') : null;
  if (!ctx) { return; }
  var tip = root.querySelector('.b3-tip');
  var stage = root.parentNode;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var COLORS = { area: { aktiv: '#4fe3ff', laufend: '#4fe3ff', Ausbildung: '#73d29b', Idee: '#ff9f43', 'im Aufbau': '#ff9f43', Thema: '#7cf0c5' },
    notiz: '#9fdcff', aufgabe: '#ffd166', lektion: '#c792ea', recherche: '#ff9f43', strategie: '#ff6bcb' };
  // Plätze für Bereiche und Themen: gleichmäßig über die Hirnrinde verteilt, für jede Anzahl (nicht festgelegt)
  function anchors(n) {
    var out = [], gold = Math.PI * (3 - Math.sqrt(5));
    for (var i = 0; i < n; i++) {
      var y = 0.85 - 1.3 * (i + 0.5) / n, r = Math.sqrt(Math.max(0, 1 - y * y)), a = i * gold + 0.6;
      out.push([Math.cos(a) * r * 0.55, y * 0.62 + 0.08, Math.sin(a) * r * 0.9]);
    }
    return out;
  }
  // Stand 20: Start als Kopf im Profil (wie ein Röntgenbild). Hineinzoomen → Gehirn → dunkles Inneres.
  var HOME = { yaw: 1.45, pitch: 0.06, dist: 3.7 };
  var FX = (function () {
    var v = window.getComputedStyle ? getComputedStyle(document.body).getPropertyValue('--fx-rgb').trim() : '';
    return /^\d{1,3},\s*\d{1,3},\s*\d{1,3}$/.test(v) ? v.replace(/\s/g, '') : '79,227,255';
  })();
  COLORS.area.aktiv = COLORS.area.laufend = 'rgb(' + FX + ')';
  var headRings = [], mouse = null, lit = {}, nearPts = [];

  var cam = { yaw: HOME.yaw, pitch: HOME.pitch, dist: HOME.dist, vyaw: 0, vpitch: 0, vdist: 0 };
  var surf = [], mesh = [], nodes = [], edges = [], pulses = [];
  var W = 0, H = 0, DPR = 1, lastInput = 0, hover = null, ready = false, lastT = 0;

  // ---------------------------------------------------------------- Zufall mit festem Startwert (gleiches Bild)
  var seed = 7;
  function rnd() { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }
  function gauss() { return Math.sqrt(-2 * Math.log(rnd() + 1e-9)) * Math.cos(2 * Math.PI * rnd()); }

  // ---------------------------------------------------------------- Gehirnform
  function brainPoint() {
    var x = gauss(), y = gauss(), z = gauss(), l = Math.sqrt(x * x + y * y + z * z) || 1;
    x /= l; y /= l; z /= l;
    var h = x < 0 ? -1 : 1;
    var ripple = 1 + 0.06 * Math.sin(11 * Math.atan2(y, z) + 6 * x) * Math.cos(9 * y + 4 * z);
    var px = (x * 0.6 + h * 0.05) * ripple, py = y * 0.7 * ripple, pz = z * 1.0 * ripple;
    if (Math.abs(px) < 0.05) { px = h * 0.05; }                 // Spalt zwischen den Hälften
    if (py < -0.32) { py = -0.32 + (py + 0.32) * 0.45; }        // flache Unterseite
    if (pz > 0.4 && py < -0.1) { py += 0.08; }                   // Stirn
    return [px, py, pz];
  }
  function buildHead() {
    // Querschnitte (y, Breite, Tiefe, Versatz nach vorn): Schädel, Stirn, Augen, Nase, Mund, Kinn, Hals
    var rows = [[1.02, 0.18, 0.22, 0], [0.85, 0.58, 0.82, 0], [0.55, 0.78, 1.1, 0.02], [0.22, 0.83, 1.18, 0.05],
      [-0.08, 0.8, 1.15, 0.1], [-0.34, 0.72, 1.04, 0.17], [-0.6, 0.62, 0.9, 0.2], [-0.84, 0.5, 0.7, 0.2],
      [-1.04, 0.38, 0.46, -0.08], [-1.4, 0.35, 0.38, -0.2], [-1.95, 0.44, 0.44, -0.26]];
    function at(y) {
      for (var i = 0; i < rows.length - 1; i++) {
        var a = rows[i], b = rows[i + 1];
        if (y <= a[0] && y >= b[0]) { var t = (a[0] - y) / (a[0] - b[0]); return [a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t]; }
      }
      return null;
    }
    for (var y = 1.0; y >= -1.95; y -= 0.11) {
      var r = at(y); if (!r) { continue; }
      var ring = [];
      for (var k = 0; k < 40; k++) {
        var an = k / 40 * 6.283, x = Math.cos(an) * r[0], z = Math.sin(an) * r[1] + r[2];
        if (z > 0.5 && y < -0.12 && y > -0.5) { z += 0.2 * Math.cos((y + 0.31) * 8) * Math.max(0, Math.sin(an)) * (1 - Math.abs(Math.cos(an)) * 3 > 0 ? 1 : 0); } // Nase
        if (z > 0.5 && y < -0.55 && y > -0.72) { z += 0.05; }                                        // Lippen
        ring.push([x, y + 0.02, z]);
      }
      headRings.push(ring);
    }
  }
  function buildSurface() {
    buildHead();
    var i, n = 950;
    for (i = 0; i < n; i++) { surf.push(brainPoint()); }
    for (i = 0; i < 150; i++) {                                   // Kleinhirn
      var a = rnd() * Math.PI * 2, b = rnd() * Math.PI - Math.PI / 2;
      var r = 1 + 0.08 * Math.sin(14 * b);
      surf.push([Math.cos(b) * Math.cos(a) * 0.42 * r, -0.5 + Math.sin(b) * 0.2 * r, -0.72 + Math.cos(b) * Math.sin(a) * 0.24 * r]);
    }
    for (i = 0; i < 40; i++) {                                    // Hirnstamm
      var t = i / 40, ang = rnd() * Math.PI * 2;
      surf.push([Math.cos(ang) * 0.1, -0.45 - t * 0.6, -0.32 - t * 0.12 + Math.sin(ang) * 0.1]);
    }
    for (i = 0; i < surf.length; i++) {                           // Windungen: nahe Punkte verbinden
      var best = [], p = surf[i];
      for (var j = i + 1; j < surf.length; j++) {
        var q = surf[j], dx = p[0] - q[0], dy = p[1] - q[1], dz = p[2] - q[2], d = dx * dx + dy * dy + dz * dz;
        if (d < 0.018) { best.push([d, j]); }
      }
      best.sort(function (u, v) { return u[0] - v[0]; });
      for (var k = 0; k < Math.min(2, best.length); k++) { mesh.push([i, best[k][1]]); }
    }
  }

  function inside(p) {                                            // Punkt in die Gehirnhülle ziehen
    var e = (p[0] * p[0]) / 0.3 + (p[1] * p[1]) / 0.4 + (p[2] * p[2]) / 0.85;
    if (e > 1) { var s = 1 / Math.sqrt(e); p[0] *= s; p[1] *= s; p[2] *= s; }
    return p;
  }

  // ---------------------------------------------------------------- Daten → Neuronen
  function build(data) {
    buildSurface();
    var core = { x: 0, y: 0.05, z: 0, r: 0.07, color: '#e8fbff', label: 'JARVIS', core: true, url: null };
    nodes.push(core);
    var areaIndex = {};
    var spots = anchors((data.areas || []).length);
    (data.areas || []).forEach(function (a, i) {
      var p = spots[i];
      var n = { x: p[0], y: p[1], z: p[2], r: 0.035 + 0.008 * Math.sqrt(a.count || 0),
        color: COLORS.area[a.status] || COLORS.area.Idee, label: a.name, sub: (a.count || 0) + ' Notizen',
        url: '/wissen?q=' + encodeURIComponent(a.search || a.name), area: true };
      areaIndex[a.slug] = nodes.length; nodes.push(n);
      edges.push([0, nodes.length - 1, 1]);
    });
    var first = nodes.length;
    (data.notes || []).forEach(function (m) {
      var base = areaIndex[m.area] !== undefined ? nodes[areaIndex[m.area]] : { x: 0, y: 0.05, z: 0 };
      var spread = areaIndex[m.area] !== undefined ? 0.26 : 0.42;
      var p = inside([base.x + gauss() * spread * 0.5, base.y + gauss() * spread * 0.5, base.z + gauss() * spread * 0.5]);
      nodes.push({ x: p[0], y: p[1], z: p[2], r: 0.012, color: COLORS[m.kind] || COLORS.notiz,
        label: m.title, sub: ({ notiz: 'Notiz', aufgabe: 'Aufgabe', lektion: 'Lektion', recherche: 'Recherche', strategie: 'Strategie' })[m.kind] || 'Notiz',
        url: '/wissen/notiz?id=' + encodeURIComponent(m.id) });
      edges.push([areaIndex[m.area] !== undefined ? areaIndex[m.area] : 0, nodes.length - 1, 0]);
    });
    (data.links || []).forEach(function (l) {
      if (nodes[first + l[0]] && nodes[first + l[1]]) { edges.push([first + l[0], first + l[1], 2]); }
    });
    stage.classList.add('js-on');
    canvas.tabIndex = 0;
    ready = true;
    resize();
    requestAnimationFrame(frame);
  }

  // ---------------------------------------------------------------- Projektion
  var cy_ = 1, sy_ = 0, cp_ = 1, sp_ = 0, F = 1;
  function setupView() {
    cy_ = Math.cos(cam.yaw); sy_ = Math.sin(cam.yaw); cp_ = Math.cos(cam.pitch); sp_ = Math.sin(cam.pitch);
    F = Math.min(W, H) * 0.95;
  }
  function project(x, y, z, out) {
    var x1 = x * cy_ + z * sy_, z1 = -x * sy_ + z * cy_;           // drehen um Hochachse
    var y2 = y * cp_ - z1 * sp_, z2 = y * sp_ + z1 * cp_;         // neigen
    var depth = cam.dist - z2;
    if (depth < 0.06) { out.v = false; return out; }               // hinter der Kamera (beim Durchfliegen)
    var s = F / depth;
    out.x = W / 2 + x1 * s; out.y = H / 2 - y2 * s; out.s = s; out.d = depth; out.v = true;
    return out;
  }
  function fade(depth) {                                         // weit weg: schwächer · ganz nah: ausblenden
    var far = Math.max(0.1, Math.min(1, 2.4 / (depth * depth)));
    var near = Math.max(0, Math.min(1, (depth - 0.08) / 0.35));
    return far * near;
  }

  // ---------------------------------------------------------------- Zeichnen
  var tmpA = {}, tmpB = {};
  var onScreen = true, slowFrames = 0, low = false;
  if (window.IntersectionObserver) {
    new IntersectionObserver(function (en) { onScreen = en[0].isIntersecting; }).observe(canvas);
  }
  function frame(t) {
    if (!ready) { return; }
    requestAnimationFrame(frame);
    // Stand 17: nicht rechnen, wenn weggescrollt, Tab im Hintergrund oder Ansicht „Datentunnel“ aktiv
    if (document.hidden || !onScreen || root.offsetParent === null) { lastT = 0; return; }
    if (root.clientWidth !== W || root.clientHeight !== H) { resize(); }
    if (lastT) { slowFrames = (t - lastT) > 30 ? slowFrames + 1 : Math.max(0, slowFrames - 1); }
    if (slowFrames > 45 && !low) { low = true; DPR = 1; resize(); }
    var dt = Math.min(0.05, (t - (lastT || t)) / 1000); lastT = t;
    // Trägheit und sanftes Schweben
    cam.yaw += cam.vyaw; cam.pitch += cam.vpitch; cam.dist += cam.vdist;
    cam.vyaw *= 0.9; cam.vpitch *= 0.9; cam.vdist *= 0.85;
    if (!reduce && t - lastInput > 3500) { cam.yaw += dt * 0.12; }
    cam.pitch = Math.max(-1.3, Math.min(1.3, cam.pitch));
    cam.dist = Math.max(0.12, Math.min(7, cam.dist));
    setupView();

    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.clearRect(0, 0, W, H);
    // Leuchten im Hintergrund kommt aus CSS (.brain3d), nicht mehr bei jedem Bild neu gezeichnet
    var headA = Math.max(0, Math.min(1, (cam.dist - 1.85) / 1.1));        // Kopf nur von außen sichtbar
    var inside = Math.max(0, Math.min(1, (1.2 - cam.dist) / 0.55));       // 1 = ganz im Gehirn: dunkel
    var dim = 1 - 0.72 * inside, now = performance.now(), LR = 150;
    nearPts = [];
    if (inside > 0) { ctx.fillStyle = 'rgba(3,2,8,' + (0.85 * inside).toFixed(2) + ')'; ctx.fillRect(0, 0, W, H); }
    if (headA > 0.02) {                                                   // Kopf im Profil als Drahtgitter
      ctx.lineWidth = 0.8; ctx.strokeStyle = 'rgba(' + FX + ',' + (0.2 * headA).toFixed(3) + ')'; ctx.beginPath();
      for (var hr = 0; hr < headRings.length; hr++) {
        var ringP = headRings[hr];
        for (var hk = 0; hk <= ringP.length; hk++) {
          var hp = ringP[hk % ringP.length]; project(hp[0], hp[1], hp[2], tmpA);
          if (!tmpA.v) { continue; } if (hk) { ctx.lineTo(tmpA.x, tmpA.y); } else { ctx.moveTo(tmpA.x, tmpA.y); }
        }
      }
      for (hk = 0; hk < 40; hk += 2) {                                   // Längslinien
        for (hr = 0; hr < headRings.length; hr++) {
          var hq = headRings[hr][hk]; project(hq[0], hq[1], hq[2], tmpA);
          if (!tmpA.v) { continue; } if (hr) { ctx.lineTo(tmpA.x, tmpA.y); } else { ctx.moveTo(tmpA.x, tmpA.y); }
        }
      }
      ctx.stroke();
    }

    // Windungen (ein Pfad = schnell)
    ctx.lineWidth = 0.7; ctx.strokeStyle = 'rgba(' + FX + ',' + (0.22 * dim).toFixed(3) + ')'; ctx.beginPath();
    for (var i = 0; i < mesh.length; i += (low ? 2 : 1)) {
      var p = surf[mesh[i][0]], q = surf[mesh[i][1]];
      project(p[0], p[1], p[2], tmpA); project(q[0], q[1], q[2], tmpB);
      if (tmpA.v && tmpB.v) { ctx.moveTo(tmpA.x, tmpA.y); ctx.lineTo(tmpB.x, tmpB.y); }
    }
    ctx.stroke();
    ctx.fillStyle = 'rgba(' + FX + ',0.75)';
    for (i = 0; i < surf.length; i += (low ? 2 : 1)) {
      project(surf[i][0], surf[i][1], surf[i][2], tmpA);
      if (tmpA.v) {
        var r = Math.max(0.5, tmpA.s * 0.004), boost = 0;
        if (mouse) {                                                       // die Maus ist ein Licht
          var mdx = tmpA.x - mouse[0], mdy = tmpA.y - mouse[1], md = mdx * mdx + mdy * mdy;
          if (md < LR * LR) { boost = Math.pow(1 - Math.sqrt(md) / LR, 2); if (nearPts.length < 80) { nearPts.push([tmpA.x, tmpA.y, md]); } }
        }
        ctx.globalAlpha = Math.min(1, fade(tmpA.d) * 0.7 * dim + boost * 0.9); r *= 1 + boost * 1.5;
        ctx.fillRect(tmpA.x - r / 2, tmpA.y - r / 2, r, r);
      }
    }
    ctx.globalAlpha = 1;

    // Verbindungen (Synapsen)
    for (i = 0; i < edges.length; i++) {
      var e = edges[i], a = nodes[e[0]], b = nodes[e[1]];
      project(a.x, a.y, a.z, tmpA); project(b.x, b.y, b.z, tmpB);
      if (!tmpA.v || !tmpB.v) { continue; }
      var on = (lit[e[0]] > now) || (lit[e[1]] > now);
      ctx.globalAlpha = on ? 0.95 : Math.min(fade(tmpA.d), fade(tmpB.d)) * (e[2] === 1 ? 0.55 : 0.28) * dim;
      ctx.strokeStyle = on ? '#ffffff' : (e[2] === 1 ? 'rgb(' + FX + ')' : (e[2] === 2 ? '#c792ea' : b.color));
      ctx.lineWidth = on ? 2.4 : (e[2] === 1 ? 1.4 : 0.7);
      if (on) { ctx.shadowColor = b.color; ctx.shadowBlur = 12; }
      ctx.beginPath(); ctx.moveTo(tmpA.x, tmpA.y); ctx.lineTo(tmpB.x, tmpB.y); ctx.stroke();
      if (on) { ctx.shadowBlur = 0; }
    }
    ctx.globalAlpha = 1;

    // Lichtimpulse: JARVIS „denkt“
    if (!reduce && edges.length) {
      var litEdges = [];
      for (var le = 0; le < edges.length && litEdges.length < 40; le++) { if (lit[edges[le][0]] > now || lit[edges[le][1]] > now) { litEdges.push(le); } }
      while (pulses.length < Math.min(45, edges.length * 2)) {
        pulses.push({ e: litEdges.length && rnd() < 0.6 ? litEdges[Math.floor(rnd() * litEdges.length)] : Math.floor(rnd() * edges.length), t: 0, v: 0.25 + rnd() * 0.6, dir: rnd() < 0.5 });
      }
      for (i = pulses.length - 1; i >= 0; i--) {
        var pu = pulses[i]; pu.t += dt * pu.v;
        if (pu.t >= 1) { pulses.splice(i, 1); continue; }
        var ed = edges[pu.e], n1 = nodes[pu.dir ? ed[0] : ed[1]], n2 = nodes[pu.dir ? ed[1] : ed[0]], k = pu.t;
        project(n1.x + (n2.x - n1.x) * k, n1.y + (n2.y - n1.y) * k, n1.z + (n2.z - n1.z) * k, tmpA);
        if (!tmpA.v) { continue; }
        var pr = Math.max(1.2, tmpA.s * 0.008);
        ctx.globalAlpha = fade(tmpA.d) * Math.sin(Math.PI * k);
        ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.arc(tmpA.x, tmpA.y, pr, 0, 6.283); ctx.fill();
      }
      ctx.globalAlpha = 1;
    }

    // Neuronen, von hinten nach vorne
    if (nodes.length && nodes[0].i === undefined) { nodes.forEach(function (n, k) { n.i = k; }); }
    var vis = [];
    for (i = 0; i < nodes.length; i++) {
      var nd = nodes[i], pp = project(nd.x, nd.y, nd.z, {});
      if (pp.v) { pp.n = nd; vis.push(pp); }
    }
    vis.sort(function (u, w) { return w.d - u.d; });
    var pulse = reduce ? 1 : 1 + 0.12 * Math.sin(t / 420);
    for (i = 0; i < vis.length; i++) {
      var v = vis[i], node = v.n, al = fade(v.d) * dim, nb = 0, idx = node.i;
      if (mouse) { var ndx = v.x - mouse[0], ndy = v.y - mouse[1], nd2 = ndx * ndx + ndy * ndy; if (nd2 < LR * LR) { nb = Math.pow(1 - Math.sqrt(nd2) / LR, 2); if (nearPts.length < 90) { nearPts.push([v.x, v.y, nd2 * 0.6]); } } }
      if (lit[idx] > now) { nb = 1; }
      al = Math.min(1, al + nb);
      var rad = Math.max(1.5, Math.min(node.core ? 30 : (node.area ? 22 : 9), node.r * v.s * (node.core ? pulse : 1)));
      if (al < 0.02) { continue; }
      v.rad = rad;
      ctx.globalAlpha = al * 0.25; ctx.fillStyle = node.color;
      ctx.beginPath(); ctx.arc(v.x, v.y, rad * (node.area || node.core ? 2.6 : 2), 0, 6.283); ctx.fill();
      ctx.globalAlpha = al; ctx.beginPath(); ctx.arc(v.x, v.y, rad, 0, 6.283); ctx.fill();
      if ((node.area || node.core) && v.d > 0.45 && (node.core || node === hover || v.d < cam.dist + 0.35)) {
        ctx.font = (node.core ? '600 ' : '') + Math.round(Math.max(10, Math.min(15, rad * 1.4))) + 'px -apple-system, Helvetica, Arial, sans-serif';
        ctx.textAlign = 'center'; ctx.fillStyle = node.core ? '#e8fbff' : '#cfe9f5'; ctx.globalAlpha = al * 0.95;
        ctx.fillText(node.label, v.x, v.y + rad + 16);
      }
      if (hover === node) {
        ctx.globalAlpha = 1; ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(v.x, v.y, rad + 5, 0, 6.283); ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
    lastVis = vis;
    if (mouse) {                                                          // Licht-Wesen: greift mit Beinen nach Nervenpunkten
      var strength = 0.35 + 0.65 * inside;
      nearPts.sort(function (u, w) { return u[2] - w[2]; });
      ctx.lineCap = 'round';
      for (var lg = 0; lg < Math.min(8, nearPts.length); lg++) {
        var tp = nearPts[lg], wig = Math.sin(t / 180 + lg * 1.7) * 14, mx2 = (mouse[0] + tp[0]) / 2 + wig, my2 = (mouse[1] + tp[1]) / 2 - 18 + wig * 0.5;
        ctx.strokeStyle = 'rgba(255,255,255,' + (0.55 * strength).toFixed(2) + ')'; ctx.lineWidth = 1.3;
        ctx.beginPath(); ctx.moveTo(mouse[0], mouse[1]); ctx.quadraticCurveTo(mx2, my2, tp[0], tp[1]); ctx.stroke();
        ctx.fillStyle = 'rgba(255,255,255,' + (0.8 * strength).toFixed(2) + ')'; ctx.beginPath(); ctx.arc(tp[0], tp[1], 1.8, 0, 6.283); ctx.fill();
      }
      var glow = ctx.createRadialGradient(mouse[0], mouse[1], 0, mouse[0], mouse[1], 70);
      glow.addColorStop(0, 'rgba(255,255,255,' + (0.9 * strength).toFixed(2) + ')'); glow.addColorStop(0.15, 'rgba(' + FX + ',' + (0.55 * strength).toFixed(2) + ')'); glow.addColorStop(1, 'rgba(' + FX + ',0)');
      ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(mouse[0], mouse[1], 70, 0, 6.283); ctx.fill();
    }
  }
  var lastVis = [];

  // ---------------------------------------------------------------- Größe
  function resize() {
    DPR = low ? 1 : Math.min(window.devicePixelRatio || 1, 1.5);
    W = root.clientWidth; H = root.clientHeight;
    canvas.width = Math.round(W * DPR); canvas.height = Math.round(H * DPR);
  }
  window.addEventListener('resize', resize);

  // ---------------------------------------------------------------- Steuerung
  function touch() { lastInput = performance.now(); }
  function pick(mx, my) {
    for (var i = lastVis.length - 1; i >= 0; i--) {
      var v = lastVis[i], r = Math.max(8, (v.rad || 4) + 4);
      if ((v.x - mx) * (v.x - mx) + (v.y - my) * (v.y - my) <= r * r) { return v; }
    }
    return null;
  }
  function showTip(v, mx, my) {
    if (!tip) { return; }
    if (!v || v.n.core) { tip.hidden = true; return; }
    tip.textContent = '';
    var b = document.createElement('b'); b.textContent = v.n.label; tip.appendChild(b);
    var s = document.createElement('span'); s.textContent = v.n.sub || ''; tip.appendChild(s);
    tip.style.left = Math.min(W - 220, mx + 14) + 'px'; tip.style.top = Math.max(0, my - 10) + 'px';
    tip.hidden = false;
  }
  function local(ev) { var r = canvas.getBoundingClientRect(); return [ev.clientX - r.left, ev.clientY - r.top]; }

  canvas.addEventListener('wheel', function (ev) {
    ev.preventDefault(); touch();
    var k = ev.deltaMode === 1 ? 16 : 1, dx = ev.deltaX * k, dy = ev.deltaY * k;
    if (ev.ctrlKey) { cam.vdist += dy * 0.004 * Math.max(0.3, cam.dist); }          // Pinch: hineinfliegen
    else if (ev.shiftKey || ev.altKey) { cam.vdist += (dy + dx) * 0.0012 * Math.max(0.3, cam.dist); }
    else { cam.vyaw += dx * 0.0009; cam.vpitch += dy * 0.0007; }                    // 2 Finger: drehen
  }, { passive: false });

  var pointers = {}, dragDist = 0, pinch0 = 0;
  canvas.addEventListener('pointerdown', function (ev) {
    pointers[ev.pointerId] = local(ev); dragDist = 0; touch();
    if (canvas.setPointerCapture) { canvas.setPointerCapture(ev.pointerId); }
    var ids = Object.keys(pointers);
    if (ids.length === 2) { var a = pointers[ids[0]], b = pointers[ids[1]]; pinch0 = Math.hypot(a[0] - b[0], a[1] - b[1]); }
  });
  canvas.addEventListener('pointermove', function (ev) {
    var m = local(ev), prev = pointers[ev.pointerId];
    mouse = m;
    if (!prev) {
      var v = pick(m[0], m[1]); hover = v ? v.n : null;
      canvas.style.cursor = v && v.n.url ? 'pointer' : (cam.dist < 1.3 ? 'none' : 'grab'); showTip(v, m[0], m[1]); return;
    }
    touch();
    var ids = Object.keys(pointers);
    if (ids.length === 2) {
      pointers[ev.pointerId] = m;
      var a = pointers[ids[0]], b = pointers[ids[1]], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (pinch0) { cam.dist *= pinch0 / Math.max(1, d); }
      pinch0 = d; return;
    }
    var dx = m[0] - prev[0], dy = m[1] - prev[1]; dragDist += Math.abs(dx) + Math.abs(dy);
    cam.vyaw = dx * 0.004; cam.vpitch = dy * 0.003;
    pointers[ev.pointerId] = m;
  });
  function release(ev) {
    var was = pointers[ev.pointerId]; delete pointers[ev.pointerId]; pinch0 = 0;
    if (was && dragDist < 6 && ev.type === 'pointerup') {
      var m = local(ev), v = pick(m[0], m[1]), now2 = performance.now();
      if (!v) { return; }
      var idx = v.n.i;
      if (lit[idx] > now2 && v.n.url) { window.location.href = v.n.url; return; }   // zweiter Klick: öffnen
      lit = {}; lit[idx] = now2 + 9000;                                             // erster Klick: Gedankengang leuchtet
      edges.forEach(function (e) { if (e[0] === idx) { lit[e[1]] = now2 + 9000; } else if (e[1] === idx) { lit[e[0]] = now2 + 9000; } });
      if (tip && !tip.hidden) { var hint = document.createElement('span'); hint.textContent = 'Nochmal klicken: öffnen'; tip.appendChild(hint); }
    }
  }
  canvas.addEventListener('pointerup', release);
  canvas.addEventListener('pointercancel', release);
  canvas.addEventListener('pointerleave', function () { hover = null; mouse = null; showTip(null); });
  canvas.addEventListener('dblclick', function () { cam.yaw = HOME.yaw; cam.pitch = HOME.pitch; cam.dist = HOME.dist; touch(); });
  canvas.addEventListener('keydown', function (ev) {
    var used = true; touch();
    if (ev.key === 'ArrowLeft') { cam.vyaw -= 0.03; } else if (ev.key === 'ArrowRight') { cam.vyaw += 0.03; }
    else if (ev.key === 'ArrowUp') { cam.vpitch -= 0.02; } else if (ev.key === 'ArrowDown') { cam.vpitch += 0.02; }
    else if (ev.key === '+' || ev.key === '=') { cam.vdist -= 0.08; } else if (ev.key === '-') { cam.vdist += 0.08; }
    else if (ev.key === '0') { cam.yaw = HOME.yaw; cam.pitch = HOME.pitch; cam.dist = HOME.dist; } else { used = false; }
    if (used) { ev.preventDefault(); }
  });

  fetch(root.getAttribute('data-src'), { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    .then(function (r) { if (!r.ok) { throw new Error('Daten'); } return r.json(); })
    .then(build)
    .catch(function () { stage.classList.remove('js-on'); });
})();
