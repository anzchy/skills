#!/usr/bin/env python3
"""出差餐食补贴计算（确定性脚本）。

标准出处：《报销检查清单-发给财务之前过一遍.md》职级标准表 + 餐补规则。
- 伙食标准（元/人/天），员工与董事/监事/投委/顾问相同：
    北上广深                         300
    其他省会城市/直辖市/计划单列市   200
    其他城市                         150
- 半天按一天算（天数向上取整）。
- 餐补 = 标准 × 人数 × 计费天数。

北京黄金样例校验：300 × 2人 × 1天 = 600。
"""
import math

TIER1 = {"北京", "上海", "广州", "深圳"}  # 北上广深 300
# 其他省会城市 / 直辖市 / 计划单列市 200（深圳已在 TIER1）
TIER2 = {
    # 直辖市
    "天津", "重庆",
    # 计划单列市
    "大连", "青岛", "宁波", "厦门",
    # 省会城市
    "石家庄", "太原", "呼和浩特", "沈阳", "长春", "哈尔滨", "南京", "杭州",
    "合肥", "福州", "南昌", "济南", "郑州", "武汉", "长沙", "成都", "贵阳",
    "昆明", "拉萨", "西安", "兰州", "西宁", "银川", "乌鲁木齐", "海口", "南宁",
}

STANDARD = {"tier1": 300, "tier2": 200, "other": 150}


def city_tier(city: str) -> str:
    """根据出差地点城市名判定档位。匹配「市」字与全/简称。"""
    c = (city or "").strip().replace("市", "")
    if c in TIER1:
        return "tier1"
    if c in TIER2:
        return "tier2"
    return "other"


def billable_days(days) -> int:
    """半天按全天：天数向上取整。1.5 -> 2，1 -> 1。"""
    d = float(days)
    return math.ceil(d - 1e-9) if d > 0 else 0


def meal_subsidy(city: str, days, people: int = 1, role: str = "员工") -> dict:
    """返回 {standard, tier, billable_days, people, amount}。

    role 入参仅作记录——伙食标准员工与董监投顾相同，不影响金额。
    """
    tier = city_tier(city)
    std = STANDARD[tier]
    bd = billable_days(days)
    amount = std * bd * int(people)
    return {
        "city": city,
        "tier": tier,
        "standard": std,
        "billable_days": bd,
        "people": int(people),
        "role": role,
        "amount": amount,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) >= 3:
        city, days = sys.argv[1], sys.argv[2]
        ppl = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        print(json.dumps(meal_subsidy(city, days, ppl), ensure_ascii=False, indent=2))
