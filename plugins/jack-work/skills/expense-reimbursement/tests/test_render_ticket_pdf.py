#!/usr/bin/env python3
"""render_pdf_to_image() 单测（TDD，红→绿）。
用 fitz 现场造一个最小假 PDF（不依赖真实发票文件），验证第一页渲染成 PNG
且像素尺寸符合 dpi 换算。需要 PyMuPDF + Pillow：
用 python3.11 跑。
"""
import os, sys, tempfile

import fitz
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from render_ticket_pdf import render_pdf_to_image

failed = 0


def check(name, got, expect):
    global failed
    if got != expect:
        failed += 1
        print(f"FAIL {name}: got {got!r} expect {expect!r}")
    else:
        print(f"ok   {name} -> {got}")


def check_close(name, got, expect, tol=2):
    # 渲染像素数 = 页面点数 × dpi/72，PyMuPDF 取整方式允许 <=2px 误差。
    global failed
    if abs(got - expect) > tol:
        failed += 1
        print(f"FAIL {name}: got {got!r} not within {tol} of {expect!r}")
    else:
        print(f"ok   {name} -> {got} (~{expect})")


def make_pdf(pages: list) -> str:
    """pages = [(宽pt, 高pt), ...]，写一行文字，返回临时 PDF 路径。"""
    path = tempfile.mktemp(suffix=".pdf")
    doc = fitz.open()
    for i, (w, h) in enumerate(pages):
        page = doc.new_page(width=w, height=h)
        page.insert_text((10, 30), f"TEST TICKET PAGE {i + 1}")
    doc.save(path)
    doc.close()
    return path


# ---- 单页 PDF：200x100pt，dpi=200 应渲染成 ~556x278 的 PNG ----
pdf1 = make_pdf([(200, 100)])
out1 = tempfile.mktemp(suffix=".png")
got1 = render_pdf_to_image(pdf1, out1, dpi=200)

check("返回图片路径", got1, out1)
check("PNG 文件已生成", os.path.isfile(out1), True)

im1 = Image.open(out1)
check("输出格式为 PNG", im1.format, "PNG")
check_close("dpi=200 宽度像素", im1.size[0], round(200 * 200 / 72))
check_close("dpi=200 高度像素", im1.size[1], round(100 * 200 / 72))

# ---- dpi 参数生效：dpi=100 应约为 dpi=200 的一半 ----
out2 = tempfile.mktemp(suffix=".png")
render_pdf_to_image(pdf1, out2, dpi=100)
im2 = Image.open(out2)
check_close("dpi=100 宽度像素", im2.size[0], round(200 * 100 / 72))
check("dpi 越小图越小", im2.size[0] < im1.size[0], True)

# ---- 不传 out_image_path 时自动生成临时 PNG 路径 ----
got3 = render_pdf_to_image(pdf1)
check("自动生成的路径以 .png 结尾", got3.endswith(".png"), True)
check("自动生成的图片文件存在", os.path.isfile(got3), True)

# ---- 多页 PDF 只渲染第一页（第二页尺寸不同，用尺寸区分） ----
pdf2 = make_pdf([(200, 100), (400, 400)])
out4 = tempfile.mktemp(suffix=".png")
render_pdf_to_image(pdf2, out4, dpi=200)
im4 = Image.open(out4)
check_close("多页 PDF 只取第 1 页-宽", im4.size[0], round(200 * 200 / 72))
check_close("多页 PDF 只取第 1 页-高", im4.size[1], round(100 * 200 / 72))
check("未误取第 2 页(400x400 正方形)", im4.size[0] == im4.size[1], False)

# ---- 默认 dpi=200 ----
out5 = tempfile.mktemp(suffix=".png")
render_pdf_to_image(pdf1, out5)
im5 = Image.open(out5)
check("默认 dpi 等价于 dpi=200", im5.size, im1.size)

print(f"\n{'ALL PASS' if not failed else str(failed) + ' FAILED'}")
sys.exit(1 if failed else 0)
