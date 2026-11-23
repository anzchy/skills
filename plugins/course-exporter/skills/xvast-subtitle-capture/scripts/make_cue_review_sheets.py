#!/usr/bin/env python3
"""Build numbered subtitle-strip review sheets and apply event-level corrections.

Input rows (JSONL) carry id, frame and a candidate text (default key: server). Sheets let a reviewer read the
burned-in subtitle of every event next to its candidate text. A corrections.json ({event id: text read from
the frame}) is turned into event-level `correction` records. Events are only marked `verified` on request.
<output-dir>/index.json records per_sheet and the first/last number on each sheet: hand readers chunks by sheet
from it instead of assuming a strip count.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

LABEL_WIDTH = 50


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_crop(value):
    box = [int(part) for part in value.split(",")]
    if len(box) != 4 or box[0] >= box[2] or box[1] >= box[3]:
        raise SystemExit("--strip-crop must be x1,y1,x2,y2 with positive size")
    return tuple(box)


def build_sheet(rows, first_number, crop, width, strip_height):
    sheet = Image.new("RGB", (width + LABEL_WIDTH, strip_height * len(rows)), "white")
    draw = ImageDraw.Draw(sheet)
    for offset, row in enumerate(rows):
        with Image.open(row["frame"]) as image:
            strip = image.convert("RGB").crop(crop).resize((width, strip_height))
        sheet.paste(strip, (LABEL_WIDTH, offset * strip_height))
        draw.text((2, offset * strip_height + strip_height // 2 - 5), str(first_number + offset), fill="red")
    return sheet


def apply_corrections(rows, corrections, text_key, mark_verified):
    known = {row["id"] for row in rows}
    unknown = sorted(set(corrections) - known)
    if unknown:
        raise SystemExit(f"corrections for unknown event ids: {', '.join(unknown)}")
    events = []
    for row in rows:
        before = row[text_key]
        after = corrections.get(row["id"], before)
        event = {key: row[key] for key in ("id", "start_ms", "end_ms") if key in row}
        event.update(text=after, evidence=row["frame"], review="verified" if mark_verified else "ocr_only")
        if after != before:
            event["correction"] = {"before": before, "after": after, "evidence": row["frame"]}
        events.append(event)
    return events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--text-key", default="server")
    parser.add_argument("--strip-crop", default="450,1175,1700,1285")
    parser.add_argument("--per-sheet", type=int, default=16)
    parser.add_argument("--strip-width", type=int, default=900)
    parser.add_argument("--corrections", type=Path)
    parser.add_argument("--output-events", type=Path)
    parser.add_argument("--mark-verified", action="store_true",
                        help="mark events verified; only after every strip was read against its frame")
    args = parser.parse_args()
    if args.output_events and args.output_events.exists():
        raise SystemExit(f"refusing to overwrite {args.output_events}")
    rows = read_rows(args.candidates)
    crop = parse_crop(args.strip_crop)
    strip_height = max(1, round(args.strip_width * (crop[3] - crop[1]) / (crop[2] - crop[0])))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sheets, index = [], []
    for start in range(0, len(rows), args.per_sheet):
        sheet = build_sheet(rows[start:start + args.per_sheet], start + 1, crop, args.strip_width, strip_height)
        path = args.output_dir / f"sheet-{start // args.per_sheet + 1:02d}.jpg"
        sheet.save(path, quality=90)
        sheets.append(str(path))
        index.append({"sheet": path.name, "first": start + 1, "last": min(start + args.per_sheet, len(rows))})
    (args.output_dir / "index.json").write_text(json.dumps({"per_sheet": args.per_sheet, "sheets": index},
                                                           ensure_ascii=False, indent=1), encoding="utf-8")
    listing = "".join(f"{n} {row['id']} {row[args.text_key]}\n" for n, row in enumerate(rows, 1))
    (args.output_dir / "candidates.txt").write_text(listing, encoding="utf-8")
    if args.corrections:
        corrections = json.loads(args.corrections.read_text(encoding="utf-8"))
        events = apply_corrections(rows, corrections, args.text_key, args.mark_verified)
        if not args.output_events:
            raise SystemExit("--corrections needs --output-events")
        args.output_events.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events),
                                      encoding="utf-8")
    elif args.output_events:
        raise SystemExit("--output-events needs --corrections")
    print(json.dumps({"events": len(rows), "sheets": sheets,
                      "candidates": str(args.output_dir / "candidates.txt")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
