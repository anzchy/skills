#!/usr/bin/env python3
"""Select low-confidence PaddleOCR frames for PP-OCRv5 server review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr-results", nargs="+", required=True)
    parser.add_argument("--output-list", required=True)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument(
        "--include-empty",
        action="store_true",
        help="Also include processed frames with no subtitle candidate; use only for suspected OCR gaps.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected: list[str] = []
    seen: set[str] = set()
    examined = 0
    for value in args.ocr_results:
        with Path(value).expanduser().resolve().open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("skipped_duplicate"):
                    continue
                source = row.get("source")
                if not source:
                    continue
                examined += 1
                texts = [str(text).strip() for text in row.get("subtitle_texts", []) if str(text).strip()]
                scores = [float(score) for score in row.get("subtitle_scores", [])]
                choose = not row.get("ok", False)
                choose = choose or (bool(texts) and (not scores or min(scores) < args.threshold))
                choose = choose or (args.include_empty and row.get("ok", False) and not texts)
                resolved = str(Path(source).expanduser().resolve())
                if choose and resolved not in seen:
                    seen.add(resolved)
                    selected.append(resolved)
    output = Path(args.output_list).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(f"{source}\n" for source in selected), encoding="utf-8")
    print(json.dumps({"examined": examined, "selected": len(selected), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
