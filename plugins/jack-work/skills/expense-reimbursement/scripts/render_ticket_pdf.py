#!/usr/bin/env python3
"""把火车票等 PDF 电子发票的第一页渲染成 PNG 图片，供 insert_ticket_screenshots.py
贴进「火车票截图-姓名.docx」。用 PyMuPDF(fitz) 渲染，不依赖 pdf2image/poppler。

电子发票都是单页，只取第 1 页；dpi 默认 200（A5 版面下打印清晰且体积可控）。
"""
import tempfile

import fitz


def render_pdf_to_image(pdf_path: str, out_image_path: str = None, dpi: int = 200) -> str:
    out_image_path = out_image_path or tempfile.mktemp(suffix=".png")

    doc = fitz.open(pdf_path)
    try:
        pix = doc[0].get_pixmap(dpi=dpi)
        pix.save(out_image_path)
    finally:
        doc.close()

    return out_image_path
