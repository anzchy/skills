"""Seam: the sidebar table of contents of a paginated Report — each entry's page number and where a click lands."""
from __future__ import annotations

from test_pagination import build_sample, open_report

# What the reader sees right of each TOC entry: the page number is drawn as generated content,
# so the entry's own label (and tocbot's text) stays unchanged.
SHOWN_PAGES = """() => [...document.querySelectorAll('.js-toc a')].map(a => {
    const c = getComputedStyle(a, '::after').content;
    return (c && c !== 'none' && c !== 'normal') ? c.replace(/^"|"$/g, '') : ''; })"""

# Where each heading really is: which Sheet (1-based) its top edge falls on, found by geometry.
REAL_PAGES = """() => { const sheets = [...document.querySelectorAll('#report .sheet')].map(s => s.getBoundingClientRect());
    return [...document.querySelectorAll('#report h2, #report h3')].map(h => {
        const y = h.getBoundingClientRect().top;
        return String(sheets.findIndex(r => y >= r.top && y < r.bottom) + 1); }); }"""


def test_every_toc_entry_shows_the_page_its_section_starts_on(context, report_path):
    page = open_report(context, report_path)
    page.wait_for_selector(".js-toc a", state="attached")

    shown, real = page.evaluate(SHOWN_PAGES), page.evaluate(REAL_PAGES)

    assert shown == real
    assert real[0] == "1" and int(real[-1]) > 3, "sample spans several Sheets"


def test_clicking_an_entry_lands_on_the_sheet_whose_number_it_shows(context, report_path):
    page = open_report(context, report_path)
    page.wait_for_selector(".js-toc a", state="attached")
    links = page.locator(".js-toc a")
    shown = page.evaluate(SHOWN_PAGES)
    top_level = page.evaluate("() => [...document.querySelectorAll('.js-toc a')].map(a => a.matches('.js-toc > ul > li > a'))")
    # a section entry (always visible, sub-sections may be collapsed) far down the Report
    i = max((k for k in range(len(shown)) if top_level[k]), key=lambda k: int(shown[k] or 0))

    links.nth(i).click()
    page.wait_for_timeout(900)

    landed = page.evaluate("""() => String([...document.querySelectorAll('#report .sheet')]
        .map(s => s.getBoundingClientRect()).findIndex(r => r.top <= 120 && r.bottom > 120) + 1)""")
    assert landed == shown[i]


def test_no_page_numbers_when_switched_off_in_settings(context, tmp_path):
    page = open_report(context, build_sample(tmp_path, {"toc": {"pageNumbers": False}}))
    page.wait_for_selector(".js-toc a", state="attached")

    assert page.locator("#report .sheet").count() > 1
    assert set(page.evaluate(SHOWN_PAGES)) == {""}


def test_no_page_numbers_when_pagination_is_disabled(context, tmp_path):
    page = open_report(context, build_sample(tmp_path, {"pagination": {"enabled": False}}))
    page.wait_for_selector(".js-toc a", state="attached")

    assert set(page.evaluate(SHOWN_PAGES)) == {""}

