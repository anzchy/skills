#!/usr/bin/env python3
"""Keep only the subtitle events that start inside [start_ms, end_ms) from a merged events jsonl.

A segment is indexed with margin on both sides so events at its edges are complete; the margin events belong to the
neighbouring segment and are dropped here.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--start-ms", required=True, type=int)
    parser.add_argument("--end-ms", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    rows = [json.loads(line) for line in args.events.read_text(encoding="utf-8").splitlines() if line.strip()]
    kept = [row for row in rows if args.start_ms <= row["start_ms"] < args.end_ms]
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in kept), encoding="utf-8")
    print(json.dumps({"events": len(rows), "in_range": len(kept)}))


if __name__ == "__main__":
    main()
