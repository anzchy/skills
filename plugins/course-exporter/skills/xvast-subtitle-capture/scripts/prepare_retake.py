#!/usr/bin/env python3
"""Extract chapter time windows for Xvast seeking; never selects a frame automatically."""
import argparse
import json
import re
from pathlib import Path


HEADING = re.compile(r"^##\s+(\d+)\s+(.+?)\s*$")
BLOCK = re.compile(r"\*\*约\s+(\d{1,3}:\d{2}(?::\d{2})?)\s*[–-]\s*(\d{1,3}:\d{2}(?::\d{2})?)\*\*")


def milliseconds(value):
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return (minutes * 60 + seconds) * 1000
    hours, minutes, seconds = parts
    return (hours * 3600 + minutes * 60 + seconds) * 1000


def extract(document):
    rows = []
    current = None
    for line in document.read_text(encoding="utf-8").splitlines():
        heading = HEADING.match(line)
        if heading:
            current = {"number": int(heading.group(1)), "title": heading.group(2), "windows": []}
            rows.append(current)
            continue
        block = BLOCK.search(line)
        if current is not None and block:
            start, end = (milliseconds(block.group(i)) for i in (1, 2))
            if end <= start:
                raise ValueError(f"invalid time block in chapter {current['number']}: {line}")
            current["windows"].append({"start_ms": start, "end_ms": end})
    if not rows:
        raise ValueError("No numbered chapter headings found")
    if len({row["number"] for row in rows}) != len(rows):
        raise ValueError("Duplicate chapter numbers")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", required=True, type=Path)
    parser.add_argument("--manifest", type=Path, help="Optional existing manifest to check chapter count/order")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows = extract(args.document)
    if args.manifest:
        slides = json.loads(args.manifest.read_text(encoding="utf-8")).get("slides", [])
        if len(slides) != len(rows):
            raise ValueError(f"Chapter count {len(rows)} differs from manifest slide count {len(slides)}")
        for row, slide in zip(rows, slides):
            row["slide_id"] = slide["id"]
            if slide.get("title") != row["title"]:
                row["title_check"] = "review_required"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.write_text(json.dumps({"document": str(args.document.resolve()), "chapters": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"chapters": len(rows), "without_time_windows": [r["number"] for r in rows if not r["windows"]], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
