#!/usr/bin/env python3
"""Merge PaddleOCR part files into chronological subtitle candidate events."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ocr_text_filter import subtitle_pieces


UI_NOISE = re.compile(
    r"邢不行|xbx|oc6bd|English|Accessib|Investigate|Notes|Comments|"
    r"^Line\s+\d+|^Column\s+\d+|Sublime|PowerPoint|AutoSave|of\s+\d+",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame-index", required=True)
    parser.add_argument("--ocr-results", nargs="+", required=True)
    parser.add_argument("--server-review", nargs="*", default=[])
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--output-markdown", required=True)
    parser.add_argument("--block-seconds", type=int, default=120)
    parser.add_argument("--low-confidence", type=float, default=0.70)
    parser.add_argument("--server-accept", type=float, default=0.85)
    parser.add_argument("--min-text-height", type=int, default=None,
                        help="drop subtitle-band text whose OCR box is shorter than this many pixels (interface text)")
    return parser.parse_args()


def read_jsonl(paths: list[str]) -> list[dict]:
    rows: list[dict] = []
    for value in paths:
        path = Path(value).expanduser().resolve()
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
    return rows


def cleaned_text(row: dict, min_height: int | None = None) -> tuple[str, list[float]]:
    pieces: list[str] = []
    scores: list[float] = []
    for text, score in subtitle_pieces(row, min_height):
        text = str(text).strip()
        if text and not UI_NOISE.search(text):
            pieces.append(text)
            scores.append(float(score))
    return "".join(pieces), scores


def format_time(ms: int) -> str:
    total = max(0, ms) // 1000
    return f"{total // 60:02d}:{total % 60:02d}"


def main() -> int:
    args = parse_args()
    index_rows = read_jsonl([args.frame_index])
    time_by_source = {str(Path(row["source"]).resolve()): int(row["video_ms"]) for row in index_rows}
    server_by_source = {
        str(Path(row["source"]).resolve()): row for row in read_jsonl(args.server_review)
    }
    observations: list[dict] = []
    missing_index = 0
    for row in read_jsonl(args.ocr_results):
        source = str(Path(row.get("source", "")).resolve())
        if source not in time_by_source:
            missing_index += 1
            continue
        text, scores = cleaned_text(row, args.min_text_height)
        model = row.get("ocr_model", "PP-OCRv5_mobile")
        mobile_failed = not row.get("ok", False)
        needs_review = mobile_failed or (bool(text) and (not scores or min(scores) < args.low_confidence))
        server = server_by_source.get(source)
        server_requested_for_empty = server is not None and not text
        if server and (needs_review or server_requested_for_empty):
            server_text, server_scores = cleaned_text(server, args.min_text_height)
            server_average = sum(server_scores) / len(server_scores) if server_scores else 0.0
            if server_text and server_average >= args.server_accept:
                text, scores = server_text, server_scores
                model = server.get("ocr_model", "PP-OCRv5_server")
                needs_review = min(scores) < args.low_confidence
            elif mobile_failed or server_requested_for_empty:
                # This source was explicitly sent to the fallback model but still
                # has no acceptable text. Preserve it as an unresolved observation.
                needs_review = True
        observations.append(
            {
                "video_ms": time_by_source[source],
                "source": source,
                "text": text,
                "scores": scores,
                "ocr_model": model,
                "skipped_duplicate": bool(row.get("skipped_duplicate")),
                "needs_review": needs_review,
            }
        )
    observations.sort(key=lambda item: (item["video_ms"], item["source"]))
    events: list[dict] = []
    active: dict | None = None
    for observation in observations:
        text = observation["text"]
        if observation["skipped_duplicate"]:
            if active:
                active["end_ms"] = observation["video_ms"]
                active["evidence"].append(observation["source"])
            continue
        if not text:
            active = None
            continue
        if active and active["text"] == text:
            active["end_ms"] = observation["video_ms"]
            active["evidence"].append(observation["source"])
            active["scores"].extend(observation["scores"])
            active["needs_review"] = active["needs_review"] or observation["needs_review"]
            if observation["ocr_model"] not in active["ocr_models"]:
                active["ocr_models"].append(observation["ocr_model"])
            continue
        active = {
            "id": f"ocr-{len(events) + 1:06d}",
            "start_ms": observation["video_ms"],
            "end_ms": observation["video_ms"],
            "text": text,
            "review": "ocr_only",
            "needs_review": observation["needs_review"],
            "scores": list(observation["scores"]),
            "ocr_models": [observation["ocr_model"]],
            "evidence": [observation["source"]],
        }
        events.append(active)
    for event in events:
        scores = event.pop("scores")
        event["confidence_min"] = round(min(scores), 4) if scores else None
        event["confidence_mean"] = round(sum(scores) / len(scores), 4) if scores else None

    output_jsonl = Path(args.output_jsonl).expanduser().resolve()
    output_markdown = Path(args.output_markdown).expanduser().resolve()
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_jsonl.write_text(
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events), encoding="utf-8"
    )
    blocks: dict[int, list[dict]] = {}
    block_ms = max(1, args.block_seconds) * 1000
    for event in events:
        blocks.setdefault(event["start_ms"] // block_ms, []).append(event)
    markdown = ["# PaddleOCR 字幕候选时间线", "", "> 审核状态：`ocr_only`。不得直接宣称逐字核验完成。", ""]
    for block, items in sorted(blocks.items()):
        start, end = block * block_ms, (block + 1) * block_ms
        markdown += [f"## {format_time(start)}–{format_time(end)}", ""]
        paragraph = ""
        for event in items:
            fragment = event["text"]
            if len(paragraph) + len(fragment) > 220 and paragraph:
                markdown += [paragraph, ""]
                paragraph = ""
            paragraph += fragment
        if paragraph:
            markdown += [paragraph, ""]
    output_markdown.write_text("\n".join(markdown).rstrip() + "\n", encoding="utf-8")
    summary = {
        "observations": len(observations),
        "events": len(events),
        "needs_review": sum(bool(event["needs_review"]) for event in events),
        "missing_frame_index": missing_index,
        "output_jsonl": str(output_jsonl),
        "output_markdown": str(output_markdown),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if missing_index == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
