"""Settings: the skill's default file, deep-merged with an optional per-report override.

The result is inlined into the Report as `<script type="application/json" id="jc-settings">`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
DEFAULTS = SKILL / "assets" / "settings.default.json"


OVERRIDE_NAME = "settings.json"   # placed next to report.src.html


def deep_merge(base: dict, over: dict) -> dict:
    """Override wins; nested objects merge key by key; null unsets a key."""
    out = dict(base)
    for k, v in over.items():
        if v is None:
            out.pop(k, None)
            continue
        out[k] = deep_merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


class SettingsError(Exception):
    def __init__(self, reasons: list[str]):
        super().__init__("\n".join(reasons))
        self.reasons = reasons


THEMES = ("white", "black", "beige")
CHART_KEYS = ("parchment", "near_black", "charcoal", "olive", "stone", "light_stone", "mist",
              "brand", "brand_tint", "grid")


HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


def _bool(path, v):
    return [] if isinstance(v, bool) else [f"{path} 必须是 true / false，实际 {v!r}"]


def _text(path, v):
    return [] if isinstance(v, str) and v.strip() else [f"{path} 必须是非空字符串，实际 {v!r}"]


def _footer(path, v):
    errors = _text(path, v)
    if not errors and "{page}" not in v:
        errors.append(f"{path} 必须包含 {{page}}，实际 {v!r}")
    return errors


def _paper(path, v):
    return [] if v == "A4" else [f"{path} 目前只支持 \"A4\"，实际 {v!r}"]


def _colour(path, v):
    return [] if isinstance(v, str) and HEX.fullmatch(v) else [f"{path} 必须是 #rgb 或 #rrggbb 颜色，实际 {v!r}"]


def _theme(path, v):
    return [] if v in THEMES else [f"非法主题名 {path} = {v!r}（可选：{' / '.join(THEMES)}）"]


def _margin(path, v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
        return [f"页边距必须是非负数（毫米） {path} = {v!r}"]
    return []


SCHEMA = {
    "defaultTheme": _theme,
    "pagination": {"enabled": _bool},
    "paper": {"size": _paper, "marginMm": {side: _margin for side in ("top", "right", "bottom", "left")}},
    "chrome": {"headerTemplate": _text, "footerTemplate": _footer},
    "toc": {"pageNumbers": _bool},
    "print": {"palette": _theme},
    "themes": {t: {"chart": {k: _colour for k in CHART_KEYS}} for t in THEMES},
}


def _check(schema: dict, value: dict, path: str) -> list[str]:
    errors = []
    for k in value:
        if k not in schema:
            errors.append(f"未知键 {path}{k}")
    for k, rule in schema.items():
        if k not in value:
            errors.append(f"缺少必填键 {path}{k}")
        elif isinstance(rule, dict):
            if not isinstance(value[k], dict):
                errors.append(f"{path}{k} 必须是对象（JSON object）")
                continue
            errors += _check(rule, value[k], f"{path}{k}.")
        else:
            errors += rule(f"{path}{k}", value[k])
    return errors


def validate(settings: dict) -> None:
    errors = _check(SCHEMA, settings, "")
    if errors:
        raise SettingsError(errors)


def load_settings(src_dir: Path) -> dict:
    settings = json.loads(DEFAULTS.read_text(encoding="utf-8"))
    override = src_dir / OVERRIDE_NAME
    if override.is_file():
        try:
            over = json.loads(override.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise SettingsError([f"{override.name} 不是合法 JSON：第 {e.lineno} 行第 {e.colno} 列 {e.msg}"])
        if not isinstance(over, dict):
            raise SettingsError([f"{override.name} 顶层必须是 JSON 对象"])
        settings = deep_merge(settings, over)
    validate(settings)
    return settings


def settings_block(settings: dict) -> str:
    data = json.dumps(settings, ensure_ascii=False, indent=1).replace("</", "<\\/")
    return f'<script type="application/json" id="jc-settings">{data}</script>\n'
