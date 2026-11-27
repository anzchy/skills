"""Seam: the built Report in a browser — charts follow the Theme a reader picks.

Colours are read the way a reader sees them: computed fill / stroke of the drawn chart marks.
Expected values are the per-Theme chart palettes of the skill default Settings
(assets/settings.default.json), written out here as literals.
"""
from __future__ import annotations

from test_theme import build_sample_copy, choose, reader_for

# (background, brand series / focus, text, grid) per Theme, from the default Settings.
PALETTE = {
    "beige": {"bg": "rgb(245, 244, 237)", "brand": "rgb(27, 54, 93)", "text": "rgb(20, 20, 19)",
              "grid": "rgb(232, 231, 225)"},
    "white": {"bg": "rgb(255, 255, 255)", "brand": "rgb(27, 54, 93)", "text": "rgb(20, 20, 19)",
              "grid": "rgb(230, 230, 227)"},
    "black": {"bg": "rgb(22, 22, 26)", "brand": "rgb(143, 180, 232)", "text": "rgb(236, 236, 234)",
              "grid": "rgb(47, 47, 54)"},
}


def chart_colours(reader, kind: str, nth: int = 0) -> dict:
    """What a reader sees of one chart: its background, first series mark, a label, a grid line."""
    return reader.page.evaluate("""([kind, nth]) => {
        const svg = document.querySelectorAll(`svg[data-kami-chart="${kind}"]`)[nth];
        const cs = (el, p) => el ? getComputedStyle(el)[p] : null;
        const bg = svg.querySelector('rect');
        const mark = svg.querySelector('rect[rx], polyline, path');
        const fillOrStroke = mark && mark.tagName === 'polyline' ? cs(mark, 'stroke') : cs(mark, 'fill');
        const grid = svg.querySelector('line[stroke-width="0.8"]');
        return {bg: cs(bg, 'fill'), brand: fillOrStroke, text: cs(svg.querySelector('text[text-anchor="middle"]:not([transform])'), 'fill'),
                grid: cs(grid, 'stroke')};
    }""", [kind, nth])


def test_a_bar_chart_takes_the_palette_of_the_chosen_theme_at_once(reader):
    assert chart_colours(reader, "bar")["bg"] == PALETTE["beige"]["bg"]

    for theme in ("black", "white", "beige"):
        choose(reader, theme)
        got = chart_colours(reader, "bar")
        assert got == PALETTE[theme], theme
    assert not reader.errors


def check_charts(path):
    import subprocess
    import sys
    from conftest import SKILL
    return subprocess.run([sys.executable, str(SKILL / "scripts" / "chart.py"), "--check-charts", str(path)],
                          capture_output=True, text=True)


def test_the_chart_check_passes_on_a_built_report_and_catches_a_hand_recoloured_chart(report_path, tmp_path):
    ok = check_charts(report_path)
    assert ok.returncode == 0, ok.stdout
    assert ok.stdout.count("matches its data") == 3          # holders, finance, revenue in the sample

    html = report_path.read_text("utf-8")
    edited = tmp_path / "edited.html"
    edited.write_text(html.replace('fill="var(--chart-brand, #1B365D)"', 'fill="#1B365D"', 1), "utf-8")
    bad = check_charts(edited)
    assert bad.returncode == 1 and "differs from the spec" in bad.stdout


# A hand-drawn schematic as references/design.md tells the author to write it.
HAND_DRAWN = ('<figure><svg id="hand" viewBox="0 0 200 60" xmlns="http://www.w3.org/2000/svg">'
              '<rect width="200" height="60" fill="var(--chart-parchment, #f5f4ed)"/>'
              '<rect id="hand-ours" x="10" y="10" width="80" height="40" fill="var(--chart-brand, #1B365D)"/>'
              '<text id="hand-label" x="110" y="35" fill="var(--chart-near-black, #141413)">下游</text>'
              '</svg></figure>')


def test_a_hand_drawn_schematic_using_the_chart_variables_follows_the_theme(tmp_path, context):
    out = build_with_more_charts(tmp_path, extra_html=HAND_DRAWN)
    r = reader_for(context, out)

    def seen():
        return r.page.evaluate("""() => ['#hand > rect', '#hand-ours', '#hand-label']
            .map(s => getComputedStyle(document.querySelector(s)).fill)""")

    assert seen() == [PALETTE["beige"]["bg"], PALETTE["beige"]["brand"], PALETTE["beige"]["text"]]
    choose(r, "black")
    assert seen() == [PALETTE["black"]["bg"], PALETTE["black"]["brand"], PALETTE["black"]["text"]]


def build_with_more_charts(tmp_path, override: dict | None = None, extra_html: str = ""):
    """The bundled sample plus a line chart and a donut chart, optionally with a settings.json."""
    import json
    import shutil
    from conftest import FIXTURE, run_build
    src_dir = tmp_path / "more-charts"
    shutil.copytree(FIXTURE, src_dir)
    (src_dir / "charts" / "trend.json").write_text(json.dumps(
        {"type": "line", "categories": ["2023", "2024", "2025"],
         "series": [{"name": "毛利率", "values": [21.5, 33.0, 41.2]}], "suffix": "%", "lang": "cn"}), "utf-8")
    (src_dir / "charts" / "share.json").write_text(json.dumps(
        {"type": "donut", "items": [{"label": "训练", "value": 62}, {"label": "推理", "value": 38}],
         "center_label": "收入占比", "lang": "cn"}), "utf-8")
    src = src_dir / "report.src.html"
    src.write_text(src.read_text("utf-8").replace(
        "<!--CHART:revenue-->",
        "<!--CHART:revenue--></figure><figure><!--CHART:trend--></figure><figure><!--CHART:share--></figure>"
        + extra_html + "<figure>"), "utf-8")
    if override is not None:
        (src_dir / "settings.json").write_text(json.dumps(override), "utf-8")
    out = src_dir / "report.html"
    res = run_build(src, out)
    assert res.returncode == 0, res.stderr
    return out


def test_line_and_donut_charts_are_readable_in_the_black_theme(context, tmp_path):
    r = reader_for(context, build_with_more_charts(tmp_path))

    choose(r, "black")

    assert chart_colours(r, "line") == PALETTE["black"]
    donut = chart_colours(r, "donut")
    assert (donut["bg"], donut["brand"], donut["text"]) == (
        PALETTE["black"]["bg"], PALETTE["black"]["brand"], PALETTE["black"]["brand"])  # centre share is brand
    choose(r, "beige")
    assert chart_colours(r, "line") == PALETTE["beige"]


def test_an_authors_chart_palette_in_settings_recolours_the_charts(context, tmp_path):
    out = build_with_more_charts(tmp_path, {"themes": {"black": {"chart": {"brand": "#ff8800"}}}})
    r = reader_for(context, out)

    choose(r, "black")

    assert chart_colours(r, "line")["brand"] == "rgb(255, 136, 0)"
    assert chart_colours(r, "donut")["brand"] == "rgb(255, 136, 0)"
    assert chart_colours(r, "line")["bg"] == PALETTE["black"]["bg"]   # untouched keys keep their default
