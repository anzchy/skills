"""Seam: the two bundled fixtures as a reader meets them in a browser.

`sample` is the realistic, well-behaved 沐曦 report; `sample-edge` holds the extreme cases that would distort it
(oversized table / figure / paragraph, a title without "·", an override `settings.json` beside the source).
Known defects found by the edge fixture are recorded as strict xfails, so fixing one flips the test and
reminds us to drop the marker.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from conftest import FIXTURE, run_build
from test_pagination import open_report

EDGE = Path(__file__).resolve().parent / "fixtures" / "sample-edge"


@pytest.fixture(scope="module")
def edge_report(tmp_path_factory) -> Path:
    work = tmp_path_factory.mktemp("edge")
    src = work / "src"
    shutil.copytree(EDGE, src)
    out = work / "report.html"
    res = run_build(src / "report.src.html", out)
    assert res.returncode == 0, res.stderr
    return out


def test_the_fixtures_keep_covering_the_edge_cases():
    sample = (FIXTURE / "report.src.html").read_text("utf-8")
    edge = (EDGE / "report.src.html").read_text("utf-8")
    kinds = {json.loads(p.read_text("utf-8"))["type"] for p in (FIXTURE / "charts").glob("*.json")}

    assert {"bar", "hbar", "donut", "line", "waterfall"} <= kinds, "every common chart type"
    assert sample.count('data-fake="repeat"') >= 3, "a repeated sentence, for annotation re-anchoring"
    assert 'class="page-break"' in sample, "an explicit page break"
    assert sample.count("<li>") >= 20 and '<ol class="qa">' in sample, "a long ordered list"
    assert sample.count('class="gap"') >= 4 and sample.count("<table") >= 12 and "<img" in sample

    assert "·" not in edge.split("<title>")[1].split("</title>")[0], "a title without a separator"
    assert edge.count("<tr") >= 90, "an oversized table"
    assert 'width="900"' in edge, "an image wider than the Sheet body"
    assert max(len(p) for p in edge.split("<p")) > 3000, "a paragraph taller than a Sheet"
    assert edge.count('data-fake="repeat"') >= 3
    assert json.loads((EDGE / "settings.json").read_text("utf-8"))["chrome"]["footerTemplate"]


def test_the_settings_override_beside_the_edge_report_applies(context, edge_report):
    page = open_report(context, edge_report)

    got = page.evaluate("""() => ({
        theme: document.documentElement.dataset.theme,
        mt: getComputedStyle(document.documentElement).getPropertyValue('--sheet-mt').trim(),
        headers: [...document.querySelectorAll('#report .sheet')].map(s => {
            const h = s.querySelector('.sheet-header'); return h ? [h.dataset.left, h.dataset.right] : null; }),
        footers: [...document.querySelectorAll('#report .sheet .sheet-footer')].map(f => f.dataset.text)})""")

    n = len(got["footers"])
    assert got["theme"] == "black" and got["mt"].startswith("20")
    assert got["headers"][0] is None, "the first Sheet has no header"
    # No "·" in the title, so {company} is the whole title; the template splits on its first "·".
    assert got["headers"][1] == ["边界样例报告（标题里没有分隔符）", "尽调底稿 · 机密"]
    assert got["footers"][0] == f"1 / {n}" and got["footers"][-1] == f"{n} / {n}"


def test_oversized_content_is_flagged_and_never_clipped(context, edge_report):
    page = open_report(context, edge_report)

    got = page.evaluate("""() => ({
        warnings: JCPaginator.warnings.length,
        oversized: [...document.querySelectorAll('#report .sheet--oversized')].map(s => ({
            clipped: s.scrollHeight > s.clientHeight + 1,
            hasTable: !!s.querySelector('table') && s.querySelectorAll('tr').length > 60 || !!s.querySelector('p')}))})""")

    assert got["warnings"] >= 2, "the 70-row table and the over-tall paragraph are both reported"
    assert got["oversized"] and not any(o["clipped"] for o in got["oversized"])


def test_no_heading_is_left_stranded_at_the_bottom_of_a_sheet(context, edge_report):
    page = open_report(context, edge_report)

    # A Sheet made only of headings is the deliberate special case pinned by the next test, so it is not counted here.
    stranded = page.evaluate("""() => [...document.querySelectorAll('#report .sheet')].slice(0, -1).filter(s => {
        const kids = [...s.querySelector('.sheet-body').children];
        return !kids.every(k => /^H[23]$/.test(k.tagName)) && /^H[23]$/.test(kids[kids.length - 1].tagName); }).length""")

    assert stranded == 0


def test_headings_that_cannot_share_a_sheet_with_a_near_full_table_get_a_sheet_of_their_own(context, edge_report):
    """Deliberate (ticket #15): the table fits a Sheet alone but not with its headings, so it is not Oversized; the
    headings keep a Sheet and the table starts the next one. There is no better place for them."""
    page = open_report(context, edge_report)

    got = page.evaluate("""() => { const t = document.getElementById('near-full'), s = t.closest('.sheet');
        const sheets = [...document.querySelectorAll('#report .sheet')], i = sheets.indexOf(s), prev = sheets[i - 1];
        return {tableAloneWithRows: [...s.querySelector('.sheet-body').children].filter(c => c.tagName === 'TABLE').length,
                prevOnlyHeadings: [...prev.querySelector('.sheet-body').children].filter(c => c.getBoundingClientRect().height > 1)
                                    .every(c => /^H[23]$/.test(c.tagName)),
                tableSheetOversized: s.classList.contains('sheet--oversized'),
                warnedAboutIt: JCPaginator.warnings.some(w => /近满页/.test(String(w.text || w)))}; }""")

    assert got["prevOnlyHeadings"] and got["tableAloneWithRows"] == 1
    assert not got["tableSheetOversized"] and not got["warnedAboutIt"]


def test_toc_page_numbers_never_go_backwards_on_the_edge_report(context, edge_report):
    page = open_report(context, edge_report)
    page.wait_for_selector(".js-toc a.toc-link", timeout=10000)

    pages = page.evaluate("() => [...document.querySelectorAll('.js-toc a.toc-link')].map(a => a.dataset.page)")

    nums = [int(p) for p in pages if p]
    assert nums and nums == sorted(nums) and nums[0] == 1


@pytest.mark.xfail(strict=True, reason="found by the edge fixture: an explicit page break followed by headings and a "
                                       "near-full table leaves a blank Sheet (only the empty .page-break marker on it)")
def test_no_sheet_is_blank(context, edge_report):
    page = open_report(context, edge_report)

    blank = page.evaluate("""() => [...document.querySelectorAll('#report .sheet')].filter(s =>
        ![...s.querySelector('.sheet-body').children].some(c => c.getBoundingClientRect().height > 1)).length""")

    assert blank == 0


@pytest.mark.xfail(strict=True, reason="found by the edge fixture: an <img width=900> is wider than the Sheet body and "
                                       "gets clipped on the right by .sheet-body{overflow:hidden}")
def test_images_stay_inside_the_sheet(context, edge_report):
    page = open_report(context, edge_report)

    too_wide = page.evaluate("""() => [...document.querySelectorAll('#report .sheet img')].filter(i => {
        const b = i.closest('.sheet-body').getBoundingClientRect(); return i.getBoundingClientRect().right > b.right + 1; }).length""")

    assert too_wide == 0
