#!/usr/bin/env python3
"""附件预检（Preflight）—— 报销前先确认材料是否齐全，否则不进入处理。

不同报销类型所需附件不同：
  ① 市内交通 transport   : 行程报销单 + 对应电子发票（按平台配对）
  ② 出差     travel       : 城市间交通票 + 出差报告 + 出差申请单
                            （含住宿则需住宿发票；含市内接驳则需行程单+电子发票）
  ③ 招待     entertainment: 餐饮发票 + 支付截图/付款记录 + 业务招待备案表

用法：
  python3 preflight.py <category|auto> <dir>
退出码：0=READY，2=BLOCK（缺关键附件），3=用法错误。

注意：本脚本仅按文件名/扩展名做轻量分类，给出「缺什么」清单；
最终是否齐全由 Claude 结合实际内容确认。它是「闸门」不是「裁判」。
"""
import os
import sys
import json

CATEGORIES = {"transport", "travel", "entertainment"}


def classify(files):
    """按文件名关键词把目录文件归到附件桶。返回 {bucket: [files]}。"""
    b = {
        "trip_report": [],   # 网约车行程报销单
        "e_invoice": [],     # 电子发票（网约车/餐饮/住宿等通用「发票」pdf）
        "intercity": [],     # 城市间交通票（高铁/机票行程单）
        "hotel": [],         # 住宿发票
        "dining": [],        # 餐饮发票
        "payment": [],       # 支付截图/付款记录
        "travel_report": [], # 出差报告
        "travel_app": [],    # 出差申请单
        "record_form": [],   # 业务招待备案表
        "itinerary": [],     # 行程单.docx
        "other": [],
    }
    for f in files:
        n = f
        low = f.lower()
        ext = os.path.splitext(low)[1]
        if n.startswith("~$") or n == ".DS_Store":
            continue
        if "行程报销单" in n:
            b["trip_report"].append(f)
        elif "出差报告" in n:
            b["travel_report"].append(f)
        elif "出差申请单" in n:
            b["travel_app"].append(f)
        elif "备案表" in n:
            b["record_form"].append(f)
        elif "住宿" in n or "酒店" in n:
            b["hotel"].append(f)
        elif "行程单" in n and ext in (".docx", ".doc"):
            b["itinerary"].append(f)
        elif ("支付" in n or "截图" in n or "付款" in n) or (ext in (".png", ".jpg", ".jpeg") and ("img" in low or "scr" in low)):
            b["payment"].append(f)
        elif ext == ".pdf" and "发票" not in n and "报销单" not in n and (
                ("-" in n and ("站" in n or any(c in n for c in ["北京", "上海", "苏州", "园区"])))
                or "机票" in n or "客票" in n):
            # 城市间交通票常见命名：日期-人名-城市-城市.pdf（排除「发票/报销单」）
            b["intercity"].append(f)
        elif "发票" in n and ext == ".pdf":
            if "餐" in n or "咖啡" in n or "午餐" in n or "晚餐" in n:
                b["dining"].append(f)
            else:
                b["e_invoice"].append(f)
        elif ext == ".pdf" and ("咖啡" in n or "餐" in n):
            b["dining"].append(f)
        else:
            b["other"].append(f)
    return b


def _has(b, *keys):
    return any(b[k] for k in keys)


def check_transport(b):
    missing = []
    if not b["trip_report"]:
        missing.append("行程报销单 PDF（滴滴/曹操等网约车平台导出）")
    if not (b["e_invoice"] or b["dining"]):
        missing.append("对应电子发票 PDF（与行程报销单配对，用于报销/抵扣）")
    warn = []
    if b["trip_report"] and not b["e_invoice"]:
        warn.append("检测到行程报销单但未见电子发票，请确认每个平台都附了发票。")
    return missing, warn


def check_travel(b):
    missing = []
    if not b["intercity"]:
        missing.append("城市间交通票据 PDF（高铁/机票电子客票行程单）")
    if not b["travel_report"]:
        missing.append("出差报告（docx，需本人签字）")
    if not b["travel_app"]:
        missing.append("出差申请单（须经批准，日期早于报销日≥2天）")
    warn = []
    if not b["hotel"]:
        warn.append("未见住宿发票——如本次出差含住宿，需附住宿发票（显示起止时间、单价）。")
    if b["trip_report"] and not (b["e_invoice"]):
        warn.append("有市内接驳行程报销单但未见对应电子发票。")
    return missing, warn


def check_entertainment(b):
    missing = []
    if not (b["dining"] or b["e_invoice"]):
        missing.append("餐饮发票 PDF")
    if not b["payment"]:
        missing.append("支付截图/付款记录（docx 或图片）")
    if not b["record_form"]:
        missing.append("业务招待备案表（须提前向审批负责人申请、经批准）")
    return missing, []


CHECKS = {
    "transport": check_transport,
    "travel": check_travel,
    "entertainment": check_entertainment,
}

CAT_CN = {"transport": "市内交通", "travel": "出差", "entertainment": "招待"}


def auto_detect(b):
    """无法确定类别时，按桶内容猜测最可能的类别（强信号优先）。"""
    if b["record_form"] or b["dining"]:        # 备案表/餐饮发票 -> 招待
        return "entertainment"
    if b["travel_app"] or b["travel_report"] or b["intercity"] or b["hotel"]:
        return "travel"                          # 申请单/报告/城际票/住宿 -> 出差
    if b["trip_report"]:                         # 仅网约车行程单 -> 市内交通
        return "transport"
    if b["payment"]:                             # 仅支付截图 -> 招待兜底
        return "entertainment"
    return None


def preflight(category, directory):
    files = os.listdir(directory)
    b = classify(files)
    if category == "auto":
        category = auto_detect(b)
        if not category:
            return {"ready": False, "category": None,
                    "blockers": ["无法自动判定报销类别，请指定 transport/travel/entertainment"],
                    "warnings": [], "buckets": {k: v for k, v in b.items() if v}}
    missing, warn = CHECKS[category](b)
    return {
        "ready": not missing,
        "category": category,
        "category_cn": CAT_CN[category],
        "blockers": missing,
        "warnings": warn,
        "buckets": {k: v for k, v in b.items() if v},
    }


def render(res):
    lines = []
    cat = res.get("category_cn") or res.get("category") or "未知"
    lines.append(f"【附件预检】类别：{cat}  ——  {'✅ 材料齐全，可处理' if res['ready'] else '⛔ 缺关键附件，暂不处理'}")
    if res["blockers"]:
        lines.append("缺少（必须补齐后才能继续）：")
        for m in res["blockers"]:
            lines.append(f"  ✗ {m}")
    if res["warnings"]:
        lines.append("提醒（请确认）：")
        for w in res["warnings"]:
            lines.append(f"  ⚠ {w}")
    if res["buckets"]:
        lines.append("已识别附件：")
        for k, v in res["buckets"].items():
            lines.append(f"  · {k}: {len(v)} 个")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python3 preflight.py <transport|travel|entertainment|auto> <dir>")
        sys.exit(3)
    cat, d = sys.argv[1], sys.argv[2]
    res = preflight(cat, d)
    print(render(res))
    print("\nJSON:", json.dumps(res, ensure_ascii=False))
    sys.exit(0 if res["ready"] else 2)
