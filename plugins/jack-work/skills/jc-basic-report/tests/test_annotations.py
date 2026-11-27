"""Seam: highlight / underline / note on selected text, as a reader uses it in a browser.

Persistence is observed the way a reader sees it (reopen the page, look at the 批注 list),
never by reading browser storage.
"""
from __future__ import annotations

import json

BODY_P = "#report p"            # body paragraphs, on a Sheet or in the continuous scroll


def test_highlighting_a_selection_lists_it_and_it_survives_reopening(reader):
    reader.select_text(BODY_P, 0)
    assert reader.toolbar_open()

    reader.toolbar("yellow")

    assert not reader.toolbar_open()
    items = reader.note_items()
    assert len(items) == 1 and len(items[0]["quote"]) >= 3
    quote = items[0]["quote"]
    reader.reopen()
    assert [i["quote"] for i in reader.note_items()] == [quote]
    assert not reader.errors


def test_underline_and_note_are_kept_with_the_note_text(reader):
    reader.select_text(BODY_P, 0)
    reader.toolbar("underline")
    reader.select_text(BODY_P, 1)
    reader.write_note("需向管理层核实口径")

    reader.reopen()

    items = reader.note_items()
    assert len(items) == 2
    assert [i["note"] for i in items] == ["", "需向管理层核实口径"]


def test_dismissing_the_toolbar_without_choosing_saves_nothing(reader):
    reader.select_text(BODY_P, 0)
    assert reader.toolbar_open()

    reader.dismiss()

    assert reader.marks_on_page() == 0, "a dismissed selection must not leave a mark"
    reader.reopen()
    assert reader.note_items() == []


def test_deleting_a_note_from_its_toolbar_removes_it_for_good(reader):
    reader.select_text(BODY_P, 0)
    reader.write_note("待删除")
    reader.open_note_from_list(0)
    assert reader.toolbar_open()

    reader.toolbar("delete")
    reader.reopen()

    assert reader.note_items() == []


def test_exported_notes_restore_in_a_fresh_browser(reader, context, browser, report_path, tmp_path):
    reader.select_text(BODY_P, 0)
    reader.write_note("导出测试备注")
    original = reader.note_items()

    exported = reader.export_notes(tmp_path / "notes.json")
    assert exported["@context"] == "http://www.w3.org/ns/anno.jsonld"
    assert len(exported["annotations"]) == 1

    fresh_ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    fresh_ctx.route("**/*.ttf", lambda route: route.abort())
    try:
        from conftest import Reader
        other = Reader(fresh_ctx.new_page(), report_path.as_uri()).open()
        assert other.note_items() == []
        other.import_notes(tmp_path / "notes.json")
        assert other.note_items() == original
    finally:
        fresh_ctx.close()
