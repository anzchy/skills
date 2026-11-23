#!/usr/bin/env python3
"""Write the manifest `coverage` block of one time range from frame-index.jsonl files.

Every frame row needs `video_ms` (and `batch`, used to tell batch seams from in-batch holes). Within
[--start-ms, --end-ms) a gap is recorded wherever two consecutive observations, or the range start/end and the
nearest frame, are more than --min-gap-ms apart; subtitles shorter than a gap may be missing there. Output:
{"capture_coverage": "complete"|"incomplete", "cue_text_review", "word_for_word_manual_review": false,
 "evidence", "gaps": [{start_ms, end_ms, reason}]}. --cue-text-review defaults to ocr_only: raise it only after the
cues really were reviewed. Refuses to overwrite --output.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frame-index", required=True, type=Path, nargs="+")
    parser.add_argument("--start-ms", required=True, type=int)
    parser.add_argument("--end-ms", required=True, type=int)
    parser.add_argument("--min-gap-ms", type=int, default=1500)
    parser.add_argument("--head-reason", default="起点前未采集")
    parser.add_argument("--tail-reason", default="末尾未采集")
    parser.add_argument("--cue-text-review", choices=("ocr_only", "visual_reviewed", "manual_exact"), default="ocr_only")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    frames = {}
    for path in args.frame_index:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if args.start_ms <= row["video_ms"] < args.end_ms:
                    frames.setdefault(row["video_ms"], row.get("batch"))
    times = sorted(frames)
    gaps = []
    if not times:
        gaps.append({"start_ms": args.start_ms, "end_ms": args.end_ms, "reason": "本区段没有采集帧"})
    else:
        if times[0] - args.start_ms > args.min_gap_ms:
            gaps.append({"start_ms": args.start_ms, "end_ms": times[0], "reason": args.head_reason})
        for a, b in zip(times, times[1:]):
            if b - a > args.min_gap_ms:
                kind = "批次接缝" if frames[a] != frames[b] else "批内帧间隔"
                gaps.append({"start_ms": a, "end_ms": b,
                             "reason": f"{kind}：{frames[a]} 与 {frames[b]} 相邻两帧相隔 {(b - a) / 1000:g} 秒，期间更短的字幕可能漏采"})
        if args.end_ms - times[-1] > args.min_gap_ms:
            gaps.append({"start_ms": times[-1], "end_ms": args.end_ms, "reason": args.tail_reason})
    total = sum(g["end_ms"] - g["start_ms"] for g in gaps) / 1000
    block = {"capture_coverage": "incomplete" if gaps else "complete", "cue_text_review": args.cue_text_review,
             "word_for_word_manual_review": False,
             "evidence": f"{len(times)} 帧纳入时间轴；间隔阈值 {args.min_gap_ms} ms；{len(gaps)} 处缺口合计 {total:g} 秒",
             "gaps": gaps}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(block, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"gaps": len(gaps), "gap_seconds": total, "frames": len(times)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
