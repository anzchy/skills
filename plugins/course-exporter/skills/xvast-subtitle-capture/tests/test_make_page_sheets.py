import json
import subprocess
import sys

from PIL import Image

from conftest import SCRIPTS


def frame_index(tmp_path, times_ms, with_batch="main-001"):
    rows = []
    for i, t in enumerate(times_ms, 1):
        path = tmp_path / f"{with_batch}-{i}.jpg"
        Image.new("RGB", (400, 300), (i * 10 % 255, 80, 120)).save(path)
        rows.append({"video_ms": t, "source": str(path), "batch": with_batch, "frame_index": i,
                     "batch_status": "valid", "layout_profile": "layout-003"})
    index = tmp_path / "frame-index.jsonl"
    index.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return index


def run_sheets(tmp_path, index, *extra, out="sheets"):
    proc = subprocess.run([sys.executable, str(SCRIPTS / "make_page_sheets.py"), "--frame-index", str(index),
                           "--output-dir", str(tmp_path / out), "--crop", "0,0,400,225", "--per-sheet", "4",
                           *extra], capture_output=True, text=True)
    return proc, tmp_path / out


def test_samples_one_frame_per_interval_and_labels_them_by_time_and_frame(tmp_path):
    index = frame_index(tmp_path, [0, 500, 1000, 5000, 5500, 11000, 16000])
    proc, out = run_sheets(tmp_path, index, "--every-ms", "5000")
    assert proc.returncode == 0, proc.stderr
    mapping = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert [m["video_ms"] for m in mapping] == [0, 5000, 11000, 16000]     # first frame of each 5 s bucket
    assert mapping[1]["label"] == "main-001:4" and mapping[1]["sheet"] == "sheet-01.jpg"
    assert sorted(p.name for p in out.glob("sheet-*.jpg")) == ["sheet-01.jpg"]


def test_sheets_hold_per_sheet_thumbnails_each(tmp_path):
    index = frame_index(tmp_path, [i * 5000 for i in range(9)])
    proc, out = run_sheets(tmp_path, index, "--every-ms", "5000")
    assert proc.returncode == 0, proc.stderr
    assert sorted(p.name for p in out.glob("sheet-*.jpg")) == ["sheet-01.jpg", "sheet-02.jpg", "sheet-03.jpg"]


def test_slide_changes_add_frames_the_interval_sampling_would_miss(tmp_path):
    index = frame_index(tmp_path, [0, 1000, 2000, 3000, 6000])
    rows = [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines()]
    changes = tmp_path / "slide-changes.json"
    changes.write_text(json.dumps({"changes": [{"time_ms": 2000, "kind": "slide", "frame": rows[2]["source"]},
                                               {"time_ms": 3000, "kind": "content", "frame": rows[3]["source"]}]}),
                       encoding="utf-8")
    proc, out = run_sheets(tmp_path, index, "--every-ms", "5000", "--changes", str(changes), "--min-gap-ms", "1000")
    assert proc.returncode == 0, proc.stderr
    mapping = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert [m["video_ms"] for m in mapping] == [0, 2000, 6000]      # only whole-slide changes are added


def test_existing_output_directory_is_refused(tmp_path):
    index = frame_index(tmp_path, [0])
    (tmp_path / "sheets").mkdir()
    proc, out = run_sheets(tmp_path, index)
    assert proc.returncode != 0 and "exists" in proc.stderr


def test_a_change_close_to_an_already_sampled_frame_adds_nothing(tmp_path):
    index = frame_index(tmp_path, [0, 1000, 2000, 6000])
    rows = [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines()]
    changes = tmp_path / "slide-changes.json"
    changes.write_text(json.dumps({"changes": [{"time_ms": 1000, "kind": "slide", "frame": rows[1]["source"]}]}), encoding="utf-8")
    proc, out = run_sheets(tmp_path, index, "--every-ms", "5000", "--changes", str(changes), "--min-gap-ms", "3000")
    assert proc.returncode == 0, proc.stderr
    assert [m["video_ms"] for m in json.loads((out / "index.json").read_text(encoding="utf-8"))] == [0, 6000]
