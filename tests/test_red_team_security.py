import os
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import socket

import pytest

import research_ledger.ledger as ledger_module
from research_ledger.bundle import export_audit_bundle
from research_ledger.crypto import merkle_root
from research_ledger.ledger import Ledger


def test_record_rejects_paths_outside_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("secret\n", encoding="utf-8")

    ledger = Ledger.init(workspace)

    with pytest.raises(ValueError, match="outside ledger workspace"):
        ledger.record(outside, event_type="claim")
    assert list((workspace / ".research-ledger" / "snapshots").glob("*")) == []


def test_record_rejects_directory_paths(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ledger = Ledger.init(workspace)

    with pytest.raises(ValueError, match="directories are not supported"):
        ledger.record(workspace, event_type="claim")


def test_record_rejects_internal_ledger_files(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ledger = Ledger.init(workspace)

    with pytest.raises(ValueError, match="internal ledger files are not supported"):
        ledger.record(ledger.private_key_path, event_type="claim")
    assert list((workspace / ".research-ledger" / "snapshots").glob("*")) == []


def test_record_rejects_symbolic_link_paths(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symbolic links are not supported on this platform")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "note.md"
    link = workspace / "linked-note.md"
    target.write_text("claim\n", encoding="utf-8")
    link.symlink_to(target)

    ledger = Ledger.init(workspace)

    with pytest.raises(ValueError, match="symbolic links are not supported"):
        ledger.record(link, event_type="claim")
    assert list((workspace / ".research-ledger" / "snapshots").glob("*")) == []


def test_record_rejects_non_regular_file_paths(tmp_path):
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO files are not supported on this platform")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fifo = workspace / "named-pipe"
    os.mkfifo(fifo)

    ledger = Ledger.init(workspace)

    with pytest.raises(ValueError, match="only regular files are supported"):
        ledger.record(fifo, event_type="claim")
    assert list((workspace / ".research-ledger" / "snapshots").glob("*")) == []


def test_record_refuses_when_write_lock_is_held(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "note.md"
    note.write_text("claim\n", encoding="utf-8")
    ledger = Ledger.init(workspace)
    (ledger.ledger_dir / "write.lock").write_text("locked\n", encoding="utf-8")
    monkeypatch.setattr(ledger_module, "LOCK_TIMEOUT_SECONDS", 0, raising=False)

    with pytest.raises(TimeoutError, match="ledger write lock"):
        ledger.record(note, event_type="claim")


def test_seal_refuses_when_write_lock_is_held(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "note.md"
    note.write_text("claim\n", encoding="utf-8")
    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="claim")
    (ledger.ledger_dir / "write.lock").write_text("locked\n", encoding="utf-8")
    monkeypatch.setattr(ledger_module, "LOCK_TIMEOUT_SECONDS", 0, raising=False)

    with pytest.raises(TimeoutError, match="ledger write lock"):
        ledger.seal(label="blocked")


def test_record_recovers_stale_write_lock_for_dead_same_host_pid(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "note.md"
    note.write_text("claim\n", encoding="utf-8")
    ledger = Ledger.init(workspace)
    ledger.lock_path.write_text(
        json.dumps(
            {
                "pid": 999999999,
                "hostname": socket.gethostname(),
                "created_at": "2026-06-04T00:00:00Z",
                "token": "stale-test",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ledger_module, "_process_exists", lambda pid: False)

    event = ledger.record(note, event_type="claim")

    assert event.sequence == 1
    assert not ledger.lock_path.exists()


def test_record_keeps_active_write_lock_for_live_same_host_pid(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "note.md"
    note.write_text("claim\n", encoding="utf-8")
    ledger = Ledger.init(workspace)
    lock_body = (
        json.dumps(
            {
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "created_at": "2026-06-04T00:00:00Z",
                "token": "active-test",
            }
        )
        + "\n"
    )
    ledger.lock_path.write_text(lock_body, encoding="utf-8")
    monkeypatch.setattr(ledger_module, "LOCK_TIMEOUT_SECONDS", 0, raising=False)
    monkeypatch.setattr(ledger_module, "_process_exists", lambda pid: True)

    with pytest.raises(TimeoutError, match="ledger write lock"):
        ledger.record(note, event_type="claim")

    assert ledger.lock_path.read_text(encoding="utf-8") == lock_body


def test_record_keeps_malformed_write_lock(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "note.md"
    note.write_text("claim\n", encoding="utf-8")
    ledger = Ledger.init(workspace)
    ledger.lock_path.write_text("locked\n", encoding="utf-8")
    monkeypatch.setattr(ledger_module, "LOCK_TIMEOUT_SECONDS", 0, raising=False)

    with pytest.raises(TimeoutError, match="ledger write lock"):
        ledger.record(note, event_type="claim")

    assert ledger.lock_path.read_text(encoding="utf-8") == "locked\n"


def test_init_refuses_to_regenerate_missing_private_key_for_existing_ledger(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ledger = Ledger.init(workspace)
    ledger.private_key_path.unlink()

    with pytest.raises(FileNotFoundError, match="private key missing"):
        Ledger.init(workspace)


def test_init_refuses_to_recreate_missing_genesis_when_events_exist(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "note.md"
    note.write_text("claim\n", encoding="utf-8")
    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="claim")
    ledger.genesis_path.unlink()

    with pytest.raises(FileNotFoundError, match="genesis missing"):
        Ledger.init(workspace)


def test_init_creates_internal_gitignore_for_secret_material(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    Ledger.init(workspace)

    gitignore = workspace / ".research-ledger" / ".gitignore"
    assert gitignore.exists()
    assert "private_key.pem" in gitignore.read_text(encoding="utf-8")


def test_init_restricts_private_ledger_directory_permissions(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX mode bits are not portable on Windows")
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    ledger = Ledger.init(workspace)

    assert ledger.ledger_dir.stat().st_mode & 0o777 == 0o700
    assert ledger.snapshots_dir.stat().st_mode & 0o777 == 0o700
    assert ledger.seals_dir.stat().st_mode & 0o777 == 0o700
    assert ledger.private_key_path.stat().st_mode & 0o777 == 0o600


def test_record_creates_private_snapshot_files(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX mode bits are not portable on Windows")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "note.md"
    note.write_text("claim\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    event = ledger.record(note, event_type="claim")
    ledger.seal(label="demo")
    snapshot = workspace / event.snapshot_path
    seal_path = next(ledger.seals_dir.glob("*.json"))

    assert snapshot.stat().st_mode & 0o777 == 0o600
    assert seal_path.stat().st_mode & 0o777 == 0o600


def test_verify_detects_tampered_seal(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "note.md"
    note.write_text("claim\n", encoding="utf-8")
    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="claim")
    ledger.seal(label="demo")
    seal_path = next((workspace / ".research-ledger" / "seals").glob("*.json"))
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    seal["merkle_root"] = "sha256:" + "0" * 64
    seal_path.write_text(json.dumps(seal), encoding="utf-8")

    result = Ledger(workspace).verify()

    assert not result.ok
    assert any("seal merkle root mismatch" in issue for issue in result.issues)


def test_verify_rejects_forged_unsigned_seal(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "note.md"
    note.write_text("claim\n", encoding="utf-8")
    ledger = Ledger.init(workspace)
    event = ledger.record(note, event_type="claim")
    forged = {
        "ledger_id": ledger.metadata().ledger_id,
        "label": "forged",
        "created_at": "2026-06-04T00:00:00Z",
        "event_count": 1,
        "merkle_root": merkle_root([event.event_hash]),
        "tip_event_hash": event.event_hash,
        "event_hashes": [event.event_hash],
    }
    forged_path = ledger.seals_dir / "20000101T000000Z-forged.json"
    forged_path.write_text(json.dumps(forged), encoding="utf-8")

    result = Ledger(workspace).verify()

    assert not result.ok
    assert any("missing seal signature" in issue for issue in result.issues)


def test_seal_rejects_overlong_label_with_clean_error(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "note.md"
    note.write_text("claim\n", encoding="utf-8")
    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="claim")

    with pytest.raises(ValueError, match="seal label"):
        ledger.seal(label="x" * 65)


def test_export_bundle_skips_symlinked_snapshot_entries(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symbolic links are not supported on this platform")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "note.md"
    note.write_text("claim\n", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("private\n", encoding="utf-8")
    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="claim")
    ledger.seal(label="demo")
    (ledger.snapshots_dir / "leak.txt").symlink_to(secret)
    bundle_path = tmp_path / "bundle.zip"

    export_audit_bundle(ledger, bundle_path)

    with zipfile.ZipFile(bundle_path) as archive:
        assert ".research-ledger/snapshots/leak.txt" not in archive.namelist()


def test_verify_rejects_extra_event_fields(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "note.md"
    note.write_text("claim\n", encoding="utf-8")
    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="claim")
    events_path = workspace / ".research-ledger" / "events.jsonl"
    row = json.loads(events_path.read_text(encoding="utf-8"))
    row["attacker_payload"] = "covert"
    events_path.write_text(json.dumps(row), encoding="utf-8")

    result = Ledger(workspace).verify()

    assert not result.ok
    assert any("malformed event" in issue for issue in result.issues)


def test_verify_reports_structured_issue_codes(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "note.md"
    note.write_text("claim\n", encoding="utf-8")
    ledger = Ledger.init(workspace)
    event = ledger.record(note, event_type="claim")
    (workspace / event.snapshot_path).unlink()

    result = Ledger(workspace).verify()

    assert not result.ok
    assert "snapshot_missing" in result.issue_codes


def test_verify_rejects_unsupported_metadata_schema_version(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    Ledger.init(workspace)
    metadata_path = workspace / ".research-ledger" / "ledger.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["schema_version"] = "99.9"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = Ledger(workspace).verify()

    assert not result.ok
    assert any("unsupported schema version" in issue for issue in result.issues)


def test_record_large_file_does_not_read_target_file_into_memory(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    large_file = workspace / "paper.pdf"
    large_file.write_bytes(b"%PDF\n" + (b"x" * 2_000_000))
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path.resolve() == large_file.resolve():
            raise AssertionError("target file was read into memory")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    ledger = Ledger.init(workspace)

    event = ledger.record(large_file, event_type="source_check")

    assert event.content_hash.startswith("sha256:")
    assert ledger.verify().ok


def test_record_serializes_datetime_and_path_metadata(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "note.md"
    note.write_text("claim\n", encoding="utf-8")
    when = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)

    ledger = Ledger.init(workspace)
    event = ledger.record(
        note,
        event_type="claim",
        metadata={"checked_at": when, "source_path": Path("sources/a.pdf")},
    )

    assert event.metadata["checked_at"] == "2026-06-02T12:00:00Z"
    assert event.metadata["source_path"] == "sources/a.pdf"
    assert Ledger(workspace).verify().ok
