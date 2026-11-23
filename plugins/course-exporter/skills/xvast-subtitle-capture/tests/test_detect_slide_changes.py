import json

from PIL import Image, ImageDraw

STATES = {"A": (250, 250, 250), "B": (30, 120, 200), "C": (200, 200, 60)}


def frame_index(tmp_path, sequence, step_ms=500, start_ms=0):
    rows = []
    for i, state in enumerate(sequence):
        path = tmp_path / f"f{i:03d}.png"
        image = Image.new("RGB", (200, 120), STATES[state])
        ImageDraw.Draw(image).rectangle((0, 100, 199, 119), fill=(0, 0, 0))  # subtitle band, ignored by region
        image.save(path)
        rows.append({"video_ms": start_ms + i * step_ms, "source": str(path)})
    index = tmp_path / "frame-index.jsonl"
    index.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return index


def detect(run, tmp_path, sequence, *extra, **kw):
    index = frame_index(tmp_path, sequence, **kw)
    return run("detect_slide_changes.py", "--frame-index", index, "--region", "0,0,200,100", *extra)


def test_reports_the_time_of_each_real_slide_change(run, tmp_path):
    code, payload, out, err = detect(run, tmp_path, "AAABBBCC")

    assert code == 0, out + err
    assert [c["time_ms"] for c in payload["changes"]] == [1500, 3000]
    assert payload["flicker"] == []


def test_segments_cover_the_stable_stretches_between_changes(run, tmp_path):
    code, payload, out, err = detect(run, tmp_path, "AAABBBCC")

    assert [(s["start_ms"], s["end_ms"]) for s in payload["segments"]] == [(0, 1000), (1500, 2500), (3000, 3500)]


def test_alternating_frames_are_flicker_not_slide_changes(run, tmp_path):
    code, payload, out, err = detect(run, tmp_path, "AAABABACCC")

    assert code == 0, out + err
    assert [c["time_ms"] for c in payload["changes"]] == [3500]
    assert len(payload["flicker"]) == 1
    flicker = payload["flicker"][0]
    assert flicker["start_ms"] == 1500 and flicker["end_ms"] == 3000


def test_frames_closer_than_the_minimum_gap_count_once(run, tmp_path):
    index = frame_index(tmp_path, "AAB", step_ms=100)  # 100 ms apart: a stray duplicate must not look like a change

    code, payload, out, err = run("detect_slide_changes.py", "--frame-index", index, "--region", "0,0,200,100",
                                  "--min-gap-ms", "300")

    assert code == 0, out + err
    assert payload["changes"] == []


def test_subtitle_band_changes_are_ignored_by_the_region(run, tmp_path):
    rows = []
    for i, band in enumerate([(0, 0, 0), (255, 255, 255), (0, 0, 0)]):
        path = tmp_path / f"s{i}.png"
        image = Image.new("RGB", (200, 120), STATES["A"])
        ImageDraw.Draw(image).rectangle((0, 100, 199, 119), fill=band)
        image.save(path)
        rows.append({"video_ms": i * 500, "source": str(path)})
    index = tmp_path / "idx.jsonl"
    index.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    code, payload, out, err = run("detect_slide_changes.py", "--frame-index", index, "--region", "0,0,200,100")

    assert payload["changes"] == []


def test_small_differences_are_labelled_content_and_large_ones_slide(run, tmp_path):
    rows = []
    for i, color in enumerate([(250, 250, 250), (250, 250, 250), (247, 247, 247), (247, 247, 247),
                               (30, 30, 30), (30, 30, 30)]):
        path = tmp_path / f"k{i}.png"
        Image.new("RGB", (200, 120), color).save(path)
        rows.append({"video_ms": i * 500, "source": str(path)})
    index = tmp_path / "idx.jsonl"
    index.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    code, payload, out, err = run("detect_slide_changes.py", "--frame-index", index, "--region", "0,0,200,100",
                                  "--threshold", "1.5", "--slide-threshold", "5")

    assert [(c["time_ms"], c["kind"]) for c in payload["changes"]] == [(1000, "content"), (2000, "slide")]
