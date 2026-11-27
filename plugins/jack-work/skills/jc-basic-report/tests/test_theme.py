"""Seam: the Theme switcher at the top of the sidebar, as a reader uses it in a browser.

Colours are observed the way a reader sees them (computed colours of what is on screen);
persistence by reopening the page, never by reading browser storage.
"""
from __future__ import annotations

THEMES = {"white": "白色", "black": "黑色", "beige": "米色"}
# Known-good page backgrounds per Theme (beige is the existing Kami parchment).
PAGE_BG = {"white": "rgb(255, 255, 255)", "black": "rgb(22, 22, 26)", "beige": "rgb(245, 244, 237)"}


def page_bg(reader) -> str:
    return reader.page.evaluate("() => getComputedStyle(document.body).backgroundColor")


def choose(reader, theme: str):
    reader.page.get_by_role("radio", name=THEMES[theme]).click()
    reader.page.wait_for_timeout(100)


def chosen(reader) -> str:
    for key, label in THEMES.items():
        if reader.page.get_by_role("radio", name=label).get_attribute("aria-checked") == "true":
            return key
    return ""


def test_sidebar_offers_three_themes_and_a_click_applies_one_at_once(reader):
    radios = reader.page.locator(".side").get_by_role("radio")
    assert [r.inner_text().strip() for r in radios.all()] == list(THEMES.values())

    for theme in ("black", "white", "beige"):
        choose(reader, theme)
        assert page_bg(reader) == PAGE_BG[theme]
        assert chosen(reader) == theme
    assert not reader.errors


def reader_for(context, path):
    from conftest import Reader
    return Reader(context.new_page(), path.as_uri()).open()


def build_sample_copy(tmp_path, name: str, override: dict | None = None):
    """Another report: the bundled sample copied to its own folder, optionally with a settings.json."""
    import json
    import shutil
    from conftest import FIXTURE, run_build
    src_dir = tmp_path / name
    shutil.copytree(FIXTURE, src_dir)
    if override is not None:
        (src_dir / "settings.json").write_text(json.dumps(override), encoding="utf-8")
    out = src_dir / "report.html"
    res = run_build(src_dir / "report.src.html", out)
    assert res.returncode == 0, res.stderr
    return out


def test_the_choice_survives_reopening_and_carries_over_to_another_report(reader, context, tmp_path):
    choose(reader, "black")

    reader.reopen()
    assert chosen(reader) == "black" and page_bg(reader) == PAGE_BG["black"]

    other = reader_for(context, build_sample_copy(tmp_path, "other-company", {"defaultTheme": "white"}))
    assert chosen(other) == "black", "a saved choice is global and beats the other report's default"
    assert page_bg(other) == PAGE_BG["black"]


def test_without_a_saved_choice_the_settings_default_theme_is_used(context, tmp_path):
    out = build_sample_copy(tmp_path, "dark-default", {"defaultTheme": "black"})

    r = reader_for(context, out)

    assert chosen(r) == "black" and page_bg(r) == PAGE_BG["black"]


def test_the_skill_default_settings_start_in_beige(reader):
    assert chosen(reader) == "beige" and page_bg(reader) == PAGE_BG["beige"]


def test_collapsing_the_sidebar_hides_the_theme_control_and_expanding_shows_it(reader):
    control = reader.page.get_by_role("radiogroup", name="主题")
    assert control.is_visible()

    reader.toggle_sidebar()
    assert not control.is_visible()

    reader.toggle_sidebar()
    assert control.is_visible()


# Every visible piece of text in the body and sidebar, with the colour it is drawn in and the
# colour actually behind it (first opaque background up the tree). Charts are excluded: they are
# self-contained SVGs themed separately (#14).
LOW_CONTRAST = """(minRatio) => {
  const rgb = s => { const m = s.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].split(/[ ,\\/]+/).filter(Boolean).map(Number); return { c: p.slice(0, 3), a: p.length > 3 ? p[3] : 1 }; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const bgOf = el => { for (let e = el; e; e = e.parentElement) { const b = rgb(getComputedStyle(e).backgroundColor);
    if (b && b.a > 0.5) return b.c; } return [255, 255, 255]; };
  const bad = [];
  for (const el of document.querySelectorAll('#report *, #side *')) {
    if (el.closest('svg')) continue;
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own || !el.getClientRects().length || getComputedStyle(el).visibility === 'hidden') continue;
    const r = ratio(rgb(getComputedStyle(el).color).c, bgOf(el));
    if (r < minRatio) bad.push(`${el.tagName.toLowerCase()}.${el.className} "${el.textContent.trim().slice(0, 20)}" ${r.toFixed(2)}`);
  }
  return bad;
}"""


def test_every_text_in_body_and_sidebar_stays_readable_in_every_theme(reader):
    for theme in THEMES:
        choose(reader, theme)
        for pane in ("toc", "ann"):
            reader.page.click(f'.side-tab[data-tab="{pane}"]')
            bad = reader.page.evaluate(LOW_CONTRAST, 4.5)
            assert bad == [], f"{theme} theme, {pane} pane: low-contrast text {bad}"


# What the reader sees where a mark is drawn. The mark layer sits ABOVE the text and is composited
# with its CSS mix-blend-mode, so both the page and the glyphs under a mark are blended with it.
MARKS = """() => {
  const rgb = s => { const p = s.match(/rgba?\\(([^)]+)\\)/)[1].split(/[ ,\\/]+/).filter(Boolean).map(Number);
    return { c: p.slice(0, 3), a: p.length > 3 ? p[3] : 1 }; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const layer = document.querySelector('.r6o-span-highlight-layer');
  const mode = getComputedStyle(layer).mixBlendMode;
  const B = { normal: (b, s) => s, multiply: (b, s) => b * s / 255, screen: (b, s) => 255 - (255 - b) * (255 - s) / 255 }[mode];
  const over = (back, src) => back.map((b, i) => (1 - src.a) * b + src.a * B(b, src.c[i]));
  const page = rgb(getComputedStyle(document.body).backgroundColor).c;
  const text = rgb(getComputedStyle(document.body).color).c;   // body text colour
  return [...layer.querySelectorAll('.r6o-annotation')].map(m => {
    const cs = getComputedStyle(m), fill = rgb(cs.backgroundColor), out = { mode };
    if (fill.a > 0) {
      const bg = over(page, fill), fg = over(text, fill);
      out.fillDistance = Math.hypot(...bg.map((v, i) => v - page[i])); out.textOnFill = ratio(fg, bg);
    }
    if (parseFloat(cs.borderBottomWidth) > 0) out.lineVsPage = ratio(over(page, rgb(cs.borderBottomColor)), page);
    return out;
  });
}"""


def test_highlights_underlines_and_note_marks_stay_visible_in_every_theme(reader):
    reader.select_text("#report > p", 0)
    reader.toolbar("yellow")
    reader.select_text("#report > p", 1)
    reader.toolbar("underline")
    reader.select_text("#report > p", 2)
    reader.write_note("核实")                             # a note mark: tinted fill + dashed line

    reader.page.locator("#report > p").nth(1).scroll_into_view_if_needed()
    reader.page.wait_for_timeout(200)
    for theme in THEMES:              # switched after marking, without scrolling: marks must repaint
        choose(reader, theme)
        reader.page.wait_for_timeout(200)
        marks = reader.page.evaluate(MARKS)
        assert any("fillDistance" in m for m in marks) and any("lineVsPage" in m for m in marks)
        # Fill distance: the existing beige yellow sits ~66 from its page, which readers accept as visible.
        for m in marks:
            if "fillDistance" in m:
                assert m["fillDistance"] >= 40, f"{theme}: highlight fill blends into the page {m}"
                assert m["textOnFill"] >= 4.5, f"{theme}: text on a highlight is hard to read {m}"
            if "lineVsPage" in m:
                assert m["lineVsPage"] >= 3, f"{theme}: underline / note line is hard to see {m}"
    assert not reader.errors


def test_data_gap_labels_and_direction_tags_follow_the_theme(reader):
    tags = ".gap, .dir.up, .dir.down, .dir.mid"
    colours = {}
    for theme in THEMES:
        choose(reader, theme)
        colours[theme] = reader.page.evaluate(
            f"() => [...document.querySelectorAll('{tags}')].map(e => getComputedStyle(e).backgroundColor)")
    assert colours["black"], "the sample report needs gap labels and direction tags"
    assert all(b != g for b, g in zip(colours["black"], colours["beige"])), \
        "every gap label / direction tag must change background with the theme"
