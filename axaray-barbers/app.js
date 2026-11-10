/* Axaray Barbers – Webseite (Entwurf v1)
 * Alles, was der Salon selbst anpassen soll, steht in CONFIG.
 */
const CONFIG = {
  draft: true, // zeigt den Hinweis "Entwurf" oben an
  phone: "+4960216246351",
  phoneDisplay: "06021 6246351",
  whatsapp: "",            // z. B. "4917612345678" – dann geht die Anfrage per WhatsApp raus
  email: "",               // z. B. "termin@axaray-barbers.de"
  bookingWebhook: "",      // z. B. n8n/Make/Zapier-URL – dann wird die Anfrage automatisch übermittelt
  reviewUrl: "https://www.google.com/maps/search/?api=1&query=Axaray+Barbers+Hauptstra%C3%9Fe+118+H%C3%B6sbach",
  address: "Hauptstraße 118, 63768 Hösbach",
  // 0 = Sonntag … 6 = Samstag; [öffnet, schließt] in Minuten ab Mitternacht
  hours: {
    0: null,
    1: [540, 1110], 2: [540, 1110], 3: [540, 1110], 4: [540, 1110], 5: [540, 1110],
    6: [540, 990],
  },
  slotMinutes: 30,
  // PLATZHALTER-PREISE – bitte durch echte Preise ersetzen
  services: [
    { id: "cut",   name: "Haarschnitt",          price: 20, dur: 30, desc: "Waschen, Schneiden, Styling" },
    { id: "fade",  name: "Skin Fade",            price: 25, dur: 40, desc: "Präziser Übergang bis auf die Haut" },
    { id: "beard", name: "Bart trimmen & Konturen", price: 15, dur: 20, desc: "Inkl. Rasur der Konturen mit Klinge" },
    { id: "combo", name: "Haarschnitt + Bart",   price: 32, dur: 50, desc: "Das Komplettpaket" },
    { id: "kids",  name: "Kinderhaarschnitt",    price: 15, dur: 25, desc: "Bis 12 Jahre" },
    { id: "wax",   name: "Gesichtspflege & Wachs", price: 10, dur: 15, desc: "Nase, Ohren, Hot Towel" },
  ],
  // PLATZHALTER-BEWERTUNGEN – bitte durch echte Google-Rezensionen ersetzen (mit Erlaubnis/Vorname)
  reviews: [
    { name: "Platzhalter A", text: "Hier kommt eine echte Google-Rezension hin – z. B. über den Fade und die Atmosphäre.", when: "Beispieltext" },
    { name: "Platzhalter B", text: "Zweite echte Rezension: Freundlichkeit, Wartezeit ohne Termin, Sauberkeit.", when: "Beispieltext" },
    { name: "Platzhalter C", text: "Dritte echte Rezension: Bartpflege, Hot Towel, Preis-Leistung.", when: "Beispieltext" },
    { name: "Platzhalter D", text: "Vierte echte Rezension: Einrichtung, Licht, Lounge.", when: "Beispieltext" },
    { name: "Platzhalter E", text: "Fünfte echte Rezension: Parken gegenüber, schnell drangekommen.", when: "Beispieltext" },
    { name: "Platzhalter F", text: "Sechste echte Rezension: Styling-Tipps und Produkte.", when: "Beispieltext" },
  ],
};

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const DAYS = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"];
const fmtTime = (m) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};

/* ---------------- Grundgerüst ---------------- */
$("#draftBar").hidden = !CONFIG.draft;
$("#year").textContent = new Date().getFullYear();
$("#reviewBtn").href = CONFIG.reviewUrl;

const burger = $("#burger"), navLinks = $("#navLinks");
burger.addEventListener("click", () => {
  const open = navLinks.classList.toggle("open");
  burger.setAttribute("aria-expanded", open);
});
$$("#navLinks a").forEach((a) => a.addEventListener("click", () => {
  navLinks.classList.remove("open"); burger.setAttribute("aria-expanded", false);
}));

/* ---------------- Live-Öffnungsstatus ---------------- */
function openState(now = new Date()) {
  const h = CONFIG.hours[now.getDay()];
  const mins = now.getHours() * 60 + now.getMinutes();
  if (h && mins >= h[0] && mins < h[1]) {
    const left = h[1] - mins;
    return { cls: left <= 45 ? "soon" : "open", text: left <= 45 ? `Schließt bald · bis ${fmtTime(h[1])}` : `Jetzt geöffnet · bis ${fmtTime(h[1])}` };
  }
  for (let i = 0; i < 8; i++) {
    const d = new Date(now); d.setDate(now.getDate() + i);
    const hh = CONFIG.hours[d.getDay()];
    if (!hh || (i === 0 && mins >= hh[0])) continue;
    const label = i === 0 ? "heute" : i === 1 ? "morgen" : DAYS[d.getDay()];
    return { cls: "closed", text: `Geschlossen · öffnet ${label} um ${fmtTime(hh[0])}` };
  }
  return { cls: "closed", text: "Geschlossen" };
}
function renderStatus() {
  const s = openState();
  const el = $("#openStatus");
  el.className = `status ${s.cls}`;
  $(".txt", el).textContent = s.text;
}
renderStatus();
setInterval(renderStatus, 60000);

(function renderHours() {
  const order = [1, 2, 3, 4, 5, 6, 0], today = new Date().getDay();
  $("#hoursTable").innerHTML = order.map((d) => {
    const h = CONFIG.hours[d];
    return `<tr class="${d === today ? "today" : ""}"><td>${DAYS[d]}</td><td>${h ? `${fmtTime(h[0])} – ${fmtTime(h[1])}` : "geschlossen"}</td></tr>`;
  }).join("");
})();

/* ---------------- Bewertungen: Laufband ---------------- */
(function reviews() {
  const card = (r) => `
    <article class="review">
      <div class="review-top">
        <div class="avatar">${r.name.charAt(0)}</div>
        <div><div class="review-name">${r.name}</div><div class="review-meta"><span class="stars">★★★★★</span> · ${r.when}</div></div>
        <span class="g-badge" aria-label="Google">G</span>
      </div>
      <p>${r.text}</p>
    </article>`;
  const html = CONFIG.reviews.map(card).join("");
  const track = $("#marqueeTrack");
  track.innerHTML = html + html.replace(/<article class="review">/g, '<article class="review" aria-hidden="true">'); // doppelt für nahtlose Schleife
  const m = $("#marquee");
  const toggle = () => m.classList.toggle("paused");
  m.addEventListener("click", toggle);
  m.addEventListener("keydown", (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); toggle(); } });
})();

/* ---------------- Leistungen ---------------- */
$("#serviceGrid").innerHTML = CONFIG.services.map((s) => `
  <article class="service reveal">
    <div class="service-row"><h3>${s.name}</h3><span class="price">${s.price} €</span></div>
    <p class="muted small">${s.desc}</p>
    <span class="dur">ca. ${s.dur} Min.</span>
    <button class="book-this" data-service="${s.id}">Diesen Termin buchen →</button>
  </article>`).join("");
$$(".book-this").forEach((b) => b.addEventListener("click", () => {
  booking.selectService(b.dataset.service);
  $("#termin").scrollIntoView({ behavior: "smooth" });
}));

/* ---------------- Terminbuchung ---------------- */
const booking = (() => {
  const state = { service: null, date: null, time: null };
  const chips = $("#serviceChips"), days = $("#dayPicker"), slots = $("#slotPicker");

  chips.innerHTML = CONFIG.services.map((s) =>
    `<button type="button" class="chip" data-id="${s.id}" aria-pressed="false">${s.name}<small>${s.price} € · ${s.dur} Min.</small></button>`).join("");
  chips.addEventListener("click", (e) => { const b = e.target.closest(".chip"); if (b) selectService(b.dataset.id); });

  const dayList = [];
  for (let i = 0; i < 21; i++) {
    const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() + i);
    dayList.push(d);
  }
  days.innerHTML = dayList.map((d, i) => {
    const closed = !CONFIG.hours[d.getDay()] || (i === 0 && availableSlots(d).length === 0);
    const top = i === 0 ? "Heute" : i === 1 ? "Morgen" : DAYS[d.getDay()].slice(0, 2);
    return `<button type="button" class="day" data-i="${i}" aria-pressed="false" ${closed ? "disabled" : ""}><small>${top}</small><b>${d.getDate()}</b><small>${d.toLocaleDateString("de-DE", { month: "short" })}</small></button>`;
  }).join("");
  days.addEventListener("click", (e) => { const b = e.target.closest(".day"); if (b && !b.disabled) selectDate(dayList[+b.dataset.i]); });

  function availableSlots(d) {
    const h = CONFIG.hours[d.getDay()];
    if (!h) return [];
    const dur = state.service ? CONFIG.services.find((s) => s.id === state.service).dur : CONFIG.slotMinutes;
    const now = new Date(), isToday = d.toDateString() === now.toDateString();
    const nowMin = now.getHours() * 60 + now.getMinutes() + 30; // mind. 30 Min. Vorlauf
    const out = [];
    for (let m = h[0]; m + dur <= h[1]; m += CONFIG.slotMinutes) if (!isToday || m >= nowMin) out.push(m);
    return out;
  }

  function selectService(id) {
    state.service = id;
    $$(".chip", chips).forEach((c) => c.setAttribute("aria-pressed", c.dataset.id === id));
    if (state.date) renderSlots();
    update();
  }
  function selectDate(d) {
    state.date = d; state.time = null;
    $$(".day", days).forEach((b) => b.setAttribute("aria-pressed", dayList[+b.dataset.i].getTime() === d.getTime()));
    renderSlots(); update();
  }
  function selectTime(m) {
    state.time = m;
    $$(".slot", slots).forEach((b) => b.setAttribute("aria-pressed", +b.dataset.m === m));
    update();
  }
  function renderSlots() {
    const list = availableSlots(state.date);
    slots.innerHTML = list.length
      ? list.map((m) => `<button type="button" class="slot" data-m="${m}" aria-pressed="${m === state.time}">${fmtTime(m)}</button>`).join("")
      : `<p class="muted small">An diesem Tag ist nichts mehr frei – komm gern ohne Termin vorbei.</p>`;
    if (!list.includes(state.time)) state.time = null;
  }
  slots.addEventListener("click", (e) => { const b = e.target.closest(".slot"); if (b) selectTime(+b.dataset.m); });

  function update() {
    const s = CONFIG.services.find((x) => x.id === state.service);
    const parts = [];
    if (s) parts.push(`<b>${s.name}</b> (${s.price} €)`);
    if (state.date) parts.push(state.date.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" }));
    if (state.time != null) parts.push(`um ${fmtTime(state.time)} Uhr`);
    $("#summary").innerHTML = parts.length ? parts.join(" · ") : "Noch nichts gewählt.";
  }

  // Datum/Uhrzeit von außen setzen (Sprachassistent)
  function prefill({ service, date, time }) {
    if (service) selectService(service);
    if (date) {
      const match = dayList.find((d) => d.getTime() === date.getTime());
      if (match && CONFIG.hours[match.getDay()]) selectDate(match);
    }
    if (time != null && state.date && availableSlots(state.date).includes(time)) selectTime(time);
    return { ...state };
  }

  $("#bookingForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target, err = $("#formError");
    const name = f.name.value.trim(), phone = f.phone.value.trim(), note = f.note.value.trim();
    if (!state.service) return (err.textContent = "Bitte eine Leistung wählen.");
    if (!state.date) return (err.textContent = "Bitte einen Tag wählen.");
    if (state.time == null) return (err.textContent = "Bitte eine Uhrzeit wählen.");
    if (name.length < 2) return (err.textContent = "Bitte deinen Namen angeben.");
    if (phone.replace(/\D/g, "").length < 6) return (err.textContent = "Bitte eine gültige Telefonnummer angeben.");
    err.textContent = "";

    const s = CONFIG.services.find((x) => x.id === state.service);
    const start = new Date(state.date); start.setMinutes(state.time);
    const dateText = start.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" });
    const req = { service: s.name, price: s.price, start: start.toISOString(), duration: s.dur, name, phone, note, createdAt: new Date().toISOString() };
    const msg = `Hallo Axaray Barbers, ich möchte einen Termin anfragen:\n${s.name}\n${dateText}, ${fmtTime(state.time)} Uhr\nName: ${name}\nTelefon: ${phone}${note ? `\nWunsch: ${note}` : ""}`;

    let sent = false;
    if (CONFIG.bookingWebhook) {
      try {
        const r = await fetch(CONFIG.bookingWebhook, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req) });
        sent = r.ok;
      } catch {}
    }
    const history = store.get("axaray-bookings") || [];
    history.push(req); store.set("axaray-bookings", history);

    const actions = [];
    if (CONFIG.whatsapp) actions.push(`<a class="btn btn-gold" target="_blank" rel="noopener" href="https://wa.me/${CONFIG.whatsapp}?text=${encodeURIComponent(msg)}">Per WhatsApp senden</a>`);
    if (CONFIG.email) actions.push(`<a class="btn btn-ghost" href="mailto:${CONFIG.email}?subject=${encodeURIComponent("Terminanfrage " + dateText)}&body=${encodeURIComponent(msg)}">Per E-Mail senden</a>`);
    if (!sent) actions.push(`<a class="btn ${actions.length ? "btn-ghost" : "btn-gold"}" href="tel:${CONFIG.phone}">Anrufen & bestätigen</a>`);
    actions.push(`<button class="btn btn-ghost" type="button" id="icsBtn">In meinen Kalender</button>`);

    $("#doneText").innerHTML = sent
      ? `Danke ${name}! Deine Anfrage für <b>${s.name}</b> am <b>${dateText}</b> um <b>${fmtTime(state.time)} Uhr</b> ist beim Salon angekommen. Wir melden uns zur Bestätigung.`
      : `Danke ${name}! <b>${s.name}</b> am <b>${dateText}</b> um <b>${fmtTime(state.time)} Uhr</b>. Schick die Anfrage jetzt ab:`;
    $("#doneActions").innerHTML = actions.join("");
    $("#icsBtn").addEventListener("click", () => downloadIcs(s, start));
    f.hidden = true; $("#bookingDone").hidden = false;
    $("#termin").scrollIntoView({ behavior: "smooth" });
  });

  $("#newBooking").addEventListener("click", () => {
    $("#bookingForm").hidden = false; $("#bookingDone").hidden = true;
  });

  function downloadIcs(s, start) {
    const end = new Date(start.getTime() + s.dur * 60000);
    const z = (d) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
    const ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Axaray Barbers//DE", "BEGIN:VEVENT",
      `UID:${Date.now()}@axaray-barbers`, `DTSTAMP:${z(new Date())}`, `DTSTART:${z(start)}`, `DTEND:${z(end)}`,
      `SUMMARY:${s.name} – Axaray Barbers (angefragt)`, `LOCATION:${CONFIG.address}`,
      "DESCRIPTION:Terminanfrage – Bestätigung durch den Salon folgt.", "END:VEVENT", "END:VCALENDAR"].join("\r\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([ics], { type: "text/calendar" }));
    a.download = "axaray-termin.ics"; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  return { selectService, prefill, availableSlots, dayList };
})();

/* ---------------- Karte erst nach Klick (Datenschutz) ---------------- */
$("#mapConsent").addEventListener("click", () => {
  $(".map-wrap").innerHTML = `<iframe title="Karte Axaray Barbers" loading="lazy" referrerpolicy="no-referrer-when-downgrade"
    src="https://www.google.com/maps?q=${encodeURIComponent("Axaray Barbers, " + CONFIG.address)}&output=embed"></iframe>`;
});

/* ---------------- Scroll-Reveal & 3D-Kippen der Bilder ---------------- */
const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: .15 });
$$(".section-head, .service, .gallery-grid figure, .contact-card, .booking-card").forEach((el) => { el.classList.add("reveal"); io.observe(el); });
$$(".tilt").forEach((el) => {
  el.addEventListener("pointermove", (e) => {
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
    el.style.transform = `rotateY(${x * 10}deg) rotateX(${-y * 10}deg)`;
  });
  el.addEventListener("pointerleave", () => (el.style.transform = ""));
});

/* ---------------- 3D-Szene: Waben-Lichtdecke + Barber-Pole ---------------- */
(function scene() {
  const canvas = $("#scene");
  if (!window.THREE) return;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true }); } catch { return; }
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x0b0b0d, 6, 26);
  const camera = new THREE.PerspectiveCamera(60, 1, .1, 100);
  camera.position.set(0, 0, 7);

  // Waben-Decke: jede Kante als dünner leuchtender Balken (Instanzen)
  const R = 1.1, edges = new Map();
  const key = (a, b) => [a, b].map((p) => `${p.x.toFixed(2)},${p.z.toFixed(2)}`).sort().join("|");
  for (let q = -6; q <= 6; q++) for (let r = -5; r <= 5; r++) {
    const cx = R * 1.5 * q, cz = R * Math.sqrt(3) * (r + q / 2);
    if (Math.hypot(cx, cz) > 9) continue;
    const v = [...Array(6)].map((_, i) => new THREE.Vector3(cx + R * Math.cos(i * Math.PI / 3), 0, cz + R * Math.sin(i * Math.PI / 3)));
    for (let i = 0; i < 6; i++) edges.set(key(v[i], v[(i + 1) % 6]), [v[i], v[(i + 1) % 6]]);
  }
  const ceiling = new THREE.Group();
  const barGeo = new THREE.BoxGeometry(1, .05, .05);
  const glowGeo = new THREE.PlaneGeometry(1, .35);
  const glowTex = (() => {
    const c = document.createElement("canvas"); c.width = 4; c.height = 64;
    const g = c.getContext("2d"), grd = g.createLinearGradient(0, 0, 0, 64);
    grd.addColorStop(0, "rgba(255,255,255,0)"); grd.addColorStop(.5, "rgba(255,248,230,1)"); grd.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = grd; g.fillRect(0, 0, 4, 64); return new THREE.CanvasTexture(c);
  })();
  const bars = new THREE.InstancedMesh(barGeo, new THREE.MeshBasicMaterial({ color: 0xfffaf0 }), edges.size);
  const glows = new THREE.InstancedMesh(glowGeo, new THREE.MeshBasicMaterial({ map: glowTex, transparent: true, opacity: .35, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }), edges.size);
  const m4 = new THREE.Matrix4(), quat = new THREE.Quaternion(), qFlat = new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2, 0, 0));
  [...edges.values()].forEach(([a, b], i) => {
    const mid = a.clone().add(b).multiplyScalar(.5), len = a.distanceTo(b) * .96;
    quat.setFromAxisAngle(new THREE.Vector3(0, 1, 0), -Math.atan2(b.z - a.z, b.x - a.x));
    m4.compose(mid, quat, new THREE.Vector3(len, 1, 1)); bars.setMatrixAt(i, m4);
    m4.compose(mid, quat.clone().multiply(qFlat), new THREE.Vector3(len, 1, 1)); glows.setMatrixAt(i, m4);
  });
  ceiling.add(bars, glows);
  ceiling.position.set(0, 3.2, -4);
  scene.add(ceiling);

  // Barber-Pole
  const poleTex = (() => {
    const c = document.createElement("canvas"); c.width = 256; c.height = 256;
    const g = c.getContext("2d"); g.fillStyle = "#f5f2ea"; g.fillRect(0, 0, 256, 256);
    g.lineWidth = 34;
    [["#c8102e", 0], ["#1f3a93", 128]].forEach(([col, off]) => {
      g.strokeStyle = col;
      for (let k = -2; k < 3; k++) { g.beginPath(); g.moveTo(-40, off + k * 256 + 296); g.lineTo(296, off + k * 256 - 40); g.stroke(); }
    });
    const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(1, 2); return t;
  })();
  const gold = new THREE.MeshStandardMaterial({ color: 0xd4af37, metalness: .9, roughness: .25 });
  const pole = new THREE.Group();
  const stripes = new THREE.Mesh(new THREE.CylinderGeometry(.32, .32, 2.6, 48, 1, true), new THREE.MeshStandardMaterial({ map: poleTex, roughness: .4, emissive: 0x222222 }));
  const glass = new THREE.Mesh(new THREE.CylinderGeometry(.38, .38, 2.6, 48, 1, true), new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: .12, roughness: 0, metalness: 0 }));
  const capTop = new THREE.Mesh(new THREE.SphereGeometry(.42, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), gold);
  const ringTop = new THREE.Mesh(new THREE.CylinderGeometry(.44, .44, .18, 48), gold);
  const ringBot = ringTop.clone(), capBot = capTop.clone();
  ringTop.position.y = 1.38; capTop.position.y = 1.47; ringBot.position.y = -1.38; capBot.position.y = -1.47; capBot.rotation.x = Math.PI;
  pole.add(stripes, glass, ringTop, capTop, ringBot, capBot);
  scene.add(pole);

  // Goldstaub
  const N = 260, pos = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) { pos[i * 3] = (Math.random() - .5) * 18; pos[i * 3 + 1] = (Math.random() - .5) * 10; pos[i * 3 + 2] = (Math.random() - .5) * 10 - 2; }
  const dustGeo = new THREE.BufferGeometry(); dustGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const dust = new THREE.Points(dustGeo, new THREE.PointsMaterial({ color: 0xd4af37, size: .035, transparent: true, opacity: .8 }));
  scene.add(dust);

  scene.add(new THREE.AmbientLight(0xffffff, .55));
  const key1 = new THREE.PointLight(0xfff3d6, 1.4, 20); key1.position.set(0, 3, 2); scene.add(key1);
  const rim = new THREE.PointLight(0xd4af37, 1.2, 15); rim.position.set(-3, -1, 3); scene.add(rim);

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    const mobile = w < 760;
    pole.position.set(mobile ? 2.3 : 4.2, mobile ? 3.0 : -.3, 0);
    pole.scale.setScalar(mobile ? .45 : 1);
  }
  addEventListener("resize", resize); resize();

  // Parallaxe per Maus oder Neigung des Handys
  const target = { x: 0, y: 0 };
  addEventListener("pointermove", (e) => { target.x = e.clientX / innerWidth - .5; target.y = e.clientY / innerHeight - .5; });
  addEventListener("deviceorientation", (e) => {
    if (e.gamma == null) return;
    target.x = Math.max(-.5, Math.min(.5, e.gamma / 60)); target.y = Math.max(-.5, Math.min(.5, (e.beta - 45) / 60));
  });

  let visible = true;
  new IntersectionObserver(([e]) => (visible = e.isIntersecting)).observe(canvas);
  const clock = new THREE.Clock();
  (function loop() {
    requestAnimationFrame(loop);
    if (!visible) return;
    const t = reduce ? 0 : clock.getElapsedTime();
    poleTex.offset.y = -t * .25;
    pole.rotation.z = Math.sin(t * .6) * .05;
    ceiling.rotation.y = t * .04;
    ceiling.rotation.x = .18 + Math.sin(t * .3) * .03;
    dust.rotation.y = t * .02;
    dust.position.y = Math.sin(t * .4) * .2;
    camera.position.x += (target.x * 1.6 - camera.position.x) * .05;
    camera.position.y += (-target.y * 1.0 - camera.position.y) * .05;
    camera.lookAt(0, .6, -3);
    renderer.render(scene, camera);
  })();
  $(".hero-fallback").style.opacity = .6;
})();

/* ---------------- Sprachassistent ---------------- */
(function voiceAgent() {
  const panel = $("#vaPanel"), log = $("#vaLog"), input = $("#vaText"), mic = $("#vaMic");
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, greeted = false, voiceOn = false;

  const toggle = (open) => {
    panel.hidden = !open;
    if (open && !greeted) {
      greeted = true;
      bot(`Hey, willkommen bei Axaray Barbers! ${openState().text}.\nFrag mich nach Preisen, Öffnungszeiten – oder sag z. B. „Skin Fade morgen um 15 Uhr“.`, false);
    }
    if (open) setTimeout(() => input.focus(), 50);
  };
  $("#vaFab").addEventListener("click", () => toggle(panel.hidden));
  $("#vaClose").addEventListener("click", () => toggle(false));

  const quick = ["Öffnungszeiten", "Preise", "Termin morgen", "Wo parke ich?", "Ohne Termin?"];
  $("#vaQuick").innerHTML = quick.map((q) => `<button type="button">${q}</button>`).join("");
  $("#vaQuick").addEventListener("click", (e) => { if (e.target.tagName === "BUTTON") handle(e.target.textContent); });

  function add(text, who) {
    const d = document.createElement("div"); d.className = `msg ${who}`; d.textContent = text;
    log.appendChild(d); log.scrollTop = log.scrollHeight;
  }
  function bot(text, speak = voiceOn) {
    add(text, "bot");
    if (speak && "speechSynthesis" in window) {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text.replace(/[•→✂🅿]/g, ""));
      u.lang = "de-DE"; u.rate = 1.03;
      const v = speechSynthesis.getVoices().find((x) => x.lang.startsWith("de"));
      if (v) u.voice = v;
      speechSynthesis.speak(u);
    }
  }

  $("#vaForm").addEventListener("submit", (e) => {
    e.preventDefault(); const t = input.value.trim(); if (!t) return; input.value = ""; handle(t);
  });

  if (!SR) { mic.title = "Spracheingabe wird von diesem Browser nicht unterstützt"; mic.style.opacity = .4; }
  mic.addEventListener("click", () => {
    if (!SR) return bot("Dein Browser unterstützt leider keine Spracheingabe – schreib mir einfach.", false);
    if (rec) { rec.stop(); return; }
    rec = new SR(); rec.lang = "de-DE"; rec.interimResults = false;
    rec.onresult = (e) => { voiceOn = true; handle(e.results[0][0].transcript); };
    rec.onend = () => { mic.classList.remove("listening"); rec = null; };
    rec.onerror = () => { mic.classList.remove("listening"); rec = null; };
    mic.classList.add("listening"); rec.start();
  });

  // --- Verstehen ---
  const norm = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ß/g, "ss");
  function parseDate(t) {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const add = (n) => { const d = new Date(today); d.setDate(d.getDate() + n); return d; };
    if (/ubermorgen/.test(t)) return add(2);
    if (/morgen/.test(t)) return add(1);
    if (/heute|jetzt|gleich/.test(t)) return add(0);
    const names = ["sonntag", "montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag"];
    const i = names.findIndex((n) => t.includes(n));
    if (i >= 0) { let diff = (i - today.getDay() + 7) % 7; if (diff === 0) diff = 7; return add(diff); }
    return null;
  }
  function parseTime(t) {
    const halb = t.match(/halb (\d{1,2})/);
    if (halb) { const h = +halb[1] - 1; return (h < 8 ? h + 12 : h) * 60 + 30; }
    let m = t.match(/(\d{1,2})[:.](\d{2})/) || t.match(/um (\d{1,2})(?: uhr)?(?: (\d{2}))?/) || t.match(/(\d{1,2}) uhr(?: (\d{2}))?/);
    if (!m) return null;
    let h = +m[1]; const min = m[2] ? +m[2] : 0;
    if (h < 8) h += 12; // "um 3" = 15 Uhr
    return h * 60 + (min >= 30 ? 30 : 0);
  }
  function parseService(t) {
    if (/kind/.test(t)) return "kids";
    if (/(haar|schnitt).*bart|bart.*(haar|schnitt)|komplett|beides|combo/.test(t)) return "combo";
    if (/fade|ubergang|skin/.test(t)) return "fade";
    if (/bart|rasur|kontur/.test(t)) return "beard";
    if (/wachs|gesicht|towel/.test(t)) return "wax";
    if (/haarschnitt|schneiden|haare/.test(t)) return "cut";
    return null;
  }

  function handle(raw) {
    add(raw, "me");
    const t = norm(raw);
    const svc = parseService(t), date = parseDate(t), time = parseTime(t);
    const wantsBooking = /termin|buchen|reservier|frei|platz|kommen|vorbei/.test(t) || (svc && (date || time != null));

    if (/hallo|hi\b|hey|servus|guten|selam|merhaba/.test(t) && t.length < 20) return bot("Hey! Wie kann ich dir helfen – Termin, Preise oder Öffnungszeiten?");
    if (/ohne termin|walk|spontan|einfach vorbei/.test(t)) return bot("Ja! Du kannst jederzeit ohne Termin vorbeikommen. Mit Termin sparst du dir aber die Wartezeit.");
    if (/park/.test(t)) return bot("Direkt gegenüber vom Salon gibt es Parkplätze – zwei Stunden kosten nur 1,50 €.");
    if (/wo |adresse|anfahrt|wie komm|standort|finde/.test(t)) return bot(`Du findest uns in der ${CONFIG.address}. Unten auf der Seite kannst du direkt die Route planen.`);
    if (/telefon|nummer|anruf|erreich/.test(t)) return bot(`Ruf uns an unter ${CONFIG.phoneDisplay}.`);
    if (/offnung|offen|geoffnet|zu\b|schliess|wann.*(auf|offen)|uhrzeit/.test(t) && !wantsBooking)
      return bot(`${openState().text}.\nMo–Fr: 09:00–18:30\nSa: 09:00–16:30\nSo: geschlossen`);
    if (/preis|kost|teuer|euro|€|was nehmt/.test(t)) {
      if (svc) { const s = CONFIG.services.find((x) => x.id === svc); return bot(`${s.name} kostet ${s.price} € und dauert ca. ${s.dur} Minuten. Soll ich dir einen Termin eintragen?`); }
      return bot(CONFIG.services.map((s) => `• ${s.name}: ${s.price} €`).join("\n"));
    }
    if (/bewert|rezension|google/.test(t)) return bot("Wir haben 5,0 Sterne bei 34 Google-Bewertungen. Warst du schon bei uns? Über den Button „Bei Google bewerten“ kannst du uns in 30 Sekunden bewerten – danke!");
    if (/instagram|insta|bilder|fotos/.test(t)) return bot("Auf Instagram findest du uns unter @axary_barbers – dort gibt’s aktuelle Cuts.");

    if (wantsBooking) {
      const st = booking.prefill({ service: svc, date, time });
      $("#termin").scrollIntoView({ behavior: "smooth" });
      if (date && !CONFIG.hours[date.getDay()]) return bot("Sonntags haben wir leider geschlossen. Wie wäre Montag oder Samstag?");
      const missing = [];
      if (!st.service) missing.push("welche Leistung");
      if (!st.date) missing.push("welcher Tag");
      if (st.time == null) {
        if (st.date) {
          const free = booking.availableSlots(st.date);
          if (time != null && !free.includes(time)) return bot(`${fmtTime(time)} Uhr geht an dem Tag leider nicht. Frei wären z. B. ${free.slice(0, 4).map(fmtTime).join(", ")} Uhr.`);
          if (!free.length) return bot("An dem Tag ist nichts mehr frei – komm gern ohne Termin vorbei oder nimm einen anderen Tag.");
          missing.push(`welche Uhrzeit (z. B. ${free.slice(0, 3).map(fmtTime).join(", ")})`);
        } else missing.push("welche Uhrzeit");
      }
      if (missing.length) return bot(`Gern! Ich hab dir das Formular schon vorbereitet. Sag mir noch: ${missing.join(", ")}?`);
      const s = CONFIG.services.find((x) => x.id === st.service);
      return bot(`Perfekt: ${s.name} am ${st.date.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" })} um ${fmtTime(st.time)} Uhr ist eingetragen. Gib unten noch Name und Telefonnummer ein und tipp auf „Termin anfragen“.`);
    }
    if (svc) { const s = CONFIG.services.find((x) => x.id === svc); return bot(`${s.name}: ${s.desc}, ${s.price} €. Willst du dafür einen Termin? Sag z. B. „morgen um 14 Uhr“.`); }
    bot(`Das kann ich dir leider nicht sicher beantworten – ruf am besten kurz an: ${CONFIG.phoneDisplay}.`);
  }

  window.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) toggle(false); });
})();
