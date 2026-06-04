import zipfile
import json

from typer.testing import CliRunner

from research_ledger.cli import app


def test_cli_init_record_verify_report(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("AI 協作研究需要揭露。\n", encoding="utf-8")

    init_result = runner.invoke(app, ["init"])
    record_result = runner.invoke(app, ["record", str(note), "--type", "claim"])
    seal_result = runner.invoke(app, ["seal", "--label", "demo"])
    verify_result = runner.invoke(app, ["verify"])
    report_result = runner.invoke(app, ["report"])

    assert init_result.exit_code == 0
    assert record_result.exit_code == 0
    assert seal_result.exit_code == 0
    assert verify_result.exit_code == 0
    assert report_result.exit_code == 0
    assert "events: 1" in report_result.output


def test_cli_init_accepts_scope_declaration_options(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    notes = tmp_path / "notes"
    notes.mkdir()

    init_result = runner.invoke(
        app,
        [
            "init",
            "--scope-title",
            "AI 協作論文研究",
            "--scope-description",
            "涵蓋 notes 內的研究筆記。",
            "--include",
            "notes",
            "--exclude",
            "notes/private",
        ],
    )

    assert init_result.exit_code == 0
    scope = (tmp_path / ".research-ledger" / "scope.json").read_text(encoding="utf-8")
    assert '"title": "AI 協作論文研究"' in scope
    assert '"description": "涵蓋 notes 內的研究筆記。"' in scope
    assert '"notes"' in scope
    assert '"notes/private"' in scope


def test_cli_verify_returns_warning_exit_code_for_working_file_drift(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("AI 協作研究需要揭露。\n", encoding="utf-8")

    runner.invoke(app, ["init"])
    runner.invoke(app, ["record", str(note), "--type", "claim"])
    note.write_text("被竄改\n", encoding="utf-8")

    verify_result = runner.invoke(app, ["verify"])

    assert verify_result.exit_code == 1
    assert "working file changed since snapshot" in verify_result.stderr


def test_cli_verify_no_working_tree_skips_working_file_warnings(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("AI 協作研究需要揭露。\n", encoding="utf-8")

    runner.invoke(app, ["init"])
    runner.invoke(app, ["record", str(note), "--type", "claim"])
    note.unlink()
    warning_result = runner.invoke(app, ["verify"])
    archive_result = runner.invoke(app, ["verify", "--no-working-tree"])

    assert warning_result.exit_code == 1
    assert "working file missing since snapshot" in warning_result.stderr
    assert archive_result.exit_code == 0
    assert "ok: 1 events verified" in archive_result.output


def test_cli_export_disclosure_outputs_markdown_and_json(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("AI 協作研究需要揭露。\n", encoding="utf-8")

    runner.invoke(app, ["init"])
    runner.invoke(app, ["record", str(note), "--type", "claim"])
    markdown_result = runner.invoke(app, ["export-disclosure"])
    json_path = tmp_path / "disclosure.json"
    json_result = runner.invoke(
        app,
        ["export-disclosure", "--format", "json", "--output", str(json_path)],
    )

    assert markdown_result.exit_code == 0
    assert "# AI 使用揭露草稿" in markdown_result.output
    assert json_result.exit_code == 0
    assert json_path.exists()
    assert '"event_count": 1' in json_path.read_text(encoding="utf-8")


def test_cli_export_bundle_excludes_private_key_and_verifies_without_working_tree(
    tmp_path, monkeypatch
):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("AI 協作研究需要揭露。\n", encoding="utf-8")
    bundle_path = tmp_path / "audit-bundle.zip"

    runner.invoke(app, ["init"])
    runner.invoke(app, ["record", str(note), "--type", "claim"])
    runner.invoke(app, ["seal", "--label", "demo"])
    result = runner.invoke(app, ["export-bundle", "--output", str(bundle_path)])

    assert result.exit_code == 0
    assert bundle_path.exists()
    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        assert ".research-ledger/ledger.json" in names
        assert ".research-ledger/genesis.json" in names
        assert ".research-ledger/scope.json" in names
        assert ".research-ledger/events.jsonl" in names
        assert "REPORT.md" in names
        assert "VERIFY.md" in names
        assert ".research-ledger/private_key.pem" not in names
        assert any(name.startswith(".research-ledger/snapshots/") for name in names)
        assert any(name.startswith(".research-ledger/seals/") for name in names)
        extract_dir = tmp_path / "extracted-bundle"
        archive.extractall(extract_dir)

    monkeypatch.chdir(extract_dir)
    verify_result = runner.invoke(app, ["verify", "--no-working-tree"])

    assert verify_result.exit_code == 0
    assert "ok: 1 events verified" in verify_result.output


def test_cli_verify_uninitialized_returns_exit_code_3_without_traceback(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["verify"])

    assert result.exit_code == 3
    assert "ledger not initialized" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_verify_malformed_metadata_returns_exit_code_3_without_traceback(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    runner.invoke(app, ["init"])
    metadata_path = tmp_path / ".research-ledger" / "ledger.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.pop("ledger_id")
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = runner.invoke(app, ["verify"])

    assert result.exit_code == 3
    assert "ledger_id" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_report_malformed_event_returns_exit_code_3_without_traceback(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("AI 協作研究需要揭露。\n", encoding="utf-8")

    runner.invoke(app, ["init"])
    runner.invoke(app, ["record", str(note), "--type", "claim"])
    events_path = tmp_path / ".research-ledger" / "events.jsonl"
    event = json.loads(events_path.read_text(encoding="utf-8"))
    event.pop("event_id")
    events_path.write_text(json.dumps(event), encoding="utf-8")

    result = runner.invoke(app, ["report"])

    assert result.exit_code == 3
    assert "event_id" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_export_disclosure_malformed_scope_returns_exit_code_3_without_traceback(
    tmp_path, monkeypatch
):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    runner.invoke(app, ["init"])
    scope_path = tmp_path / ".research-ledger" / "scope.json"
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    scope.pop("included_paths")
    scope_path.write_text(json.dumps(scope), encoding="utf-8")

    result = runner.invoke(app, ["export-disclosure"])

    assert result.exit_code == 3
    assert "included_paths" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_export_disclosure_uninitialized_returns_exit_code_3(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["export-disclosure"])

    assert result.exit_code == 3
    assert "ledger not initialized" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_record_outside_workspace_returns_exit_code_2_without_traceback(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    outside = tmp_path.parent / "outside.md"
    outside.write_text("secret\n", encoding="utf-8")

    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["record", str(outside), "--type", "claim"])

    assert result.exit_code == 2
    assert "outside ledger workspace" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_record_internal_ledger_file_returns_exit_code_2_without_traceback(
    tmp_path, monkeypatch
):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["record", ".research-ledger/private_key.pem", "--type", "claim"])

    assert result.exit_code == 2
    assert "internal ledger files are not supported" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_seal_and_report_uninitialized_return_exit_code_3(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    seal_result = runner.invoke(app, ["seal"])
    report_result = runner.invoke(app, ["report"])

    assert seal_result.exit_code == 3
    assert report_result.exit_code == 3
    assert "ledger not initialized" in seal_result.stderr
    assert "ledger not initialized" in report_result.stderr
    assert "Traceback" not in seal_result.stderr
    assert "Traceback" not in report_result.stderr


def test_cli_delete_and_rename_clear_drift_warnings(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    old_note = tmp_path / "old.md"
    new_note = tmp_path / "new.md"
    obsolete = tmp_path / "obsolete.md"
    old_note.write_text("renamed note\n", encoding="utf-8")
    obsolete.write_text("deleted note\n", encoding="utf-8")

    runner.invoke(app, ["init"])
    runner.invoke(app, ["record", str(old_note), "--type", "claim"])
    runner.invoke(app, ["record", str(obsolete), "--type", "claim"])
    old_note.rename(new_note)
    obsolete.unlink()
    warning_result = runner.invoke(app, ["verify"])
    rename_result = runner.invoke(app, ["rename", "old.md", "new.md", "--reason", "Obsidian rename"])
    delete_result = runner.invoke(app, ["delete", "obsolete.md", "--reason", "Removed stale note"])
    verify_result = runner.invoke(app, ["verify"])

    assert warning_result.exit_code == 1
    assert rename_result.exit_code == 0
    assert delete_result.exit_code == 0
    assert verify_result.exit_code == 0


def test_cli_verify_uses_structured_issue_code_for_snapshot_missing(
    tmp_path, monkeypatch
):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("AI 協作研究需要揭露。\n", encoding="utf-8")

    runner.invoke(app, ["init"])
    runner.invoke(app, ["record", str(note), "--type", "claim"])
    events_path = tmp_path / ".research-ledger" / "events.jsonl"
    event = json.loads(events_path.read_text(encoding="utf-8"))
    event["snapshot_path"] = ".research-ledger/snapshots/missing.json"
    events_path.write_text(json.dumps(event), encoding="utf-8")

    result = runner.invoke(app, ["verify"])

    assert result.exit_code == 4
    assert "snapshot" in result.stderr


def test_cli_verify_uses_structured_issue_code_for_malformed_event(
    tmp_path, monkeypatch
):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("AI 協作研究需要揭露。\n", encoding="utf-8")

    runner.invoke(app, ["init"])
    runner.invoke(app, ["record", str(note), "--type", "claim"])
    events_path = tmp_path / ".research-ledger" / "events.jsonl"
    event = json.loads(events_path.read_text(encoding="utf-8"))
    event.pop("sequence")
    events_path.write_text(json.dumps(event), encoding="utf-8")

    result = runner.invoke(app, ["verify"])

    assert result.exit_code == 3
    assert "sequence" in result.stderr
    assert "Traceback" not in result.stderr
