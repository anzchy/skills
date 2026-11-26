#!/usr/bin/env python3
"""把多张票据截图（如火车票 PDF 发票渲染出的图）纵向堆叠贴进「火车票截图-姓名.docx」：
页面设为 A5（纵向/横向可选），清空文档已有内容，按给定顺序逐张居中插入。

与单图版 insert_payment_screenshot() 的差别：多图场景要求**宽度统一占满**可打印
宽度（高度按原始长宽比等比缩放，不受可打印高度压缩），这样一页里堆叠的几张票
左右对齐、观感一致；累计高度放不下下一张时，在该张之前插入分页符另起一页。
"""
import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from PIL import Image

from insert_payment_screenshot import apply_a5_page, clear_paragraphs


def insert_stacked_images(
    docx_path: str,
    image_paths: list,
    out_path: str = None,
    page_orientation: str = "portrait",
) -> dict:
    out_path = out_path or docx_path
    doc = docx.Document(docx_path)

    section = apply_a5_page(doc.sections[0], page_orientation)
    clear_paragraphs(doc)

    avail_w = section.page_width - section.left_margin - section.right_margin
    avail_h = section.page_height - section.top_margin - section.bottom_margin

    used_h = 0  # 当前页已用高度
    pages = 1
    for image_path in image_paths:
        img_w_px, img_h_px = Image.open(image_path).size
        width = avail_w
        height = round(avail_w * img_h_px / img_w_px)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()

        # 本页放不下这张 → 换页重新累计（used_h==0 说明单张就超高，不再空转分页）
        if used_h and used_h + height > avail_h:
            run.add_break(WD_BREAK.PAGE)
            used_h = 0
            pages += 1

        run.add_picture(image_path, width=width, height=height)
        used_h += height

    doc.save(out_path)
    return {"out": out_path, "images": len(image_paths), "pages": pages}
