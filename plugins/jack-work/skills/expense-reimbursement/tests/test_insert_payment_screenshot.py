#!/usr/bin/env python3
"""insert_payment_screenshot() 单测（TDD，红→绿）。
需要 python-docx + Pillow：用装有该依赖的 Python 3.11+ 跑（如 uv run --with …）。
"""
import os, sys, tempfile
import docx
from docx.shared import Mm
from docx.enum.section import WD_ORIENT
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from insert_payment_screenshot import insert_payment_screenshot

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


# ---- 造一个横向(landscape)、已贴过旧截图的空白模板docx，模拟真实起始状态 ----
tpl_path = tempfile.mktemp(suffix=".docx")
d = docx.Document()
sec = d.sections[0]
sec.page_width, sec.page_height = Mm(210), Mm(148)  # 起始为横向 A5
sec.orientation = WD_ORIENT.LANDSCAPE
p = d.add_paragraph()
old_img = tempfile.mktemp(suffix=".png")
Image.new("RGB", (100, 100), "white").save(old_img)
p.add_run().add_picture(old_img, width=Mm(50))
d.save(tpl_path)

# ---- 造一张竖长截图（模拟真实支付截图 1170x2532） ----
shot_path = tempfile.mktemp(suffix=".png")
Image.new("RGB", (1170, 2532), "white").save(shot_path)

out_path = tempfile.mktemp(suffix=".docx")
result = insert_payment_screenshot(tpl_path, shot_path, out_path)

check("返回out路径", result["out"], out_path)

d2 = docx.Document(out_path)
sec2 = d2.sections[0]
check_close("页面设为A5纵向-宽", sec2.page_width, Mm(148))
check_close("页面设为A5纵向-高", sec2.page_height, Mm(210))
check("orientation=PORTRAIT", sec2.orientation, WD_ORIENT.PORTRAIT)

shapes = d2.inline_shapes
check("旧图被替换,只剩1张新图", len(shapes), 1)

shp = shapes[0]
avail_w = sec2.page_width - sec2.left_margin - sec2.right_margin
avail_h = sec2.page_height - sec2.top_margin - sec2.bottom_margin
check("图片宽度未溢出可打印区域", shp.width <= avail_w, True)
check("图片高度未溢出可打印区域", shp.height <= avail_h, True)

orig_ratio = 1170 / 2532
got_ratio = shp.width / shp.height
check(
    "插入图片保持原始长宽比(四舍五入到万分位)",
    round(got_ratio * 10000),
    round(orig_ratio * 10000),
)

# ---- A5 横向：竖长截图应旋转90度铺满横向版面，不能仍按竖版比例缩小贴在中间 ----
tpl_path2 = tempfile.mktemp(suffix=".docx")
d3 = docx.Document()
d3.save(tpl_path2)

out_path2 = tempfile.mktemp(suffix=".docx")
result2 = insert_payment_screenshot(
    tpl_path2, shot_path, out_path2, page_orientation="landscape"
)

d4 = docx.Document(out_path2)
sec4 = d4.sections[0]
check_close("A5横向-页面宽(210mm)", sec4.page_width, Mm(210))
check_close("A5横向-页面高(148mm)", sec4.page_height, Mm(148))
check("orientation=LANDSCAPE", sec4.orientation, WD_ORIENT.LANDSCAPE)

shapes2 = d4.inline_shapes
check("横向版面只插入1张图", len(shapes2), 1)
shp2 = shapes2[0]

check("竖长截图在横向版面应旋转为横向摆放(宽>高)", shp2.width > shp2.height, True)

# 原图 1170x2532(宽:高≈0.4621)，逆时针旋转90度后应变为≈2532:1170(≈2.1641)
rotated_ratio = 2532 / 1170
got_ratio2 = shp2.width / shp2.height
check(
    "旋转后长宽比与(原图转90度)一致,而非仍是未旋转的竖版比例",
    round(got_ratio2 * 10000),
    round(rotated_ratio * 10000),
)

avail_w2 = sec4.page_width - sec4.left_margin - sec4.right_margin
avail_h2 = sec4.page_height - sec4.top_margin - sec4.bottom_margin
check("横向版面图片宽度未溢出", shp2.width <= avail_w2, True)
check("横向版面图片高度未溢出", shp2.height <= avail_h2, True)

# ---- 边界：图片本身已是横向，贴到横向版面时不应被误旋转 ----
landscape_img_path = tempfile.mktemp(suffix=".png")
Image.new("RGB", (200, 100), "white").save(landscape_img_path)  # 宽>高,本身已是横向
out_path3 = tempfile.mktemp(suffix=".docx")
insert_payment_screenshot(
    tpl_path2, landscape_img_path, out_path3, page_orientation="landscape"
)
d5 = docx.Document(out_path3)
shp3 = d5.inline_shapes[0]
check(
    "已是横向的图片贴到横向版面不应被误旋转(长宽比不变,200:100=2.0)",
    round((shp3.width / shp3.height) * 10000),
    round(2.0 * 10000),
)

print(f"\n{'ALL PASS' if not failed else str(failed)+' FAILED'}")
sys.exit(1 if failed else 0)
