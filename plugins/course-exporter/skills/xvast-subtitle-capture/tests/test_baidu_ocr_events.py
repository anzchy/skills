import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from PIL import Image
from conftest import SCRIPTS, write_json

STUB = Path(__file__).resolve().parent / "stub_baidu.py"


@pytest.fixture
def server(tmp_path):
    answers = tmp_path / "answers.json"
    log = tmp_path / "requests.log"
    procs = []

    def start(answer_list):
        write_json(answers, answer_list)
        proc = subprocess.Popen([sys.executable, str(STUB)], stdout=subprocess.PIPE, text=True,
                                env={**os.environ, "STUB_BAIDU_MAP": str(answers), "STUB_BAIDU_LOG": str(log)})
        procs.append(proc)
        return f"http://127.0.0.1:{int(proc.stdout.readline())}", log

    yield start
    for proc in procs:
        proc.terminate()


def candidates(tmp_path, mobile, server_text):
    rows = []
    for i, (m, s) in enumerate(zip(mobile, server_text), 1):
        frame = tmp_path / f"f{i}.png"
        Image.new("RGB", (800, 300), "white").save(frame)
        rows.append({"id": f"ocr-{i:06d}", "start_ms": i * 1000, "mobile": m, "server": s, "frame": str(frame)})
    path = tmp_path / "candidates.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path


def run_baidu(tmp_path, base, candidates_path, creds="KEY\nSECRET", extra=()):
    cred = tmp_path / "credentials"
    cred.write_text(f"BAIDU_OCR_API_KEY={creds.splitlines()[0]}\nBAIDU_OCR_SECRET_KEY={creds.splitlines()[1]}\n")
    cred.chmod(0o600)
    out = tmp_path / "baidu.jsonl"
    report = tmp_path / "triage.json"
    env = {k: v for k, v in os.environ.items() if not k.startswith("BAIDU_")}
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "baidu_ocr_events.py"), "--candidates", str(candidates_path),
         "--strip-crop", "0,100,800,300", "--credentials", str(cred), "--api-base", base,
         "--output-jsonl", str(out), "--output-report", str(report), *extra],
        capture_output=True, text=True, env=env)
    return proc, out, report


def test_three_way_agreement_is_auto_accepted_and_the_rest_needs_review(tmp_path, server):
    base, log = server([["我们开始"], ["找们之前"], ["你好呢"]])
    path = candidates(tmp_path, ["我们开始", "找们之前", "你好呃"], ["我们开始", "我们之前", "你好呢"])

    proc, out, report = run_baidu(tmp_path, base, path)

    assert proc.returncode == 0, proc.stderr
    triage = json.loads(report.read_text(encoding="utf-8"))
    assert triage["events"] == 3 and triage["agree"] == 1
    assert [e["id"] for e in triage["needs_review"]] == ["ocr-000002", "ocr-000003"]
    second = triage["needs_review"][0]
    assert (second["mobile"], second["server"], second["baidu"]) == ("找们之前", "我们之前", "找们之前")


def test_whitespace_and_line_splits_do_not_count_as_disagreement(tmp_path, server):
    base, log = server([["我们 开始", "啊"]])
    path = candidates(tmp_path, ["我们开始啊"], ["我们开始啊"])

    proc, out, report = run_baidu(tmp_path, base, path)

    assert json.loads(report.read_text(encoding="utf-8"))["agree"] == 1


def test_credentials_are_never_printed_or_written_to_outputs(tmp_path, server):
    base, log = server([["甲"]])
    path = candidates(tmp_path, ["甲"], ["甲"])

    proc, out, report = run_baidu(tmp_path, base, path)

    everything = proc.stdout + proc.stderr + out.read_text(encoding="utf-8") + report.read_text(encoding="utf-8")
    assert "SECRET" not in everything and "TOKEN" not in everything


def test_token_is_requested_once_for_many_events(tmp_path, server):
    base, log = server([["甲"], ["乙"], ["丙"]])
    path = candidates(tmp_path, ["甲", "乙", "丙"], ["甲", "乙", "丙"])

    run_baidu(tmp_path, base, path)

    paths = [json.loads(l)["path"] for l in log.read_text().splitlines()]
    assert paths.count("/oauth/2.0/token") == 1 and sum(p.endswith("accurate_basic") for p in paths) == 3


def test_wrong_credentials_fail_before_any_image_is_sent(tmp_path, server):
    base, log = server([["甲"]])
    path = candidates(tmp_path, ["甲"], ["甲"])

    proc, out, report = run_baidu(tmp_path, base, path, creds="BAD\nBAD")

    assert proc.returncode != 0
    assert not any(json.loads(l)["has_image"] for l in log.read_text().splitlines())
    assert not report.exists()


def test_missing_credentials_file_is_an_error(tmp_path):
    path = candidates(tmp_path, ["甲"], ["甲"])
    env = {k: v for k, v in os.environ.items() if not k.startswith("BAIDU_")}
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "baidu_ocr_events.py"), "--candidates", str(path),
         "--credentials", str(tmp_path / "nope"), "--output-jsonl", str(tmp_path / "o"),
         "--output-report", str(tmp_path / "r")], capture_output=True, text=True, env=env)
    assert proc.returncode != 0 and "credentials" in proc.stderr.lower()


def test_an_api_error_for_one_event_marks_it_for_review_instead_of_agreeing(tmp_path, server):
    base, log = server([{"error_code": 216202, "error_msg": "image size error"}, ["乙"]])
    path = candidates(tmp_path, ["甲", "乙"], ["甲", "乙"])

    proc, out, report = run_baidu(tmp_path, base, path)

    triage = json.loads(report.read_text(encoding="utf-8"))
    assert [e["id"] for e in triage["needs_review"]] == ["ocr-000001"]
    assert triage["needs_review"][0]["baidu_error"] is not None


def test_dry_run_sends_nothing_and_reports_how_many_images_would_go_out(tmp_path, server):
    base, log = server([["甲"]])
    path = candidates(tmp_path, ["甲", "乙"], ["甲", "乙"])

    proc, out, report = run_baidu(tmp_path, base, path, extra=["--dry-run"])

    assert proc.returncode == 0
    assert json.loads(proc.stdout)["would_send"] == 2
    assert not log.exists() or log.read_text() == ""


def test_a_credentials_file_readable_by_others_is_rejected(tmp_path):
    path = candidates(tmp_path, ["甲"], ["甲"])
    cred = tmp_path / "credentials"
    cred.write_text("BAIDU_OCR_API_KEY=KEY\nBAIDU_OCR_SECRET_KEY=SECRET\n")
    cred.chmod(0o644)
    env = {k: v for k, v in os.environ.items() if not k.startswith("BAIDU_")}
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "baidu_ocr_events.py"), "--candidates", str(path),
         "--credentials", str(cred), "--output-jsonl", str(tmp_path / "o"),
         "--output-report", str(tmp_path / "r")], capture_output=True, text=True, env=env)
    assert proc.returncode != 0 and "chmod 600" in proc.stderr
    assert "SECRET" not in proc.stdout + proc.stderr


def triage_of(tmp_path, server, mobile, server_text, baidu_answers):
    base, log = server(baidu_answers)
    path = candidates(tmp_path, mobile, server_text)
    proc, out, report = run_baidu(tmp_path, base, path)
    assert proc.returncode == 0, proc.stderr
    return json.loads(report.read_text(encoding="utf-8"))


def test_axis_labels_around_the_subtitle_do_not_break_agreement(tmp_path, server):
    triage = triage_of(tmp_path, server, ["我们开始"], ["我们开始"], [["201620182020", "我们开始", "6日12日"]])
    assert triage["agree"] == 1 and triage["needs_review"] == []


def test_server_and_baidu_agreeing_against_mobile_is_accepted_as_two_model(tmp_path, server):
    triage = triage_of(tmp_path, server, ["找们之前"], ["我们之前"], [["我们之前"]])
    assert triage["agree"] == 0 and triage["two_model"] == 1 and triage["needs_review"] == []
    assert triage["two_model_ids"] == ["ocr-000001"]


def test_filler_particles_always_go_to_review_even_when_two_models_agree(tmp_path, server):
    triage = triage_of(tmp_path, server, ["然后呢呢介绍"], ["然后呢呃介绍"], [["然后呢呃介绍"]])
    assert triage["two_model"] == 0
    assert [e["id"] for e in triage["needs_review"]] == ["ocr-000001"]


def test_baidu_reading_different_characters_goes_to_review(tmp_path, server):
    triage = triage_of(tmp_path, server, ["石侧交易"], ["石侧交易"], [["右侧交易"]])
    assert [e["id"] for e in triage["needs_review"]] == ["ocr-000001"]


def test_qps_limit_errors_are_retried_and_the_retry_result_is_used(tmp_path, server):
    triage = triage_of(tmp_path, server, ["甲"], ["甲"],
                       [{"error_code": 18, "error_msg": "Open api qps request limit reached"}, ["甲"]])
    assert triage["agree"] == 1 and triage["needs_review"] == []


@pytest.mark.parametrize("text", ["high那个那个走势基本一致啊", "他跌了6日12日8日", "分布在2016201820", "跌到低位对不对10月19日"])
def test_chart_label_noise_in_the_text_always_goes_to_review(tmp_path, server, text):
    triage = triage_of(tmp_path, server, [text], [text], [[text]])
    assert triage["agree"] == 0 and [e["id"] for e in triage["needs_review"]] == ["ocr-000001"]


def test_ordinary_numbers_in_speech_are_not_flagged(tmp_path, server):
    triage = triage_of(tmp_path, server, ["最大回撤26%左右啊"], ["最大回撤26%左右啊"], [["最大回撤26%左右啊"]])
    assert triage["agree"] == 1
