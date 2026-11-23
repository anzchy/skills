#!/usr/bin/env python3
"""Run PaddleOCR over a frame list with a hard maximum of five workers."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Images, directories, or UTF-8 path lists.")
    parser.add_argument("-o", "--output-prefix", required=True)
    parser.add_argument("--workers", type=int, default=5, help="Parallel processes; hard limit 5.")
    parser.add_argument("--crop", default="auto")
    parser.add_argument("--score-threshold", type=float, default=0.50)
    parser.add_argument("--dedupe-threshold", type=float, default=0.01)
    parser.add_argument("--model-size", choices=("mobile", "server"), default="mobile")
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.workers <= 5:
        raise SystemExit("--workers must be between 1 and 5; the Skill hard limit is 5")
    from paddleocr_subtitles import expand_inputs

    images = expand_inputs(args.inputs)
    if not images:
        raise SystemExit("No input images found")
    workers = min(args.workers, len(images))
    prefix = Path(args.output_prefix).expanduser().resolve()
    prefix.parent.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).with_name("paddleocr_subtitles.py")
    processes: list[tuple[int, subprocess.Popen, object, Path, Path]] = []
    outputs: list[str] = []
    chunk_size = math.ceil(len(images) / workers)
    for part in range(workers):
        chunk = images[part * chunk_size : (part + 1) * chunk_size]
        if not chunk:
            continue
        list_path = prefix.parent / f"{prefix.name}-part-{part + 1:02d}.txt"
        output = prefix.parent / f"{prefix.name}-part-{part + 1:02d}.jsonl"
        log_path = prefix.parent / f"{prefix.name}-part-{part + 1:02d}.progress.log"
        if output.exists() and not args.overwrite:
            raise SystemExit(f"Refusing to overwrite {output}; pass --overwrite")
        list_path.write_text("".join(f"{path}\n" for path in chunk), encoding="utf-8")
        command = [
            sys.executable,
            str(script),
            str(list_path),
            "-o",
            str(output),
            "--model-size",
            args.model_size,
            "--crop",
            args.crop,
            "--score-threshold",
            str(args.score_threshold),
            "--dedupe-threshold",
            str(args.dedupe_threshold),
        ]
        if args.cache_dir:
            command += ["--cache-dir", args.cache_dir]
        if args.overwrite:
            command.append("--overwrite")
        log_handle = log_path.open("w", encoding="utf-8")
        process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT)
        processes.append((part + 1, process, log_handle, output, log_path))
        outputs.append(str(output))
    failed: list[dict] = []
    for part, process, log_handle, output, log_path in processes:
        code = process.wait()
        log_handle.close()
        if code != 0:
            failed.append({"part": part, "exit_code": code, "log": str(log_path)})
    summary = {
        "images": len(images),
        "workers": workers,
        "model_size": args.model_size,
        "outputs": outputs,
        "failed": failed,
    }
    summary_path = prefix.parent / f"{prefix.name}.parallel.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
