"""Seam: scripts/build.py — a filled template (+ chart specs) in, one self-contained HTML out."""
from __future__ import annotations

import json
from pathlib import Path

from conftest import run_build

PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>测试报告</title>
<!--JC:CSS-->
</head><body>
<main id="report">
<h2 id="s0">〇、投资要点</h2>
<p>一段正文。</p>
{body}
</main>
<!--JC:SCRIPTS-->
</body></html>
"""


def write_src(tmp_path: Path, body: str = "", charts: dict | None = None) -> Path:
    src = tmp_path / "report.src.html"
    src.write_text(PAGE.format(body=body), encoding="utf-8")
    for name, spec in (charts or {}).items():
        d = tmp_path / "charts"
        d.mkdir(exist_ok=True)
        (d / f"{name}.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return src


def test_styles_are_inlined_so_the_report_needs_no_external_css(tmp_path):
    src = write_src(tmp_path)
    out = tmp_path / "report.html"

    res = run_build(src, out)

    assert res.returncode == 0, res.stderr
    html = out.read_text(encoding="utf-8")
    assert "<!--JC:CSS-->" not in html
    assert "--parchment: #f5f4ed" in html          # kami design token is present
    assert '<link rel="stylesheet"' not in html


def test_chart_markers_become_svg_charts_drawn_from_their_json_spec(tmp_path):
    spec = {"type": "bar", "categories": ["2024年", "2025年"],
            "series": [{"name": "营收", "values": [3.2, 7.4]}], "unit": "亿元"}
    src = write_src(tmp_path, body="<figure><!--CHART:revenue--></figure>", charts={"revenue": spec})
    out = tmp_path / "report.html"

    res = run_build(src, out)

    assert res.returncode == 0, res.stderr
    html = out.read_text(encoding="utf-8")
    assert "<!--CHART:revenue-->" not in html
    assert 'data-kami-chart="bar"' in html
    assert "2024年" in html and "2025年" in html


def test_unfilled_placeholders_fail_the_build_and_are_named(tmp_path):
    src = write_src(tmp_path, body="<p>注册资本：{{注册资本}}</p>")
    out = tmp_path / "report.html"

    res = run_build(src, out)

    assert res.returncode != 0
    assert "{{注册资本}}" in res.stdout + res.stderr


def test_draft_mode_builds_despite_unfilled_placeholders(tmp_path):
    src = write_src(tmp_path, body="<p>注册资本：{{注册资本}}</p>")
    out = tmp_path / "report.html"

    res = run_build(src, out, "--draft")

    assert res.returncode == 0, res.stderr
    assert "{{注册资本}}" in out.read_text(encoding="utf-8")


def test_data_gaps_are_listed_after_a_successful_build(tmp_path):
    body = ('<p>实控人：<span class="gap">[DATA NEEDED: 实控人认定]</span></p>'
            '<p>良率：<span class="gap">[DATA NEEDED]</span></p>')
    src = write_src(tmp_path, body=body)
    out = tmp_path / "report.html"

    res = run_build(src, out)

    assert res.returncode == 0, res.stderr
    assert "GAP 2" in res.stdout
    assert "实控人认定" in res.stdout
