#!/usr/bin/env python3
"""scan_materials() 单测（TDD，红→绿）。
先用临时目录覆盖各条文件名关键词规则，再拿真实的 `句容出差/` 目录跑一遍回归。
用 python3.11 跑。
"""
import os, sys, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from scan_reimbursement_materials import scan_materials

failed = 0


def check(name, got, expect):
    global failed
    if got != expect:
        failed += 1
        print(f"FAIL {name}: got {got!r} expect {expect!r}")
    else:
        print(f"ok   {name} -> {got}")


def touch(dir_path: str, name: str):
    with open(os.path.join(dir_path, name), "w") as f:
        f.write("x")


# ---- 造一个覆盖各类规则的临时目录 ----
tmp = tempfile.mkdtemp()
names = [
    "张三-上海虹桥站-句容站-147 元.pdf",  # 含「站」+ .pdf → 火车票发票
    "G7371 车次电子客票.pdf",  # 车次号 G\d+ → 火车票发票
    "高铁票-回程.pdf",  # 含「高铁」→ 火车票发票
    "滴滴出行行程报销单.pdf",  # 含「行程单/滴滴」→ 网约车行程单
    "曹操出行-行程单.pdf",  # 网约车行程单
    "T3出行电子发票.pdf",  # 含「T3」→ 网约车行程单
    "支付截图.docx",  # 含「支付截图」→ 支付截图
    "IMG_3083.PNG",  # 图片但无关键词 → 其他(需人工确认)
    "01费用报销单-句容出差.xlsx",  # 表单 → 其他
    "句容出差报告.docx",  # 报告 → 其他
]
for n in names:
    touch(tmp, n)
os.mkdir(os.path.join(tmp, "子目录"))
touch(os.path.join(tmp, "子目录"), "子目录里的-上海虹桥站-句容站.pdf")

rows = scan_materials(tmp)
by_file = {r["file"]: r for r in rows}

check("返回条数=目录内文件数(不递归子目录)", len(rows), len(names))
check("不包含子目录内的文件", "子目录里的-上海虹桥站-句容站.pdf" in by_file, False)
check("不把子目录本身当文件", "子目录" in by_file, False)
check("每条含 file/category/reason 三个键", sorted(rows[0].keys()), ["category", "file", "reason"])

check("含「站」的PDF→火车票发票", by_file["张三-上海虹桥站-句容站-147 元.pdf"]["category"], "火车票发票")
check("车次号G\\d+→火车票发票", by_file["G7371 车次电子客票.pdf"]["category"], "火车票发票")
check("含「高铁」→火车票发票", by_file["高铁票-回程.pdf"]["category"], "火车票发票")
check("含「滴滴/行程报销单」→网约车行程单", by_file["滴滴出行行程报销单.pdf"]["category"], "网约车行程单")
check("含「曹操/行程单」→网约车行程单", by_file["曹操出行-行程单.pdf"]["category"], "网约车行程单")
check("含「T3」→网约车行程单", by_file["T3出行电子发票.pdf"]["category"], "网约车行程单")
check("含「支付截图」→支付截图", by_file["支付截图.docx"]["category"], "支付截图")

img = by_file["IMG_3083.PNG"]
check("无关键词图片→其他", img["category"], "其他")
check("无关键词图片 reason 提示人工确认", "需人工确认" in img["reason"], True)

xlsx = by_file["01费用报销单-句容出差.xlsx"]
check("xlsx表单→其他", xlsx["category"], "其他")
check("xlsx reason 注明非截图类素材", "非截图类素材" in xlsx["reason"], True)

rpt = by_file["句容出差报告.docx"]
check("出差报告docx→其他", rpt["category"], "其他")
check("报告 reason 注明非截图类素材", "非截图类素材" in rpt["reason"], True)

check("每条 reason 非空", all(r["reason"].strip() for r in rows), True)

# ---- 真实目录回归：句容出差/ 的 12 张火车票 PDF ----
real_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "句容出差")
)
if os.path.isdir(real_dir):
    real_rows = scan_materials(real_dir)
    real_by_file = {r["file"]: r for r in real_rows}
    pdfs = [r for r in real_rows if r["file"].lower().endswith(".pdf")]
    check("句容出差/ 有12张PDF发票", len(pdfs), 12)
    check("12张PDF全部分类为火车票发票", {r["category"] for r in pdfs}, {"火车票发票"})

    check("句容出差报告.docx→其他", real_by_file["句容出差报告.docx"]["category"], "其他")
    check(
        "句容出差报告.docx reason 注明非截图类素材",
        "非截图类素材" in real_by_file["句容出差报告.docx"]["reason"],
        True,
    )
    for x in ["03出差费用报销单-句容出差.xlsx", "2026年8月报销-句容出差-出差申请单.xlsx"]:
        check(f"{x}→其他", real_by_file[x]["category"], "其他")
        check(f"{x} reason 注明非截图类素材", "非截图类素材" in real_by_file[x]["reason"], True)
    check("忽略 .DS_Store 等隐藏文件", any(r["file"].startswith(".") for r in real_rows), False)
    check("忽略 ~$ 开头的 Word 临时锁文件", any(r["file"].startswith("~$") for r in real_rows), False)
else:
    print(f"skip 真实目录回归（未找到 {real_dir}）")

print(f"\n{'ALL PASS' if not failed else str(failed) + ' FAILED'}")
sys.exit(1 if failed else 0)
