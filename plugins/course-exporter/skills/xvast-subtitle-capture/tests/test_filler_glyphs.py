import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from conftest import SCRIPTS, write_json

SCRIPT = SCRIPTS / "filler_glyphs.py"


def glyph(draw, x, kind):
    """Draw a 30x30 white synthetic glyph at x (y fixed at 20) on a dark strip."""
    draw.rectangle((x, 20, x + 29, 49), outline="white", width=3)
    if kind == "e":   # 'e' glyph: horizontal bar
        draw.rectangle((x + 6, 32, x + 23, 37), fill="white")
    else:             # 'n' glyph: vertical bar
        draw.rectangle((x + 12, 26, x + 17, 43), fill="white")


def frame(path, kinds):
    im = Image.new("RGB", (400, 70), (40, 40, 40))
    d = ImageDraw.Draw(im)
    for i, kind in enumerate(kinds):
        if kind != " ":
            glyph(d, 20 + i * 45, kind)
    im.save(path)
    return str(path)


def make_events(tmp_path, events):
    """events: {id: kinds}. The first event's frame also provides the templates."""
    tpl = frame(tmp_path / "tpl.png", "en")
    rows = [{"id": eid, "frame": frame(tmp_path / f"{eid}.png", kinds)} for eid, kinds in events.items()]
    path = tmp_path / "events.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path, tpl


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def detect(tmp_path, events):
    path, tpl = make_events(tmp_path, events)
    out = tmp_path / "detections.jsonl"
    proc = run("detect", "--events", path, "--output", out, "--band", "0,10,400,60",
               "--template", f"呃={tpl}:18,18,52,52", "--template", f"呢={tpl}:63,18,97,52")
    assert proc.returncode == 0, proc.stderr
    return {r["id"]: r for r in map(json.loads, out.read_text(encoding="utf-8").splitlines())}


def test_detect_labels_filler_glyphs_left_to_right(tmp_path):
    found = detect(tmp_path, {"a": "n e", "b": "   ", "c": "ee"})
    assert found["a"]["fillers"] == "呢呃"
    assert found["b"]["fillers"] == ""
    assert found["c"]["fillers"] == "呃呃"


def test_apply_fixes_reader_fillers_and_reports_count_mismatches(tmp_path):
    detections = tmp_path / "detections.jsonl"
    detections.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in [
        {"id": "ocr-1", "fillers": "呃"}, {"id": "ocr-2", "fillers": "呃"},
        {"id": "ocr-3", "fillers": ""}, {"id": "ocr-4", "fillers": ""}]), encoding="utf-8")
    cands = tmp_path / "candidates.txt"
    cands.write_text("1 ocr-1 我们呢好\n2 ocr-2 呢呃\n3 ocr-3 无\n4 ocr-4 好的\n", encoding="utf-8")
    reads = write_json(tmp_path / "reader.json", {"items": [
        {"n": 1, "cand": "我们呢好", "read": "我们呢好"}, {"n": 2, "cand": "呢呃", "read": "呢呃"},
        {"n": 3, "cand": "无", "read": "DROP"}, {"n": 4, "cand": "好的", "read": "好的"}]})
    out, report = tmp_path / "reader-fixed.json", tmp_path / "report.json"
    proc = run("apply", "--detections", detections, "--candidates", cands, "--reads", reads,
               "--output", out, "--report", report)
    assert proc.returncode == 0, proc.stderr
    items = {i["n"]: i["read"] for i in json.loads(out.read_text(encoding="utf-8"))["items"]}
    assert items == {1: "我们呃好", 2: "呢呃", 3: "DROP", 4: "好的"}
    rep = json.loads(report.read_text(encoding="utf-8"))
    assert [c["n"] for c in rep["changed"]] == [1]
    assert [m["n"] for m in rep["mismatch"]] == [2]
