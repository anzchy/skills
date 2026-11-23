import json

from conftest import minimal_manifest, write_json
from test_measure_bounds import synthetic_frame

LAYOUTS = ["--layout", "layout-001=20,20,380,260", "--layout", "layout-002=5,20,365,260"]
EYE = ["--reviewed-by-eye", "Claude：Read 首/中/末帧拼图"]


def batch(raw, name, frames=3, status="pending_manual_review", shift_from=None, layout="layout-001"):
    folder = raw / name
    folder.mkdir(parents=True)
    for i in range(1, frames + 1):
        synthetic_frame(folder / f"frame-{i:06d}.jpg", dx=-15 if shift_from and i >= shift_from else 0)
    write_json(folder / "frames.json", {"status": status, "batch": name, "video_start_ms": 0, "video_end_ms": 60000,
                                        "wall_start_ms": 0, "wall_end_ms": 60000, "playback_rate": 1,
                                        "frame_count": frames, "layout_profile": layout,
                                        "invalid_reasons": ["playback stopped"] if status == "invalid" else []})
    return folder / "frames.json"


def mark(run, raw, *args):
    code, payload, out, err = run("mark_batches_valid.py", "--raw-root", raw, *LAYOUTS, *args)
    rows = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    return code, rows, err


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_marked_batch_passes_the_validator_viewport_review_check(run, tmp_path):
    raw = tmp_path / ".raw"
    batch(raw, "main-001")
    batch_list = tmp_path / "batches.txt"

    code, rows, err = mark(run, raw, "--batches", "main-001", "--batch-list", batch_list, *EYE)

    assert code == 0, err
    vcode, report, out, verr = run("validate_capture.py", "--manifest", minimal_manifest(tmp_path), "--batch-root", raw,
                                   "--batch-list", batch_list, "--require-viewport-review")
    assert vcode == 0, out + verr
    review = load(raw / "main-001" / "frames.json")["viewport_review"]
    assert review["evidence"] == ["frame-000001.jpg", "frame-000002.jpg", "frame-000003.jpg"]
    assert review["reviewer"] == "Claude：Read 首/中/末帧拼图"


def test_without_reviewed_by_eye_nothing_is_written(run, tmp_path):
    raw = tmp_path / ".raw"
    path = batch(raw, "main-001")

    code, rows, err = mark(run, raw, "--batches", "main-001")

    assert code != 0 and load(path)["status"] == "pending_manual_review"


def test_a_measured_video_area_off_the_layout_is_refused_unless_accepted_with_a_note(run, tmp_path):
    raw = tmp_path / ".raw"
    path = batch(raw, "main-001", shift_from=3)

    code, rows, err = mark(run, raw, "--batches", "main-001", *EYE)
    assert code == 1 and rows[0]["status"] == "refused" and load(path)["status"] == "pending_manual_review"

    code, rows, err = mark(run, raw, "--batches", "main-001", "--accept-measure", "main-001=末帧被深色画面误导", *EYE)
    assert code == 0, err
    assert load(path)["viewport_review"]["measure_note"] == "末帧被深色画面误导"


def test_a_layout_switch_inside_a_batch_is_recorded_as_layout_segments(run, tmp_path):
    raw = tmp_path / ".raw"
    path = batch(raw, "main-001", frames=5, shift_from=3)

    code, rows, err = mark(run, raw, "--batches", "main-001", "--layout-segment", "main-001:3-5=layout-002", *EYE)

    assert code == 0, err
    data = load(path)
    assert data["layout_profile"] == "layout-002"
    assert [(s["frames"], s["layout_profile"]) for s in data["viewport_review"]["layout_segments"]] == \
        [([1, 2], "layout-001"), ([3, 5], "layout-002")]


def test_an_invalid_batch_needs_excluded_frames_and_the_picks_skip_them(run, tmp_path):
    raw = tmp_path / ".raw"
    path = batch(raw, "main-009", frames=5, status="invalid")

    code, rows, err = mark(run, raw, "--batches", "main-009", *EYE)
    assert code == 1 and load(path)["status"] == "invalid"

    code, rows, err = mark(run, raw, "--batches", "main-009", "--exclude-frames", "main-009:4-5", *EYE)
    assert code == 0, err
    data = load(path)
    assert data["status"] == "valid" and data["manual_review"]["excluded_frames"] == [4, 5]
    assert data["manual_review"]["resolved_invalid_reasons"] == ["playback stopped"]
    assert data["viewport_review"]["evidence"] == ["frame-000001.jpg", "frame-000002.jpg", "frame-000003.jpg"]


def test_range_selects_batches_and_the_batch_list_is_appended_once(run, tmp_path):
    raw = tmp_path / ".raw"
    for n in (1, 2):
        batch(raw, f"main-{n:03d}")
    batch_list = tmp_path / "batches.txt"
    batch_list.write_text("preflight-001\nmain-001\n", encoding="utf-8")

    code, rows, err = mark(run, raw, "--range", "main:1-2", "--batch-list", batch_list, *EYE)
    code2, rows2, err2 = mark(run, raw, "--range", "main:1-2", "--batch-list", batch_list, *EYE)

    assert code == 0 and code2 == 0, err + err2
    assert [r["status"] for r in rows2] == ["already_valid", "already_valid"]
    assert batch_list.read_text(encoding="utf-8").split() == ["preflight-001", "main-001", "main-002"]
