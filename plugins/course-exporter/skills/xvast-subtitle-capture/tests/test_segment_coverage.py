import json


def index(tmp_path, rows, name="frame-index.jsonl"):
    path = tmp_path / name
    path.write_text("".join(json.dumps({"video_ms": ms, "batch": batch, "source": f"{batch}/f.jpg"}) + "\n"
                            for ms, batch in rows), encoding="utf-8")
    return path


def coverage(run, tmp_path, *args):
    out = tmp_path / "coverage.json"
    code, payload, stdout, err = run("segment_coverage.py", *args, "--output", out)
    assert code == 0, stdout + err
    return json.loads(out.read_text(encoding="utf-8"))


def test_a_hole_between_batches_becomes_one_seam_gap(run, tmp_path):
    rows = [(0, "main-001"), (500, "main-001"), (1000, "main-001"), (3000, "main-002"), (3500, "main-002")]

    cov = coverage(run, tmp_path, "--frame-index", index(tmp_path, rows), "--start-ms", 0, "--end-ms", 3600)

    assert cov["capture_coverage"] == "incomplete"
    assert [(g["start_ms"], g["end_ms"]) for g in cov["gaps"]] == [(1000, 3000)]
    assert "批次接缝" in cov["gaps"][0]["reason"]


def test_uncaptured_head_and_tail_are_gaps_and_tail_reason_is_used(run, tmp_path):
    rows = [(3000, "main-001"), (3500, "main-001"), (4000, "main-001")]

    cov = coverage(run, tmp_path, "--frame-index", index(tmp_path, rows), "--start-ms", 0, "--end-ms", 10000,
                   "--tail-reason", "视频播到结尾停止")

    assert [(g["start_ms"], g["end_ms"]) for g in cov["gaps"]] == [(0, 3000), (4000, 10000)]
    assert cov["gaps"][1]["reason"] == "视频播到结尾停止"


def test_only_frames_inside_the_range_count_and_no_gap_means_complete(run, tmp_path):
    rows = [(ms, "main-001") for ms in range(0, 20001, 500)]

    cov = coverage(run, tmp_path, "--frame-index", index(tmp_path, rows), "--start-ms", 5000, "--end-ms", 10000)

    assert cov["gaps"] == [] and cov["capture_coverage"] == "complete"
    assert cov["cue_text_review"] == "ocr_only"


def test_refuses_to_overwrite(run, tmp_path):
    out = tmp_path / "coverage.json"
    out.write_text("{}")
    code, payload, stdout, err = run("segment_coverage.py", "--frame-index", index(tmp_path, [(0, "a")]),
                                     "--start-ms", 0, "--end-ms", 500, "--output", out)
    assert code != 0 and out.read_text() == "{}"
