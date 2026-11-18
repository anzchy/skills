#!/usr/bin/env python3
"""市内交通税抵扣判定（确定性脚本）。

规则出处：《报销检查清单》「报销测算汇总」：
- 滴滴出行平台「滴滴快车」（含特惠快车/惊喜特价等快车类）的税【可抵扣】，计入汇总表。
- 出租车纸质发票、曹操出行电子发票、T3 出行电子发票 的税【不可抵扣】，不填汇总表。

判定以「平台」为准：滴滴平台快车类 -> True；其余 -> False。
"""

# 不可抵扣平台关键词
NON_DEDUCTIBLE = ("曹操", "T3", "t3", "出租车", "首汽", "神州")
# 可抵扣：滴滴平台快车类
DIDI_KEYS = ("滴滴",)
# 滴滴平台内若为非快车类（专车/豪华车），按需另判；当前样例均为快车类。
DIDI_NON_KUAICHE = ("专车", "豪华车", "六座")


def is_tax_deductible(platform: str, car_type: str = "") -> bool:
    """平台/车型 -> 税是否可抵扣。"""
    p = (platform or "")
    ct = (car_type or "")
    if any(k in p for k in NON_DEDUCTIBLE):
        return False
    if any(k in p for k in DIDI_KEYS):
        # 滴滴平台：默认快车类可抵扣；明确为专车/豪华车则不抵扣
        if any(k in ct for k in DIDI_NON_KUAICHE):
            return False
        return True
    return False


def deductible_trips(trips: list) -> list:
    """从行程列表筛出税可抵扣的行程。trip 需含 'platform'（可选 'car_type'）。"""
    return [t for t in trips if is_tax_deductible(t.get("platform", ""), t.get("car_type", ""))]


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2:
        print(is_tax_deductible(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""))
