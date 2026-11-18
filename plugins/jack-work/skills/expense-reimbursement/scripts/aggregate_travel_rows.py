#!/usr/bin/env python3
"""聚合层：把逐段车票记录按 (路线+方向, 日期) 分组，跨出差人汇总城市间交通费。

不做行数上限截断——超过模板容量后如何插行由 fill_forms.py 处理。
"""

_STATION_SUFFIXES = ("站",)


def _normalize_station(name: str) -> str:
    name = (name or "").strip()
    for suf in _STATION_SUFFIXES:
        if name.endswith(suf) and len(name) > len(suf):
            name = name[: -len(suf)]
    return name


def aggregate_travel_rows(records: list, other_fees: dict = None) -> list:
    """records = [{日期, 出发地, 到达地, 金额, 出差人(可选)} ...]（逐段车票，含真实票价与退票费）
    分组键 = (归一化出发地, 归一化到达地, 日期)：同组金额相加（跨出差人、票价+退票费一并合并）。
    other_fees = {住宿费,餐食补贴,会议费,其他费用}（可选，trip 级别、非路线维度），只写在返回结果第一行，其余行留0。
    返回按 (日期, 首次出现顺序) 排序的 rows，兼容 fill_travel_reimbursement 的 rows 参数。
    """
    if not records:
        raise ValueError("records 不能为空")

    other_fees = other_fees or {}
    fee_keys = ("住宿费", "餐食补贴", "会议费", "其他费用")

    groups = {}
    order = []
    for rec in records:
        date = rec["日期"]
        origin = rec["出发地"]
        dest = rec["到达地"]
        key = (_normalize_station(origin), _normalize_station(dest), date)
        if key not in groups:
            groups[key] = {
                "日期": date,
                "起讫地点": f"{origin}-{dest}",
                "城市间交通费": 0.0,
            }
            order.append(key)
        groups[key]["城市间交通费"] += float(rec["金额"])

    first_seen = {key: i for i, key in enumerate(order)}
    order.sort(key=lambda k: (groups[k]["日期"], first_seen[k]))

    rows = []
    for i, key in enumerate(order):
        row = dict(groups[key])
        row["城市间交通费"] = round(row["城市间交通费"], 2)
        for k in fee_keys:
            row[k] = other_fees.get(k, 0) if i == 0 else 0
        rows.append(row)
    return rows
