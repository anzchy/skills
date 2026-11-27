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
    """Pages when Chrome prints the same HTML as compare.py does: one Sheet per A4 page."""
    import pymupdf
    page = browser.new_page()
    page.route("**/*.ttf", lambda route: route.abort())   # the CDN web font is not under test; as in conftest.context
    page.goto(report_path.as_uri(), wait_until="load")
    page.wait_for_selector("html[data-pagination]:not([data-pagination='pending'])", state="attached", timeout=15000)
    page.evaluate("() => document.querySelectorAll('script, button, .ann-tools, .ann-save, .ann-hint, #side')"
                  ".forEach(e => e.remove())")
    pdf = tmp_path_factory.mktemp("html") / "html.pdf"
    page.pdf(path=str(pdf), print_background=True, prefer_css_page_size=True)
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


@pytest.fixture()
def slow_image_server():
    """A local image server that answers after 1.5 s, so the Paginator settles well after page load."""
    import http.server
    import threading
    import time
    from test_pagination import tall_png
    png = tall_png()

    class Slow(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(1.5)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(png)))
            self.end_headers()
            self.wfile.write(png)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Slow)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_compare_prints_one_sheet_per_a4_page_with_its_page_chrome(docx_path, tmp_path, slow_image_server):
    # references/docx.md: compare.py prints the Report one Sheet per A4 page, with page chrome, even when
    # pagination finishes late (here a slow image holds it back past page load)
    import re
    import pymupdf
    from test_pagination import build_sample
    report = build_sample(tmp_path / "src", extra_body=f'<h2>九、晚到的图</h2>\n<figure><img src="{slow_image_server}/late.png" alt="">'
                                                      "<figcaption>图 9-1 · 晚到的图</figcaption></figure>")
    out = tmp_path / "cmp"
    subprocess.run([sys.executable, str(DOCX / "compare.py"), str(report), str(docx_path), str(out)],
                   check=True, capture_output=True)

    pdf = pymupdf.open(str(out / "html.pdf"))
    n = len(pdf)
    assert n >= 3
    for i, page in enumerate(pdf, start=1):
        assert abs(page.rect.width * 25.4 / 72 - 210) < 0.5 and abs(page.rect.height * 25.4 / 72 - 297) < 0.5
        assert re.findall(r"第 \d+ 页 共 \d+ 页", page.get_text()) == [f"第 {i} 页 共 {n} 页"], i


def test_rendered_pages_carry_the_header_and_their_own_page_numbers(rendered):
    # Word fields: every page shows "第 X 页 共 Y 页" with its own X and the real total; the header
    # (default template, {company} from the title) is on every page except the first
    import pymupdf
    pdf = pymupdf.open(str(rendered))
    total = len(pdf)
    assert total > 1
    for i, page in enumerate(pdf, start=1):
        text = page.get_text().replace("\n", " ")
        assert f"第 {i} 页 共 {total} 页" in text, (i, text[-80:])
        assert ("沐曦股份 · 项目基本信息报告" in text) == (i > 1), (i, text[:80])


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


def test_a_picture_pasted_into_body_text_shows_at_full_height(docx_path, tmp_path):
    # A reader pastes a picture into the exported docx. Word inserts it inline, in a Body Text paragraph
    # with no direct formatting. It must render at its full height, not cropped to one 15pt text line.
    import docx
    import pymupdf
    from docx.shared import Cm
    from PIL import Image

    red = tmp_path / "red.png"
    Image.new("RGB", (400, 300), (255, 0, 0)).save(red)
    d = docx.Document(str(docx_path))
    host = next(p for p in d.paragraphs if p.style.name == "Body Text" and len(p.text) > 20)
    pasted = d.add_paragraph(style="Body Text")
    host._p.addnext(pasted._p)
    pasted.add_run().add_picture(str(red), height=Cm(6))
    edited = tmp_path / "pasted.docx"
    d.save(str(edited))

    subprocess.run([sys.executable, str(DOCX / "render.py"), str(edited), str(tmp_path)], check=True)
    pdf = pymupdf.open(str(tmp_path / "pasted.pdf"))
    tallest = 0
    for page in pdf:
        pix = page.get_pixmap(dpi=72)            # 1 px = 1 pt
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        px = img.load()
        rows = sum(1 for y in range(pix.height)
                   if any(px[x, y][0] > 200 and px[x, y][1] < 60 and px[x, y][2] < 60 for x in range(0, pix.width, 2)))
        tallest = max(tallest, rows)
    expected = 6 / 2.54 * 72                      # 6cm in pt
    assert tallest >= expected * 0.95, f"picture shows {tallest}pt of {expected:.0f}pt"
