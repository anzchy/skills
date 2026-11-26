#!/usr/bin/env python3
"""出差费用报销单「两行布局」回归单测（TDD，红→绿）。

来源：2026-11-19 苏州示例项目公司出差报销的真实纠错，防止复发：
  1. 市内打车不单列一行，计入「其他费用」列（同一行程行）。
  2. 餐补不单列一行，计入「餐食补贴」列（同一行程行）。
  3. 同日往返只需两行：第一行「上海—苏州」，第二行「苏州—上海」。
  4. 模板多余的空数据行（第3行）不得残留小计公式（会显示 0.00）。
  5. 「其他费用」填公式字符串（如 =67.08+31.59）时，回退总额必须仍然正确。

运行：python3 tests/test_travel_two_row_layout.py
需要 openpyxl：python3 跑。
"""
import os, re, sys, tempfile
import openpyxl

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from fill_forms import fill_travel_reimbursement

failed = 0


def check(name, got, expect):
    global failed
    if got != expect:
        failed += 1
        print(f"FAIL {name}: got {got!r} expect {expect!r}")
    else:
        print(f"ok   {name} -> {got}")


def shanghai_suzhou_trip():
    """苏州示例项目出差的真实数据：两行，打车+餐补并入第一行。"""
    return {
        "部门": "示例部门",
        "日期": "2026-11-23",
        "出差人员": "张三",
        "出差地点": "苏州",
        "出差时间": "2026-11-19（当日往返）",
        "出差事由": "测试事由",
        "rows": [
            {"日期": "2026-11-19", "起讫地点": "上海—苏州",
             "城市间交通费": 46, "其他费用": "=67.08+31.59", "餐食补贴": 150},
            {"日期": "2026-11-19", "起讫地点": "苏州—上海",
             "城市间交通费": 46},
        ],
    }


out = tempfile.mktemp(suffix=".xlsx")
result = fill_travel_reimbursement(shanghai_suzhou_trip(), out)
ws = openpyxl.load_workbook(out)["出差费用报销单"]

# ---- 1. 两行布局：数据行只到第8行，第9行必须是空行 ----
check("第1行起讫地点为 上海—苏州", ws["C7"].value, "上海—苏州")
check("第2行起讫地点为 苏州—上海", ws["C8"].value, "苏州—上海")
check("第1行城市间交通费为 46（高铁去程）", ws["D7"].value, 46)
check("第2行城市间交通费为 46（高铁返程）", ws["D8"].value, 46)

# ---- 2. 打车计入「其他费用」列（H），不单列行 ----
check("打车金额写入第1行其他费用H7", ws["H7"].value, "=67.08+31.59")
check("打车不单列：第2行其他费用H8为空", ws["H8"].value, None)

# ---- 3. 餐补计入「餐食补贴」列（F），不单列行 ----
check("餐补写入第1行餐食补贴F7", ws["F7"].value, 150)
check("餐补不单列：第2行餐食补贴F8为空", ws["F8"].value, None)

# ---- 4. 多余空行不残留公式/内容（第9行） ----
for col in "BCDEFGHI":
    check(f"第9行{col}列为空（无残留）", ws[f"{col}9"].value, None)

# ---- 5. 行小计公式仅在有数据的行 ----
check("第1行小计I7 公式", ws["I7"].value, "=D7+E7+F7+G7+H7")
check("第2行小计I8 公式", ws["I8"].value, "=D8+E8+F8+G8+H8")

# ---- 6. 汇总行与总额 ----
check("类别合计D10 覆盖第7-9行", ws["D10"].value, "=D7+D8+D9")
check("金额合计I11 覆盖第7-9行", ws["I11"].value, "=I7+I8+I9")
# 公式字符串「=67.08+31.59」不能被当作0 — 回退总额必须是 46+46+98.67+150 = 340.67
check("回退总额含公式字符串其他费用(=340.67)", result["总额"], 340.67)
check("大写金额为叁佰肆拾元陆角柒分", result["大写"], "叁佰肆拾元陆角柒分")

# ---- 7. 模板残留的第3行格式/合并：大写合并区仍在汇总行 ----
check("大写合并区C11:H11 仍存在", "C11:H11" in {str(m) for m in ws.merged_cells.ranges}, True)

# ---- 8. 错误样例 fixture（2026-11-19 的错误三行版）不得再被生成 ----
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "03_wrong_three_rows.xlsx")
wrong = openpyxl.load_workbook(FIXTURE)["出差费用报销单"]
check("fixture 确为错误版：第3个数据行是「苏州市内打车」单列行",
      "市内打车" in str(wrong["C8"].value), True)
check("fixture 确为错误版：餐补单列为第3行", "餐食补贴" in str(wrong["C9"].value), True)
check("新生成结果没有「市内打车」单列行",
      any("市内打车" in str(ws[f"C{r}"].value or "") for r in range(7, 10)), False)
check("新生成结果没有「餐食补贴」单列行",
      any("餐食补贴1天" in str(ws[f"C{r}"].value or "") for r in range(7, 10)), False)

# ---- 9. SOP 文档规则存在（防止 SKILL.md 与实现再次脱节） ----
skill = open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
check("SKILL 写明市内接驳计入「其他费用」",
      bool(re.search(r"市内接驳.*其他费用", skill)), True)
check("SKILL 写明餐补并入「餐食补贴」同一行",
      bool(re.search(r"餐食补贴.*同一行|同一行.*餐食补贴", skill)), True)
check("SKILL 写明同日往返只两行（上海—苏州、苏州—上海）",
      bool(re.search(r"两行.*上海.*苏州|上海—苏州.*苏州—上海", skill)), True)

print(f"\n{'ALL PASS' if not failed else str(failed)+' FAILED'}")
sys.exit(1 if failed else 0)
