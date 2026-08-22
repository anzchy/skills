#!/usr/bin/env python3
"""Build a verified Songy course export from captured API JSON responses."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
LEADING_DATE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})\.(.+)$")
ALLOWED_MEDIA_HOST = "bandu-resources.songy.info"


class ExportError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-json", required=True, type=Path)
    parser.add_argument("--contents-json", required=True, type=Path)
    parser.add_argument("--output-root", default=Path.cwd(), type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--allow-local-media",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExportError(f"Cannot read valid JSON from {path}: {exc}") from exc


def unwrap_data(payload: Any, expected_type: type) -> Any:
    value = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
    if not isinstance(value, expected_type):
        raise ExportError(f"Expected {expected_type.__name__} JSON data")
    return value


def safe_filename(value: str) -> str:
    cleaned = INVALID_FILENAME_CHARS.sub("_", value).strip().rstrip(".")
    if cleaned in {"", ".", ".."}:
        raise ExportError("Course title does not produce a safe filename")
    return cleaned


def notes_filename(title: str, safe_title: str) -> str:
    match = LEADING_DATE.match(title)
    if not match:
        return f"{safe_title}-notes.md"
    year, month, day, remainder = match.groups()
    safe_remainder = safe_filename(remainder)
    return f"{year}{month}{day}-{safe_remainder}-notes.md"


def normalize_course_id(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        raise ExportError("Course ID is missing")
    course_id = str(value).strip()
    if not course_id:
        raise ExportError("Course ID is empty")
    return course_id


def extract_inputs(course_payload: Any, contents_payload: Any) -> tuple[str, str, list[dict[str, Any]], list[dict[str, Any]]]:
    course = unwrap_data(course_payload, dict)
    contents = unwrap_data(contents_payload, list)
    course_id = normalize_course_id(course.get("id"))
    title = course.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ExportError("Course title is missing")

    ordered: list[dict[str, Any]] = []
    for item in contents:
        if not isinstance(item, dict):
            raise ExportError("Course contents contain a non-object item")
        if normalize_course_id(item.get("course_id")) != course_id:
            raise ExportError("Course metadata and contents use different course IDs")
        order = item.get("order")
        if isinstance(order, bool) or not isinstance(order, (int, float)):
            raise ExportError("Every content item must have a numeric order")
        ordered.append(item)
    ordered.sort(key=lambda item: (float(item["order"]), int(item.get("id", 0))))

    audio = [item for item in ordered if item.get("category") == "audio"]
    text = [item for item in ordered if item.get("category") == "text"]
    if not audio:
        raise ExportError("Course contains no audio items")
    if not text:
        raise ExportError("Course contains no text items")
    return course_id, title, audio, text


def media_details(item: dict[str, Any]) -> tuple[str, int | None, int | None]:
    attachment = item.get("attachment")
    if not isinstance(attachment, dict):
        raise ExportError(f"Audio item order {item.get('order')} has no attachment")
    url = attachment.get("url") or attachment.get("raw_url")
    if not isinstance(url, str) or not url:
        raise ExportError(f"Audio item order {item.get('order')} has no media URL")
    size = attachment.get("size")
    duration = item.get("duration")
    valid_size = int(size) if isinstance(size, (int, float)) and not isinstance(size, bool) else None
    valid_duration = int(duration) if isinstance(duration, (int, float)) and not isinstance(duration, bool) else None
    return url, valid_size, valid_duration


def validate_media_url(url: str, allow_local_media: bool) -> None:
    parsed = urllib.parse.urlparse(url)
    if allow_local_media and parsed.scheme == "file":
        return
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_MEDIA_HOST:
        raise ExportError(f"Refusing media URL outside https://{ALLOWED_MEDIA_HOST}: {url}")


def download(url: str, target: Path, expected_size: int | None, resume: bool, allow_local_media: bool) -> None:
    validate_media_url(url, allow_local_media)
    if target.exists() and target.stat().st_size > 0:
        if expected_size is None or target.stat().st_size == expected_size:
            if resume:
                return
        target.unlink()

    partial = target.with_suffix(target.suffix + ".part")
    offset = partial.stat().st_size if resume and partial.exists() else 0
    headers = {"User-Agent": "Codex Songy Course Exporter/1.0"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            append = offset > 0 and getattr(response, "status", None) == 206
            if offset and not append:
                offset = 0
            mode = "ab" if append else "wb"
            with partial.open(mode) as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
    except (OSError, urllib.error.URLError) as exc:
        raise ExportError(f"Download failed for {url}: {exc}") from exc

    actual_size = partial.stat().st_size if partial.exists() else 0
    if actual_size <= 0:
        raise ExportError(f"Downloaded empty media file: {url}")
    if expected_size is not None and actual_size != expected_size:
        raise ExportError(
            f"Media size mismatch for {url}: expected {expected_size}, got {actual_size}"
        )
    os.replace(partial, target)


def ffconcat_quote(path: Path) -> str:
    return str(path.resolve()).replace("'", "'\\''")


def run(command: list[str], description: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise ExportError(f"{description} failed: {details}")
    return result


def require_tools() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ExportError("FFmpeg and FFprobe must already be installed and available on PATH")
    return ffmpeg, ffprobe


def build_notes(title: str, text_items: list[dict[str, Any]]) -> str:
    lines = [f"# {title}", "", "## 课程文本", ""]
    for index, item in enumerate(text_items, start=1):
        content = item.get("content")
        if not isinstance(content, str):
            raise ExportError(f"Text item order {item.get('order')} is not a string")
        content_lines = content.split("\n")
        lines.append(f"{index}. {content_lines[0]}")
        lines.extend(f"    {line}" if line else "" for line in content_lines[1:])
    return "\n".join(lines) + "\n"


def probe_duration(ffprobe: str, path: Path) -> float:
    result = run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        "Duration verification",
    )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise ExportError("FFprobe returned an invalid duration") from exc


def ensure_output_is_safe(course_dir: Path, audio_path: Path, notes_path: Path, overwrite: bool) -> None:
    if not course_dir.exists():
        return
    unexpected = [path for path in course_dir.iterdir() if path not in {audio_path, notes_path}]
    if unexpected:
        names = ", ".join(path.name for path in unexpected[:5])
        raise ExportError(f"Course folder contains unexpected files; refusing to modify it: {names}")
    existing = [path for path in (audio_path, notes_path) if path.exists()]
    if existing and not overwrite:
        raise ExportError("Completed or partial final output already exists; ask before using --overwrite")


def export(args: argparse.Namespace) -> dict[str, Any]:
    ffmpeg, ffprobe = require_tools()
    course_payload = load_json(args.course_json)
    contents_payload = load_json(args.contents_json)
    course_id, title, audio_items, text_items = extract_inputs(course_payload, contents_payload)
    safe_title = safe_filename(title)
    output_root = args.output_root.expanduser().resolve()
    course_dir = output_root / safe_title
    audio_path = course_dir / f"{safe_title}-完整音频.mp3"
    notes_path = course_dir / notes_filename(title, safe_title)
    ensure_output_is_safe(course_dir, audio_path, notes_path, args.overwrite)

    work_root = output_root / ".songy-course-exporter-work" / course_id
    parts_dir = work_root / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    expected_duration_ms = 0
    part_paths: list[Path] = []
    for index, item in enumerate(audio_items, start=1):
        url, expected_size, duration_ms = media_details(item)
        suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
        if suffix != ".mp3":
            raise ExportError(f"Unsupported audio format {suffix or '[none]'} at order {item.get('order')}")
        part_path = parts_dir / f"{index:04d}.mp3"
        download(url, part_path, expected_size, args.resume, args.allow_local_media)
        part_paths.append(part_path)
        if duration_ms is not None:
            expected_duration_ms += duration_ms

    concat_path = work_root / "concat.txt"
    concat_path.write_text(
        "".join(f"file '{ffconcat_quote(path)}'\n" for path in part_paths),
        encoding="utf-8",
    )
    merged_temp = work_root / "merged.mp3"
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c",
            "copy",
            str(merged_temp),
        ],
        "Audio merge",
    )
    run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(merged_temp), "-f", "null", "-"],
        "Merged-audio decode verification",
    )
    actual_duration = probe_duration(ffprobe, merged_temp)
    if expected_duration_ms:
        expected_duration = expected_duration_ms / 1000.0
        tolerance = max(1.0, expected_duration * 0.005)
        if abs(actual_duration - expected_duration) > tolerance:
            raise ExportError(
                f"Merged duration {actual_duration:.3f}s differs from expected "
                f"{expected_duration:.3f}s by more than {tolerance:.3f}s"
            )

    notes = build_notes(title, text_items)
    if sum(1 for line in notes.splitlines() if re.match(r"^\d+\. ", line)) != len(text_items):
        raise ExportError("Markdown item-count verification failed")

    course_dir.mkdir(parents=True, exist_ok=True)
    notes_temp = work_root / notes_path.name
    notes_temp.write_text(notes, encoding="utf-8")
    os.replace(merged_temp, audio_path)
    os.replace(notes_temp, notes_path)

    final_files = sorted(path.name for path in course_dir.iterdir())
    expected_files = sorted([audio_path.name, notes_path.name])
    if final_files != expected_files:
        raise ExportError("Final course folder does not contain exactly the two required deliverables")

    shutil.rmtree(work_root)
    work_parent = work_root.parent
    if work_parent.exists() and not any(work_parent.iterdir()):
        work_parent.rmdir()

    return {
        "status": "verified",
        "course_id": course_id,
        "course_title": title,
        "course_folder": str(course_dir),
        "audio_file": str(audio_path),
        "notes_file": str(notes_path),
        "audio_part_count": len(part_paths),
        "text_item_count": len(text_items),
        "merged_duration_seconds": round(actual_duration, 3),
    }


def main() -> int:
    args = parse_args()
    try:
        summary = export(args)
    except ExportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
