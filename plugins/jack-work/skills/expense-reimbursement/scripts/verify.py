#!/usr/bin/env python3
"""验收层（D2/D6）：把 skill 产出与黄金样例逐字段比对。

口径：A 类字段（金额/合计/大写/日期/张数）100% 一致；B 类（事由/行程文字）不在自动比对内。
- compare_values(): 通用单元格值比对（按计算值 data_only）。
- run_transport_regression(): 对「纯网约车、全部计入」的交通样例跑端到端
  （解析→写出→比对合计与大写），可完全自动验收。

注意：202409 含出租车纸质发票（71.00 元）不在任何 PDF 中，需 Claude/用户补录，
故不纳入纯自动回归；出差/招待需 Claude 读票据（住宿/机票/餐饮）后才能端到端验收。
"""
import os
import sys
import re

sys.path.insert(0, os.path.dirname(__file__))
import openpyxl
from rmb_capitalize import rmb_capitalize
from parse_trip_report import parse_trip_report
from fill_forms import fill_transport_list, fill_reimbursement

BASE = os.path.join(os.path.dirname(__file__), "..", "..")


def cell_value(path, sheet, cell):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet] if sheet else wb.active
    return ws[cell].value


def norm_capital(s):
    """归一化大写串：去掉「（大写）」与空白，便于比对。"""
    if s is None:
        return ""
    return re.sub(r"[（）()\s]", "", str(s)).replace("大写", "")


def compare_values(gen_path, gold_path, checks):
    """checks: [(sheet, cell, kind)] kind in {'num','text','capital'}。返回结果列表。"""
    out = []
    for sheet, cell, kind in checks:
        g = cell_value(gen_path, sheet, cell)
        r = cell_value(gold_path, sheet, cell)
        if kind == "num":
            ok = (g is not None and r is not None
                  and abs(float(g) - float(r)) < 0.011)
        elif kind == "capital":
            ok = norm_capital(g) == norm_capital(r)
        else:
            ok = str(g) == str(r)
        out.append({"cell": f"{sheet}!{cell}", "gen": g, "gold": r, "ok": ok})
    return out


# ---------------------------------------------------------------------------
# 交通端到端回归（完全自动可验收的样例）
# ---------------------------------------------------------------------------
def build_trips_from_folder(folder):
    """解析目录下所有行程报销单，按平台分组生成 trips（全部计入），
    发票张数 = 每个平台首行记 1。"""
    pdfs = [f for f in os.listdir(folder) if "行程报销单" in f and f.endswith(".pdf")]
    groups = []  # [(platform, [trips])]
    for f in sorted(pdfs):
        r = parse_trip_report(os.path.join(folder, f))
        if not r["total_match"]:
            print(f"  ⚠ 交叉核对未通过 {f}: 解析{r['parsed_total']} vs 自报{r['reported_total']}（可能有行程被排除）")
        groups.append((r["platform"], r["trips"]))
    trips = []
    serial = 1
    for platform, ts in groups:
        for i, t in enumerate(ts):
            trips.append({
                "序号": serial,
                "日期": t["date"],
                "行程": t["start"] + "-" + t["end"],
                "事由": "(待补全)",
                "金额": t["amount"],
                "平台": platform,
                "发票张数": 1 if i == 0 else None,
            })
            serial += 1
    return trips


def run_transport_regression(folder, gold_reimb, label):
    trips = build_trips_from_folder(folder)
    total = round(sum(t["金额"] for t in trips), 2)
    os.makedirs("/tmp/verify_out", exist_ok=True)
    out = f"/tmp/verify_out/{label}_报销单.xlsx"
    fill_reimbursement({"部门": "投资部", "日期": "", "报销内容": "",
                        "金额": total, "金额数值": total}, out)
    gold_total = float(cell_value(gold_reimb, "费用报销单", "F4"))
    gold_cap = cell_value(gold_reimb, "费用报销单", "C7")
    gen_cap = rmb_capitalize(total)
    ok_total = abs(total - gold_total) < 0.011
    ok_cap = norm_capital(gen_cap) == norm_capital(gold_cap)
    print(f"[{label}] 合计 gen={total} gold={gold_total} {'✓' if ok_total else '✗'} | "
          f"大写 gen={gen_cap} gold={norm_capital(gold_cap)} {'✓' if ok_cap else '✗'}")
    return ok_total and ok_cap


def main():
    print("=== 交通端到端回归（纯网约车、全部计入）===")
    samples = [
        ("2024 年 12 月上海市内交通",
         "2024 年 12 月上海市内交通/2024年12月 上海市内交通费用报销单.xlsx", "202412"),
        ("2025 年四季度上海交通费用",
         "2025 年四季度上海交通费用/2025年第四季度-上海市内交通-报销单.xlsx", "2025Q4"),
    ]
    ok = True
    for folder, gold, label in samples:
        fp = os.path.join(BASE, folder)
        gp = os.path.join(BASE, gold)
        if not (os.path.isdir(fp) and os.path.exists(gp)):
            print(f"[{label}] 跳过（样例不在 {fp}）")
            continue
        ok = run_transport_regression(fp, gp, label) and ok
    print("\n注：202409（含出租车纸质票 71.00）、出差、招待 需 Claude 读票/用户补录后再验收，"
          "用 compare_values() 做单元格比对。")
    print("RESULT:", "ALL PASS ✓" if ok else "SOME FAILED ✗")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
