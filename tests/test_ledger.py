import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from research_ledger.crypto import canonical_json_bytes, hash_bytes
from research_ledger.ledger import Ledger


def test_init_creates_signed_genesis_binding_ledger_and_key(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    ledger = Ledger.init(workspace)
    genesis = ledger.genesis()
    metadata = ledger.metadata()

    assert genesis.event_type == "genesis"
    assert genesis.ledger_id == metadata.ledger_id
    assert genesis.author_public_key == metadata.author_public_key
    assert genesis.key_id == metadata.key_id
    assert genesis.event_hash.startswith("sha256:")
    assert ledger.verify().ok


def test_init_creates_signed_scope_declaration(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    notes = workspace / "notes"
    notes.mkdir()

    ledger = Ledger.init(
        workspace,
        scope_title="AI 協作論文",
        scope_description="只涵蓋 notes 研究筆記。",
        include_paths=["notes"],
        exclude_paths=["notes/private"],
    )
    scope = ledger.scope()

    assert scope.declaration_type == "scope"
    assert scope.title == "AI 協作論文"
    assert scope.description == "只涵蓋 notes 研究筆記。"
    assert scope.included_paths == ["notes"]
    assert scope.excluded_paths == ["notes/private"]
    assert scope.ledger_id == ledger.metadata().ledger_id
    assert scope.genesis_event_hash == ledger.genesis().event_hash
    assert scope.event_hash.startswith("sha256:")
    assert ledger.verify().ok


def test_verify_rejects_scope_declaration_tampering(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    ledger = Ledger.init(workspace, scope_title="原始範圍")
    scope_path = workspace / ".research-ledger" / "scope.json"
    row = json.loads(scope_path.read_text(encoding="utf-8"))
    row["title"] = "竄改後範圍"
    scope_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    result = ledger.verify()

    assert not result.ok
    assert any("scope: invalid declaration" in issue for issue in result.issues)


def test_record_creates_signed_hash_chained_event(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "claim.md"
    note.write_text("# 命題\n\nAI 協作研究需要可驗證留痕。\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    event = ledger.record(note, event_type="claim")

    assert event.sequence == 1
    assert event.previous_event_hash == ledger.genesis().event_hash
    assert event.content_hash.startswith("sha256:")
    assert event.event_hash.startswith("sha256:")
    assert event.signature
    assert ledger.verify().ok


def test_verify_detects_content_tampering(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "claim.md"
    note.write_text("原始命題\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="claim")
    note.write_text("被修改的命題\n", encoding="utf-8")

    result = ledger.verify()

    assert result.ok
    assert any("working file changed since snapshot" in issue for issue in result.warnings)


def test_verify_detects_event_log_tampering(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "claim.md"
    note.write_text("原始命題\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="claim")
    events_path = workspace / ".research-ledger" / "events.jsonl"
    row = json.loads(events_path.read_text(encoding="utf-8").strip())
    row["event_type"] = "ai_output"
    events_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    result = Ledger(workspace).verify()

    assert not result.ok
    assert any("signature invalid" in issue or "event hash mismatch" in issue for issue in result.issues)


@pytest.mark.parametrize(
    ("field", "tampered_value"),
    [
        ("sequence", 99),
        ("event_id", "evt-999999-attacker"),
        ("event_type", "ai_output"),
        ("created_at", "2026-06-03T00:00:00Z"),
        ("content_path", "other.md"),
        ("content_hash", "sha256:" + "0" * 64),
        ("snapshot_path", ".research-ledger/snapshots/attacker.md"),
        ("previous_event_hash", "sha256:" + "1" * 64),
        ("metadata", {"topic": "tampered"}),
        ("author_public_key", "attacker"),
        ("key_id", "ed25519-sha256:attacker"),
        ("signature", "attacker"),
        ("event_hash", "sha256:" + "2" * 64),
    ],
)
def test_verify_rejects_core_event_field_tamper_matrix(tmp_path, field, tampered_value):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "claim.md"
    note.write_text("原始命題\n", encoding="utf-8")

    Ledger.init(workspace).record(note, event_type="claim")
    events_path = workspace / ".research-ledger" / "events.jsonl"
    row = json.loads(events_path.read_text(encoding="utf-8").strip())
    row[field] = tampered_value
    events_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    result = Ledger(workspace).verify()

    assert not result.ok
    assert result.issues


def test_verify_fails_when_event_is_resigned_with_untrusted_key(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "claim.md"
    note.write_text("原始命題\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    ledger.record(note, event_type="claim")
    events_path = workspace / ".research-ledger" / "events.jsonl"
    row = json.loads(events_path.read_text(encoding="utf-8").strip())
    attacker_key = Ed25519PrivateKey.generate()
    attacker_public = attacker_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    import base64

    row["author_public_key"] = base64.b64encode(attacker_public).decode("ascii")
    row["key_id"] = "ed25519-sha256:attacker"
    payload = {key: value for key, value in row.items() if key not in {"signature", "event_hash"}}
    row["signature"] = base64.b64encode(attacker_key.sign(canonical_json_bytes(payload))).decode(
        "ascii"
    )
    row["event_hash"] = hash_bytes(
        canonical_json_bytes({key: value for key, value in row.items() if key != "event_hash"})
    )
    events_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    result = Ledger(workspace).verify()

    assert not result.ok
    assert any("untrusted signing key" in issue for issue in result.issues)


def test_verify_detects_missing_middle_event(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    first = workspace / "001.md"
    second = workspace / "002.md"
    first.write_text("命題一\n", encoding="utf-8")
    second.write_text("命題二\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    ledger.record(first, event_type="claim")
    ledger.record(second, event_type="source_check")
    events_path = workspace / ".research-ledger" / "events.jsonl"
    lines = events_path.read_text(encoding="utf-8").splitlines()
    events_path.write_text(lines[1] + "\n", encoding="utf-8")

    result = Ledger(workspace).verify()

    assert not result.ok
    assert any("sequence mismatch" in issue or "previous hash mismatch" in issue for issue in result.issues)


def test_seal_generates_deterministic_merkle_root(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    first = workspace / "001.md"
    second = workspace / "002.md"
    first.write_text("命題一\n", encoding="utf-8")
    second.write_text("命題二\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    ledger.record(first, event_type="claim")
    ledger.record(second, event_type="source_check")

    seal = ledger.seal(label="demo")

    assert seal.event_count == 2
    assert seal.merkle_root.startswith("sha256:")
    assert ledger.verify().ok


def test_verify_fails_if_snapshot_is_tampered(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    note = workspace / "claim.md"
    note.write_text("原始命題\n", encoding="utf-8")

    ledger = Ledger.init(workspace)
    event = ledger.record(note, event_type="claim")
    snapshot_path = workspace / event.snapshot_path
    snapshot_path.write_text("竄改 snapshot\n", encoding="utf-8")

    result = ledger.verify()

    assert not result.ok
    assert any("snapshot hash mismatch" in issue for issue in result.issues)
