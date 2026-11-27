"""Seam: scripts/build.py — a filled template (+ chart specs) in, one self-contained HTML out."""
from __future__ import annotations

import base64
import json
import re
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


# A tiny valid PNG (1x1, grey): an independent, known-good byte string.
PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c63f8cfc0f01f0005000201a7f3d6"
    "0a0000000049454e44ae426082")


def test_local_images_are_embedded_so_the_report_stays_one_file(tmp_path):
    # the built report is opened (and converted to docx) away from its source folder
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "dot.png").write_bytes(PNG_1x1)
    src = write_src(tmp_path, body='<figure><img src="images/dot.png" width="20"><figcaption>图 1</figcaption></figure>')
    out = tmp_path / "elsewhere" / "report.html"
    out.parent.mkdir()

    res = run_build(src, out)

    assert res.returncode == 0, res.stderr
    html = out.read_text(encoding="utf-8")
    srcs = re.findall(r'<img[^>]*\ssrc="([^"]*)"', html)
    assert len(srcs) == 1
    assert srcs[0].startswith("data:image/png;base64,")
    assert base64.b64decode(srcs[0].split(",", 1)[1]) == PNG_1x1


# ---------- Settings: skill defaults + per-report override, validated and inlined ----------
SETTINGS_BLOCK = re.compile(r'<script type="application/json" id="jc-settings">(.*?)</script>', re.S)


def inlined_settings(out: Path) -> dict:
    blocks = SETTINGS_BLOCK.findall(out.read_text(encoding="utf-8"))
    assert len(blocks) == 1, "the Report carries exactly one inlined Settings block"
    return json.loads(blocks[0])


def test_without_an_override_the_report_carries_the_skill_default_settings(tmp_path):
    src = write_src(tmp_path)
    out = tmp_path / "report.html"

    res = run_build(src, out)

    assert res.returncode == 0, res.stderr
    s = inlined_settings(out)
    assert s["defaultTheme"] == "beige"
    assert s["pagination"] == {"enabled": True}
    assert s["paper"] == {"size": "A4", "marginMm": {"top": 16, "right": 18, "bottom": 18, "left": 18}}
    assert s["chrome"]["headerTemplate"] == "{company} · 项目基本信息报告"
    assert s["chrome"]["footerTemplate"] == "第 {page} 页 共 {pages} 页"
    assert s["toc"] == {"pageNumbers": True}
    assert s["print"] == {"palette": "white"}
    assert set(s["themes"]) == {"white", "black", "beige"}
    assert s["themes"]["beige"]["chart"]["parchment"] == "#f5f4ed"   # current Kami chart colours
    assert s["themes"]["beige"]["chart"]["brand"] == "#1B365D"


def write_override(tmp_path: Path, override) -> None:
    """The per-report override file the author places next to report.src.html."""
    text = override if isinstance(override, str) else json.dumps(override, ensure_ascii=False)
    (tmp_path / "settings.json").write_text(text, encoding="utf-8")


def test_a_partial_override_wins_and_every_other_key_keeps_its_default(tmp_path):
    src = write_src(tmp_path)
    write_override(tmp_path, {
        "defaultTheme": "black",
        "paper": {"marginMm": {"top": 25}},
        "chrome": {"headerTemplate": "{company} · 尽调底稿"},
        "themes": {"black": {"chart": {"brand": "#ff8800"}}},
    })
    out = tmp_path / "report.html"

    res = run_build(src, out)

    assert res.returncode == 0, res.stderr
    s = inlined_settings(out)
    assert s["defaultTheme"] == "black"
    assert s["paper"] == {"size": "A4", "marginMm": {"top": 25, "right": 18, "bottom": 18, "left": 18}}
    assert s["chrome"] == {"headerTemplate": "{company} · 尽调底稿", "footerTemplate": "第 {page} 页 共 {pages} 页"}
    assert s["themes"]["black"]["chart"]["brand"] == "#ff8800"
    assert s["themes"]["black"]["chart"]["parchment"] == "#16161a"   # sibling colour untouched
    assert s["print"] == {"palette": "white"}


def build_with_override(tmp_path: Path, override):
    src = write_src(tmp_path)
    write_override(tmp_path, override)
    out = tmp_path / "report.html"
    return run_build(src, out), out


def test_an_unknown_settings_key_fails_the_build_and_is_named(tmp_path):
    res, out = build_with_override(tmp_path, {"chrome": {"headerTemplte": "typo"}})

    assert res.returncode != 0
    assert "chrome.headerTemplte" in res.stderr
    assert not out.exists()


def test_an_illegal_theme_name_fails_the_build(tmp_path):
    res, out = build_with_override(tmp_path, {"defaultTheme": "dark"})

    assert res.returncode != 0
    assert "defaultTheme" in res.stderr and "dark" in res.stderr
    assert not out.exists()


def test_the_print_palette_must_name_a_theme(tmp_path):
    res, out = build_with_override(tmp_path, {"print": {"palette": "sepia"}})

    assert res.returncode != 0
    assert "print.palette" in res.stderr and "sepia" in res.stderr


def test_a_negative_page_margin_fails_the_build(tmp_path):
    res, out = build_with_override(tmp_path, {"paper": {"marginMm": {"left": -5}}})

    assert res.returncode != 0
    assert "paper.marginMm.left" in res.stderr
    assert not out.exists()


def test_a_bad_colour_error_names_both_accepted_hex_forms(tmp_path):
    # #rgb and #rrggbb are both accepted; the message must say so
    (tmp_path / "ok").mkdir()
    (tmp_path / "bad").mkdir()
    ok, _ =build_with_override(tmp_path / "ok", {"themes": {"white": {"chart": {"brand": "#abc"}}}})
    res, out = build_with_override(tmp_path / "bad", {"themes": {"white": {"chart": {"brand": "blue"}}}})

    assert ok.returncode == 0, ok.stderr
    assert res.returncode != 0
    assert "#rgb" in res.stderr and "#rrggbb" in res.stderr, res.stderr


def test_unsetting_a_required_key_fails_the_build_and_names_it(tmp_path):
    # null in the override removes the key, leaving the merged Settings without it
    res, out = build_with_override(tmp_path, {"chrome": {"headerTemplate": None}})

    assert res.returncode != 0
    assert "chrome.headerTemplate" in res.stderr
    assert not out.exists()


def test_every_invalid_setting_is_listed_in_one_failed_build(tmp_path):
    res, out = build_with_override(tmp_path, {
        "defaultTheme": "dark",
        "colour": "red",
        "pagination": {"enabled": "yes"},
        "paper": {"size": "Letter", "marginMm": {"top": -1}},
        "toc": {"pageNumbers": 1},
        "chrome": {"footerTemplate": 3},
        "themes": {"black": {"chart": {"brand": "blue"}}},
    })

    assert res.returncode != 0
    for path in ("defaultTheme", "colour", "pagination.enabled", "paper.size", "paper.marginMm.top",
                 "toc.pageNumbers", "chrome.footerTemplate", "themes.black.chart.brand"):
        assert path in res.stderr, f"{path} not reported:\n{res.stderr}"
    assert not out.exists()


def test_the_opened_report_reads_its_merged_settings_from_the_single_file(tmp_path, context):
    tricky = "{company}</script><b>x</b> · 底稿"
    res, out = build_with_override(tmp_path, {"chrome": {"headerTemplate": tricky}, "toc": {"pageNumbers": False}})
    assert res.returncode == 0, res.stderr
    moved = tmp_path / "sent" / "report.html"      # the file travels alone, away from settings.json
    moved.parent.mkdir()
    moved.write_bytes(out.read_bytes())

    page = context.new_page()
    page.goto(moved.as_uri(), wait_until="domcontentloaded")
    s = page.evaluate("JSON.parse(document.getElementById('jc-settings').textContent)")

    assert s["chrome"]["headerTemplate"] == tricky
    assert s["toc"]["pageNumbers"] is False
    assert s["defaultTheme"] == "beige"
    assert page.locator("b", has_text="x").count() == 0   # nothing leaked out of the JSON block


def test_a_settings_file_that_is_not_a_json_object_fails_the_build(tmp_path):
    res, out = build_with_override(tmp_path, '{"defaultTheme": "black",}')

    assert res.returncode != 0
    assert "settings.json" in res.stderr
    assert "Traceback" not in res.stderr
    assert not out.exists()
