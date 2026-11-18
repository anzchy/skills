#!/usr/bin/env python3
"""人民币金额转中文大写（确定性脚本，禁止 LLM 手算）。

输出口径与黄金样例一致：
  177.64  -> 壹佰柒拾柒元陆角肆分
  4109.07 -> 肆仟壹佰零玖元零柒分
  442.00  -> 肆佰肆拾贰元整

规则（参照 GB/T 通行写法）：
- 数字：零壹贰叁肆伍陆柒捌玖
- 整数单位：个十百千 / 万 / 亿（四位一节）
- 角、分用于小数两位；元后无角分写「整」。
- 连续零折叠为单个「零」，节末不带多余「零」。
- 角位为零、分位非零时写「零X分」（见 4109.07）。
"""
from decimal import Decimal, ROUND_HALF_UP

DIGITS = "零壹贰叁肆伍陆柒捌玖"
# 每位的单位：个、十、百、千
UNIT_SMALL = ["", "拾", "佰", "仟"]
# 每节（4位）的单位：节0、万、亿、万亿
UNIT_BIG = ["", "万", "亿", "兆"]


def _section_to_cn(section: int) -> str:
    """把 0..9999 的一节转中文，内部零折叠，不处理节末尾零。"""
    s = ""
    zero_pending = False
    started = False
    for pos in range(3, -1, -1):  # 千 百 十 个
        digit = (section // (10 ** pos)) % 10
        if digit == 0:
            if started:
                zero_pending = True
        else:
            if zero_pending:
                s += DIGITS[0]
                zero_pending = False
            s += DIGITS[digit] + UNIT_SMALL[pos]
            started = True
    return s


def _integer_to_cn(n: int) -> str:
    """整数部分（元）转中文大写，不含「元」。"""
    if n == 0:
        return DIGITS[0]
    sections = []
    while n > 0:
        sections.append(n % 10000)
        n //= 10000
    # sections[0] 是最低节
    parts = []
    for idx in range(len(sections) - 1, -1, -1):
        sec = sections[idx]
        sec_cn = _section_to_cn(sec)
        if sec == 0:
            # 整节为零：折叠零，由上层节间补零
            continue
        # 若本节高位不足4位且不是最高节，需要前导零（如 1_0009 -> 壹万零玖）
        if idx < len(sections) - 1 and sec < 1000:
            sec_cn = DIGITS[0] + sec_cn
        parts.append(sec_cn + UNIT_BIG[idx])
    result = "".join(parts)
    return result


def rmb_capitalize(amount) -> str:
    """金额（数字/字符串/Decimal）-> 人民币中文大写字符串。"""
    amt = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amt < 0:
        return "负" + rmb_capitalize(-amt)
    yuan = int(amt)
    cents = int((amt - yuan) * 100)  # 0..99
    jiao = cents // 10
    fen = cents % 10

    yuan_cn = _integer_to_cn(yuan)
    out = yuan_cn + "元"

    # 公司口径（据黄金样例）：仅「整元」用「整」；只要有角/分，就写满角分两位，
    # 零位用「零」占位。
    #   442.00  -> 元整
    #   230.50  -> 伍角零分   （角非零、分为零：写「零分」，不写「整」）
    #   4109.07 -> 零柒分     （角为零：写单个「零」，不写「零角」）
    #   177.64  -> 陆角肆分
    if jiao == 0 and fen == 0:
        return out + "整"

    if jiao == 0:
        # 角为零、分非零：元后补单个「零」再写分（4109.07 -> ...元零柒分）
        return out + DIGITS[0] + DIGITS[fen] + "分"

    out += DIGITS[jiao] + "角"
    # 角非零：分位为零写「零分」，非零写「X分」（230.50 -> 伍角零分）
    out += (DIGITS[fen] + "分") if fen > 0 else "零分"
    return out


if __name__ == "__main__":
    import sys
    for a in sys.argv[1:]:
        print(a, "->", rmb_capitalize(a))
