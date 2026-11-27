"""Seam: the left sidebar table of contents, as a reader uses it in a browser."""
from __future__ import annotations

import pytest


def heading_texts(reader) -> list[str]:
    """What the reader sees as section titles in the body (rating badge excluded)."""
    return reader.page.evaluate("""() => [...document.querySelectorAll('#report h2, #report h3')]
        .map(h => (h.childNodes[0] && h.childNodes[0].nodeType === 3 && h.querySelector('.h2-rating'))
                   ? h.childNodes[0].textContent.trim() : h.textContent.trim())""")


def test_sidebar_lists_every_section_and_subsection(reader):
    assert reader.toc_labels() == heading_texts(reader)
    assert not reader.errors


def test_sidebar_labels_for_the_sample_report(reader, request):
    if request.config.getoption("--report"):
        pytest.skip("literal labels apply to the bundled sample only")
    labels = reader.toc_labels()
    assert labels[0] == "〇、投资要点"          # rating badge is not part of the label
    assert "1.1 第一层：为什么 AI 需要 GPU" in labels
    assert labels[-1] == "附录 B：数据来源"


def visible_toc_labels(reader) -> list[str]:
    """Entries a reader can actually see: collapsed groups are squeezed to zero height."""
    return reader.page.evaluate("""() => [...document.querySelectorAll('.js-toc a')].filter(a => {
        for (let el = a.parentElement; el && !el.classList.contains('js-toc'); el = el.parentElement)
            if (el.getBoundingClientRect().height < 1) return false;
        return a.getBoundingClientRect().height > 0; }).map(a => a.textContent.trim())""")


def test_clicking_an_entry_jumps_there_marks_it_active_and_expands_only_its_subsections(reader):
    first_h2 = reader.page.locator("#report h2").nth(1)          # a section with sub-sections
    target = first_h2.evaluate("h => h.textContent.trim()")
    sub = reader.page.locator("#report h2").nth(1).evaluate(     # next heading in reading order, Sheets or not
        "h => { const hs = [...document.querySelectorAll('#report h2, #report h3')], n = hs[hs.indexOf(h) + 1];"
        " return n && n.tagName === 'H3' ? n.textContent.trim() : null; }")
    assert sub, "test needs a section with at least one sub-section"

    reader.click_toc(target)

    top = first_h2.evaluate("h => h.getBoundingClientRect().top")
    assert 0 <= top < 200, f"section heading should be near the top of the window, got {top}px"
    assert reader.active_toc() in (target, sub)
    shown = visible_toc_labels(reader)
    assert sub in shown
    others = [l for l in reader.toc_labels() if l not in shown]
    assert others, "sub-sections of other sections should stay collapsed"


def test_sidebar_collapses_to_a_rail_and_stays_collapsed_after_reload(reader):
    wide = reader.sidebar_width()

    reader.toggle_sidebar()
    narrow = reader.sidebar_width()
    reader.reopen()

    assert wide > 200 and narrow < 60
    assert reader.sidebar_width() < 60, "collapsed state should be remembered"
    reader.toggle_sidebar()
    assert reader.sidebar_width() > 200
