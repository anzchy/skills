import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import SCRIPTS, write_json

STUB = Path(__file__).resolve().parent / "stub_xvast_capture.py"


def series(tmp_path, position_ms=100000, behaviour=None, existing=(), dead=False, **opts):
    raw = tmp_path / ".raw"
    raw.mkdir(exist_ok=True)
    for name in existing:
        (raw / name).mkdir()
        (raw / name / "frames.json").write_text("{}")
    state = write_json(tmp_path / "state.json", {"position_ms": position_ms, "behaviour": behaviour or {}, "dead": dead})
    log = tmp_path / "calls.log"
    args = ["--raw-root", raw, "--video-id", "v.mp4", "--target-ms", opts.pop("target", 400000),
            "--warmup-seconds", "0", "--xvast-capture", f"{sys.executable} {STUB}", "--no-measure",
            "--layout-profile", "layout-test"]
    for key, value in opts.items():
        args += [f"--{key.replace('_', '-')}"] + ([] if value == "" else [value])
    proc = subprocess.run([sys.executable, str(SCRIPTS / "capture_series.py"), *map(str, args)], capture_output=True, text=True,
                          env={**os.environ, "STUB_XVAST_STATE": str(state), "STUB_XVAST_LOG": str(log)})
    lines = [json.loads(l) for l in proc.stdout.splitlines() if l.startswith("{")]
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return proc, lines, calls, raw


def test_batches_are_captured_until_the_target_is_reached(tmp_path):
    proc, lines, calls, raw = series(tmp_path, start_batch=1, target=380000)

    assert proc.returncode == 0, proc.stderr
    # each batch advances 50 s (60 s captured minus the 10 s rewind): ends at 150, 200, 250, 300, 350, 400 s
    assert [l["video_end_ms"] for l in lines] == [150000, 200000, 250000, 300000, 350000, 400000]
    assert lines[-1]["video_end_ms"] >= 380000 > lines[-2]["video_end_ms"]


def test_each_batch_is_preceded_by_the_rewind_warmup_in_order(tmp_path):
    proc, lines, calls, raw = series(tmp_path, start_batch=1, target=150000)

    first = [c.split()[0] for c in calls[:4]]
    assert first == ["seek", "play", "park-cursor", "capture"]
    assert calls[0] == "seek --by -10"


def test_consecutive_batches_overlap_by_the_rewind(tmp_path):
    proc, lines, calls, raw = series(tmp_path, position_ms=100000, start_batch=1, target=300000)

    assert lines[0]["video_start_ms"] == 90000
    assert lines[1]["video_start_ms"] == lines[0]["video_end_ms"] - 10000


def test_numbering_continues_after_the_highest_existing_batch(tmp_path):
    proc, lines, calls, raw = series(tmp_path, existing=["main-001", "main-002", "main-007"], target=150000)

    assert lines[0]["batch"] == "main-008"


def test_an_invalid_batch_stops_the_series_with_a_failure(tmp_path):
    proc, lines, calls, raw = series(tmp_path, start_batch=1, behaviour={"main-002": "invalid"}, target=900000)

    assert proc.returncode != 0
    assert [l["batch"] for l in lines] == ["main-001", "main-002"]
    assert lines[-1]["status"] == "invalid"
    assert not (raw / "main-003").exists()


def test_unreadable_capture_output_stops_the_series(tmp_path):
    proc, lines, calls, raw = series(tmp_path, start_batch=1, behaviour={"main-001": "garbage"}, target=900000)

    assert proc.returncode != 0
    assert sum(1 for c in calls if c.startswith("capture")) == 1


def test_max_batches_limits_the_run(tmp_path):
    proc, lines, calls, raw = series(tmp_path, start_batch=1, target=9000000, max_batches=2)

    assert proc.returncode == 0 and len(lines) == 2


def test_capture_receives_the_requested_batch_settings(tmp_path):
    proc, lines, calls, raw = series(tmp_path, start_batch=1, target=120000, frame_count=30, interval_ms=300, batch_prefix="late")

    capture = [c for c in calls if c.startswith("capture")][0]
    assert "--frame-count 30" in capture and "--interval-ms 300" in capture and "--batch-dir late-001" in capture
    assert "--pause-after-capture" in capture and "--layout-profile layout-test" in capture


def test_xvast_dying_during_a_capture_stops_with_a_resume_point(tmp_path):
    proc, lines, calls, raw = series(tmp_path, start_batch=1, behaviour={"main-002": "crash"}, target=900000)

    assert proc.returncode == 3
    lost = lines[-1]
    assert lost["event"] == "xvast_lost" and lost["batch"] == "main-002"
    assert lost["last_valid_batch"] == "main-001" and lost["resume_from_ms"] == 150000
    assert "main-003" not in " ".join(calls)
    assert "not running" in proc.stderr or "lost" in proc.stderr


def test_xvast_already_gone_before_the_first_batch_is_not_captured(tmp_path):
    proc, lines, calls, raw = series(tmp_path, start_batch=1, dead=True, target=900000)

    assert proc.returncode == 3
    assert lines[-1]["event"] == "xvast_lost" and lines[-1]["last_valid_batch"] is None
    assert not any(c.startswith("capture") for c in calls)


def test_a_non_crash_capture_failure_keeps_the_ordinary_failure_code(tmp_path):
    proc, lines, calls, raw = series(tmp_path, start_batch=1, behaviour={"main-001": "garbage"}, target=900000)

    assert proc.returncode == 1
    assert not any(l.get("event") == "xvast_lost" for l in lines)


def test_continuous_mode_never_seeks_and_keeps_playing_between_batches(tmp_path):
    proc, lines, calls, raw = series(tmp_path, position_ms=100000, start_batch=1, target=280000, continuous="")

    assert proc.returncode == 0, proc.stderr
    assert not any(c.startswith("seek") for c in calls)
    assert [c.split()[0] for c in calls[:3]] == ["play", "park-cursor", "capture"]
    assert sum(1 for c in calls if c.startswith("play")) == 1
    captures = [c for c in calls if c.startswith("capture")]
    assert len(captures) == 3 and not any("--pause-after-capture" in c for c in captures)
    assert calls[-1] == "pause"
    assert lines[1]["video_start_ms"] == lines[0]["video_end_ms"]


def test_continuous_mode_clips_the_last_batch_to_the_target(tmp_path):
    proc, lines, calls, raw = series(tmp_path, position_ms=100000, start_batch=1, target=180000, continuous="")

    captures = [c for c in calls if c.startswith("capture")]
    assert "--frame-count 120" in captures[0]
    # first batch ends at 160 s; 20 s left at 500 ms -> 41 frames
    assert "--frame-count 41" in captures[1]


def test_continuous_mode_pauses_the_player_when_a_batch_is_invalid(tmp_path):
    proc, lines, calls, raw = series(tmp_path, start_batch=1, behaviour={"main-002": "invalid"}, target=900000,
                                     continuous="")

    assert proc.returncode == 1
    assert calls[-1] == "pause"


def test_continuous_mode_reports_the_seam_to_the_previous_batch(tmp_path):
    proc, lines, calls, raw = series(tmp_path, position_ms=100000, start_batch=1, target=280000, continuous="")

    assert proc.returncode == 0, proc.stderr
    assert "seam_ms" not in lines[0]
    assert [l["seam_ms"] for l in lines[1:]] == [0, 0]


def test_measure_after_defers_layout_measurement_until_the_series_ends(tmp_path):
    proc, lines, calls, raw = series(tmp_path, position_ms=100000, start_batch=1, target=220000, continuous="",
                                     measure_after="")

    assert proc.returncode == 0, proc.stderr
    batches = [l for l in lines if "event" not in l]
    layouts = [l for l in lines if l.get("event") == "layout"]
    assert all("layout" not in l for l in batches)
    assert [l["batch"] for l in layouts] == [l["batch"] for l in batches]
    assert lines.index(layouts[0]) > lines.index(batches[-1])
