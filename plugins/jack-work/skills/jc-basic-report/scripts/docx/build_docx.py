"""Steps B+C: pandoc main.html -> docx, then restyle with python-docx.

Usage: python build_docx.py <workdir> <out.docx>
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

wd = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
meta = json.loads((wd / "meta.json").read_text(encoding="utf-8"))

# ---- palette (from the report's CSS) ----
NEAR_BLACK, DARK_WARM, OLIVE, STONE = "141413", "3d3d3a", "504e49", "6b6a64"
BRAND, BORDER, PARCHMENT = "1B365D", "d9d6c8", "f5f4ed"
SERIF_LATIN, SERIF_CJK = "Georgia", "TsangerJinKai02"

# header/metric paragraphs: <p data-k="x"> -> named paragraph style K_x
html = (wd / "main.html").read_text(encoding="utf-8")
html = re.sub(r'<p data-k="(\w+)">(.*?)</p>',
              lambda m: f'<div data-custom-style="K_{m.group(1)}"><p>{m.group(2)}</p></div>', html, flags=re.S)
(wd / "main2.html").write_text(html, encoding="utf-8")

ref = wd / "ref.docx"
ref.write_bytes(subprocess.run(["pandoc", "--print-default-data-file", "reference.docx"],
                               capture_output=True, check=True).stdout)
raw = wd / "raw.docx"
subprocess.run(["pandoc", str(wd / "main2.html"), "-f", "html", "-t", "docx", "--reference-doc", str(ref),
                "--resource-path", str(wd), "-o", str(raw)], check=True)

doc = Document(str(raw))


def set_fonts(style_or_run, size=None, color=None, bold=None, latin=SERIF_LATIN, cjk=SERIF_CJK):
    f = style_or_run.font
    f.name = latin
    rpr = style_or_run.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for k in ("w:ascii", "w:hAnsi", "w:cs"):
        rfonts.set(qn(k), latin)
    rfonts.set(qn("w:eastAsia"), cjk)
    for k in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        rfonts.attrib.pop(qn(k), None)
    if size is not None:
        f.size = Pt(size)
    if color is not None:
        f.color.rgb = RGBColor.from_string(color)
    if bold is not None:
        f.bold = bold


def shade(rpr_or_pr, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    rpr_or_pr.append(shd)


def style(name, kind=WD_STYLE_TYPE.PARAGRAPH):
    try:
        return doc.styles[name]
    except KeyError:
        return doc.styles.add_style(name, kind)


# ---- page: A4, 2 cm margins, parchment page colour ----
for s in doc.sections:
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.left_margin = s.right_margin = Cm(2)
    s.top_margin = s.bottom_margin = Cm(2)
bg = OxmlElement("w:background")
bg.set(qn("w:color"), PARCHMENT)
doc.element.insert(0, bg)
settings = doc.settings.element
if settings.find(qn("w:displayBackgroundShape")) is None:
    settings.insert(0, OxmlElement("w:displayBackgroundShape"))

# ---- base text ----
for n in ("Normal", "Body Text", "First Paragraph", "Compact"):
    st = style(n)
    set_fonts(st, size=10, color=NEAR_BLACK)
    pf = st.paragraph_format
    pf.line_spacing = Pt(15)            # CSS: 10pt x line-height 1.5, a fixed line box
    pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    pf.space_after = Pt(8) if n != "Compact" else Pt(2)
    pf.space_before = Pt(0)
for n in ("Body Text", "First Paragraph"):
    style(n).paragraph_format.first_line_indent = Pt(20)   # 2em at 10pt
    style(n).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

for n, size, color in (("Heading 1", 18, NEAR_BLACK), ("Heading 2", 16, NEAR_BLACK), ("Heading 3", 13, DARK_WARM)):
    st = style(n)
    set_fonts(st, size=size, color=color, bold=False)
    st.font.italic = False
    st.paragraph_format.space_before = Pt(18 if n != "Heading 3" else 12)
    st.paragraph_format.space_after = Pt(6 if n != "Heading 3" else 4)
    st.paragraph_format.keep_with_next = True

# ---- named paragraph styles ----
def pstyle(name, size, color, bold=False, indent0=True, space_after=4, align=None, line=1.4):
    st = style(name)
    st.base_style = style("Normal")
    set_fonts(st, size=size, color=color, bold=bold)
    pf = st.paragraph_format
    pf.first_line_indent = Pt(0) if indent0 else None
    pf.space_after, pf.space_before, pf.line_spacing = Pt(space_after), Pt(0), line
    if align:
        pf.alignment = align
    return st

pstyle("Note", 9, STONE, space_after=8)
cap = pstyle("Image Caption", 9, STONE, space_after=8, align=WD_ALIGN_PARAGRAPH.CENTER)   # CSS figcaption
cap.font.italic = False
src_st = pstyle("Source", 9, DARK_WARM, space_after=2, line=1.35)
src_st.paragraph_format.left_indent = Pt(18); src_st.paragraph_format.first_line_indent = Pt(-18)
pstyle("VerdictLead", 11, NEAR_BLACK, space_after=6)
pstyle("K_eyebrow", 9, BRAND, bold=True, space_after=2)
pstyle("K_name", 24, NEAR_BLACK, space_after=2, line=1.15)
pstyle("K_sub", 10, OLIVE, space_after=0)
cstyle_later = True
pstyle("K_price", 28, NEAR_BLACK, space_after=2, line=1.0, align=WD_ALIGN_PARAGRAPH.RIGHT)
pstyle("K_change", 10, BRAND, bold=True, space_after=0, align=WD_ALIGN_PARAGRAPH.RIGHT)
pstyle("K_date", 9, STONE, space_after=0, align=WD_ALIGN_PARAGRAPH.RIGHT)
pstyle("K_mval", 16, BRAND, space_after=0, line=1.1)
pstyle("K_mlab", 9, OLIVE, space_after=0, line=1.2)

# ---- named character styles ----
def cstyle(name, color, fill=None, size=None, bold=False):
    st = style(name, WD_STYLE_TYPE.CHARACTER)
    set_fonts(st, size=size, color=color, bold=bold)
    if fill:
        shade(st.element.get_or_add_rPr(), fill)

cstyle("Gap", OLIVE, "f0eee6", 8.5)
cstyle("DirUp", BRAND, "E4ECF5", 8.5)
cstyle("DirDown", OLIVE, "f0eee6", 8.5)
cstyle("DirMid", "2D5A8A", "EEF2F7", 8.5)
cstyle("Hl", BRAND, bold=True)
cstyle("RatingLead", STONE, None, 9)        # CSS .h2-rating
cstyle("RatingWord", BRAND, None, 15)       # CSS .h2-rating b
cstyle("K_nameSub", STONE, None, 14)

# ---- tables ----
def borders(tbl, top=None, bottom=None, inside_h=None, header_bottom=None):
    tblPr = tbl._tbl.tblPr
    old = tblPr.find(qn("w:tblBorders"))
    if old is not None:
        tblPr.remove(old)
    b = OxmlElement("w:tblBorders")
    for edge, spec in (("top", top), ("left", None), ("bottom", bottom), ("right", None),
                       ("insideH", inside_h), ("insideV", None)):
        e = OxmlElement(f"w:{edge}")
        if spec:
            e.set(qn("w:val"), "single"); e.set(qn("w:sz"), str(spec[0])); e.set(qn("w:color"), spec[1])
        else:
            e.set(qn("w:val"), "nil")
        b.append(e)
    tblPr.append(b)


def cell_margins(tbl, top=40, bottom=40, left=80, right=80):
    tblPr = tbl._tbl.tblPr
    m = OxmlElement("w:tblCellMar")
    for edge, v in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        e = OxmlElement(f"w:{edge}"); e.set(qn("w:w"), str(v)); e.set(qn("w:type"), "dxa"); m.append(e)
    old = tblPr.find(qn("w:tblCellMar"))
    if old is not None:
        tblPr.remove(old)
    tblPr.append(m)


def col_pct(info, ncol):
    """Column widths in %: explicit HTML widths first, else estimate from text length."""
    kind = info["kind"]
    if kind == "header":
        return [100 - info["right_pct"], info["right_pct"]]
    if kind == "metrics":
        return [100 / ncol] * ncol
    if kind in ("risk", "verdict"):
        return [16, 84]
    if kind == "twocol":
        return [50, 50]
    w = info.get("widths") or []
    lens = info.get("lens") or []
    if len(w) == ncol and any(w):
        known = sum(x for x in w if x)
        rest = [x for x in w if not x]
        fill = (100 - known) / len(rest) if rest else 0
        return [x if x else fill for x in w]
    if len(lens) == ncol and sum(lens):
        weights = [max(4, L) ** 0.75 for L in lens]
        tot = sum(weights)
        return [100 * x / tot for x in weights]
    return [100 / ncol] * ncol


TOTAL_DXA = int(17 / 2.54 * 1440)          # 17 cm text width in twips


def full_width(tbl, info):
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    tblPr = tbl._tbl.tblPr
    w = tblPr.find(qn("w:tblW"))
    if w is None:
        w = OxmlElement("w:tblW"); tblPr.append(w)
    w.set(qn("w:type"), "dxa"); w.set(qn("w:w"), str(TOTAL_DXA))
    for old in tblPr.findall(qn("w:tblLayout")):
        tblPr.remove(old)
    layout = OxmlElement("w:tblLayout"); layout.set(qn("w:type"), "fixed"); tblPr.append(layout)
    ncol = len(tbl._tbl.tblGrid.findall(qn("w:gridCol")))
    pct = col_pct(info, ncol)
    dx = [int(TOTAL_DXA * p / 100) for p in pct]
    for gc, d in zip(tbl._tbl.tblGrid.findall(qn("w:gridCol")), dx):
        gc.set(qn("w:w"), str(d))
    for row in tbl.rows:
        for tc, d in zip(row._tr.findall(qn("w:tc")), dx):
            tcPr = tc.get_or_add_tcPr()
            tcW = tcPr.find(qn("w:tcW"))
            if tcW is None:
                tcW = OxmlElement("w:tcW"); tcPr.insert(0, tcW)
            tcW.set(qn("w:type"), "dxa"); tcW.set(qn("w:w"), str(d))


def price_width_pct(text, size_pt=28, pad_pt=10):
    """Share of the 17cm line the 28pt headline figure needs: CJK ~1em, Latin digits/symbols ~0.6em."""
    em = sum(1.0 if "\u3000" <= ch <= "\u9fff" or "\uff00" <= ch <= "\uffef" else 0.6 for ch in text.strip())
    return max(20, min(45, round(100 * (em * size_pt + pad_pt) / (17 / 2.54 * 72) + 2)))


kinds = meta["tables"]
for info in kinds:
    if info["kind"] == "header":
        price = next((p.text for p in doc.paragraphs if p.style.name == "K_price"), "")
        if not price:
            price = next((p.text for t in doc.tables for r in t.rows for c in r.cells for p in c.paragraphs
                          if p.style is not None and p.style.name == "K_price"), "")
        info["right_pct"] = price_width_pct(price)
tables = doc.tables
assert len(tables) == len(kinds), f"table count mismatch: docx {len(tables)} vs html {len(kinds)}"
for tbl, info in zip(tables, kinds):
    kind = info["kind"]
    tbl.style = None
    full_width(tbl, info)
    if kind == "twocol":                      # CSS .two-col: no rules, a small gutter
        borders(tbl)
        cell_margins(tbl, 0, 0, 60, 60)
        continue
    if kind in ("header", "metrics"):
        borders(tbl, bottom=(4, BORDER) if kind == "metrics" else None, top=(4, BORDER) if kind == "metrics" else None)
        cell_margins(tbl, 60, 60, 0, 120)
        continue
    borders(tbl, inside_h=(2, BORDER), bottom=(2, BORDER),
            top=None if kind in ("risk", "verdict") else None)
    cell_margins(tbl, 50, 50, 120, 120)     # CSS table.compact td: padding 2.5pt 6pt
    size = 8 if kind in ("compact", "financial", "spec") else 9.5
    for ri, row in enumerate(tbl.rows):
        is_head = ri == 0 and kind not in ("risk", "verdict")
        for ci, cell in enumerate(row.cells):
            for para in cell.paragraphs:
                para.paragraph_format.first_line_indent = Pt(0)
                para.paragraph_format.space_after = Pt(1)
                if kind in ("compact", "financial", "spec"):   # CSS table.compact: 8pt x line-height 1.4
                    para.paragraph_format.line_spacing = Pt(11.2)
                    para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
                else:
                    para.paragraph_format.line_spacing = 1.35
                para.alignment = WD_ALIGN_PARAGRAPH.RIGHT if (kind == "financial" and ci > 0) else WD_ALIGN_PARAGRAPH.LEFT
                for run in para.runs:
                    run.font.size = Pt(size)
                    if run.style is None or run.style.name in ("Default Paragraph Font",):
                        if is_head:
                            run.font.color.rgb = RGBColor.from_string(DARK_WARM)
                            run.font.bold = True
                    if kind in ("risk", "verdict") and ci == 0:
                        run.font.color.rgb = RGBColor.from_string(BRAND)
        if is_head:
            trPr = row._tr.get_or_add_trPr()
            h = OxmlElement("w:tblHeader"); trPr.append(h)       # repeat header row across pages
            for cell in row.cells:
                tcPr = cell._tc.get_or_add_tcPr()
                b = OxmlElement("w:tcBorders"); e = OxmlElement("w:bottom")
                e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "6"); e.set(qn("w:color"), "b9b5a5")
                b.append(e); tcPr.append(b)
        if ri < len(tbl.rows) - 1:            # CSS table { break-inside: avoid }: hold the table together
            for cell in row.cells:
                for para in cell.paragraphs:
                    para.paragraph_format.keep_with_next = True
        # keep rows from splitting across pages
        trPr = row._tr.get_or_add_trPr()
        cs = OxmlElement("w:cantSplit"); trPr.append(cs)

# ---- rating badge: flush right on the heading line (CSS justify-content: space-between) ----
for para in doc.paragraphs:
    lead = next((r for r in para.runs if r.style is not None and r.style.name == "RatingLead"), None)
    if lead is None:
        continue
    para.paragraph_format.tab_stops.add_tab_stop(Cm(17), WD_TAB_ALIGNMENT.RIGHT)
    tab_run = OxmlElement("w:r"); tab_run.append(OxmlElement("w:tab"))
    lead._r.addprevious(tab_run)

# ---- images: centre them ----
from docx.text.paragraph import Paragraph
for p_el in doc.element.body.iter(qn("w:p")):          # includes paragraphs inside table cells
    para = Paragraph(p_el, doc)
    if p_el.xpath(".//w:drawing"):
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.first_line_indent = Pt(0)
        para.paragraph_format.line_spacing = 1.0   # a fixed line box would clip the picture

doc.core_properties.title = meta.get("title", "")
doc.core_properties.author = ""
doc.save(str(out))
print("wrote", out, "tables", len(tables), "images", len(doc.inline_shapes))
