import json

from conftest import write_json


def jsonl(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path


def test_flags_reads_that_contradict_mobile_vision_or_copy_server_only(tmp_path, run):
    events = jsonl(tmp_path / "events.jsonl", [
        {"id": "e1", "mobile": "我们来看", "server": "找们来看"},       # read copied server's look-alike
        {"id": "e2", "mobile": "今天的直播", "server": "今大的直播"},   # read contradicts mobile = Vision (and copies server)
        {"id": "e3", "mobile": "好的啊", "server": "好的啊"},           # read agrees -> no flag
        {"id": "e4", "mobile": "小币值", "server": "小币值"},           # read differs but no M=V agreement
        {"id": "e5", "mobile": "什么", "server": "什么"},               # DROP is never flagged
        {"id": "e6", "mobile": "风火轮Accessibility: Unavailable", "server": "风灭轮"},  # UI noise ignored
    ])
    vision = jsonl(tmp_path / "vision.jsonl", [
        {"id": "e1", "vision": "我们来看"}, {"id": "e2", "vision": "今天的直播"},
        {"id": "e3", "vision": "好的啊"}, {"id": "e4", "vision": "小市值"},
        {"id": "e5", "vision": "什么"}, {"id": "e6", "vision": "风火轮"},
    ])
    cands = tmp_path / "candidates.txt"
    cands.write_text("".join(f"{i} e{i} x\n" for i in range(1, 7)), encoding="utf-8")
    reads = write_json(tmp_path / "reader.json", {"items": [
        {"n": 1, "cand": "x", "read": "找们来看"}, {"n": 2, "cand": "x", "read": "今大的直播"},
        {"n": 3, "cand": "x", "read": "好的啊。"}, {"n": 4, "cand": "x", "read": "小币值"},
        {"n": 5, "cand": "x", "read": "DROP"}, {"n": 6, "cand": "x", "read": "风灭轮"}]})
    out = tmp_path / "flags.json"
    code, payload, _, err = run("check_reader_reads.py", "--reads", reads, "--candidates", cands,
                                "--events", events, "--vision", vision, "--output", out)
    assert code == 0, err
    flags = {f["n"]: f["reasons"] for f in json.loads(out.read_text(encoding="utf-8"))["flags"]}
    assert flags == {1: ["contradicts_mobile_vision", "server_only"],
                     2: ["contradicts_mobile_vision", "server_only"],
                     6: ["contradicts_mobile_vision", "server_only"]}
    assert payload == {"items": 6, "flagged": 3}


def test_refuses_to_overwrite_output(tmp_path, run):
    out = tmp_path / "flags.json"
    out.write_text("{}", encoding="utf-8")
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    cands = tmp_path / "c.txt"
    cands.write_text("", encoding="utf-8")
    reads = write_json(tmp_path / "r.json", {"items": []})
    code, _, _, _ = run("check_reader_reads.py", "--reads", reads, "--candidates", cands,
                        "--events", empty, "--vision", empty, "--output", out)
    assert code != 0
    assert out.read_text(encoding="utf-8") == "{}"
