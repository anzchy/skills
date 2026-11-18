#!/usr/bin/env python3
"""把支付截图贴进 支付截图.docx 模板：页面设为 A5（纵向/横向可选），替换
文档中已有的内容，把新截图按原始长宽比缩放到不溢出可打印区域后居中插入。
若截图的横竖朝向与页面朝向不一致（如竖长截图贴进横向版面），先把截图逆
时针旋转90度再铺满版面，避免竖版比例的照片缩得很小挤在横向页面中间。
"""
import os
import tempfile

import docx
from docx.shared import Mm
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from PIL import Image


def insert_payment_screenshot(
    docx_path: str, image_path: str, out_path: str = None, page_orientation: str = "portrait"
) -> dict:
    out_path = out_path or docx_path
    doc = docx.Document(docx_path)

    section = doc.sections[0]
    if page_orientation == "landscape":
        section.page_width, section.page_height = Mm(210), Mm(148)
        section.orientation = WD_ORIENT.LANDSCAPE
    else:
        section.page_width, section.page_height = Mm(148), Mm(210)
        section.orientation = WD_ORIENT.PORTRAIT

    for p in list(doc.paragraphs):
        p._element.getparent().remove(p._element)

    avail_w = section.page_width - section.left_margin - section.right_margin
    avail_h = section.page_height - section.top_margin - section.bottom_margin

    img = Image.open(image_path)
    img_w_px, img_h_px = img.size
    page_is_landscape = section.page_width > section.page_height
    img_is_portrait_shaped = img_h_px > img_w_px

    insert_image_path = image_path
    if page_is_landscape and img_is_portrait_shaped:
        rotated = img.transpose(Image.ROTATE_90)  # 逆时针旋转90度，铺满横向版面
        ext = os.path.splitext(image_path)[1] or ".png"
        insert_image_path = tempfile.mktemp(suffix=ext)
        rotated.save(insert_image_path)
        img_w_px, img_h_px = rotated.size

    ratio = img_w_px / img_h_px
    width, height = avail_w, round(avail_w / ratio)
    if height > avail_h:
        height, width = avail_h, round(avail_h * ratio)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(insert_image_path, width=width, height=height)

    doc.save(out_path)
    return {"out": out_path}
