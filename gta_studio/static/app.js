"use strict";
// GTA TikTok Studio – Oberfläche. Kein Framework, keine fremden Skripte.

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => Number(n || 0).toLocaleString("de-DE");
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "");
let META = null, FACTS = [], VIDEOS = [], SETTINGS = {};

async function api(path, method = "GET", body) {
  const opt = { method, headers: { "X-Studio": "1" } };
  if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  const r = await fetch("/api/" + path, opt);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { toast(data.error || "Fehler " + r.status); throw new Error(data.error); }
  return data;
}
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 2600); }
function formData(form) {
  const o = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "number") { if (el.value !== "") o[el.name] = Number(el.value); }
    else o[el.name] = el.value;
  }
  return o;
}
function fillForm(form, data) { for (const el of form.elements) if (el.name && data[el.name] !== undefined) el.value = Array.isArray(data[el.name]) ? JSON.stringify(data[el.name]) : data[el.name]; }
function badge(key, label) { return `<span class="badge b-${esc(key)}">${esc(label || key)}</span>`; }
function statusLabel(k) { return (META.fact_status.find((s) => s.key === k) || {}).label || k; }
function download(name, text, type = "text/plain") {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
async function copy(text) { try { await navigator.clipboard.writeText(text); toast("Kopiert"); } catch { download("text.txt", text); } }
function bar(pct) { const w = document.createElement("div"); w.className = "bar"; const i = document.createElement("i"); i.style.width = Math.max(0, Math.min(100, pct)) + "%"; w.append(i); return w; }

// ------------------------------------------------------------------ Tabs
const LOADERS = {};
function showTab(name) {
  $$("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".tab").forEach((s) => s.classList.toggle("active", s.id === "tab-" + name));
  try { localStorage.setItem("tab", name); } catch {}
  (LOADERS[name] || (() => {}))();
}
$("#tabs").addEventListener("click", (e) => { if (e.target.dataset.tab) showTab(e.target.dataset.tab); });

// ------------------------------------------------------------------ Cockpit
LOADERS.dashboard = async () => {
  const d = await api("dashboard");
  SETTINGS = d.settings;
  $("#handle").textContent = d.settings.account_handle;
  $("#countdown").textContent = d.countdown.released ? `🎮 GTA 6 ist draußen · ${d.countdown.label}` : `⏳ GTA 6: ${d.countdown.label}`;
  const k = [
    [`${d.posted_today} / ${d.posts_per_day}`, "heute gepostet"],
    [fmt(d.totals.views), "Aufrufe gesamt (gemessen)"],
    [fmt(d.totals.followers_gained), "neue Follower (gemessen)"],
    [`${d.facts.unused} / ${d.facts.total}`, "ungenutzte Fakten"],
  ];
  $("#dash-kpis").innerHTML = k.map(([v, l]) => `<div class="kpi"><div class="v">${esc(v)}</div><div class="l">${esc(l)}</div></div>`).join("");
  const up = d.overdue.map((v) => ({ ...v, _over: true })).concat(d.upcoming);
  $("#dash-upcoming").innerHTML = up.length ? up.map((v) => videoItem(v, v._over ? "überfällig" : "")).join("")
    : `<p class="muted">Nichts geplant. Geh auf <b>Planung</b> und lege die Launch-Woche an.</p>`;
  $("#dash-insights").innerHTML = d.insights.map((t) => `<li>${esc(t)}</li>`).join("");
  $("#dash-metrics").innerHTML = d.needs_metrics.length ? d.needs_metrics.map((v) => `<div class="item"><span>${esc(v.title)}</span><button class="small" data-metric="${v.id}">Zahlen eintragen</button></div>`).join("") : `<p class="muted">Alles erfasst.</p>`;
  $("#dash-pipeline").innerHTML = META.video_status.map((s) => `<div><b>${d.pipeline[s] || 0}</b><span>${esc(s)}</span></div>`).join("");
  $("#dash-checklist").innerHTML = META.checklist.map((c, i) => `<li><input type="checkbox" id="chk${i}"><label class="inline" for="chk${i}">${esc(c)}</label></li>`).join("");
};
function videoItem(v, flag, del = false) {
  const when = v.planned_at ? new Date(v.planned_at).toLocaleString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "ohne Termin";
  return `<div class="item"><div><div class="t">${esc(v.title)}</div><div class="s">${esc(when)} · ${esc(v.series || "–")} ${flag ? `· <span class="hot">${esc(flag)}</span>` : ""}</div></div>
  <div class="actions">${badge(v.status)}<button class="small" data-edit="${v.id}">Öffnen</button>${v.status !== "gepostet" ? `<button class="small" data-posted="${v.id}">Gepostet ✓</button>` : ""}${del ? `<button class="small danger" data-delvideo="${v.id}">✕</button>` : ""}</div></div>`;
}
document.addEventListener("click", async (e) => {
  const t = e.target;
  if (t.dataset.edit) openVideo(Number(t.dataset.edit));
  if (t.dataset.metric) { showTab("analytics"); setTimeout(() => { $("#metric-video").value = t.dataset.metric; }, 200); }
  if (t.dataset.posted) {
    const url = prompt("Link zum TikTok (optional):", "") ?? null;
    if (url === null) return;
    await api(`videos/${t.dataset.posted}/posted`, "POST", { tiktok_url: url.trim() });
    toast("Als gepostet markiert. Morgen Zahlen eintragen!");
    reloadActive();
  }
  if (t.dataset.delvideo && confirm("Video wirklich löschen?")) { await api("videos/" + t.dataset.delvideo, "DELETE"); reloadActive(); }
});
function reloadActive() { const a = $("#tabs button.active"); if (a) LOADERS[a.dataset.tab]?.(); }

// ------------------------------------------------------------------ Faktenbank
LOADERS.facts = async () => { FACTS = await api("facts"); renderFacts(); };
function renderFacts() {
  const q = $("#fact-search").value.toLowerCase(), st = $("#fact-filter").value;
  const rows = FACTS.filter((f) => (!st || f.status === st) && (!q || (f.title + " " + f.detail).toLowerCase().includes(q)));
  $("#fact-list").innerHTML = rows.map((f) => {
    const url = safeUrl(f.source_url);
    const src = url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(f.source_name || "Link")}</a>` : esc(f.source_name || "– fehlt –");
    return `<tr><td><b>${esc(f.title)}</b><div class="muted">${esc(f.detail)}</div></td><td>${badge(f.status, statusLabel(f.status))}</td>
    <td>${src}</td><td>${f.used_count}×</td><td class="actions"><button class="small" data-fedit="${f.id}">Bearbeiten</button>
    <button class="small" data-fuse="${f.id}">→ Skript</button><button class="small danger" data-fdel="${f.id}">✕</button></td></tr>`;
  }).join("") || `<tr><td colspan="5" class="muted">Keine Treffer.</td></tr>`;
}
$("#fact-search").addEventListener("input", renderFacts);
$("#fact-filter").addEventListener("change", renderFacts);
$("#fact-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const d = formData(e.target); const id = d.id; delete d.id;
  await (id ? api("facts/" + id, "PUT", d) : api("facts", "POST", d));
  e.target.reset(); e.target.elements.id.value = ""; toast("Gespeichert"); LOADERS.facts();
});
$("#fact-list").addEventListener("click", async (e) => {
  const t = e.target;
  if (t.dataset.fedit) { fillForm($("#fact-form"), FACTS.find((f) => f.id == t.dataset.fedit)); window.scrollTo({ top: 0, behavior: "smooth" }); }
  if (t.dataset.fdel && confirm("Fakt löschen?")) { await api("facts/" + t.dataset.fdel, "DELETE"); LOADERS.facts(); }
  if (t.dataset.fuse) { const f = FACTS.find((x) => x.id == t.dataset.fuse); showTab("studio"); setTimeout(() => preselect(f.title, [f.id]), 150); }
});

// ------------------------------------------------------------------ Skript-Studio
LOADERS.studio = async () => {
  FACTS = await api("facts");
  const sel = new Set($$("#fact-picker input:checked").map((i) => Number(i.value)));
  $("#fact-picker").innerHTML = FACTS.filter((f) => f.status !== "widerlegt").map((f) =>
    `<label><input type="checkbox" value="${f.id}" ${sel.has(f.id) ? "checked" : ""}> <span>${badge(f.status, statusLabel(f.status))} ${esc(f.title)} <span class="muted">(${f.used_count}×)</span></span></label>`).join("");
  const ideas = await api("ideas?limit=8");
  $("#idea-list").innerHTML = ideas.map((i) => `<div class="idea"><span><b>${esc(i.series)}</b> · ${esc(i.hook)}</span><button class="small" data-idea='${esc(JSON.stringify(i))}'>Nehmen</button></div>`).join("") || `<p class="muted">Alle Fakten schon genutzt. Neue Infos sammeln!</p>`;
};
function preselect(topic, ids, series, hook) {
  const f = $("#script-form");
  f.elements.topic.value = topic;
  if (series) f.elements.series.value = series;
  if (hook) f.elements.hook_type.value = hook;
  $$("#fact-picker input").forEach((i) => { i.checked = ids.includes(Number(i.value)); });
}
$("#idea-list").addEventListener("click", (e) => {
  if (!e.target.dataset.idea) return;
  const i = JSON.parse(e.target.dataset.idea);
  preselect(i.topic, [i.fact_id], i.series, i.hook_type);
  $("#script-form").requestSubmit();
});
function scriptRequest() {
  const d = formData($("#script-form"));
  d.fact_ids = $$("#fact-picker input:checked").map((i) => Number(i.value));
  return d;
}
$("#script-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const req = scriptRequest();
  if (req.fact_ids.length > 3) toast("Mehr als 3 Fakten: es werden die ersten 3 genutzt");
  const s = await api("generate/script", "POST", req);
  const vf = $("#video-form");
  vf.reset(); vf.elements.id.value = "";
  fillForm(vf, { title: s.title, series: s.series, hook: s.hook, hook_type: s.hook_type, script: s.script, onscreen: s.onscreen,
    caption: s.caption, hashtags: s.hashtags, fact_ids: s.fact_ids, target_seconds: s.target_seconds, status: "skript" });
  $("#script-meta").innerHTML = `<span>Dauer ca. <b>${s.seconds}s</b> / Ziel ${s.target_seconds}s</span><span><b>${s.word_count}</b> Wörter (Ziel ~${s.target_words})</span><span>Check-Punkte: <b>${s.quality}/100</b></span>`;
  $("#script-warnings").innerHTML = s.warnings.map((w) => `<li>${esc(w)}</li>`).join("");
  $("#script-sources").innerHTML = s.sources.length ? "<h3>Quellen fürs Video</h3>" + s.sources.map((x) => {
    const u = safeUrl(x.source_url);
    return `<div class="s">${esc(x.status)}: ${esc(x.title)} – ${u ? `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(x.source_name || u)}</a>` : esc(x.source_name || "keine Quelle")}</div>`;
  }).join("") : "";
  updateDuration();
});
$("#btn-hooks").addEventListener("click", async () => {
  const topic = $("#script-form").elements.topic.value;
  const hooks = await api("generate/hooks", "POST", { topic });
  $("#hook-list").innerHTML = hooks.map((h) => `<div class="hook"><span>${esc(h.text)}</span><small>${esc(h.trigger)}</small><button class="small" data-hook="${esc(h.type)}" data-text="${esc(h.text)}">Nehmen</button></div>`).join("");
});
$("#hook-list").addEventListener("click", (e) => {
  if (!e.target.dataset.hook) return;
  $("#script-form").elements.hook_type.value = e.target.dataset.hook;
  const vf = $("#video-form");
  if (vf.elements.script.value) {
    const old = vf.elements.hook.value;
    vf.elements.hook.value = e.target.dataset.text; vf.elements.hook_type.value = e.target.dataset.hook;
    if (old && vf.elements.script.value.startsWith(old)) vf.elements.script.value = e.target.dataset.text + vf.elements.script.value.slice(old.length);
    updateDuration(); toast("Hook übernommen");
  } else $("#script-form").requestSubmit();
});
$("#btn-prompt").addEventListener("click", async () => { const r = await api("generate/prompt", "POST", scriptRequest()); copy(r.prompt); });
let durTimer;
function updateDuration() {
  clearTimeout(durTimer);
  durTimer = setTimeout(async () => {
    const r = await api("generate/duration", "POST", { script: $("#script-text").value });
    $("#live-duration").textContent = `· ${r.words} Wörter · ca. ${r.seconds}s`;
  }, 300);
}
$("#script-text").addEventListener("input", updateDuration);
$("#video-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const d = formData(e.target); const id = d.id; delete d.id;
  d.fact_ids = JSON.parse(d.fact_ids || "[]");
  if (d.planned_at && d.status === "skript") d.status = "geplant";
  const v = await (id ? api("videos/" + id, "PUT", d) : api("videos", "POST", d));
  e.target.elements.id.value = v.id; toast("Im Plan gespeichert");
});
$("#btn-to-voice").addEventListener("click", () => { $("#voice-text").value = $("#script-text").value; showTab("voice"); });
$("#btn-srt").addEventListener("click", async () => {
  const r = await api("generate/srt", "POST", { script: $("#script-text").value });
  if (!r.srt) return toast("Kein Sprechtext");
  download(($("#video-form").elements.title.value || "untertitel").replace(/[^\wäöüÄÖÜß-]+/g, "_") + ".srt", r.srt);
});
$("#btn-copy-caption").addEventListener("click", () => { const f = $("#video-form").elements; copy(f.caption.value + "\n\n" + f.hashtags.value); });
async function openVideo(id) {
  const v = await api("videos/" + id);
  showTab("studio");
  const vf = $("#video-form"); vf.reset(); fillForm(vf, v);
  if (v.planned_at) vf.elements.planned_at.value = v.planned_at.slice(0, 16);
  $("#script-form").elements.topic.value = v.title.split(": ").slice(1).join(": ") || v.title;
  if (v.hook_type) $("#script-form").elements.hook_type.value = v.hook_type;
  if (v.series && META.series.some((s) => s.name === v.series)) $("#script-form").elements.series.value = v.series;
  $("#script-meta").innerHTML = ""; $("#script-warnings").innerHTML = ""; $("#script-sources").innerHTML = "";
  updateDuration();
}

// ------------------------------------------------------------------ Voice-over
let voices = [];
function loadVoices() {
  voices = (window.speechSynthesis?.getVoices() || []).slice().sort((a, b) => (b.lang.startsWith("de") - a.lang.startsWith("de")) || a.name.localeCompare(b.name));
  $("#voice-select").innerHTML = voices.map((v, i) => `<option value="${i}">${esc(v.name)} (${esc(v.lang)})</option>`).join("") || "<option>keine Stimme gefunden</option>";
}
if ("speechSynthesis" in window) { loadVoices(); speechSynthesis.onvoiceschanged = loadVoices; }
else $("#voice-info").textContent = "Dieser Browser kann nicht vorlesen. Nimm Chrome, Edge oder Safari.";
$("#voice-rate").addEventListener("input", (e) => ($("#rate-val").textContent = e.target.value));
$("#voice-pitch").addEventListener("input", (e) => ($("#pitch-val").textContent = e.target.value));
$("#tts-play").addEventListener("click", () => {
  if (!("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const text = $("#voice-text").value.trim(); if (!text) return toast("Kein Text");
  const u = new SpeechSynthesisUtterance(text);
  const v = voices[Number($("#voice-select").value)]; if (v) { u.voice = v; u.lang = v.lang; } else u.lang = "de-DE";
  u.rate = Number($("#voice-rate").value); u.pitch = Number($("#voice-pitch").value);
  const t0 = performance.now();
  u.onend = () => { $("#voice-info").textContent = `Gesprochen in ${((performance.now() - t0) / 1000).toFixed(1)} s bei Tempo ${u.rate}.`; };
  $("#voice-info").textContent = "Spricht…";
  speechSynthesis.speak(u);
});
$("#tts-stop").addEventListener("click", () => window.speechSynthesis?.cancel());

// Teleprompter
let prAnim = null;
$("#prompter-open").addEventListener("click", async () => {
  const text = $("#voice-text").value.trim(); if (!text) return toast("Kein Text");
  const r = await api("generate/duration", "POST", { script: text });
  $("#pr-seconds").value = Math.max(10, Math.round(r.seconds));
  $("#prompter-text").textContent = text;
  $("#prompter-text").style.fontSize = $("#pr-size").value + "px";
  $("#prompter-text").scrollTop = 0;
  $("#prompter").classList.remove("hidden");
});
$("#pr-size").addEventListener("input", (e) => ($("#prompter-text").style.fontSize = e.target.value + "px"));
$("#pr-close").addEventListener("click", () => { cancelAnimationFrame(prAnim); $("#prompter").classList.add("hidden"); });
$("#pr-start").addEventListener("click", () => {
  const el = $("#prompter-text"); cancelAnimationFrame(prAnim); el.scrollTop = 0;
  const total = el.scrollHeight - el.clientHeight, dur = Number($("#pr-seconds").value) * 1000, t0 = performance.now() + 1500;
  const step = (now) => { const p = Math.max(0, Math.min(1, (now - t0) / dur)); el.scrollTop = p * total; if (p < 1) prAnim = requestAnimationFrame(step); };
  prAnim = requestAnimationFrame(step);
});

// Aufnahme
let rec = null, chunks = [], recT0 = 0, recTimer = null;
$("#rec-start").addEventListener("click", async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    rec = new MediaRecorder(stream); chunks = [];
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      const url = URL.createObjectURL(blob), secs = ((performance.now() - recT0) / 1000).toFixed(1);
      const ext = (rec.mimeType || "").includes("mp4") ? "m4a" : "webm";
      const div = document.createElement("div"); div.className = "item";
      const audio = document.createElement("audio"); audio.controls = true; audio.src = url;
      const a = document.createElement("a"); a.href = url; a.download = `voiceover-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.${ext}`; a.textContent = `Herunterladen (${secs.replace(".", ",")} s)`;
      div.append(audio, a); $("#rec-list").prepend(div);
    };
    rec.start(); recT0 = performance.now();
    $("#rec-start").disabled = true; $("#rec-stop").disabled = false; $("#rec-timer").classList.add("recording");
    recTimer = setInterval(() => ($("#rec-timer").textContent = ((performance.now() - recT0) / 1000).toFixed(1).replace(".", ",") + " s"), 100);
  } catch (err) { toast("Kein Mikrofon-Zugriff: " + err.message); }
});
$("#rec-stop").addEventListener("click", () => {
  rec?.stop(); clearInterval(recTimer);
  $("#rec-start").disabled = false; $("#rec-stop").disabled = true; $("#rec-timer").classList.remove("recording");
});

// ------------------------------------------------------------------ Planung
LOADERS.pipeline = async () => {
  VIDEOS = await api("videos");
  const f = $("#plan-form");
  if (!f.elements.start.value) f.elements.start.value = new Date().toISOString().slice(0, 10);
  if (SETTINGS.post_times) f.elements.times.value = SETTINGS.post_times;
  if (SETTINGS.posts_per_day) f.elements.posts_per_day.value = SETTINGS.posts_per_day;
  renderCalendar();
};
function renderCalendar() {
  const st = $("#video-filter").value;
  const list = VIDEOS.filter((v) => !st || v.status === st);
  const days = {};
  for (const v of list) (days[v.planned_at ? v.planned_at.slice(0, 10) : "ohne Termin"] ||= []).push(v);
  const keys = Object.keys(days).sort((a, b) => (a === "ohne Termin") - (b === "ohne Termin") || a.localeCompare(b));
  $("#calendar").innerHTML = keys.map((k) => {
    const label = k === "ohne Termin" ? k : new Date(k + "T12:00").toLocaleDateString("de-DE", { weekday: "long", day: "2-digit", month: "long" });
    const items = days[k].sort((a, b) => a.planned_at.localeCompare(b.planned_at)).map((v) => videoItem(v, "", true)).join("");
    return `<div class="day"><h4>${esc(label)} · ${days[k].length}</h4>${items}</div>`;
  }).join("") || `<p class="muted">Noch keine Videos.</p>`;
}
$("#video-filter").addEventListener("change", renderCalendar);
async function planRequest(create) { const d = formData($("#plan-form")); d.create = create; return api("plan", "POST", d); }
$("#plan-preview").addEventListener("click", async () => {
  const r = await planRequest(false);
  $("#plan-preview-list").innerHTML = "<h3>Vorschau</h3>" + r.slots.map((s) => `<div class="item"><span><b>${esc(s.weekday)} ${esc(s.date.slice(8))}.${esc(s.date.slice(5, 7))}. ${esc(s.time)}</b> · ${esc(s.series)}</span><span class="s">${esc(s.hook)}</span></div>`).join("");
});
$("#plan-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!confirm("Alle Slots als Video-Ideen anlegen?")) return;
  const r = await planRequest(true); toast(`${r.created} Videos angelegt`); $("#plan-preview-list").innerHTML = ""; LOADERS.pipeline();
});

// ------------------------------------------------------------------ Analyse
LOADERS.analytics = async () => {
  const [a, vids] = await Promise.all([api("analytics"), api("videos")]);
  VIDEOS = vids;
  const cur = $("#metric-video").value;
  $("#metric-video").innerHTML = vids.slice().sort((x, y) => (y.status === "gepostet") - (x.status === "gepostet")).map((v) => `<option value="${v.id}">${v.status === "gepostet" ? "✓ " : ""}${esc(v.title)}</option>`).join("");
  if (cur) $("#metric-video").value = cur;
  const t = a.total;
  $("#an-kpis").innerHTML = [[fmt(t.views), "Aufrufe"], [fmt(t.median_views), "Median pro Video"], [t.avg_engagement + " %", "Ø Interaktionsrate"], [t.avg_completion + " %", "Ø komplett angesehen"]]
    .map(([v, l]) => `<div class="kpi"><div class="v">${esc(v)}</div><div class="l">${esc(l)}</div></div>`).join("");
  $("#an-insights").innerHTML = a.insights.map((i) => `<li>${esc(i)}</li>`).join("");
  const grp = (rows) => rows.length ? `<div class="tablewrap"><table class="table"><tr><th></th><th>Videos</th><th>Median Aufrufe</th><th>Interaktion</th><th>Komplett</th><th>Geteilt</th></tr>${rows.map((g) => `<tr><td>${esc(g.name)}</td><td>${g.videos}</td><td>${fmt(g.median_views)}</td><td>${g.avg_engagement} %</td><td>${g.avg_completion} %</td><td>${g.avg_share_rate} %</td></tr>`).join("")}</table></div>` : `<p class="muted">Noch keine Daten.</p>`;
  $("#an-series").innerHTML = grp(a.by_series); $("#an-hooks").innerHTML = grp(a.by_hook);
  const maxV = Math.max(1, ...a.videos.map((v) => v.views));
  const wrap = document.createElement("div"); wrap.className = "tablewrap";
  wrap.innerHTML = `<table class="table"><thead><tr><th>Video</th><th>Aufrufe</th><th></th><th>× Median</th><th>Interaktion</th><th>Geteilt</th><th>Gespeichert</th><th>Komplett</th><th>Follow-Rate</th></tr></thead><tbody></tbody></table>`;
  const tb = $("tbody", wrap);
  for (const v of a.videos) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${esc(v.title)}<div class="muted">${esc(v.series)} · ${esc(v.hook_type)} · nach ${v.hours_after} h</div></td><td>${fmt(v.views)}</td><td></td><td class="${v.outlier >= 2 ? "hot" : ""}">${v.outlier}×</td><td>${v.engagement_rate} %</td><td>${v.share_rate} %</td><td>${v.save_rate} %</td><td>${v.completion_pct} %</td><td>${v.follow_rate} %</td>`;
    tr.children[2].append(bar((v.views / maxV) * 100)); tb.append(tr);
  }
  $("#an-table").replaceChildren(a.videos.length ? wrap : Object.assign(document.createElement("p"), { className: "muted", textContent: "Noch keine Zahlen eingetragen." }));
};
$("#metric-form").addEventListener("submit", async (e) => {
  e.preventDefault(); const d = formData(e.target); d.video_id = Number(d.video_id); d.hours_after = Number(d.hours_after);
  await api("metrics", "POST", d); toast("Eingetragen");
  for (const el of e.target.elements) if (el.type === "number") el.value = "";
  LOADERS.analytics();
});
$("#csv-import").addEventListener("click", async () => {
  const r = await api("metrics/import", "POST", { csv: $("#csv-text").value, create_missing: $("#csv-create").checked, hours_after: 24 });
  $("#csv-result").textContent = ` ${r.imported} von ${r.rows} Zeilen übernommen, ${r.videos_created} Videos neu angelegt.`; LOADERS.analytics();
});

// ------------------------------------------------------------------ Konkurrenz
const FORMATS = ["News", "Leak-Analyse", "Easter Egg", "Guide/Tipps", "Theorie", "Vergleich", "Reaktion", "Meme/Comedy", "Gameplay-Clip", "Liste/Ranking"];
LOADERS.competition = async () => {
  const r = await api("competitors/report");
  $("#cpost-comp").innerHTML = r.competitors.map((c) => `<option value="${c.id}">${esc(c.handle)}</option>`).join("") || `<option value="">zuerst Account anlegen</option>`;
  $("#comp-list").innerHTML = r.competitors.map((c) => `<div class="item"><div><div class="t">${esc(c.handle)} <span class="muted">${fmt(c.followers)} Follower · ${esc(c.language)}</span></div>
    <div class="s">${c.focus ? esc(c.focus) + " · " : ""}${c.posts} Videos erfasst · Median ${fmt(c.median_views)} · Top ${fmt(c.max_views)}</div>${c.notes ? `<div class="s">${esc(c.notes)}</div>` : ""}</div>
    <button class="small danger" data-cdel="${c.id}">✕</button></div>`).join("") || `<p class="muted">Leg 5–10 Accounts an: große deutsche GTA-Accounts, englische Leak/News-Accounts und kleine, schnell wachsende.</p>`;
  $("#comp-formats").innerHTML = r.formats.length ? r.formats.map((f) => `<div class="item"><span>${esc(f.format)} <span class="muted">(${f.posts})</span></span><b>${f.avg_outlier}×</b></div>`).join("") : `<p class="muted">Noch keine Videos erfasst.</p>`;
  $("#comp-top").innerHTML = r.top_posts.length ? `<div class="tablewrap"><table class="table"><tr><th>Account</th><th>Video</th><th>Format</th><th>Aufrufe</th><th>Ausreißer</th><th>Aufrufe/Follower</th><th>Interaktion</th><th></th></tr>${r.top_posts.map((p) => {
    const u = safeUrl(p.url);
    return `<tr><td>${esc(p.handle)}</td><td><b>${esc(p.title)}</b>${p.hook ? `<div class="muted">„${esc(p.hook)}“</div>` : ""}</td><td>${esc(p.format)}</td><td>${fmt(p.views)}</td><td class="${p.outlier >= 3 ? "hot" : ""}">${p.outlier}×</td><td>${p.views_per_follower}</td><td>${p.engagement_rate} %</td>
    <td class="actions">${u ? `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">ansehen</a>` : ""}<button class="small" data-remake='${esc(JSON.stringify({ t: p.title, f: p.format }))}'>Eigene Version</button><button class="small danger" data-cpdel="${p.id}">✕</button></td></tr>`;
  }).join("")}</table></div>` : `<p class="muted">Trag Videos der Konkurrenz ein, dann siehst du hier, was überdurchschnittlich läuft.</p>`;
};
$("#cpost-format").innerHTML = FORMATS.map((f) => `<option>${esc(f)}</option>`).join("");
$("#comp-form").addEventListener("submit", async (e) => { e.preventDefault(); await api("competitors", "POST", formData(e.target)); e.target.reset(); toast("Hinzugefügt"); LOADERS.competition(); });
$("#cpost-form").addEventListener("submit", async (e) => {
  e.preventDefault(); const d = formData(e.target); d.competitor_id = Number(d.competitor_id);
  await api("competitor-posts", "POST", d); for (const el of e.target.elements) if (el.name !== "competitor_id" && el.name !== "format") el.value = "";
  toast("Gespeichert"); LOADERS.competition();
});
$("#tab-competition").addEventListener("click", async (e) => {
  const t = e.target;
  if (t.dataset.cdel && confirm("Account und alle erfassten Videos löschen?")) { await api("competitors/" + t.dataset.cdel, "DELETE"); LOADERS.competition(); }
  if (t.dataset.cpdel) { await api("competitor-posts/" + t.dataset.cpdel, "DELETE"); LOADERS.competition(); }
  if (t.dataset.remake) {
    const r = JSON.parse(t.dataset.remake);
    const hook = { "Leak-Analyse": "leak_realitaet", "Easter Egg": "geheimnis", "Guide/Tipps": "fehler", "Theorie": "fakt_fake", "Vergleich": "vergleich", "Liste/Ranking": "rang" }[r.f] || "keiner_bemerkt";
    showTab("studio"); setTimeout(() => preselect(r.t, [], undefined, hook), 150); toast("Thema übernommen. Mit eigenen Fakten und eigenem Gameplay neu machen.");
  }
});

// ------------------------------------------------------------------ Einstellungen
LOADERS.settings = async () => { SETTINGS = await api("settings"); fillForm($("#settings-form"), SETTINGS); };
$("#settings-form").addEventListener("submit", async (e) => {
  e.preventDefault(); const d = formData(e.target); SETTINGS = await api("settings", "PUT", d); toast("Gespeichert"); LOADERS.dashboard();
});
$("#btn-export").addEventListener("click", async () => download(`gta-studio-sicherung-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(await api("export"), null, 2), "application/json"));

// ------------------------------------------------------------------ Start
(async function init() {
  META = await api("meta");
  $("#fact-status").innerHTML = META.fact_status.map((s) => `<option value="${s.key}">${esc(s.label)}</option>`).join("");
  $("#fact-filter").innerHTML += META.fact_status.map((s) => `<option value="${s.key}">${esc(s.label)}</option>`).join("");
  $("#series-select").innerHTML = META.series.map((s) => `<option title="${esc(s.description)}">${esc(s.name)}</option>`).join("");
  $("#hook-select").innerHTML = META.hooks.map((h) => `<option value="${h.type}">${esc(h.template.replace("{thema}", "…"))}</option>`).join("");
  $("#video-status").innerHTML = META.video_status.map((s) => `<option>${s}</option>`).join("");
  $("#video-filter").innerHTML += META.video_status.map((s) => `<option>${s}</option>`).join("");
  await LOADERS.dashboard();
  let tab = "dashboard"; try { tab = localStorage.getItem("tab") || tab; } catch {}
  if (tab !== "dashboard") showTab(tab);
})();
