#!/usr/bin/env python3
"""Re-run OCR with the server model on one representative frame per merged subtitle event.

Lists the events whose server text differs from the mobile text, so the visual review can start there.
The result is still ocr_only: agreement between two models does not verify a subtitle.
"""
import argparse
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

from ocr_text_filter import subtitle_pieces

DEFAULT_OCR = str(Path(__file__).resolve().parent / "paddleocr-subtitles")


def read_events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def representative_frame(event):
    evidence = event["evidence"]
    return evidence[len(evidence) // 2]


def run_ocr(command, frames, crop, workdir):
    listing = workdir / "frames.txt"
    listing.write_text("".join(f"{frame}\n" for frame in frames), encoding="utf-8")
    result = workdir / "server-raw.jsonl"
    argv = shlex.split(command) + [str(listing), "-o", str(result), "--model-size", "server",
                                   "--dedupe-threshold", "0"]
    if crop:
        argv += ["--crop", crop]
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0 or not result.exists():
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"OCR command failed with exit code {proc.returncode}")
    rows = [json.loads(line) for line in result.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {Path(row["source"]).as_posix(): row for row in rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True, type=Path, help="merged subtitle-events.jsonl")
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    parser.add_argument("--crop", default=None, help="x1,y1,x2,y2 subtitle crop, same as the mobile run")
    parser.add_argument("--ocr-command", default=DEFAULT_OCR,
                        help="command taking '<list> -o <out> --model-size server ...' (default: paddleocr-subtitles)")
    parser.add_argument("--min-text-height", type=int, default=None,
                        help="drop subtitle-band text whose OCR box is shorter than this many pixels (interface text)")
    args = parser.parse_args()
    for target in (args.output_jsonl, args.output_report):
        if target.exists():
            raise SystemExit(f"refusing to overwrite {target}")
    events = read_events(args.events)
    frames = [representative_frame(event) for event in events]
    with tempfile.TemporaryDirectory() as tmp:
        answers = run_ocr(args.ocr_command, frames, args.crop, Path(tmp))
    rows, disagree = [], []
    for event, frame in zip(events, frames):
        answer = answers.get(Path(frame).as_posix(), {})
        pieces = subtitle_pieces(answer, args.min_text_height)
        server = "".join(text for text, _ in pieces)
        row = {"id": event["id"], "start_ms": event["start_ms"], "end_ms": event["end_ms"],
               "mobile": event["text"], "server": server, "agree": server == event["text"],
               "server_scores": [score for _, score in pieces], "frame": frame}
        rows.append(row)
        if not row["agree"]:
            disagree.append({key: row[key] for key in ("id", "start_ms", "mobile", "server", "frame")})
    args.output_jsonl.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    summary = {"events": len(rows), "agree": len(rows) - len(disagree), "disagree": disagree}
    args.output_report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"events": summary["events"], "agree": summary["agree"],
                      "disagree": len(disagree), "report": str(args.output_report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
