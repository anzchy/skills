#!/usr/bin/env python3
"""Find the frames of a page whose burned-in subtitle is absent or narrowest, to pick a frame where the subtitle
does not cover slide content (tables, formulas, chart axes).

Reads frame-index.jsonl rows (video_ms, batch, frame_index, source) inside one or more --range A-B (ms, inclusive),
measures the subtitle text width with measure_bounds (0 = no subtitle found), and prints the --top candidates,
narrowest first and then by time: {"candidates": [{label "batch:frame", video_ms, source, subtitle_width, text}]}.
The label is the `frame` value pages.json expects. --sheet writes a labelled contact sheet of the candidates to
look at; it is never overwritten. A width of 0 is a measurement, not a verdict: check the candidate on the sheet.
--video x1,y1,x2,y2 skips the video-area detection when dark slides fool it.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure_bounds import slide_bounds, subtitle_text, video_bounds  # noqa: E402

TILE_W, TILE_H = 640, 360


def measure(path, video=None):
    with Image.open(path) as image:
        gray = np.asarray(image.convert("L"), dtype=np.float32)
    video = video or video_bounds(gray)
    text = subtitle_text(gray, video, slide_bounds(gray, video))
    return video, text


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frame-index", required=True, type=Path, nargs="+")
    parser.add_argument("--range", required=True, action="append", help="A-B in video ms, inclusive")
    parser.add_argument("--top", type=int, default=6)
    parser.add_argument("--step", type=int, default=1, help="measure every Nth frame in the range")
    parser.add_argument("--video", help="x1,y1,x2,y2")
    parser.add_argument("--sheet", type=Path)
    args = parser.parse_args()
    if args.sheet and args.sheet.exists():
        raise SystemExit(f"refusing to overwrite {args.sheet}")
    spans = [tuple(int(v) for v in item.split("-", 1)) for item in args.range]
    video = [int(v) for v in args.video.split(",")] if args.video else None
    rows = []
    for path in args.frame_index:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if any(a <= row["video_ms"] <= b for a, b in spans):
                    rows.append(row)
    rows.sort(key=lambda r: r["video_ms"])
    candidates = []
    for row in rows[::max(1, args.step)]:
        area, text = measure(row["source"], video)
        candidates.append({"label": f"{row['batch']}:{row['frame_index']}", "video_ms": row["video_ms"],
                           "source": row["source"], "subtitle_width": (text[2] - text[0]) if text else 0,
                           "text": text, "video": area})
    candidates.sort(key=lambda c: (c["subtitle_width"], c["video_ms"]))
    top = candidates[:args.top]
    if args.sheet and top:
        cols = 2 if len(top) > 1 else 1
        sheet = Image.new("RGB", (cols * TILE_W, -(-len(top) // cols) * TILE_H), "white")
        for i, cand in enumerate(top):
            with Image.open(cand["source"]) as image:
                x1, y1, x2, y2 = cand["video"]
                tile = image.convert("RGB").crop((x1, y1, x2, y2)).resize((TILE_W, TILE_H))
            draw = ImageDraw.Draw(tile)
            draw.rectangle((0, 0, 330, 16), fill="white")
            draw.text((3, 2), f"{i + 1}. {cand['label']} {cand['video_ms'] / 1000:.1f}s w={cand['subtitle_width']}",
                      fill="red")
            sheet.paste(tile, ((i % cols) * TILE_W, (i // cols) * TILE_H))
        args.sheet.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(args.sheet, quality=85)
    for cand in top:
        cand.pop("video")
    print(json.dumps({"measured": len(candidates), "candidates": top}, ensure_ascii=False))


if __name__ == "__main__":
    main()
