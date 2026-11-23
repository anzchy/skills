#!/usr/bin/env python3
"""Tell the look-alike filler glyphs 呃 and 呢 apart in burned-in subtitles by template matching.

OCR engines and readers of downscaled strips confuse 呃 and 呢. The subtitles of one video are rendered in one
font at one size, so a glyph cut from a frame matches every other occurrence almost exactly (normalised
correlation ~0.97-1.0). How close the other filler glyph scores depends on the video's font: ~0.88-0.91 in
风火轮2周年, ~0.34 in 风火轮3; ordinary characters stayed below ~0.7. Check both templates against each other on
every new video before trusting the 0.85 threshold.

  detect   events JSONL (id, frame) -> one row per event: {id, fillers, matches}
           `fillers` is the left-to-right sequence of detected filler glyphs, e.g. "呃呢".
           --template LABEL=PATH:x0,y0,x1,y1 cuts a template from a raw frame (give one per glyph);
           --band x0,y0,x1,y1 is the subtitle text band searched in every frame.
  apply    reader items file ({"items": [{n, cand, read}]}, numbered by sheets-rev/candidates.txt) + detections
           -> a new items file whose filler characters follow the detected glyphs. Only when the read text holds
           exactly as many 呃/呢 as were detected are they replaced, in order; otherwise the item is left as read
           and listed under `mismatch` in --report for a visual check. DROP/UNCERTAIN items are not touched.
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np


def box(text):
    values = [int(v) for v in text.split(",")]
    if len(values) != 4:
        raise argparse.ArgumentTypeError("expected x0,y0,x1,y1")
    return values


def template(text):
    label, _, rest = text.partition("=")
    path, _, coords = rest.rpartition(":")
    if not label or not path:
        raise argparse.ArgumentTypeError("expected LABEL=PATH:x0,y0,x1,y1")
    x0, y0, x1, y1 = box(coords)
    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise argparse.ArgumentTypeError(f"cannot read template frame {path}")
    return label, image[y0:y1, x0:x1]


def scan(path, band, templates, threshold):
    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise SystemExit(f"cannot read frame {path}")
    x0, y0, x1, y1 = band
    strip = image[y0:y1, x0:x1]
    scores = {label: cv2.matchTemplate(strip, tpl, cv2.TM_CCOEFF_NORMED).max(axis=0)
              for label, tpl in templates}
    best = np.max(np.stack(list(scores.values())), axis=0)
    width = min(tpl.shape[1] for _, tpl in templates)
    matches, x = [], 0
    while x < len(best):
        if best[x] < threshold:
            x += 1
            continue
        window = best[x:x + width]
        peak = x + int(np.argmax(window))
        per_label = {label: round(float(s[peak]), 3) for label, s in scores.items()}
        label = max(per_label, key=per_label.get)
        matches.append({"label": label, "x": x0 + peak, "scores": per_label})
        x = peak + width
    return matches


def cmd_detect(args):
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    templates = args.template
    rows = [json.loads(line) for line in args.events.read_text(encoding="utf-8").splitlines() if line.strip()]
    out = []
    for row in rows:
        matches = scan(row["frame"], args.band, templates, args.threshold)
        out.append({"id": row["id"], "fillers": "".join(m["label"] for m in matches), "matches": matches})
    args.output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    print(json.dumps({"events": len(out), "with_fillers": sum(1 for r in out if r["fillers"])}))


FILLERS = "呃呢"


def cmd_apply(args):
    for path in (args.output, args.report):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")
    detected = {}
    for line in args.detections.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            detected[row["id"]] = row["fillers"]
    ids = {}
    for line in args.candidates.read_text(encoding="utf-8").splitlines():
        parts = line.split(" ", 2)
        if len(parts) >= 2:
            ids[int(parts[0])] = parts[1]
    data = json.loads(args.reads.read_text(encoding="utf-8"))
    changed, mismatch = [], []
    for item in data["items"]:
        read = item["read"]
        eid = ids.get(item["n"])
        if read in ("DROP", "UNCERTAIN") or eid not in detected:
            continue
        found = detected[eid]
        have = [c for c in read if c in FILLERS]
        if len(have) != len(found):
            mismatch.append({"n": item["n"], "id": eid, "read": read, "detected": found})
            continue
        glyphs = iter(found)
        fixed = "".join(next(glyphs) if c in FILLERS else c for c in read)
        if fixed != read:
            changed.append({"n": item["n"], "id": eid, "before": read, "after": fixed})
            item["read"] = fixed
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    args.report.write_text(json.dumps({"changed": changed, "mismatch": mismatch}, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(json.dumps({"items": len(data["items"]), "changed": len(changed), "mismatch": len(mismatch)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("detect")
    d.add_argument("--events", required=True, type=Path)
    d.add_argument("--output", required=True, type=Path)
    d.add_argument("--template", required=True, action="append", type=template)
    d.add_argument("--band", default="300,1195,1850,1268", type=box)
    d.add_argument("--threshold", type=float, default=0.85)
    a = sub.add_parser("apply")
    a.add_argument("--detections", required=True, type=Path)
    a.add_argument("--candidates", required=True, type=Path)
    a.add_argument("--reads", required=True, type=Path)
    a.add_argument("--output", required=True, type=Path)
    a.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "detect":
        cmd_detect(args)
    else:
        cmd_apply(args)


if __name__ == "__main__":
    sys.exit(main())
