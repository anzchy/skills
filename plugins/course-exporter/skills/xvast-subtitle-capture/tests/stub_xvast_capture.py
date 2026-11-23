"""Stand-in for xvast-capture. State in STUB_XVAST_STATE (json): position_ms, behaviour; calls appended to STUB_XVAST_LOG."""
import json
import os
import sys
from pathlib import Path

state_path = Path(os.environ["STUB_XVAST_STATE"])
state = json.loads(state_path.read_text(encoding="utf-8"))
argv = sys.argv[1:]
with open(os.environ["STUB_XVAST_LOG"], "a", encoding="utf-8") as log:
    log.write(" ".join(argv) + "\n")
command = argv[0]
GONE = "xvast-capture: Xvast (com.haihaisoft.xvast) is not running"
if state.get("dead"):
    print(GONE, file=sys.stderr)
    sys.exit(1)


def option(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


if command == "status":
    print(json.dumps({"position_ms": state["position_ms"], "video_id": "v.mp4"}))
    sys.exit(0)
if command == "seek":
    state["position_ms"] += int(option("--by")) * 1000
elif command == "capture":
    batch = option("--batch-dir")
    root = Path(option("--output-root"))
    out = root / batch
    if out.exists() and any(out.iterdir()):
        print("refusing to overwrite existing batch", file=sys.stderr)
        sys.exit(1)
    out.mkdir(parents=True, exist_ok=True)
    start = state["position_ms"]
    end = start + 60000
    behaviour = state.get("behaviour", {}).get(batch, "ok")
    if behaviour == "crash":
        state["dead"] = True
        state_path.write_text(json.dumps(state), encoding="utf-8")
        print(GONE, file=sys.stderr)
        sys.exit(1)
    if behaviour == "garbage":
        print("something went wrong, no json here")
        sys.exit(1)
    status = "invalid" if behaviour == "invalid" else "pending_manual_review"
    payload = {"status": status, "batch": batch, "video_start_ms": start, "video_end_ms": end, "frame_count": 120,
               "median_frame_gap_ms": 504, "max_frame_gap_ms": 510, "output_dir": str(out),
               "layout_profile": option("--layout-profile")}
    (out / "frames.json").write_text(json.dumps(payload), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    state["position_ms"] = end
    state_path.write_text(json.dumps(state), encoding="utf-8")
    sys.exit(1 if status == "invalid" else 0)
state_path.write_text(json.dumps(state), encoding="utf-8")
