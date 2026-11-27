"""Settings: the skill's default file, deep-merged with an optional per-report override.

The result is inlined into the Report as `<script type="application/json" id="jc-settings">`.
"""
from __future__ import annotations

import json
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
DEFAULTS = SKILL / "assets" / "settings.default.json"


OVERRIDE_NAME = "settings.json"   # placed next to report.src.html


def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = deep_merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


class SettingsError(Exception):
    def __init__(self, reasons: list[str]):
        super().__init__("\n".join(reasons))
        self.reasons = reasons


THEMES = ("white", "black", "beige")
CHART_KEYS = ("parchment", "near_black", "charcoal", "olive", "stone", "light_stone", "mist",
              "brand", "brand_tint", "grid")


def _any(path, v):
    return []


def _theme(path, v):
    return [] if v in THEMES else [f"非法主题名 {path} = {v!r}（可选：{' / '.join(THEMES)}）"]


def _margin(path, v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
        return [f"页边距必须是非负数（毫米） {path} = {v!r}"]
    return []


SCHEMA = {
    "defaultTheme": _theme,
    "pagination": {"enabled": _any},
    "paper": {"size": _any, "marginMm": {side: _margin for side in ("top", "right", "bottom", "left")}},
    "chrome": {"headerTemplate": _any, "footerTemplate": _any},
    "toc": {"pageNumbers": _any},
    "print": {"palette": _theme},
    "themes": {t: {"chart": {k: _any for k in CHART_KEYS}} for t in THEMES},
}


def _check(schema: dict, value: dict, path: str) -> list[str]:
    errors = []
    for k in value:
        if k not in schema:
            errors.append(f"未知键 {path}{k}")
    for k, rule in schema.items():
        if k not in value:
            continue
        if isinstance(rule, dict):
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
        settings = deep_merge(settings, json.loads(override.read_text(encoding="utf-8")))
    validate(settings)
    return settings


def settings_block(settings: dict) -> str:
    data = json.dumps(settings, ensure_ascii=False, indent=1).replace("</", "<\\/")
    return f'<script type="application/json" id="jc-settings">{data}</script>\n'
