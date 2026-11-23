import json

from PIL import Image
from conftest import write_json


def build_case(tmp_path, slide_extra, crop_review_extra):
    raw = tmp_path / ".raw" / "b1"
    raw.mkdir(parents=True)
    Image.new("RGB", (400, 300), "white").save(raw / "frame.jpg")
    assets = tmp_path / "assets"
    assets.mkdir()
    Image.new("RGB", (200, 150), "white").save(assets / "ppt-001.png")
    document = tmp_path / "doc.md"
    document.write_text("![s](assets/ppt-001.png)\n", encoding="utf-8")
    slide = {"id": "p01", "title": "s", "image": "assets/ppt-001.png", "source": str(raw / "frame.jpg"),
             "crop_box": [50, 50, 250, 200], **slide_extra,
             "crop_review": {"slide_bounds": [60, 60, 240, 190], **crop_review_extra}}
    manifest = write_json(tmp_path / "manifest.json", {"slides": [slide]})
    return manifest, document


def audited_subtitle_bounds(run, tmp_path, slide_extra, crop_review_extra):
    manifest, document = build_case(tmp_path, slide_extra, crop_review_extra)
    out = tmp_path / "audit"
    code, payload, stdout, stderr = run("make_crop_audit.py", "--manifest", manifest,
                                        "--document", document, "--output-dir", out)
    assert code == 0, stdout + stderr
    report = json.loads((out / "crop-audit.json").read_text(encoding="utf-8"))
    return report["slides"][0]["subtitle_bounds"]


def test_audit_reports_slide_level_subtitle_bounds(run, tmp_path):
    assert audited_subtitle_bounds(run, tmp_path, {"subtitle_bounds": [80, 160, 220, 190]}, {}) == [80, 160, 220, 190]


def test_audit_falls_back_to_subtitle_bounds_under_crop_review(run, tmp_path):
    assert audited_subtitle_bounds(run, tmp_path, {}, {"subtitle_bounds": [80, 160, 220, 190]}) == [80, 160, 220, 190]
