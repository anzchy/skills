"""Seam: the built Report in a browser — its body laid out as A4 Sheets by the Paginator.

Geometry is read from the page the way a reader sees it (bounding boxes in CSS px, 96 px = 1 in).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from conftest import FIXTURE, run_build

MM = 96 / 25.4


def mm(px: float) -> float:
    return px / MM


def open_report(context, path: Path, url_suffix: str = ""):
    page = context.new_page()
    page.goto(path.as_uri() + url_suffix, wait_until="domcontentloaded")
    page.wait_for_selector("html[data-pagination='done'], html[data-pagination='off']",
                           state="attached", timeout=10000)
    return page


def build_sample(tmp_path: Path, override: dict | None = None, extra_body: str = "") -> Path:
    """The bundled sample report, optionally with a settings override and extra Blocks before </main>."""
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    for p in FIXTURE.rglob("*"):
        if p.is_file():
            dest = src_dir / p.relative_to(FIXTURE)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(p.read_bytes())
    src = src_dir / "report.src.html"
    if extra_body:
        html = src.read_text(encoding="utf-8")
        src.write_text(html.replace("</main>", extra_body + "\n</main>", 1), encoding="utf-8")
    if override is not None:
        (src_dir / "settings.json").write_text(json.dumps(override), encoding="utf-8")
    out = tmp_path / "report.html"
    res = run_build(src, out)
    assert res.returncode == 0, res.stderr
    return out


def sheet_boxes(page) -> list[dict]:
    return page.evaluate("""() => [...document.querySelectorAll('#report .sheet')].map(s => {
        const r = s.getBoundingClientRect(); return {top: r.top + scrollY, bottom: r.bottom + scrollY,
        width: r.width, height: r.height}; })""")


def test_the_body_is_laid_out_as_several_a4_sheets(context, report_path):
    page = open_report(context, report_path)

    boxes = sheet_boxes(page)

    assert len(boxes) >= 3, "the sample report is several A4 Sheets long"
    for b in boxes:
        assert abs(mm(b["width"]) - 210) < 0.5 and abs(mm(b["height"]) - 297) < 0.5, b


BLOCK_GEOMETRY = """() => [...document.querySelectorAll('#report .sheet')].flatMap((s, i) => {
    const sr = s.getBoundingClientRect();
    return [...s.querySelectorAll('h2, h3, p, ul, ol, table, figure, .metrics, .report-header, .risk-grid, .verdict')]
      .filter(el => !el.parentElement.closest('table, figure, .verdict, .risk-grid, .report-header, .metrics, ul, ol'))
      .map(el => { const r = el.getBoundingClientRect();
        return {sheet: i, tag: el.tagName, cls: el.className, text: el.textContent.trim().slice(0, 30),
                top: (r.top - sr.top), bottom: (r.bottom - sr.top), left: (r.left - sr.left),
                right: (sr.right - r.right), sheetHeight: sr.height}; }); })"""


def test_page_margins_come_from_settings(context, tmp_path):
    out = build_sample(tmp_path, {"paper": {"marginMm": {"top": 30, "right": 22, "bottom": 40, "left": 25}}})
    page = open_report(context, out)

    blocks = page.evaluate(BLOCK_GEOMETRY)

    heads = [b for b in blocks if b["tag"] == "H2"]
    assert heads and all(abs(mm(b["left"]) - 25) < 0.5 for b in heads), heads[:3]
    assert all(mm(b["right"]) >= 22 - 0.5 for b in blocks)
    assert min(mm(b["top"]) for b in blocks) >= 30 - 0.5
    assert all(mm(b["sheetHeight"] - b["bottom"]) >= 40 - 0.5 for b in blocks), \
        "no Block reaches into the bottom margin"


def test_tables_and_figures_sit_whole_on_one_sheet(context, report_path):
    page = open_report(context, report_path)
    m = page.evaluate("JSON.parse(document.getElementById('jc-settings').textContent).paper.marginMm")

    blocks = page.evaluate(BLOCK_GEOMETRY)

    tables = [b for b in blocks if b["tag"] in ("TABLE", "FIGURE")]
    assert len(tables) >= 8
    for b in tables:
        assert mm(b["top"]) >= m["top"] - 0.5 and mm(b["sheetHeight"] - b["bottom"]) >= m["bottom"] - 0.5, b


def test_a_heading_is_never_left_alone_at_the_bottom_of_a_sheet(context, report_path):
    page = open_report(context, report_path)

    blocks = page.evaluate(BLOCK_GEOMETRY)

    for i, b in enumerate(blocks):
        if b["tag"] in ("H2", "H3"):
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            assert nxt and nxt["sheet"] == b["sheet"], f"heading {b['text']!r} is stranded on sheet {b['sheet'] + 1}"


LONG_TABLE = ("<h3>9.9 超长明细</h3>\n<table class=\"compact\" id=\"long-table\"><thead><tr><th>序号</th><th>事项</th></tr></thead><tbody>"
              + "".join(f"<tr><td>{i}</td><td>明细第 {i} 行</td></tr>" for i in range(1, 121))
              + "</tbody></table>\n<p id=\"after-long\">超长表格之后的一段正文。</p>")


def test_an_oversized_table_gets_its_own_sheet_and_a_visible_warning(context, tmp_path):
    out = build_sample(tmp_path, extra_body=LONG_TABLE)
    page = context.new_page()
    warnings = []
    page.on("console", lambda m: warnings.append(m.text) if m.type == "warning" else None)
    page.goto(out.as_uri(), wait_until="domcontentloaded")
    page.wait_for_selector("html[data-pagination='done']", state="attached", timeout=10000)

    on_sheet = page.evaluate("""() => {
        const sheetOf = el => [...document.querySelectorAll('#report .sheet')].indexOf(el.closest('.sheet'));
        const t = document.getElementById('long-table'), s = t.closest('.sheet');
        const blocks = [...s.querySelectorAll('h2, h3, p, table, figure')].filter(e => !e.closest('table') || e === t);
        const last = t.querySelector('tbody tr:last-child td');
        last.scrollIntoView({block: 'center'});
        const r = last.getBoundingClientRect(), sr = s.getBoundingClientRect();
        const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        return {table: sheetOf(t), after: sheetOf(document.getElementById('after-long')),
                others: blocks.filter(e => e !== t && e.tagName !== 'H3').length,
                visible: r.bottom <= sr.bottom && hit === last}; }""")

    assert on_sheet["others"] == 0, "the Oversized table has a Sheet to itself (its heading may stay with it)"
    assert on_sheet["after"] == on_sheet["table"] + 1
    assert on_sheet["visible"], "the table is not cut off at the Sheet edge"
    assert any("Oversized table" in w for w in warnings), warnings
    banner = page.locator("[role='alert']", has_text="Oversized table")
    assert banner.count() == 1 and banner.is_visible()
    assert banner.evaluate("b => b.getBoundingClientRect().top + scrollY") < 200, "warned at the top of the page"
    assert "9.9 超长明细" in banner.inner_text()


def tall_png() -> bytes:
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (600, 700), (27, 54, 93)).save(buf, format="PNG")
    return buf.getvalue()


def test_sheets_are_measured_only_after_slow_images_have_loaded(context, tmp_path):
    figs = "".join(f'<figure id="late-{i}"><img src="https://img.jc.test/tall-{i}.png" alt="">'
                   f"<figcaption>图 9-{i} · 晚到的图</figcaption></figure>\n" for i in range(3))
    out = build_sample(tmp_path, extra_body="<h2 id=\"s9\">九、晚到的图</h2>\n" + figs)
    png = tall_png()

    def slow(route):
        time.sleep(0.6)                                   # the image arrives after the DOM is parsed
        route.fulfill(status=200, content_type="image/png", body=png)
    context.route("https://img.jc.test/**", slow)
    page = open_report(context, out)

    placed = page.evaluate("""() => [0, 1, 2].map(i => {
        const f = document.getElementById('late-' + i), s = f.closest('.sheet');
        const r = f.getBoundingClientRect(), sr = s.getBoundingClientRect();
        return {sheet: [...document.querySelectorAll('#report .sheet')].indexOf(s),
                height: r.height, room: sr.bottom - r.bottom}; })""")
    m = page.evaluate("JSON.parse(document.getElementById('jc-settings').textContent).paper.marginMm")

    assert all(mm(p["height"]) > 150 for p in placed), placed
    assert len({p["sheet"] for p in placed}) == 3, "each 185 mm figure needs its own Sheet"
    assert all(mm(p["room"]) >= m["bottom"] - 0.5 for p in placed), placed


SHEET_LAYOUT = """() => [...document.querySelectorAll('#report .sheet')].map(s => ({
    w: s.getBoundingClientRect().width, h: s.getBoundingClientRect().height,
    first: s.querySelector('h2, h3, p, table, figure, div') && s.querySelector('h2, h3, p, table, figure, div').textContent.trim().slice(0, 40),
    blocks: s.querySelectorAll('p, table, figure, h2, h3').length }))"""


def test_toggling_the_sidebar_resizing_or_switching_theme_does_not_repaginate(reader):
    before = reader.page.evaluate(SHEET_LAYOUT)

    reader.toggle_sidebar()
    collapsed = reader.page.evaluate(SHEET_LAYOUT)
    reader.page.evaluate("document.documentElement.setAttribute('data-theme', 'black')")
    reader.page.set_viewport_size({"width": 1100, "height": 700})
    reader.page.wait_for_timeout(400)
    after = reader.page.evaluate(SHEET_LAYOUT)

    assert len(before) >= 3
    assert collapsed == before
    assert after == before


def test_an_explicit_page_break_starts_a_new_sheet(context, tmp_path):
    out = build_sample(tmp_path, extra_body='<p id="before-break">分页标记之前。</p>\n'
                                            '<div class="page-break"></div>\n<p id="after-break">分页标记之后。</p>')
    page = open_report(context, out)

    sheet = page.evaluate("""id => { const s = document.getElementById(id).closest('.sheet');
        return {index: [...document.querySelectorAll('#report .sheet')].indexOf(s),
                first: s.querySelector('p') && s.querySelector('p').id}; }""", "after-break")
    before = page.evaluate("id => [...document.querySelectorAll('#report .sheet')]"
                           ".indexOf(document.getElementById(id).closest('.sheet'))", "before-break")

    assert sheet["index"] == before + 1
    assert sheet["first"] == "after-break"


def test_a_highlight_on_a_later_sheet_is_drawn_over_its_own_text_after_reopening(reader):
    para = reader.page.evaluate("""() => { const ps = [...document.querySelectorAll('#report .sheet')].slice(2)
            .flatMap(s => [...s.querySelectorAll('p')]);
        const p = ps.find(p => p.textContent.trim().length > 40 && !p.closest('table'));
        return [...document.querySelectorAll('#report p')].indexOf(p); }""")
    assert para > 0, "the sample has a body paragraph on Sheet 3 or later"
    reader.select_text("#report p", para)
    reader.toolbar("yellow")
    quote = reader.note_items()[0]["quote"]

    reader.reopen()
    target = reader.page.locator("#report p").nth(para)
    target.scroll_into_view_if_needed()
    reader.page.wait_for_timeout(300)
    marks = reader.page.evaluate("""() => [...document.querySelectorAll('.r6o-span-highlight-layer .r6o-annotation')]
        .map(m => { const r = m.getBoundingClientRect(); return {x: r.left + r.width / 2, y: r.top + r.height / 2}; })""")
    box = target.bounding_box()

    assert [i["quote"] for i in reader.note_items()] == [quote]
    assert marks, "the highlight is painted"
    assert all(box["x"] <= m["x"] <= box["x"] + box["width"] and box["y"] <= m["y"] <= box["y"] + box["height"]
               for m in marks), (marks, box)
    assert quote in target.inner_text()


def test_with_pagination_disabled_the_report_scrolls_continuously(context, tmp_path):
    out = build_sample(tmp_path, {"pagination": {"enabled": False}})
    page = open_report(context, out)

    assert page.locator("#report .sheet").count() == 0
    report_h = page.evaluate("document.getElementById('report').getBoundingClientRect().height")
    assert mm(report_h) > 2 * 297, "one continuous column, not cut into Sheets"
    page.wait_for_selector(".js-toc a", state="attached")


def report_text(page) -> str:
    return page.evaluate("document.getElementById('report').textContent")


def test_pagination_leaves_the_annotatable_text_flow_unchanged(context, tmp_path):
    flat = open_report(context, build_sample(tmp_path / "off", {"pagination": {"enabled": False}}))
    paged = open_report(context, build_sample(tmp_path / "on"))

    assert paged.locator("#report .sheet").count() >= 3
    assert report_text(paged) == report_text(flat)
