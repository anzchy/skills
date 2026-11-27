/* jc-basic-report Paginator: lays the Report's Blocks into A4 Sheets (ADR 0001).
   Moves whole child nodes of #report, in order, into .sheet > .sheet-body; never splits or clones. */
(function () {
  'use strict';
  var root = document.documentElement;
  var report = document.getElementById('report');
  var S = JSON.parse(document.getElementById('jc-settings').textContent);
  var PAPER_MM = { A4: { w: 210, h: 297 } };

  function paginate() {
    var paper = PAPER_MM[S.paper.size], m = S.paper.marginMm;
    root.style.setProperty('--sheet-w', paper.w + 'mm');
    root.style.setProperty('--sheet-h', paper.h + 'mm');
    root.style.setProperty('--sheet-mt', m.top + 'mm');
    root.style.setProperty('--sheet-mr', m.right + 'mm');
    root.style.setProperty('--sheet-mb', m.bottom + 'mm');
    root.style.setProperty('--sheet-ml', m.left + 'mm');
    root.classList.add('jc-paginated');

    var nodes = Array.prototype.slice.call(report.childNodes);
    var sheets = [], body = null;
    function newSheet() {
      var sheet = document.createElement('div');
      sheet.className = 'sheet';
      body = document.createElement('div');
      body.className = 'sheet-body';
      sheet.appendChild(body);
      report.appendChild(sheet);
      sheets.push(sheet);
      return sheet;
    }
    function overflows() { return body.scrollHeight > body.clientHeight + 1; }
    function isHeading(n) { return n.nodeType === 1 && /^H[1-6]$/.test(n.tagName); }
    // Nodes that must move with Block n: n itself, plus the headings (and the text between them)
    // directly above it, so no heading is stranded at the bottom of a Sheet.
    function withLeadingHeadings(n) {
      var start = n;
      for (var p = n.previousSibling; p; p = p.previousSibling) {
        if (p.nodeType === 1) { if (!isHeading(p)) break; start = p; }
      }
      if (!start.previousElementSibling) return null;   // nothing would stay behind: the Block cannot move
      var run = [];
      for (var q = start; q; q = q.nextSibling) run.push(q);
      return run;
    }

    var closeSheet = false;                       // the previous Sheet holds an Oversized Block
    newSheet();
    nodes.forEach(function (n) {
      var explicitBreak = n.nodeType === 1 && body.firstElementChild && getComputedStyle(n).breakBefore === 'page';
      if (n.nodeType === 1 && (closeSheet || explicitBreak)) { newSheet(); closeSheet = false; }
      body.appendChild(n);
      if (n.nodeType !== 1 || !overflows()) return;
      var run = withLeadingHeadings(n);
      if (run) {
        newSheet();
        run.forEach(function (x) { body.appendChild(x); });
      }
      if (overflows()) { oversized(n, sheets[sheets.length - 1], body); closeSheet = true; }
    });
    return sheets;
  }

  /* A Block taller than a whole Sheet: it keeps a Sheet to itself, grown to fit (never clipped),
     and the author is told to split it. */
  var MM = 96 / 25.4, warnings = [];
  function oversized(block, sheet, body) {
    var avail = body.clientHeight;
    sheet.classList.add('sheet--oversized');
    var tall = block.getBoundingClientRect().height;
    var h = null, heads = report.querySelectorAll('h2, h3');   // the last heading above the Block
    for (var i = 0; i < heads.length; i++) if (heads[i].compareDocumentPosition(block) & Node.DOCUMENT_POSITION_FOLLOWING) h = heads[i];
    var table = block.tagName === 'TABLE';
    var msg = (table ? 'Oversized table' : 'Oversized block') + '：' + (h ? '「' + h.textContent.trim() + '」下的' : '') +
      (table ? '表格' : '内容') + '高 ' + Math.round(tall / MM) + ' mm，超过一张 Sheet 的可用高度 ' +
      Math.round(avail / MM) + ' mm，已单独成页、未截断；请' + (table ? '拆成多张表。' : '拆分。');
    warnings.push(msg);
    console.warn('[jc-basic-report] ' + msg);
  }

  function showWarnings() {
    if (!warnings.length) return;
    var box = document.createElement('div');
    box.className = 'jc-pagination-warning';
    box.setAttribute('role', 'alert');
    warnings.forEach(function (w) { var p = document.createElement('p'); p.textContent = w; box.appendChild(p); });
    report.parentNode.insertBefore(box, report);  // outside #report: not part of the annotatable text
  }

  /* ---------- readiness: other scripts (tocbot, recogito, page chrome…) start only after this ---------- */
  var waiting = [], settled = false, resolveReady;
  var api = window.JCPaginator = {
    state: 'pending',                            // 'pending' | 'done' | 'off'
    sheets: [],
    warnings: warnings,
    ready: new Promise(function (r) { resolveReady = r; }),
    // Run fn once the Sheets are final (or at once when pagination is off). Called outside any
    // promise so an error in fn surfaces as a normal page error.
    whenReady: function (fn) { if (settled) fn(api); else waiting.push(fn); }
  };
  function settle(state) {
    api.state = state;
    root.setAttribute('data-pagination', state);
    settled = true;
    resolveReady(api);
    waiting.splice(0).forEach(function (fn) {   // one failing script must not stop the ones after it
      try { fn(api); } catch (err) { console.error(err); }
    });
    document.dispatchEvent(new CustomEvent('jc:paginated', { detail: api }));
  }

  // Undo a half-done pagination: the original nodes back in #report, in order, and no Sheet geometry.
  function unpaginate(original) {
    original.forEach(function (n) { report.appendChild(n); });
    Array.prototype.slice.call(report.querySelectorAll(':scope > .sheet')).forEach(function (s) { s.remove(); });
    root.classList.remove('jc-paginated');
    ['--sheet-w', '--sheet-h', '--sheet-mt', '--sheet-mr', '--sheet-mb', '--sheet-ml']
      .forEach(function (p) { root.style.removeProperty(p); });
  }

  if (!S.pagination.enabled) { settle('off'); return; }   // fallback: the original continuous scroll

  // Heights are only stable once fonts and images are in; a hung request must not block the Report.
  // Wait for DOMContentLoaded first: touching document.fonts flushes style, and the scripts after this
  // one (ui.js restoring the collapsed sidebar) must get to set the first style without a transition.
  root.setAttribute('data-pagination', 'pending');
  function whenLoaded(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn); else fn();
  }
  whenLoaded(function () {
    var loads = Array.prototype.map.call(report.querySelectorAll('img'), function (img) {
      img.loading = 'eager';
      if (img.complete) return Promise.resolve();
      return new Promise(function (r) { img.addEventListener('load', r); img.addEventListener('error', r); });
    });
    var fonts = document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve();
    var timeout = new Promise(function (r) { setTimeout(r, 8000); });
    Promise.race([Promise.all(loads.concat([fonts])), timeout]).then(function () {
      setTimeout(function () {                   // leave the promise chain: errors stay visible
        var original = Array.prototype.slice.call(report.childNodes);
        try {
          api.sheets = paginate();
        } catch (err) {                          // never leave a dead Report: fall back to continuous scroll
          console.error('[jc-basic-report] pagination failed, showing the Report as one continuous page:', err);
          unpaginate(original);
          settle('off');
          return;
        }
        showWarnings();
        settle('done');
      }, 0);
    });
  });
})();
