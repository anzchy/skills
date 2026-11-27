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


def load_settings(src_dir: Path) -> dict:
    settings = json.loads(DEFAULTS.read_text(encoding="utf-8"))
    override = src_dir / OVERRIDE_NAME
    if override.is_file():
        settings = deep_merge(settings, json.loads(override.read_text(encoding="utf-8")))
    return settings


def settings_block(settings: dict) -> str:
    data = json.dumps(settings, ensure_ascii=False, indent=1).replace("</", "<\\/")
    return f'<script type="application/json" id="jc-settings">{data}</script>\n'
