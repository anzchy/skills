#!/usr/bin/env python3
"""fill_transport_list() 对齐方式 + 发票张数纵向合并 单测。
python3 tests/test_fill_transport_list.py
需要 openpyxl：用 python3.11 跑。
"""
import os, sys, tempfile
import openpyxl

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fill_forms import fill_transport_list

failed = 0


def check(name, got, expect):
    global failed
    if got != expect:
        failed += 1
        print(f"FAIL {name}: got {got!r} expect {expect!r}")
    else:
        print(f"ok   {name} -> {got}")


# 3 组发票：组1(行5-6,2笔) 组2(行7,1笔) 组3(行8-10,3笔)
trips = [
    {"序号": 1, "日期": "2026-07-01", "行程": "A-B", "事由": "事由1", "金额": 10.0, "平台": "曹操出行", "发票张数": 1},
    {"序号": 2, "日期": "2026-07-01", "行程": "B-C", "事由": "事由2", "金额": 20.0, "平台": "曹操出行"},
    {"序号": 3, "日期": "2026-07-02", "行程": "C-D", "事由": "事由3", "金额": 30.0, "平台": "滴滴出行", "发票张数": 1},
    {"序号": 4, "日期": "2026-07-03", "行程": "D-E", "事由": "事由4", "金额": 40.0, "平台": "阳光出行", "发票张数": 1},
    {"序号": 5, "日期": "2026-07-04", "行程": "E-F", "事由": "事由5", "金额": 50.0, "平台": "阳光出行"},
    {"序号": 6, "日期": "2026-07-05", "行程": "F-G", "事由": "事由6", "金额": 60.0, "平台": "阳光出行"},
]

out = tempfile.mktemp(suffix=".xlsx")
result = fill_transport_list({"报销人": "张三", "trips": trips}, out)
wb = openpyxl.load_workbook(out)
ws = wb["Sheet1"]

# ---- 对齐：序号/金额居中，日期/行程/事由/发票张数/备注左对齐 ----
check("序号列(A5)居中", ws["A5"].alignment.horizontal, "center")
check("金额列(E5)居中", ws["E5"].alignment.horizontal, "center")
check("日期列(B5)左对齐", ws["B5"].alignment.horizontal, "left")
check("行程列(C5)左对齐", ws["C5"].alignment.horizontal, "left")
check("事由列(D5)左对齐", ws["D5"].alignment.horizontal, "left")
check("备注/平台列(G5)左对齐", ws["G5"].alignment.horizontal, "left")

# ---- 发票张数列：同组纵向合并，合并格居中 ----
merged = {str(m) for m in ws.merged_cells.ranges}
check("组1(2笔,行5-6)合并", "F5:F6" in merged, True)
check("组3(3笔,行8-10)合并", "F8:F10" in merged, True)
check("组2(1笔,行7)不产生单行合并", "F7:F7" in merged, False)
check("组1合并格(F5)居中", ws["F5"].alignment.horizontal, "center")
check("组3合并格(F8)居中", ws["F8"].alignment.horizontal, "center")
check("组2单行(F7)居中", ws["F7"].alignment.horizontal, "center")

# ---- 合计行：A/E/F 居中 ----
total_r = 5 + len(trips)
check("合计行标签(A)居中", ws.cell(row=total_r, column=1).alignment.horizontal, "center")
check("合计行金额(E)居中", ws.cell(row=total_r, column=5).alignment.horizontal, "center")
check("合计行发票张数(F)居中", ws.cell(row=total_r, column=6).alignment.horizontal, "center")
check("合计=210", ws.cell(row=total_r, column=5).value, "=SUM(E5:E10)")
check("发票张数合计=3", ws.cell(row=total_r, column=6).value, 3)
check("返回值 invoice_count=3", result["invoice_count"], 3)
check("返回值 total=210.0", result["total"], 210.0)

print(f"\n{'ALL PASS' if not failed else str(failed)+' FAILED'}")
sys.exit(1 if failed else 0)
