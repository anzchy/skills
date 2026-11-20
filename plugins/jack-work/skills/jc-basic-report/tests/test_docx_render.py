"""docx export, seam ②: the docx as LibreOffice renders it (scripts/docx/render.py with fonts.conf).

Skipped when LibreOffice or the TsangerJinKai02 font (in ~/Library/Fonts) is missing.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import DOCX

pytestmark = [
    pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice (soffice) not installed"),
    pytest.mark.skipif(not list((Path.home() / "Library" / "Fonts").glob("TsangerJinKai02*")),
                       reason="TsangerJinKai02 not installed in ~/Library/Fonts"),
]


@pytest.fixture(scope="session")
def rendered(docx_path, tmp_path_factory):
    out = tmp_path_factory.mktemp("render")
    subprocess.run([sys.executable, str(DOCX / "render.py"), str(docx_path), str(out)], check=True)
    return out / (docx_path.stem + ".pdf")


@pytest.fixture(scope="session")
def html_pages(report_path, browser, tmp_path_factory):
    """Pages when Chrome prints the same HTML on A4 with 2cm margins (the docx page setup)."""
    import pymupdf
    page = browser.new_page()
    page.goto(report_path.as_uri(), wait_until="load")
    page.evaluate("() => document.querySelectorAll('script, button, .ann-tools, .ann-save, .ann-hint, #side')"
                  ".forEach(e => e.remove())")
    pdf = tmp_path_factory.mktemp("html") / "html.pdf"
    page.pdf(path=str(pdf), format="A4", print_background=True,
             margin={"top": "2cm", "bottom": "2cm", "left": "2cm", "right": "2cm"})
    page.close()
    return len(pymupdf.open(str(pdf)))


def cjk_chars_by_font(pdf):
    import pymupdf
    counts = {}
    for page in pymupdf.open(str(pdf)):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    n = sum(1 for ch in span["text"] if "一" <= ch <= "鿿")
                    if n:
                        counts[span["font"]] = counts.get(span["font"], 0) + n
    return counts


def test_cjk_text_renders_in_the_report_font(rendered):
    # report.css --serif: TsangerJinKai02 first; a stray glyph it lacks may fall back, the text must not
    counts = cjk_chars_by_font(rendered)
    total = sum(counts.values())
    jinkai = sum(n for f, n in counts.items() if f.startswith("TsangerJinKai02"))
    assert total > 1000, counts
    assert jinkai / total >= 0.99, counts


def test_page_count_tracks_the_html(rendered, html_pages):
    import pymupdf
    assert abs(len(pymupdf.open(str(rendered))) - html_pages) <= 1


def test_header_figure_stays_on_one_line(rendered, source_html):
    # the headline figure (.price-current, 28pt) sits on one line in the HTML; the docx must not wrap it
    import html as htmllib
    import re
    import pymupdf
    figure = htmllib.unescape(re.search(r'class="price-current">(.*?)</div>', source_html).group(1)).strip()
    page = pymupdf.open(str(rendered))[0]
    lines = ["".join(s["text"] for s in l["spans"]).strip()
             for b in page.get_text("dict")["blocks"] for l in b.get("lines", [])]
    assert any(figure.replace(" ", "") in ln.replace(" ", "") for ln in lines), (figure, lines[:12])
