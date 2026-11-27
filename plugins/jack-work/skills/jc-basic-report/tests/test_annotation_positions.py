"""Seam: Annotations on the paginated Report, reopened or imported — the highlight must be drawn
over the very text that was selected, not merely listed with the right quote.

The annotator only paints marks inside the viewport, so every check scrolls its paragraph into view
first; a mark missing from an off-screen paragraph is not a lost Annotation.
"""
from __future__ import annotations

import json

from conftest import Reader, run_build
from test_pagination import build_sample

P = "#report p"
TOL = 3   # px

# The text range of the k-th occurrence of `phrase` inside paragraph i, as client rects.
PHRASE_RECTS = """([i, phrase, k]) => {
    const p = document.querySelectorAll('#report p')[i];
    const walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
    const nodes = []; let text = '';
    for (let n = walker.nextNode(); n; n = walker.nextNode()) { nodes.push([n, text.length]); text += n.data; }
    let at = -1;
    for (let j = 0; j <= k; j++) { at = text.indexOf(phrase, at + 1); if (at < 0) return null; }
    const point = off => { for (let j = nodes.length - 1; j >= 0; j--) if (nodes[j][1] <= off) return [nodes[j][0], off - nodes[j][1]]; };
    const r = document.createRange();
    r.setStart(...point(at)); r.setEnd(...point(at + phrase.length));
    const rs = [...r.getClientRects()].filter(x => x.width > 0);
    return rs.map(x => ({left: x.left, top: x.top, right: x.right, bottom: x.bottom}));
}"""

MARKS = """() => [...document.querySelectorAll('.r6o-span-highlight-layer .r6o-annotation')].map(m => {
    const r = m.getBoundingClientRect();
    return {id: m.dataset.annotation, left: r.left, top: r.top, right: r.right, bottom: r.bottom}; })"""


def union(rects):
    return {"left": min(r["left"] for r in rects), "top": min(r["top"] for r in rects),
            "right": max(r["right"] for r in rects), "bottom": max(r["bottom"] for r in rects)}


def show(reader, i):
    reader.page.locator(P).nth(i).evaluate("p => p.scrollIntoView({block: 'center'})")
    reader.page.wait_for_timeout(400)


def select_phrase(reader, i, phrase, k=0):
    """Drag the mouse across the k-th occurrence of phrase in paragraph i, as a reader would."""
    show(reader, i)
    rects = reader.page.evaluate(PHRASE_RECTS, [i, phrase, k])
    assert rects and len(rects) == 1, f"pick a phrase that sits on one line: {rects}"
    r = rects[0]
    y = (r["top"] + r["bottom"]) / 2
    reader.page.mouse.move(r["left"] + 1, y)
    reader.page.mouse.down()
    reader.page.mouse.move(r["right"] - 1, y, steps=8)
    reader.page.mouse.up()
    reader.page.wait_for_timeout(400)


def highlight_phrase(reader, i, phrase, k=0):
    select_phrase(reader, i, phrase, k)
    reader.toolbar("yellow")
    quotes = [it["quote"] for it in reader.note_items()]
    assert phrase in quotes, (phrase, quotes)


def assert_marked(reader, i, phrase, k=0):
    """The mark the reader sees covers exactly the k-th occurrence of phrase in paragraph i."""
    show(reader, i)
    want = union(reader.page.evaluate(PHRASE_RECTS, [i, phrase, k]))
    marks = reader.page.evaluate(MARKS)
    near = [m for m in marks if m["bottom"] > want["top"] - 40 and m["top"] < want["bottom"] + 40]
    assert near, f"no mark drawn near {phrase!r} in paragraph {i}: {marks}"
    got = union(near)
    assert all(abs(got[s] - want[s]) <= TOL for s in want), \
        f"mark for {phrase!r} drifted: drawn at {got}, text at {want}"


def sheet_of(reader, i) -> int:
    return reader.page.evaluate("""i => { const p = document.querySelectorAll('#report p')[i];
        return [...document.querySelectorAll('#report .sheet')].indexOf(p.closest('.sheet')); }""", i)


def body_paragraphs(reader) -> list[dict]:
    """Body paragraphs (not in tables) with their Sheet index and text."""
    return reader.page.evaluate("""() => [...document.querySelectorAll('#report p')].map((p, i) => ({
        i, sheet: [...document.querySelectorAll('#report .sheet')].indexOf(p.closest('.sheet')),
        inTable: !!p.closest('table, figure, .verdict, .metrics, .risk-grid'),
        text: p.textContent.replace(/\\s+/g, ' ').trim()})).filter(p => !p.inTable)""")


def phrase_of(text: str, n: int = 8) -> str:
    """A short phrase from the start of the paragraph's first line, free of spaces."""
    s = text[:40].split(" ")
    return max(s, key=len)[:n]


# ---------- reopening the paginated Report ----------

def test_a_highlight_on_the_first_sheet_lands_back_on_its_text(reader):
    p = next(p for p in body_paragraphs(reader) if p["sheet"] == 0 and len(p["text"]) > 30)
    phrase = phrase_of(p["text"])
    highlight_phrase(reader, p["i"], phrase)

    reader.reopen()

    assert_marked(reader, p["i"], phrase)
    assert not reader.errors


def test_a_highlight_on_a_later_sheet_lands_back_on_its_text(reader):
    p = [p for p in body_paragraphs(reader) if p["sheet"] >= 2 and len(p["text"]) > 30][-1]
    phrase = phrase_of(p["text"])
    highlight_phrase(reader, p["i"], phrase)

    reader.reopen()

    assert sheet_of(reader, p["i"]) >= 2
    assert_marked(reader, p["i"], phrase)


def test_paragraphs_either_side_of_a_sheet_boundary_keep_their_highlights(reader):
    ps = body_paragraphs(reader)
    pair = next((a, b) for a, b in zip(ps, ps[1:])
                if b["sheet"] == a["sheet"] + 1 and len(a["text"]) > 20 and len(b["text"]) > 20)
    last, first = pair
    highlight_phrase(reader, last["i"], phrase_of(last["text"]))
    highlight_phrase(reader, first["i"], phrase_of(first["text"]))

    reader.reopen()

    assert_marked(reader, last["i"], phrase_of(last["text"]))
    assert_marked(reader, first["i"], phrase_of(first["text"]))


REPEATED = ('<h2 id="s9">九、重复短语</h2>\n'
            '<p id="rep">甲方案：核心指标同比增长。乙方案：核心指标同比增长。丙方案：核心指标同比增长。</p>\n')


def para_index(reader, pid: str) -> int:
    return reader.page.evaluate("id => [...document.querySelectorAll('#report p')].indexOf(document.getElementById(id))", pid)


def test_a_repeated_phrase_keeps_the_occurrence_that_was_highlighted(context, tmp_path):
    out = build_sample(tmp_path, extra_body=REPEATED)
    reader = Reader(context.new_page(), out.as_uri()).open()
    i = para_index(reader, "rep")
    highlight_phrase(reader, i, "核心指标同比增长", k=1)

    reader.reopen()

    assert_marked(reader, i, "核心指标同比增长", k=1)


# ---------- export / import JSON on the paginated Report ----------

def fresh_reader(browser, url: str) -> tuple:
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.route("**/*.ttf", lambda route: route.abort())
    return ctx, Reader(ctx.new_page(), url).open()


def test_imported_highlights_land_on_their_text_in_a_fresh_browser(reader, browser, report_path, tmp_path):
    p = [p for p in body_paragraphs(reader) if p["sheet"] >= 2 and len(p["text"]) > 30][-1]
    phrase = phrase_of(p["text"])
    highlight_phrase(reader, p["i"], phrase)
    reader.export_notes(tmp_path / "notes.json")

    ctx, other = fresh_reader(browser, report_path.as_uri())
    try:
        other.import_notes(tmp_path / "notes.json")
        assert_marked(other, p["i"], phrase)
        other.reopen()
        assert_marked(other, p["i"], phrase)
    finally:
        ctx.close()


INSERTED = "<p id=\"added\">修订版新增的一段说明文字，插在正文最前面，使后文的字符位置整体后移。</p>\n"


def revised(tmp_path, name: str, edit) -> str:
    """The sample Report rebuilt after the author edited its source."""
    out = build_sample(tmp_path / name, extra_body=REPEATED)
    src = tmp_path / name / "src" / "report.src.html"
    html = src.read_text(encoding="utf-8")
    src.write_text(edit(html), encoding="utf-8")
    res = run_build(src, out)
    assert res.returncode == 0, res.stderr
    return out.as_uri()


def test_imported_highlights_follow_their_text_when_the_report_was_revised(context, browser, tmp_path):
    """Text added above an Annotation shifts every character offset; the mark must follow its quote."""
    url = build_sample(tmp_path / "v1", extra_body=REPEATED).as_uri()
    reader = Reader(context.new_page(), url).open()
    i = para_index(reader, "rep")
    highlight_phrase(reader, i, "核心指标同比增长", k=1)
    reader.export_notes(tmp_path / "notes.json")

    v2 = revised(tmp_path, "v2", lambda h: h.replace('<main id="report">', '<main id="report">\n' + INSERTED, 1))
    ctx, other = fresh_reader(browser, v2)
    try:
        other.import_notes(tmp_path / "notes.json")
        j = para_index(other, "rep")
        assert_marked(other, j, "核心指标同比增长", k=1)
        assert other.page.locator(".ann-item", has_text="未定位").count() == 0
    finally:
        ctx.close()


def test_an_annotation_whose_text_is_gone_is_kept_and_flagged_unlocated(context, browser, tmp_path):
    url = build_sample(tmp_path / "v1", extra_body=REPEATED).as_uri()
    reader = Reader(context.new_page(), url).open()
    i = para_index(reader, "rep")
    select_phrase(reader, i, "核心指标同比增长", k=1)
    reader.write_note("这条要核实")
    reader.export_notes(tmp_path / "notes.json")

    v2 = revised(tmp_path, "v2", lambda h: h.replace("核心指标同比增长", "收入稳步提升"))
    ctx, other = fresh_reader(browser, v2)
    try:
        other.import_notes(tmp_path / "notes.json")
        flagged = other.page.locator(".ann-item", has_text="未定位")
        assert flagged.count() == 1, other.note_items()
        assert "核心指标同比增长" in flagged.inner_text() and "这条要核实" in flagged.inner_text()
        show(other, para_index(other, "rep"))
        assert other.page.evaluate(MARKS) == [], "an unlocated Annotation is not painted on other text"

        other.reopen()
        assert other.page.locator(".ann-item", has_text="未定位").count() == 1, "kept across reopening"
        again = other.export_notes(tmp_path / "again.json")
        first = json.loads((tmp_path / "notes.json").read_text(encoding="utf-8"))
        assert [a["id"] for a in again["annotations"]] == [a["id"] for a in first["annotations"]], \
            "an unlocated Annotation is exported, not dropped"
        assert not other.errors
    finally:
        ctx.close()


def test_the_import_message_counts_unlocated_annotations_separately(context, browser, tmp_path):
    url = build_sample(tmp_path / "v1", extra_body=REPEATED).as_uri()
    reader = Reader(context.new_page(), url).open()
    i = para_index(reader, "rep")
    highlight_phrase(reader, i, "甲方案")
    highlight_phrase(reader, i, "核心指标同比增长", k=1)
    reader.export_notes(tmp_path / "notes.json")

    v2 = revised(tmp_path, "v2", lambda h: h.replace("核心指标同比增长", "收入稳步提升"))
    ctx, other = fresh_reader(browser, v2)
    try:
        said = []
        other.page.on("dialog", lambda d: said.append(d.message))
        other.import_notes(tmp_path / "notes.json")

        assert said == ["已导入 2 条批注，其中 1 条未定位。"], said
    finally:
        ctx.close()
