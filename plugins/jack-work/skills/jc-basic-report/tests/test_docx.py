"""docx export, seam ①: the generated docx read back with python-docx.

Expected style values come from assets/report.css; expected counts are read from the report HTML.
Run: uv run --with pytest --with playwright --with python-docx --with pymupdf python -m pytest <skill>/tests
"""
import re

import pytest
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.text.paragraph import Paragraph

from conftest import build_fixture_with_settings, export_docx

BRAND, STONE = RGBColor.from_string("1B365D"), RGBColor.from_string("6B6A64")


def data_tables(doc):
    """Tables with a repeating header row: the report's .compact data tables."""
    return [t for t in doc.tables if t.rows[0]._tr.trPr is not None
            and t.rows[0]._tr.trPr.find(qn("w:tblHeader")) is not None]


def all_paragraphs(doc):
    return [Paragraph(p, doc) for p in doc.element.body.iter(qn("w:p"))]


def east_asia_font(style):
    return style.element.rPr.find(qn("w:rFonts")).get(qn("w:eastAsia"))


def rating(source_html):
    lead, word = re.search(r'class="h2-rating">([^<]*)<b>([^<]*)</b>', source_html).groups()
    return lead.strip(), word.strip()


def test_body_text_uses_the_report_serif_cjk_font(doc):
    # report.css: --serif starts with "TsangerJinKai02"
    assert east_asia_font(doc.styles["Body Text"]) == "TsangerJinKai02"


def test_body_text_line_height_matches_css_but_grows_for_pictures(doc):
    # report.css: body { font-size: 10pt; line-height: 1.5 } -> a 15pt line box.
    # It must be "at least", not "exactly": Word inserts pasted pictures inline, and an exact line box
    # crops them to a 15pt strip, which pushes readers to floating pictures that drift when text is edited.
    for name in ("Normal", "Body Text", "First Paragraph", "Compact"):
        pf = doc.styles[name].paragraph_format
        assert pf.line_spacing_rule == WD_LINE_SPACING.AT_LEAST, name
        assert pf.line_spacing == Pt(15), name


def _size(run):
    return run.font.size or (run.style.font.size if run.style is not None else None)


def _shaded(run):
    for rpr in (run._r.rPr, run.style.element.rPr if run.style is not None else None):
        if rpr is not None and rpr.find(qn("w:shd")) is not None:
            return True
    return False


def test_rating_badge_matches_css(doc, source_html):
    # report.css: .h2-rating 9pt stone, .h2-rating b 15pt brand, no background
    lead_text, word_text = rating(source_html)
    para = next(p for p in doc.paragraphs if word_text in p.text and lead_text in p.text)
    runs = [r for r in para.runs if r.text.strip()]
    assert not any(_shaded(r) for r in runs)
    word = next(r for r in runs if r.text.strip() == word_text)
    assert _size(word) == Pt(15)
    assert (word.font.color.rgb or word.style.font.color.rgb) == BRAND
    lead = next(r for r in runs if r.text.strip() == lead_text)
    assert _size(lead) == Pt(9)


def test_rating_badge_sits_at_the_right_margin(doc, source_html):
    # report.css: h2.with-rating { justify-content: space-between } -> flush right on the 17cm text line
    lead_text, word_text = rating(source_html)
    para = next(p for p in doc.paragraphs if word_text in p.text and lead_text in p.text)
    stops = [t for t in para.paragraph_format.tab_stops if t.alignment == WD_TAB_ALIGNMENT.RIGHT]
    assert stops and abs(stops[0].position - Cm(17)) < Cm(0.05)
    prev = next(r for r in para.runs if r.text.strip() == lead_text)._r.getprevious()
    assert prev is not None and prev.find(qn("w:tab")) is not None


def test_content_survives_conversion(doc, source_html):
    charts = source_html.count("<svg")
    photos = len(re.findall(r"<img\b", source_html))   # report pictures (<img>), embedded by build.py
    gaps = len(re.findall(r'<span class="gap[" ]', source_html))   # span.gap, including "gap legend"
    tables = source_html.count("<table")
    assert charts and photos and gaps and tables
    assert len(doc.inline_shapes) == charts + photos
    assert len(data_tables(doc)) == tables
    gap_text = "".join(
        r.findtext(qn("w:t")) or "" for r in doc.element.body.iter(qn("w:r"))
        if (rs := r.find(qn("w:rPr") + "/" + qn("w:rStyle"))) is not None and rs.get(qn("w:val")) == "Gap")
    assert gap_text.count("[DATA NEEDED") == gaps


def test_data_table_cells_use_the_compact_line_box(doc):
    # report.css: table.compact td { font-size: 8pt; line-height: 1.4 } -> fixed 11.2pt
    paras = [p for t in data_tables(doc) for r in t.rows for c in r.cells for p in c.paragraphs if p.text.strip()]
    assert paras
    for p in paras:
        assert p.paragraph_format.line_spacing_rule == WD_LINE_SPACING.EXACTLY, p.text
        assert p.paragraph_format.line_spacing == Pt(11.2), p.text


def test_data_table_cell_padding_matches_css(doc):
    # report.css: table.compact td { padding: 2.5pt 6pt } -> 50 / 120 twips
    for t in data_tables(doc):
        mar = t._tbl.tblPr.find(qn("w:tblCellMar"))
        assert {e.tag.split("}")[1]: int(e.get(qn("w:w"))) for e in mar} == \
            {"top": 50, "bottom": 50, "left": 120, "right": 120}


def test_data_tables_are_kept_on_one_page(doc):
    # report.css: table { break-inside: avoid } -> every row but the last keeps with the next
    for t in data_tables(doc):
        for row in t.rows[:-1]:
            for c in row.cells:
                for p in c.paragraphs:
                    assert p.paragraph_format.keep_with_next, p.text


def test_figure_captions_match_css(doc, source_html):
    # report.css: figcaption { font-size: 9pt; color: stone; text-align: center } (upright)
    expected = re.findall(r"<figcaption>(.*?)</figcaption>", source_html)
    caps = [p for p in all_paragraphs(doc) if p.style is not None and p.style.name == "Image Caption"]
    assert len(caps) == len(expected) > 0
    st = caps[0].style
    assert st.font.size == Pt(9) and st.font.color.rgb == STONE and not st.font.italic
    for p in caps:
        assert (p.alignment or st.paragraph_format.alignment) == WD_ALIGN_PARAGRAPH.CENTER


def test_two_column_charts_sit_side_by_side(doc, source_html):
    # report.css .two-col: two figures share one row
    blocks = re.findall(r'<div class="two-col">(.*?)</div>', source_html, flags=re.S)
    assert blocks, "the fixture must exercise .two-col"
    for block in blocks:
        left, right = (re.sub(r"<[^>]+>", "", c).split("·")[0].strip()
                       for c in re.findall(r"<figcaption>(.*?)</figcaption>", block))
        row = next(r for t in doc.tables for r in t.rows if any(left in c.text for c in r.cells))
        assert len(row.cells) == 2
        assert left in row.cells[0].text and right in row.cells[1].text
        for c in row.cells:
            assert c._tc.xpath(".//w:drawing")


def test_no_chart_is_clipped_by_a_fixed_line_box(doc):
    # a paragraph holding a picture must not use an exact line height, or Word/LibreOffice crop it
    pics = [p for p in all_paragraphs(doc) if p._p.xpath(".//w:drawing")]
    assert pics
    for p in pics:
        rule, st = p.paragraph_format.line_spacing_rule, p.style
        while rule is None and st is not None:
            rule, st = st.paragraph_format.line_spacing_rule, st.base_style
        assert rule != WD_LINE_SPACING.EXACTLY, p.style.name


def test_document_title_comes_from_the_report(doc, source_html):
    title = re.search(r"<title>(.*?)</title>", source_html).group(1).strip()
    assert doc.core_properties.title == title


def test_pictures_are_inline_in_order_and_fit_the_text_width(doc, source_html):
    # every <figure> picture becomes an inline picture (never a floating anchor, which drifts when text is edited),
    # immediately followed by its own caption, and no wider than the 17cm text line
    body = doc.element.body
    assert not body.xpath(".//wp:anchor")
    expected = [re.sub(r"<[^>]+>", "", c).split("·")[0].strip()
                for c in re.findall(r"<figcaption>(.*?)</figcaption>", source_html)]
    paras = all_paragraphs(doc)
    seen = []
    for i, p in enumerate(paras):
        if p._p.xpath(".//w:drawing"):
            cap = paras[i + 1]
            assert cap.style.name == "Image Caption", (i, cap.text)
            seen.append(cap.text.split("·")[0].strip())
    assert seen == expected
    for shape in doc.inline_shapes:
        assert shape.width <= Cm(17), shape.width


# ---------- Page chrome and Print palette (read from the Settings inlined in the Report) ----------
def page_background(doc):
    bg = doc.element.find(qn("w:background"))
    return bg.get(qn("w:color")).upper() if bg is not None else None


def test_page_background_follows_the_default_print_palette_white(doc):
    # Settings default: print.palette = "white" -> a white page, not the screen's parchment
    assert page_background(doc) == "FFFFFF"


@pytest.fixture(scope="module")
def doc_with_override(tmp_path_factory):
    """The fixture exported after the author overrides Print palette and the header template."""
    from docx import Document
    tmp = tmp_path_factory.mktemp("override")
    report = build_fixture_with_settings(tmp, {
        "defaultTheme": "black",
        "pagination": {"enabled": True},
        "print": {"palette": "beige"},
        "chrome": {"headerTemplate": "{company} · 尽调底稿"},
    })
    wd = tmp / "docx"
    wd.mkdir()
    return Document(str(export_docx(report, wd)))


def test_page_background_follows_an_overridden_print_palette(doc_with_override):
    # settings.json { "print": { "palette": "beige" } } -> the beige theme's page colour (Kami parchment)
    assert page_background(doc_with_override) == "F5F4ED"


@pytest.fixture(scope="module")
def doc_with_short_hex(tmp_path_factory):
    """The fixture exported after the author sets the white page colour as 3-digit hex and puts
    {company} in the footer."""
    from docx import Document
    tmp = tmp_path_factory.mktemp("short-hex")
    report = build_fixture_with_settings(tmp, {
        "print": {"palette": "white"},
        "themes": {"white": {"chart": {"parchment": "#fe8"}}},
        "chrome": {"footerTemplate": "{company} · 第 {page} 页"},
    })
    wd = tmp / "docx"
    wd.mkdir()
    return Document(str(export_docx(report, wd)))


def test_a_three_digit_page_colour_is_written_as_six_digit_hex(doc_with_short_hex):
    # w:background w:color takes RRGGBB only; "#fe8" means "#ffee88"
    assert page_background(doc_with_short_hex) == "FFEE88"


def test_every_page_but_the_first_carries_the_settings_header(doc):
    # fixture <title>沐曦股份 · 项目基本信息报告（样例）</title>: {company} is the part before " · ";
    # default chrome.headerTemplate "{company} · 项目基本信息报告"; the first page (title block) has no header
    for s in doc.sections:
        assert s.different_first_page_header_footer
        assert s.header.paragraphs[0].text == "沐曦股份 · 项目基本信息报告"
        assert not "".join(p.text for p in s.first_page_header.paragraphs).strip()


def footer_tokens(para):
    """A footer paragraph as Word evaluates it: literal text, and {FIELD} for each field instruction."""
    tokens, in_result = [], False
    for el in para._p.iter():
        tag = el.tag.split("}")[1]
        if tag == "fldSimple":
            tokens.append("{%s}" % el.get(qn("w:instr")).split()[0])
        elif tag == "fldChar":
            kind = el.get(qn("w:fldCharType"))
            in_result = kind == "separate"
        elif tag == "instrText":
            tokens.append("{%s}" % el.text.split()[0])
        elif tag == "t" and not in_result and el.getparent().getparent().tag != qn("w:fldSimple"):
            tokens.append(el.text)
    return "".join(tokens)


def test_every_page_footer_is_a_centred_word_page_count(doc):
    # default chrome.footerTemplate "第 {page} 页 共 {pages} 页" -> Word PAGE / NUMPAGES fields, so Word
    # computes its own numbering; the first page has no header but is counted, so it carries the footer too
    for s in doc.sections:
        for footer in (s.footer, s.first_page_footer):
            para = footer.paragraphs[0]
            assert footer_tokens(para) == "第 {PAGE} 页 共 {NUMPAGES} 页"
            assert para.paragraph_format.alignment == WD_ALIGN_PARAGRAPH.CENTER


def test_company_in_the_footer_template_is_filled_from_the_title(doc_with_short_hex):
    # chrome.footerTemplate "{company} · 第 {page} 页"; fixture title "沐曦股份 · 项目基本信息报告（样例）"
    for s in doc_with_short_hex.sections:
        for footer in (s.footer, s.first_page_footer):
            assert footer_tokens(footer.paragraphs[0]) == "沐曦股份 · 第 {PAGE} 页"


def test_export_ignores_the_screen_sheets_and_the_dark_theme(doc_with_override):
    # The author's Report opens paginated in the black theme. The docx is laid out by Word, so the export
    # must not carry the screen Sheets' page chrome into the text, and charts must not be dark pictures.
    import io
    from PIL import Image
    body = "\n".join(p.text for p in all_paragraphs(doc_with_override))
    assert not re.search(r"第 \d+ 页 共 \d+ 页", body)
    assert "沐曦股份 · 尽调底稿" not in body
    for shape in doc_with_override.inline_shapes:
        rid = shape._inline.graphic.graphicData.pic.blipFill.blip.embed
        img = Image.open(io.BytesIO(doc_with_override.part.related_parts[rid].blob)).convert("L")
        w, h = img.size
        corners = [img.getpixel(xy) for xy in ((1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2))]
        assert min(corners) > 200, corners


def test_the_header_reads_an_overridden_template(doc_with_override):
    for s in doc_with_override.sections:
        assert s.header.paragraphs[0].text == "沐曦股份 · 尽调底稿"
