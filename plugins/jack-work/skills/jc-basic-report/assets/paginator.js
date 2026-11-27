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
      if (n.nodeType === 1 && closeSheet) { newSheet(); closeSheet = false; }
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
  var warnings = [];
  function oversized(block, sheet, body) {
    var avail = body.clientHeight;
    sheet.classList.add('sheet--oversized');
    var tall = block.getBoundingClientRect().height;
    var h = null;
    for (var p = block.previousElementSibling; p && !h; p = p.previousElementSibling) if (/^H[1-6]$/.test(p.tagName)) h = p;
    if (!h) {
      var all = report.querySelectorAll('h2, h3');
      for (var i = 0; i < all.length; i++) if (all[i].compareDocumentPosition(block) & Node.DOCUMENT_POSITION_FOLLOWING) h = all[i];
    }
    var where = h ? '「' + h.textContent.trim() + '」下的' : '';
    var what = block.tagName === 'TABLE' ? 'Oversized table' : 'Oversized block';
    var msg = what + '：' + where + (block.tagName === 'TABLE' ? '表格' : '内容') + '高 ' + Math.round(tall / MM) +
      ' mm，超过一张 Sheet 的可用高度 ' + Math.round(avail / MM) + ' mm，已单独成页、未截断；请拆成多张表。';
    warnings.push(msg);
    console.warn('[jc-basic-report] ' + msg);
  }
  var MM = 96 / 25.4;

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
    waiting.splice(0).forEach(function (fn) { fn(api); });
    document.dispatchEvent(new CustomEvent('jc:paginated', { detail: api }));
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
        api.sheets = paginate();
        showWarnings();
        settle('done');
      }, 0);
    });
  });
})();
