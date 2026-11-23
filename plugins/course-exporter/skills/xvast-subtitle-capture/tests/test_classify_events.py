import json
import subprocess
import sys

from conftest import SCRIPTS


def write_inputs(tmp_path, rows):
    """rows: list of (mobile, server, vision)."""
    events, vision = [], []
    for index, (mobile, server, vis) in enumerate(rows, 1):
        event_id = f"ocr-{index:06d}"
        events.append({"id": event_id, "start_ms": index * 1000, "end_ms": index * 1000 + 800,
                       "mobile": mobile, "server": server, "agree": mobile == server, "frame": f"/f/{index}.jpg"})
        vision.append({"id": event_id, "vision": vis, "vision_all": vis, "vision_error": None})
    ev = tmp_path / "event-server.jsonl"
    vi = tmp_path / "event-vision.jsonl"
    ev.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in events), encoding="utf-8")
    vi.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in vision), encoding="utf-8")
    return ev, vi


def classify(tmp_path, rows, out_name="classified.json"):
    ev, vi = write_inputs(tmp_path, rows)
    out = tmp_path / out_name
    proc = subprocess.run([sys.executable, str(SCRIPTS / "classify_events.py"), "--events", str(ev),
                           "--vision", str(vi), "--output", str(out)], capture_output=True, text=True)
    return proc, out


def load(out):
    return json.loads(out.read_text(encoding="utf-8"))


def test_three_way_agreement_is_accepted_as_ocr_agreement(tmp_path):
    proc, out = classify(tmp_path, [("我们开始吧", "我们开始吧", "我们开始吧")])
    assert proc.returncode == 0, proc.stderr
    (item,) = load(out)
    assert item["class"] == "three_model" and item["review_basis"] == "ocr_agreement" and item["flags"] == []


def test_server_and_vision_agreeing_against_mobile_is_two_model(tmp_path):
    proc, out = classify(tmp_path, [("找们开始吧", "我们开始吧", "我们开始吧")])
    (item,) = load(out)
    assert item["class"] == "two_model" and item["review_basis"] == "ocr_agreement"


def test_punctuation_and_spaces_do_not_break_agreement(tmp_path):
    proc, out = classify(tmp_path, [("我们，开始 吧。", "我们开始吧", "我们开始吧！")])
    (item,) = load(out)
    assert item["class"] == "three_model"


def test_disagreement_needs_visual_review(tmp_path):
    proc, out = classify(tmp_path, [("我们开始吧", "找们开始吧", "同学开始吧")])
    (item,) = load(out)
    assert item["class"] == "needs_review" and item["review_basis"] == "needs_visual_review"


def test_mobile_and_server_agreeing_against_vision_still_needs_review(tmp_path):
    proc, out = classify(tmp_path, [("我们开始吧", "我们开始吧", "我们开始")])
    (item,) = load(out)
    assert item["class"] == "needs_review"


def test_fillers_and_chart_text_force_visual_review_even_when_all_agree(tmp_path):
    proc, out = classify(tmp_path, [("呃我们开始", "呃我们开始", "呃我们开始"),
                                    ("这是六日线", "这是6日线", "这是6日线"),
                                    ("看high这里", "看high这里", "看high这里")])
    filler, digits, letters = load(out)
    assert filler["class"] == "forced_review" and filler["flags"] == ["filler"]
    assert digits["class"] == "forced_review" and digits["flags"] == ["chart_or_digits"]
    assert letters["class"] == "forced_review" and letters["flags"] == ["chart_or_digits"]
    assert all(r["review_basis"] == "needs_visual_review" for r in (filler, digits, letters))


def test_interface_noise_in_the_strip_is_removed_before_comparing(tmp_path):
    proc, out = classify(tmp_path, [("我们开始吧", "我们开始吧Notes", "我们开始吧(China)Accessibility: Unavailable")])
    (item,) = load(out)
    assert item["class"] == "three_model"
    assert item["vision"] == "我们开始吧"           # cleaned text is what later steps read
    assert item["raw"]["vision"].endswith("Unavailable")  # the untouched reading is kept


def test_axis_dates_are_dropped_only_when_there_are_several(tmp_path):
    proc, out = classify(tmp_path, [("我们开始吧12日13日14日", "我们开始吧", "我们开始吧"),
                                    ("到6日再说", "到6日再说", "到6日再说")])
    first, second = load(out)
    assert first["class"] == "three_model"
    assert second["class"] == "forced_review"        # a single "6日" is real speech, kept and sent to review


def test_missing_vision_reading_cannot_agree(tmp_path):
    ev, vi = write_inputs(tmp_path, [("我们开始吧", "我们开始吧", "")])
    row = json.loads(vi.read_text(encoding="utf-8"))
    row.update(vision=None, vision_error="Cannot decode input image")
    vi.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    out = tmp_path / "classified.json"
    proc = subprocess.run([sys.executable, str(SCRIPTS / "classify_events.py"), "--events", str(ev),
                           "--vision", str(vi), "--output", str(out)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    (item,) = load(out)
    assert item["class"] == "needs_review"


def test_summary_counts_and_refuses_to_overwrite(tmp_path):
    proc, out = classify(tmp_path, [("甲乙丙", "甲乙丙", "甲乙丙"), ("甲乙", "丙丁", "戊己")])
    summary = json.loads(proc.stdout)
    assert summary["total"] == 2 and summary["classes"] == {"three_model": 1, "needs_review": 1}
    again = subprocess.run([sys.executable, str(SCRIPTS / "classify_events.py"), "--events", str(tmp_path / "event-server.jsonl"),
                            "--vision", str(tmp_path / "event-vision.jsonl"), "--output", str(out)],
                           capture_output=True, text=True)
    assert again.returncode != 0 and "exists" in again.stderr
