#!/usr/bin/env python3
"""Flag reader transcriptions that the OCR evidence argues against, for a visual re-check.

Readers of subtitle sheets tend to anchor on the candidate text they are shown. Two machine checks catch most of it:

  contradicts_mobile_vision  mobile and Vision OCR agree (after removing interface noise and punctuation), but the
                             read text differs from them. Two independent engines agreeing is strong evidence.
  server_only                the read text equals the server reading while neither mobile nor Vision supports it:
                             the reader probably copied a server look-alike error (今大, 风灭轮, 币值 ...).

Inputs: the reader items file ({"items": [{n, cand, read}]}) numbered by sheets-rev/candidates.txt, the events JSONL
with `mobile` / `server` (review-candidates.jsonl) and the vision_events.py JSONL. DROP/UNCERTAIN reads are skipped.
Output: {"flags": [{n, id, read, mobile, server, vision, reasons}]}; never overwritten. A flag is a prompt to zoom on
the raw frame, not a verdict: the image decides.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify_events import clean, norm, read_jsonl  # noqa: E402


def key(text):
    return norm(clean(text))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reads", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--vision", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    ids = {}
    for line in args.candidates.read_text(encoding="utf-8").splitlines():
        parts = line.split(" ", 2)
        if len(parts) >= 2:
            ids[int(parts[0])] = parts[1]
    events = {row["id"]: row for row in read_jsonl(args.events)}
    vision = {row["id"]: row.get("vision") or "" for row in read_jsonl(args.vision)}
    items = json.loads(args.reads.read_text(encoding="utf-8"))["items"]
    flags = []
    for item in items:
        read = item["read"]
        eid = ids.get(item["n"])
        if read in ("DROP", "UNCERTAIN") or eid not in events:
            continue
        ev = events[eid]
        m, s, v, r = key(ev.get("mobile")), key(ev.get("server")), key(vision.get(eid)), key(read)
        reasons = []
        if m and m == v and r != m:
            reasons.append("contradicts_mobile_vision")
        if r == s and s != m and s != v:
            reasons.append("server_only")
        if reasons:
            flags.append({"n": item["n"], "id": eid, "read": read, "mobile": ev.get("mobile"),
                          "server": ev.get("server"), "vision": vision.get(eid), "reasons": reasons})
    args.output.write_text(json.dumps({"flags": flags}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"items": len(items), "flagged": len(flags)}))


if __name__ == "__main__":
    sys.exit(main())
