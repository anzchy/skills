from conftest import batch_log, minimal_manifest, write_json


def validate(run, tmp_path, *extra):
    manifest = minimal_manifest(tmp_path)
    return run("validate_capture.py", "--manifest", manifest, *extra)


def test_batch_list_validates_only_listed_batches(run, tmp_path):
    root = tmp_path / ".raw"
    write_json(root / "main-001" / "frames.json", batch_log())
    write_json(root / "legacy-pending" / "frames.json", batch_log(status="pending_manual_review"))
    listing = tmp_path / "batches.txt"
    listing.write_text("main-001\n", encoding="utf-8")

    code, payload, out, err = validate(run, tmp_path, "--batch-root", root, "--batch-list", listing,
                                       "--require-viewport-review")

    assert code == 0, out + err
    assert payload["valid_batches_checked"] == 1


def test_batch_list_with_missing_batch_fails_with_error(run, tmp_path):
    root = tmp_path / ".raw"
    write_json(root / "main-001" / "frames.json", batch_log())
    listing = tmp_path / "batches.txt"
    listing.write_text("main-001\nmain-002\n", encoding="utf-8")

    code, payload, out, err = validate(run, tmp_path, "--batch-root", root, "--batch-list", listing)

    assert code == 1
    assert payload is not None, err
    assert any("main-002" in e for e in payload["errors"])


def test_batch_list_still_rejects_a_listed_pending_batch(run, tmp_path):
    root = tmp_path / ".raw"
    write_json(root / "main-001" / "frames.json", batch_log(status="pending_manual_review"))
    listing = tmp_path / "batches.txt"
    listing.write_text("main-001\n", encoding="utf-8")

    code, payload, out, err = validate(run, tmp_path, "--batch-root", root, "--batch-list", listing)

    assert code == 1
    assert any("pending manual review" in e for e in payload["errors"])


def test_batch_list_without_batch_root_is_an_error(run, tmp_path):
    listing = tmp_path / "batches.txt"
    listing.write_text("main-001\n", encoding="utf-8")

    code, payload, out, err = validate(run, tmp_path, "--batch-list", listing)

    assert code == 1
    assert any("--batch-root" in e for e in payload["errors"])


def edge_viewport(**over):
    view = {"player_top_visible": True, "player_bottom_visible": True,
            "player_left_visible": True, "player_right_visible": True,
            "controls_visible": True, "scroll_state": "player_fully_in_view",
            "evidence": "layout.png"}
    view.update(over)
    return view


def run_with_viewport(run, tmp_path, viewport):
    root = tmp_path / ".raw"
    write_json(root / "main-001" / "frames.json", batch_log(viewport=False, viewport_review=viewport))
    listing = tmp_path / "batches.txt"
    listing.write_text("main-001\n", encoding="utf-8")
    return validate(run, tmp_path, "--batch-root", root, "--batch-list", listing, "--require-viewport-review")


def test_per_edge_viewport_fields_written_by_capture_tool_are_accepted(run, tmp_path):
    code, payload, out, err = run_with_viewport(run, tmp_path, edge_viewport())
    assert code == 0, out + err


def test_one_hidden_edge_fails_viewport_review(run, tmp_path):
    code, payload, out, err = run_with_viewport(run, tmp_path, edge_viewport(player_bottom_visible=False))
    assert code == 1
    assert any("viewport_review" in e for e in payload["errors"])


def test_unreviewed_edges_fail_viewport_review(run, tmp_path):
    code, payload, out, err = run_with_viewport(run, tmp_path, edge_viewport(player_top_visible=None))
    assert code == 1


def test_missing_evidence_fails_viewport_review(run, tmp_path):
    code, payload, out, err = run_with_viewport(run, tmp_path, edge_viewport(evidence=""))
    assert code == 1
