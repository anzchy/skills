#!/usr/bin/env python3
"""扫描报销材料目录，按**文件名关键词**把每个文件分类，产出「哪些素材需要贴截图」
的清单，供出差 SOP 里 render_ticket_pdf.py / insert_ticket_screenshots.py 取用。

只看文件名，不解析文件内容；只扫描本层目录，不递归子目录（与本 skill 其它脚本
对目录的扁平处理保持一致）。跳过 `.` 开头的隐藏文件（.DS_Store 等）与 `~$` 开头
的 Word 临时锁文件。

分类规则（按此优先级依次匹配，命中即止）：

| 类别 | 判断依据（文件名关键词） |
|---|---|
| 火车票发票 | `.pdf` 且含「站」；或含「高铁」「动车」「车次」「火车票」「铁路」；或含 `G/D/K/T/Z/C + 数字` 车次号 |
| 网约车行程单 | 含「行程单」「行程报销单」「滴滴」「曹操」「高德」「T3」「网约车」 |
| 支付截图 | 含「支付截图」「付款截图」「付款记录」「支付记录」「收款记录」 |
| 其他 | 以上都不命中。图片(.png/.jpg/.jpeg)→ 注明「无法从文件名判断，需人工确认」；其余(.xlsx/.xls/.docx 等)→ 注明「非截图类素材，如报销表单/出差报告」 |

注：
- 「T3」在网约车规则里先于车次号规则判定，避免 `T3出行` 被误当成 T3 次列车。
- `.xlsx/.xls/.docx/.doc` 在火车票规则之前就归入「其他」，避免把「火车票截图-张三.docx」
  这类**产出文档**误判成待处理的火车票发票（发票本身都是 PDF）。
"""
import os
import re

TRAIN_KEYWORDS = ["高铁", "动车", "车次", "火车票", "铁路"]
TRAIN_NO_RE = re.compile(r"(?<![A-Za-z0-9])[GDKTZC]\d{1,4}(?![0-9])")
RIDEHAIL_KEYWORDS = ["行程报销单", "行程单", "滴滴", "曹操", "高德", "T3", "网约车"]
PAYMENT_KEYWORDS = ["支付截图", "付款截图", "付款记录", "支付记录", "收款记录"]
IMAGE_EXTS = (".png", ".jpg", ".jpeg")
FORM_EXTS = (".xlsx", ".xls", ".docx", ".doc")
NOT_SCREENSHOT_REASON = "非截图类素材，如报销表单/出差报告"


def classify_material(file_name: str) -> dict:
    """按文件名给单个文件定类，返回 {"category", "reason"}。规则见模块 docstring。"""
    ext = os.path.splitext(file_name)[1].lower()

    for kw in RIDEHAIL_KEYWORDS:
        if kw in file_name:
            return {"category": "网约车行程单", "reason": f"文件名含「{kw}」，判为网约车行程单/发票"}

    for kw in PAYMENT_KEYWORDS:
        if kw in file_name:
            return {"category": "支付截图", "reason": f"文件名含「{kw}」，判为支付截图"}

    if ext in FORM_EXTS:
        return {"category": "其他", "reason": NOT_SCREENSHOT_REASON}

    if ext == ".pdf" and "站" in file_name:
        return {"category": "火车票发票", "reason": "PDF 且文件名含「站」（起止车站），判为火车票电子发票"}
    for kw in TRAIN_KEYWORDS:
        if kw in file_name:
            return {"category": "火车票发票", "reason": f"文件名含「{kw}」，判为火车票电子发票"}
    m = TRAIN_NO_RE.search(file_name)
    if m:
        return {"category": "火车票发票", "reason": f"文件名含车次号「{m.group()}」，判为火车票电子发票"}

    if ext in IMAGE_EXTS:
        return {"category": "其他", "reason": "图片文件但无匹配关键词，无法从文件名判断，需人工确认"}

    return {"category": "其他", "reason": NOT_SCREENSHOT_REASON}


def scan_materials(dir_path: str) -> list:
    """扫描 dir_path 本层文件，返回 [{"file","category","reason"}, ...]（按文件名排序）。"""
    rows = []
    for name in sorted(os.listdir(dir_path)):
        if name.startswith(".") or name.startswith("~$"):
            continue
        if not os.path.isfile(os.path.join(dir_path, name)):
            continue
        row = {"file": name}
        row.update(classify_material(name))
        rows.append(row)
    return rows
