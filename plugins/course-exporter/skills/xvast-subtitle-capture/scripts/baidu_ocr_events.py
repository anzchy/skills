#!/usr/bin/env python3
"""Third-opinion OCR of subtitle strips with the Baidu OCR cloud API, to shrink the manual review.

For each event row (id, frame, mobile, server) the subtitle strip of its frame is cropped and sent to Baidu
(accurate_basic). Events where mobile and server agree and Baidu contains the same text are "three_model"; where only server and Baidu
agree they are "two_model" (except filler particles 呃/呢, always reviewed). Everything else goes to needs_review
for visual reading against the frame.
Agreement of three OCR engines is not verification: the document must say so for the auto-accepted events.

Cloud use: this uploads cropped subtitle images to Baidu. Use --dry-run to see what would be sent. Credentials are
read from a 0600 file (default ~/.config/baidu-ocr/credentials: BAIDU_OCR_API_KEY / BAIDU_OCR_SECRET_KEY) or the same
environment variables, and are never printed or written to any output.
"""
import argparse
import base64
import io
import json
import os
import re
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

DEFAULT_CREDENTIALS = Path.home() / ".config/baidu-ocr/credentials"
DEFAULT_API = "https://aip.baidubce.com"
KEY_NAMES = ("BAIDU_OCR_API_KEY", "BAIDU_OCR_SECRET_KEY")
WHITESPACE = re.compile(r"\s+")
PUNCTUATION = re.compile(r"[，。、！？,.!?：:；;“”\"'（）()]")
FILLERS = ("呃", "呢")  # the most common OCR confusion pair in this corpus: always read these against the frame
QPS_ERRORS = {18, 19}
# Chart text sitting next to the subtitle is read identically by every engine, so agreement cannot expose it.
CHART_NOISE = re.compile(r"(?i)high|\d{4,}|\d+日")


def load_credentials(path):
    values = {name: os.environ[name] for name in KEY_NAMES if os.environ.get(name)}
    if len(values) < 2 and path.is_file():
        if path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise SystemExit(f"credentials file {path} must not be readable by group/others (chmod 600)")
        for line in path.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() in KEY_NAMES and value.strip():
                values.setdefault(name.strip(), value.strip())
    if len(values) < 2:
        raise SystemExit(f"missing Baidu credentials: create {path} (BAIDU_OCR_API_KEY / BAIDU_OCR_SECRET_KEY) or set the env vars")
    return values[KEY_NAMES[0]], values[KEY_NAMES[1]]


def post(url, form=None, retries=3):
    data = urllib.parse.urlencode(form).encode() if form is not None else b""
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:  # 4xx carry a JSON body worth reporting; do not retry
            try:
                return json.loads(error.read().decode("utf-8"))
            except ValueError:
                last = error
        except (urllib.error.URLError, TimeoutError) as error:
            last = error
        time.sleep(1 + attempt)
    raise SystemExit(f"network error talking to Baidu: {last}")


def fetch_token(api_base, key, secret):
    query = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": key, "client_secret": secret})
    reply = post(f"{api_base}/oauth/2.0/token?{query}")
    token = reply.get("access_token")
    if not token:
        raise SystemExit(f"Baidu rejected the credentials: {reply.get('error', 'unknown error')}")
    return token


def strip_png(frame, crop):
    with Image.open(frame) as image:
        buffer = io.BytesIO()
        image.convert("RGB").crop(crop).save(buffer, format="PNG")
    return buffer.getvalue()


def recognise(api_base, token, png, retries=4):
    reply = {}
    for attempt in range(retries):
        reply = post(f"{api_base}/rest/2.0/ocr/v1/accurate_basic?access_token={urllib.parse.quote(token)}",
                     {"image": base64.b64encode(png).decode(), "language_type": "CHN_ENG"})
        if reply.get("error_code") not in QPS_ERRORS:
            break
        time.sleep(1 + attempt)
    if "error_code" in reply:
        return None, f"{reply['error_code']}: {reply.get('error_msg', '')}"
    return "".join(item["words"] for item in reply.get("words_result", [])), None


def normal(text):
    return PUNCTUATION.sub("", WHITESPACE.sub("", text or ""))


def classify(row, baidu, error):
    """three_model | two_model | review. Baidu may carry chart labels around the subtitle, so it only has to contain it."""
    if error is not None:
        return "review"
    mobile, server, other = normal(row["mobile"]), normal(row["server"]), normal(baidu)
    if not server or server not in other or CHART_NOISE.search(row["server"]):
        return "review"
    if mobile == server:
        return "three_model"
    if any(mark in server or mark in mobile for mark in FILLERS):
        return "review"
    return "two_model"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidates", required=True, type=Path, help="jsonl with id, frame, mobile, server per event")
    parser.add_argument("--strip-crop", default="450,1175,1700,1285")
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--api-base", default=DEFAULT_API)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--output-report", required=True, type=Path)
    parser.add_argument("--pause", type=float, default=0.0, help="seconds between requests (QPS limits)")
    parser.add_argument("--dry-run", action="store_true", help="send nothing; print how many images would be uploaded")
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.candidates.read_text(encoding="utf-8").splitlines() if line.strip()]
    crop = tuple(int(part) for part in args.strip_crop.split(","))
    if args.dry_run:
        print(json.dumps({"would_send": len(rows), "strip_crop": crop}))
        return
    for target in (args.output_jsonl, args.output_report):
        if target.exists():
            raise SystemExit(f"refusing to overwrite {target}")
    key, secret = load_credentials(args.credentials)
    token = fetch_token(args.api_base, key, secret)
    results, needs_review, agree, two_model = [], [], 0, []
    for row in rows:
        text, error = recognise(args.api_base, token, strip_png(row["frame"], crop))
        results.append({"id": row["id"], "baidu": text, "baidu_error": error})
        verdict = classify(row, text, error)
        if verdict == "three_model":
            agree += 1
        elif verdict == "two_model":
            two_model.append(row["id"])
        else:
            needs_review.append({"id": row["id"], "start_ms": row.get("start_ms"), "mobile": row["mobile"],
                                 "server": row["server"], "baidu": text, "baidu_error": error, "frame": row["frame"]})
        if args.pause:
            time.sleep(args.pause)
    args.output_jsonl.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results), encoding="utf-8")
    report = {"events": len(rows), "agree": agree, "two_model": len(two_model), "two_model_ids": two_model,
              "needs_review": needs_review}
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"events": len(rows), "agree": agree, "two_model": len(two_model), "needs_review": len(needs_review)}))


if __name__ == "__main__":
    main()
