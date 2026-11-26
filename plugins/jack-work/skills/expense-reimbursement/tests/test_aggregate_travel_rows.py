#!/usr/bin/env python3
"""aggregate_travel_rows() 单测（TDD，红→绿）。python3 tests/test_aggregate_travel_rows.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from aggregate_travel_rows import aggregate_travel_rows

failed = 0


def check(name, got, expect):
    global failed
    if got != expect:
        failed += 1
        print(f"FAIL {name}: got {got!r} expect {expect!r}")
    else:
        print(f"ok   {name} -> {got}")


# ---- 用户给出的① 同路线同方向同日期，多个出差人 → 合并为一行，金额相加 ----
records = [
    {"日期": "2026-08-06", "出发地": "上海虹桥", "到达地": "句容", "金额": 147.0, "出差人": "张三"},
    {"日期": "2026-08-06", "出发地": "上海虹桥", "到达地": "句容", "金额": 147.0, "出差人": "王云美"},
    {"日期": "2026-08-06", "出发地": "上海虹桥", "到达地": "句容", "金额": 147.0, "出差人": "蔡文洁"},
]
rows = aggregate_travel_rows(records)
check("①合并为1行", len(rows), 1)
check("①金额相加", rows[0]["城市间交通费"], 441.0)
check("①起讫地点", rows[0]["起讫地点"], "上海虹桥-句容")

# ---- 用户给出的② 同日期方向相反 → 各自独立成行，不合并 ----
records2 = [
    {"日期": "2026-08-06", "出发地": "上海虹桥", "到达地": "句容", "金额": 147.0},
    {"日期": "2026-08-06", "出发地": "句容", "到达地": "上海虹桥", "金额": 150.0},
]
rows2 = aggregate_travel_rows(records2)
check("②方向相反分2行", len(rows2), 2)
check("②去程金额", rows2[0]["城市间交通费"], 147.0)
check("②返程金额", rows2[1]["城市间交通费"], 150.0)

# ---- 同路线不同日期（多日行程）→ 按日期分行 ----
records3 = [
    {"日期": "2026-08-06", "出发地": "上海虹桥", "到达地": "句容", "金额": 147.0},
    {"日期": "2026-08-07", "出发地": "上海虹桥", "到达地": "句容", "金额": 147.0},
]
rows3 = aggregate_travel_rows(records3)
check("③不同日期分2行", len(rows3), 2)
check("③第1行日期", rows3[0]["日期"], "2026-08-06")
check("③第2行日期", rows3[1]["日期"], "2026-08-07")

# ---- 站名书写变体指向同一物理站点 → 归一化后应合并（"南京南" vs "南京南站"） ----
records4 = [
    {"日期": "2026-08-06", "出发地": "句容西", "到达地": "南京南", "金额": 3.0},
    {"日期": "2026-08-06", "出发地": "句容西", "到达地": "南京南站", "金额": 32.5},
]
rows4 = aggregate_travel_rows(records4)
check("④站名归一化后合并为1行", len(rows4), 1)
check("④金额相加", rows4[0]["城市间交通费"], 35.5)

# ---- 真实票价 与 退票费 同路线同日期 → 合并为一行、金额相加（用户已确认：合并） ----
records5 = [
    {"日期": "2026-08-06", "出发地": "南京南", "到达地": "上海虹桥", "金额": 162.0},
    {"日期": "2026-08-06", "出发地": "南京南", "到达地": "上海虹桥", "金额": 32.5},
]
rows5 = aggregate_travel_rows(records5)
check("⑤票价+退票费合并1行", len(rows5), 1)
check("⑤金额相加", rows5[0]["城市间交通费"], 194.5)

# ---- 分组数 >3 → aggregate_travel_rows 原样输出全部分组，不在此处截断（插行逻辑在 fill_forms.py 侧处理） ----
records6 = [
    {"日期": f"2026-08-0{i}", "出发地": "A", "到达地": "B", "金额": 10.0}
    for i in range(1, 6)
]
rows6 = aggregate_travel_rows(records6)
check("⑥超过3组不截断", len(rows6), 5)

# ---- 空输入（0条腿程记录）→ 报错，不生成空白报销单 ----
try:
    aggregate_travel_rows([])
    check("⑦空输入应报错", "no error raised", "ValueError")
except ValueError:
    check("⑦空输入报错", "ValueError", "ValueError")

# ---- 非路线维度列（住宿费/餐食补贴/会议费/其他费用）只写在第一行，其余行留0 ----
rows8 = aggregate_travel_rows(
    records, other_fees={"住宿费": 737.44, "餐食补贴": 600, "会议费": 0, "其他费用": 0}
)
check("⑧首行住宿费", rows8[0]["住宿费"], 737.44)
check("⑧首行餐食补贴", rows8[0]["餐食补贴"], 600)

rows8b = aggregate_travel_rows(
    records2, other_fees={"住宿费": 737.44, "餐食补贴": 600, "会议费": 0, "其他费用": 0}
)
check("⑧非首行住宿费为0", rows8b[1]["住宿费"], 0)
check("⑧非首行餐食补贴为0", rows8b[1]["餐食补贴"], 0)
check("⑧首行住宿费(多行场景)", rows8b[0]["住宿费"], 737.44)

print(f"\n{'ALL PASS' if not failed else str(failed)+' FAILED'}")
sys.exit(1 if failed else 0)
