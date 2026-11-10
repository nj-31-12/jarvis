/* Axaray Barbers – Seitenlogik. Einstellungen stehen in config.js */
const C = window.CONFIG;
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const DAYS = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"];
const fmtTime = (m) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
const fmtDate = (d) => d.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" });
const euro = (n) => `${n.toFixed(2).replace(".", ",")} €`;
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
  del(k) { try { localStorage.removeItem(k); } catch {} },
};
const svcById = (id) => C.services.find((s) => s.id === id);
const barberById = (id) => C.barbers.find((b) => b.id === id);

/* ---------------- Grundgerüst ---------------- */
$("#draftBar").hidden = !C.draft;
$("#year").textContent = new Date().getFullYear();
const burger = $("#burger"), navLinks = $("#navLinks");
burger.addEventListener("click", () => burger.setAttribute("aria-expanded", navLinks.classList.toggle("open")));
$$("#navLinks a, #navLinks button").forEach((a) => a.addEventListener("click", () => { navLinks.classList.remove("open"); burger.setAttribute("aria-expanded", false); }));

/* ---------------- Modale ---------------- */
function openModal(id) { const m = $(id); m.hidden = false; document.body.classList.add("modal-open"); setTimeout(() => $("input, button:not([data-close])", m)?.focus(), 50); }
function closeModal(m) { m.hidden = true; if (!$$(".modal").some((x) => !x.hidden)) document.body.classList.remove("modal-open"); }
$$(".modal").forEach((m) => m.addEventListener("click", (e) => { if (e.target === m || e.target.closest("[data-close]")) closeModal(m); }));
addEventListener("keydown", (e) => { if (e.key === "Escape") $$(".modal").forEach((m) => !m.hidden && closeModal(m)); });

/* ---------------- Öffnungsstatus ---------------- */
function openState(now = new Date()) {
  const h = C.hours[now.getDay()], mins = now.getHours() * 60 + now.getMinutes();
  if (h && mins >= h[0] && mins < h[1]) {
    const left = h[1] - mins;
    return { cls: left <= 45 ? "soon" : "open", text: left <= 45 ? `Schließt bald · bis ${fmtTime(h[1])}` : `Jetzt geöffnet · bis ${fmtTime(h[1])}` };
  }
  for (let i = 0; i < 8; i++) {
    const d = new Date(now); d.setDate(now.getDate() + i);
    const hh = C.hours[d.getDay()];
    if (!hh || (i === 0 && mins >= hh[0])) continue;
    return { cls: "closed", text: `Geschlossen · öffnet ${i === 0 ? "heute" : i === 1 ? "morgen" : DAYS[d.getDay()]} um ${fmtTime(hh[0])}` };
  }
  return { cls: "closed", text: "Geschlossen" };
}
function renderStatus() { const s = openState(), el = $("#openStatus"); el.className = `status ${s.cls}`; $(".txt", el).textContent = s.text; }
renderStatus(); setInterval(renderStatus, 60000);
$("#hoursTable").innerHTML = [1, 2, 3, 4, 5, 6, 0].map((d) => {
  const h = C.hours[d];
  return `<tr class="${d === new Date().getDay() ? "today" : ""}"><td>${DAYS[d]}</td><td>${h ? `${fmtTime(h[0])} – ${fmtTime(h[1])}` : "geschlossen"}</td></tr>`;
}).join("");

/* ---------------- Bewertungen ---------------- */
(function reviews() {
  $("#reviewWrite").href = C.reviewWriteUrl || C.reviewUrl;
  $("#reviewAll").href = C.reviewUrl;
  const card = (r, hidden) => `
    <article class="review"${hidden ? ' aria-hidden="true"' : ""}>
      <header class="review-top">
        <div class="avatar">${esc(r.name.charAt(0))}</div>
        <div class="review-who"><b>${esc(r.name)}</b><span>${esc(r.when)}</span></div>
        <span class="g-mini" aria-label="Google-Bewertung">G</span>
      </header>
      <div class="stars">${"★".repeat(r.stars)}<span class="off">${"★".repeat(5 - r.stars)}</span></div>
      <p>${esc(r.text)}</p>
    </article>`;
  const half = Math.ceil(C.reviews.length / 2);
  [C.reviews.slice(0, half), C.reviews.slice(half)].forEach((list, i) => {
    const html = list.map((r) => card(r)).join("");
    $(`.marquee-row[data-row="${i}"] .marquee-track`).innerHTML = html + list.map((r) => card(r, true)).join("");
  });
  $("#reviewGrid").innerHTML = C.reviews.map((r) => card(r)).join("");

  const m = $("#marquee");
  const toggle = () => m.classList.toggle("paused");
  m.addEventListener("click", toggle);
  m.addEventListener("keydown", (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); toggle(); } });
  $$(".view-toggle button").forEach((b) => b.addEventListener("click", () => {
    $$(".view-toggle button").forEach((x) => x.setAttribute("aria-selected", x === b));
    const grid = b.dataset.view === "grid";
    m.hidden = grid; $("#reviewGrid").hidden = !grid;
  }));
})();

/* ---------------- Leistungen ---------------- */
$("#serviceGrid").innerHTML = C.services.map((s) => `
  <article class="service">
    <div class="service-row"><h3>${s.name}</h3><span class="price">${s.price} €</span></div>
    <p class="muted small">${s.desc}</p>
    <span class="dur">ca. ${s.dur} Min.</span>
    <button class="book-this" data-service="${s.id}">Buchen →</button>
  </article>`).join("");
$$(".book-this").forEach((b) => b.addEventListener("click", () => { booking.prefill({ service: b.dataset.service }); booking.focus(); }));

/* ---------------- Team ---------------- */
(function team() {
  $("#teamGrid").innerHTML = C.barbers.map((b, i) => `
    <article class="barber" data-id="${b.id}">
      <div class="barber-photo" style="--bg-img:url('${b.img}')">
        <span class="barber-place">Platz ${i + 1}</span>
      </div>
      <div class="barber-body">
        <h3>${esc(b.name)}</h3>
        <p class="barber-tag">${esc(b.tag)} · <span class="gold">${esc(b.specialty)}</span></p>
        <p class="muted small">${esc(b.text)}</p>
        <p class="cuts-label">Signature-Cuts</p>
        <div class="cuts">
          ${b.cuts.map((c, k) => `<button type="button" class="cut" data-b="${b.id}" data-k="${k}"><span class="cut-img" data-snap="${b.id}-${k}"></span><span>${esc(c.label)}</span></button>`).join("")}
        </div>
        <p class="tiny muted">3D-Vorschau · echte Kunden-Fotos folgen</p>
        <button type="button" class="btn btn-gold btn-sm btn-block" data-book-barber="${b.id}">Bei ${esc(b.name)} buchen</button>
      </div>
    </article>`).join("");

  // Cut antippen → im Style-Studio öffnen
  $$(".cut").forEach((el) => el.addEventListener("click", () => {
    const c = barberById(el.dataset.b).cuts[+el.dataset.k];
    studio.set({ style: c.style, fade: c.fade, beard: c.beard });
    $("#studio").scrollIntoView({ behavior: "smooth" });
  }));
  $$("[data-book-barber]").forEach((el) => el.addEventListener("click", () => { booking.prefill({ barber: el.dataset.bookBarber }); booking.focus(); }));

  // 3D-Vorschaubilder erzeugen, sobald der Bereich in Sicht kommt
  const io = new IntersectionObserver(([e]) => {
    if (!e.isIntersecting || !window.HEAD) return;
    io.disconnect();
    HEAD.whenReady(run);
  }, { rootMargin: "300px" });
  io.observe($("#teamGrid"));
  function run() {
    const jobs = C.barbers.flatMap((b) => b.cuts.map((c, k) => [b.id, k, c]));
    (function next() {
      const j = jobs.shift(); if (!j) return;
      const url = HEAD.snapshot({ style: j[2].style, fade: j[2].fade, beard: j[2].beard, shape: "oval" });
      const el = $(`[data-snap="${j[0]}-${j[1]}"]`);
      if (url && el) el.style.backgroundImage = `url(${url})`;
      setTimeout(next, 30);
    })();
  }
})();

/* ---------------- Style-Studio ---------------- */
const studio = (() => {
  const H = window.HEAD;
  if (!H) return { set() {}, look: () => null };
  const st = H.state;
  const reco = () => H.RECO[st.shape];
  const swatch = (c, sel, name, val = c) => `<button type="button" class="swatch" style="--c:${c}" aria-pressed="${sel}" data-c="${val}" title="${name || c}" aria-label="${name || "Farbe"}"></button>`;

  function render() {
    const r = reco();
    $("#optShape").innerHTML = H.SHAPES.map((s) => `<button type="button" class="opt" data-k="shape" data-v="${s.id}" aria-pressed="${st.shape === s.id}">${s.name}</button>`).join("");
    $("#optSkin").innerHTML = H.SKINS.map((c, i) => swatch(c.s, st.skin === c.m, `Hautton ${i + 1}`, c.m)).join("");
    $("#optStyle").innerHTML = H.STYLES.map((s) => `<button type="button" class="opt style-opt" data-k="style" data-v="${s.id}" aria-pressed="${st.style === s.id}">${r.hair.includes(s.id) ? '<span class="reco">★</span>' : ""}${s.name}</button>`).join("");
    $("#optFade").innerHTML = H.FADES.map((f) => `<button type="button" class="opt" data-k="fade" data-v="${f.id}" aria-pressed="${st.fade === f.id}">${f.name}</button>`).join("");
    $("#optHairColor").innerHTML = H.HAIR_COLORS.map((c) => swatch(c.c, st.hair === c.c, c.n)).join("");
    $("#optBeard").innerHTML = H.BEARDS.map((b) => `<button type="button" class="opt" data-k="beard" data-v="${b.id}" aria-pressed="${st.beard === b.id}">${r.beard.includes(b.id) ? '<span class="reco">★</span>' : ""}${b.name}</button>`).join("");
    $("#optBeardColor").innerHTML = H.HAIR_COLORS.map((c) => swatch(c.c, st.beardColor === c.c, c.n)).join("");
    const L = look();
    $("#lookName").textContent = L.title;
    $("#lookTitle").textContent = L.title;
    $("#lookTip").innerHTML = `${L.tip} <span class="gold">${L.fits ? "★ Passt zu deiner Gesichtsform." : ""}</span><br><span class="muted">Empfohlen: ${esc(svcById(L.service).name)} · ${svcById(L.service).price} €</span>`;
  }
  function look() {
    const s = H.STYLES.find((x) => x.id === st.style), f = H.FADES.find((x) => x.id === st.fade), b = H.BEARDS.find((x) => x.id === st.beard);
    const hasBeard = !["none"].includes(st.beard);
    const service = hasBeard && st.beard !== "stubble" ? "combo" : st.fade !== "none" ? "fade" : s.svc;
    const title = `${s.name}${st.fade !== "none" ? ` · ${f.name} Fade` : ""}${hasBeard ? ` · ${b.name}` : ""}`;
    return { title, tip: s.tip, service, fits: reco().hair.includes(st.style), cfg: { ...st } };
  }
  function set(patch) {
    // Neuer Haarschnitt bringt seinen typischen Fade mit
    if (patch.style && !("fade" in patch)) patch.fade = H.STYLES.find((s) => s.id === patch.style).fade;
    if (patch.hair && st.beardColor === st.hair && !("beardColor" in patch)) patch.beardColor = patch.hair;
    H.set(patch); render();
  }

  $(".studio-panel").addEventListener("click", (e) => {
    const o = e.target.closest(".opt"); if (o) return set({ [o.dataset.k]: o.dataset.v });
    const sw = e.target.closest(".swatch"); if (!sw) return;
    const box = sw.parentElement.id;
    set(box === "optSkin" ? { skin: sw.dataset.c } : box === "optHairColor" ? { hair: sw.dataset.c } : { beardColor: sw.dataset.c });
  });
  $$(".tab").forEach((t) => t.addEventListener("click", () => {
    $$(".tab").forEach((x) => x.setAttribute("aria-selected", x === t));
    $$(".tab-body").forEach((b) => (b.hidden = b.dataset.body !== t.dataset.tab));
  }));
  $("#bookLook").addEventListener("click", () => {
    const L = look();
    booking.prefill({ service: L.service, note: `Look aus dem Style-Studio: ${L.title}` });
    booking.focus();
  });
  $("#saveLook").addEventListener("click", () => {
    const acc = account.get();
    if (!acc) { account.open("Leg ein Konto an, um deinen Look zu speichern."); return; }
    acc.look = look(); account.save(acc);
    $("#saveLook").textContent = "✓ Gemerkt";
    setTimeout(() => ($("#saveLook").textContent = "Im Konto merken"), 1800);
  });
  render();
  return { set, look };
})();

/* ---------------- Kundenkonto (Demo: nur auf diesem Gerät) ---------------- */
const account = (() => {
  const KEY = "axaray-account";
  const get = () => store.get(KEY);
  const save = (a) => { store.set(KEY, a); renderStrip(); booking?.fillFromAccount?.(); };
  const bookings = () => store.get("axaray-bookings") || [];

  function open(msg = "") {
    const a = get(), body = $("#accountBody");
    if (!a) {
      body.innerHTML = `
        <h3 id="accTitle">Kundenkonto anlegen</h3>
        <p class="muted small">${esc(msg || "Schneller buchen, Zahlungsart speichern, Termine im Blick.")}</p>
        <form id="accForm" class="fields acc-fields">
          <label class="full">Name<input name="name" autocomplete="name" required></label>
          <label class="full">Telefon<input name="phone" type="tel" autocomplete="tel" required></label>
          <label class="full">E-Mail<input name="email" type="email" autocomplete="email" required></label>
          <label class="full">Bevorzugte Zahlung
            <select name="pay">${C.payment.methods.map((m) => `<option value="${m.id}">${m.name}</option>`).join("")}<option value="vorort">Vor Ort bezahlen</option></select>
          </label>
          <button class="btn btn-gold btn-block full" type="submit">Konto anlegen</button>
        </form>
        <p class="tiny muted">Demo: Daten bleiben nur auf diesem Gerät. Live: Login per E-Mail-Code, Zahlungsdaten sicher beim Zahlungsanbieter.</p>`;
      $("#accForm").addEventListener("submit", (e) => {
        e.preventDefault(); const f = e.target;
        if (!f.name.value.trim() || !f.phone.value.trim() || !/@/.test(f.email.value)) return;
        save({ name: f.name.value.trim(), phone: f.phone.value.trim(), email: f.email.value.trim(), pay: f.pay.value, since: new Date().toISOString() });
        open();
      });
    } else {
      const list = bookings().slice().reverse();
      body.innerHTML = `
        <h3 id="accTitle">Hallo ${esc(a.name.split(" ")[0])} 👋</h3>
        <p class="muted small">${esc(a.email)} · ${esc(a.phone)}</p>
        <div class="acc-box"><span class="muted small">Bevorzugte Zahlung</span><b>${esc((C.payment.methods.find((m) => m.id === a.pay) || { name: "Vor Ort" }).name)}</b></div>
        ${a.look ? `<div class="acc-box"><span class="muted small">Gemerkter Look</span><b>${esc(a.look.title)}</b><button class="btn btn-ghost btn-sm" id="accLook" type="button">Ansehen</button></div>` : ""}
        <h4>Deine Termine</h4>
        <div class="acc-list">${list.length ? list.map((b) => `
          <div class="acc-booking"><div><b>${esc(b.service)}</b><span class="muted small">${fmtDate(new Date(b.start))}, ${fmtTime(new Date(b.start).getHours() * 60 + new Date(b.start).getMinutes())} · ${esc(b.barber)}</span></div>
          <span class="badge ${b.paid ? "ok" : ""}">${b.paid ? "bezahlt" : "vor Ort"}</span></div>`).join("") : '<p class="muted small">Noch keine Termine.</p>'}</div>
        <div class="acc-actions"><a href="#termin" class="btn btn-gold btn-sm" data-close>Neuen Termin buchen</a><button class="btn btn-link" id="accOut" type="button">Abmelden</button></div>`;
      $("#accOut").addEventListener("click", () => { store.del(KEY); renderStrip(); open(); });
      $("#accLook")?.addEventListener("click", () => { studio.set(a.look.cfg); closeModal($("#accountModal")); $("#studio").scrollIntoView({ behavior: "smooth" }); });
    }
    openModal("#accountModal");
  }
  function renderStrip() {
    const a = get();
    $("#accountStrip").innerHTML = a
      ? `<span>👤 Angemeldet als <b>${esc(a.name)}</b></span><button type="button" class="btn-link" data-open-account>Konto</button>`
      : `<span>Schneller buchen mit Kundenkonto</span><button type="button" class="btn-link" data-open-account>Anmelden / Konto anlegen</button>`;
  }
  document.addEventListener("click", (e) => { if (e.target.closest("[data-open-account]")) open(); });
  renderStrip();
  return { get, save, open };
})();

/* ---------------- Terminbuchung + Bezahlung ---------------- */
const booking = (() => {
  const state = { service: null, barber: "any", date: null, time: null, method: C.payment.methods[0].id };
  const chips = $("#serviceChips"), barberChips = $("#barberChips"), days = $("#dayPicker"), slots = $("#slotPicker"), form = $("#bookingForm");

  chips.innerHTML = C.services.map((s) => `<button type="button" class="chip" data-id="${s.id}" aria-pressed="false">${s.name}<small>${s.price} € · ${s.dur} Min.</small></button>`).join("");
  chips.addEventListener("click", (e) => { const b = e.target.closest(".chip"); if (b) selectService(b.dataset.id); });

  barberChips.innerHTML = [{ id: "any", name: "Egal – wer frei ist", specialty: "schnellster Termin" }, ...C.barbers]
    .map((b) => `<button type="button" class="chip" data-id="${b.id}" aria-pressed="${b.id === "any"}">${esc(b.name)}<small>${esc(b.specialty)}</small></button>`).join("");
  barberChips.addEventListener("click", (e) => { const b = e.target.closest(".chip"); if (b) selectBarber(b.dataset.id); });

  const dayList = [...Array(21)].map((_, i) => { const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() + i); return d; });
  days.innerHTML = dayList.map((d, i) => {
    const closed = !C.hours[d.getDay()] || (i === 0 && availableSlots(d).length === 0);
    const top = i === 0 ? "Heute" : i === 1 ? "Morgen" : DAYS[d.getDay()].slice(0, 2);
    return `<button type="button" class="day" data-i="${i}" aria-pressed="false" ${closed ? "disabled" : ""}><small>${top}</small><b>${d.getDate()}</b><small>${d.toLocaleDateString("de-DE", { month: "short" })}</small></button>`;
  }).join("");
  days.addEventListener("click", (e) => { const b = e.target.closest(".day"); if (b && !b.disabled) selectDate(dayList[+b.dataset.i]); });

  // Zahlungsarten
  const ico = { paypal: "P", applepay: "Pay", googlepay: "G", card: "▭", klarna: "K" };
  $("#payMethods").innerHTML = C.payment.methods.map((m) => `
    <button type="button" class="pay-method pm-${m.id}" data-id="${m.id}" aria-pressed="${m.id === state.method}"><span class="pm-ico">${ico[m.id] || "€"}</span>${m.name}</button>`).join("");
  $("#payMethods").addEventListener("click", (e) => { const b = e.target.closest(".pay-method"); if (b) { state.method = b.dataset.id; $$(".pay-method").forEach((x) => x.setAttribute("aria-pressed", x === b)); update(); } });
  $$('input[name="paymode"]').forEach((r) => r.addEventListener("change", update));
  const payOnline = () => $('input[name="paymode"]:checked').value === "online";

  function availableSlots(d) {
    const h = C.hours[d.getDay()]; if (!h) return [];
    const dur = state.service ? svcById(state.service).dur : C.slotMinutes;
    const now = new Date(), isToday = d.toDateString() === now.toDateString(), nowMin = now.getHours() * 60 + now.getMinutes() + 30;
    const taken = new Set((store.get("axaray-bookings") || []).filter((b) => new Date(b.start).toDateString() === d.toDateString() && (state.barber === "any" ? false : b.barberId === state.barber)).map((b) => { const s = new Date(b.start); return s.getHours() * 60 + s.getMinutes(); }));
    const out = [];
    for (let m = h[0]; m + dur <= h[1]; m += C.slotMinutes) if ((!isToday || m >= nowMin) && !taken.has(m)) out.push(m);
    return out;
  }
  function selectService(id) { state.service = id; $$(".chip", chips).forEach((c) => c.setAttribute("aria-pressed", c.dataset.id === id)); if (state.date) renderSlots(); update(); }
  function selectBarber(id) { state.barber = id; $$(".chip", barberChips).forEach((c) => c.setAttribute("aria-pressed", c.dataset.id === id)); if (state.date) renderSlots(); update(); }
  function selectDate(d) { state.date = d; state.time = null; $$(".day", days).forEach((b) => b.setAttribute("aria-pressed", dayList[+b.dataset.i].getTime() === d.getTime())); renderSlots(); update(); }
  function selectTime(m) { state.time = m; $$(".slot", slots).forEach((b) => b.setAttribute("aria-pressed", +b.dataset.m === m)); update(); }
  function renderSlots() {
    const list = availableSlots(state.date);
    if (!list.includes(state.time)) state.time = null;
    slots.innerHTML = list.length
      ? list.map((m) => `<button type="button" class="slot" data-m="${m}" aria-pressed="${m === state.time}">${fmtTime(m)}</button>`).join("")
      : `<p class="muted small">An diesem Tag ist nichts mehr frei – komm gern ohne Termin vorbei.</p>`;
  }
  slots.addEventListener("click", (e) => { const b = e.target.closest(".slot"); if (b) selectTime(+b.dataset.m); });

  function update() {
    const s = svcById(state.service), parts = [];
    if (s) parts.push(`<b>${s.name}</b>`);
    if (state.barber !== "any") parts.push(esc(barberById(state.barber).name));
    if (state.date) parts.push(fmtDate(state.date));
    if (state.time != null) parts.push(`${fmtTime(state.time)} Uhr`);
    const total = s ? `<span class="sum-total">${payOnline() ? "Jetzt zahlen" : "Vor Ort"}: <b>${euro(s.price)}</b></span>` : "";
    $("#summary").innerHTML = parts.length ? `${parts.join(" · ")}${total}` : "Noch nichts gewählt.";
    $("#payMethods").hidden = !payOnline();
    const m = C.payment.methods.find((x) => x.id === state.method);
    $("#submitBtn").textContent = payOnline() ? (s ? `Buchen & ${euro(s.price)} mit ${m.name} zahlen` : "Buchen & bezahlen") : "Termin verbindlich buchen";
  }

  function fillFromAccount() {
    const a = account.get(); if (!a) return;
    if (!form.name.value) form.name.value = a.name;
    if (!form.phone.value) form.phone.value = a.phone;
    if (!form.email.value) form.email.value = a.email;
    if (a.pay === "vorort") $('input[value="vorort"]').checked = true;
    else if (C.payment.methods.some((m) => m.id === a.pay)) { state.method = a.pay; $$(".pay-method").forEach((x) => x.setAttribute("aria-pressed", x.dataset.id === a.pay)); }
    update();
  }

  function prefill({ service, barber, date, time, note } = {}) {
    if (form.hidden) { form.hidden = false; $("#bookingDone").hidden = true; }
    if (service) selectService(service);
    if (barber) selectBarber(barber);
    if (date) { const m = dayList.find((d) => d.getTime() === date.getTime()); if (m && C.hours[m.getDay()]) selectDate(m); }
    if (time != null && state.date && availableSlots(state.date).includes(time)) selectTime(time);
    if (note) form.note.value = note;
    return { ...state };
  }
  const focus = () => $("#termin").scrollIntoView({ behavior: "smooth" });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("#formError");
    const name = form.name.value.trim(), phone = form.phone.value.trim(), email = form.email.value.trim(), note = form.note.value.trim();
    const fail = (t) => { err.textContent = t; };
    if (!state.service) return fail("Bitte eine Leistung wählen.");
    if (!state.date) return fail("Bitte einen Tag wählen.");
    if (state.time == null) return fail("Bitte eine Uhrzeit wählen.");
    if (name.length < 2) return fail("Bitte deinen Namen angeben.");
    if (phone.replace(/\D/g, "").length < 6) return fail("Bitte eine gültige Telefonnummer angeben.");
    if (payOnline() && !/@/.test(email)) return fail("Für die Online-Zahlung brauchen wir deine E-Mail (Beleg).");
    err.textContent = "";

    const s = svcById(state.service);
    const start = new Date(state.date); start.setMinutes(state.time);
    let barber = state.barber;
    if (barber === "any") barber = C.barbers[(start.getDate() + state.time / 30) % C.barbers.length | 0].id; // Demo-Zuteilung
    const req = {
      id: "AX" + Date.now().toString(36).toUpperCase(), service: s.name, serviceId: s.id, price: s.price, duration: s.dur,
      start: start.toISOString(), barberId: barber, barber: barberById(barber).name, name, phone, email, note,
      payment: payOnline() ? state.method : "vorort", paid: false, createdAt: new Date().toISOString(),
    };

    if (payOnline()) {
      const ok = await pay(req);
      if (!ok) return;
      req.paid = true;
    }
    let sent = false;
    if (C.bookingWebhook) {
      try { sent = (await fetch(C.bookingWebhook, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req) })).ok; } catch {}
    }
    const list = store.get("axaray-bookings") || []; list.push(req); store.set("axaray-bookings", list);
    done(req, start, sent);
  });

  // Zahlung: echter Checkout (falls eingerichtet) oder Demo-Bezahlfenster
  function pay(req) {
    const P = C.payment;
    if (!P.demo && P.paymentLinks[req.serviceId]) {
      const url = new URL(P.paymentLinks[req.serviceId]);
      url.searchParams.set("client_reference_id", req.id); if (req.email) url.searchParams.set("prefilled_email", req.email);
      store.set("axaray-pending", req); location.href = url; return Promise.resolve(false);
    }
    if (!P.demo && P.checkoutEndpoint) {
      return fetch(P.checkoutEndpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req) })
        .then((r) => r.json()).then(({ url }) => { store.set("axaray-pending", req); location.href = url; return false; })
        .catch(() => { $("#formError").textContent = "Zahlung gerade nicht möglich – bitte vor Ort bezahlen wählen."; return false; });
    }
    return new Promise((resolve) => {
      const m = P.methods.find((x) => x.id === req.payment);
      $("#payBody").innerHTML = `
        <p class="eyebrow">Sichere Zahlung</p>
        <h3 id="payTitle">${esc(m.name)}</h3>
        <div class="pay-line"><span>${esc(req.service)} · ${esc(req.barber)}</span><b>${euro(req.price)}</b></div>
        <div class="pay-line muted small"><span>${fmtDate(new Date(req.start))}, ${fmtTime(state.time)} Uhr</span><span>inkl. MwSt.</span></div>
        <div class="pay-line total"><span>Gesamt</span><b>${euro(req.price)}</b></div>
        <button class="btn btn-block pay-go pm-${m.id}" id="payGo" type="button">${m.id === "applepay" ? "Mit Apple Pay bezahlen" : m.id === "googlepay" ? "Mit Google Pay bezahlen" : `Mit ${esc(m.name)} bezahlen`}</button>
        <p class="tiny muted center">Demo-Modus: Es wird kein Geld abgebucht. Live läuft die Zahlung über den Zahlungsanbieter des Salons.</p>`;
      const modal = $("#payModal");
      let settled = false;
      const finish = (v) => { if (settled) return; settled = true; obs.disconnect(); closeModal(modal); resolve(v); };
      const obs = new MutationObserver(() => modal.hidden && finish(false));
      obs.observe(modal, { attributes: true, attributeFilter: ["hidden"] });
      $("#payGo").addEventListener("click", () => {
        $("#payGo").disabled = true; $("#payGo").innerHTML = '<span class="spinner"></span> Zahlung wird bestätigt …';
        setTimeout(() => finish(true), 1200);
      });
      openModal("#payModal");
    });
  }

  function done(req, start, sent) {
    const dateText = fmtDate(start), time = fmtTime(state.time);
    const msg = `Hallo Axaray Barbers, Termin ${req.id}:\n${req.service} bei ${req.barber}\n${dateText}, ${time} Uhr\nName: ${req.name}\nTelefon: ${req.phone}${req.note ? `\nWunsch: ${req.note}` : ""}\nZahlung: ${req.paid ? "online bezahlt" : "vor Ort"}`;
    const actions = [];
    if (!sent && C.whatsapp) actions.push(`<a class="btn btn-gold" target="_blank" rel="noopener" href="https://wa.me/${C.whatsapp}?text=${encodeURIComponent(msg)}">Bestätigung per WhatsApp</a>`);
    if (!sent && C.email) actions.push(`<a class="btn btn-ghost" href="mailto:${C.email}?subject=${encodeURIComponent("Termin " + req.id)}&body=${encodeURIComponent(msg)}">Per E-Mail senden</a>`);
    actions.push(`<button class="btn btn-ghost" type="button" id="icsBtn">In meinen Kalender</button>`);
    actions.push(`<a class="btn btn-ghost" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(C.mapsQuery)}">Route planen</a>`);
    $("#doneTitle").textContent = req.paid ? "Gebucht & bezahlt!" : "Termin gebucht!";
    $("#doneText").innerHTML = `Danke ${esc(req.name.split(" ")[0])}! <b>${esc(req.service)}</b> bei <b>${esc(req.barber)}</b><br> am <b>${dateText}</b> um <b>${time} Uhr</b>.<br>
      <span class="muted small">Buchungsnummer ${req.id} · ${req.paid ? `${euro(req.price)} bezahlt – Beleg an ${esc(req.email)}` : "Bezahlung vor Ort"}</span>
      ${C.bookingWebhook && !sent ? '<br><span class="small" style="color:#ffb547">Übermittlung fehlgeschlagen – bitte kurz anrufen.</span>' : ""}
      ${!C.bookingWebhook && C.draft ? '<br><span class="tiny muted">Entwurf: Buchungen werden noch nicht an den Salon übertragen.</span>' : ""}`;
    $("#doneActions").innerHTML = actions.join("");
    $("#icsBtn").addEventListener("click", () => downloadIcs(req, start));
    form.hidden = true; $("#bookingDone").hidden = false; focus();
  }
  $("#newBooking").addEventListener("click", () => { form.hidden = false; $("#bookingDone").hidden = true; state.time = null; if (state.date) renderSlots(); update(); });

  function downloadIcs(req, start) {
    const end = new Date(start.getTime() + req.duration * 60000);
    const z = (d) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
    const ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Axaray Barbers//DE", "BEGIN:VEVENT", `UID:${req.id}@axaray-barbers`, `DTSTAMP:${z(new Date())}`,
      `DTSTART:${z(start)}`, `DTEND:${z(end)}`, `SUMMARY:${req.service} – Axaray Barbers`, `LOCATION:${C.address}`,
      `DESCRIPTION:Bei ${req.barber} · Buchung ${req.id}`, "BEGIN:VALARM", "TRIGGER:-PT2H", "ACTION:DISPLAY", "DESCRIPTION:Termin bei Axaray Barbers", "END:VALARM", "END:VEVENT", "END:VCALENDAR"].join("\r\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([ics], { type: "text/calendar" })); a.download = "axaray-termin.ics"; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  update(); fillFromAccount();
  return { prefill, focus, availableSlots, fillFromAccount };
})();

/* ---------------- Anfahrt: Adler-Ansicht + Navi-Apps ---------------- */
(function directions() {
  const q = encodeURIComponent(C.mapsQuery);
  $("#navGoogle").href = `https://www.google.com/maps/dir/?api=1&destination=${q}&travelmode=driving`;
  $("#navApple").href = `https://maps.apple.com/?daddr=${q}&dirflg=d`;
  $("#mapConsent").addEventListener("click", () => {
    $("#aerialFrame").innerHTML = `<iframe title="Luftbild Axaray Barbers" loading="lazy" referrerpolicy="no-referrer-when-downgrade"
      src="https://maps.google.com/maps?q=${q}&t=k&z=19&output=embed"></iframe><span class="aerial-pin">📍 Axaray Barbers</span>`;
  });
})();

/* ---------------- Scroll-Reveal ---------------- */
const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: .12 });
$$(".section-head, .service, .barber, .contact-card, .booking-card, .rating-card, .studio-wrap, .aerial").forEach((el) => { el.classList.add("reveal"); io.observe(el); });

/* ---------------- Sprachassistent ---------------- */
(function voiceAgent() {
  const panel = $("#vaPanel"), log = $("#vaLog"), input = $("#vaText"), mic = $("#vaMic");
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, greeted = false, voiceOn = false;
  const toggle = (open) => {
    panel.hidden = !open;
    if (open && !greeted) { greeted = true; bot(`Hey, willkommen bei Axaray Barbers! ${openState().text}.\nFrag mich nach Preisen, Barbern, Anfahrt – oder sag z. B. „Fade morgen um 15 Uhr“.`, false); }
    if (open) setTimeout(() => input.focus(), 50);
  };
  $("#vaFab").addEventListener("click", () => toggle(panel.hidden));
  $("#vaClose").addEventListener("click", () => toggle(false));
  const quick = ["Termin morgen", "Preise", "Welcher Look passt?", "Anfahrt", "Bezahlung"];
  $("#vaQuick").innerHTML = quick.map((q) => `<button type="button">${q}</button>`).join("");
  $("#vaQuick").addEventListener("click", (e) => { if (e.target.tagName === "BUTTON") handle(e.target.textContent); });

  function add(text, who) { const d = document.createElement("div"); d.className = `msg ${who}`; d.textContent = text; log.appendChild(d); log.scrollTop = log.scrollHeight; }
  function bot(text, speak = voiceOn) {
    add(text, "bot");
    if (speak && "speechSynthesis" in window) {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text.replace(/[•→✂🅿★]/g, "")); u.lang = "de-DE"; u.rate = 1.03;
      const v = speechSynthesis.getVoices().find((x) => x.lang.startsWith("de")); if (v) u.voice = v;
      speechSynthesis.speak(u);
    }
  }
  $("#vaForm").addEventListener("submit", (e) => { e.preventDefault(); const t = input.value.trim(); if (!t) return; input.value = ""; handle(t); });
  if (!SR) { mic.title = "Spracheingabe wird von diesem Browser nicht unterstützt"; mic.style.opacity = .4; }
  mic.addEventListener("click", () => {
    if (!SR) return bot("Dein Browser unterstützt leider keine Spracheingabe – schreib mir einfach.", false);
    if (rec) { rec.stop(); return; }
    rec = new SR(); rec.lang = "de-DE"; rec.interimResults = false;
    rec.onresult = (e) => { voiceOn = true; handle(e.results[0][0].transcript); };
    rec.onend = rec.onerror = () => { mic.classList.remove("listening"); rec = null; };
    mic.classList.add("listening"); rec.start();
  });

  const norm = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ß/g, "ss");
  function parseDate(t) {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const plus = (n) => { const d = new Date(today); d.setDate(d.getDate() + n); return d; };
    if (/ubermorgen/.test(t)) return plus(2);
    if (/morgen/.test(t)) return plus(1);
    if (/heute|jetzt|gleich/.test(t)) return plus(0);
    const i = ["sonntag", "montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag"].findIndex((n) => t.includes(n));
    if (i >= 0) { let diff = (i - today.getDay() + 7) % 7; if (diff === 0) diff = 7; return plus(diff); }
    return null;
  }
  function parseTime(t) {
    const halb = t.match(/halb (\d{1,2})/);
    if (halb) { const h = +halb[1] - 1; return (h < 8 ? h + 12 : h) * 60 + 30; }
    const m = t.match(/(\d{1,2})[:.](\d{2})/) || t.match(/um (\d{1,2})(?: uhr)?(?: (\d{2}))?/) || t.match(/(\d{1,2}) uhr(?: (\d{2}))?/);
    if (!m) return null;
    let h = +m[1]; const min = m[2] ? +m[2] : 0; if (h < 8) h += 12;
    return h * 60 + (min >= 30 ? 30 : 0);
  }
  function parseService(t) {
    if (/kind/.test(t)) return "kids";
    if (/(haar|schnitt|fade).*bart|bart.*(haar|schnitt|fade)|komplett|beides|combo/.test(t)) return "combo";
    if (/fade|ubergang|skin/.test(t)) return "fade";
    if (/bart|rasur|kontur/.test(t)) return "beard";
    if (/wachs|gesicht|towel/.test(t)) return "wax";
    if (/haarschnitt|schneiden|haare/.test(t)) return "cut";
    return null;
  }
  const go = (sel) => $(sel).scrollIntoView({ behavior: "smooth" });

  function handle(raw) {
    add(raw, "me");
    const t = norm(raw), svc = parseService(t), date = parseDate(t), time = parseTime(t);
    const wantsBooking = /termin|buchen|reservier|frei|platz|kommen|vorbei/.test(t) || (svc && (date || time != null));
    if (/hallo|hi\b|hey|servus|guten|selam|merhaba/.test(t) && t.length < 20) return bot("Hey! Wie kann ich dir helfen – Termin, Preise oder Anfahrt?");
    if (/ohne termin|walk|spontan|einfach vorbei/.test(t)) return bot("Ja! Du kannst jederzeit ohne Termin vorbeikommen. Mit Online-Termin sparst du dir die Wartezeit.");
    if (/bezahl|zahl|paypal|apple|google pay|karte|klarna|bar\b/.test(t)) return bot("Du kannst online beim Buchen zahlen – PayPal, Apple Pay, Google Pay, Karte oder Klarna – oder ganz normal vor Ort.");
    if (/aschaffenburg|wie lange|wie weit|fahrt|anfahrt|route|navi/.test(t)) { go("#kontakt"); return bot("Von Aschaffenburg sind es nur ca. 10 Minuten mit dem Auto. Unten kannst du die Route direkt in Google Maps oder Apple Karten starten."); }
    if (/park/.test(t)) return bot("Direkt gegenüber gibt es Parkplätze – zwei Stunden kosten nur 1,50 €.");
    if (/wo |adresse|standort|finde/.test(t)) { go("#kontakt"); return bot(`Du findest uns in der ${C.address} – ca. 10 Minuten von Aschaffenburg.`); }
    if (/telefon|nummer|anruf|erreich/.test(t)) return bot(`Ruf uns an unter ${C.phoneDisplay}.`);
    if (/look|passt|steht mir|gesicht|frisur|style/.test(t) && !wantsBooking) { go("#studio"); return bot("Probier’s im 3D Style-Studio aus: Gesichtsform wählen, dann zeigen dir die ★ welche Schnitte und Bärte zu dir passen."); }
    if (/barber|friseur|team|wer schneidet/.test(t) && !wantsBooking) { go("#team"); return bot(C.barbers.map((b, i) => `• Platz ${i + 1}: ${b.name} – ${b.specialty}`).join("\n")); }
    if (/rundgang|laden|salon|innen|aussehen/.test(t)) { go("#rundgang"); return bot("Scroll einfach durch den virtuellen Rundgang – vom Schaufenster bis zu den drei Plätzen."); }
    if (/offnung|offen|geoffnet|schliess|wann.*(auf|offen)/.test(t) && !wantsBooking) return bot(`${openState().text}.\nMo–Fr: 09:00–18:30\nSa: 09:00–16:30\nSo: geschlossen`);
    if (/preis|kost|teuer|euro|€/.test(t)) {
      if (svc) { const s = svcById(svc); return bot(`${s.name} kostet ${s.price} € und dauert ca. ${s.dur} Minuten. Soll ich dir einen Termin eintragen?`); }
      return bot(C.services.map((s) => `• ${s.name}: ${s.price} €`).join("\n"));
    }
    if (/bewert|rezension/.test(t)) return bot("Wir haben 5,0 Sterne bei 34 Google-Bewertungen. Warst du schon da? Über „Jetzt bewerten“ geht’s in 30 Sekunden – danke!");
    if (wantsBooking) {
      const st = booking.prefill({ service: svc, date, time });
      booking.focus();
      if (date && !C.hours[date.getDay()]) return bot("Sonntags haben wir leider geschlossen. Wie wäre Montag oder Samstag?");
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
      if (missing.length) return bot(`Gern! Ich hab das Formular schon vorbereitet. Sag mir noch: ${missing.join(", ")}?`);
      return bot(`Perfekt: ${svcById(st.service).name} am ${fmtDate(st.date)} um ${fmtTime(st.time)} Uhr ist eingetragen. Jetzt nur noch Name, Telefon und Zahlungsart – fertig.`);
    }
    if (svc) { const s = svcById(svc); return bot(`${s.name}: ${s.desc}, ${s.price} €. Willst du dafür einen Termin? Sag z. B. „morgen um 14 Uhr“.`); }
    bot(`Das kann ich dir leider nicht sicher beantworten – ruf am besten kurz an: ${C.phoneDisplay}.`);
  }
})();

/* ---------------- Film (MP4) ---------------- */
(function filmVideo() {
  const v = $("#filmVideo"); if (!v) return;
  document.addEventListener("click", (e) => {
    if (!e.target.closest("[data-film]")) return;
    const tall = matchMedia("(orientation: portrait)").matches;
    const src = `film/axaray-rundgang-${tall ? "9x16" : "16x9"}.mp4`;
    if (!v.src.endsWith(src)) v.src = src;
    $("#filmModal").classList.toggle("tall", tall);
    openModal("#filmModal"); v.play().catch(() => {});
  });
  new MutationObserver(() => $("#filmModal").hidden && v.pause()).observe($("#filmModal"), { attributes: true });
})();
