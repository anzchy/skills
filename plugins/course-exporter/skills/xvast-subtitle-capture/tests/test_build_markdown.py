from conftest import write_json


def manifest(tmp_path, cues, gaps=(), duration=60000, **coverage):
    cov = {"capture_coverage": "complete", "cue_text_review": "visual_reviewed",
           "word_for_word_manual_review": False, "evidence": "e", "gaps": list(gaps), **coverage}
    return write_json(tmp_path / "m.json", {"title": "t", "duration_ms": duration, "coverage": cov,
                                             "slides": [{"id": "p01", "title": "页"}], "cues": cues})


def cue(n, basis=None):
    item = {"id": f"c{n}", "start_ms": n * 1000, "end_ms": n * 1000 + 900, "slide_id": "p01",
            "text": f"字{n}", "review": "verified", "evidence": "e"}
    if basis:
        item["review_basis"] = basis
    return item


def build(run, tmp_path, path):
    out = tmp_path / "doc" / "稿.md"
    code, payload, stdout, err = run("build_markdown.py", "--manifest", path, "--output", out)
    assert code == 0, stdout + err
    return out.read_text(encoding="utf-8")


def test_text_review_line_counts_cues_accepted_on_ocr_agreement(run, tmp_path):
    cues = [cue(1, "visual_reviewed"), cue(2, "visual_reviewed"), cue(3, "ocr_agreement")]

    text = build(run, tmp_path, manifest(tmp_path, cues))

    assert "字幕文字校核：3 条中 2 条已对照字幕画面目视核对，1 条按 OCR 一致接受、未逐条目视；" in text


def test_text_review_line_is_unchanged_when_no_cue_is_ocr_agreement(run, tmp_path):
    text = build(run, tmp_path, manifest(tmp_path, [cue(1), cue(2)]))

    assert "字幕文字校核：已对照字幕画面目视核对；非逐字人工听写" in text


def test_timeline_line_summarises_gaps_instead_of_a_placeholder(run, tmp_path):
    gaps = [{"start_ms": 0, "end_ms": 3000, "reason": "片头"},
            {"start_ms": 30000, "end_ms": 31500, "reason": "批次接缝"},
            {"start_ms": 58000, "end_ms": 60000, "reason": "片尾"}]

    text = build(run, tmp_path, manifest(tmp_path, [cue(4)], gaps=gaps, capture_coverage="incomplete"))

    assert "字幕时间轴覆盖：共 3 处未采集区段，合计 6.5 秒（见文末「字幕缺口」），不能认定为全片时间轴完整。" in text
