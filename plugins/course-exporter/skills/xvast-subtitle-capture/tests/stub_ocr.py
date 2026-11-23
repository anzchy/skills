"""Stand-in for scripts/paddleocr-subtitles: reads a path list, answers from STUB_OCR_MAP (source -> text)."""
import json
import os
import sys

args = sys.argv[1:]
list_file = args[0]
out = args[args.index("-o") + 1]
answers = json.load(open(os.environ["STUB_OCR_MAP"], encoding="utf-8"))
with open(out, "w", encoding="utf-8") as handle:
    for line in open(list_file, encoding="utf-8").read().splitlines():
        text = answers.get(line)
        if isinstance(text, list):  # [[text, box height], ...]: every piece passes the band filter, boxes kept
            row = {"source": line, "ok": True, "texts": [t for t, _ in text], "scores": [0.95] * len(text),
                   "boxes": [[0, 10, 50, 10 + h] for _, h in text],
                   "subtitle_texts": [t for t, _ in text], "subtitle_scores": [0.95] * len(text)}
        else:
            row = {"source": line, "ok": True,
                   "subtitle_texts": [text] if text else [], "subtitle_scores": [0.95] if text else []}
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
