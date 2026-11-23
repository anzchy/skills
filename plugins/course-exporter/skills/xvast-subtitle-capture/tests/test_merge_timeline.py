import json
import subprocess
import sys

from conftest import SCRIPTS


def ocr_row(source, pieces):
    """pieces: [(text, box height)] all inside the subtitle band, as paddleocr-subtitles reports them."""
    return {"source": source, "ok": True, "ocr_model": "PP-OCRv5_mobile",
            "texts": [t for t, _ in pieces], "scores": [0.95] * len(pieces),
            "boxes": [[0, 10, 50, 10 + h] for _, h in pieces],
            "subtitle_texts": [t for t, _ in pieces], "subtitle_scores": [0.95] * len(pieces)}


def merge(tmp_path, rows, *extra):
    index = tmp_path / "index.jsonl"
    index.write_text("".join(json.dumps({"source": r["source"], "video_ms": i * 500}) + "\n"
                             for i, r in enumerate(rows)), encoding="utf-8")
    ocr = tmp_path / "mobile.jsonl"
    ocr.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    out = tmp_path / "events.jsonl"
    proc = subprocess.run([sys.executable, str(SCRIPTS / "merge_paddleocr_timeline.py"), "--frame-index", str(index),
                           "--ocr-results", str(ocr), "--output-jsonl", str(out),
                           "--output-markdown", str(tmp_path / "events.md"), *extra], capture_output=True, text=True)
    events = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()] if out.exists() else []
    return proc, events


def frames(tmp_path):
    return [ocr_row(str(tmp_path / "f1.jpg"), [("辅助功能：调查", 19), ("字幕甲", 42), ("Q搜索", 21)]),
            ocr_row(str(tmp_path / "f2.jpg"), [("字幕甲", 42), ("Q搜索", 21)]),
            ocr_row(str(tmp_path / "f3.jpg"), [("Q搜索", 21)]),
            ocr_row(str(tmp_path / "f4.jpg"), [("字幕乙", 41)])]


def test_min_text_height_keeps_only_tall_subtitle_text(tmp_path):
    proc, events = merge(tmp_path, frames(tmp_path), "--min-text-height", "30")

    assert proc.returncode == 0, proc.stderr
    assert [e["text"] for e in events] == ["字幕甲", "字幕乙"]
    assert events[0]["end_ms"] == 500  # the two frames differ only in interface text, so they are one event


def test_without_min_text_height_every_band_text_is_kept(tmp_path):
    proc, events = merge(tmp_path, frames(tmp_path))

    assert proc.returncode == 0, proc.stderr
    assert events[0]["text"] == "辅助功能：调查字幕甲Q搜索"
