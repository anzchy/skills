(function () {
  'use strict';
  var META = document.querySelector('meta[name="report-id"]');
  var RID = (META && META.content) || location.pathname;
  var KEY_ANN = 'jc-report-ann:' + RID;
  var KEY_SIDE = 'kami-side-collapsed';
  var SOURCE = 'urn:report:' + RID;
  var KINDS = {
    'hl-yellow': { label: '黄色高亮', color: 'var(--hl-yellow, #F3E3A0)' },
    'hl-green':  { label: '绿色高亮', color: 'var(--hl-green, #D5E6C3)' },
    'hl-blue':   { label: '蓝色高亮', color: 'var(--hl-blue, #D6E2F0)' },
    'underline': { label: '划线',     color: 'var(--ul-red, #A4442B)' }
  };
  var BRAND = 'var(--brand, #1B365D)';
  /* Mark colours follow the Theme: CSS reads var() directly, the annotator needs the resolved value. */
  function paint(c) {
    var m = /^var\((--[\w-]+),\s*([^)]+)\)$/.exec(c);
    return m ? (getComputedStyle(document.documentElement).getPropertyValue(m[1]).trim() || m[2]) : c;
  }

  var root = document.documentElement;
  var report = document.getElementById('report');
  var side = document.getElementById('side');
  var toggleBtn = document.getElementById('side-toggle');
  root.classList.add('has-side');

  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* file:// 或隐私模式下不可用 */ } }
  };

  /* ---------- 侧栏折叠 ---------- */
  function setCollapsed(c) {
    root.classList.toggle('side-collapsed', c);
    toggleBtn.setAttribute('aria-expanded', String(!c));
    toggleBtn.setAttribute('title', c ? '展开侧栏' : '收起侧栏');
    toggleBtn.textContent = c ? '☰' : '«';
    store.set(KEY_SIDE, c ? '1' : '0');
  }
  var savedSide = store.get(KEY_SIDE);
  setCollapsed(savedSide === null ? window.innerWidth < 900 : savedSide === '1');
  toggleBtn.addEventListener('click', function () { setCollapsed(!root.classList.contains('side-collapsed')); });

  /* ---------- 标签页 ---------- */
  var tabs = side.querySelectorAll('.side-tab');
  function showTab(name) {
    tabs.forEach(function (t) {
      var on = t.dataset.tab === name;
      t.setAttribute('aria-selected', String(on));
      document.getElementById('pane-' + t.dataset.tab).hidden = !on;
    });
  }
  tabs.forEach(function (t) { t.addEventListener('click', function () { showTab(t.dataset.tab); }); });

  // Sidebar state above is restored at once (no flash); TOC and annotations wait for the final Sheets.
  (window.JCPaginator ? window.JCPaginator.whenReady : function (fn) { fn(); })(function () {
  /* ---------- 目录（tocbot） ---------- */
  report.querySelectorAll('h2, h3').forEach(function (h, i) { if (!h.id) h.id = 'sec-' + i; });
  // Headings like "〇、投资要点" carry a rating badge (.h2-rating); keep it out of TOC labels.
  var ratings = Array.prototype.map.call(report.querySelectorAll('.h2-rating'), function (e) { return e.textContent; });
  function stripRating(label) {
    ratings.forEach(function (r) {
      var chars = r.replace(/\s+/g, '').split('').map(function (c) { return c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); });
      if (chars.length) label = label.replace(new RegExp('\\s*' + chars.join('\\s*') + '\\s*$'), '');
    });
    return label.trim();
  }
  window.tocbot.init({
    tocSelector: '.js-toc',
    contentSelector: '#report',
    headingSelector: 'h2, h3',
    collapseDepth: 2,
    orderedList: false,
    scrollSmooth: true,
    scrollSmoothDuration: 300,
    headingsOffset: 24,
    scrollSmoothOffset: -16,
    hasInnerContainers: true,
    headingLabelCallback: stripRating
  });
  /* 目录页码：每项的页码与 tocbot 的点击跳转共用同一个目标（链接指向的标题），页码 = 该标题所在 Sheet 的序号。 */
  (function tocPageNumbers() {
    var P = window.JCPaginator, S = JSON.parse(document.getElementById('jc-settings').textContent);
    if (!P || P.state !== 'done' || !S.toc.pageNumbers) return;   // continuous scroll / switched off: no numbers
    side.querySelectorAll('.js-toc a.toc-link').forEach(function (a) {
      var target = document.getElementById(decodeURIComponent(a.hash.slice(1)));
      var n = target ? P.sheets.indexOf(target.closest('.sheet')) + 1 : 0;
      if (n > 0) a.setAttribute('data-page', String(n));   // drawn by CSS, so the label text stays unchanged
    });
  })();
  side.querySelector('.js-toc').addEventListener('click', function (e) {
    if (e.target.closest('a') && window.innerWidth < 900) setCollapsed(true);
  });

  /* ---------- 批注（Recogito Text Annotator，W3C Web Annotation 格式） ---------- */
  var R = window.RecogitoJS;
  function bodiesOf(a) {
    var b = a.bodies || a.body || [];
    return Array.isArray(b) ? b : [b];
  }
  function kindOf(a) {
    var t = bodiesOf(a).find(function (b) { return b.purpose === 'tagging' && KINDS[b.value]; });
    return t ? t.value : null;
  }
  function noteOf(a) {
    var c = bodiesOf(a).find(function (b) { return b.purpose === 'commenting'; });
    return c ? c.value : '';
  }
  function isKept(a) { return !!(kindOf(a) || noteOf(a)); }

  /* ---------- 定位：保存的位置若已不对应引文（报告修订、页面结构变化），按引文重新定位 ---------- */
  // The annotator revives a target from character offsets alone and never checks the quote, so a
  // shifted offset would paint the mark on other text. Annotations whose quote is gone are kept
  // apart (lost) and listed as 「未定位」 instead of being painted anywhere or silently dropped.
  var lost = [];
  function annotatableText() {   // the same text the annotator counts offsets in
    var w = document.createTreeWalker(report, NodeFilter.SHOW_TEXT, function (n) {
      return n.parentElement && n.parentElement.closest('.not-annotatable') ? NodeFilter.FILTER_SKIP : NodeFilter.FILTER_ACCEPT;
    });
    var t = '';
    for (var n = w.nextNode(); n; n = w.nextNode()) t += n.data;
    return t;
  }
  function common(a, b, fromEnd) {
    var i = 0, n = Math.min(a.length, b.length);
    while (i < n && (fromEnd ? a[a.length - 1 - i] === b[b.length - 1 - i] : a[i] === b[i])) i++;
    return i;
  }
  function anchorTarget(t, text) {
    var sels = Array.isArray(t.selector) ? t.selector : [t.selector || {}];
    var q = sels.find(function (s) { return s.type === 'TextQuoteSelector'; });
    var pos = sels.find(function (s) { return s.type === 'TextPositionSelector'; });
    if (!q || !q.exact) return pos ? t : null;
    if (pos && text.slice(pos.start, pos.end) === q.exact) return t;
    var len = q.exact.length, from = pos ? pos.start : 0, best = -1, bestScore = -1;
    for (var at = text.indexOf(q.exact); at >= 0; at = text.indexOf(q.exact, at + 1)) {
      var score = common(text.slice(Math.max(0, at - (q.prefix || '').length), at), q.prefix || '', true) +
                  common(text.slice(at + len, at + len + (q.suffix || '').length), q.suffix || '', false);
      if (score > bestScore || (score === bestScore && Math.abs(at - from) < Math.abs(best - from))) { best = at; bestScore = score; }
    }
    if (best < 0) return null;
    var moved = { type: 'TextPositionSelector', start: best, end: best + len };
    return Object.assign({}, t, { selector: sels.filter(function (s) { return s !== pos; }).concat([moved]) });
  }
  // The Annotation placed on the current text, or null when its quote is no longer in the Report.
  function anchor(a, text) {
    var many = Array.isArray(a.target), ts = (many ? a.target : [a.target]).map(function (t) { return anchorTarget(t || {}, text); });
    if (ts.some(function (t) { return !t; })) return null;
    return Object.assign({}, a, { target: many ? ts : ts[0] });
  }
  // Split stored Annotations into the ones to hand to the annotator and the lost ones.
  function place(arr) {
    var text = annotatableText(), ok = [];
    arr.forEach(function (a) {
      var placed = anchor(a, text);
      lost = lost.filter(function (x) { return x.id !== a.id; });
      if (placed) ok.push(placed); else lost.push(a);
    });
    return ok;
  }

  function styleFn(a, state) {
    var kind = kindOf(a), note = noteOf(a), sel = state && state.selected;
    if (!kind && !note) return { fill: paint(BRAND), fillOpacity: 0.16 };
    var s;
    if (kind === 'underline') {
      s = { fill: paint(KINDS.underline.color), fillOpacity: sel ? 0.10 : 0, underlineColor: paint(KINDS.underline.color), underlineThickness: 2, underlineOffset: 1 };
    } else {
      s = { fill: paint(KINDS[kind || 'hl-blue'].color), fillOpacity: sel ? 1 : 0.85 };
      if (!kind) s.fillOpacity = sel ? 0.6 : 0.35;
    }
    if (note && kind !== 'underline') {
      s.underlineColor = paint(BRAND); s.underlineStyle = 'dashed'; s.underlineThickness = 1.5; s.underlineOffset = 1;
    }
    return s;
  }

  var anno = R.createTextAnnotator(report, {
    adapter: R.W3CTextFormat(SOURCE, report),
    style: styleFn,
    userSelectAction: 'EDIT',
    dismissOnNotAnnotatable: function (e) { return !e.target.closest('.ann-pop, .side'); }
  });

  document.addEventListener('jc:themechange', function () { anno.setStyle(styleFn); });

  function save() {
    var keep = anno.getAnnotations().filter(isKept).concat(lost);
    store.set(KEY_ANN, JSON.stringify(keep));
    renderList();
  }
  function setBodies(id, kind, note) {
    var a = anno.getAnnotationById(id);
    if (!a) return;
    var others = bodiesOf(a).filter(function (b) { return b.purpose !== 'tagging' && b.purpose !== 'commenting'; });
    var now = new Date().toISOString();
    if (kind) others.push({ type: 'TextualBody', purpose: 'tagging', value: kind, created: now });
    if (note) others.push({ type: 'TextualBody', purpose: 'commenting', value: note, format: 'text/plain', created: now });
    a.body = others;
    anno.updateAnnotation(a);
    save();
  }

  /* ---------- 选区工具条 ---------- */
  var pop = document.createElement('div');
  pop.className = 'ann-pop';
  pop.setAttribute('role', 'toolbar');
  pop.setAttribute('aria-label', '批注工具');
  pop.innerHTML =
    '<div class="ann-row">' +
      Object.keys(KINDS).filter(function (k) { return k !== 'underline'; }).map(function (k) {
        return '<button type="button" data-kind="' + k + '" title="' + KINDS[k].label + '"><span class="dot" style="background:' + KINDS[k].color + '"></span></button>';
      }).join('') +
      '<button type="button" data-kind="underline" title="划线"><span style="text-decoration:underline;text-decoration-color:#e07a5f;text-decoration-thickness:2px;text-underline-offset:3px">划线</span></button>' +
      '<span class="sep"></span>' +
      '<button type="button" data-act="note" title="添加或编辑备注">备注</button>' +
      '<button type="button" data-act="delete" title="删除这条批注">删除</button>' +
    '</div>' +
    '<textarea placeholder="写下备注…（⌘/Ctrl + Enter 保存）" aria-label="备注内容"></textarea>' +
    '<div class="ann-save"><button type="button" data-act="cancel">取消</button><button type="button" class="primary" data-act="save">保存备注</button></div>';
  document.body.appendChild(pop);
  var ta = pop.querySelector('textarea');
  var tip = document.createElement('div');
  tip.className = 'ann-tip';
  document.body.appendChild(tip);

  var currentId = null;

  function rectOf(id) {
    try {
      var internal = anno.state.store.getAnnotation(id);
      var sels = internal && internal.target && internal.target.selector;
      if (sels && sels.length && sels[0].range) {
        var rects = sels[0].range.getClientRects();
        if (rects.length) return rects[0];
        return sels[0].range.getBoundingClientRect();
      }
    } catch (e) { /* 回退到浏览器选区 */ }
    var s = window.getSelection();
    return s && s.rangeCount ? s.getRangeAt(0).getBoundingClientRect() : null;
  }
  function placePop(id) {
    var r = rectOf(id);
    if (!r) return;
    pop.style.left = '0px'; pop.style.top = '0px';
    var w = pop.offsetWidth, h = pop.offsetHeight;
    var left = Math.min(Math.max(8, r.left + window.scrollX), window.scrollX + document.documentElement.clientWidth - w - 8);
    var top = r.top + window.scrollY - h - 8;
    if (r.top - h - 8 < 0) top = r.bottom + window.scrollY + 8;
    pop.style.left = left + 'px'; pop.style.top = top + 'px';
  }
  function openPop(id) {
    currentId = id;
    var a = anno.getAnnotationById(id);
    var kind = a ? kindOf(a) : null, note = a ? noteOf(a) : '';
    pop.querySelectorAll('[data-kind]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.kind === kind)); });
    pop.querySelector('[data-act="note"]').textContent = note ? '编辑备注' : '备注';
    ta.value = note;
    pop.classList.remove('noting');
    pop.classList.add('open');
    placePop(id);
  }
  function closePop() {
    var id = currentId;
    currentId = null;
    pop.classList.remove('open', 'noting');
    if (id) {
      var a = anno.getAnnotationById(id);
      if (a && !isKept(a)) anno.removeAnnotation(id);
    }
  }
  function finish() { anno.cancelSelected(); closePop(); }

  pop.addEventListener('mousedown', function (e) { if (e.target !== ta) e.preventDefault(); });
  pop.addEventListener('click', function (e) {
    var b = e.target.closest('button');
    if (!b || !currentId) return;
    var a = anno.getAnnotationById(currentId);
    if (!a) return;
    if (b.dataset.kind) {
      var k = kindOf(a) === b.dataset.kind ? null : b.dataset.kind;
      setBodies(currentId, k, noteOf(a));
      finish();
    } else if (b.dataset.act === 'note') {
      pop.classList.add('noting');
      placePop(currentId);
      ta.focus();
    } else if (b.dataset.act === 'save') {
      var kind = kindOf(a) || (ta.value.trim() ? 'hl-yellow' : null);
      setBodies(currentId, kind, ta.value.trim());
      finish();
    } else if (b.dataset.act === 'cancel') {
      pop.classList.remove('noting');
      placePop(currentId);
    } else if (b.dataset.act === 'delete') {
      var id = currentId;
      currentId = null;
      anno.removeAnnotation(id);
      save();
      finish();
    }
  });
  ta.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); pop.querySelector('[data-act="save"]').click(); }
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && currentId) finish(); });
  window.addEventListener('resize', function () { if (currentId) placePop(currentId); });

  anno.on('selectionChanged', function (sel) {
    if (sel && sel.length) {
      var id = sel[0].id;
      if (currentId && currentId !== id) closePop();
      openPop(id);
    } else if (currentId) {
      closePop();
    }
  });
  anno.on('updateAnnotation', function (a) { if (a && a.id === currentId) placePop(a.id); });
  anno.on('deleteAnnotation', function () { save(); });
  anno.on('mouseEnterAnnotation', function (a) {
    var note = noteOf(a);
    if (!note || currentId) return;
    var r = rectOf(a.id);
    if (!r) return;
    tip.textContent = note;
    tip.style.display = 'block';
    tip.style.left = Math.max(8, r.left + window.scrollX) + 'px';
    tip.style.top = (r.bottom + window.scrollY + 6) + 'px';
  });
  anno.on('mouseLeaveAnnotation', function () { tip.style.display = 'none'; });

  /* ---------- 批注列表 ---------- */
  var list = document.getElementById('ann-list');
  var count = document.getElementById('ann-count');
  function selectorInfo(a) {
    var targets = Array.isArray(a.target) ? a.target : [a.target || {}];
    var sels = [];
    targets.forEach(function (t) { var s = t.selector || []; sels = sels.concat(Array.isArray(s) ? s : [s]); });
    var quote = '', start = Infinity;
    sels.forEach(function (s) {
      if (s.exact || s.quote) quote = quote || s.exact || s.quote;
      if (typeof s.start === 'number') start = Math.min(start, s.start);
    });
    return { quote: quote, start: start };
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function sectionOf(a) {
    try {
      var internal = anno.state.store.getAnnotation(a.id);
      var node = internal.target.selector[0].range.startContainer;
      var el = node.nodeType === 1 ? node : node.parentElement;
      var hs = report.querySelectorAll('h2'), last = '';
      for (var i = 0; i < hs.length; i++) {
        if (hs[i].compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING || hs[i] === el) last = hs[i].firstChild.textContent.trim();
      }
      return last;
    } catch (e) { return ''; }
  }
  function renderList() {
    var items = anno.getAnnotations().filter(isKept).map(function (a) {
      var i = selectorInfo(a);
      return { a: a, quote: i.quote, start: i.start };
    }).sort(function (x, y) { return x.start - y.start; });
    items = items.concat(lost.map(function (a) { return { a: a, quote: selectorInfo(a).quote, lost: true }; }));
    count.textContent = items.length ? '（' + items.length + '）' : '';
    if (!items.length) {
      list.innerHTML = '<p class="ann-hint">暂无批注。</p>';
      return;
    }
    list.innerHTML = items.map(function (it) {
      var k = kindOf(it.a), n = noteOf(it.a), sec = it.lost ? '' : sectionOf(it.a);
      var sw = k ? '<span class="ann-swatch" style="background:' + KINDS[k].color + '"></span>' : '';
      var meta = it.lost ? '<span class="ann-lost" title="原文已找不到这段文字，批注仍保留">未定位</span>' : esc(sec);
      return '<div class="ann-item' + (it.lost ? ' ann-item--lost' : '') + '" data-id="' + esc(it.a.id) + '" tabindex="0">' +
        '<div class="ann-quote">' + sw + esc(it.quote) + '</div>' +
        (n ? '<div class="ann-note">' + esc(n) + '</div>' : '') +
        (meta ? '<div class="ann-meta">' + meta + '</div>' : '') +
      '</div>';
    }).join('');
  }
  function jump(id) {
    if (lost.some(function (a) { return a.id === id; })) return;   // nowhere to scroll to
    anno.scrollIntoView(id);
    setTimeout(function () { anno.setSelected(id); }, 350);
    if (window.innerWidth < 900) setCollapsed(true);
  }
  list.addEventListener('click', function (e) { var it = e.target.closest('.ann-item'); if (it) jump(it.dataset.id); });
  list.addEventListener('keydown', function (e) { var it = e.target.closest('.ann-item'); if (it && e.key === 'Enter') jump(it.dataset.id); });

  /* ---------- 导出 / 导入 / 清空 ---------- */
  document.getElementById('ann-export').addEventListener('click', function () {
    var data = { '@context': 'http://www.w3.org/ns/anno.jsonld', source: SOURCE, exported: new Date().toISOString(), annotations: anno.getAnnotations().filter(isKept).concat(lost) };
    var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = (document.title || '报告').replace(/[\\/:*?"<>|\s·]+/g, '-') + '-批注-' + new Date().toISOString().slice(0, 10) + '.json';
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  });
  var fileIn = document.getElementById('ann-file');
  document.getElementById('ann-import').addEventListener('click', function () { fileIn.click(); });
  fileIn.addEventListener('change', function () {
    var f = fileIn.files && fileIn.files[0];
    if (!f) return;
    f.text().then(function (txt) {
      var data = JSON.parse(txt);
      var arr = Array.isArray(data) ? data : (data.annotations || []);
      arr = arr.filter(function (a) { return a && a.id && a.target; });
      var placed = place(arr);
      arr.forEach(function (a) {   // an imported copy that cannot be placed replaces the painted one
        if (!placed.some(function (p) { return p.id === a.id; }) && anno.getAnnotationById(a.id)) anno.removeAnnotation(a.id);
      });
      placed.forEach(function (a) {
        if (anno.getAnnotationById(a.id)) anno.updateAnnotation(a); else anno.addAnnotation(a);
      });
      var n = arr.length;
      save();
      alert('已导入 ' + n + ' 条批注。');
    }).catch(function (err) { alert('导入失败：' + err.message); });
    fileIn.value = '';
  });
  document.getElementById('ann-clear').addEventListener('click', function () {
    if (!anno.getAnnotations().filter(isKept).length && !lost.length) return;
    if (confirm('确定清空本报告的全部批注？建议先导出备份。')) { lost = []; anno.clearAnnotations(); save(); }
  });

  /* ---------- 恢复已保存的批注 ---------- */
  try {
    var saved = JSON.parse(store.get(KEY_ANN) || '[]');
    if (saved.length) anno.setAnnotations(place(saved));
  } catch (e) { /* 存储损坏时忽略 */ }
  renderList();

  window.__report = { anno: anno, save: save };
  });
})();
