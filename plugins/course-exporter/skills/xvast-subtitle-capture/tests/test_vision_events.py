import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image

from conftest import SCRIPTS, write_json

STUB = Path(__file__).resolve().parent / "stub_vision.py"


def row(text, x, h):
    return {"text": text, "confidence": 0.9, "x": x, "y": 0.1, "w": 0.2, "h": h}


def make_events(tmp_path, ids):
    rows = []
    for index, event_id in enumerate(ids, 1):
        frame = tmp_path / f"{event_id}.jpg"
        Image.new("RGB", (40, 20), "white").save(frame)
        rows.append({"id": event_id, "start_ms": index * 1000, "end_ms": index * 1000 + 800,
                     "mobile": "m", "server": "s", "agree": True, "frame": str(frame)})
    path = tmp_path / "event-server.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path


def run_vision(tmp_path, events, answers, out_name="event-vision.jsonl"):
    amap = write_json(tmp_path / "answers.json", answers)
    out = tmp_path / out_name
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "vision_events.py"), "--events", str(events),
         "--output", str(out), "--work-dir", str(tmp_path / "work"), "--crop", "0,0,30,15",
         "--vision-command", f"{sys.executable} {STUB}"],
        capture_output=True, text=True, env={**os.environ, "STUB_VISION_MAP": str(amap)})
    return proc, out


def read(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def test_keeps_subtitle_height_rows_in_left_to_right_order(tmp_path):
    events = make_events(tmp_path, ["ocr-000001"])
    answers = {"ocr-000001": {"rows": [row("我们", 0.6, 0.10), row("开始吧", 0.2, 0.09), row("0.35", 0.1, 0.02)]}}
    proc, out = run_vision(tmp_path, events, answers)
    assert proc.returncode == 0, proc.stderr
    (item,) = read(out)
    assert item["id"] == "ocr-000001"
    assert item["vision"] == "开始吧我们"          # the small chart label is dropped, rows sorted by x
    assert item["vision_all"] == "0.35开始吧我们"  # but kept in the full reading
    assert item["vision_error"] is None


def test_records_an_error_without_inventing_text(tmp_path):
    events = make_events(tmp_path, ["ocr-000001", "ocr-000002"])
    answers = {"ocr-000001": {"rows": [], "ok": False, "error": "Cannot decode input image"},
               "ocr-000002": {"rows": [row("好的", 0.3, 0.1)]}}
    proc, out = run_vision(tmp_path, events, answers)
    assert proc.returncode == 0, proc.stderr
    first, second = read(out)
    assert first["vision"] is None and first["vision_error"] == "Cannot decode input image"
    assert second["vision"] == "好的"


def test_empty_reading_is_an_empty_string(tmp_path):
    events = make_events(tmp_path, ["ocr-000001"])
    proc, out = run_vision(tmp_path, events, {})
    assert proc.returncode == 0, proc.stderr
    (item,) = read(out)
    assert item["vision"] == "" and item["vision_all"] == ""


def test_refuses_to_overwrite_existing_output(tmp_path):
    events = make_events(tmp_path, ["ocr-000001"])
    (tmp_path / "event-vision.jsonl").write_text("keep\n", encoding="utf-8")
    proc, out = run_vision(tmp_path, events, {})
    assert proc.returncode != 0
    assert out.read_text(encoding="utf-8") == "keep\n"
    assert "exists" in proc.stderr or "overwrite" in proc.stderr


def test_vision_ocr_source_still_parses():
    import shutil
    import pytest
    if shutil.which("clang") is None or sys.platform != "darwin":
        pytest.skip("needs clang on macOS")
    proc = subprocess.run(["clang", "-fobjc-arc", "-fsyntax-only", "-Wno-deprecated-declarations",
                           str(SCRIPTS / "vision_ocr.m")], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
