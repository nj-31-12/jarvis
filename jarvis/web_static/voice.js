/* JARVIS Sprach-Ansicht (Stand 23): Knopf → sprechen → JARVIS antwortet mit Stimme über den 3D-Kern.
 * Spracherkennung: Browser (Chrome/Safari). Firefox hat keine → Textfeld + Mac-Diktat.
 * Mikrofon-Pegel lässt den Kern beim Zuhören mitschwingen (bleibt im Browser, wird nirgends gespeichert).
 * Texte nur per textContent. Anfragen nur an diese Seite, mit Prüfzeichen (CSRF).
 */
(function () {
  'use strict';
  var canvas = document.getElementById('orb');
  if (!canvas || !window.JarvisOrb) { return; }
  var orb = window.JarvisOrb(canvas), say = window.JarvisSpeak;
  var ctl = document.querySelector('.voice-controls'), csrf = ctl.getAttribute('data-csrf');
  var talk = document.getElementById('v-talk'), statusEl = document.getElementById('v-status'), liveEl = document.getElementById('v-live');
  var dauer = document.getElementById('v-dauer'), fxSel = document.getElementById('v-fx');
  var form = document.getElementById('v-form'), input = document.getElementById('v-text');
  var log = document.getElementById('v-log'), propose = document.getElementById('v-propose');
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var rec = null, listening = false, busy = false, micStream = null, micTimer = null;

  try { var f = window.localStorage.getItem('jarvis-fx'); if (f) { fxSel.value = f; } } catch (e) { /* egal */ }
  fxSel.addEventListener('change', function () { try { window.localStorage.setItem('jarvis-fx', fxSel.value); } catch (e) { /* egal */ } });

  function status(t) { statusEl.textContent = t; }
  function add(role, text) {
    var li = document.createElement('li'); li.className = 'v-' + role;
    var b = document.createElement('b'); b.textContent = role === 'du' ? 'Du' : 'JARVIS';
    var p = document.createElement('p'); p.textContent = text;
    li.appendChild(b); li.appendChild(p); log.insertBefore(li, log.firstChild);
    while (log.children.length > 30) { log.removeChild(log.lastChild); }
  }

  // Mikrofon-Pegel → Kern (nur Anzeige)
  function micOn() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { return; }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      micStream = stream;
      var AC = window.AudioContext || window.webkitAudioContext; if (!AC) { return; }
      var ac = new AC(), an = ac.createAnalyser(), buf = new Uint8Array(512);
      an.fftSize = 512; ac.createMediaStreamSource(stream).connect(an);
      micTimer = setInterval(function () {
        an.getByteTimeDomainData(buf); var s = 0;
        for (var i = 0; i < buf.length; i++) { var v = (buf[i] - 128) / 128; s += v * v; }
        orb.level(Math.min(1, Math.sqrt(s / buf.length) * 6));
      }, 60);
      micStream._ac = ac;
    }).catch(function () { /* ohne Pegel */ });
  }
  function micOff() {
    if (micTimer) { clearInterval(micTimer); micTimer = null; }
    if (micStream) { micStream.getTracks().forEach(function (t) { t.stop(); }); if (micStream._ac) { micStream._ac.close(); } micStream = null; }
    orb.level(0);
  }

  function listen() {
    if (!SR) { status('Dieser Browser kann nicht zuhören. Schreib unten – oder öffne JARVIS in Chrome oder Safari.'); input.focus(); return; }
    if (listening || busy) { return; }
    say.stop();
    rec = new SR(); rec.lang = 'de-DE'; rec.interimResults = true; rec.continuous = false;
    var finalText = '';
    rec.onstart = function () { listening = true; talk.setAttribute('aria-pressed', 'true'); talk.classList.add('on'); orb.mode('zuhoeren'); status('Ich höre zu …'); micOn(); };
    rec.onresult = function (ev) {
      var interim = '';
      for (var i = ev.resultIndex; i < ev.results.length; i++) {
        if (ev.results[i].isFinal) { finalText += ev.results[i][0].transcript; } else { interim += ev.results[i][0].transcript; }
      }
      liveEl.textContent = (finalText + ' ' + interim).trim();
    };
    rec.onerror = function (ev) { if (ev.error === 'not-allowed') { status('Mikrofon ist blockiert. Bitte in der Adresszeile erlauben.'); } };
    rec.onend = function () {
      listening = false; talk.setAttribute('aria-pressed', 'false'); talk.classList.remove('on'); micOff();
      var t = finalText.trim();
      if (t) { send(t); } else { orb.mode('ruhe'); status('Nichts gehört. Drück den Knopf und sprich.'); liveEl.textContent = ''; }
    };
    rec.start();
  }
  function stopListening() { if (rec && listening) { rec.stop(); } }

  function showProposal(v) {
    propose.textContent = '';
    if (!v) { propose.hidden = true; return; }
    var h = document.createElement('p');
    h.textContent = v.art === 'akquise' ? '🔎 Auftrag: ' + v.branche + ' in ' + v.ort + ' – schwache Webseiten finden und neu bauen'
      : '🛠 Auftrag: Webseite für ' + v.name;
    var fm = document.createElement('form'); fm.method = 'post'; fm.action = '/auftraege/start';
    var fields = { csrf: csrf, art: v.art, branche: v.branche || '', ort: v.ort || '', name: v.name || '' };
    Object.keys(fields).forEach(function (k) { var i = document.createElement('input'); i.type = 'hidden'; i.name = k; i.value = fields[k]; fm.appendChild(i); });
    var go = document.createElement('button'); go.type = 'submit'; go.textContent = '▶ Starten';
    var edit = document.createElement('a'); edit.href = v.link; edit.textContent = 'Vorher anpassen'; edit.className = 'ghost-link';
    fm.appendChild(go); fm.appendChild(edit);
    propose.appendChild(h); propose.appendChild(fm); propose.hidden = false;
  }

  function send(text) {
    busy = true; add('du', text); liveEl.textContent = ''; orb.mode('denken'); status('JARVIS denkt nach …');
    var body = new URLSearchParams(); body.set('csrf', csrf); body.set('text', text);
    fetch('/stimme/frage', { method: 'POST', body: body, credentials: 'same-origin', headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
      .then(function (r) { if (r.status === 403) { throw new Error('Sitzung abgelaufen – bitte Seite neu laden.'); } return r.json(); })
      .then(function (d) {
        busy = false;
        add('jarvis', d.text || '…');
        showProposal(d.vorschlag || null);
        if (d.weiter) { status('Auftrag läuft – ich öffne die Auftrags-Zentrale.'); }
        if (!d.audio) { orb.mode('ruhe'); status('Drück den Knopf und sprich.'); return; }
        status('JARVIS spricht …');
        say.speak(d.audio + '&fx=' + encodeURIComponent(fxSel.value), (d.text || '').slice(0, 1200), orb, function () {
          if (d.weiter) { window.location.href = d.weiter; return; }
          status(dauer.checked && SR ? 'Ich höre wieder zu …' : 'Drück den Knopf und sprich.');
          if (dauer.checked && SR) { setTimeout(listen, 350); }
        });
      })
      .catch(function (e) { busy = false; orb.mode('ruhe'); status(e.message || 'Verbindung zu JARVIS unterbrochen.'); });
  }

  talk.addEventListener('click', function () { if (listening) { stopListening(); } else { listen(); } });
  form.addEventListener('submit', function (ev) { ev.preventDefault(); var t = input.value.trim(); if (t && !busy) { input.value = ''; say.stop(); send(t); } });
  document.addEventListener('keydown', function (ev) {      // Leertaste (außerhalb des Textfelds) = Sprechen
    if (ev.code === 'Space' && document.activeElement !== input && !ev.repeat) { ev.preventDefault(); if (listening) { stopListening(); } else { listen(); } }
    if (ev.key === 'Escape') { say.stop(); stopListening(); orb.mode('ruhe'); }
  });
  if (!SR) { talk.title = 'Spracherkennung gibt es in Chrome und Safari'; status('Firefox: Schreib unten oder diktiere mit 2× fn. In Chrome/Safari: Knopf drücken und sprechen.'); }
})();
