#!/usr/bin/env python3
"""rmb_capitalize 边界单测（D5）。直接运行：python3 tests/test_rmb_capitalize.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from rmb_capitalize import rmb_capitalize as cap

CASES = {
    # 黄金样例实测值（4 类输出的大写串，公司口径）
    177.64: "壹佰柒拾柒元陆角肆分",   # 2025Q4 交通
    4109.07: "肆仟壹佰零玖元零柒分",  # 北京出差
    442: "肆佰肆拾贰元整",            # 启浦招待
    442.00: "肆佰肆拾贰元整",
    230.50: "贰佰叁拾元伍角零分",     # 苏州出差：角非零、分为零 -> 「伍角零分」
    84: "捌拾肆元整",                 # 旭辉招待
    # 边界：零/角/分/整（公司口径——仅整元用「整」，有角分写满两位用零占位）
    0: "零元整",
    0.5: "零元伍角零分",
    0.05: "零元零伍分",
    0.07: "零元零柒分",
    10.40: "壹拾元肆角零分",
    100: "壹佰元整",
    1000: "壹仟元整",
    10000: "壹万元整",
    100000000: "壹亿元整",
    10009: "壹万零玖元整",
    100000: "壹拾万元整",
    1000000: "壹佰万元整",
    20070.07: "贰万零柒拾元零柒分",
    317: "叁佰壹拾柒元整",
    208.10: "贰佰零捌元壹角零分",
}


def main():
    failed = 0
    for amt, expect in CASES.items():
        got = cap(amt)
        ok = got == expect
        if not ok:
            failed += 1
            print(f"FAIL {amt}: got {got!r} expect {expect!r}")
        else:
            print(f"ok   {amt} -> {got}")
    print(f"\n{len(CASES)-failed}/{len(CASES)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
