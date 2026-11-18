#!/usr/bin/env python3
"""解析滴滴 / 曹操「行程报销单」PDF -> 结构化行程列表（D1 结构化路径）。

仅解析平台导出的标准行程单（字段规整）。机票/酒店/餐饮等非结构化发票
由 Claude 阅读，不走本脚本。

输出每条行程：
  {serial, car_type, date(YYYY-MM-DD), time, city, start, end, distance, amount, platform}
并返回 reported_total（行程单自报「合计X元」）供交叉核对。

依赖：PyMuPDF(fitz)。
"""
import re
import sys
import json

DATE_RE = re.compile(r"^(\d{2})-(\d{2})\s+(\d{2}:\d{2})")
AMOUNT_RE = re.compile(r"^\d+(\.\d+)?$")
TOTAL_RE = re.compile(r"共\s*(\d+)\s*笔行程[，,]\s*合计\s*([\d.]+)\s*元")
RANGE_RE = re.compile(r"行程起止日期[：:]\s*(\d{4})-(\d{2})-(\d{2})")
APPLY_RE = re.compile(r"申请日期[：:]\s*(\d{4})-(\d{2})-(\d{2})")


def detect_platform(text: str) -> str:
    if "曹操出行" in text:
        return "曹操出行"
    if "滴滴" in text:
        return "滴滴出行"
    return "未知平台"


def _year_for(text: str) -> int:
    m = RANGE_RE.search(text) or APPLY_RE.search(text)
    return int(m.group(1)) if m else None


def parse_trip_report(path: str) -> dict:
    import fitz
    doc = fitz.open(path)
    text = "\n".join(p.get_text() for p in doc)
    platform = detect_platform(text)
    year = _year_for(text)
    mt = TOTAL_RE.search(text)
    reported_count = int(mt.group(1)) if mt else None
    reported_total = float(mt.group(2)) if mt else None

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    trips = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        # 行程行起点：纯数字序号，后跟 车型 与 日期时间
        if ln.isdigit() and i + 7 < len(lines) and DATE_RE.match(lines[i + 2]):
            serial = int(ln)
            car_type = lines[i + 1]
            dm = DATE_RE.match(lines[i + 2])
            mm, dd, hhmm = dm.group(1), dm.group(2), dm.group(3)
            city = lines[i + 3]
            start = lines[i + 4]
            end = lines[i + 5]
            distance = lines[i + 6]
            amount = lines[i + 7]
            if AMOUNT_RE.match(amount):
                date = f"{year}-{mm}-{dd}" if year else f"{mm}-{dd}"
                trips.append({
                    "serial": serial,
                    "car_type": car_type,
                    "date": date,
                    "time": hhmm,
                    "city": city,
                    "start": start,
                    "end": end,
                    "distance": float(distance) if re.match(r"^\d+(\.\d+)?$", distance) else distance,
                    "amount": float(amount),
                    "platform": platform,
                })
                i += 8
                continue
        i += 1

    parsed_total = round(sum(t["amount"] for t in trips), 2)
    return {
        "platform": platform,
        "year": year,
        "reported_count": reported_count,
        "reported_total": reported_total,
        "parsed_count": len(trips),
        "parsed_total": parsed_total,
        # 交叉核对：解析金额合计 vs 行程单自报合计（容差 0.01）
        "total_match": (reported_total is not None
                        and abs(parsed_total - reported_total) < 0.011),
        "trips": trips,
    }


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(json.dumps(parse_trip_report(p), ensure_ascii=False, indent=2))
