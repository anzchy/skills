import json
import subprocess
import sys

from conftest import SCRIPTS


def make_seg(tmp_path, classes, candidates):
    """classes: {id: class}; candidates: [(n, id, text)] numbered as on the review sheets."""
    seg = tmp_path / "seg"
    (seg / "ocr").mkdir(parents=True)
    (seg / "sheets-rev").mkdir()
    rows = [{"id": i, "class": c, "server": "s", "mobile": "m", "vision": "v"} for i, c in classes.items()]
    (seg / "ocr" / "vision-classified.json").write_text(json.dumps(rows), encoding="utf-8")
    (seg / "sheets-rev" / "candidates.txt").write_text(
        "".join(f"{n} {i} {t}\n" for n, i, t in candidates), encoding="utf-8")
    return seg


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def merge(seg, *reviews, out="review.json"):
    proc = subprocess.run([sys.executable, str(SCRIPTS / "merge_cue_review.py"), "--seg-dir", str(seg),
                           "--reviews", *map(str, reviews), "--output", str(seg / out)],
                          capture_output=True, text=True)
    return proc, seg / out


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_items_become_corrections_drop_and_uncertain(tmp_path):
    seg = make_seg(tmp_path, {"e1": "needs_review", "e2": "needs_review", "e3": "needs_review", "e4": "needs_review"},
                [(1, "e1", "找们开始"), (2, "e2", "好的"), (3, "e3", "杂字"), (4, "e4", "看不清")])
    items = write(tmp_path / "r.json", {"items": [
        {"n": 1, "cand": "找们开始", "read": "我们开始"}, {"n": 2, "cand": "好的", "read": "好的"},
        {"n": 3, "cand": "杂字", "read": "DROP"}, {"n": 4, "cand": "看不清", "read": "UNCERTAIN"}]})
    proc, out = merge(seg, items)
    assert proc.returncode == 0, proc.stderr
    review = load(out)
    assert review["corrections"] == {"e1": "我们开始"}      # e2 read the same as the candidate: no correction
    assert review["drop"] == ["e3"] and review["uncertain"] == ["e4"]


def test_candidate_mismatch_is_rejected_because_the_reader_was_misaligned(tmp_path):
    seg = make_seg(tmp_path, {"e1": "needs_review"}, [(1, "e1", "原文")])
    items = write(tmp_path / "r.json", {"items": [{"n": 1, "cand": "别的字幕", "read": "别的字幕"}]})
    proc, out = merge(seg, items)
    assert proc.returncode != 0 and "misaligned" in proc.stderr and not out.exists()


def test_a_cue_left_unread_is_rejected(tmp_path):
    seg = make_seg(tmp_path, {"e1": "needs_review", "e2": "needs_review"}, [(1, "e1", "甲"), (2, "e2", "乙")])
    items = write(tmp_path / "r.json", {"items": [{"n": 1, "cand": "甲", "read": "甲"}]})
    proc, out = merge(seg, items)
    assert proc.returncode != 0 and "unread" in proc.stderr and not out.exists()


def test_old_format_lists_are_accepted_and_conflicts_resolve_to_uncertain(tmp_path):
    seg = make_seg(tmp_path, {"e1": "needs_review", "e2": "needs_review", "e3": "needs_review"},
                [(1, "e1", "甲"), (2, "e2", "乙"), (3, "e3", "丙")])
    old = write(tmp_path / "old.json", {"corrections": {"e1": "甲甲", "e2": "乙乙"}, "drop": ["e2"], "uncertain": [],
                                        "read_count": 3})
    proc, out = merge(seg, old)
    assert proc.returncode == 0, proc.stderr
    review = load(out)
    assert review["corrections"] == {"e1": "甲甲"}
    assert review["uncertain"] == ["e2"]          # listed twice (correction and drop): not trusted either way
    assert review["unread_ids"] == ["e3"]


def test_ocr_agreement_events_go_to_auto_and_ids_outside_the_review_set_are_ignored(tmp_path):
    seg = make_seg(tmp_path, {"e1": "three_model", "e2": "two_model", "e3": "needs_review", "e4": "forced_review"},
                [(1, "e3", "丙"), (2, "e4", "丁")])
    items = write(tmp_path / "r.json", {"items": [{"n": 1, "cand": "丙", "read": "丙"}, {"n": 2, "cand": "丁", "read": "丁"}]})
    proc, out = merge(seg, items)
    assert proc.returncode == 0, proc.stderr
    review = load(out)
    assert review["auto"] == ["e1", "e2"]
    assert review["basis"] == "codex_visual"


def test_later_review_files_override_earlier_ones_and_output_is_never_overwritten(tmp_path):
    seg = make_seg(tmp_path, {"e1": "needs_review"}, [(1, "e1", "甲")])
    first = write(tmp_path / "a.json", {"items": [{"n": 1, "cand": "甲", "read": "乙"}]})
    second = write(tmp_path / "b.json", {"items": [{"n": 1, "cand": "甲", "read": "丙"}]})
    proc, out = merge(seg, first, second)
    assert proc.returncode == 0, proc.stderr
    assert load(out)["corrections"] == {"e1": "丙"}
    again, _ = merge(seg, first, second)
    assert again.returncode != 0 and "exists" in again.stderr


def test_a_lightly_retyped_candidate_still_counts_as_aligned(tmp_path):
    seg = make_seg(tmp_path, {"e1": "needs_review"}, [(1, "e1", "继续通过这个正损类的策略曲")])
    items = write(tmp_path / "r.json", {"items": [{"n": 1, "cand": "继续通过这个止损类的策略", "read": "继续通过这个止损类的策略"}]})
    proc, out = merge(seg, items)
    assert proc.returncode == 0, proc.stderr
    assert load(out)["corrections"] == {"e1": "继续通过这个止损类的策略"}
