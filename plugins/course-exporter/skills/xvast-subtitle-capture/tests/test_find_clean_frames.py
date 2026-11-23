import json

from test_measure_bounds import synthetic_frame


def index(tmp_path, specs):
    rows = []
    for n, (ms, subtitle) in enumerate(specs, 1):
        frame = synthetic_frame(tmp_path / f"frame-{n:06d}.png", subtitle=subtitle)
        rows.append({"video_ms": ms, "batch": "main-001", "frame_index": n, "source": str(frame)})
    path = tmp_path / "frame-index.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def test_frames_without_a_subtitle_come_first_within_the_range(run, tmp_path):
    path = index(tmp_path, [(0, False), (1000, True), (2000, False), (3000, True), (9000, False)])
    sheet = tmp_path / "sheet.jpg"

    code, payload, out, err = run("find_clean_frames.py", "--frame-index", path, "--range", "500-5000",
                                  "--top", 3, "--sheet", sheet)

    assert code == 0, out + err
    cands = payload["candidates"]
    assert [c["label"] for c in cands] == ["main-001:3", "main-001:2", "main-001:4"]
    assert cands[0]["subtitle_width"] == 0 and cands[1]["subtitle_width"] > 0
    assert sheet.exists()


def test_sheet_is_never_overwritten(run, tmp_path):
    path = index(tmp_path, [(0, False)])
    sheet = tmp_path / "sheet.jpg"
    sheet.write_bytes(b"old")

    code, payload, out, err = run("find_clean_frames.py", "--frame-index", path, "--range", "0-100", "--sheet", sheet)

    assert code != 0 and sheet.read_bytes() == b"old"
