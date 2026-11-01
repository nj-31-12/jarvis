/* JARVIS Auftrags-Zentrale (Stand 23): Live-Ablauf mit Erzählerstimme.
 * Holt jede Sekunde neue Schritte (/auftraege/daten), blendet sie animiert ein und lässt JARVIS sie aussprechen.
 * Fertige Aufträge: „Schnellablauf abspielen“ zeigt alle Schritte noch einmal im Zeitraffer.
 * Texte nur per textContent (nie als HTML).
 */
(function () {
  'use strict';
  var box = document.getElementById('m-live');
  if (!box) { return; }
  var id = box.getAttribute('data-id'), list = document.getElementById('m-steps'), statusEl = document.getElementById('m-status');
  var speakBox = document.getElementById('m-speak'), canvas = box.querySelector('canvas[data-orb]');
  var orb = canvas && window.JarvisOrb ? window.JarvisOrb(canvas) : { mode: function () {}, level: function () {} };
  var say = window.JarvisSpeak, queue = [], talking = false, running = box.getAttribute('data-status') === 'läuft';
  var next = list.children.length, fx = 'film', ICON = { start: '◆', ok: '✓', warn: '!', fehler: '✕', fertig: '★' };
  try { fx = window.localStorage.getItem('jarvis-fx') || 'film'; speakBox.checked = window.localStorage.getItem('jarvis-erzaehlt') !== 'aus'; } catch (e) { /* egal */ }
  speakBox.addEventListener('change', function () {
    try { window.localStorage.setItem('jarvis-erzaehlt', speakBox.checked ? 'an' : 'aus'); } catch (e) { /* egal */ }
    if (!speakBox.checked) { queue = []; say.stop(); talking = false; orb.mode(running ? 'denken' : 'ruhe'); }
  });
  orb.mode(running ? 'denken' : 'ruhe');

  function stepEl(s) {
    var li = document.createElement('li'); li.className = 'm-step art-' + s.art + ' fresh'; li.setAttribute('data-n', s.n);
    var i = document.createElement('i'); i.textContent = ICON[s.art] || '•';
    var t = document.createElement('span'); t.className = 'mono'; t.textContent = s.zeit;
    var p = document.createElement('p'); p.textContent = s.text;
    if (s.detail) { var sm = document.createElement('small'); sm.textContent = s.detail; p.appendChild(sm); }
    li.appendChild(i); li.appendChild(t); li.appendChild(p);
    return li;
  }
  function show(s, narrate) {
    var li = stepEl(s); list.appendChild(li);
    setTimeout(function () { li.classList.remove('fresh'); }, 30);
    li.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    if (narrate && speakBox.checked && say) { queue.push(s); pump(); }
  }
  function pump() {
    if (talking || !queue.length) { if (!talking) { orb.mode(running ? 'denken' : 'ruhe'); } return; }
    var s = queue.shift(); talking = true;
    say.speak('/auftraege/stimme?id=' + encodeURIComponent(id) + '&n=' + s.n + '&fx=' + encodeURIComponent(fx), s.text, orb, function () {
      talking = false; orb.mode(running ? 'denken' : 'ruhe'); pump();
      if (!running && !queue.length && !talking && box.getAttribute('data-reload') === '1') { window.location.reload(); }
    });
  }
  function poll() {
    fetch('/auftraege/daten?id=' + encodeURIComponent(id) + '&ab=' + next, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        (d.schritte || []).forEach(function (s) { if (s.n >= next) { next = s.n + 1; show(s, true); } });
        statusEl.textContent = d.status;
        if (d.status === 'läuft') { setTimeout(poll, 1000); return; }
        running = false; box.setAttribute('data-reload', '1');
        if (!talking && !queue.length) { setTimeout(function () { window.location.reload(); }, 1200); }
      })
      .catch(function () { setTimeout(poll, 3000); });
  }
  if (running) { setTimeout(poll, 600); }

  // Schnellablauf: alle Schritte nacheinander, mit Stimme (falls an) oder im Zeitraffer
  var replay = document.getElementById('m-replay');
  if (replay) {
    replay.addEventListener('click', function () {
      var all = Array.prototype.map.call(list.children, function (li) {
        var p = li.querySelector('p'), sm = p.querySelector('small');
        return { n: +li.getAttribute('data-n'), art: (li.className.match(/art-(\w+)/) || [0, 'info'])[1],
                 zeit: li.querySelector('.mono').textContent, text: sm ? p.firstChild.textContent : p.textContent, detail: sm ? sm.textContent : '' };
      });
      list.textContent = ''; replay.disabled = true; var k = 0;
      (function nextStep() {
        if (k >= all.length) { replay.disabled = false; orb.mode('ruhe'); return; }
        var s = all[k++];
        show(s, false); orb.mode('denken');
        if (speakBox.checked && say) {
          talking = true;
          say.speak('/auftraege/stimme?id=' + encodeURIComponent(id) + '&n=' + s.n + '&fx=' + encodeURIComponent(fx), s.text, orb, function () { talking = false; setTimeout(nextStep, 150); });
        } else { setTimeout(nextStep, 550); }
      })();
    });
  }
})();
