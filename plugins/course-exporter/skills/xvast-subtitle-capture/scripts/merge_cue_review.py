#!/usr/bin/env python3
"""Merge reader outputs for one segment into the review.json that build_segment_manifest.py reads.

Reader files (later files override earlier ones, per event):
  items format   {"items": [{"n": sheet number, "cand": candidate text copied from candidates.txt, "read": text | "DROP" | "UNCERTAIN"}]}
                 `cand` is checked against <seg>/sheets-rev/candidates.txt (similarity >= 0.7): a mismatch means the reader was misaligned
                 with the sheet numbering and the whole run is rejected. Every candidate must be covered.
  list format    {"corrections": {id: text}, "drop": [ids], "uncertain": [ids]}
                 an id in more than one list is not trusted and becomes uncertain; ids absent from the review set
                 are ignored and reported; unlisted ids are reported as `unread_ids` (nothing proves they were read).

Events that OCR agreement accepted (classes three_model / two_model in ocr/vision-classified.json) are written to `auto`.
Output: {corrections, drop, uncertain, auto, basis, method, read_count, unread_ids, ignored_ids}; never overwritten.
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

ALIGNED = 0.7   # a copied candidate this close to candidates.txt is the same cue; a shifted one is not
PUNCT = r"[\s，。,.！!？?：:、；;“”\"'（）()\-—…·]"


def norm(text):
    return re.sub(PUNCT, "", text or "")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seg-dir", required=True, type=Path)
    parser.add_argument("--reviews", required=True, nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--basis", default="codex_visual", help="review_basis for cues that were read, not OCR-accepted")
    parser.add_argument("--method", default="codex gpt-6-luna medium，逐条读拼图（字幕条缩略图，未放大原帧）")
    args = parser.parse_args()
    if args.output.exists():
        sys.exit(f"{args.output} already exists; refusing to overwrite")

    candidates = {}
    for line in (args.seg_dir / "sheets-rev" / "candidates.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split(None, 2)
        if len(parts) >= 2:
            candidates[int(parts[0])] = (parts[1], parts[2] if len(parts) > 2 else "")
    review_ids = {event_id for event_id, _ in candidates.values()}

    corrections, drop, uncertain, ignored = {}, set(), set(), set()
    covered, explicit, strict = set(), 0, True
    for path in args.reviews:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "items" in data:
            for item in data["items"]:
                number = item["n"]
                if number not in candidates:
                    ignored.add(f"n{number}")
                    continue
                event_id, cand = candidates[number]
                if difflib.SequenceMatcher(None, norm(item["cand"]), norm(cand)).ratio() < ALIGNED:
                    sys.exit(f"{path}: item {number} candidate does not match candidates.txt; the reader was misaligned")
                corrections.pop(event_id, None)
                drop.discard(event_id)
                uncertain.discard(event_id)
                covered.add(event_id)
                explicit += 1
                read = item["read"]
                if read == "DROP":
                    drop.add(event_id)
                elif read == "UNCERTAIN":
                    uncertain.add(event_id)
                elif norm(read) != norm(cand):
                    corrections[event_id] = read
        else:
            strict = False
            listed = list(data.get("corrections", {})) + list(data.get("drop", [])) + list(data.get("uncertain", []))
            for event_id in set(listed) - review_ids:
                ignored.add(event_id)
            for event_id in set(listed) & review_ids:
                corrections.pop(event_id, None)
                drop.discard(event_id)
                uncertain.discard(event_id)
                covered.add(event_id)
                lists = ((event_id in data.get("corrections", {})) + (event_id in data.get("drop", []))
                         + (event_id in data.get("uncertain", [])))
                if lists > 1:
                    uncertain.add(event_id)
                elif event_id in data.get("corrections", {}):
                    corrections[event_id] = data["corrections"][event_id]
                elif event_id in data.get("drop", []):
                    drop.add(event_id)
                else:
                    uncertain.add(event_id)
    unread = sorted(review_ids - covered)
    if strict and unread:
        sys.exit(f"unread candidates: {unread[:5]}{' ...' if len(unread) > 5 else ''} ({len(unread)} in total)")

    classified = json.loads((args.seg_dir / "ocr" / "vision-classified.json").read_text(encoding="utf-8"))
    auto = [row["id"] for row in classified if row["class"] in ("three_model", "two_model")]
    result = {"corrections": corrections, "drop": sorted(drop), "uncertain": sorted(uncertain), "auto": auto,
              "basis": args.basis, "method": args.method, "read_count": explicit,
              "unread_ids": unread, "ignored_ids": sorted(ignored)}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"corrections": len(corrections), "drop": len(drop), "uncertain": len(uncertain), "auto": len(auto),
                      "unread": len(unread), "ignored": len(ignored)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
