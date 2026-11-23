import json
import subprocess
import sys

from PIL import Image

from conftest import SCRIPTS, write_json


def project(tmp_path, excluded=()):
    root = tmp_path / "proj"
    raw = root / "video" / ".raw"
    seg = raw / "seg-t1"
    (seg / "ocr").mkdir(parents=True)
    rows = []
    for batch, count in (("main-001", 3), ("main-002", 3)):
        (raw / batch).mkdir(parents=True)
        for i in range(1, count + 1):
            Image.new("RGB", (40, 30), "white").save(raw / batch / f"frame-{i:06d}.jpg")
        write_json(raw / batch / "frames.json", {"status": "valid", "manual_review": {"excluded_frames": list(excluded) if batch == "main-002" else []}})
    return root, seg


def run_config(root, seg, pages, out_name="build-config.json", start_ms=None, **extra):
    pages_file = write_json(seg / "pages.json", pages)
    out = seg / out_name
    args = [*(["--start-ms", start_ms] if start_ms is not None else []), "--project-root", root, "--seg-dir", seg.relative_to(root), "--pages", pages_file, "--output", out,
            "--out-dir", "video/.staging-t1-v1", "--title", "段一", "--end-ms", 600000,
            "--coverage", write_json(seg / "coverage.json", {"capture_coverage": "complete"})]
    proc = subprocess.run([sys.executable, str(SCRIPTS / "make_segment_config.py"), *map(str, args)], capture_output=True, text=True)
    return proc, out


def page(title, start, frame, **extra):
    return {"title": title, "first_seen_ms": start, "range_start_ms": start, "frame": frame, "type": "full_slide", **extra}


def test_pages_become_slides_ranges_and_resolved_frame_paths(tmp_path):
    root, seg = project(tmp_path)
    proc, out = run_config(root, seg, [page("甲", 0, "main-001:2"), page("乙", 90000, "main-002:1", type="editor_window",
                                                                         fallback="PowerPoint 编辑窗口")])
    assert proc.returncode == 0, proc.stderr
    config = json.loads(out.read_text(encoding="utf-8"))
    assert [s["id"] for s in config["slides"]] == ["t1-ppt-001", "t1-ppt-002"]
    assert config["slides"][0]["frame"].endswith("video/.raw/main-001/frame-000002.jpg")
    assert config["slides"][1]["fallback"] == "PowerPoint 编辑窗口" and config["slides"][1]["type"] == "editor_canvas"
    assert config["ranges"] == [[0, "t1-ppt-001"], [90000, "t1-ppt-002"]]
    assert config["seg_dir"] == "video/.raw/seg-t1" and config["out_dir"] == "video/.staging-t1-v1"
    assert config["end_ms"] == 600000 and config["title"] == "段一" and config["coverage"] == {"capture_coverage": "complete"}


def test_a_revisit_folds_into_the_earlier_page_without_a_new_slide(tmp_path):
    root, seg = project(tmp_path)
    proc, out = run_config(root, seg, [page("甲", 0, "main-001:1"), page("乙", 30000, "main-001:2"),
                                       {"title": "回到甲", "range_start_ms": 60000, "same_as": 1}])
    assert proc.returncode == 0, proc.stderr
    config = json.loads(out.read_text(encoding="utf-8"))
    assert [s["id"] for s in config["slides"]] == ["t1-ppt-001", "t1-ppt-002"]
    assert config["ranges"][2][0] == 60000
    assert config["merge_keys"] == {config["ranges"][2][1]: "t1-ppt-001"}


def test_a_frame_excluded_by_the_batch_review_is_rejected(tmp_path):
    root, seg = project(tmp_path, excluded=[2])
    proc, out = run_config(root, seg, [page("甲", 0, "main-002:2")])
    assert proc.returncode != 0 and "excluded" in proc.stderr and not out.exists()


def test_a_missing_frame_or_a_page_out_of_order_is_rejected(tmp_path):
    root, seg = project(tmp_path)
    proc, out = run_config(root, seg, [page("甲", 0, "main-001:9")])
    assert proc.returncode != 0 and "missing" in proc.stderr
    proc, out = run_config(root, seg, [page("甲", 5000, "main-001:1"), page("乙", 1000, "main-001:2")], out_name="b.json")
    assert proc.returncode != 0 and "order" in proc.stderr


def test_existing_output_is_never_overwritten(tmp_path):
    root, seg = project(tmp_path)
    run_config(root, seg, [page("甲", 0, "main-001:1")])
    proc, out = run_config(root, seg, [page("甲", 0, "main-001:1")])
    assert proc.returncode != 0 and "exists" in proc.stderr


def test_same_as_counts_positions_in_the_pages_list_not_slides(tmp_path):
    root, seg = project(tmp_path)
    proc, out = run_config(root, seg, [page("甲", 0, "main-001:1"), {"title": "回甲", "range_start_ms": 10000, "same_as": 1},
                                       page("乙", 20000, "main-001:2"), {"title": "回乙", "range_start_ms": 30000, "same_as": 3}])
    assert proc.returncode == 0, proc.stderr
    config = json.loads(out.read_text(encoding="utf-8"))
    assert [s["id"] for s in config["slides"]] == ["t1-ppt-001", "t1-ppt-002"]
    assert sorted(config["merge_keys"].values()) == ["t1-ppt-001", "t1-ppt-002"]
    assert config["merge_keys"][config["ranges"][3][1]] == "t1-ppt-002"


def test_page_kinds_map_to_the_slide_types_the_validator_accepts(tmp_path):
    root, seg = project(tmp_path)
    proc, out = run_config(root, seg, [
        page("甲", 0, "main-001:1"),
        page("乙", 10000, "main-001:2", type="editor_window", fallback="PowerPoint 编辑窗口"),
        page("丙", 20000, "main-001:3", type="software", fallback="表格软件界面"),
        page("丁", 30000, "main-002:1", type="zoomed", fallback="放大局部画面")])
    assert proc.returncode == 0, proc.stderr
    assert [s["type"] for s in json.loads(out.read_text(encoding="utf-8"))["slides"]] == [
        "full_slide", "editor_canvas", "full_slide", "full_slide"]


def test_a_non_slide_page_without_a_fallback_reason_is_rejected(tmp_path):
    root, seg = project(tmp_path)
    proc, out = run_config(root, seg, [page("甲", 0, "main-001:1", type="editor_window")])
    assert proc.returncode != 0 and "fallback" in proc.stderr and not out.exists()


def test_a_revisit_of_a_revisit_resolves_to_the_original_slide(tmp_path):
    root, seg = project(tmp_path)
    proc, out = run_config(root, seg, [page("甲", 0, "main-001:1"), page("乙", 10000, "main-001:2"),
                                       {"title": "回甲", "range_start_ms": 20000, "same_as": 1},
                                       {"title": "再回甲", "range_start_ms": 30000, "same_as": 3}])
    assert proc.returncode == 0, proc.stderr
    config = json.loads(out.read_text(encoding="utf-8"))
    assert set(config["merge_keys"].values()) == {"t1-ppt-001"} and len(config["slides"]) == 2


def test_pages_that_start_at_or_after_the_segment_end_are_dropped(tmp_path):
    root, seg = project(tmp_path)
    proc, out = run_config(root, seg, [page("甲", 0, "main-001:1"), page("乙", 590000, "main-001:2"),
                                       page("下一段的页", 600000, "main-001:3"), page("下下页", 603000, "main-002:1")])
    assert proc.returncode == 0, proc.stderr
    config = json.loads(out.read_text(encoding="utf-8"))
    assert [s["title"] for s in config["slides"]] == ["甲", "乙"] and len(config["ranges"]) == 2


def test_with_a_start_only_the_last_earlier_page_is_kept_and_moved_to_the_start(tmp_path):
    root, seg = project(tmp_path)
    proc, out = run_config(root, seg, [page("更早的页", 1000, "main-001:1"), page("开头可见的页", 4000, "main-001:2"),
                                       page("之后的页", 9000, "main-001:3")], start_ms=5000)
    assert proc.returncode == 0, proc.stderr
    config = json.loads(out.read_text(encoding="utf-8"))
    assert [s["title"] for s in config["slides"]] == ["开头可见的页", "之后的页"]
    assert config["ranges"][0][0] == 5000 and config["slides"][0]["first_seen"] == 4000


def test_video_bounds_pass_through_to_the_slide(tmp_path):
    root, seg = project(tmp_path)
    proc, out = run_config(root, seg, [page("甲", 0, "main-001:1", video_bounds=[117, 198, 2037, 1278])])
    assert proc.returncode == 0, proc.stderr
    assert json.loads(out.read_text(encoding="utf-8"))["slides"][0]["video_bounds"] == [117, 198, 2037, 1278]


def test_no_subtitle_passes_through_to_the_slide(tmp_path):
    root, seg = project(tmp_path)
    proc, out = run_config(root, seg, [page("甲", 0, "main-001:1", no_subtitle=True), page("乙", 5000, "main-001:2")])
    assert proc.returncode == 0, proc.stderr
    slides = json.loads(out.read_text(encoding="utf-8"))["slides"]
    assert slides[0]["no_subtitle"] is True and "no_subtitle" not in slides[1]
