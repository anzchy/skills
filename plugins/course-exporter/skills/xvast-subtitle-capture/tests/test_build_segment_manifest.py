import json

import pytest
from conftest import write_json
from test_measure_bounds import synthetic_frame


def event(index, start, end, text, frame):
    return {"id": f"ocr-{index:06d}", "start_ms": start, "end_ms": end, "server": text, "mobile": text,
            "frame": str(frame)}


def project(tmp_path, events, review=None, slides=None, ranges=None, end_ms=10000, **cfg_extra):
    root = tmp_path / "proj"
    seg = root / "video" / ".raw" / "seg-1"
    (seg / "ocr").mkdir(parents=True)
    frame = synthetic_frame(root / "f.png")
    rows = [event(i, s, e, t, frame) for i, (s, e, t) in enumerate(events, 1)]
    (seg / "ocr" / "event-server.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    write_json(seg / "review.json", review or {"corrections": {}, "drop": []})
    config = {"seg_dir": "video/.raw/seg-1", "out_dir": "video/.staging", "end_ms": end_ms, "title": "段",
              "coverage": {"capture_coverage": "complete"},
              "ranges": ranges or [[0, "s1"]],
              "slides": slides or [{"id": "s1", "title": "第一页", "frame": str(frame), "first_seen": 0}], **cfg_extra}
    cfg = write_json(tmp_path / "cfg.json", config)
    return root, cfg


def build(run, root, cfg):
    code, payload, out, err = run("build_segment_manifest.py", "--config", cfg, "--project-root", root)
    manifest = root / "video" / ".staging" / "manifest.json"
    return code, out, err, (json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else None)


def test_cues_take_the_slide_whose_range_contains_their_start(run, tmp_path):
    slides = [{"id": "s1", "title": "一", "frame": None, "first_seen": 0}, {"id": "s2", "title": "二", "frame": None, "first_seen": 5000}]
    root, cfg = project(tmp_path, [(0, 900, "甲"), (6000, 6900, "乙")], ranges=[[0, "s1"], [5000, "s2"]])
    frame = str(root / "f.png")
    for s in slides:
        s["frame"] = frame
    data = json.loads(cfg.read_text(encoding="utf-8")); data["slides"] = slides; cfg.write_text(json.dumps(data), encoding="utf-8")

    code, out, err, m = build(run, root, cfg)

    assert code == 0, out + err
    assert [(c["text"], c["slide_id"]) for c in m["cues"]] == [("甲", "s1"), ("乙", "s2")]


def test_review_corrections_are_applied_with_an_event_level_record(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "找们开始")], review={"corrections": {"ocr-000001": "我们开始"}, "drop": []})

    code, out, err, m = build(run, root, cfg)

    cue = m["cues"][0]
    assert cue["text"] == "我们开始"
    assert cue["correction"]["before"] == "找们开始" and cue["correction"]["after"] == "我们开始"
    assert cue["review"] == "verified"


def test_dropped_events_are_removed(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲"), (1000, 1900, "W")], review={"corrections": {}, "drop": ["ocr-000002"]})

    code, out, err, m = build(run, root, cfg)

    assert [c["text"] for c in m["cues"]] == ["甲"]


def test_a_repeated_text_within_1500ms_becomes_one_cue_covering_both(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲"), (1500, 2400, "甲"), (6000, 6500, "甲")])

    code, out, err, m = build(run, root, cfg)

    assert [(c["start_ms"], c["end_ms"]) for c in m["cues"]] == [(0, 2400), (6000, 6500)]
    assert m["cues"][0]["ocr_event_ids"] == ["ocr-000001", "ocr-000002"]


def test_cue_ends_are_cut_at_the_segment_end(run, tmp_path):
    root, cfg = project(tmp_path, [(9500, 11000, "甲")], end_ms=10000)

    code, out, err, m = build(run, root, cfg)

    assert m["cues"][0]["end_ms"] == 10000


def test_blank_events_are_skipped_and_zero_length_cues_get_a_minimum_length(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 0, "甲"), (2000, 2500, "  ")])

    code, out, err, m = build(run, root, cfg)

    assert [(c["text"], c["end_ms"] - c["start_ms"]) for c in m["cues"]] == [("甲", 500)]


def test_slide_geometry_is_measured_from_the_chosen_frame(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲")])

    code, out, err, m = build(run, root, cfg)

    slide = m["slides"][0]
    assert slide["crop_review"]["slide_bounds"] == [60, 40, 340, 230]
    assert slide["viewport_review"]["video_content_bounds"] == [20, 20, 380, 260]
    assert slide["crop_box"] == [60, 40, 340, 260]  # slide edges, down to the video bottom so the subtitle stays whole
    assert slide["image_review"] == "complete" and slide["crop_review"]["bottom_edge"] == "verified_full"
    assert slide["subtitle_bounds"][1] >= 20


def test_a_fallback_slide_records_reason_and_gaps_and_never_claims_full_edges(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲")])
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data["slides"][0].update(fallback="字幕压住横轴", gaps=["横轴刻度被遮挡"], type="editor_canvas", crop_box=[20, 20, 380, 260])
    cfg.write_text(json.dumps(data), encoding="utf-8")

    code, out, err, m = build(run, root, cfg)

    slide = m["slides"][0]
    assert slide["image_review"] == "fallback_original" and slide["candidate_type"] == "editor_canvas"
    assert slide["fallback_reason"] == "字幕压住横轴" and slide["known_crop_gaps"] == ["横轴刻度被遮挡"]
    assert slide["fallback_preserves_core_content"] is True
    assert "bottom_edge" not in slide["crop_review"] and slide["crop_box"] == [20, 20, 380, 260]


def test_a_cue_that_falls_in_no_slide_range_is_an_error_not_a_silent_loss(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲")], ranges=[[0, "missing"]])

    code, out, err, m = build(run, root, cfg)

    assert code != 0 and "missing" in out + err and m is None


def test_merge_keys_fold_a_range_label_into_another_slide(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲"), (6000, 6900, "乙")], ranges=[[0, "s1"], [5000, "s1-again"]],
                        merge_keys={"s1-again": "s1"})

    code, out, err, m = build(run, root, cfg)

    assert {c["slide_id"] for c in m["cues"]} == {"s1"}


def test_the_config_must_not_overwrite_an_existing_manifest(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲")])
    build(run, root, cfg)

    code, out, err, m = build(run, root, cfg)

    assert code != 0


def test_uncertain_events_make_their_cue_uncertain(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲"), (6000, 6900, "乙")],
                        review={"corrections": {}, "drop": [], "uncertain": ["ocr-000002"]})

    code, out, err, m = build(run, root, cfg)

    assert code == 0, out + err
    assert [c["review"] for c in m["cues"]] == ["verified", "uncertain"]


def test_a_merged_cue_is_uncertain_if_any_of_its_events_is(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲"), (1500, 2400, "甲")],
                        review={"corrections": {}, "drop": [], "uncertain": ["ocr-000002"]})

    code, out, err, m = build(run, root, cfg)

    assert len(m["cues"]) == 1 and m["cues"][0]["review"] == "uncertain"


def test_review_basis_separates_ocr_agreement_from_the_reader(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲"), (6000, 6900, "乙"), (8000, 8900, "丙")],
                        review={"corrections": {"ocr-000002": "乙乙"}, "drop": [], "auto": ["ocr-000001"],
                                "basis": "codex_visual"})

    code, out, err, m = build(run, root, cfg)

    assert code == 0, out + err
    assert [c["review_basis"] for c in m["cues"]] == ["ocr_agreement", "codex_visual", "codex_visual"]


def test_a_merged_cue_counts_as_ocr_agreement_only_if_all_its_events_are(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲"), (1500, 2400, "甲")],
                        review={"corrections": {}, "drop": [], "auto": ["ocr-000001"], "basis": "codex_visual"})

    code, out, err, m = build(run, root, cfg)

    assert m["cues"][0]["review_basis"] == "codex_visual"


def test_cues_have_no_review_basis_when_the_review_names_none(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲")])

    code, out, err, m = build(run, root, cfg)

    assert "review_basis" not in m["cues"][0]


def test_a_slide_can_name_its_video_area_instead_of_having_it_detected(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲")])
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data["slides"][0]["video_bounds"] = [10, 10, 390, 270]
    cfg.write_text(json.dumps(data), encoding="utf-8")

    code, out, err, m = build(run, root, cfg)

    assert code == 0, out + err
    assert m["slides"][0]["viewport_review"]["video_content_bounds"] == [10, 10, 390, 270]


def test_a_no_subtitle_page_records_null_subtitle_bounds_with_a_note(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲")])
    data = json.loads(cfg.read_text(encoding="utf-8"))
    data["slides"][0]["no_subtitle"] = True
    cfg.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    code, out, err, m = build(run, root, cfg)

    assert code == 0, out + err
    slide = m["slides"][0]
    assert slide["subtitle_bounds"] is None
    assert "无烧录字幕" in slide["crop_review"]["subtitle_note"]


def test_crop_evidence_from_the_config_replaces_the_pending_placeholder(run, tmp_path):
    root, cfg = project(tmp_path, [(0, 900, "甲")], crop_evidence="crop-audit 联系表逐页目视")

    code, out, err, m = build(run, root, cfg)

    assert m["slides"][0]["crop_review"]["evidence"] == "crop-audit 联系表逐页目视"
