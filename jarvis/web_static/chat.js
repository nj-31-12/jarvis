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
  var end = document.getElementById('ende');
  if (end && end.scrollIntoView && !body.classList.contains('portal-on')) { end.scrollIntoView(); }
})();
