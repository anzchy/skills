/* SPIKE — throwaway. Paginator + theme switcher + TOC page numbers. */
(function () {
  var S = JSON.parse(document.getElementById('jc-settings').textContent);
  var root = document.documentElement;
  var MM = 96 / 25.4;

  /* ---------- Theme ---------- */
  function applyTheme(t) { root.setAttribute('data-theme', t); try { localStorage.setItem('jc-theme', t); } catch (e) {} }
  var saved = null; try { saved = localStorage.getItem('jc-theme'); } catch (e) {}
  applyTheme(S.themes[saved] ? saved : S.defaultTheme);

  window.JCSpike = { phase: 'paginate', warnings: [], sheets: 0 };
  var report = document.getElementById('report');
  if (!S.pagination.enabled) { window.JCSpike.phase = 'disabled'; return; }

  /* ---------- Paginator (block-level, never splits a Block) ---------- */
  var M = S.paper.marginMm;
  var textBefore = report.textContent.replace(/\s+/g, '');
  var blocks = Array.prototype.slice.call(report.children);
  var companyEl = report.querySelector('.ticker-name');
  var company = companyEl ? companyEl.childNodes[0].textContent.trim() : '';

  function newSheet() {
    var s = document.createElement('div'); s.className = 'sheet';
    s.style.cssText = 'width:210mm;height:297mm;padding:' + M.top + 'mm ' + M.right + 'mm ' + M.bottom + 'mm ' + M.left + 'mm';
    s.innerHTML = '<div class="sheet-head"></div><div class="sheet-body"></div><div class="sheet-foot"></div>';
    report.appendChild(s);
    return s;
  }
  function overflows(sheet) { var b = sheet.querySelector('.sheet-body'); return b.scrollHeight > b.clientHeight + 1; }
  function isHeading(n) { return /^H[23]$/.test(n.tagName); }

  report.innerHTML = '';
  var sheet = newSheet(), body = sheet.querySelector('.sheet-body');
  blocks.forEach(function (blk) {
    if (blk.nodeType !== 1) return;
    body.appendChild(blk);
    if (!overflows(sheet)) return;
    if (body.children.length === 1) {            // alone and still too tall -> Oversized
      var what = blk.tagName.toLowerCase() + (blk.className ? '.' + blk.className : '');
      window.JCSpike.warnings.push('Oversized ' + what + ' (' + Math.round(blk.getBoundingClientRect().height / MM) + 'mm > ' + Math.round(body.clientHeight / MM) + 'mm)');
      blk.classList.add('oversized');
      return;
    }
    var carry = [blk];                           // headings must not be stranded at the bottom
    body.removeChild(blk);
    while (body.children.length > 1 && isHeading(body.lastElementChild)) carry.unshift(body.removeChild(body.lastElementChild));
    sheet = newSheet(); body = sheet.querySelector('.sheet-body');
    carry.forEach(function (n) { body.appendChild(n); });
  });
  var sheets = report.querySelectorAll('.sheet');
  window.JCSpike.sheets = sheets.length;
  window.JCSpike.textPreserved = textBefore === report.textContent.replace(/\s+/g, '').replace(new RegExp(''), '');

  /* ---------- Page chrome ---------- */
  var n = sheets.length;
  sheets.forEach(function (sh, i) {
    var head = sh.querySelector('.sheet-head'), foot = sh.querySelector('.sheet-foot');
    if (i > 0 || S.chrome.headerOnFirstSheet) head.textContent = S.chrome.headerTemplate.replace('{company}', company);
    foot.textContent = S.chrome.footerTemplate.replace('{page}', i + 1).replace('{pages}', n);
  });
  // Chrome text lives outside #report text stream? It is inside, so exclude it from annotation via data attribute.
  window.JCSpike.textPreserved = textBefore === Array.prototype.map.call(report.querySelectorAll('.sheet-body'), function (b) { return b.textContent; }).join('').replace(/\s+/g, '');
  window.JCSpike.phase = 'paginated';

  /* ---------- after ui.js: TOC page numbers + theme switcher ---------- */
  window.addEventListener('load', function () {
    function stamp() {
      if (!S.toc.pageNumbers) return;
      document.querySelectorAll('.js-toc a.toc-link').forEach(function (a) {
        if (a.querySelector('.toc-pg')) return;
        var id = decodeURIComponent((a.getAttribute('href') || '').slice(1)), h = document.getElementById(id);
        var sh = h && h.closest('.sheet'); if (!sh) return;
        var pg = Array.prototype.indexOf.call(report.querySelectorAll('.sheet'), sh) + 1;
        var s = document.createElement('span'); s.className = 'toc-pg'; s.textContent = pg; a.appendChild(s);
      });
    }
    stamp();
    new MutationObserver(stamp).observe(document.querySelector('.js-toc'), { childList: true, subtree: true });

    var bar = document.createElement('div'); bar.className = 'theme-bar';
    bar.innerHTML = '<span>主题</span>' + [['white', '白'], ['black', '黑'], ['beige', '米']].map(function (t) {
      return '<button type="button" data-theme="' + t[0] + '" title="' + t[1] + '色主题">' + t[1] + '</button>'; }).join('');
    var tabs = document.querySelector('.side-tabs'); tabs.parentNode.insertBefore(bar, tabs);
    function mark() { var cur = root.getAttribute('data-theme'); bar.querySelectorAll('button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.theme === cur)); }); }
    bar.addEventListener('click', function (e) { var b = e.target.closest('button'); if (b) { applyTheme(b.dataset.theme); mark(); } });
    mark();
    window.JCSpike.phase = 'ready';
  });
})();
