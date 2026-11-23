#!/usr/bin/env python3
"""Measure the video area, the slide canvas and the burned-in subtitle in one raw Xvast window frame.

Assumes the video has black letterbox/bottom bars against a lighter page, as in the Xvast player. Output
boxes are [x0, y0, x1, y1] with exclusive x1/y1. `text` is the white subtitle glyph extent; `subtitle` is that
extent padded to cover the translucent box. Measurements are evidence for the review, not a verdict.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

BLACK = 5
DARK = 30
WHITE = 235
NEIGHBOUR_DARK = 140
NEIGHBOUR_REACH = 10
CLUSTER_GAP = 40
PAD_X, PAD_TOP, PAD_BOTTOM = 26, 24, 20
MIN_TEXT_HEIGHT = 10  # glyph rows; thinner clusters are watermarks or edge pixels, not subtitles
ROW_FLOOR = 0.10  # a row belongs to the text only if it holds at least this share of the densest row


def span(flags):
    index = np.flatnonzero(flags)
    return (int(index.min()), int(index.max()) + 1) if len(index) else None


PAGE_GRAY = 221  # the light page behind the player
PAGE_TOLERANCE = 8  # the page is a flat grey; anything else, bright or dark, is the player
PAGE_RUN = 20  # a content edge needs this many consecutive off-page pixels (ignores thin lines and icons)


def first_run(flags):
    """Index where `flags` first stays true for PAGE_RUN consecutive entries, or None."""
    run = 0
    for i, flag in enumerate(flags):
        run = run + 1 if flag else 0
        if run == PAGE_RUN:
            return i - PAGE_RUN + 1
    return None


def video_bounds_against_page(gray):
    """Fallback for captures whose video has no black letterbox: the area is what differs from the page
    background, 16:9, anchored at its top-left corner. Rows and columns count as video when nearly all of
    them differ from the page, so toolbar icons and the scroll bar do not move the edges."""
    height, width = gray.shape
    off = np.abs(gray - PAGE_GRAY) > PAGE_TOLERANCE
    skip = round(0.09 * height)  # browser toolbar: its theme may be dark, which is not the video either
    inner = off[skip:, round(0.07 * width): round(0.88 * width)]
    top = first_run(inner.mean(axis=1) >= 0.9)
    top = None if top is None else top + skip
    if top is None:
        raise SystemExit("cannot find the video area (no black letterbox region, no content against the page)")
    band = off[top + 4: top + 24, :].mean(axis=0) >= 0.5
    left = first_run(band)
    if left is None:
        raise SystemExit("cannot find the video area (no black letterbox region, no content against the page)")
    right = left
    while right < width and band[right]:
        right += 1
    return [left, top, right, top + round((right - left) * 9 / 16)]


def video_bounds(gray):
    black = gray < BLACK
    rows = span(black.mean(axis=1) >= 0.03)
    cols = span(black.mean(axis=0) >= 0.03)
    height, width = gray.shape
    plausible = rows is not None and cols is not None and cols[1] - cols[0] >= 0.3 * width and rows[1] - rows[0] >= 0.2 * height
    if not plausible:  # no letterbox, or only a black sticker/icon inside the slide
        return video_bounds_against_page(gray)
    return [cols[0], rows[0], cols[1], rows[1]]


def slide_bounds(gray, video):
    vx0, vy0, vx1, vy1 = video
    probe = gray[(vy0 + vy1) // 2, vx0:vx1]
    cols = span(probe > DARK)
    if cols is None:
        raise SystemExit("cannot find the slide canvas inside the video area")
    left, right = cols[0] + vx0, cols[1] + vx0
    x = left + max(10, (right - left) // 25)
    column = gray[vy0:vy1, x]
    rows = span(column > DARK)
    if rows is None:
        raise SystemExit("cannot find the slide canvas top and bottom")
    return [left, rows[0] + vy0, right, rows[1] + vy0]


def text_like(gray):
    """White pixels with a dark pixel close by on the same row: subtitle glyphs, not the white slide card."""
    white = gray > WHITE
    dark = gray < NEIGHBOUR_DARK
    near_dark = np.zeros_like(dark)
    for shift in range(1, NEIGHBOUR_REACH + 1):
        near_dark[:, shift:] |= dark[:, :-shift]
        near_dark[:, :-shift] |= dark[:, shift:]
    return white & near_dark


def clusters(columns, gap):
    groups, current = [], []
    for x in np.flatnonzero(columns):
        if current and x - current[-1] > gap:
            groups.append(current)
            current = []
        current.append(int(x))
    if current:
        groups.append(current)
    return groups


def subtitle_text(gray, video, slide):
    vx0, vy0, vx1, vy1 = video
    sx0, sy0, sx1, sy1 = slide
    slide_h = sy1 - sy0
    top = max(vy0, sy1 - round(0.05 * slide_h))
    mask = text_like(gray)
    band = mask[top:vy1, sx0:sx1]
    if band.sum() < 20:
        return None
    groups = clusters(band.any(axis=0), CLUSTER_GAP)
    best = max(groups, key=lambda g: int(band[:, g[0]:g[-1] + 1].sum()))
    x0, x1 = best[0] + sx0, best[-1] + sx0 + 1
    per_row = mask[:, x0:x1].sum(axis=1)
    peak = top + int(np.argmax(per_row[top:vy1]))  # the densest row must lie in the bottom band
    if per_row[peak] == 0:
        return None
    floor = ROW_FLOOR * per_row[peak]
    first = last = peak
    while first > vy0 and per_row[first - 1] >= floor:
        first -= 1
    while last + 1 < vy1 and per_row[last + 1] >= floor:
        last += 1
    if last + 1 - first < MIN_TEXT_HEIGHT:
        return None
    return [x0, first, x1, last + 1]


def padded(text, video):
    vx0, vy0, vx1, vy1 = video
    return [max(vx0, text[0] - PAD_X), max(vy0, text[1] - PAD_TOP),
            min(vx1, text[2] + PAD_X), min(vy1, text[3] + PAD_BOTTOM)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--video", help="x1,y1,x2,y2: use this video area instead of detecting it (for frames whose "
                                        "dark content, e.g. thick black arrows, fools the detection)")
    args = parser.parse_args()
    with Image.open(args.source) as image:
        rgb = image.convert("RGB")
        gray = np.asarray(rgb.convert("L"), dtype=np.float32)
        size = list(rgb.size)
    video = [int(v) for v in args.video.split(",")] if args.video else video_bounds(gray)
    slide = slide_bounds(gray, video)
    text = subtitle_text(gray, video, slide)
    print(json.dumps({"source": str(args.source), "dimensions": size, "video": video, "slide": slide,
                      "text": text, "subtitle": padded(text, video) if text else None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
