import json

from conftest import write_json


def candidates_file(tmp_path, n=4):
    cands = tmp_path / "candidates.txt"
    cands.write_text("".join(f"{i} ocr-{i:06d} 字{i}\n" for i in range(1, n + 1)), encoding="utf-8")
    return cands


def items(*pairs):
    return {"items": [{"n": n, "cand": f"字{n}", "read": read} for n, read in pairs]}


def join(run, tmp_path, cands, *chunks):
    out = tmp_path / "review-reader-1.json"
    code, payload, stdout, err = run("join_reader_chunks.py", "--candidates", cands, "--output", out, "--chunks", *chunks)
    return code, (json.loads(out.read_text(encoding="utf-8")) if out.exists() else None), stdout + err


def test_chunks_join_in_number_order_and_a_retry_file_overrides(run, tmp_path):
    cands = candidates_file(tmp_path)
    c1 = write_json(tmp_path / "c1.json", items((1, "甲"), (2, "乙")))
    c2 = write_json(tmp_path / "c2.json", items((3, "丙"), (4, "丁")))
    retry = write_json(tmp_path / "c2b.json", items((4, "DROP")))

    code, joined, log = join(run, tmp_path, cands, c2, c1, retry)

    assert code == 0, log
    assert [(i["n"], i["read"]) for i in joined["items"]] == [(1, "甲"), (2, "乙"), (3, "丙"), (4, "DROP")]


def test_a_missing_number_fails_and_writes_nothing(run, tmp_path):
    cands = candidates_file(tmp_path)
    c1 = write_json(tmp_path / "c1.json", items((1, "甲"), (2, "乙"), (4, "丁")))

    code, joined, log = join(run, tmp_path, cands, c1)

    assert code != 0 and joined is None and "3" in log


def test_a_number_repeated_inside_one_chunk_fails(run, tmp_path):
    cands = candidates_file(tmp_path, n=2)
    c1 = write_json(tmp_path / "c1.json", items((1, "甲"), (1, "甲甲"), (2, "乙")))

    code, joined, log = join(run, tmp_path, cands, c1)

    assert code != 0 and joined is None
