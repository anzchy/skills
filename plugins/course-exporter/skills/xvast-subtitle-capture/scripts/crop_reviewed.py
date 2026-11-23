#!/usr/bin/env python3
"""Crop reviewed Xvast source frames into a new staging assets directory."""
import argparse
import json
from pathlib import Path

from PIL import Image


def source_path(value, manifest):
    path = Path(value)
    return path if path.is_absolute() else manifest.parent / path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing nonempty output directory: {output}")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    jobs = []
    for number, slide in enumerate(data.get("slides", []), 1):
        if not slide.get("image"):
            continue
        sid = slide.get("id", f"slide-{number}")
        viewport = slide.get("viewport_review") or {}
        review = slide.get("crop_review") or {}
        if viewport.get("source_slide_complete") is not True or viewport.get("scroll_state") != "player_fully_in_view":
            raise ValueError(f"{sid}: source not confirmed complete")
        if review.get("subtitle_edge") != "verified_full":
            raise ValueError(f"{sid}: subtitle edge not reviewed")
        box = slide.get("crop_box")
        if not isinstance(box, list) or len(box) != 4 or not all(type(v) is int for v in box):
            raise ValueError(f"{sid}: invalid crop_box")
        source = source_path(slide["source"], manifest)
        if ".raw" not in source.parts:
            raise ValueError(f"{sid}: source must be an original frame under .raw")
        with Image.open(source) as image:
            width, height = image.size
            if review.get("source_dimensions") != [width, height] or viewport.get("window_dimensions") != [width, height]:
                raise ValueError(f"{sid}: reviewed dimensions differ from source")
            x0, y0, x1, y1 = box
            if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
                raise ValueError(f"{sid}: crop_box outside source")
        jobs.append((source, box, output / f"ppt-{number:03d}.png"))
    output.mkdir(parents=True, exist_ok=True)
    for source, box, destination in jobs:
        with Image.open(source) as image:
            image.crop(tuple(box)).convert("RGB").save(destination)
    print(json.dumps({"images": len(jobs), "output_dir": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
