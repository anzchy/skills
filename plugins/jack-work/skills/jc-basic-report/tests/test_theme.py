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
