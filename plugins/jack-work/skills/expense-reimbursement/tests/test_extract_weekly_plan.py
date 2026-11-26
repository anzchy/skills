#!/usr/bin/env python3
"""extract_days() 单测。造一个临时「周计划」xlsx 当源文件，验证：
1. 能按日期取到 上午/下午/晚上 原文；
2. sheet 名字带空格（如「2026 年周计划」）也能模糊匹配到；
3. 源文件内容/mtime 读取前后不变（只读复制件，绝不编辑原文件）。
用 python3.11 跑。
"""
import os, sys, tempfile, shutil, hashlib
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from extract_weekly_plan import extract_days

failed = 0


def check(name, got, expect):
    global failed
    if got != expect:
        failed += 1
        print(f"FAIL {name}: got {got!r} expect {expect!r}")
    else:
        print(f"ok   {name} -> {got}")


def file_md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


# ---- 造一个临时源文件，sheet 名带空格模拟真实文件 ----
import openpyxl

tmp_dir = tempfile.mkdtemp()
source_path = os.path.join(tmp_dir, "周计划-持续记录.xlsx")
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "2026 年周计划"
ws.append([datetime(2026, 1, 1), None, "示例部门工作", "上午", "下午", "晚上"])
ws.append([datetime(2026, 7, 6), "一", None, None, "13:30 对接宝利国际", None])
ws.append([datetime(2026, 7, 9), "四", None, "山东未来机器人报告汇报讨论", "拜访盛盎资本", None])
wb.save(source_path)

before_md5 = file_md5(source_path)
before_mtime = os.path.getmtime(source_path)

result = extract_days(["2026-07-06", "2026-07-09", "2026-07-31"], source_path=source_path)

check("2026-07-06 下午", result["2026-07-06"]["下午"], "13:30 对接宝利国际")
check("2026-07-06 上午为空", result["2026-07-06"]["上午"], None)
check("2026-07-09 上午", result["2026-07-09"]["上午"], "山东未来机器人报告汇报讨论")
check("2026-07-09 下午", result["2026-07-09"]["下午"], "拜访盛盎资本")
check("2026-07-31 无记录", result["2026-07-31"], None)

check("源文件 md5 未变", file_md5(source_path), before_md5)
check("源文件 mtime 未变", os.path.getmtime(source_path), before_mtime)

shutil.rmtree(tmp_dir, ignore_errors=True)

if failed:
    print(f"\n{failed} 项失败")
    sys.exit(1)
print("\n全部通过")
