import json
from pathlib import Path

from conftest import write_json


def part(tmp_path, name, slides, cues):
    folder = tmp_path / name
    (folder / "assets").mkdir(parents=True)
    for i, sid in enumerate(slides, 1):
        (folder / "assets" / f"ppt-{i:03d}.png").write_bytes(b"png")
    manifest = write_json(folder / "manifest.json", {
        "title": name, "duration_ms": 1000, "coverage": {},
        "slides": [{"id": sid, "title": sid, "image": f"assets/ppt-{i:03d}.png", "source": f"/src/{sid}.jpg",
                    "crop_box": [0, 0, 1, 1]} for i, sid in enumerate(slides, 1)],
        "cues": [{"id": cid, "start_ms": start, "end_ms": start + 100, "slide_id": sid, "text": cid,
                  "review": "verified", "evidence": "e"} for cid, start, sid in cues]})
    return manifest


def merge(run, tmp_path, parts, **extra):
    config = {"title": "总稿", "duration_ms": 5000,
              "coverage": {"capture_coverage": "incomplete", "cue_text_review": "visual_reviewed",
                           "word_for_word_manual_review": False, "evidence": "e", "gaps": []},
              "parts": [{"tag": tag, "manifest": str(m)} for tag, m in parts], **extra}
    cfg = write_json(tmp_path / "merge.json", config)
    out = tmp_path / "merged.json"
    code, payload, stdout, stderr = run("merge_segment_manifests.py", "--config", cfg, "--output", out)
    return code, stdout, stderr, (json.loads(out.read_text(encoding="utf-8")) if out.exists() else None)


def two_parts(tmp_path):
    m1 = part(tmp_path, "p1", ["a1", "a2"], [("c1", 0, "a1"), ("c2", 500, "a2")])
    m2 = part(tmp_path, "p2", ["b1", "b2"], [("c1", 1000, "b1"), ("c2", 1500, "b2")])
    return [("x", m1), ("y", m2)]


def test_slides_keep_part_order_and_cue_ids_get_the_part_tag(run, tmp_path):
    code, out, err, merged = merge(run, tmp_path, two_parts(tmp_path))

    assert code == 0, out + err
    assert [s["id"] for s in merged["slides"]] == ["a1", "a2", "b1", "b2"]
    assert [c["id"] for c in merged["cues"]] == ["x-c1", "x-c2", "y-c1", "y-c2"]


def test_cues_are_sorted_by_time_across_parts(run, tmp_path):
    m1 = part(tmp_path, "p1", ["a1"], [("c1", 2000, "a1")])
    m2 = part(tmp_path, "p2", ["b1"], [("c1", 100, "b1")])

    code, out, err, merged = merge(run, tmp_path, [("x", m1), ("y", m2)])

    assert [c["id"] for c in merged["cues"]] == ["y-c1", "x-c1"]


def test_image_paths_become_absolute_so_the_build_can_find_each_part_asset(run, tmp_path):
    code, out, err, merged = merge(run, tmp_path, two_parts(tmp_path))

    first = Path(merged["slides"][0]["image"])
    assert first.is_absolute() and first.read_bytes() == b"png"
    assert first.parent.parent.name == "p1"


def test_a_duplicate_slide_is_dropped_and_its_cues_move_to_the_kept_slide(run, tmp_path):
    code, out, err, merged = merge(run, tmp_path, two_parts(tmp_path), merge={"b1": "a2"})

    assert [s["id"] for s in merged["slides"]] == ["a1", "a2", "b2"]
    assert {c["id"]: c["slide_id"] for c in merged["cues"]}["y-c1"] == "a2"


def test_use_image_of_copies_the_picture_and_crop_fields_from_another_slide(run, tmp_path):
    code, out, err, merged = merge(run, tmp_path, two_parts(tmp_path), merge={"b2": "a2"}, use_image_of={"a2": "b2"})

    a2 = [s for s in merged["slides"] if s["id"] == "a2"][0]
    assert a2["source"] == "/src/b2.jpg"
    assert a2["image"].endswith("p2/assets/ppt-002.png")
    assert a2["title"] == "a2"  # the page keeps its own title and identity


def test_duplicate_slide_ids_across_parts_are_an_error(run, tmp_path):
    m1 = part(tmp_path, "p1", ["s1"], [("c1", 0, "s1")])
    m2 = part(tmp_path, "p2", ["s1"], [("c1", 10, "s1")])

    code, out, err, merged = merge(run, tmp_path, [("x", m1), ("y", m2)])

    assert code != 0 and "s1" in out + err


def test_final_mode_rewrites_images_to_flat_assets_names(run, tmp_path):
    cfg_parts = two_parts(tmp_path)
    config = {"title": "t", "duration_ms": 5000, "coverage": {}, "parts": [{"tag": t, "manifest": str(m)} for t, m in cfg_parts]}
    cfg = write_json(tmp_path / "merge.json", config)
    out = tmp_path / "final.json"

    code, payload, stdout, stderr = run("merge_segment_manifests.py", "--config", cfg, "--output", out, "--final")

    merged = json.loads(out.read_text(encoding="utf-8"))
    assert [s["image"] for s in merged["slides"]] == [f"assets/ppt-{i:03d}.png" for i in range(1, 5)]


def test_refuses_to_overwrite_an_existing_output(run, tmp_path):
    cfg_parts = two_parts(tmp_path)
    cfg = write_json(tmp_path / "merge.json", {"title": "t", "duration_ms": 1, "coverage": {},
                                              "parts": [{"tag": t, "manifest": str(m)} for t, m in cfg_parts]})
    out = tmp_path / "exists.json"
    out.write_text("keep", encoding="utf-8")

    code, payload, stdout, stderr = run("merge_segment_manifests.py", "--config", cfg, "--output", out)

    assert code != 0 and out.read_text(encoding="utf-8") == "keep"


def with_coverage(manifest, gaps):
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["coverage"] = {"capture_coverage": "incomplete" if gaps else "complete", "gaps": gaps}
    manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return manifest


def test_part_gaps_are_joined_when_the_config_coverage_has_no_gaps(run, tmp_path):
    (tag1, m1), (tag2, m2) = two_parts(tmp_path)
    with_coverage(m1, [{"start_ms": 0, "end_ms": 300, "reason": "片头"}])
    with_coverage(m2, [{"start_ms": 1200, "end_ms": 1400, "reason": "批次接缝"}])
    config = {"title": "总稿", "duration_ms": 5000,
              "coverage": {"cue_text_review": "visual_reviewed", "word_for_word_manual_review": False, "evidence": "e"},
              "parts": [{"tag": tag1, "manifest": str(m1)}, {"tag": tag2, "manifest": str(m2)}]}
    out = tmp_path / "merged.json"

    code, payload, stdout, err = run("merge_segment_manifests.py", "--config", write_json(tmp_path / "c.json", config),
                                     "--output", out)

    assert code == 0, stdout + err
    cov = json.loads(out.read_text(encoding="utf-8"))["coverage"]
    assert [g["reason"] for g in cov["gaps"]] == ["片头", "批次接缝"]
    assert cov["capture_coverage"] == "incomplete"


def test_output_parent_directory_is_created(run, tmp_path):
    config = write_json(tmp_path / "c.json", {"title": "t", "duration_ms": 5000, "coverage": {"gaps": []},
                                              "parts": [{"tag": t, "manifest": str(m)} for t, m in two_parts(tmp_path)]})
    out = tmp_path / "doc" / "manifest.json"

    code, payload, stdout, err = run("merge_segment_manifests.py", "--config", config, "--output", out, "--final")

    assert code == 0, stdout + err
    assert out.exists()


def test_suggest_lists_repeated_titles_without_writing_output(run, tmp_path):
    m1 = part(tmp_path, "p1", ["a1", "a2"], [("c1", 0, "a1")])
    m2 = part(tmp_path, "p2", ["a2", "b2"], [("c1", 1000, "b2")])
    for path, titles in ((m1, ["目录", "收益"]), (m2, ["收益", "目录"])):
        data = json.loads(path.read_text(encoding="utf-8"))
        for slide, title in zip(data["slides"], titles):
            slide["title"] = title
        data["slides"][0]["id"] = path.parent.name + "-1"
        data["slides"][1]["id"] = path.parent.name + "-2"
        data["cues"] = []
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    config = write_json(tmp_path / "c.json", {"title": "t", "duration_ms": 5000, "coverage": {"gaps": []},
                                              "parts": [{"tag": "x", "manifest": str(m1)}, {"tag": "y", "manifest": str(m2)}]})

    code, payload, stdout, err = run("merge_segment_manifests.py", "--config", config, "--suggest")

    assert code == 0, stdout + err
    assert payload["merge"] == {"p2-1": "p1-2", "p2-2": "p1-1"}
    assert [s["kind"] for s in payload["suggestions"]] == ["boundary", "same_title"]
