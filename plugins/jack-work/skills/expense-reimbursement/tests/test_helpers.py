#!/usr/bin/env python3
"""餐补 + 税抵扣 边界单测（D5）。python3 tests/test_helpers.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from meal_subsidy import meal_subsidy, city_tier, billable_days
from tax_deduction import is_tax_deductible, deductible_trips

failed = 0


def check(name, got, expect):
    global failed
    if got != expect:
        failed += 1
        print(f"FAIL {name}: got {got!r} expect {expect!r}")
    else:
        print(f"ok   {name} -> {got}")


# ---- 餐补 ----
# 北京黄金样例：300×2×1 = 600
check("北京 1天 2人", meal_subsidy("北京", 1, 2)["amount"], 600)
check("北京市 后缀", meal_subsidy("北京市", 1, 2)["amount"], 600)
# 半天按全天
check("1.5天向上取整", billable_days(1.5), 2)
check("0.5天->1", billable_days(0.5), 1)
check("出差1.5天上海300/天=900? 单人", meal_subsidy("上海", 1.5, 1)["amount"], 600)  # 300*2*1
# 城市档位
check("苏州=其他城市150", city_tier("苏州"), "other")
check("苏州餐补 1天1人", meal_subsidy("苏州", 1, 1)["amount"], 150)
check("南京=省会200", city_tier("南京"), "tier2")
check("天津=直辖市200", city_tier("天津"), "tier2")
check("深圳=北上广深300", meal_subsidy("深圳", 1, 1)["amount"], 300)
check("某县城=其他150", meal_subsidy("某县", 2, 1)["amount"], 300)
# people 缺省=1人
check("people缺省=1人", meal_subsidy("北京", 1)["amount"], 300)
# 0天出差(如当日往返未过夜) -> 餐补0，不报错不为负
check("0天出差餐补为0", meal_subsidy("北京", 0, 2)["amount"], 0)
check("billable_days(0)=0", billable_days(0), 0)
# 空/None城市 -> 归为other档，不报错
check("空字符串城市=other", city_tier(""), "other")
check("None城市=other", city_tier(None), "other")
check("None城市餐补按150计", meal_subsidy(None, 1, 1)["amount"], 150)

# ---- 税抵扣 ----
check("滴滴特惠快车可抵扣", is_tax_deductible("滴滴出行", "特惠快车"), True)
check("滴滴惊喜特价可抵扣", is_tax_deductible("滴滴出行", "惊喜特价"), True)
check("曹操不可抵扣", is_tax_deductible("曹操出行", "曹操出行"), False)
check("T3不可抵扣", is_tax_deductible("T3出行", ""), False)
check("出租车纸质不可抵扣", is_tax_deductible("出租车", ""), False)
check("滴滴专车不可抵扣", is_tax_deductible("滴滴出行", "专车"), False)
trips = [
    {"platform": "滴滴出行", "car_type": "特惠快车", "amount": 17.6},
    {"platform": "曹操出行", "car_type": "曹操出行", "amount": 16.48},
]
check("筛选仅滴滴", [t["amount"] for t in deductible_trips(trips)], [17.6])

print(f"\n{'ALL PASS' if not failed else str(failed)+' FAILED'}")
sys.exit(1 if failed else 0)
