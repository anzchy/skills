#!/usr/bin/env python3
"""Build a chronological OCR input list and frame-to-video-time index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-root", required=True, help="Directory containing batch */frames.json files.")
    parser.add_argument("--output-list", required=True, help="UTF-8 image path list for PaddleOCR.")
    parser.add_argument("--output-index", required=True, help="Chronological JSONL frame index.")
    parser.add_argument("--start-ms", type=int, default=None)
    parser.add_argument("--end-ms", type=int, default=None)
    parser.add_argument("--include-pending", action="store_true", help="Include pending_manual_review batches.")
    parser.add_argument("--include-invalid", action="store_true")
    return parser.parse_args()


def frame_time_ms(manifest: dict, frame: dict, ordinal: int, count: int) -> int:
    start = int(manifest["video_start_ms"])
    wall_start = manifest.get("wall_start_ms")
    wall_before = frame.get("wall_before_ms") or frame.get("wall_ms")
    rate = float(manifest.get("playback_rate", 1.0))
    if wall_start is not None and wall_before is not None:
        return round(start + (int(wall_before) - int(wall_start)) * rate)
    end = int(manifest.get("video_end_ms", start))
    if count <= 1:
        return start
    return round(start + (end - start) * ordinal / (count - 1))


def main() -> int:
    args = parse_args()
    root = Path(args.batch_root).expanduser().resolve()
    rows: list[dict] = []
    ignored = 0
    for manifest_path in sorted(root.glob("*/frames.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        status = str(manifest.get("status", "unknown"))
        allowed = status == "valid" or (status == "pending_manual_review" and args.include_pending)
        allowed = allowed or (status == "invalid" and args.include_invalid)
        if not allowed:
            ignored += 1
            continue
        frames = manifest.get("frames", [])
        for ordinal, frame in enumerate(frames):
            raw_path = frame.get("path") or frame.get("file") or frame.get("filename")
            if not raw_path:
                continue
            image = Path(raw_path).expanduser()
            if not image.is_absolute():
                image = manifest_path.parent / image
            image = image.resolve()
            if not image.is_file():
                continue
            video_ms = frame_time_ms(manifest, frame, ordinal, len(frames))
            if args.start_ms is not None and video_ms < args.start_ms:
                continue
            if args.end_ms is not None and video_ms > args.end_ms:
                continue
            rows.append(
                {
                    "video_ms": video_ms,
                    "source": str(image),
                    "batch": manifest.get("batch", manifest_path.parent.name),
                    "frame_index": frame.get("index", ordinal + 1),
                    "batch_status": status,
                    "layout_profile": manifest.get("layout_profile"),
                }
            )
    rows.sort(key=lambda row: (row["video_ms"], row["batch"], row["frame_index"]))
    unique: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        if row["source"] not in seen:
            seen.add(row["source"])
            unique.append(row)
    output_list = Path(args.output_list).expanduser().resolve()
    output_index = Path(args.output_index).expanduser().resolve()
    output_list.parent.mkdir(parents=True, exist_ok=True)
    output_index.parent.mkdir(parents=True, exist_ok=True)
    output_list.write_text("".join(f'{row["source"]}\n' for row in unique), encoding="utf-8")
    output_index.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in unique), encoding="utf-8"
    )
    print(json.dumps({"frames": len(unique), "ignored_batches": ignored}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
