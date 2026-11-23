#!/usr/bin/env python3
"""Prepare one time segment of a video for subtitle review: index -> OCR -> merge -> range -> recheck -> sheets.

Writes everything under <video-dir>/.raw/seg-<name>/ (batches/ symlinks, ocr/, sheets/). Frames are indexed from
`margin` before the start to `margin` after the end so events at the edges are complete; frames of a batch that
a later batch also covers are indexed once, by the later batch (otherwise OCR sees interleaved duplicates). Events are
then filtered to those starting inside [start, end). Only batches named in --batch-list are used, and each must exist
with status valid.

Stages (use --stop-after to run a prefix): index, ocr, merge, range, recheck, sheets.
The OCR crop must be given for layouts other than the default; the skill's auto crop cuts off the subtitle box.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
STAGES = ["index", "ocr", "merge", "range", "recheck", "sheets"]


def listed_batches(raw, list_file):
    names = [line.strip() for line in list_file.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    for name in names:
        manifest = raw / name / "frames.json"
        if not manifest.is_file():
            raise SystemExit(f"listed batch has no frames.json: {name}")
        status = json.loads(manifest.read_text(encoding="utf-8")).get("status")
        if status != "valid":
            raise SystemExit(f"listed batch is not valid ({status}): {name}")
    return names


def trim_batch_overlap(raw, index_path, list_path):
    rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    starts = {b: json.loads((raw / b / "frames.json").read_text(encoding="utf-8"))["video_start_ms"]
              for b in {r["batch"] for r in rows}}
    order = sorted(starts, key=starts.get)
    cut = {b: (starts[order[i + 1]] if i + 1 < len(order) else float("inf")) for i, b in enumerate(order)}
    kept = [r for r in rows if r["video_ms"] < cut[r["batch"]]]
    index_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
    list_path.write_text("".join(r["source"] + "\n" for r in kept), encoding="utf-8")
    return len(rows), len(kept)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video-dir", required=True, type=Path, help="directory that holds .raw/")
    parser.add_argument("--name", required=True)
    parser.add_argument("--batch-list", required=True, type=Path)
    parser.add_argument("--start-ms", required=True, type=int)
    parser.add_argument("--end-ms", required=True, type=int, help="exclusive")
    parser.add_argument("--margin-ms", type=int, default=15000)
    parser.add_argument("--crop", default="450,1160,1700,1285", help="OCR crop x1,y1,x2,y2")
    parser.add_argument("--strip-crop", default="450,1175,1700,1285", help="review sheet strip crop")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--min-text-height", type=int, default=None,
                        help="passed to merge and recheck: drop OCR text boxes shorter than this (interface text)")
    parser.add_argument("--per-sheet", type=int, default=16)
    parser.add_argument("--stop-after", choices=STAGES, default="sheets")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raw = args.video_dir.resolve() / ".raw"
    seg = raw / f"seg-{args.name}"
    ocr = seg / "ocr"
    py = sys.executable
    commands = {
        "index": [py, str(SCRIPTS / "build_paddleocr_frame_index.py"), "--batch-root", str(seg / "batches"),
                  "--output-list", str(ocr / "frames.txt"), "--output-index", str(ocr / "frame-index.jsonl"),
                  "--start-ms", str(args.start_ms - args.margin_ms), "--end-ms", str(args.end_ms + args.margin_ms)],
        "ocr": [str(SCRIPTS / "paddleocr-parallel"), str(ocr / "frames.txt"), "-o", str(ocr / "mobile"),
                "--workers", str(args.workers), "--crop", args.crop, "--dedupe-threshold", "0.01"],
        "merge": [py, str(SCRIPTS / "merge_paddleocr_timeline.py"), "--frame-index", str(ocr / "frame-index.jsonl"),
                  "--ocr-results", "<ocr/mobile-part-*.jsonl>", "--output-jsonl", str(ocr / "subtitle-events.jsonl"),
                  "--output-markdown", str(ocr / "subtitle-candidates.md")],
        "range": [py, str(SCRIPTS / "filter_events_in_range.py"), "--events", str(ocr / "subtitle-events.jsonl"),
                  "--start-ms", str(args.start_ms), "--end-ms", str(args.end_ms), "--output", str(ocr / "events-in-range.jsonl")],
        "recheck": [py, str(SCRIPTS / "recheck_events_with_server.py"), "--events", str(ocr / "events-in-range.jsonl"),
                    "--output-jsonl", str(ocr / "event-server.jsonl"), "--output-report", str(ocr / "disagree.json"),
                    "--crop", args.crop],
        "sheets": [py, str(SCRIPTS / "make_cue_review_sheets.py"), "--candidates", str(ocr / "event-server.jsonl"),
                   "--output-dir", str(seg / "sheets"), "--strip-crop", args.strip_crop, "--per-sheet", str(args.per_sheet)],
    }
    if args.min_text_height:
        for stage in ("merge", "recheck"):
            commands[stage] += ["--min-text-height", str(args.min_text_height)]
    wanted = STAGES[:STAGES.index(args.stop_after) + 1]
    if args.dry_run:
        print(json.dumps({"segment": str(seg), "stages": [{"stage": s, "command": commands[s]} for s in STAGES]}, ensure_ascii=False))
        return
    names = listed_batches(raw, args.batch_list)
    if (ocr / "frame-index.jsonl").exists():
        raise SystemExit(f"segment already prepared: {seg} (use a new --name)")
    (seg / "batches").mkdir(parents=True, exist_ok=True)
    ocr.mkdir(parents=True, exist_ok=True)
    for name in names:
        link = seg / "batches" / name
        if not link.exists():
            os.symlink(os.path.join("..", "..", name), link)
    summary = {}
    for stage in wanted:
        command = commands[stage]
        if stage == "merge":
            parts = sorted(str(p) for p in ocr.glob("mobile-part-*.jsonl"))
            if not parts:
                raise SystemExit("no mobile-part-*.jsonl found; run the ocr stage first")
            at = command.index("<ocr/mobile-part-*.jsonl>")
            command = command[:at] + parts + command[at + 1:]
        proc = subprocess.run(command, capture_output=True, text=True)
        (ocr / f"{stage}.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr or proc.stdout)
            raise SystemExit(f"stage {stage} failed with exit code {proc.returncode}")
        if stage == "index":
            before, after = trim_batch_overlap(raw, ocr / "frame-index.jsonl", ocr / "frames.txt")
            summary["frames"] = {"indexed": before, "after_overlap_trim": after}
    print(json.dumps({"segment": str(seg), "stages_done": wanted, **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
