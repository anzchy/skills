import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import SCRIPTS, write_json

STUB = Path(__file__).resolve().parent / "stub_ocr.py"


def events_file(tmp_path, texts):
    path = tmp_path / "events.jsonl"
    rows = []
    for index, text in enumerate(texts, 1):
        frames = [str(tmp_path / f"e{index}-{k}.jpg") for k in range(3)]
        rows.append({"id": f"ocr-{index:06d}", "start_ms": index * 1000, "end_ms": index * 1000 + 800,
                     "text": text, "review": "ocr_only", "evidence": frames})
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path, rows


def run_recheck(tmp_path, texts, server_answers):
    events, rows = events_file(tmp_path, texts)
    answers = {r["evidence"][1]: server_answers.get(r["id"], "") for r in rows}  # middle frame is the representative
    amap = write_json(tmp_path / "answers.json", answers)
    out = tmp_path / "server.jsonl"
    report = tmp_path / "report.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "recheck_events_with_server.py"), "--events", str(events),
         "--output-jsonl", str(out), "--output-report", str(report),
         "--ocr-command", f"{sys.executable} {STUB}"],
        capture_output=True, text=True, env={**os.environ, "STUB_OCR_MAP": str(amap)})
    return proc, out, report


def test_lists_events_whose_server_text_differs_from_mobile(tmp_path):
    proc, out, report = run_recheck(
        tmp_path, ["我们开始", "找们之前", "同学说"],
        {"ocr-000001": "我们开始", "ocr-000002": "我们之前", "ocr-000003": ""})

    assert proc.returncode == 0, proc.stderr
    summary = json.loads(report.read_text(encoding="utf-8"))
    assert summary["events"] == 3
    assert summary["agree"] == 1
    assert [d["id"] for d in summary["disagree"]] == ["ocr-000002", "ocr-000003"]
    assert summary["disagree"][0]["mobile"] == "找们之前"
    assert summary["disagree"][0]["server"] == "我们之前"
    assert summary["disagree"][1]["server"] == ""


def test_writes_one_server_row_per_event_with_agreement_flag(tmp_path):
    proc, out, report = run_recheck(tmp_path, ["甲", "乙"], {"ocr-000001": "甲", "ocr-000002": "丙"})

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [(r["id"], r["agree"]) for r in rows] == [("ocr-000001", True), ("ocr-000002", False)]
    assert rows[1]["server"] == "丙" and rows[1]["mobile"] == "乙"


def test_refuses_to_overwrite_existing_output(tmp_path):
    events, rows = events_file(tmp_path, ["甲"])
    out = tmp_path / "server.jsonl"
    out.write_text("keep\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "recheck_events_with_server.py"), "--events", str(events),
         "--output-jsonl", str(out), "--output-report", str(tmp_path / "r.json"),
         "--ocr-command", f"{sys.executable} {STUB}"], capture_output=True, text=True)
    assert proc.returncode != 0
    assert out.read_text(encoding="utf-8") == "keep\n"


def test_failing_ocr_command_is_reported_not_swallowed(tmp_path):
    events, rows = events_file(tmp_path, ["甲"])
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "recheck_events_with_server.py"), "--events", str(events),
         "--output-jsonl", str(tmp_path / "o.jsonl"), "--output-report", str(tmp_path / "r.json"),
         "--ocr-command", f"{sys.executable} -c 'import sys; sys.exit(3)'"], capture_output=True, text=True)
    assert proc.returncode != 0
    assert not (tmp_path / "o.jsonl").exists()


def test_min_text_height_drops_small_interface_text_from_the_server_reading(tmp_path):
    events, rows = events_file(tmp_path, ["字幕甲"])
    amap = write_json(tmp_path / "answers.json",
                      {rows[0]["evidence"][1]: [["辅助功能：调查", 19], ["字幕甲", 42], ["Q搜索", 21]]})
    out, report = tmp_path / "server.jsonl", tmp_path / "report.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "recheck_events_with_server.py"), "--events", str(events),
         "--output-jsonl", str(out), "--output-report", str(report), "--min-text-height", "30",
         "--ocr-command", f"{sys.executable} {STUB}"],
        capture_output=True, text=True, env={**os.environ, "STUB_OCR_MAP": str(amap)})

    assert proc.returncode == 0, proc.stderr
    row = json.loads(out.read_text(encoding="utf-8"))
    assert row["server"] == "字幕甲" and row["agree"] is True
