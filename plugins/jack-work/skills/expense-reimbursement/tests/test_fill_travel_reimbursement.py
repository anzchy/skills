#!/usr/bin/env python3
"""fill_travel_reimbursement() 自动插行 单测（TDD，红→绿）。
python3 tests/test_fill_travel_reimbursement.py
需要 openpyxl：用 python3.11 跑。
"""
import os, sys, tempfile
import openpyxl

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fill_forms import fill_travel_reimbursement

failed = 0


def check(name, got, expect):
    global failed
    if got != expect:
        failed += 1
        print(f"FAIL {name}: got {got!r} expect {expect!r}")
    else:
        print(f"ok   {name} -> {got}")


def make_rows(n):
    return [
        {"日期": "2026-08-06", "起讫地点": f"站{i}-站{i+1}", "城市间交通费": 10.0 * (i + 1)}
        for i in range(n)
    ]


# ---- 基线：n<=3 不插行，模板原有公式/合并单元格不变（回归锁定） ----
out1 = tempfile.mktemp(suffix=".xlsx")
result1 = fill_travel_reimbursement(
    {"部门": "示例部门", "日期": "2026-08-25", "rows": make_rows(2)}, out1
)
wb1 = openpyxl.load_workbook(out1)
ws1 = wb1["出差费用报销单"]
check("n=2 不插行:D10公式不变", ws1["D10"].value, "=D7+D8+D9")
check("n=2 不插行:I11公式不变", ws1["I11"].value, "=I7+I8+I9")
check("n=2 不插行:大写合并单元格不变", "C11:H11" in {str(m) for m in ws1.merged_cells.ranges}, True)
check("n=2 回退总额=两行相加(10+20=30)", result1["总额"], 30.0)

# ---- 超过3行 → 自动在汇总行之前插入所需行数 ----
out2 = tempfile.mktemp(suffix=".xlsx")
result2 = fill_travel_reimbursement(
    {"部门": "示例部门", "日期": "2026-08-25", "rows": make_rows(5)}, out2
)
wb2 = openpyxl.load_workbook(out2)
ws2 = wb2["出差费用报销单"]
# n=5 -> extra=2 -> 数据行 7..11，类别合计行12，金额合计行13
check("n=5 数据行7值", ws2["C7"].value, "站0-站1")
check("n=5 数据行11值(第5行)", ws2["C11"].value, "站4-站5")
check("n=5 类别合计行D12公式覆盖全部数据行", ws2["D12"].value, "=SUM(D7:D11)")
check("n=5 金额合计行I13公式覆盖全部数据行", ws2["I13"].value, "=SUM(I7:I11)")
check(
    "n=5 大写合并单元格随插行移动到C13:H13",
    "C13:H13" in {str(m) for m in ws2.merged_cells.ranges},
    True,
)
check(
    "n=5 旧位置C11:H11不再是合并单元格",
    "C11:H11" in {str(m) for m in ws2.merged_cells.ranges},
    False,
)
check("n=5 print_area随插行扩展", ws2.print_area, "'出差费用报销单'!$B$1:$I$16")
check("n=5 插入行样式沿用原数据行边框", ws2["C10"].border.left.style, "thin")
# 城市间交通费 10+20+30+40+50=150；回退总额必须累加全部5行，不能只算前3行（原bug）
check("n=5 回退总额累加全部5行(150)不再只算前3行", result2["总额"], 150.0)

# ---- 金额为0的单元格应留空(None)，不写 0/¥0.00（住宿费/餐食补贴等非路线列常见） ----
out3 = tempfile.mktemp(suffix=".xlsx")
rows3 = [
    {"日期": "2026-08-06", "起讫地点": "上海虹桥-句容", "城市间交通费": 147.0,
     "住宿费": 737.44, "餐食补贴": 600, "会议费": 0, "其他费用": 0},
    {"日期": "2026-08-06", "起讫地点": "句容-上海虹桥", "城市间交通费": 150.0,
     "住宿费": 0, "餐食补贴": 0, "会议费": 0, "其他费用": 0},
]
result3 = fill_travel_reimbursement(
    {"部门": "示例部门", "日期": "2026-08-25", "rows": rows3}, out3
)
wb3 = openpyxl.load_workbook(out3)
ws3 = wb3["出差费用报销单"]
check("首行有值列(住宿费737.44)正常写入", ws3["E7"].value, 737.44)
check("首行有值列(餐食补贴600)正常写入", ws3["F7"].value, 600)
check("首行金额为0列(会议费)留空非0", ws3["G7"].value, None)
check("首行金额为0列(其他费用)留空非0", ws3["H7"].value, None)
check("次行金额为0列(住宿费)留空非0", ws3["E8"].value, None)
check("次行金额为0列(餐食补贴)留空非0", ws3["F8"].value, None)
check("城市间交通费有值正常写入不受影响", ws3["D8"].value, 150.0)

print(f"\n{'ALL PASS' if not failed else str(failed)+' FAILED'}")
sys.exit(1 if failed else 0)
