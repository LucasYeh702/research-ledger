import shutil
import unicodedata

import pytest

from research_ledger.ledger import Ledger


def test_moving_entire_obsidian_vault_preserves_verification(tmp_path):
    original = tmp_path / "法學知識腦-v1"
    note_dir = original / "03-法學碩論" / "06-人工智慧協作方法框架"
    note_dir.mkdir(parents=True)
    note = note_dir / "001-命題.md"
    note.write_text("AI 協作研究需要可驗證留痕。\n", encoding="utf-8")

    ledger = Ledger.init(original)
    event = ledger.record(note, event_type="claim")
    ledger.seal(label="before-move")
    moved = tmp_path / "新電腦-法學知識腦-v1"
    shutil.copytree(original, moved)

    moved_ledger = Ledger(moved)
    moved_event = moved_ledger.events()[0]

    assert event.content_path == "03-法學碩論/06-人工智慧協作方法框架/001-命題.md"
    assert moved_event.content_hash == event.content_hash
    assert moved_ledger.verify().ok


def test_verify_warns_if_line_endings_change_during_migration(tmp_path):
    original = tmp_path / "vault"
    original.mkdir()
    note = original / "claim.md"
    note.write_bytes("第一行\n第二行\n".encode("utf-8"))

    ledger = Ledger.init(original)
    ledger.record(note, event_type="claim")
    moved = tmp_path / "moved-vault"
    shutil.copytree(original, moved)
    moved_note = moved / "claim.md"
    moved_note.write_bytes("第一行\r\n第二行\r\n".encode("utf-8"))

    result = Ledger(moved).verify()

    assert result.ok
    assert any("working file changed since snapshot" in issue for issue in result.warnings)


def test_revising_a_wrong_conclusion_records_a_new_snapshot_without_breaking_history(tmp_path):
    workspace = tmp_path / "vault"
    workspace.mkdir()
    note = workspace / "claim.md"
    note.write_text("初步結論：A。\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    first = ledger.record(note, event_type="claim")
    note.write_text("修正結論：A 是錯的，應改為 B。\n", encoding="utf-8")
    second = ledger.record(note, event_type="adjudication", metadata={"reason": "new source found"})

    result = ledger.verify()

    assert result.ok
    assert result.warnings == []
    assert first.content_hash != second.content_hash
    assert first.snapshot_path != second.snapshot_path
    assert "初步結論：A。" in (workspace / first.snapshot_path).read_text(encoding="utf-8")
    assert "修正結論" in (workspace / second.snapshot_path).read_text(encoding="utf-8")


def test_only_moving_notes_without_ledger_is_not_verifiable(tmp_path):
    original = tmp_path / "vault"
    original.mkdir()
    note = original / "claim.md"
    note.write_text("研究命題\n", encoding="utf-8")
    Ledger.init(original).record(note, event_type="claim")
    notes_only = tmp_path / "notes-only"
    notes_only.mkdir()
    shutil.copy2(note, notes_only / "claim.md")

    with pytest.raises(FileNotFoundError):
        Ledger(notes_only).verify()


def test_delete_event_stops_permanent_missing_file_warning(tmp_path):
    workspace = tmp_path / "vault"
    workspace.mkdir()
    note = workspace / "obsolete.md"
    note.write_text("後來證明不需要的筆記\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="claim")
    note.unlink()
    before_delete = ledger.verify()
    ledger.record_delete("obsolete.md", metadata={"reason": "merged into newer note"})
    after_delete = ledger.verify()

    assert before_delete.ok
    assert any("working file missing since snapshot" in issue for issue in before_delete.warnings)
    assert after_delete.ok
    assert after_delete.warnings == []


def test_rename_event_stops_permanent_old_path_warning(tmp_path):
    workspace = tmp_path / "vault"
    workspace.mkdir()
    old_note = workspace / "舊命題.md"
    new_note = workspace / "新命題.md"
    old_note.write_text("命題內容\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    ledger.record(old_note, event_type="claim")
    old_note.rename(new_note)
    before_rename = ledger.verify()
    event = ledger.record_rename("舊命題.md", "新命題.md", metadata={"reason": "renamed in Obsidian"})
    after_rename = ledger.verify()

    assert before_rename.ok
    assert any("working file missing since snapshot" in issue for issue in before_rename.warnings)
    assert event.event_type == "rename"
    assert event.metadata["new_path"] == "新命題.md"
    assert after_rename.ok
    assert after_rename.warnings == []


def test_unicode_normalized_filename_still_resolves_working_file(tmp_path):
    workspace = tmp_path / "vault"
    workspace.mkdir()
    nfc_name = unicodedata.normalize("NFC", "café.md")
    nfd_name = unicodedata.normalize("NFD", "café.md")
    note = workspace / nfc_name
    note.write_text("Unicode filename note\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="claim")
    note.rename(workspace / nfd_name)

    result = ledger.verify()

    assert result.ok
    assert result.warnings == []


def test_verify_warns_on_out_of_order_timestamps(tmp_path, monkeypatch):
    workspace = tmp_path / "vault"
    workspace.mkdir()
    first = workspace / "first.md"
    second = workspace / "second.md"
    first.write_text("first\n", encoding="utf-8")
    second.write_text("second\n", encoding="utf-8")
    times = iter(["2026-06-02T10:00:00Z", "2026-06-02T09:00:00Z"])

    Ledger.init(workspace)
    monkeypatch.setattr("research_ledger.ledger._now_utc", lambda: next(times))
    ledger = Ledger(workspace)
    ledger.record(first, event_type="claim")
    ledger.record(second, event_type="claim")

    result = ledger.verify()

    assert result.ok
    assert any("timestamp moved backwards" in warning for warning in result.warnings)
