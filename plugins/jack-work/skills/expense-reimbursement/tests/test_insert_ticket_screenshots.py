#!/usr/bin/env python3
"""insert_stacked_images() 单测（TDD，红→绿）。
版式基准取自用户手工做好的 `句容出差/火车票截图.docx`：A5 纵向、两张火车票
截图纵向堆叠居中、宽度占满可打印区域、两张同页不分页。测试用同像素尺寸的
假图（1492x996 / 1796x1198，即该文件里的 image1.png / image2.png）复现该版式。
需要 python-docx + Pillow：用 python3.11 跑。
"""
import os, sys, tempfile

import docx
from docx.shared import Mm
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from insert_ticket_screenshots import insert_stacked_images

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

failed = 0


def check(name, got, expect):
    global failed
    if got != expect:
        failed += 1
        print(f"FAIL {name}: got {got!r} expect {expect!r}")
    else:
        print(f"ok   {name} -> {got}")


def check_close(name, got, expect, tol_emu=635):
    # 页面尺寸(w:pgSz)在 docx XML 里以 twips(1/20pt=635EMU) 存储，
    # Mm() 值经 EMU->twips->EMU 往返后允许 <=1 twip 的取整误差。
    global failed
    if abs(got - expect) > tol_emu:
        failed += 1
        print(f"FAIL {name}: got {got!r} not within {tol_emu}EMU of {expect!r}")
    else:
        print(f"ok   {name} -> {got} (~{expect})")


def make_img(w: int, h: int) -> str:
    path = tempfile.mktemp(suffix=".png")
    Image.new("RGB", (w, h), "white").save(path)
    return path


def count_page_breaks(doc) -> int:
    return len(
        [
            br
            for br in doc.element.body.iter(f"{W_NS}br")
            if br.get(f"{W_NS}type") == "page"
        ]
    )


def make_tpl() -> str:
    """造一个已有旧内容的模板 docx，模拟真实起始状态（会被清空重写）。"""
    path = tempfile.mktemp(suffix=".docx")
    d = docx.Document()
    d.add_paragraph("旧的说明文字，应该被清空")
    p = d.add_paragraph()
    p.add_run().add_picture(make_img(100, 100), width=Mm(50))
    d.save(path)
    return path


# ---- 版式基准：2 张火车票截图（1492x996 / 1796x1198）应同页、不分页 ----
imgs2 = [make_img(1492, 996), make_img(1796, 1198)]
tpl = make_tpl()
out = tempfile.mktemp(suffix=".docx")
result = insert_stacked_images(tpl, imgs2, out)

check("返回out路径", result["out"], out)

d2 = docx.Document(out)
sec2 = d2.sections[0]
check_close("页面设为A5纵向-宽", sec2.page_width, Mm(148))
check_close("页面设为A5纵向-高", sec2.page_height, Mm(210))
check("orientation=PORTRAIT", sec2.orientation, WD_ORIENT.PORTRAIT)

check("旧内容被清空，无残留文字段落", any(p.text.strip() for p in d2.paragraphs), False)

shapes = d2.inline_shapes
check("插入2张图（旧图已被替换）", len(shapes), 2)

avail_w = sec2.page_width - sec2.left_margin - sec2.right_margin
avail_h = sec2.page_height - sec2.top_margin - sec2.bottom_margin

check("第1张宽度占满可打印宽度", shapes[0].width, avail_w)
check("第2张宽度占满可打印宽度", shapes[1].width, avail_w)
check(
    "第1张高度按原始比例等比缩放(1492:996)",
    shapes[0].height,
    round(avail_w / (1492 / 996)),
)
check(
    "第2张高度按原始比例等比缩放(1796:1198)",
    shapes[1].height,
    round(avail_w / (1796 / 1198)),
)
check("两张总高不超过一页可打印高度", shapes[0].height + shapes[1].height <= avail_h, True)
check("版式基准：2张图同页，不产生分页符", count_page_breaks(d2), 0)

check("每张图各占一个段落", len([p for p in d2.paragraphs if p.runs]), 2)
check(
    "图片段落居中",
    [p.alignment for p in d2.paragraphs if p.runs],
    [WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER],
)

# ---- 超出一页时自动分页：4 张同尺寸图（每页放 2 张）应产生 1 个分页符 ----
imgs4 = [make_img(1492, 996) for _ in range(4)]
out4 = tempfile.mktemp(suffix=".docx")
insert_stacked_images(make_tpl(), imgs4, out4)
d4 = docx.Document(out4)
check("4张图全部插入", len(d4.inline_shapes), 4)
check("4张图(每页2张)应产生1个分页符", count_page_breaks(d4), 1)

# ---- 6 张同尺寸图 → 3 页 → 2 个分页符 ----
out6 = tempfile.mktemp(suffix=".docx")
insert_stacked_images(make_tpl(), [make_img(1492, 996) for _ in range(6)], out6)
d6 = docx.Document(out6)
check("6张图全部插入", len(d6.inline_shapes), 6)
check("6张图(每页2张)应产生2个分页符", count_page_breaks(d6), 2)

# ---- 单张超高图：高度可以超过 avail_h（宽度统一优先），但不额外分页 ----
tall = make_img(400, 4000)
out_tall = tempfile.mktemp(suffix=".docx")
insert_stacked_images(make_tpl(), [tall], out_tall)
d_tall = docx.Document(out_tall)
sec_t = d_tall.sections[0]
avail_w_t = sec_t.page_width - sec_t.left_margin - sec_t.right_margin
check("单张图仍按宽度占满(不受avail_h压缩)", d_tall.inline_shapes[0].width, avail_w_t)
check("只有一张图时不产生分页符", count_page_breaks(d_tall), 0)

# ---- out_path 缺省时原地覆盖 ----
tpl_inplace = make_tpl()
res_inplace = insert_stacked_images(tpl_inplace, imgs2)
check("out_path缺省=原文件", res_inplace["out"], tpl_inplace)
check("原地覆盖后确有2张图", len(docx.Document(tpl_inplace).inline_shapes), 2)

# ---- page_orientation="landscape" 走 A5 横向 ----
out_ls = tempfile.mktemp(suffix=".docx")
insert_stacked_images(make_tpl(), imgs2, out_ls, page_orientation="landscape")
d_ls = docx.Document(out_ls)
sec_ls = d_ls.sections[0]
check_close("A5横向-页面宽(210mm)", sec_ls.page_width, Mm(210))
check_close("A5横向-页面高(148mm)", sec_ls.page_height, Mm(148))
check("orientation=LANDSCAPE", sec_ls.orientation, WD_ORIENT.LANDSCAPE)

print(f"\n{'ALL PASS' if not failed else str(failed) + ' FAILED'}")
sys.exit(1 if failed else 0)
