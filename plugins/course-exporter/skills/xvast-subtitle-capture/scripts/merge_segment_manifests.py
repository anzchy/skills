#!/usr/bin/env python3
"""Merge several reviewed segment manifests into one manifest for a combined document.

Config (JSON):
  title, duration_ms, coverage      the merged document's header (same shape as a manifest)
  parts                             [{"tag": "p", "manifest": "path/manifest.json"}, ...] in time order
  merge                             {dropped_slide_id: kept_slide_id}: the same logical page seen in two parts
  use_image_of                      {slide_id: other_slide_id}: take picture and crop fields from another slide
                                    (e.g. a page first seen as a bare title whose final state is in the next part)

Cue ids get "<tag>-" prefixed because every part numbers its cues from c00001. Slide ids must already be unique.
Without --final, image paths are absolute so build_markdown.py can copy each part's cropped asset; with --final they
are rewritten to assets/ppt-NNN.png for validation next to the built document.

When the config coverage has no "gaps" key, the parts' coverage.gaps are joined in time order (write each part's
block with segment_coverage.py) and capture_coverage becomes incomplete if any gap remains. The output's parent
directory is created. --suggest prints proposed `merge` entries instead of merging: a part's first slide whose title
equals the previous part's last slide ("boundary"), and any later slide repeating an earlier title ("same_title").
These are proposals only: the same title with a different body is a different page, so check each against its frames.
"""
import argparse
import json
from pathlib import Path

PICTURE_FIELDS = ("image", "image_review", "candidate_type", "source", "crop_box", "subtitle_bounds",
                  "viewport_review", "crop_review", "fallback_reason", "known_crop_gaps",
                  "fallback_preserves_core_content")


def load_part(tag, manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    slides = []
    for slide in manifest["slides"]:
        slide = dict(slide)
        if slide.get("image"):
            slide["image"] = str((manifest_path.parent / slide["image"]).resolve())
        slides.append(slide)
    cues = [dict(cue, id=f"{tag}-{cue['id']}") for cue in manifest["cues"]]
    return slides, cues


def suggest(parts):
    seen, suggestions, previous_last = {}, [], None
    for slides in parts:
        for i, slide in enumerate(slides):
            title = " ".join(str(slide.get("title", "")).split())
            if i == 0 and previous_last is not None and previous_last[0] == title:
                suggestions.append({"drop": slide["id"], "keep": previous_last[1], "title": title, "kind": "boundary"})
            elif title in seen:
                suggestions.append({"drop": slide["id"], "keep": seen[title], "title": title, "kind": "same_title"})
            seen.setdefault(title, slide["id"])
        if slides:
            previous_last = (" ".join(str(slides[-1].get("title", "")).split()), slides[-1]["id"])
    keep = {}
    for item in suggestions:
        item["keep"] = keep.get(item["keep"], item["keep"])
        keep[item["drop"]] = item["keep"]
    return {"merge": {item["drop"]: item["keep"] for item in suggestions}, "suggestions": suggestions}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--final", action="store_true", help="write images as assets/ppt-NNN.png")
    parser.add_argument("--suggest", action="store_true", help="print proposed merge entries and exit")
    args = parser.parse_args()
    if args.suggest:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        parts = [load_part(p["tag"], Path(p["manifest"]))[0] for p in config["parts"]]
        print(json.dumps(suggest(parts), ensure_ascii=False, indent=1))
        return
    if args.output is None:
        parser.error("--output is required unless --suggest")
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    by_id, order, cues, part_gaps = {}, [], [], []
    for part in config["parts"]:
        part_gaps.extend(json.loads(Path(part["manifest"]).read_text(encoding="utf-8")).get("coverage", {}).get("gaps", []))
        slides, part_cues = load_part(part["tag"], Path(part["manifest"]))
        for slide in slides:
            if slide["id"] in by_id:
                raise SystemExit(f"duplicate slide id across parts: {slide['id']}")
            by_id[slide["id"]] = slide
            order.append(slide["id"])
        cues.extend(part_cues)
    merge_map = config.get("merge", {})
    for target, source in config.get("use_image_of", {}).items():
        for field in PICTURE_FIELDS:
            if field in by_id[source]:
                by_id[target][field] = by_id[source][field]
            else:
                by_id[target].pop(field, None)
    for cue in cues:
        cue["slide_id"] = merge_map.get(cue.get("slide_id"), cue.get("slide_id"))
    slides = [by_id[sid] for sid in order if sid not in merge_map]
    known = {slide["id"] for slide in slides}
    stray = [cue["id"] for cue in cues if cue.get("slide_id") not in known and cue.get("slide_id") is not None]
    if stray:
        raise SystemExit(f"cues point at unknown slides: {stray[:5]}")
    cues.sort(key=lambda cue: (cue["start_ms"], cue["end_ms"]))
    if args.final:
        for number, slide in enumerate(slides, 1):
            if slide.get("image"):
                slide["image"] = f"assets/ppt-{number:03d}.png"
    coverage = dict(config["coverage"])
    if "gaps" not in coverage:
        coverage["gaps"] = sorted(part_gaps, key=lambda g: (g["start_ms"], g["end_ms"]))
        if coverage["gaps"]:
            coverage["capture_coverage"] = "incomplete"
    merged = {"title": config["title"], "duration_ms": config["duration_ms"], "coverage": coverage,
              "slides": slides, "cues": cues}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"slides": len(slides), "cues": len(cues), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
