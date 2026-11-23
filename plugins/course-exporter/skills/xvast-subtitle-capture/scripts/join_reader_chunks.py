#!/usr/bin/env python3
"""Join the chunked reader outputs of one segment into a single reader file in the items format.

Each chunk is {"items": [{"n", "cand", "read"}, ...]} covering some sheets of <seg>/sheets-rev. Chunks are applied in
the order given, so a retry chunk listed later overrides earlier reads of the same n. The join fails, writing
nothing, when a chunk repeats an n, when an n is not in --candidates (candidates.txt), or when any candidate
number is left unread. The output feeds filler_glyphs.py apply, check_reader_reads.py and merge_cue_review.py.
Refuses to overwrite --output.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--chunks", required=True, type=Path, nargs="+")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    numbers = {int(line.split(maxsplit=1)[0]) for line in args.candidates.read_text(encoding="utf-8").splitlines()
               if line.strip()}
    joined, source = {}, {}
    for chunk in args.chunks:
        seen = set()
        for item in json.loads(chunk.read_text(encoding="utf-8"))["items"]:
            n = item["n"]
            if n in seen:
                raise SystemExit(f"{chunk}: n={n} appears twice")
            if n not in numbers:
                raise SystemExit(f"{chunk}: n={n} is not in {args.candidates}")
            seen.add(n)
            joined[n], source[n] = item, chunk.name
    missing = sorted(numbers - set(joined))
    if missing:
        raise SystemExit(f"unread candidate numbers: {missing[:30]}{' …' if len(missing) > 30 else ''}")
    items = [joined[n] for n in sorted(joined)]
    args.output.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"items": len(items), "chunks": len(args.chunks), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
