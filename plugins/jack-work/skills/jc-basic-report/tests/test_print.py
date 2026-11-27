"""Seam: the built Report in a browser, printed to PDF (`page.pdf`) the way a reader prints it.

Printing uses the Print palette from Settings (default white), whatever Theme the reader picked
on screen, and every Sheet comes out as exactly one sheet of paper.
"""
from __future__ import annotations

import re
from types import SimpleNamespace

import pymupdf as fitz

from test_chart_theme import PALETTE, chart_colours
from test_pagination import LONG_TABLE, build_sample, open_report
from test_theme import choose, reader_for

WHITE = (255, 255, 255)
BEIGE = (245, 244, 237)


def print_pdf(page, dest) -> fitz.Document:
    page.wait_for_timeout(300)
    page.pdf(path=str(dest), print_background=True, prefer_css_page_size=True)
    return fitz.open(str(dest))


def paper_colour(pdf_page) -> tuple[int, int, int]:
    """The colour of the paper in the top-left page margin (no text or rules there)."""
    pix = pdf_page.get_pixmap(dpi=36)
    return tuple(pix.pixel(3, 3)[:3])


def near(colour, expected, tol: int = 2) -> bool:
    """PDF rasterising rounds colours by a unit or so."""
    return all(abs(a - b) <= tol for a, b in zip(colour, expected))


def sheet_count(page) -> int:
    return page.locator("#report .sheet").count()


def test_each_sheet_prints_as_exactly_one_page(context, report_path, tmp_path):
    page = open_report(context, report_path)

    pdf = print_pdf(page, tmp_path / "report.pdf")

    assert pdf.page_count == sheet_count(page) >= 3
    pt_mm = 25.4 / 72
    n = pdf.page_count
    for i, p in enumerate(pdf, start=1):
        assert abs(p.rect.width * pt_mm - 210) < 0.5 and abs(p.rect.height * pt_mm - 297) < 0.5
        # Laid out like the Sheet on screen: the page number sits in the Sheet's 18 mm bottom margin.
        (footer,) = p.search_for(f"第 {i} 页 共 {n} 页")
        assert 0 < p.rect.height * pt_mm - footer.y1 * pt_mm < 18, (i, footer)


def test_printing_is_white_even_when_the_reader_chose_the_black_theme(context, report_path, tmp_path):
    r = reader_for(context, report_path)
    choose(r, "black")

    pdf = print_pdf(r.page, tmp_path / "black.pdf")

    assert all(near(paper_colour(p), WHITE) for p in pdf), [paper_colour(p) for p in pdf]
    assert not r.errors


def test_charts_print_in_the_white_palette_when_the_reader_chose_the_black_theme(context, report_path):
    r = reader_for(context, report_path)
    choose(r, "black")

    r.page.emulate_media(media="print")

    assert chart_colours(r, "bar") == PALETTE["white"]


def test_each_printed_page_carries_its_own_page_number_once_and_no_other_counter(context, report_path, tmp_path):
    page = open_report(context, report_path)

    pdf = print_pdf(page, tmp_path / "report.pdf")

    n = pdf.page_count
    for i, p in enumerate(pdf, start=1):
        text = p.get_text()
        assert text.count(f"第 {i} 页 共 {n} 页") == 1, (i, text[-200:])
        assert len(re.findall(r"第 \d+ 页", text)) == 1, i
        assert not re.search(r"\d+\s+·\s+项目基本信息报告", text), (i, "old bottom-centre counter")


def test_the_print_palette_can_be_set_back_to_beige_in_settings(context, tmp_path):
    out = build_sample(tmp_path, {"print": {"palette": "beige"}, "defaultTheme": "white"})
    page = open_report(context, out)

    pdf = print_pdf(page, tmp_path / "beige.pdf")

    assert pdf.page_count == sheet_count(page)
    assert all(near(paper_colour(p), BEIGE) for p in pdf), [paper_colour(p) for p in pdf]
    page.emulate_media(media="print")
    assert chart_colours(SimpleNamespace(page=page), "bar") == PALETTE["beige"]


def test_an_oversized_sheet_runs_over_several_printed_pages_without_blank_ones(context, tmp_path):
    out = build_sample(tmp_path, extra_body=LONG_TABLE)
    page = open_report(context, out)

    pdf = print_pdf(page, tmp_path / "oversized.pdf")

    # The only exception to one Sheet = one page: an Oversized table's Sheet grows past A4.
    assert pdf.page_count > sheet_count(page)
    assert all(p.get_text().strip() for p in pdf), "no blank page"
    assert "明细第 120 行" in "".join(p.get_text() for p in pdf)


def test_without_pagination_the_continuous_print_is_also_on_the_print_palette(context, tmp_path):
    out = build_sample(tmp_path, {"pagination": {"enabled": False}, "defaultTheme": "black"})
    page = open_report(context, out)

    pdf = print_pdf(page, tmp_path / "continuous.pdf")

    assert pdf.page_count >= 2
    assert all(near(paper_colour(p), WHITE) for p in pdf), [paper_colour(p) for p in pdf]
