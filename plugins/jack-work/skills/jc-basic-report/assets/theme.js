(function () {
  'use strict';
  /* Theme: white / black / beige. Runs in <head> (right after the Settings block) so the
     chosen Theme is on <html data-theme> before the first paint. The choice is global
     (one localStorage key for every report), the default comes from Settings.defaultTheme.
     Other scripts read window.jcTheme.get() and listen for the 'jc:themechange' event. */
  var KEY = 'jc-report-theme';
  var THEMES = [['white', '白色'], ['black', '黑色'], ['beige', '米色']];
  var FALLBACK = 'beige';
  var root = document.documentElement;

  function valid(t) { return THEMES.some(function (x) { return x[0] === t; }); }
  function settingsDefault() {
    try { return JSON.parse(document.getElementById('jc-settings').textContent).defaultTheme; } catch (e) { return null; }
  }
  function saved() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function persist(t) { try { localStorage.setItem(KEY, t); } catch (e) { /* file:// 或隐私模式下不可用 */ } }

  var current = [saved(), settingsDefault(), FALLBACK].filter(valid)[0];
  var group = null;

  function sync() {
    if (!group) return;
    group.querySelectorAll('[data-theme]').forEach(function (b) {
      var on = b.dataset.theme === current;
      b.setAttribute('aria-checked', String(on));
      b.tabIndex = on ? 0 : -1;
    });
  }
  function set(t) {
    if (!valid(t)) return;
    current = t;
    root.setAttribute('data-theme', t);
    persist(t);
    sync();
    document.dispatchEvent(new CustomEvent('jc:themechange', { detail: { theme: t } }));
  }
  root.setAttribute('data-theme', current);

  function mount() {
    var head = document.querySelector('#side .side-head');
    if (!head || group) return;
    group = document.createElement('div');
    group.className = 'side-theme';
    group.setAttribute('role', 'radiogroup');
    group.setAttribute('aria-label', '主题');
    group.innerHTML = THEMES.map(function (x) {
      return '<button type="button" role="radio" data-theme="' + x[0] + '">' + x[1] + '</button>';
    }).join('');
    head.insertAdjacentElement('afterend', group);
    group.addEventListener('click', function (e) {
      var b = e.target.closest('[data-theme]');
      if (b) set(b.dataset.theme);
    });
    group.addEventListener('keydown', function (e) {
      var step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
      if (!step) return;
      e.preventDefault();
      var i = THEMES.findIndex(function (x) { return x[0] === current; });
      set(THEMES[(i + step + THEMES.length) % THEMES.length][0]);
      group.querySelector('[aria-checked="true"]').focus();
    });
    sync();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();

  window.jcTheme = { get: function () { return current; }, set: set, names: THEMES.map(function (x) { return x[0]; }) };
})();
