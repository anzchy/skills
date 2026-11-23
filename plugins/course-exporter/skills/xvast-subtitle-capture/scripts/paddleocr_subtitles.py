#!/usr/bin/env python3
"""Run local PaddleOCR/ONNX subtitle OCR on Xvast frame captures."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
NON_SUBTITLE_PATTERN = re.compile(
    r"邢不行|xbx|oc6bd|^\d+$|^-?\d{1,2}:\d{2}$|^\d+(?:\.\d+)?x$|"
    r"English|Accessib|Investigate|Notes|Comments|of\s+\d+|"
    r"^Line\s+\d+|^Column\s+\d+|Sublime|PowerPoint|AutoSave|^[品日]$",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crop subtitle bands from Xvast frames and run local PP-OCRv5 via ONNX Runtime."
    )
    parser.add_argument("inputs", nargs="*", help="Image, directory, or UTF-8 text file containing image paths.")
    parser.add_argument("-o", "--output", default="paddleocr-subtitles.jsonl", help="Output JSONL path.")
    parser.add_argument(
        "--crop",
        default="auto",
        help="Crop box x1,y1,x2,y2. Default 'auto' uses the bottom subtitle band.",
    )
    parser.add_argument("--score-threshold", type=float, default=0.50)
    parser.add_argument(
        "--model-size",
        choices=("mobile", "server"),
        default="mobile",
        help="PP-OCRv5 model size. Mobile is the default batch model; server is the accuracy fallback.",
    )
    parser.add_argument(
        "--dedupe-threshold",
        type=float,
        default=0.0,
        help="Skip near-identical consecutive subtitle crops. 0 disables; try 0.01 for dense captures.",
    )
    parser.add_argument("--max-images", type=int, default=None, help="Process only the first N images.")
    parser.add_argument("--keep-crops", action="store_true", help="Keep cropped subtitle images next to output.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Model cache. Default: $PADDLE_PDX_CACHE_HOME or ./.paddleocr-cache in the current project.",
    )
    parser.add_argument("--download-models", action="store_true", help="Download missing local ONNX models.")
    parser.add_argument("--setup-only", action="store_true", help="Prepare/check models, then exit without OCR.")
    return parser.parse_args()


def natural_key(path: Path) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(path))]


def expand_inputs(values: list[str]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for value in values:
        item = Path(value).expanduser()
        if item.is_dir():
            candidates = sorted(
                (p for p in item.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES),
                key=natural_key,
            )
        elif item.suffix.lower() == ".txt" and item.is_file():
            candidates = []
            for line in item.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    candidates.append(Path(line).expanduser())
        else:
            candidates = [item]
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.is_file() and resolved.suffix.lower() in IMAGE_SUFFIXES and resolved not in seen:
                seen.add(resolved)
                paths.append(resolved)
    return paths


def crop_box_for(image: np.ndarray, spec: str) -> tuple[int, int, int, int]:
    height, width = image.shape[:2]
    if spec != "auto":
        values = tuple(int(value) for value in spec.split(","))
        if len(values) != 4:
            raise ValueError("--crop must be auto or x1,y1,x2,y2")
        x1, y1, x2, y2 = values
    elif width >= 2100 and height >= 1800:
        # Validated 2154x1898 Xvast layout: central subtitle-only band.
        # A three-frame smoke test remains mandatory because page layout can drift.
        x1, y1, x2, y2 = 500, 1120, 1650, 1260
    elif width >= 1800 and height >= 1000:
        # Already cropped player frame (normally 1920x1082).
        x1, y1, x2, y2 = 0, int(height * 0.80), width, height
    else:
        x1, y1, x2, y2 = 0, int(height * 0.75), width, height
    x1, x2 = max(0, x1), min(width, x2)
    y1, y2 = max(0, y1), min(height, y2)
    if x1 >= x2 or y1 >= y2:
        raise ValueError(f"Invalid crop box {(x1, y1, x2, y2)} for {width}x{height}")
    return x1, y1, x2, y2


def difference_score(previous: np.ndarray | None, current: np.ndarray) -> float:
    if previous is None:
        return 1.0
    # Compare only the vertical subtitle band. Binary white-text masks suppress
    # anti-aliasing, background video noise, and watermark drift.
    y1, y2 = int(current.shape[0] * 0.52), int(current.shape[0] * 0.90)
    size = (640, 64)
    a = cv2.cvtColor(cv2.resize(previous[y1:y2], size, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(cv2.resize(current[y1:y2], size, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    a = cv2.threshold(a, 190, 255, cv2.THRESH_BINARY)[1]
    b = cv2.threshold(b, 190, 255, cv2.THRESH_BINARY)[1]
    return float(np.mean(cv2.absdiff(a, b)) / 255.0)


def main() -> int:
    args = parse_args()
    invocation_root = Path.cwd().resolve()
    cache_root = Path(
        args.cache_dir
        or os.environ.get("PADDLE_PDX_CACHE_HOME")
        or invocation_root / ".paddleocr-cache"
    ).expanduser().resolve()
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache_root)
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

    from paddleocr import PaddleOCR

    det_name = f"PP-OCRv5_{args.model_size}_det"
    rec_name = f"PP-OCRv5_{args.model_size}_rec"
    det_model = cache_root / "official_models" / f"{det_name}_onnx"
    rec_model = cache_root / "official_models" / f"{rec_name}_onnx"
    missing_models = [path for path in (det_model, rec_model) if not (path / "inference.onnx").is_file()]
    if missing_models and args.download_models:
        # Instantiation downloads the official local ONNX packages into CACHE_HOME.
        PaddleOCR(
            engine="onnxruntime",
            device="cpu",
            text_detection_model_name=det_name,
            text_recognition_model_name=rec_name,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        missing_models = [path for path in (det_model, rec_model) if not (path / "inference.onnx").is_file()]
    if missing_models:
        paths = ", ".join(str(path) for path in missing_models)
        raise SystemExit(f"Local OCR models are missing: {paths}. Run with --download-models while online.")
    if args.setup_only:
        print(json.dumps({"ready": True, "cache": str(cache_root)}, ensure_ascii=False, indent=2))
        return 0

    output = Path(args.output).expanduser().resolve()
    if output.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite {output}; pass --overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)

    images = expand_inputs(args.inputs)
    if args.max_images is not None:
        images = images[: args.max_images]
    if not images:
        raise SystemExit("No input images found")

    engine = PaddleOCR(
        engine="onnxruntime",
        device="cpu",
        text_detection_model_name=det_name,
        text_detection_model_dir=str(det_model),
        text_recognition_model_name=rec_name,
        text_recognition_model_dir=str(rec_model),
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_rec_score_thresh=args.score_threshold,
    )

    crops_dir = output.parent / f"{output.stem}-crops"
    if args.keep_crops:
        crops_dir.mkdir(parents=True, exist_ok=True)
    previous_crop: np.ndarray | None = None
    processed = skipped = failed = 0
    started = time.time()

    with output.open("w", encoding="utf-8") as handle:
        for index, image_path in enumerate(images, start=1):
            image = cv2.imread(str(image_path))
            if image is None:
                record = {"source": str(image_path), "ok": False, "error": "Cannot decode image"}
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                failed += 1
                continue
            x1, y1, x2, y2 = crop_box_for(image, args.crop)
            crop = image[y1:y2, x1:x2]
            diff = difference_score(previous_crop, crop)
            if args.dedupe_threshold > 0 and diff < args.dedupe_threshold:
                handle.write(
                    json.dumps(
                        {
                            "source": str(image_path),
                            "ok": True,
                            "skipped_duplicate": True,
                            "difference": diff,
                            "ocr_model": f"PP-OCRv5_{args.model_size}",
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                skipped += 1
                continue
            previous_crop = crop.copy()

            # The subtitle crop may still contain chart labels above and the
            # player status bar below. Mask both before OCR while keeping the
            # original crop for change detection and optional evidence.
            ocr_crop = crop.copy()
            ocr_crop[: int(ocr_crop.shape[0] * 0.45)] = 0
            ocr_crop[int(ocr_crop.shape[0] * 0.92) :] = 0

            if args.keep_crops:
                crop_path = crops_dir / f"{index:06d}-{image_path.stem}.png"
                cv2.imwrite(str(crop_path), ocr_crop)
                temporary_path = crop_path
                cleanup = False
            else:
                temp = tempfile.NamedTemporaryFile(suffix=".png", delete=False, dir=output.parent)
                temp.close()
                temporary_path = Path(temp.name)
                cv2.imwrite(str(temporary_path), ocr_crop)
                cleanup = True

            frame_started = time.time()
            try:
                results = list(engine.predict(str(temporary_path)))
                data = results[0].json["res"] if results else {}
                texts = data.get("rec_texts", [])
                scores = data.get("rec_scores", [])
                boxes = data.get("rec_boxes", [])
                subtitle_texts: list[str] = []
                subtitle_scores: list[float] = []
                crop_height = crop.shape[0]
                for text, score, box in zip(texts, scores, boxes):
                    center_y = (box[1] + box[3]) / 2
                    if (
                        crop_height * 0.55 <= center_y <= crop_height * 0.88
                        and score >= args.score_threshold
                        and not NON_SUBTITLE_PATTERN.search(text.strip())
                    ):
                        subtitle_texts.append(text.strip())
                        subtitle_scores.append(score)
                record = {
                    "source": str(image_path),
                    "ok": True,
                    "ocr_model": f"PP-OCRv5_{args.model_size}",
                    "crop_box": [x1, y1, x2, y2],
                    "difference": diff,
                    "texts": texts,
                    "scores": scores,
                    "boxes": boxes,
                    "subtitle_texts": subtitle_texts,
                    "subtitle_scores": subtitle_scores,
                    "elapsed_ms": round((time.time() - frame_started) * 1000),
                }
                processed += 1
            except Exception as error:  # Keep the batch resumable and inspectable.
                record = {"source": str(image_path), "ok": False, "error": repr(error)}
                failed += 1
            finally:
                if cleanup:
                    temporary_path.unlink(missing_ok=True)
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"[{index}/{len(images)}] {image_path.name}: {len(record.get('texts', []))} lines", file=sys.stderr)

    meta = {
        "output": str(output),
        "inputs": len(images),
        "processed": processed,
        "skipped_duplicates": skipped,
        "failed": failed,
        "elapsed_seconds": round(time.time() - started, 2),
        "engine": "onnxruntime",
        "ocr_version": "PP-OCRv5",
        "model_size": args.model_size,
        "cache": str(cache_root),
    }
    output.with_suffix(output.suffix + ".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
