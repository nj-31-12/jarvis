/* JARVIS Chat (Version 5.3): Stimme, automatisches Vorlesen, „JARVIS denkt nach“.
 * Eigene Datei, kein Inline-Skript, kein CDN (strenge CSP). Texte werden nie als HTML eingesetzt.
 * Stimme: zuerst die Mac-Stimme mit Effekt (/chat/stimme). Geht das nicht, liest der Browser selbst vor.
 */
(function () {
  'use strict';
  var body = document.body;
  var buttons = document.querySelectorAll('button.speak[data-id]');
  var auto = document.getElementById('autovoice');
  var autoLabel = auto ? auto.parentNode : null;
  var current = null;
  var startWake = function () {}, stopWake = function () {};

  function store(kind, key, value) {
    try {
      var s = kind === 'local' ? window.localStorage : window.sessionStorage;
      if (value === undefined) { return s.getItem(key); }
      s.setItem(key, value);
    } catch (e) { return null; }
    return null;
  }

  function stop() {
    if (current) { current.pause(); current = null; }
    if (window.speechSynthesis) { window.speechSynthesis.cancel(); }
    body.classList.remove('speaking');
  }

  function browserVoice(text) {
    if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) { return; }
    var u = new SpeechSynthesisUtterance(text);
    u.lang = 'de-DE'; u.rate = 0.95; u.pitch = 0.7;
    var voices = window.speechSynthesis.getVoices();
    var pick = null;
    ['Markus', 'Yannick', 'Viktor'].forEach(function (n) {
      voices.forEach(function (v) { if (!pick && v.name.indexOf(n) === 0) { pick = v; } });
    });
    if (!pick) { voices.forEach(function (v) { if (!pick && v.lang && v.lang.indexOf('de') === 0) { pick = v; } }); }
    if (pick) { u.voice = pick; }
    u.onend = function () { body.classList.remove('speaking'); };
    body.classList.add('speaking');
    window.speechSynthesis.speak(u);
  }

  function textOf(id) {
    var art = document.querySelector('article.msg[data-id="' + id + '"] .body');
    if (!art) { return ''; }
    var clone = art.cloneNode(true);
    var src = clone.querySelector('.sources'); if (src) { src.parentNode.removeChild(src); }
    var t = clone.textContent || '';
    var i = t.indexOf('🔎 Prüfung:'); if (i >= 0) { t = t.slice(0, i); }
    return t.replace(/\s+/g, ' ').trim().slice(0, 2500);
  }

  function speak(id, btn) {
    stop();
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Stimme lädt …'; }
    var audio = new Audio('/chat/stimme?id=' + encodeURIComponent(id));
    current = audio;
    audio.onplaying = function () { body.classList.add('speaking'); if (btn) { btn.disabled = false; btn.textContent = '⏹ Stopp'; } };
    audio.onended = function () { body.classList.remove('speaking'); if (btn) { btn.textContent = '🔊 Vorlesen'; } current = null; };
    audio.onerror = function () {                       // keine Mac-Stimme → Browser-Stimme
      if (btn) { btn.disabled = false; btn.textContent = '🔊 Vorlesen'; }
      current = null; browserVoice(textOf(id));
    };
    var p = audio.play();
    if (p && p.catch) { p.catch(function () { if (btn) { btn.disabled = false; btn.textContent = '🔊 Vorlesen'; } }); }
  }

  Array.prototype.forEach.call(buttons, function (btn) {
    btn.hidden = false;
    btn.addEventListener('click', function () {
      if (current || body.classList.contains('speaking')) { stop(); btn.textContent = '🔊 Vorlesen'; return; }
      speak(btn.getAttribute('data-id'), btn);
    });
  });

  // Automatisch vorlesen (Einstellung bleibt im Browser gespeichert)
  if (auto && autoLabel) {
    autoLabel.hidden = false;
    auto.checked = store('local', 'jarvis-autovoice') === '1';
    auto.addEventListener('change', function () { store('local', 'jarvis-autovoice', auto.checked ? '1' : '0'); });
    var fresh = document.querySelector('article.msg-jarvis.fresh');
    if (auto.checked && fresh) {
      var id = fresh.getAttribute('data-id');
      if (store('session', 'jarvis-spoken') !== id) {
        store('session', 'jarvis-spoken', id);
        var b = fresh.querySelector('button.speak');
        window.setTimeout(function () { speak(id, b); }, 600);
      }
    }
  }

  // „JARVIS denkt nach“ während die Antwort entsteht und geprüft wird
  var form = document.querySelector('form.composer');
  var thinking = document.querySelector('.thinking');
  if (form && thinking) {
    form.addEventListener('submit', function () { stop(); thinking.hidden = false; body.classList.add('is-thinking'); });
  }
  // ------------------------------------------------------------ Stand 18: Sprechen (Push-to-talk + Wake-Word)
  // Spracherkennung des Browsers: Chrome/Safari (Ton geht zur Erkennung an Google/Apple). Firefox hat sie nicht →
  // dort Hinweis auf die Mac-Diktierfunktion (fn fn). Gesprochenes wird wie Getipptes behandelt; freigeben geht nie.
  var ctl = document.querySelector('.voice-ctl'), mic = document.getElementById('mic'), wake = document.getElementById('wake');
  var hint = document.getElementById('vchint'), area = document.getElementById('text');
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  function say(t) { if (hint) { hint.textContent = t; } }
  function submitText(t) {
    t = (t || '').trim(); if (!t || !form || !area) { return; }
    area.value = t; stopWake(true);
    if (form.requestSubmit) { form.requestSubmit(); } else { form.submit(); }
  }
  if (ctl && mic && area) {
    ctl.hidden = false;
    if (!SR) {
      mic.textContent = '🎙 Diktieren';
      mic.addEventListener('click', function () { area.focus(); say('In Firefox: zweimal die fn-Taste drücken und sprechen (Mac-Diktat).'); });
    } else {
      // Push-to-talk: Knopf halten oder ⌥ (Option) halten
      var ptt = null, pttText = '';
      var startPTT = function () {
        if (ptt) { return; }
        stopWake(false); stop();
        ptt = new SR(); ptt.lang = 'de-DE'; ptt.interimResults = true; ptt.continuous = true; pttText = '';
        ptt.onresult = function (e) {
          var all = ''; for (var i = 0; i < e.results.length; i++) { all += e.results[i][0].transcript; }
          pttText = all; area.value = all; say('🎙 ' + all);
        };
        ptt.onerror = function (e) { say('Mikrofon: ' + (e.error || 'Fehler') + '. Bitte Mikrofon im Browser erlauben.'); };
        try { ptt.start(); body.classList.add('listening'); mic.setAttribute('aria-pressed', 'true'); say('🎙 Ich höre …'); } catch (err) { ptt = null; }
      };
      var endPTT = function () {
        if (!ptt) { return; }
        var r = ptt; ptt = null; body.classList.remove('listening'); mic.setAttribute('aria-pressed', 'false');
        r.onend = function () { if (pttText.trim()) { submitText(pttText); } else { say('Nichts verstanden.'); startWake(); } };
        try { r.stop(); } catch (err) { /* schon beendet */ }
      };
      mic.addEventListener('pointerdown', function (e) { e.preventDefault(); startPTT(); });
      mic.addEventListener('pointerup', endPTT); mic.addEventListener('pointerleave', endPTT);
      document.addEventListener('keydown', function (e) { if (e.key === 'Alt' && !e.repeat) { startPTT(); } });
      document.addEventListener('keyup', function (e) { if (e.key === 'Alt') { endPTT(); } });

      // Wake-Word „Jarvis“ (Schalter, standardmäßig AUS, Einstellung bleibt im Browser)
      var wakeLabel = wake ? wake.parentNode : null, wakeRec = null, armed = 0, wakeOn = false;
      if (wake && wakeLabel) {
        wakeLabel.hidden = false;
        wake.checked = store('local', 'jarvis-wake') === '1';
        wake.addEventListener('change', function () {
          store('local', 'jarvis-wake', wake.checked ? '1' : '0');
          if (wake.checked) { startWake(); } else { stopWake(false); say(''); }
        });
      }
      startWake = function () {
        if (!wake || !wake.checked || wakeRec || ptt) { return; }
        wakeOn = true;
        wakeRec = new SR(); wakeRec.lang = 'de-DE'; wakeRec.continuous = true; wakeRec.interimResults = false;
        wakeRec.onresult = function (e) {
          if (body.classList.contains('speaking')) { return; }            // eigene Stimme nicht als Befehl werten
          var r = e.results[e.results.length - 1]; if (!r.isFinal) { return; }
          var t = r[0].transcript.trim(), m = t.match(/\b(jarvis|javis|charvis|dschawis)\b[,.!\s]*(.*)$/i);
          if (m) {
            if (m[2] && m[2].length > 2) { submitText(m[2]); return; }
            armed = Date.now(); body.classList.add('listening'); say('Ja, Sir?');
          } else if (armed && Date.now() - armed < 8000) { submitText(t); }
        };
        wakeRec.onend = function () { wakeRec = null; body.classList.remove('listening'); if (wakeOn && wake.checked) { setTimeout(startWake, 400); } };
        wakeRec.onerror = function (e) { if (e.error === 'not-allowed') { wake.checked = false; wakeOn = false; say('Mikrofon nicht erlaubt.'); } };
        try { wakeRec.start(); say('Ich höre auf „Jarvis“.'); body.classList.add('wake-on'); } catch (err) { wakeRec = null; }
      };
      stopWake = function (keepSetting) {
        wakeOn = false; armed = 0; body.classList.remove('wake-on');
        if (wakeRec) { var w = wakeRec; wakeRec = null; try { w.stop(); } catch (err) { /* egal */ } }
        if (!keepSetting && wake && !wake.checked) { store('local', 'jarvis-wake', '0'); }
      };
      // Nach JARVIS' gesprochener Antwort wieder zuhören
      setTimeout(startWake, 1200);
    }
  }

  var end = document.getElementById('ende');
  if (end && end.scrollIntoView && !body.classList.contains('portal-on')) { end.scrollIntoView(); }
})();
