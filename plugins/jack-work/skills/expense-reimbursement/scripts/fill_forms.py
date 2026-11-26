#!/usr/bin/env python3
"""写出层：用 openpyxl 把已核对的字段填入官方空白模板，保留公式/打印区。

设计：每个 fill_* 接收一个 dict（A 类由脚本算出、B 类由用户补全后合并），
读取 templates/ 下对应模板，填值后另存到 out_path。

不重画模板、不动打印区与既有公式（合计/大写沿用模板公式或显式写出）。
"""
import os
import re
from copy import copy

import openpyxl
from datetime import datetime
from openpyxl.styles import Alignment

from rmb_capitalize import rmb_capitalize

_ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
_ALIGN_LEFT = Alignment(horizontal="left", vertical="center")

TPL = os.path.join(os.path.dirname(__file__), "..", "templates")


def _tpl(name):
    return os.path.join(TPL, name)


def resolve_out_path(source_dir: str, filename: str) -> str:
    """报销单输出路径 = 材料所在目录 + 文件名，不建「输出/」子文件夹。"""
    return os.path.join(source_dir.rstrip("/"), filename)


# ---------------------------------------------------------------------------
# ① 市内交通：交通费报销清单（使用实际沿用模板，非官方04）
# ---------------------------------------------------------------------------
def fill_transport_list(data: dict, out_path: str):
    """data = {
        '报销人': '张三',
        'trips': [ {序号:int, 日期:'YYYY-MM-DD', 行程:str, 事由:str,
                    金额:float, 平台:'滴滴出行'/'曹操出行', 发票张数:int|None} ... ],
      }
    发票张数：每个平台组的首行填 1，其余留空（同一发票多行程只记一张），
    并把同一组的发票张数列纵向合并成一个单元格（合并后居中显示）。

    对齐：序号/金额列居中；日期/行程/事由/发票张数/备注列左对齐（发票张数
    合并单元格例外，为便于在多行合并后的框内居中显示数字，单独居中）。
    """
    wb = openpyxl.load_workbook(_tpl("市内交通费报销清单模板.xlsx"))
    ws = wb["Sheet1"]
    ws["B3"] = data["报销人"]

    # 先解除数据区残留合并（发票张数列纵向合并等），再清空
    for mr in list(ws.merged_cells.ranges):
        if mr.min_row >= 5:
            ws.unmerge_cells(str(mr))
    for r in range(5, ws.max_row + 1):
        for c in range(1, 8):
            ws.cell(row=r, column=c).value = None

    trips = data["trips"]
    start = 5
    for i, t in enumerate(trips):
        r = start + i
        ws.cell(row=r, column=1).value = t["序号"]
        ws.cell(row=r, column=1).alignment = _ALIGN_CENTER
        d = t["日期"]
        ws.cell(row=r, column=2).value = (
            datetime.strptime(d, "%Y-%m-%d") if isinstance(d, str) else d
        )
        ws.cell(row=r, column=2).number_format = "yyyy/m/d"
        ws.cell(row=r, column=2).alignment = _ALIGN_LEFT
        ws.cell(row=r, column=3).value = t.get("行程", "")
        ws.cell(row=r, column=3).alignment = _ALIGN_LEFT
        ws.cell(row=r, column=4).value = t.get("事由", "")
        ws.cell(row=r, column=4).alignment = _ALIGN_LEFT
        ws.cell(row=r, column=5).value = round(float(t["金额"]), 2)
        ws.cell(row=r, column=5).alignment = _ALIGN_CENTER
        if t.get("发票张数"):
            ws.cell(row=r, column=6).value = t["发票张数"]
        ws.cell(row=r, column=6).alignment = _ALIGN_LEFT
        ws.cell(row=r, column=7).value = t.get("平台", "")
        ws.cell(row=r, column=7).alignment = _ALIGN_LEFT

    last = start + len(trips) - 1

    # 发票张数列：按「发票张数」标记行切分组，纵向合并同组行，合并格居中
    group_starts = [start + i for i, t in enumerate(trips) if t.get("发票张数")]
    for gi, r0 in enumerate(group_starts):
        r1 = (group_starts[gi + 1] - 1) if gi + 1 < len(group_starts) else last
        if r1 > r0:
            ws.merge_cells(start_row=r0, start_column=6, end_row=r1, end_column=6)
        ws.cell(row=r0, column=6).alignment = _ALIGN_CENTER

    total_r = last + 1
    ws.cell(row=total_r, column=1).value = "合  计"
    ws.cell(row=total_r, column=1).alignment = _ALIGN_CENTER
    ws.cell(row=total_r, column=5).value = f"=SUM(E{start}:E{last})"
    ws.cell(row=total_r, column=5).alignment = _ALIGN_CENTER
    inv = sum(int(t["发票张数"]) for t in trips if t.get("发票张数"))
    ws.cell(row=total_r, column=6).value = inv
    ws.cell(row=total_r, column=6).alignment = _ALIGN_CENTER

    note_r = total_r + 2
    ws.cell(row=note_r, column=1).value = "备注："
    ws.cell(row=note_r, column=2).value = "网约车发票，多个行程，如果在一张发票上，发票张数只记一张"
    wb.save(out_path)
    return {"out": out_path, "total": round(sum(float(t["金额"]) for t in trips), 2),
            "invoice_count": inv}


# ---------------------------------------------------------------------------
# 通用：费用报销单（01）—— 交通汇总 / 招待 共用
# ---------------------------------------------------------------------------
def fill_reimbursement(data: dict, out_path: str):
    """data = {部门, 日期, 报销内容, 金额(float)或 金额公式(str如'=125+317'), 金额数值(float)}
    C7 大写按 金额数值 计算。
    """
    wb = openpyxl.load_workbook(_tpl("01费用报销单模板.xlsx"))
    ws = wb["费用报销单"]
    ws["C3"] = data.get("部门", "")
    ws["E3"] = data.get("日期", "")
    ws["C4"] = data.get("报销内容", "")
    ws["F4"] = data.get("金额公式", data.get("金额"))
    amt = float(data["金额数值"])
    ws["C7"] = "（大写）  " + rmb_capitalize(amt)
    # F7 模板已是 =SUM(F4:G6)，保留
    wb.save(out_path)
    return {"out": out_path, "大写": rmb_capitalize(amt)}


# ---------------------------------------------------------------------------
# ② 出差：出差申请单（07.1）
# ---------------------------------------------------------------------------
def fill_travel_application(data: dict, out_path: str):
    """data = {出差部门,出差时间,出差地点,出差负责人,其他人员,出差事由,
               交通工具:set/str, 住宿:str,
               预算:{交通费,住宿费,餐贴,会议费,其他}, 备注}"""
    wb = openpyxl.load_workbook(_tpl("07.1出差申请单模板.xlsx"))
    ws = wb["出差申请单"]
    ws["C3"] = data.get("出差部门", "")
    ws["H3"] = data.get("出差时间", "")
    ws["L3"] = data.get("出差地点", "")
    ws["C4"] = data.get("出差负责人", "")
    ws["H4"] = data.get("其他人员", "")
    ws["C5"] = data.get("出差事由", "")
    if data.get("交通工具"):
        ws["C6"] = data["交通工具"]
    if data.get("住宿"):
        ws["C7"] = data["住宿"]
    b = data.get("预算", {})
    ws["D8"] = b.get("交通费", 0)
    ws["F8"] = b.get("住宿费", 0)
    ws["H8"] = b.get("餐贴", 0)
    ws["J8"] = b.get("会议费", 0)
    ws["L8"] = b.get("其他", 0)
    # N8 模板公式 =D8+F8+H8+L8+J8 保留
    if data.get("备注"):
        ws["C13"] = data["备注"]
    wb.save(out_path)
    return {"out": out_path}


# ---------------------------------------------------------------------------
# ② 出差：出差费用报销单（03）
# ---------------------------------------------------------------------------
_PLUS_SUM = re.compile(r"\d+(\.\d+)?(\+\d+(\.\d+)?)*")


def _as_number(v) -> float:
    """金额单元格值 → 数值，用于回退总额。

    支持数值、数字字符串，以及纯加法公式字符串（如 '=67.08+31.59'）。
    其他（空、None、非纯加法公式）计 0；Excel 公式本身仍原样写入单元格。
    """
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s.startswith("="):
        body = s[1:]
        if _PLUS_SUM.fullmatch(body):
            return sum(float(x) for x in body.split("+"))
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def fill_travel_reimbursement(data: dict, out_path: str):
    """data = {部门,日期,出差人员,出差地点,出差时间,出差事由,
               rows:[{日期,起讫地点,城市间交通费,住宿费,餐食补贴,会议费,其他费用}...]}
    模板原生 3 个数据行(7,8,9)，类别合计行10，金额合计行11。
    rows 超过 3 行时自动在类别合计行之前插入所需行数，并把类别合计/金额合计的
    求和公式、大写合并单元格、打印区一并扩展到新的数据行范围。
    """
    if not data["rows"]:
        raise ValueError("rows 不能为空")

    wb = openpyxl.load_workbook(_tpl("03出差费用报销单模板.xlsx"))
    ws = wb["出差费用报销单"]
    ws["C3"] = data.get("部门", "")
    ws["E3"] = data.get("日期", "")
    ws["C4"] = data.get("出差人员", "")
    ws["F4"] = data.get("出差地点", "")
    ws["C5"] = data.get("出差时间", "")
    ws["F5"] = data.get("出差事由", "")

    rows = data["rows"]
    cols = {"城市间交通费": "D", "住宿费": "E", "餐食补贴": "F",
            "会议费": "G", "其他费用": "H"}

    extra = max(0, len(rows) - 3)
    if extra:
        _insert_travel_rows(ws, extra)
    last_data_row = 9 + extra
    total_row = last_data_row + 1   # 类别合计
    amount_row = total_row + 1      # 金额合计（含大写）

    total = 0.0
    for i, row in enumerate(rows):
        r = 7 + i
        ws[f"B{r}"] = row.get("日期", "")
        ws[f"C{r}"] = row.get("起讫地点", "")
        for k, col in cols.items():
            v = row.get(k)
            if v:
                ws[f"{col}{r}"] = v
        ws[f"I{r}"] = f"=D{r}+E{r}+F{r}+G{r}+H{r}"
        for k in cols:
            total += _as_number(row.get(k))

    # 模板原生 3 个数据行，若实际行数更少，清空多出的空行（含小计公式），避免残留 0.00
    for r in range(7 + len(rows), 7 + max(3, len(rows))):
        for col in "BCDEFGHI":
            ws[f"{col}{r}"] = None

    if extra:
        for col in ["D", "E", "F", "G", "H"]:
            ws[f"{col}{total_row}"] = f"=SUM({col}7:{col}{last_data_row})"
        ws[f"I{amount_row}"] = f"=SUM(I7:I{last_data_row})"

    amt = float(data.get("总额数值", total))
    ws[f"C{amount_row}"] = "（大写）  " + rmb_capitalize(amt)
    wb.save(out_path)
    return {"out": out_path, "大写": rmb_capitalize(amt), "总额": amt}


def _insert_travel_rows(ws, extra: int):
    """在出差费用报销单第10行（类别合计）之前插入 extra 个数据行。
    openpyxl 的 insert_rows 只移动单元格内容，不会跟着调整合并单元格范围
    与打印区，所以这里手动：先记录并拆掉插入点之后的合并单元格，插行，
    再按 +extra 平移重新合并；新插入的行套用原第9行（末尾数据行）的样式。
    """
    insert_at = 10
    shifted_merges = []
    for mr in list(ws.merged_cells.ranges):
        if mr.min_row >= insert_at:
            shifted_merges.append(mr)
            ws.unmerge_cells(str(mr))

    ws.insert_rows(insert_at, amount=extra)

    for mr in shifted_merges:
        ws.merge_cells(
            start_row=mr.min_row + extra, start_column=mr.min_col,
            end_row=mr.max_row + extra, end_column=mr.max_col,
        )

    for i in range(extra):
        new_r = insert_at + i
        for c in range(1, ws.max_column + 1):
            src_cell = ws.cell(row=9, column=c)
            dst_cell = ws.cell(row=new_r, column=c)
            dst_cell.font = copy(src_cell.font)
            dst_cell.border = copy(src_cell.border)
            dst_cell.fill = copy(src_cell.fill)
            dst_cell.number_format = src_cell.number_format
            dst_cell.alignment = copy(src_cell.alignment)
        ws.row_dimensions[new_r].height = ws.row_dimensions[9].height

    if ws.print_area:
        head, tail = ws.print_area.rsplit(":", 1)
        tail = re.sub(
            r"(\$?[A-Za-z]+\$?)(\d+)$",
            lambda m: f"{m.group(1)}{int(m.group(2)) + extra}",
            tail,
        )
        ws.print_area = f"{head}:{tail}"


# ---------------------------------------------------------------------------
# ③ 招待：业务招待备案表（05）
# ---------------------------------------------------------------------------
def fill_entertainment_record(data: dict, out_path: str):
    """data = {申请部门,申请日期,接待负责人,参与接待人数,客人单位人数,
               接待事由,申请金额,申请标准,具体方式}"""
    wb = openpyxl.load_workbook(_tpl("05业务招待备案表模板.xlsx"))
    ws = wb["业务招待备案表"]
    ws["C3"] = data.get("申请部门", "")
    ws["F3"] = data.get("申请日期", "")
    ws["C4"] = data.get("接待负责人", "")
    ws["F4"] = data.get("参与接待人数", "")
    ws["C5"] = data.get("客人单位人数", "")
    ws["C6"] = data.get("接待事由", "")
    ws["C7"] = data.get("申请金额", "")
    ws["F7"] = data.get("申请标准", "")
    if data.get("具体方式"):
        ws["F8"] = data["具体方式"]
    wb.save(out_path)
    return {"out": out_path}
