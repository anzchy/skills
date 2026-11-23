#!/usr/bin/env python3
"""Third OCR source: run macOS Vision on the subtitle strip of each event's representative frame.

Reads an events JSONL (each row needs `id` and `frame`, e.g. recheck_events_with_server.py output), crops the
subtitle strip from the raw frame, runs scripts/vision_ocr.m on the strips and writes one row per event:
  {"id", "vision", "vision_all", "vision_error"}
`vision` keeps only rows whose height is at least 60% of the tallest row (the subtitle, not chart labels),
ordered left to right; `vision_all` is every row. Vision results stay OCR candidates, never verified text.
"""
import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
DEFAULT_CROP = "400,1175,1700,1285"
HEIGHT_RATIO = 0.6
SDK_DIR = Path("/Library/Developer/CommandLineTools/SDKs")


def subtitle_text(rows):
    rows = [r for r in rows if r["text"].strip()]
    if not rows:
        return ""
    tallest = max(r["h"] for r in rows)
    keep = sorted((r for r in rows if r["h"] >= HEIGHT_RATIO * tallest), key=lambda r: r["x"])
    return "".join(r["text"] for r in keep)


def compile_vision(work_dir):
    """Compile vision_ocr.m. The newest Command Line Tools SDK can fail at link time (malformed .tbd), so on a
    failure retry with each other installed SDK."""
    binary = work_dir / "vision_ocr"
    if binary.exists():
        return [str(binary)]
    base = ["clang", "-fobjc-arc", "-Wno-deprecated-declarations", "-framework", "AppKit", "-framework", "Vision",
            "-framework", "ImageIO", str(HERE / "vision_ocr.m"), "-o", str(binary)]
    sdks = [None] + sorted((p for p in SDK_DIR.glob("MacOSX*.*.sdk") if p.is_dir()), reverse=True)
    for sdk in sdks:
        command = base if sdk is None else [*base, "-isysroot", str(sdk)]
        if subprocess.run(command, capture_output=True).returncode == 0:
            return [str(binary)]
    sys.exit("could not compile vision_ocr.m with any SDK; compile it by hand and pass --vision-command")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="new JSONL; an existing file is never overwritten")
    parser.add_argument("--work-dir", required=True, type=Path, help="holds the strip crops and the compiled binary")
    parser.add_argument("--crop", default=DEFAULT_CROP, help="x1,y1,x2,y2 subtitle strip in the raw frame")
    parser.add_argument("--vision-command", help="override the compiled vision_ocr, e.g. for tests")
    args = parser.parse_args()

    if args.output.exists():
        sys.exit(f"{args.output} already exists; refusing to overwrite")
    crop = tuple(int(v) for v in args.crop.split(","))
    events = [json.loads(line) for line in args.events.read_text(encoding="utf-8").splitlines() if line.strip()]

    args.work_dir.mkdir(parents=True, exist_ok=True)
    strips = args.work_dir / "strips"
    strips.mkdir(exist_ok=True)
    paths = []
    for event in events:
        strip = strips / f"{event['id']}.png"
        Image.open(event["frame"]).convert("RGB").crop(crop).save(strip)
        paths.append(str(strip))
    listing = args.work_dir / "strips.txt"
    listing.write_text("\n".join(paths) + "\n", encoding="utf-8")
    raw = args.work_dir / "vision-raw.jsonl"
    if raw.exists():
        sys.exit(f"{raw} already exists; use a new --work-dir")

    command = shlex.split(args.vision_command) if args.vision_command else compile_vision(args.work_dir)
    subprocess.run([*command, str(listing), str(raw)], check=True)

    results = {}
    for line in raw.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        results[Path(item["image"]).stem] = item
    with args.output.open("w", encoding="utf-8") as handle:
        for event in events:
            item = results[event["id"]]
            ok = item["ok"]
            handle.write(json.dumps({
                "id": event["id"],
                "vision": subtitle_text(item["rows"]) if ok else None,
                "vision_all": "".join(r["text"] for r in sorted(item["rows"], key=lambda r: r["x"])),
                "vision_error": None if ok else item["error"]}, ensure_ascii=False) + "\n")
    print(json.dumps({"events": len(events), "output": str(args.output),
                      "errors": sum(1 for e in events if not results[e["id"]]["ok"])}))


if __name__ == "__main__":
    main()
