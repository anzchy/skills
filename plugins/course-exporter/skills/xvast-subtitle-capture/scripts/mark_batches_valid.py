#!/usr/bin/env python3
"""Mark reviewed capture batches valid: write the batch-level viewport_review and append them to the batch list.

Run it only after you have looked at each batch's first, middle and last frame yourself; --reviewed-by-eye is
required and is recorded as the reviewer, so the claim stays explicit. For every batch the script:
  - picks the first, middle and last frame that is not excluded, and measures the video area with measure_bounds;
  - checks each measurement against the expected layout (--layout NAME=x1,y1,x2,y2; the batch's layout_profile, or
    --layout-segment BATCH:A-B=NAME for frames after a scrollbar shift). A mismatch refuses the batch unless
    --accept-measure BATCH=note explains it (e.g. dark slide content fooling the detection);
  - refuses an `invalid` batch unless --exclude-frames BATCH:A-B drops the bad frames (e.g. playback stopped at
    the end of the video); the original reasons are kept in manual_review.resolved_invalid_reasons;
  - skips batches that are already valid; appends each valid batch to --batch-list once.
Writes nothing for a refused batch. One JSON line per batch; exit code 1 if any batch was refused.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure_bounds import video_bounds  # noqa: E402


def box(text):
    values = [int(v) for v in text.split(",")]
    if len(values) != 4:
        raise argparse.ArgumentTypeError(f"expected x1,y1,x2,y2: {text}")
    return values


def keyed(items, parse=lambda v: v):
    out = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep:
            raise SystemExit(f"expected KEY=VALUE: {item}")
        out[key] = parse(value)
    return out


def frame_span(text):
    batch, sep, span = text.partition(":")
    a, dash, b = span.partition("-")
    if not sep:
        raise SystemExit(f"expected BATCH:A-B: {text}")
    return batch, int(a), int(b or a)


def measure(path):
    with Image.open(path) as image:
        return video_bounds(np.asarray(image.convert("L"), dtype=np.float32))


def frame_files(folder):
    files = {}
    for path in folder.glob("frame-*.*"):
        if path.suffix.lower() in (".jpg", ".jpeg", ".png") and not path.name.startswith(("_", ".")):
            files[int(path.stem.split("-")[1])] = path
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--batches", nargs="+", default=[])
    parser.add_argument("--range", action="append", default=[], help="PREFIX:A-B, e.g. main:22-40")
    parser.add_argument("--layout", action="append", required=True, help="NAME=x1,y1,x2,y2 expected video area")
    parser.add_argument("--layout-segment", action="append", default=[], help="BATCH:A-B=NAME")
    parser.add_argument("--exclude-frames", action="append", default=[], help="BATCH:A-B")
    parser.add_argument("--accept-measure", action="append", default=[], help="BATCH=note")
    parser.add_argument("--reviewed-by-eye", required=True, help="who looked at the frames, and how")
    parser.add_argument("--note", help="extra note stored in viewport_review")
    parser.add_argument("--batch-list", type=Path)
    args = parser.parse_args()
    layouts = keyed(args.layout, box)
    accept = keyed(args.accept_measure)
    names = list(args.batches)
    for item in args.range:
        prefix, a, b = frame_span(item)
        names += [f"{prefix}-{n:03d}" for n in range(a, b + 1)]
    segments, excluded = {}, {}
    for item in args.layout_segment:
        span, _, layout = item.partition("=")
        batch, a, b = frame_span(span)
        if layout not in layouts:
            raise SystemExit(f"unknown layout {layout!r} in {item}")
        segments.setdefault(batch, []).append((a, b, layout))
    for item in args.exclude_frames:
        batch, a, b = frame_span(item)
        excluded.setdefault(batch, set()).update(range(a, b + 1))
    listed = []
    if args.batch_list and args.batch_list.exists():
        listed = [line.strip() for line in args.batch_list.read_text(encoding="utf-8").splitlines() if line.strip()]
    refused = False
    for name in names:
        path = args.raw_root / name / "frames.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        row = {"batch": name}
        status = data.get("status")
        if status == "valid":
            row["status"] = "already_valid"
        elif status == "invalid" and name not in excluded:
            row.update(status="refused", reason=f"batch is invalid {data.get('invalid_reasons')}; pass --exclude-frames")
        elif status not in ("pending_manual_review", "invalid"):
            row.update(status="refused", reason=f"unknown status {status!r}")
        else:
            files = frame_files(args.raw_root / name)
            kept = sorted(i for i in files if i not in excluded.get(name, set()))
            base = data.get("layout_profile")
            spans = segments.get(name, [])

            def layout_of(index):
                return next((lay for a, b, lay in spans if a <= index <= b), base)

            if not kept:
                row.update(status="refused", reason="no frames left")
            else:
                picks = [kept[0], kept[len(kept) // 2], kept[-1]]
                measured = [measure(files[i]) for i in picks]
                expected = [layouts.get(layout_of(i)) for i in picks]
                if None in expected:
                    row.update(status="refused", reason=f"no --layout for {[layout_of(i) for i in picks]}")
                elif measured != expected and name not in accept:
                    row.update(status="refused", reason="measured video area differs from the layout",
                               measured=measured, expected=expected)
                else:
                    main_layout = layout_of(picks[1])
                    review = {"four_edges_visible": True, "player_top_visible": True, "player_bottom_visible": True,
                              "player_left_visible": True, "player_right_visible": True, "controls_visible": True,
                              "scroll_state": "player_fully_in_view", "source_slide_complete": True,
                              "player_bounds": layouts[main_layout], "video_content_bounds": layouts[main_layout],
                              "evidence": [files[i].name for i in picks],
                              "measured_video_bounds_first_mid_last": measured,
                              "controls_note": "控制条所在区域在视口内可见；控制层已自动隐藏，未遮挡字幕。",
                              "reviewer": args.reviewed_by_eye}
                    if name in accept:
                        review["measure_note"] = accept[name]
                    if args.note:
                        review["note"] = args.note
                    if spans:
                        bounds, start, out = sorted(spans), 1, []
                        for a, b, lay in bounds:
                            if a > start:
                                out.append({"frames": [start, a - 1], "layout_profile": base})
                            out.append({"frames": [a, b], "layout_profile": lay})
                            start = b + 1
                        last = max(files)
                        if start <= last:
                            out.append({"frames": [start, last], "layout_profile": base})
                        for item in out:
                            item["video_content_bounds"] = layouts[item["layout_profile"]]
                        review["layout_segments"] = out
                    if name in excluded:
                        manual = data.setdefault("manual_review", {})
                        manual["excluded_frames"] = sorted(excluded[name])
                        if status == "invalid":
                            manual["resolved_invalid_reasons"] = data.get("invalid_reasons", [])
                    data["layout_profile"] = main_layout
                    data["viewport_review"] = review
                    data["status"] = "valid"
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
                    row["status"] = "valid"
        if row["status"] == "refused":
            refused = True
        elif name not in listed:
            listed.append(name)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    if args.batch_list:
        args.batch_list.write_text("".join(f"{n}\n" for n in listed), encoding="utf-8")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
