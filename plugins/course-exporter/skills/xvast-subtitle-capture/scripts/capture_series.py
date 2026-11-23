#!/usr/bin/env python3
"""Capture consecutive batches with xvast-capture until a target video time is reached.

Each batch follows the protocol's rewind warm-up: `seek --by -10`, `play`, `park-cursor`, wait for the player controls
to hide, then `capture --frame-count N --interval-ms M --pause-after-capture`. Because the player is paused at the
previous batch's end, the rewind makes consecutive batches overlap by about 10 seconds (no gap).

One JSON line per batch goes to stdout: status, video start/end, frame count, frame gaps and, unless --no-measure,
the measured video area and whether a subtitle was detected on the first, middle and last frame. The series stops
with a non-zero exit as soon as a batch is invalid or its output cannot be read. Batches stay pending_manual_review:
look at their first, middle and last frames before marking them valid.

With --continuous there is no seek at all (for videos where seeking crashes Xvast): `play`, `park-cursor` and the
warm-up happen once, then batches are captured back to back while the video keeps playing, without
--pause-after-capture; the player is paused after the last batch. Consecutive batches then neither overlap nor rewind:
the gap between them is the capture start-up time, which must be checked and disclosed. The last batch is clipped to
the frames needed to reach --target-ms so it does not run into the end of the video. In continuous mode each batch
line after the first carries `seam_ms`: its video start minus the previous batch's video end (whole-second AX anchors,
so treat it as approximate and check the frame index). --measure-after skips the measuring between batches, which
otherwise runs measure_bounds three times while the video keeps playing and lengthens the seams; the measurements are
printed as {"event": "layout", "batch", "layout"} lines once the series stops.

Run it from a terminal that has Accessibility and Screen Recording permission.
"""
import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
OK_STATUSES = {"pending_manual_review", "valid"}
EXIT_LOST = 3  # Xvast is gone (crashed or quit); distinct from an ordinary invalid batch (1)


def next_batch_number(raw, prefix):
    numbers = [int(m.group(1)) for p in raw.iterdir() if (m := re.fullmatch(rf"{re.escape(prefix)}-(\d+)", p.name))]
    return max(numbers, default=0) + 1


def parse_capture_output(text):
    start = text.find("{")
    if start < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(text[start:])[0]
    except ValueError:
        return None


def player_alive(xvast):
    """True when `status` can still read the player (Xvast running with its progress bar)."""
    return subprocess.run(xvast + ["status"], capture_output=True, text=True).returncode == 0


def report_lost(batch, last_valid):
    """Print the resume point and return the lost-player exit code."""
    event = {"event": "xvast_lost", "batch": batch,
             "last_valid_batch": last_valid["batch"] if last_valid else None,
             "resume_from_ms": last_valid["video_end_ms"] if last_valid else None}
    print(json.dumps(event, ensure_ascii=False), flush=True)
    print(f"xvast lost during {batch}: Xvast is not running or its player is gone. Relaunch it, select the video in "
          f"chrome://playlist, seek back to just before {event['resume_from_ms']} ms and rerun; {batch} is not valid.",
          file=sys.stderr)
    return EXIT_LOST


def measure_frames(batch_dir, count):
    results = []
    for number in sorted({1, max(1, count // 2), count}):
        frame = batch_dir / f"frame-{number:06d}.jpg"
        try:
            out = subprocess.run([sys.executable, str(SCRIPTS / "measure_bounds.py"), str(frame)],
                                 capture_output=True, text=True, check=True).stdout
            info = json.loads(out)
            results.append({"frame": number, "video": info["video"], "subtitle": info["text"] is not None})
        except (subprocess.CalledProcessError, ValueError, OSError):
            results.append({"frame": number, "video": None, "subtitle": None})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw-root", required=True, type=Path, help="absolute .raw directory")
    parser.add_argument("--video-id", required=True, help="full playlist file name of the video")
    parser.add_argument("--target-ms", required=True, type=int, help="stop once a batch ends at or after this")
    parser.add_argument("--layout-profile", default="layout-003")
    parser.add_argument("--batch-prefix", default="main")
    parser.add_argument("--start-batch", type=int, default=None, help="default: after the highest existing batch")
    parser.add_argument("--frame-count", type=int, default=120)
    parser.add_argument("--interval-ms", type=int, default=500)
    parser.add_argument("--warmup-seconds", type=float, default=7.0)
    parser.add_argument("--max-batches", type=int, default=None)
    parser.add_argument("--no-measure", action="store_true")
    parser.add_argument("--measure-after", action="store_true",
                        help="measure first/middle/last frames after the series instead of between batches")
    parser.add_argument("--continuous", action="store_true",
                        help="never seek: play once and capture batches back to back without pausing")
    parser.add_argument("--xvast-capture", default=str(SCRIPTS / "xvast-capture"),
                        help="command used to drive the player (default: the skill wrapper)")
    args = parser.parse_args()
    raw = args.raw_root.resolve()
    xvast = shlex.split(args.xvast_capture)
    number = args.start_batch or next_batch_number(raw, args.batch_prefix)
    done = 0
    last_valid = None
    captured = []

    def finish(code):
        if args.measure_after:
            for name, count in captured:
                print(json.dumps({"event": "layout", "batch": name, "layout": measure_frames(raw / name, count)},
                                 ensure_ascii=False), flush=True)
        return code

    while True:
        batch = f"{args.batch_prefix}-{number:03d}"
        if not args.continuous or last_valid is None:
            steps = [["play"], ["park-cursor"]] if args.continuous else [["seek", "--by", "-10"], ["play"], ["park-cursor"]]
            for step in steps:
                if subprocess.run(xvast + step, capture_output=True, text=True).returncode != 0 and not player_alive(xvast):
                    return finish(report_lost(batch, last_valid))
            time.sleep(args.warmup_seconds)
        frame_count = args.frame_count
        if args.continuous and last_valid is not None and last_valid["video_end_ms"] is not None:
            remaining = args.target_ms - last_valid["video_end_ms"]
            frame_count = max(1, min(frame_count, remaining // args.interval_ms + 1))
        command = ["capture", "--video-id", args.video_id, "--output-root", str(raw), "--batch-dir", batch,
                   "--layout-profile", args.layout_profile, "--frame-count", str(frame_count),
                   "--interval-ms", str(args.interval_ms)]
        if not args.continuous:
            command.append("--pause-after-capture")
        proc = subprocess.run(xvast + command, capture_output=True, text=True)
        info = parse_capture_output(proc.stdout + "\n" + proc.stderr)
        if (info is None or info.get("status") not in OK_STATUSES) and not player_alive(xvast):
            return finish(report_lost(batch, last_valid))
        if info is None:
            print(f"capture of {batch} produced no readable output: {(proc.stderr or proc.stdout)[-300:]}", file=sys.stderr)
            return finish(1)
        line = {key: info.get(key) for key in ("batch", "status", "video_start_ms", "video_end_ms", "frame_count",
                                               "median_frame_gap_ms", "max_frame_gap_ms")}
        line["batch"] = line["batch"] or batch
        if args.continuous and last_valid is not None and None not in (line["video_start_ms"], last_valid["video_end_ms"]):
            line["seam_ms"] = line["video_start_ms"] - last_valid["video_end_ms"]
        captured.append((line["batch"], info.get("frame_count") or frame_count))
        if not args.no_measure and not args.measure_after:
            line["layout"] = measure_frames(raw / batch, info.get("frame_count") or frame_count)
        print(json.dumps(line, ensure_ascii=False), flush=True)
        if info.get("status") not in OK_STATUSES:
            if args.continuous:
                subprocess.run(xvast + ["pause"], capture_output=True, text=True)
            print(f"stopping: {batch} is {info.get('status')} ({info.get('invalid_reasons')})", file=sys.stderr)
            return finish(1)
        last_valid = {"batch": line["batch"], "video_end_ms": line["video_end_ms"]}
        done += 1
        if (info.get("video_end_ms") or 0) >= args.target_ms or (args.max_batches and done >= args.max_batches):
            if args.continuous:
                subprocess.run(xvast + ["pause"], capture_output=True, text=True)
            return finish(0)
        number += 1


if __name__ == "__main__":
    sys.exit(main())
