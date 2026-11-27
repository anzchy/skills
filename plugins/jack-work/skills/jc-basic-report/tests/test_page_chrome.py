"""Seam: the built Report in a browser — the Page chrome (header + centred page number) on each Sheet.

Chrome text is painted by the page, not part of the annotatable text, so it is read the way it is
rendered: the visible text of each Sheet's header / footer area (pseudo-element content included).
"""
from __future__ import annotations

from test_pagination import MM, build_sample, open_report

# Visible text of the header and footer areas of every Sheet, in order ("" when none is shown).
CHROME = """() => {
  const painted = el => {
    if (!el || getComputedStyle(el).display === 'none' || getComputedStyle(el).visibility === 'hidden') return '';
    const parts = [];
    const walk = n => {
      const b = getComputedStyle(n, '::before').content, a = getComputedStyle(n, '::after').content;
      const txt = c => (c && c !== 'none' && c !== 'normal') ? JSON.parse(c) : '';
      parts.push(txt(b));
      n.childNodes.forEach(c => c.nodeType === 3 ? parts.push(c.textContent) : c.nodeType === 1 && walk(c));
      parts.push(txt(a));
    };
    walk(el);
    return parts.join(' ').replace(/\\s+/g, ' ').trim();
  };
  return [...document.querySelectorAll('#report .sheet')].map(s => {
    const sr = s.getBoundingClientRect(), body = s.querySelector('.sheet-body').getBoundingClientRect();
    const box = el => { if (!el) return null; const r = el.getBoundingClientRect();
      return {top: r.top - sr.top, bottom: r.bottom - sr.top, left: r.left - sr.left, right: sr.right - r.right,
              cx: (r.left + r.right) / 2 - (sr.left + sr.right) / 2, h: r.height}; };
    const head = s.querySelector('.sheet-header'), foot = s.querySelector('.sheet-footer');
    return {header: painted(head), footer: painted(foot), headBox: box(head), footBox: box(foot),
            bodyTop: body.top - sr.top, bodyBottom: body.bottom - sr.top};
  });
}"""


def test_first_sheet_has_no_header_and_later_sheets_show_the_company_header(context, report_path):
    page = open_report(context, report_path)

    chrome = page.evaluate(CHROME)

    assert len(chrome) >= 3
    assert chrome[0]["header"] == ""
    for c in chrome[1:]:
        # The sample's title is "沐曦股份 · 项目基本信息报告（样例）": {company} is the part before "·".
        # The default template "{company} · 项目基本信息报告" puts the company left, the report name right.
        assert c["header"] == "沐曦股份 项目基本信息报告", c


def test_every_sheet_footer_shows_a_continuous_page_number_out_of_the_sheet_count(context, report_path):
    page = open_report(context, report_path)

    chrome = page.evaluate(CHROME)

    n = len(chrome)
    assert n >= 3
    # The first Sheet has no header but is page 1; numbering is continuous and Y is the Sheet count.
    assert [c["footer"] for c in chrome] == [f"第 {i} 页 共 {n} 页" for i in range(1, n + 1)]


def test_chrome_sits_in_the_sheet_margins_with_the_page_number_centred(context, report_path):
    page = open_report(context, report_path)

    chrome = page.evaluate(CHROME)

    for i, c in enumerate(chrome):
        foot = c["footBox"]
        assert foot["top"] >= c["bodyBottom"] - 0.5, (i, c)        # below the text, in the bottom margin
        assert foot["bottom"] <= c["bodyBottom"] + 18 * MM + 0.5, (i, c)
        assert abs(foot["cx"]) < 1, (i, c)                          # horizontally centred on the Sheet
        if i:
            head = c["headBox"]
            assert head["top"] >= -0.5 and head["bottom"] <= c["bodyTop"] + 0.5, (i, c)   # top margin


def test_header_and_page_number_formats_come_from_settings(context, tmp_path):
    out = build_sample(tmp_path, {"chrome": {"headerTemplate": "{company} 尽调", "footerTemplate": "- {page} -"}})
    page = open_report(context, out)

    chrome = page.evaluate(CHROME)

    assert chrome[0]["header"] == ""
    assert {c["header"] for c in chrome[1:]} == {"沐曦股份 尽调"}
    assert [c["footer"] for c in chrome] == [f"- {i} -" for i in range(1, len(chrome) + 1)]


def test_chrome_stays_out_of_the_annotatable_text(context, report_path):
    page = open_report(context, report_path)

    text = page.evaluate("document.getElementById('report').textContent")
    page.locator("#report .sheet").nth(1).scroll_into_view_if_needed()
    page.keyboard.press("ControlOrMeta+a")
    selected = page.evaluate("String(getSelection())")

    assert "第 2 页" not in text and "共 " not in text
    assert "第 2 页" not in selected


def test_no_chrome_when_pagination_is_off(context, tmp_path):
    out = build_sample(tmp_path, {"pagination": {"enabled": False}})
    page = open_report(context, out)

    assert page.locator("#report .sheet-header, #report .sheet-footer").count() == 0
