"""Side-by-side visual check: the report HTML as Chrome prints it vs the docx as LibreOffice renders it.

Usage: python compare.py <report.html> <report.docx> <outdir>
Writes <outdir>/html.pdf, <outdir>/<docx stem>.pdf and <outdir>/pages_NN-MM.png (two pages per sheet).
"""
import subprocess
import sys
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

html, docx, out = (Path(a).resolve() for a in sys.argv[1:4])
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page()
    pg.goto(html.as_uri(), wait_until="load")
    pg.wait_for_timeout(500)
    pg.evaluate("() => document.querySelectorAll('script, button, .ann-tools, .ann-save, .ann-hint, #side').forEach(e => e.remove())")
    pg.pdf(path=str(out / "html.pdf"), format="A4", print_background=True,
           margin={"top": "2cm", "bottom": "2cm", "left": "2cm", "right": "2cm"})
    b.close()

subprocess.run([sys.executable, str(Path(__file__).with_name("render.py")), str(docx), str(out)], check=True,
               capture_output=True)
a, d = pymupdf.open(str(out / "html.pdf")), pymupdf.open(str(out / (docx.stem + ".pdf")))
W = 620


def shot(doc, i):
    if i >= len(doc):
        return Image.new("RGB", (W, int(W * 1.414)), "white")
    pix = doc[i].get_pixmap(dpi=90)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return im.resize((W, int(W * pix.height / pix.width)))


n = max(len(a), len(d))
for start in range(0, n, 2):
    pairs = [(shot(a, i), shot(d, i), i) for i in (start, start + 1) if i < n]
    h = max(x.height for p_ in pairs for x in p_[:2]) + 22
    sheet = Image.new("RGB", ((W + 12) * 2 * len(pairs), h), "#777")
    for k, (x, y, i) in enumerate(pairs):
        ox = k * (W + 12) * 2
        for j, (im, label) in enumerate(((x, "HTML"), (y, "DOCX"))):
            sheet.paste(im, (ox + j * (W + 12), 22))
            ImageDraw.Draw(sheet).text((ox + j * (W + 12) + 4, 5), f"{label} p{i + 1}", fill="white")
    sheet.save(out / f"pages_{start + 1:02d}-{min(start + 2, n):02d}.png")
print(f"html {len(a)} pages, docx {len(d)} pages -> {out}")
