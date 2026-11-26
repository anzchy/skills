#!/usr/bin/env python3
"""从《周计划-持续记录》复制件里按日期抽取当日日程原文，供市内交通报销的
「事由」草稿比对用（不做语义匹配，只做确定性的读取）。

**只读源文件**：源文件本身从不打开写入，一律先 `shutil.copy2` 到临时目录，
再对副本调用 openpyxl 读取；读完删除临时目录。

Sheet 定位：按名字包含「周计划」模糊匹配（不同年份/版本的 sheet 名可能带
空格，如「2026 年周计划」），避免因空格/年份写死而找不到。

每行日程结构固定：A=日期 B=星期 D=上午 E=下午 F=晚上（与
`~/Desktop/周计划-持续记录.xlsx` 的既有格式一致）。

依赖：openpyxl。
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime

DEFAULT_SOURCE = os.path.expanduser("~/Desktop/周计划-持续记录.xlsx")


def copy_to_temp(source_path: str) -> str:
    """把源文件复制到临时目录，返回副本路径。源文件不会被打开写入。"""
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"未找到周计划文件：{source_path}")
    tmp_dir = tempfile.mkdtemp(prefix="weekly_plan_")
    tmp_path = os.path.join(tmp_dir, os.path.basename(source_path))
    shutil.copy2(source_path, tmp_path)
    return tmp_path


def _find_plan_sheet(wb):
    for name in wb.sheetnames:
        if "周计划" in name:
            return wb[name]
    raise ValueError(f"未找到名字含「周计划」的 sheet，现有 sheet：{wb.sheetnames}")


def extract_days(dates: list, source_path: str = DEFAULT_SOURCE) -> dict:
    """按 dates（'YYYY-MM-DD' 字符串列表）抽取当天上午/下午/晚上原文。

    返回 {日期: {"weekday", "上午", "下午", "晚上"} | None}；
    源文件里没有该日期的行时值为 None。
    """
    import openpyxl

    tmp_path = copy_to_temp(source_path)
    try:
        wb = openpyxl.load_workbook(tmp_path, data_only=True)
        ws = _find_plan_sheet(wb)

        targets = {datetime.strptime(d, "%Y-%m-%d").date(): d for d in dates}
        out = {d: None for d in dates}
        for row in ws.iter_rows(min_row=2):
            a = row[0].value
            if not isinstance(a, datetime):
                continue
            key = targets.get(a.date())
            if key is None:
                continue
            out[key] = {
                "weekday": row[1].value if len(row) > 1 else None,
                "上午": row[3].value if len(row) > 3 else None,
                "下午": row[4].value if len(row) > 4 else None,
                "晚上": row[5].value if len(row) > 5 else None,
            }
        return out
    finally:
        shutil.rmtree(os.path.dirname(tmp_path), ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(
        description="从周计划文件的只读复制件中，按日期抽取当日上午/下午/晚上日程原文"
    )
    ap.add_argument("dates", nargs="+", help="日期，YYYY-MM-DD，可传多个")
    ap.add_argument(
        "--source", default=DEFAULT_SOURCE,
        help=f"周计划源文件路径（只读，默认 {DEFAULT_SOURCE}）",
    )
    args = ap.parse_args()
    try:
        result = extract_days(args.dates, args.source)
    except (FileNotFoundError, ValueError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
