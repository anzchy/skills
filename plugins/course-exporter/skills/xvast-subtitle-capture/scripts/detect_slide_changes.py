#!/usr/bin/env python3
"""Find slide changes in a time-ordered frame index by differencing the slide region of consecutive frames.

A frame that flips back to the state two frames earlier is treated as flicker (the presenter or the player
alternating between two pages), not as a slide change. Subtitle bands and controls are excluded via --region.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

SIGNATURE_SIZE = (96, 54)


def read_index(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return sorted(rows, key=lambda row: row["video_ms"])


def thin(rows, min_gap_ms):
    kept, last = [], None
    for row in rows:
        if last is None or row["video_ms"] - last >= min_gap_ms:
            kept.append(row)
            last = row["video_ms"]
    return kept


def signature(source, region):
    with Image.open(source) as image:
        gray = image.convert("L").crop(region).resize(SIGNATURE_SIZE)
    return np.asarray(gray, dtype=np.float32)


def distance(a, b):
    return float(np.abs(a - b).mean())


def classify(times, sigs, threshold):
    """Return (changes, flicker_ranges) as index lists. Change i means frame i differs from frame i-1."""
    changed = [i for i in range(1, len(sigs)) if distance(sigs[i], sigs[i - 1]) > threshold]
    flicker_idx = set()
    for i in changed:
        returns_to_previous = i >= 2 and distance(sigs[i], sigs[i - 2]) <= threshold
        next_returns = i + 1 < len(sigs) and i - 1 >= 0 and distance(sigs[i + 1], sigs[i - 1]) <= threshold \
            and i + 1 in changed
        if returns_to_previous or next_returns:
            flicker_idx.add(i)
    ranges, current = [], []
    for i in sorted(flicker_idx):
        if current and i - current[-1] > 1:
            ranges.append(current)
            current = []
        current.append(i)
    if current:
        ranges.append(current)
    return [i for i in changed if i not in flicker_idx], ranges


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame-index", required=True, type=Path)
    parser.add_argument("--region", required=True, help="x1,y1,x2,y2 slide area without subtitle or controls")
    parser.add_argument("--threshold", type=float, default=1.5, help="mean abs gray difference that counts as change")
    parser.add_argument("--slide-threshold", type=float, default=5.0,
                        help="changes at or above this are whole-slide changes; smaller ones are content (bullet) changes")
    parser.add_argument("--min-gap-ms", type=int, default=300, help="drop frames closer than this to the previous kept one")
    args = parser.parse_args()
    region = tuple(int(part) for part in args.region.split(","))
    rows = thin(read_index(args.frame_index), args.min_gap_ms)
    if not rows:
        raise SystemExit("frame index is empty")
    times = [row["video_ms"] for row in rows]
    sigs = [signature(row["source"], region) for row in rows]
    real, ranges = classify(times, sigs, args.threshold)
    changes = []
    for i in real:
        diff = distance(sigs[i], sigs[i - 1])
        changes.append({"time_ms": times[i], "diff": round(diff, 2), "frame": rows[i]["source"],
                        "kind": "slide" if diff >= args.slide_threshold else "content"})
    flicker = [{"start_ms": times[group[0]], "end_ms": times[group[-1]], "changes": len(group)} for group in ranges]
    segments, start = [], 0
    for i, change in zip(real, changes):
        if change["kind"] == "slide":
            segments.append((start, i - 1))
            start = i
    segments.append((start, len(rows) - 1))
    payload = {"frames": len(rows), "changes": changes, "flicker": flicker,
               "segments": [{"start_ms": times[a], "end_ms": times[b]} for a, b in segments]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
