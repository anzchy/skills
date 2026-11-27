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
