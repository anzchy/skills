#!/usr/bin/env python3
"""Time-labelled contact sheets of the video area, for deciding logical PPT pages and choosing frames.

Samples the first frame of every --every-ms bucket from a time-ordered frame-index.jsonl, adds the frame after each
whole-slide change from detect_slide_changes.py output (--changes) when it is at least --min-gap-ms from every other frame, crops each frame to the video area and tiles them
--per-sheet to a sheet. Every thumbnail is labelled `H:MM:SS batch:frame_index`; that label is what a page decision
uses to name its frame. index.json maps each label to its frame path, time and sheet. The output directory must be new.
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COLUMNS = 3
THUMB_WIDTH = 620
LABEL_HEIGHT = 34


def timestamp(ms):
    seconds = ms // 1000
    return f"{seconds // 3600}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def pick_frames(rows, every_ms, change_times, min_gap_ms):
    chosen, seen_buckets = {}, set()
    for row in rows:
        bucket = row["video_ms"] // every_ms
        if bucket not in seen_buckets:
            seen_buckets.add(bucket)
            chosen[row["video_ms"]] = row
    for moment in change_times:
        after = next((r for r in rows if r["video_ms"] >= moment), None)
        if after and all(abs(after["video_ms"] - t) >= min_gap_ms for t in chosen):
            chosen[after["video_ms"]] = after
    return [chosen[t] for t in sorted(chosen)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frame-index", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--every-ms", type=int, default=6000)
    parser.add_argument("--per-sheet", type=int, default=12)
    parser.add_argument("--min-gap-ms", type=int, default=3000, help="a slide change adds a frame only this far from the others")
    parser.add_argument("--crop", default="100,198,2040,1278", help="x1,y1,x2,y2 video area in the raw frame")
    parser.add_argument("--changes", type=Path, help="detect_slide_changes.py output; whole-slide changes add frames")
    args = parser.parse_args()
    if args.output_dir.exists():
        sys.exit(f"{args.output_dir} already exists; use a new directory")

    rows = [json.loads(line) for line in args.frame_index.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows.sort(key=lambda r: r["video_ms"])
    changes = []
    if args.changes:
        changes = [c["time_ms"] for c in json.loads(args.changes.read_text(encoding="utf-8")).get("changes", [])
                   if c.get("kind") == "slide"]
    frames = pick_frames(rows, args.every_ms, changes, args.min_gap_ms)
    crop = tuple(int(v) for v in args.crop.split(","))
    thumb_height = round((crop[3] - crop[1]) * THUMB_WIDTH / (crop[2] - crop[0]))
    cell_height = thumb_height + LABEL_HEIGHT
    font = ImageFont.load_default(size=24)

    args.output_dir.mkdir(parents=True)
    mapping = []
    for start in range(0, len(frames), args.per_sheet):
        group = frames[start:start + args.per_sheet]
        name = f"sheet-{start // args.per_sheet + 1:02d}.jpg"
        rows_count = -(-len(group) // COLUMNS)
        sheet = Image.new("RGB", (COLUMNS * THUMB_WIDTH, rows_count * cell_height), "white")
        draw = ImageDraw.Draw(sheet)
        for position, row in enumerate(group):
            thumb = Image.open(row["source"]).convert("RGB").crop(crop).resize((THUMB_WIDTH, thumb_height))
            x, y = (position % COLUMNS) * THUMB_WIDTH, (position // COLUMNS) * cell_height
            label = f"{row['batch']}:{row['frame_index']}"
            draw.text((x + 6, y + 4), f"{timestamp(row['video_ms'])}  {label}", fill=(200, 0, 0), font=font)
            sheet.paste(thumb, (x, y + LABEL_HEIGHT))
            mapping.append({"video_ms": row["video_ms"], "label": label, "source": row["source"], "sheet": name})
        sheet.save(args.output_dir / name, quality=88)
    (args.output_dir / "index.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"frames": len(mapping), "sheets": -(-len(frames) // args.per_sheet), "output": str(args.output_dir)}))


if __name__ == "__main__":
    main()
