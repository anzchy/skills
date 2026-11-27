"""Settings: the skill's default file, deep-merged with an optional per-report override.

The result is inlined into the Report as `<script type="application/json" id="jc-settings">`.
"""
from __future__ import annotations

import json
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
DEFAULTS = SKILL / "assets" / "settings.default.json"


def load_settings(src_dir: Path) -> dict:
    return json.loads(DEFAULTS.read_text(encoding="utf-8"))


def settings_block(settings: dict) -> str:
    data = json.dumps(settings, ensure_ascii=False, indent=1).replace("</", "<\\/")
    return f'<script type="application/json" id="jc-settings">{data}</script>\n'
