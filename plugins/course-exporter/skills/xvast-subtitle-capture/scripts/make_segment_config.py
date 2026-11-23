#!/usr/bin/env python3
"""Turn a reviewer's page decisions into the build-config.json that build_segment_manifest.py reads.

pages.json is a list in time order. A page that starts a slide:
  {"title", "range_start_ms", "first_seen_ms" (default: range_start_ms), "frame": "batch:frame_index",
   "type": "full_slide|editor_window|zoomed|software" (default full_slide; editor_window becomes `editor_canvas`, the
   others `full_slide`, the only types validate_capture.py accepts), "fallback": reason (required unless full_slide),
   "gaps": [..], "video_bounds": [x1,y1,x2,y2] (optional: use instead of detecting the video area; for frames where
   dark content such as thick black arrows fools measure_bounds.py), "no_subtitle": true (optional: the chosen frame
   has no burned-in subtitle; see build_segment_manifest.py)}
`frame` uses the label printed on make_page_sheets.py sheets and must be a valid batch frame that the batch review
did not exclude. A revisit of an earlier page is {"title", "range_start_ms", "same_as": <position in this list, from 1>}:
it adds a range folded into that page's slide by merge_keys and no new slide. Slide ids are `<segment>-ppt-NNN` in order of appearance.
"""
import argparse
import json
import sys
from pathlib import Path


SLIDE_TYPES = {"full_slide": "full_slide", "editor_window": "editor_canvas", "software": "full_slide", "zoomed": "full_slide"}


def fail(message):
    sys.exit(message)


def appeared(page):
    """When the page was first on screen: a revisit counts from its range start."""
    start = page["range_start_ms"]
    return start if "same_as" in page else min(start, page.get("first_seen_ms", start))


def trim_to_segment(pages, start_ms, end_ms):
    """Sheets include margin frames, so the reviewer may list pages of the neighbouring segments. Drop pages that
    start at or after the end; with a start, keep only the last page that appeared before it, moved to the start."""
    keep = [i for i, page in enumerate(pages) if page["range_start_ms"] < end_ms]
    if start_ms is not None:
        earlier = sorted((i for i in keep if appeared(pages[i]) < start_ms), key=lambda i: (appeared(pages[i]), i))
        keep = [i for i in keep if i not in set(earlier[:-1])]
    position = {old: new for new, old in enumerate(keep, 1)}
    trimmed = []
    for i in keep:
        page = dict(pages[i])
        if "same_as" in page:
            if page["same_as"] - 1 not in position:
                fail(f"revisit at {page['range_start_ms']} ms points at a page outside the segment")
            page["same_as"] = position[page["same_as"] - 1]
        if start_ms is not None and appeared(page) < start_ms:
            page["range_start_ms"] = start_ms
        trimmed.append(page)
    return trimmed


def resolve_frame(raw_dir, label):
    batch, _, index = label.partition(":")
    if not index.isdigit():
        fail(f"frame label {label!r} is not batch:index")
    manifest = raw_dir / batch / "frames.json"
    path = raw_dir / batch / f"frame-{int(index):06d}.jpg"
    if not manifest.exists() or not path.exists():
        fail(f"frame {label} is missing ({path})")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("status") != "valid":
        fail(f"frame {label}: batch {batch} is not valid")
    if int(index) in (data.get("manual_review", {}).get("excluded_frames") or []):
        fail(f"frame {label} is excluded by the batch review")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--seg-dir", required=True, type=Path, help="relative to --project-root, e.g. 视频/.raw/seg-t170")
    parser.add_argument("--pages", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, help="new staging directory, relative to --project-root")
    parser.add_argument("--title", required=True)
    parser.add_argument("--end-ms", required=True, type=int, help="segment end; pages starting at or after it are dropped")
    parser.add_argument("--start-ms", type=int, help="segment start; of the pages that appeared before it only the last "
                                                     "is kept, and its range starts here")
    parser.add_argument("--coverage", required=True, type=Path, help="JSON file with the manifest coverage block")
    args = parser.parse_args()
    if args.output.exists():
        fail(f"{args.output} already exists; refusing to overwrite")

    root = args.project_root.resolve()
    seg_name = args.seg_dir.name.removeprefix("seg-")
    raw_dir = (root / args.seg_dir).parent
    pages = trim_to_segment(json.loads(args.pages.read_text(encoding="utf-8")), args.start_ms, args.end_ms)

    slides, ranges, merge_keys, previous = [], [], {}, -1
    slide_of = {}      # 1-based position in pages -> slide id
    for position, page in enumerate(pages, 1):
        start = page["range_start_ms"]
        if start < previous:
            fail(f"pages are out of order at {start} ms ({page.get('title')!r})")
        previous = start
        if "same_as" in page:
            number = page["same_as"]
            if number not in slide_of:
                fail(f"same_as {number} does not name an earlier page")
            label = f"{seg_name}-rev-{len(merge_keys) + 1:03d}"
            merge_keys[label] = slide_of[number]
            slide_of[position] = slide_of[number]       # a later revisit may point at this revisit
            ranges.append([start, label])
            continue
        kind = page.get("type", "full_slide")
        if kind not in SLIDE_TYPES:
            fail(f"page at {start} ms: unknown type {kind!r}")
        if kind != "full_slide" and not page.get("fallback"):
            fail(f"page at {start} ms is {kind} and needs a fallback reason (it is not a complete PPT page)")
        slide_id = f"{seg_name}-ppt-{len(slides) + 1:03d}"
        slide = {"id": slide_id, "title": page["title"], "frame": str(resolve_frame(raw_dir, page["frame"])),
                 "first_seen": page.get("first_seen_ms", start), "type": SLIDE_TYPES[kind]}
        if page.get("video_bounds"):
            slide["video_bounds"] = page["video_bounds"]
        if page.get("no_subtitle"):
            slide["no_subtitle"] = True
        if page.get("fallback"):
            slide["fallback"] = page["fallback"]
            if page.get("gaps"):
                slide["gaps"] = page["gaps"]
        slides.append(slide)
        slide_of[position] = slide_id
        ranges.append([start, slide_id])

    config = {"seg_dir": str(args.seg_dir), "out_dir": args.out_dir, "title": args.title, "end_ms": args.end_ms,
              "coverage": json.loads(args.coverage.read_text(encoding="utf-8")), "ranges": ranges, "slides": slides}
    if merge_keys:
        config["merge_keys"] = merge_keys
    args.output.write_text(json.dumps(config, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"slides": len(slides), "ranges": len(ranges), "revisits": len(merge_keys)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
