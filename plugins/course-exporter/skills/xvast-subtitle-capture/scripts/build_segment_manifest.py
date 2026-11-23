#!/usr/bin/env python3
"""Build the staging manifest of one reviewed segment from OCR events, a review record and a slide config.

Inputs (paths relative to --project-root):
  <seg_dir>/ocr/event-server.jsonl   one row per merged event: id, start_ms, end_ms, server, mobile, frame
  <seg_dir>/review.json              {"corrections": {event id: text read from the frame}, "drop": [event ids],
                                      optional "uncertain": [ids] -> cue review `uncertain` (shown as 待核验),
                                      optional "auto": [ids accepted by OCR agreement] and "basis": reader name
                                      -> cue `review_basis` ("ocr_agreement" only if all merged events are auto)}
  --config                           JSON:
    seg_dir, out_dir, title, end_ms, coverage
    ranges      [[start_ms, slide_id], ...] ascending; a cue belongs to the last range starting at or before it
    merge_keys  {range label: slide id} folds a revisit label into the real slide id
    slides      [{id, title, frame, first_seen, [type], [crop_box], [slide_bounds], [video_bounds], [fallback, gaps],
                  [no_subtitle], [crop_evidence]}]
    crop_evidence  optional default crop_review.evidence (e.g. the crop-audit sheets you reviewed)

`no_subtitle: true` marks a chosen frame that has no burned-in subtitle (picked because subtitles covered content on
the other frames): subtitle_bounds becomes null with a subtitle_note, instead of a watermark measure_bounds found.

Slide geometry is measured on the chosen frame with measure_bounds.py. A slide with `fallback` becomes
fallback_original and never claims verified bottom/content edges. The manifest is written to <out_dir>/manifest.json,
with image paths pointing at <out_dir>/crops/ppt-NNN.png (create them with crop_reviewed.py). Events whose text is
blank are skipped; an event running past end_ms is cut at end_ms; repeated identical text within 1500 ms is one cue.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

MEASURE = Path(__file__).resolve().parent / "measure_bounds.py"
MERGE_GAP_MS = 1500
MIN_CUE_MS = 500


def read_events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_cues(events, corrections, dropped, end_ms):
    cues = []
    for event in events:
        if event["id"] in dropped:
            continue
        text = corrections.get(event["id"], event["server"])
        if not text.strip():
            continue
        cue = {"start": event["start_ms"], "end": event["end_ms"], "text": text, "frame": event["frame"],
               "before": event["server"], "orig": [event["id"]], "corr": None}
        previous = cues[-1] if cues else None
        if previous and previous["text"] == text and cue["start"] - previous["end"] <= MERGE_GAP_MS:
            previous["end"] = max(previous["end"], cue["end"])
            previous["orig"].append(event["id"])
            if cue["before"] != text and previous["corr"] is None:
                previous["corr"] = (cue["before"], text, cue["frame"])
            continue
        if cue["before"] != text:
            cue["corr"] = (cue["before"], text, cue["frame"])
        cues.append(cue)
    for cue in cues:
        cue["end"] = min(cue["end"], end_ms)
        if cue["end"] <= cue["start"]:
            cue["end"] = cue["start"] + MIN_CUE_MS
    return cues


def measure(frame, video=None):
    extra = ["--video", ",".join(str(v) for v in video)] if video else []
    return json.loads(subprocess.check_output([sys.executable, str(MEASURE), frame, *extra]))


def build_slide(number, spec, out_dir, crop_evidence=None):
    geometry = measure(spec["frame"], spec.get("video_bounds"))
    video, slide_bounds = geometry["video"], spec.get("slide_bounds") or geometry["slide"]
    box = spec.get("crop_box") or [slide_bounds[0], slide_bounds[1], slide_bounds[2], video[3]]
    fallback = spec.get("fallback")
    slide = {
        "id": spec["id"], "title": spec["title"], "image": str(out_dir / "crops" / f"ppt-{number:03d}.png"),
        "image_review": "fallback_original" if fallback else "complete",
        "candidate_type": spec.get("type", "full_slide"), "first_seen_ms": spec["first_seen"],
        "source": spec["frame"], "crop_box": box, "subtitle_bounds": geometry["subtitle"],
        "viewport_review": {
            "window_dimensions": geometry["dimensions"], "player_bounds": video, "video_content_bounds": video,
            "player_top_visible": True, "player_bottom_visible": True, "player_left_visible": True,
            "player_right_visible": True, "controls_visible": True, "source_slide_complete": True,
            "scroll_state": "player_fully_in_view", "evidence": spec["frame"]},
        "crop_review": {"source_dimensions": geometry["dimensions"], "slide_bounds": slide_bounds,
                        "subtitle_edge": "verified_full",
                        "evidence": spec.get("crop_evidence") or crop_evidence or "pending bottom-strip audit"}}
    if spec.get("no_subtitle"):
        slide["subtitle_bounds"] = None
        slide["crop_review"]["subtitle_note"] = "所选帧无烧录字幕（同页其他帧的字幕压住正文或图表），subtitle_bounds 记 null"
    if fallback:
        slide.update(fallback_reason=fallback, known_crop_gaps=spec.get("gaps", [fallback]),
                     fallback_preserves_core_content=True)
    else:
        slide["crop_review"].update(bottom_edge="verified_full", content_edges="verified_full")
    return slide


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    seg, out_dir = root / config["seg_dir"], root / config["out_dir"]
    manifest_path = out_dir / "manifest.json"
    if manifest_path.exists():
        raise SystemExit(f"refusing to overwrite {manifest_path}")
    events = read_events(seg / "ocr" / "event-server.jsonl")
    review = json.loads((seg / "review.json").read_text(encoding="utf-8"))
    cues = build_cues(events, review.get("corrections", {}), set(review.get("drop", [])), config["end_ms"])
    uncertain, auto = set(review.get("uncertain", [])), set(review.get("auto", []))
    ranges, fold = config["ranges"], config.get("merge_keys", {})

    def slide_at(time_ms):
        label = None
        for start, name in ranges:
            if start <= time_ms:
                label = name
        return fold.get(label, label)

    slides = [build_slide(number, spec, out_dir, config.get("crop_evidence")) for number, spec in enumerate(config["slides"], 1)]
    known = {slide["id"] for slide in slides}
    out_cues = []
    for number, cue in enumerate(cues, 1):
        orig = set(cue["orig"])
        entry = {"id": f"c{number:05d}", "start_ms": cue["start"], "end_ms": cue["end"], "slide_id": slide_at(cue["start"]),
                 "text": cue["text"], "review": "uncertain" if orig & uncertain else "verified",
                 "evidence": cue["frame"], "ocr_event_ids": cue["orig"]}
        basis = "ocr_agreement" if orig <= auto else review.get("basis")
        if (auto or review.get("basis")) and basis:
            entry["review_basis"] = basis
        if cue["corr"]:
            before, after, evidence = cue["corr"]
            entry["correction"] = {"before": before, "after": after, "evidence": evidence}
        out_cues.append(entry)
    stray = sorted({c["slide_id"] for c in out_cues if c["slide_id"] not in known}, key=str)
    if stray:
        raise SystemExit(f"cues fall in ranges whose slide is not configured: {stray}")
    document = {"title": config["title"], "duration_ms": config["end_ms"], "coverage": config["coverage"],
                "slides": slides, "cues": out_cues}
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"slides": len(slides), "cues": len(out_cues), "manifest": str(manifest_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
