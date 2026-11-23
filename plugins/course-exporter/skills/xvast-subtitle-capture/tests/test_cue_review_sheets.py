import json

from PIL import Image
from conftest import write_json


def candidate_rows(tmp_path, texts):
    rows = []
    for index, text in enumerate(texts, 1):
        frame = tmp_path / f"f{index}.jpg"
        Image.new("RGB", (400, 300), (index * 40, 90, 90)).save(frame)
        rows.append({"id": f"ocr-{index:06d}", "start_ms": index * 1000, "end_ms": index * 1000 + 700,
                     "server": text, "mobile": text, "frame": str(frame)})
    path = tmp_path / "candidates.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path, rows


def run_sheets(run, tmp_path, texts, *extra, per_sheet=2):
    candidates, rows = candidate_rows(tmp_path, texts)
    out = tmp_path / "sheets"
    code, payload, stdout, stderr = run(
        "make_cue_review_sheets.py", "--candidates", candidates, "--output-dir", out,
        "--strip-crop", "0,200,400,300", "--per-sheet", per_sheet, *extra)
    return code, payload, stdout, stderr, out, rows


def test_splits_events_into_numbered_sheets_and_a_numbered_text_list(run, tmp_path):
    code, payload, stdout, stderr, out, rows = run_sheets(run, tmp_path, ["甲", "乙", "丙"])

    assert code == 0, stdout + stderr
    assert payload["events"] == 3 and len(payload["sheets"]) == 2
    first = Image.open(payload["sheets"][0])
    last = Image.open(payload["sheets"][1])
    assert first.height > last.height  # two strips on the first sheet, one on the second
    lines = (out / "candidates.txt").read_text(encoding="utf-8").splitlines()
    assert lines == ["1 ocr-000001 甲", "2 ocr-000002 乙", "3 ocr-000003 丙"]


def test_corrections_become_event_level_correction_records(run, tmp_path):
    corrections = write_json(tmp_path / "corrections.json", {"ocr-000002": "丁"})
    events_out = tmp_path / "events.jsonl"
    code, payload, stdout, stderr, out, rows = run_sheets(
        run, tmp_path, ["甲", "乙", "丙"], "--corrections", corrections, "--output-events", events_out,
        "--mark-verified")

    assert code == 0, stdout + stderr
    events = [json.loads(line) for line in events_out.read_text(encoding="utf-8").splitlines()]
    assert [e["text"] for e in events] == ["甲", "丁", "丙"]
    assert "correction" not in events[0]
    assert events[1]["correction"] == {"before": "乙", "after": "丁", "evidence": rows[1]["frame"]}
    assert events[1]["review"] == "verified" and events[0]["review"] == "verified"


def test_events_stay_ocr_only_unless_marked_verified(run, tmp_path):
    corrections = write_json(tmp_path / "corrections.json", {"ocr-000001": "丁"})
    events_out = tmp_path / "events.jsonl"
    code, payload, stdout, stderr, out, rows = run_sheets(
        run, tmp_path, ["甲", "乙"], "--corrections", corrections, "--output-events", events_out)

    assert code == 0, stdout + stderr
    events = [json.loads(line) for line in events_out.read_text(encoding="utf-8").splitlines()]
    assert {e["review"] for e in events} == {"ocr_only"}
    assert events[0]["correction"]["after"] == "丁"


def test_correction_for_an_unknown_event_is_an_error(run, tmp_path):
    corrections = write_json(tmp_path / "corrections.json", {"ocr-999999": "丁"})
    code, payload, stdout, stderr, out, rows = run_sheets(
        run, tmp_path, ["甲"], "--corrections", corrections, "--output-events", tmp_path / "events.jsonl")

    assert code != 0
    assert "ocr-999999" in stderr + stdout


def test_an_index_records_which_numbers_each_sheet_holds(run, tmp_path):
    code, payload, stdout, stderr, out, rows = run_sheets(run, tmp_path, ["甲", "乙", "丙"], per_sheet=2)

    assert code == 0, stderr
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert index["per_sheet"] == 2
    assert [(s["sheet"], s["first"], s["last"]) for s in index["sheets"]] == [("sheet-01.jpg", 1, 2), ("sheet-02.jpg", 3, 3)]
