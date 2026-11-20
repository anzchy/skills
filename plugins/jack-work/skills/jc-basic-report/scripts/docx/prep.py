"""Step A: render charts to PNG and rewrite the report DOM into pandoc-friendly HTML.

Usage: python prep.py <report.html> <outdir>
Writes <outdir>/main.html, <outdir>/imgs/chartN.png, <outdir>/meta.json
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

src = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
(out / "imgs").mkdir(parents=True, exist_ok=True)

TRANSFORM = r"""
() => {
  const R = document.querySelector('#report');
  const q = (s, el=R) => [...el.querySelectorAll(s)];
  const txt = el => el ? el.textContent.trim() : '';
  // 1. drop UI that has no place in a document
  q('script, button, .ann-tools, .ann-save, .ann-item, .ann-hint', document).forEach(e => e.remove());

  // 2. header block -> two borderless tables
  const hdr = R.querySelector('.report-header');
  if (hdr) {
    const t = document.createElement('table');
    t.dataset.kind = 'header';
    t.innerHTML = `<tbody><tr>
      <td><p data-k="eyebrow">${txt(hdr.querySelector('.ticker-eyebrow'))}</p>
          <p data-k="name">${[...hdr.querySelector('.ticker-name').childNodes].map(n => n.nodeType===3 ? n.textContent : `<span data-custom-style="K_nameSub">${n.textContent}</span>`).join('')}</p>
          <p data-k="sub">${txt(hdr.querySelector('.ticker-sub'))}</p></td>
      <td><p data-k="price">${txt(hdr.querySelector('.price-current'))}</p>
          <p data-k="change">${txt(hdr.querySelector('.price-change'))}</p>
          <p data-k="date">${txt(hdr.querySelector('.price-date'))}</p></td></tr></tbody>`;
    hdr.replaceWith(t);
  }
  const mets = R.querySelector('.metrics');
  if (mets) {
    const t = document.createElement('table');
    t.dataset.kind = 'metrics';
    t.innerHTML = '<tbody><tr>' + q('.metric', mets).map(m =>
      `<td><p data-k="mval">${txt(m.querySelector('.metric-value'))}</p><p data-k="mlab">${txt(m.querySelector('.metric-label'))}</p></td>`
    ).join('') + '</tr></tbody>';
    mets.replaceWith(t);
  }
  // 3. rating badge in the first h2
  q('.h2-rating').forEach(s => {
    const word = s.querySelector('b');
    const lead = [...s.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
    s.outerHTML = `<span data-custom-style="RatingLead">${lead}</span><span data-custom-style="RatingWord">${word ? word.textContent.trim() : ''}</span>`;
  });

  // 4. inline tags -> named Word character styles
  const map = {'gap':'Gap','hl':'Hl'};
  q('span.gap, span.hl').forEach(s => { s.dataset.customStyle = map[s.classList[0]]; });
  q('span.dir').forEach(s => {
    s.dataset.customStyle = s.classList.contains('up') ? 'DirUp' : s.classList.contains('down') ? 'DirDown' : 'DirMid';
  });
  // 5. paragraph-level named styles
  const wrap = (el, style) => { const d = document.createElement('div'); d.dataset.customStyle = style; el.replaceWith(d); d.appendChild(el); };
  q('p.note').forEach(p => wrap(p, 'Note'));
  q('p.verdict-lead').forEach(p => wrap(p, 'VerdictLead'));

  // 6. risk cards and verdict list -> 2-column tables
  q('.risk-grid').forEach(g => {
    const t = document.createElement('table');
    t.dataset.kind = 'risk';
    t.innerHTML = '<tbody>' + q('.risk-item', g).map(it =>
      `<tr><td><strong>${it.querySelector('.risk-label').innerHTML}</strong></td><td>${it.querySelector('.risk-desc').innerHTML}</td></tr>`).join('') + '</tbody>';
    g.replaceWith(t);
  });
  q('dl.verdict-list').forEach(dl => {
    const dts = q('dt', dl), dds = q('dd', dl);
    const t = document.createElement('table');
    t.dataset.kind = 'verdict';
    t.innerHTML = '<tbody>' + dts.map((dt, i) => `<tr><td><strong>${dt.innerHTML}</strong></td><td>${dds[i] ? dds[i].innerHTML : ''}</td></tr>`).join('') + '</tbody>';
    dl.replaceWith(t);
  });
  // 6b. sources list: the 〔Sx〕 label is the number; drop the automatic ordinal
  q('ol.sources').forEach(ol => {
    const d = document.createElement('div');
    d.innerHTML = q('li', ol).map(li => `<div data-custom-style="Source"><p>${li.innerHTML}</p></div>`).join('');
    ol.replaceWith(d);
  });
  // 7. emphasis that CSS carried
  q('tr.total td, td.group').forEach(td => { td.innerHTML = '<strong>' + td.innerHTML + '</strong>'; });

  // 7b. two-column chart rows (CSS grid .two-col) -> a borderless two-cell table, charts sized to half the line
  q('.two-col').forEach(g => {
    const t = document.createElement('table');
    t.dataset.kind = 'twocol';
    t.innerHTML = '<tbody><tr>' + [...g.children].map(c => '<td>' + c.outerHTML + '</td>').join('') + '</tr></tbody>';
    g.replaceWith(t);
    t.querySelectorAll('img').forEach(img => img.setAttribute('width', Math.min(+img.getAttribute('width') || 300, 300)));
  });

  // 8. record per-table kind and column widths (same order pandoc will emit)
  const tables = q('table').map(t => {
    const kind = t.dataset.kind || (t.classList.contains('financial') ? 'financial'
               : t.classList.contains('spec') ? 'spec' : 'compact');
    const first = t.querySelector('tr');
    const widths = first ? [...first.children].map(c => {
      const m = (c.getAttribute('style') || '').match(/width:\s*([\d.]+)%/); return m ? +m[1] : null; }) : [];
    const lens = [];
    [...t.querySelectorAll('tr')].forEach(tr => [...tr.children].forEach((c, i) => {
      const L = c.textContent.trim().length; lens[i] = Math.max(lens[i] || 0, Math.min(L, 60)); }));
    return {kind, widths, lens};
  });
  return {html: R.innerHTML, tables, title: document.title.trim()};
}
"""

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=3)
    pg.route("**/*.ttf", lambda r: r.abort())
    pg.goto(src.as_uri(), wait_until="load")
    pg.wait_for_timeout(800)
    # grow each svg's viewBox to its painted content so overflowing labels are not cropped
    pg.evaluate("""() => document.querySelectorAll('#report svg').forEach(s => {
        const bb = s.getBBox(); const vb = s.viewBox.baseVal;
        if (!vb || !vb.width) return;
        const pad = 4;
        const x0 = Math.min(vb.x, bb.x - pad), y0 = Math.min(vb.y, bb.y - pad);
        const x1 = Math.max(vb.x + vb.width, bb.x + bb.width + pad), y1 = Math.max(vb.y + vb.height, bb.y + bb.height + pad);
        const r = s.getBoundingClientRect(), k = r.width / vb.width;
        s.setAttribute('viewBox', `${x0} ${y0} ${x1 - x0} ${y1 - y0}`);
        s.style.width = ((x1 - x0) * k) + 'px'; s.style.height = ((y1 - y0) * k) + 'px'; s.style.maxWidth = 'none';
    })""")
    charts = []
    svgs = pg.locator("#report svg")
    for i in range(svgs.count()):
        el = svgs.nth(i)
        el.scroll_into_view_if_needed()
        box = el.bounding_box()
        name = f"chart{i+1}.png"
        el.screenshot(path=str(out / "imgs" / name))
        charts.append({"file": name, "width": round(box["width"]), "height": round(box["height"])})
    # swap each svg for an <img> pointing at its PNG
    pg.evaluate("""(charts) => {
        [...document.querySelectorAll('#report svg')].forEach((s, i) => {
            const img = document.createElement('img');
            img.src = 'imgs/' + charts[i].file;
            img.setAttribute('width', Math.min(charts[i].width, 620));
            img.alt = '';
            s.replaceWith(img);
        });
    }""", charts)
    res = pg.evaluate(TRANSFORM)
    b.close()

(out / "main.html").write_text(
    '<!doctype html><html><head><meta charset="utf-8"></head><body>' + res["html"] + "</body></html>",
    encoding="utf-8")
(out / "meta.json").write_text(json.dumps({"title": res["title"], "charts": charts, "tables": res["tables"]}, ensure_ascii=False, indent=1),
                               encoding="utf-8")
print(f"charts={len(charts)} tables={len(res['tables'])}")
print([t["kind"] for t in res["tables"]])
