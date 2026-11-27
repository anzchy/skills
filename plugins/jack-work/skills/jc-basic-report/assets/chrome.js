/* jc-basic-report Page chrome: a header and a centred page number on every Sheet.
   Runs once the Paginator has laid out the Sheets. The text is painted with CSS
   `content: attr(...)`, so it never enters #report's annotatable text. */
(function () {
  'use strict';
  var S = JSON.parse(document.getElementById('jc-settings').textContent);

  // {company} is the document title up to its first "·" (same rule as the docx export).
  function company() { return document.title.split('·')[0].trim(); }

  function fill(template, vars) {
    return template.replace(/\{(\w+)\}/g, function (m, k) { return k in vars ? String(vars[k]) : m; });
  }

  // "{company} · 项目基本信息报告" -> company on the left, report name on the right.
  function headerParts(text) {
    var i = text.indexOf('·');
    return i < 0 ? [text.trim(), ''] : [text.slice(0, i).trim(), text.slice(i + 1).trim()];
  }

  function chrome(api) {
    if (api.state !== 'done') return;                 // pagination off: continuous scroll, no chrome
    var vars = { company: company() };
    var parts = headerParts(fill(S.chrome.headerTemplate, vars));
    var pages = api.sheets.length;
    api.sheets.forEach(function (sheet, i) {
      var foot = document.createElement('div');
      foot.className = 'sheet-footer';
      foot.setAttribute('data-text', fill(S.chrome.footerTemplate, { company: vars.company, page: i + 1, pages: pages }));
      sheet.appendChild(foot);
      if (i === 0) return;                            // the title Sheet: no header, but counted
      var head = document.createElement('div');
      head.className = 'sheet-header';
      head.setAttribute('data-left', parts[0]);
      head.setAttribute('data-right', parts[1]);
      sheet.appendChild(head);
    });
  }

  window.JCPaginator.whenReady(chrome);
})();
