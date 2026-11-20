"""Render a docx to PDF with LibreOffice, using fonts.conf so CJK fonts resolve.

Usage: python render.py <in.docx> <outdir>   -> <outdir>/<stem>.pdf
Without fonts.conf, headless soffice on macOS sees only its bundled fonts and drops every CJK glyph.
"""
import os
import subprocess
import sys
from pathlib import Path

src, outdir = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
outdir.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, FONTCONFIG_FILE=str(Path(__file__).resolve().parent / "fonts.conf"))
subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(src)],
               env=env, check=True, capture_output=True)
pdf = outdir / (src.stem + ".pdf")
if not pdf.exists():
    sys.exit(f"LibreOffice produced no PDF for {src}")
print(pdf)
