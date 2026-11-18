#!/usr/bin/env python3
"""Build a jc-basic-report source HTML into one self-contained HTML file.

    python3 scripts/build.py report.src.html -o report.html
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ASSETS = SKILL / "assets"
VENDOR = ASSETS / "vendor"
sys.path.insert(0, str(SKILL / "scripts"))
from chart import render_chart  # noqa: E402  (kami chart generator, MIT)

CHART_MARKER = re.compile(r"<!--CHART:([\w-]+)-->")
PLACEHOLDER = re.compile(r"\{\{[^{}]*\}\}")
# Real gaps only: the legend sample in the template uses class="gap legend" and is not counted.
GAP = re.compile(r'<span class="gap">\[DATA NEEDED(?::\s*([^\]]*))?\]</span>')


def embed_charts(html: str, charts_dir: Path) -> str:
    def repl(m: re.Match) -> str:
        spec = json.loads((charts_dir / f"{m.group(1)}.json").read_text(encoding="utf-8"))
        return render_chart(spec)
    return CHART_MARKER.sub(repl, html)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def styles() -> str:
    return ("<style>\n" + read(ASSETS / "report.css") + read(ASSETS / "ui.css") + "</style>\n"
            "<style>/* @recogito/text-annotator 4.3.7 · BSD-3-Clause · (c) Pelagios Network */\n"
            + read(VENDOR / "recogito-text-annotator-4.3.7.css") + "</style>")


def scripts() -> str:
    parts = [
        ("/*! tocbot 4.36.8 · MIT · (c) Tim Scanlin */", read(VENDOR / "tocbot-4.36.8.min.js")),
        ("/*! @recogito/text-annotator 4.3.7 · BSD-3-Clause · (c) Pelagios Network */\n"
         "if(!window.process){window.process={env:{NODE_ENV:\"production\"}};}",
         read(VENDOR / "recogito-text-annotator-4.3.7.umd.js")),
        ("/* jc-basic-report reading tools */", read(ASSETS / "ui.js")),
    ]
    for _, js in parts:
        assert "</script" not in js
    return "\n".join(f"<script>{head}\n{js}</script>" for head, js in parts)


def build(src: Path, out: Path, draft: bool = False) -> int:
    html = src.read_text(encoding="utf-8")
    unfilled = sorted(set(PLACEHOLDER.findall(html)))
    if unfilled and not draft:
        print(f"ERROR: {len(unfilled)} 个占位符未填写（用 --draft 可强制生成预览）：", file=sys.stderr)
        for p in unfilled:
            print("  " + p, file=sys.stderr)
        return 1
    html = html.replace("<!--JC:CSS-->", styles())
    html = html.replace("<!--JC:SCRIPTS-->", scripts())
    html = embed_charts(html, src.parent / "charts")
    out.write_text(html, encoding="utf-8")
    gaps = [g.strip() or "（未写明）" for g in GAP.findall(html)]
    print(f"OK: wrote {out}")
    print(f"GAP {len(gaps)}")
    for g in gaps:
        print("  - " + g)
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--draft", action="store_true", help="允许未填写的占位符，仅用于预览")
    args = ap.parse_args(argv)
    return build(args.src, args.out, draft=args.draft)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
