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

    newSheet();
    nodes.forEach(function (n) {
      body.appendChild(n);
      if (n.nodeType !== 1 || !overflows()) return;
      var run = withLeadingHeadings(n);
      if (!run) return;
      newSheet();
      run.forEach(function (x) { body.appendChild(x); });
    });
    return sheets;
  }

  if (!S.pagination.enabled) {                   // fallback: the original continuous scroll
    root.setAttribute('data-pagination', 'off');
    return;
  }
  paginate();
  root.setAttribute('data-pagination', 'done');
})();
