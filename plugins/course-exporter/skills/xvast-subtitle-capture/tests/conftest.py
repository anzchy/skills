import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def run_script(name, *args):
    """Run a skill script as a subprocess and return (returncode, parsed-json-or-None, stdout, stderr)."""
    proc = subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)],
                          capture_output=True, text=True)
    try:
        payload = json.loads(proc.stdout)
    except ValueError:
        payload = None
    return proc.returncode, payload, proc.stdout, proc.stderr


@pytest.fixture
def run():
    return run_script


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def minimal_manifest(tmp_path):
    """A manifest with no slide images, one cue, one coverage gap: enough for batch-level checks."""
    return write_json(tmp_path / "manifest.json", {
        "title": "t", "duration_ms": 10000,
        "coverage": {"capture_coverage": "complete", "cue_text_review": "visual_reviewed",
                     "word_for_word_manual_review": False, "evidence": "e", "gaps": []},
        "slides": [{"id": "p01", "title": "s"}],
        "cues": [{"id": "c1", "start_ms": 0, "end_ms": 1000, "slide_id": "p01",
                  "text": "x", "review": "verified", "evidence": "e"}]})


def batch_log(status="valid", viewport=True, **over):
    item = {"video_start_ms": 0, "video_end_ms": 60000, "wall_start_ms": 0, "wall_end_ms": 60000,
            "playback_rate": 1, "frame_count": 120, "layout_profile": "layout-003", "status": status}
    if viewport:
        item["viewport_review"] = {"four_edges_visible": True, "controls_visible": True,
                                   "scroll_state": "player_fully_in_view", "evidence": "layout.png"}
    item.update(over)
    return item
