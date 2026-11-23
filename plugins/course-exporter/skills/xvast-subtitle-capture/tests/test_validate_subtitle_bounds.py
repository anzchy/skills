import copy

import pytest
from conftest import minimal_manifest, write_json

SLIDE = {
    "id": "p01", "title": "s", "image": "assets/ppt-001.png", "image_review": "complete",
    "candidate_type": "full_slide", "source": "x.jpg", "crop_box": [100, 100, 900, 700],
    "viewport_review": {
        "window_dimensions": [1000, 800], "player_bounds": [50, 50, 950, 750],
        "video_content_bounds": [50, 50, 950, 750],
        "player_top_visible": True, "player_bottom_visible": True,
        "player_left_visible": True, "player_right_visible": True,
        "controls_visible": True, "source_slide_complete": True,
        "scroll_state": "player_fully_in_view", "evidence": "x.jpg"},
    "crop_review": {"source_dimensions": [1000, 800], "slide_bounds": [120, 120, 880, 640],
                    "subtitle_edge": "verified_full", "bottom_edge": "verified_full",
                    "content_edges": "verified_full", "evidence": "sheet"},
}
BOUNDS = [200, 650, 800, 695]


def validate(run, tmp_path, slide, *extra):
    manifest = minimal_manifest(tmp_path)
    data = __import__("json").loads(manifest.read_text(encoding="utf-8"))
    data["slides"] = [slide]
    data["cues"][0]["slide_id"] = "p01"
    write_json(manifest, data)
    return run("validate_capture.py", "--manifest", manifest,
               "--require-crop-review", "--require-viewport-review", *extra)


def slide_with(top=None, nested=None, fallback=False):
    slide = copy.deepcopy(SLIDE)
    if top is not None:
        slide["subtitle_bounds"] = top
    if nested is not None:
        slide["crop_review"]["subtitle_bounds"] = nested
    if fallback:
        slide.update(image_review="fallback_original", fallback_reason="r",
                     known_crop_gaps=["g"], fallback_preserves_core_content=True)
        slide["crop_review"].pop("bottom_edge")
        slide["crop_review"].pop("content_edges")
    return slide


@pytest.mark.parametrize("fallback", [False, True])
def test_top_level_subtitle_bounds_are_accepted(run, tmp_path, fallback):
    code, payload, out, err = validate(run, tmp_path, slide_with(top=BOUNDS, fallback=fallback))
    assert code == 0, out + err


@pytest.mark.parametrize("fallback", [False, True])
def test_subtitle_bounds_under_crop_review_are_accepted(run, tmp_path, fallback):
    code, payload, out, err = validate(run, tmp_path, slide_with(nested=BOUNDS, fallback=fallback))
    assert code == 0, out + err


@pytest.mark.parametrize("fallback", [False, True])
def test_missing_subtitle_bounds_fail(run, tmp_path, fallback):
    code, payload, out, err = validate(run, tmp_path, slide_with(fallback=fallback))
    assert code == 1
    assert any("subtitle_bounds" in e for e in payload["errors"])


def test_nested_subtitle_bounds_outside_crop_box_fail(run, tmp_path):
    code, payload, out, err = validate(run, tmp_path, slide_with(nested=[200, 650, 800, 760]))
    assert code == 1
    assert any("does not contain subtitle_bounds" in e for e in payload["errors"])


def test_malformed_nested_subtitle_bounds_fail(run, tmp_path):
    code, payload, out, err = validate(run, tmp_path, slide_with(nested=[1, 2, 3]))
    assert code == 1
    assert any("invalid subtitle_bounds" in e for e in payload["errors"])
