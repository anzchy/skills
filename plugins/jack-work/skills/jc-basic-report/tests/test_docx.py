"""docx export, seam ①: the generated docx read back with python-docx.

Expected style values come from assets/report.css; expected counts are read from the report HTML.
Run: uv run --with pytest --with playwright --with python-docx --with pymupdf python -m pytest <skill>/tests
"""
import re

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.text.paragraph import Paragraph

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


def test_body_text_line_height_matches_css_exactly(doc):
    # report.css: body { font-size: 10pt; line-height: 1.5 } -> a fixed 15pt line box
    pf = doc.styles["Body Text"].paragraph_format
    assert pf.line_spacing_rule == WD_LINE_SPACING.EXACTLY
    assert pf.line_spacing == Pt(15)


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
    gaps = len(re.findall(r'<span class="gap[" ]', source_html))   # span.gap, including "gap legend"
    tables = source_html.count("<table")
    assert charts and gaps and tables
    assert len(doc.inline_shapes) == charts
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
