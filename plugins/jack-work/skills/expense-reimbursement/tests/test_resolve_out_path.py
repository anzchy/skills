#!/usr/bin/env python3
"""resolve_out_path() 单测（TDD，红→绿）。python3 tests/test_resolve_out_path.py
报销单输出路径 = 材料所在目录 + 文件名，不建 输出/ 子文件夹。
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fill_forms import resolve_out_path

failed = 0


def check(name, got, expect):
    global failed
    if got != expect:
        failed += 1
        print(f"FAIL {name}: got {got!r} expect {expect!r}")
    else:
        print(f"ok   {name} -> {got}")


check(
    "直接拼接材料目录+文件名",
    resolve_out_path("招待厦门象屿投资", "01费用报销单-招待厦门象屿投资.xlsx"),
    os.path.join("招待厦门象屿投资", "01费用报销单-招待厦门象屿投资.xlsx"),
)
check(
    "不生成/引用 输出 子文件夹",
    "输出" in resolve_out_path("招待美的资本合伙人", "01费用报销单-招待美的资本合伙人.xlsx"),
    False,
)
check(
    "材料目录带末尾斜杠也能正确拼接",
    resolve_out_path("句容出差/", "03出差费用报销单-句容出差.xlsx"),
    os.path.join("句容出差", "03出差费用报销单-句容出差.xlsx"),
)

print(f"\n{'ALL PASS' if not failed else str(failed)+' FAILED'}")
sys.exit(1 if failed else 0)
