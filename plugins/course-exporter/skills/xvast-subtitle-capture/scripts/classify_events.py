#!/usr/bin/env python3
"""Classify subtitle events by how far the OCR sources agree, to decide which ones need visual review.

Inputs: an events JSONL with `mobile` and `server` readings (recheck_events_with_server.py output) and the
vision_events.py JSONL. Interface noise (status-bar English, axis date labels) is removed before comparing;
the untouched readings are kept under `raw`.

  three_model    mobile = server = Vision          -> review_basis `ocr_agreement` (accepted without a visual check)
  two_model      server = Vision                   -> review_basis `ocr_agreement`
  forced_review  one of the two above, but the text has 呃/呢 or ASCII letters/digits -> visual review
  needs_review   everything else                   -> visual review

Comparison ignores punctuation and whitespace. `flags` lists `filler` (呃/呢) and `chart_or_digits`.
OCR agreement is not human verification: the document must say how many cues were accepted this way.
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

NOISE = [
    r"\(?\s*(United\s*States|China|Simplified,?\s*Mainland\s*China)\s*\)?",
    r"[（(]Simplified[^）)]*[）)]",
    r"Accessibility:?\s*Unavailable",
    r"Notes?|Notas|Votes|Co[mr]+nments?",
]
DATE_LABEL = r"\d{1,2}日|\d月"
PUNCTUATION = r"[\s，。,.！!？?：:、；;“”\"'（）()\-—…·]"


def clean(text):
    text = text or ""
    for pattern in NOISE:
        text = re.sub(pattern, "", text)
    if len(re.findall(DATE_LABEL, text)) >= 2:          # a run of axis labels, not speech
        text = re.sub(DATE_LABEL, "", text)
        text = re.sub(r"(?<=\D)\d{2}\s*$", "", text)
    return re.sub(r"^[：:，,。.“”\"]+|[“”\"]+$", "", text).strip()


def norm(text):
    return re.sub(PUNCTUATION, "", text)


def classify(mobile, server, vision):
    m, s, v = norm(mobile), norm(server), norm(vision)
    flags = []
    joined = mobile + server + vision
    if re.search("[呃呢]", joined):
        flags.append("filler")
    if re.search("[A-Za-z0-9]", joined):
        flags.append("chart_or_digits")
    if s and s == v:
        base = "three_model" if m == s else "two_model"
    else:
        base = "needs_review"
    if base != "needs_review" and flags:
        return "forced_review", flags
    return base, flags


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--vision", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="new JSON list; never overwritten")
    args = parser.parse_args()
    if args.output.exists():
        sys.exit(f"{args.output} already exists; refusing to overwrite")

    vision = {row["id"]: row for row in read_jsonl(args.vision)}
    result = []
    for event in read_jsonl(args.events):
        raw = {"mobile": event.get("mobile") or "", "server": event.get("server") or "",
               "vision": (vision.get(event["id"]) or {}).get("vision") or ""}
        cleaned = {key: clean(value) for key, value in raw.items()}
        klass, flags = classify(cleaned["mobile"], cleaned["server"], cleaned["vision"])
        result.append({"id": event["id"], "start_ms": event["start_ms"], "end_ms": event["end_ms"],
                       "class": klass, "flags": flags, **cleaned, "raw": raw, "frame": event.get("frame"),
                       "review_basis": "ocr_agreement" if klass in ("three_model", "two_model") else "needs_visual_review"})
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"total": len(result), "classes": dict(collections.Counter(r["class"] for r in result))},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
