import json
import os
import subprocess
import sys

from PIL import Image
from conftest import SCRIPTS, write_json


def make_batch(raw, name, start_ms, count, status="valid"):
    folder = raw / name
    folder.mkdir(parents=True)
    frames = []
    for i in range(1, count + 1):
        file = f"frame-{i:06d}.jpg"
        Image.new("RGB", (8, 8), "white").save(folder / file)
        frames.append({"index": i, "file": file, "wall_before_ms": 1000 + (i - 1) * 500})
    write_json(folder / "frames.json", {"batch": name, "status": status, "video_start_ms": start_ms, "video_end_ms": start_ms + (count - 1) * 500,
                                       "wall_start_ms": 1000, "wall_end_ms": 1000 + (count - 1) * 500, "playback_rate": 1,
                                       "layout_profile": "l", "frames": frames})


def index_rows(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def video_with_batches(tmp_path):
    video = tmp_path / "video"
    raw = video / ".raw"
    make_batch(raw, "main-001", 0, 10)        # 0..4500 ms
    make_batch(raw, "main-002", 4000, 10)     # 4000..8500, overlaps main-001 by 500 ms
    make_batch(raw, "stale-pending", 0, 3, status="pending_manual_review")
    (video / "batches.txt").write_text("main-001\nmain-002\n", encoding="utf-8")
    return video


def prepare(video, *extra, name="s", start=0, end=9000):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "prepare_segment.py"), "--video-dir", str(video), "--name", name,
         "--batch-list", str(video / "batches.txt"), "--start-ms", str(start), "--end-ms", str(end), *extra],
        capture_output=True, text=True)


def test_only_listed_batches_are_indexed(tmp_path):
    video = video_with_batches(tmp_path)

    proc = prepare(video, "--stop-after", "index")

    assert proc.returncode == 0, proc.stderr
    rows = index_rows(video / ".raw" / "seg-s" / "ocr" / "frame-index.jsonl")
    assert {r["batch"] for r in rows} == {"main-001", "main-002"}


def test_the_overlap_between_batches_is_indexed_once_by_the_later_batch(tmp_path):
    video = video_with_batches(tmp_path)

    prepare(video, "--stop-after", "index")

    rows = index_rows(video / ".raw" / "seg-s" / "ocr" / "frame-index.jsonl")
    first = [r for r in rows if r["batch"] == "main-001"]
    assert max(r["video_ms"] for r in first) < 4000          # main-001 stops where main-002 starts
    assert min(r["video_ms"] for r in rows if r["batch"] == "main-002") == 4000
    times = [r["video_ms"] for r in rows]
    assert times == sorted(times) and len(times) == len(set(times))


def test_frames_list_matches_the_trimmed_index(tmp_path):
    video = video_with_batches(tmp_path)

    prepare(video, "--stop-after", "index")

    ocr = video / ".raw" / "seg-s" / "ocr"
    listed = ocr.joinpath("frames.txt").read_text(encoding="utf-8").splitlines()
    assert listed == [r["source"] for r in index_rows(ocr / "frame-index.jsonl")]


def test_frames_beyond_the_margin_of_the_segment_are_left_out(tmp_path):
    video = video_with_batches(tmp_path)

    prepare(video, "--stop-after", "index", start=1000, end=2000, name="narrow")  # margin is 15 s: all frames fit
    rows = index_rows(video / ".raw" / "seg-narrow" / "ocr" / "frame-index.jsonl")
    assert rows

    make_batch(video / ".raw", "main-003", 60000, 4)
    (video / "batches.txt").write_text("main-001\nmain-002\nmain-003\n", encoding="utf-8")
    prepare(video, "--stop-after", "index", start=1000, end=2000, name="narrow2")
    rows = index_rows(video / ".raw" / "seg-narrow2" / "ocr" / "frame-index.jsonl")
    assert "main-003" not in {r["batch"] for r in rows}


def test_a_listed_batch_that_does_not_exist_is_an_error(tmp_path):
    video = video_with_batches(tmp_path)
    (video / "batches.txt").write_text("main-001\nmain-999\n", encoding="utf-8")

    proc = prepare(video, "--stop-after", "index")

    assert proc.returncode != 0 and "main-999" in proc.stderr + proc.stdout


def test_a_listed_batch_that_is_not_valid_is_an_error(tmp_path):
    video = video_with_batches(tmp_path)
    (video / "batches.txt").write_text("main-001\nstale-pending\n", encoding="utf-8")

    proc = prepare(video, "--stop-after", "index")

    assert proc.returncode != 0 and "stale-pending" in proc.stderr + proc.stdout


def test_dry_run_prints_the_stages_and_creates_nothing(tmp_path):
    video = video_with_batches(tmp_path)

    proc = prepare(video, "--dry-run")

    assert proc.returncode == 0, proc.stderr
    plan = json.loads(proc.stdout)
    assert [s["stage"] for s in plan["stages"]] == ["index", "ocr", "merge", "range", "recheck", "sheets"]
    assert not (video / ".raw" / "seg-s").exists()


def test_events_are_kept_only_when_they_start_inside_the_range(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text("".join(json.dumps({"id": i, "start_ms": s, "end_ms": s + 1}) + "\n" for i, s in enumerate([500, 1000, 1999, 2000, 2500])), encoding="utf-8")
    out = tmp_path / "in-range.jsonl"

    proc = subprocess.run([sys.executable, str(SCRIPTS / "filter_events_in_range.py"), "--events", str(events),
                           "--start-ms", "1000", "--end-ms", "2000", "--output", str(out)], capture_output=True, text=True)

    assert proc.returncode == 0, proc.stderr
    assert [json.loads(l)["start_ms"] for l in out.read_text(encoding="utf-8").splitlines()] == [1000, 1999]
    assert json.loads(proc.stdout) == {"events": 5, "in_range": 2}


def test_min_text_height_is_passed_to_merge_and_recheck(tmp_path):
    video = video_with_batches(tmp_path)

    proc = prepare(video, "--dry-run", "--min-text-height", "30")

    assert proc.returncode == 0, proc.stderr
    stages = {s["stage"]: s["command"] for s in json.loads(proc.stdout)["stages"]}
    for stage in ("merge", "recheck"):
        command = stages[stage]
        assert command[command.index("--min-text-height") + 1] == "30"
