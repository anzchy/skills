"""Seam: the built Report in a browser — its body laid out as A4 Sheets by the Paginator.

Geometry is read from the page the way a reader sees it (bounding boxes in CSS px, 96 px = 1 in).
"""
from __future__ import annotations

import json
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
