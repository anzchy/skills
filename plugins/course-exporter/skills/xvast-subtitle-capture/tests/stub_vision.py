"""Stand-in for the compiled vision_ocr binary: `stub_vision.py IMAGE_LIST OUTPUT_JSONL`.
Answers from STUB_VISION_MAP (image file stem -> {"rows": [...], "ok": bool, "error": str})."""
import json
import os
import sys
from pathlib import Path

list_file, out = sys.argv[1], sys.argv[2]
answers = json.load(open(os.environ["STUB_VISION_MAP"], encoding="utf-8"))
with open(out, "w", encoding="utf-8") as handle:
    for line in open(list_file, encoding="utf-8").read().splitlines():
        if not line:
            continue
        a = answers.get(Path(line).stem, {"rows": [], "ok": True, "error": ""})
        handle.write(json.dumps({"image": line, "rows": a["rows"], "ok": a.get("ok", True),
                                 "error": a.get("error", "")}, ensure_ascii=False) + "\n")
