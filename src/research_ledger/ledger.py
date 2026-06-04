"""Core ledger logic for Research Ledger.

This module implements the append-only, tamper-evident research event
ledger.  It provides Pydantic data models for ledger metadata, genesis
events, research events, and Merkle seals, as well as the :class:`Ledger`
class that orchestrates initialization, event recording, verification,
and sealing.

All cryptographic operations delegate to :mod:`research_ledger.crypto`.
"""

from __future__ import annotations

import base64
import os
import json
import shutil
import socket
import time
import unicodedata
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field

from research_ledger.crypto import (
    canonical_json_bytes,
    hash_bytes,
    hash_file,
    merkle_root,
    normalize_json_value,
)


LEDGER_DIR = ".research-ledger"
SCHEMA_VERSION = "0.1"
CANONICALIZATION_VERSION = "research-ledger-c14n-v1"
TOOL_NAME = "research-ledger"
TOOL_VERSION = "0.1.0"
LIFECYCLE_EVENT_TYPES = {"delete", "rename"}
LOCK_TIMEOUT_SECONDS = 10.0
LOCK_POLL_SECONDS = 0.05
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
ISSUE_MALFORMED = "malformed"
ISSUE_SNAPSHOT_MISSING = "snapshot_missing"


class LedgerMetadata(BaseModel):
    """Persistent metadata stored in ``ledger.json``.

    Binds the ledger identity, schema version, and trusted public key.
    Created once during :meth:`Ledger.init` and referenced during every
    subsequent operation.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    canonicalization_version: str = CANONICALIZATION_VERSION
    ledger_id: str
    created_at: str
    author_public_key: str
    key_id: str
    genesis_event_hash: Optional[str] = None


class GenesisEvent(BaseModel):
    """Signed trust root stored in ``genesis.json``.

    The genesis event anchors the hash chain.  The first research event
    links its ``previous_event_hash`` to the genesis ``event_hash``.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    canonicalization_version: str
    ledger_id: str
    event_type: str
    created_at: str
    actor_id: str
    author_public_key: str
    key_id: str
    tool_name: str
    tool_version: str
    signature: str
    event_hash: str


class ScopeDeclaration(BaseModel):
    """Signed first-run declaration of the ledger's research scope.

    The declaration defines the research-note boundary the ledger is
    intended to cover.  It is governance metadata, not a guarantee that
    every eligible file has been recorded.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    canonicalization_version: str
    ledger_id: str
    declaration_type: str
    created_at: str
    title: str
    description: str
    included_paths: list[str]
    excluded_paths: list[str]
    recording_policy: str
    genesis_event_hash: str
    author_public_key: str
    key_id: str
    tool_name: str
    tool_version: str
    signature: str
    event_hash: str


class Event(BaseModel):
    """A single research event in the append-only event log.

    Each event is cryptographically signed, hash-chained to its
    predecessor, and linked to an immutable content snapshot.  Unknown
    fields are rejected (``extra="forbid"``) to prevent injection.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    canonicalization_version: str = CANONICALIZATION_VERSION
    ledger_id: str
    sequence: int
    event_id: str
    event_type: str
    created_at: str
    content_path: str
    content_hash: str
    snapshot_path: str
    previous_event_hash: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    author_public_key: str
    key_id: str
    signature: str
    event_hash: str


class Seal(BaseModel):
    """Merkle-root seal over a prefix of the event hash list.

    Seals are summary artifacts.  Inclusion proofs and external
    timestamp anchoring are planned for future versions.
    """

    model_config = ConfigDict(extra="forbid")

    ledger_id: str
    label: str
    created_at: str
    event_count: int
    merkle_root: str
    tip_event_hash: str
    event_hashes: list[str]


@dataclass(frozen=True)
class VerificationResult:
    """Result of ledger verification.

    Attributes:
        ok: ``True`` when no integrity issues were found.
        event_count: Number of events that were checked.
        issues: Hard failures (tamper detected, signature invalid, etc.).
        warnings: Soft issues (working file drift, timestamp anomalies).
    """

    ok: bool
    event_count: int
    issues: list[str]
    warnings: list[str]
    issue_codes: list[str] = field(default_factory=list)


class Ledger:
    """Local-first, tamper-evident research event ledger.

    A ``Ledger`` instance is bound to a workspace directory and manages
    the ``.research-ledger/`` sub-directory containing the event log,
    metadata, genesis record, snapshots, and seals.

    Typical usage::

        ledger = Ledger.init(Path.cwd())
        ledger.record("notes/claim.md", event_type="claim")
        ledger.seal()
        result = ledger.verify()
    """

    def __init__(self, root: Union[Path, str] = ".") -> None:
        self.root = Path(root).resolve()
        self.ledger_dir = self.root / LEDGER_DIR
        self.events_path = self.ledger_dir / "events.jsonl"
        self.metadata_path = self.ledger_dir / "ledger.json"
        self.genesis_path = self.ledger_dir / "genesis.json"
        self.scope_path = self.ledger_dir / "scope.json"
        self.private_key_path = self.ledger_dir / "private_key.pem"
        self.lock_path = self.ledger_dir / "write.lock"
        self.seals_dir = self.ledger_dir / "seals"
        self.snapshots_dir = self.ledger_dir / "snapshots"

    @classmethod
    def init(
        cls,
        root: Union[Path, str] = ".",
        *,
        scope_title: Optional[str] = None,
        scope_description: Optional[str] = None,
        include_paths: Optional[list[Union[Path, str]]] = None,
        exclude_paths: Optional[list[Union[Path, str]]] = None,
    ) -> "Ledger":
        """Initialize a new research ledger at *root*.

        Creates the ``.research-ledger/`` directory structure, generates
        an Ed25519 key pair (if absent), writes ``ledger.json`` and a
        signed ``genesis.json``, writes a signed ``scope.json`` research
        boundary declaration, and sets up an internal ``.gitignore``.

        Safety guards:

        - If ``ledger.json`` exists but ``private_key.pem`` is missing,
          raises :class:`FileNotFoundError` rather than silently
          generating a replacement key.
        - If events already exist but ``genesis.json`` is missing,
          raises :class:`FileNotFoundError` to prevent orphaned chains.

        Args:
            root: Workspace directory (defaults to current directory).
            scope_title: Human-readable title for the research scope.
            scope_description: Plain-language boundary statement.
            include_paths: Workspace-relative paths covered by the
                scope declaration.  Defaults to the workspace root.
            exclude_paths: Workspace-relative paths excluded from the
                scope declaration.

        Returns:
            The initialized :class:`Ledger` instance.

        Raises:
            FileNotFoundError: When key or genesis recovery is required.
        """
        ledger = cls(root)
        _ensure_private_directory(ledger.ledger_dir)
        _ensure_private_directory(ledger.seals_dir)
        _ensure_private_directory(ledger.snapshots_dir)
        ledger._write_internal_gitignore()
        if ledger.metadata_path.exists() and not ledger.private_key_path.exists():
            raise FileNotFoundError(f"private key missing: {ledger.private_key_path}")
        if ledger.events_path.exists() and ledger.events_path.stat().st_size > 0 and not ledger.genesis_path.exists():
            raise FileNotFoundError(f"genesis missing: {ledger.genesis_path}")
        if not ledger.private_key_path.exists():
            private_key = Ed25519PrivateKey.generate()
            _write_private_bytes(
                ledger.private_key_path,
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                ),
                exclusive=True,
            )
        if not ledger.metadata_path.exists():
            private_key = ledger._load_private_key()
            public_key = _public_key_b64(private_key.public_key())
            metadata = LedgerMetadata(
                ledger_id=str(uuid.uuid4()),
                created_at=_now_utc(),
                author_public_key=public_key,
                key_id=_key_id(public_key),
            )
            _write_private_text(
                ledger.metadata_path,
                json.dumps(metadata.model_dump(), ensure_ascii=False, indent=2) + "\n",
            )
        if not ledger.genesis_path.exists():
            ledger._write_genesis()
        if not ledger.scope_path.exists():
            ledger._write_scope_declaration(
                title=scope_title,
                description=scope_description,
                include_paths=include_paths,
                exclude_paths=exclude_paths,
            )
        _touch_private_file(ledger.events_path)
        return ledger

    def record(
        self,
        content_path: Union[Path, str],
        event_type: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Event:
        """Record a research event for a local file.

        Copies the file into ``.research-ledger/snapshots/`` as an
        immutable snapshot, computes its content hash via streaming I/O,
        signs the event payload with Ed25519, and appends the event to
        ``events.jsonl``.

        Only regular files inside the workspace are accepted.

        Args:
            content_path: Path to the working file (absolute or relative
                to the workspace root).
            event_type: Semantic event category (e.g. ``"claim"``,
                ``"ai_output"``, ``"source_check"``).
            metadata: Optional dict of extra metadata (must be
                JSON-serializable with string keys).

        Returns:
            The created :class:`Event`.

        Raises:
            FileNotFoundError: If the file or ledger does not exist.
            ValueError: If the path is a directory or outside the
                workspace.
        """
        self._require_initialized()
        path = Path(content_path)
        if not path.is_absolute():
            path = self.root / path
        if path.is_symlink():
            raise ValueError("symbolic links are not supported")
        path = path.resolve(strict=True)
        if not path.exists():
            raise FileNotFoundError(path)
        if path.is_dir():
            raise ValueError("directories are not supported")
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"path outside ledger workspace: {path}") from exc
        try:
            path.relative_to(self.ledger_dir)
        except ValueError:
            pass
        else:
            raise ValueError("internal ledger files are not supported")
        if not path.is_file():
            raise ValueError("only regular files are supported")

        with self._write_lock():
            return self._append_event(
                content_path=_display_path(self.root, path),
                event_type=event_type,
                metadata=_normalize_metadata(metadata or {}),
                snapshot_path=self._write_snapshot_for_file(path),
            )

    def record_delete(
        self,
        content_path: Union[Path, str],
        metadata: Optional[dict[str, Any]] = None,
    ) -> Event:
        """Record that a working note was intentionally deleted.

        Creates a lifecycle event with a synthetic snapshot.  Suppresses
        future working-file drift warnings for the old path.

        Args:
            content_path: Path that was deleted.
            metadata: Optional dict (e.g. ``{"reason": "merged"}``)

        Returns:
            The created lifecycle :class:`Event`.
        """
        self._require_initialized()
        path = self._workspace_relative_path(content_path)
        lifecycle_metadata = _normalize_metadata({"action": "delete", **(metadata or {})})
        with self._write_lock():
            return self._append_lifecycle_event(
                content_path=path.as_posix(),
                event_type="delete",
                metadata=lifecycle_metadata,
            )

    def record_rename(
        self,
        old_path: Union[Path, str],
        new_path: Union[Path, str],
        metadata: Optional[dict[str, Any]] = None,
    ) -> Event:
        """Record that a working note was intentionally renamed.

        The ``content_path`` of the resulting event is the *old* path;
        ``metadata["new_path"]`` records the destination.  Users should
        subsequently ``record`` the new path if they want a fresh
        content snapshot.

        Args:
            old_path: Original path.
            new_path: Destination path.
            metadata: Optional dict (e.g. ``{"reason": "Obsidian rename"}``)

        Returns:
            The created lifecycle :class:`Event`.
        """
        self._require_initialized()
        old_relative = self._workspace_relative_path(old_path)
        new_relative = self._workspace_relative_path(new_path)
        lifecycle_metadata = {
            "action": "rename",
            "new_path": new_relative.as_posix(),
            **(metadata or {}),
        }
        lifecycle_metadata = _normalize_metadata(lifecycle_metadata)
        with self._write_lock():
            return self._append_lifecycle_event(
                content_path=old_relative.as_posix(),
                event_type="rename",
                metadata=lifecycle_metadata,
            )

    def _append_lifecycle_event(
        self,
        content_path: str,
        event_type: str,
        metadata: dict[str, Any],
    ) -> Event:
        snapshot_path = self._write_snapshot_for_lifecycle(
            {
                "content_path": content_path,
                "event_type": event_type,
                "metadata": metadata,
            }
        )
        return self._append_event(
            content_path=content_path,
            event_type=event_type,
            metadata=metadata,
            snapshot_path=snapshot_path,
        )

    def _append_event(
        self,
        content_path: str,
        event_type: str,
        metadata: dict[str, Any],
        snapshot_path: str,
    ) -> Event:
        events = self.events()
        sequence = len(events) + 1
        event_id = f"evt-{sequence:06d}-{uuid.uuid4().hex[:12]}"
        previous_event_hash = events[-1].event_hash if events else self.genesis().event_hash
        private_key = self._load_private_key()
        ledger_metadata = self.metadata()
        snapshot_path = self._finalize_snapshot_path(snapshot_path, sequence, event_id)
        content_hash = hash_file(self.root / snapshot_path)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "ledger_id": ledger_metadata.ledger_id,
            "sequence": sequence,
            "event_id": event_id,
            "event_type": event_type,
            "created_at": _now_utc(),
            "content_path": content_path,
            "content_hash": content_hash,
            "snapshot_path": snapshot_path,
            "previous_event_hash": previous_event_hash,
            "metadata": metadata,
            "author_public_key": ledger_metadata.author_public_key,
            "key_id": ledger_metadata.key_id,
        }
        signature = _sign_b64(private_key, canonical_json_bytes(payload))
        event_hash = hash_bytes(canonical_json_bytes({**payload, "signature": signature}))
        event = Event(**payload, signature=signature, event_hash=event_hash)
        with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event.model_dump(), ensure_ascii=False, sort_keys=True) + "\n")
        return event

    def events(self) -> list[Event]:
        """Parse and return all research events from ``events.jsonl``.

        Returns:
            Ordered list of :class:`Event` instances.
        """
        self._require_initialized()
        rows = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(Event(**json.loads(line)))
        return rows

    def metadata(self) -> LedgerMetadata:
        """Load and return the ledger metadata from ``ledger.json``.

        Returns:
            :class:`LedgerMetadata` instance.
        """
        self._require_initialized()
        data = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        if "key_id" not in data and "author_public_key" in data:
            data["key_id"] = _key_id(data["author_public_key"])
        return LedgerMetadata(**data)

    def genesis(self) -> GenesisEvent:
        """Load and return the signed genesis event.

        Returns:
            :class:`GenesisEvent` instance.
        """
        self._require_initialized()
        return GenesisEvent(**json.loads(self.genesis_path.read_text(encoding="utf-8")))

    def scope(self) -> ScopeDeclaration:
        """Load and return the signed first-run scope declaration."""
        self._require_initialized()
        return ScopeDeclaration(**json.loads(self.scope_path.read_text(encoding="utf-8")))

    def verify(self, check_working_files: bool = True) -> VerificationResult:
        """Verify the integrity of the entire ledger.

        Checks performed (in order):

        1. Schema and canonicalization version compatibility.
        2. Genesis trust root (signature, hash, key binding).
        3. For each event: sequence continuity, hash chain,
           Ed25519 signature, schema/ledger-id consistency,
           key trust, content-hash vs snapshot, and working-file
           drift detection.
        4. Seal integrity (event hash list, Merkle root, tip hash).

        Working-file changes produce *warnings*; snapshot or chain
        tampering produces *issues* (hard failures).

        Returns:
            :class:`VerificationResult` with ``ok``, ``issues``,
            and ``warnings``.
        """
        self._require_initialized()
        issues: list[str] = []
        issue_codes: list[str] = []
        warnings: list[str] = []
        def add_issue(message: str, code: Optional[str] = None) -> None:
            issues.append(message)
            if code:
                issue_codes.append(code)

        metadata = self.metadata()
        if metadata.schema_version != SCHEMA_VERSION:
            add_issue(f"unsupported schema version: {metadata.schema_version}", ISSUE_MALFORMED)
        if metadata.canonicalization_version != CANONICALIZATION_VERSION:
            add_issue(
                f"unsupported canonicalization version: {metadata.canonicalization_version}",
                ISSUE_MALFORMED,
            )
        previous_event_hash: Optional[str] = None
        previous_created_at: Optional[datetime] = None
        event_count = 0
        valid_event_hashes: list[str] = []
        raw_lines = [line for line in self.events_path.read_text(encoding="utf-8").splitlines() if line]
        latest_sequence_by_content_path = _latest_sequence_by_content_path(raw_lines)

        try:
            genesis = self.genesis()
            self._verify_genesis(genesis, metadata)
            previous_event_hash = genesis.event_hash
        except Exception as exc:  # noqa: BLE001 - verifier reports malformed trust root.
            add_issue(f"genesis: invalid trust root: {exc}", ISSUE_MALFORMED)

        try:
            scope = self.scope()
            self._verify_scope(scope, metadata)
        except Exception as exc:  # noqa: BLE001 - verifier reports malformed scope declaration.
            add_issue(f"scope: invalid declaration: {exc}", ISSUE_MALFORMED)

        for expected_sequence, line in enumerate(raw_lines, start=1):
            try:
                raw = json.loads(line)
                event = Event(**raw)
            except Exception as exc:  # noqa: BLE001 - verifier reports malformed records.
                add_issue(f"event {expected_sequence}: malformed event: {exc}", ISSUE_MALFORMED)
                continue

            event_count += 1
            if event.sequence != expected_sequence:
                add_issue(f"event {event.sequence}: sequence mismatch")
            if event.previous_event_hash != previous_event_hash:
                add_issue(f"event {event.sequence}: previous hash mismatch")
            if event.schema_version != metadata.schema_version:
                add_issue(f"event {event.sequence}: schema version mismatch")
            if event.canonicalization_version != metadata.canonicalization_version:
                add_issue(f"event {event.sequence}: canonicalization version mismatch")
            if event.ledger_id != metadata.ledger_id:
                add_issue(f"event {event.sequence}: ledger id mismatch")
            if event.author_public_key != metadata.author_public_key or event.key_id != metadata.key_id:
                add_issue(f"event {event.sequence}: untrusted signing key")
            try:
                created_at = _parse_utc(event.created_at)
            except ValueError as exc:
                warnings.append(f"event {event.sequence}: timestamp parse failed: {exc}")
                created_at = None
            if previous_created_at and created_at and created_at < previous_created_at:
                warnings.append(f"event {event.sequence}: timestamp moved backwards")

            payload = event.model_dump(exclude={"signature", "event_hash"})
            try:
                _verify_signature(event.author_public_key, event.signature, canonical_json_bytes(payload))
            except InvalidSignature:
                add_issue(f"event {event.sequence}: signature invalid")
            except Exception as exc:  # noqa: BLE001 - verifier reports exact key/signature issue.
                add_issue(f"event {event.sequence}: signature check failed: {exc}")

            expected_event_hash = hash_bytes(
                canonical_json_bytes(event.model_dump(exclude={"event_hash"}))
            )
            if event.event_hash != expected_event_hash:
                add_issue(f"event {event.sequence}: event hash mismatch")
            else:
                valid_event_hashes.append(event.event_hash)

            snapshot = self.root / event.snapshot_path
            if not snapshot.exists():
                add_issue(
                    f"event {event.sequence}: snapshot missing: {event.snapshot_path}",
                    ISSUE_SNAPSHOT_MISSING,
                )
            elif hash_file(snapshot) != event.content_hash:
                add_issue(f"event {event.sequence}: snapshot hash mismatch: {event.snapshot_path}")

            if (
                check_working_files
                and
                event.sequence == latest_sequence_by_content_path.get(event.content_path)
                and event.event_type not in LIFECYCLE_EVENT_TYPES
            ):
                path = _resolve_existing_working_path(self.root, event.content_path)
                if not path.exists():
                    warnings.append(
                        f"event {event.sequence}: working file missing since snapshot: {event.content_path}"
                    )
                elif hash_file(path) != event.content_hash:
                    warnings.append(
                        f"event {event.sequence}: working file changed since snapshot: {event.content_path}"
                    )

            previous_event_hash = event.event_hash
            if created_at:
                previous_created_at = created_at

        for issue, code in self._verify_seals(valid_event_hashes):
            add_issue(issue, code)

        return VerificationResult(
            ok=not issues,
            event_count=event_count,
            issues=issues,
            warnings=warnings,
            issue_codes=issue_codes,
        )

    def seal(self, label: str = "seal") -> Seal:
        """Create a Merkle-root seal over all current events.

        The seal is written as a timestamped JSON file under
        ``.research-ledger/seals/``.

        Args:
            label: Human-readable label for the seal file name.

        Returns:
            The created :class:`Seal`.

        Raises:
            ValueError: If the ledger contains no events.
        """
        self._require_initialized()
        with self._write_lock():
            events = self.events()
            if not events:
                raise ValueError("cannot seal an empty ledger")
            metadata = self.metadata()
            event_hashes = [event.event_hash for event in events]
            seal = Seal(
                ledger_id=metadata.ledger_id,
                label=label,
                created_at=_now_utc(),
                event_count=len(events),
                merkle_root=merkle_root(event_hashes),
                tip_event_hash=event_hashes[-1],
                event_hashes=event_hashes,
            )
            safe_label = "".join(char if char.isalnum() or char in "-_" else "-" for char in label)
            seal_path = self.seals_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{safe_label}.json"
            temporary = self.seals_dir / f".pending-{uuid.uuid4().hex}.json"
            _write_private_text(
                temporary,
                json.dumps(seal.model_dump(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                exclusive=True,
            )
            temporary.replace(seal_path)
            return seal

    @contextmanager
    def _write_lock(self):
        with _ledger_write_lock(self.lock_path):
            yield

    def _require_initialized(self) -> None:
        if not self.ledger_dir.exists() or not self.metadata_path.exists():
            raise FileNotFoundError(f"ledger not initialized at {self.ledger_dir}")

    def _load_private_key(self) -> Ed25519PrivateKey:
        data = self.private_key_path.read_bytes()
        key = serialization.load_pem_private_key(data, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise TypeError("private key is not Ed25519")
        return key

    def _write_snapshot_for_file(self, path: Path) -> str:
        _ensure_private_directory(self.snapshots_dir)
        temporary = self.snapshots_dir / f".pending-{uuid.uuid4().hex}{path.suffix or '.snapshot'}"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, PRIVATE_FILE_MODE)
        with path.open("rb") as source, os.fdopen(fd, "wb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
        return _display_path(self.root, temporary)

    def _write_snapshot_for_lifecycle(self, payload: dict[str, Any]) -> str:
        _ensure_private_directory(self.snapshots_dir)
        snapshot = self.snapshots_dir / f".pending-{uuid.uuid4().hex}.json"
        _write_private_bytes(snapshot, canonical_json_bytes(payload), exclusive=True)
        return _display_path(self.root, snapshot)

    def _finalize_snapshot_path(self, pending_snapshot_path: str, sequence: int, event_id: str) -> str:
        pending = self.root / pending_snapshot_path
        suffix = pending.suffix if pending.suffix else ".snapshot"
        snapshot = self.snapshots_dir / f"{sequence:06d}-{event_id}{suffix}"
        pending.replace(snapshot)
        return _display_path(self.root, snapshot)

    def _workspace_relative_path(self, path_value: Union[Path, str]) -> Path:
        path = Path(path_value)
        if not path.is_absolute():
            path = self.root / path
        resolved = path.resolve()
        try:
            return resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"path outside ledger workspace: {resolved}") from exc

    def _verify_seals(self, event_hashes_by_sequence: list[str]) -> list[tuple[str, Optional[str]]]:
        issues: list[tuple[str, Optional[str]]] = []
        for seal_path in sorted(self.seals_dir.glob("*.json")):
            try:
                seal = Seal(**json.loads(seal_path.read_text(encoding="utf-8")))
            except Exception as exc:  # noqa: BLE001 - verifier reports malformed seals.
                issues.append((f"seal {seal_path.name}: malformed seal: {exc}", ISSUE_MALFORMED))
                continue
            if seal.ledger_id != self.metadata().ledger_id:
                issues.append((f"seal {seal_path.name}: ledger id mismatch", None))
            if seal.event_count != len(seal.event_hashes):
                issues.append((f"seal {seal_path.name}: event count mismatch", None))
            if seal.event_hashes != event_hashes_by_sequence[: seal.event_count]:
                issues.append((f"seal {seal_path.name}: event hashes mismatch", None))
            if seal.event_hashes:
                try:
                    expected_merkle_root = merkle_root(seal.event_hashes)
                except ValueError as exc:
                    issues.append((f"seal {seal_path.name}: invalid event hashes: {exc}", ISSUE_MALFORMED))
                else:
                    if seal.merkle_root != expected_merkle_root:
                        issues.append((f"seal {seal_path.name}: seal merkle root mismatch", None))
                if seal.tip_event_hash != seal.event_hashes[-1]:
                    issues.append((f"seal {seal_path.name}: tip event hash mismatch", None))
        return issues

    def _write_internal_gitignore(self) -> None:
        gitignore = self.ledger_dir / ".gitignore"
        if not gitignore.exists():
            _write_private_text(
                gitignore,
                "private_key.pem\n",
                exclusive=True,
            )

    def _write_genesis(self) -> None:
        private_key = self._load_private_key()
        metadata = self.metadata()
        payload = {
            "schema_version": metadata.schema_version,
            "canonicalization_version": metadata.canonicalization_version,
            "ledger_id": metadata.ledger_id,
            "event_type": "genesis",
            "created_at": metadata.created_at,
            "actor_id": "local-user",
            "author_public_key": metadata.author_public_key,
            "key_id": metadata.key_id,
            "tool_name": TOOL_NAME,
            "tool_version": TOOL_VERSION,
        }
        signature = _sign_b64(private_key, canonical_json_bytes(payload))
        event_hash = hash_bytes(canonical_json_bytes({**payload, "signature": signature}))
        genesis = GenesisEvent(**payload, signature=signature, event_hash=event_hash)
        _write_private_text(
            self.genesis_path,
            json.dumps(genesis.model_dump(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        metadata.genesis_event_hash = event_hash
        _write_private_text(
            self.metadata_path,
            json.dumps(metadata.model_dump(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

    def _write_scope_declaration(
        self,
        *,
        title: Optional[str],
        description: Optional[str],
        include_paths: Optional[list[Union[Path, str]]],
        exclude_paths: Optional[list[Union[Path, str]]],
    ) -> None:
        private_key = self._load_private_key()
        metadata = self.metadata()
        included = _normalize_scope_paths(self.root, include_paths or ["."])
        excluded = _normalize_scope_paths(self.root, exclude_paths or [])
        payload = {
            "schema_version": metadata.schema_version,
            "canonicalization_version": metadata.canonicalization_version,
            "ledger_id": metadata.ledger_id,
            "declaration_type": "scope",
            "created_at": _now_utc(),
            "title": title or self.root.name or "research-workspace",
            "description": description
            or "All research notes under the declared workspace unless explicitly excluded.",
            "included_paths": included,
            "excluded_paths": excluded,
            "recording_policy": (
                "Only explicit record/delete/rename events are included in the audit trail; "
                "this scope declaration defines eligible research-note boundaries, not a "
                "guarantee of exhaustive capture."
            ),
            "genesis_event_hash": metadata.genesis_event_hash or self.genesis().event_hash,
            "author_public_key": metadata.author_public_key,
            "key_id": metadata.key_id,
            "tool_name": TOOL_NAME,
            "tool_version": TOOL_VERSION,
        }
        signature = _sign_b64(private_key, canonical_json_bytes(payload))
        event_hash = hash_bytes(canonical_json_bytes({**payload, "signature": signature}))
        scope = ScopeDeclaration(**payload, signature=signature, event_hash=event_hash)
        _write_private_text(
            self.scope_path,
            json.dumps(scope.model_dump(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

    def _verify_genesis(self, genesis: GenesisEvent, metadata: LedgerMetadata) -> None:
        if genesis.event_type != "genesis":
            raise ValueError("event_type is not genesis")
        if genesis.ledger_id != metadata.ledger_id:
            raise ValueError("ledger_id mismatch")
        if genesis.author_public_key != metadata.author_public_key:
            raise ValueError("public key mismatch")
        if genesis.key_id != metadata.key_id:
            raise ValueError("key id mismatch")
        if metadata.genesis_event_hash and genesis.event_hash != metadata.genesis_event_hash:
            raise ValueError("genesis hash mismatch")
        payload = genesis.model_dump(exclude={"signature", "event_hash"})
        _verify_signature(metadata.author_public_key, genesis.signature, canonical_json_bytes(payload))
        expected_event_hash = hash_bytes(
            canonical_json_bytes(genesis.model_dump(exclude={"event_hash"}))
        )
        if genesis.event_hash != expected_event_hash:
            raise ValueError("event hash mismatch")

    def _verify_scope(self, scope: ScopeDeclaration, metadata: LedgerMetadata) -> None:
        if scope.declaration_type != "scope":
            raise ValueError("declaration_type is not scope")
        if scope.ledger_id != metadata.ledger_id:
            raise ValueError("ledger_id mismatch")
        if scope.schema_version != metadata.schema_version:
            raise ValueError("schema version mismatch")
        if scope.canonicalization_version != metadata.canonicalization_version:
            raise ValueError("canonicalization version mismatch")
        if scope.author_public_key != metadata.author_public_key:
            raise ValueError("public key mismatch")
        if scope.key_id != metadata.key_id:
            raise ValueError("key id mismatch")
        if metadata.genesis_event_hash and scope.genesis_event_hash != metadata.genesis_event_hash:
            raise ValueError("genesis hash mismatch")
        if not scope.included_paths:
            raise ValueError("included_paths is empty")
        payload = scope.model_dump(exclude={"signature", "event_hash"})
        _verify_signature(metadata.author_public_key, scope.signature, canonical_json_bytes(payload))
        expected_event_hash = hash_bytes(
            canonical_json_bytes(scope.model_dump(exclude={"event_hash"}))
        )
        if scope.event_hash != expected_event_hash:
            raise ValueError("event hash mismatch")


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=PRIVATE_DIR_MODE)
    if os.name != "nt":
        path.chmod(PRIVATE_DIR_MODE)


def _touch_private_file(path: Path) -> None:
    if path.exists():
        _chmod_private_file(path)
        return
    _write_private_bytes(path, b"", exclusive=True)


def _write_private_text(path: Path, content: str, *, exclusive: bool = False) -> None:
    _write_private_bytes(path, content.encode("utf-8"), exclusive=exclusive)


def _write_private_bytes(path: Path, content: bytes, *, exclusive: bool = False) -> None:
    flags = os.O_WRONLY | os.O_CREAT
    if exclusive:
        flags |= os.O_EXCL
    else:
        flags |= os.O_TRUNC
    fd = os.open(path, flags, PRIVATE_FILE_MODE)
    try:
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(content)
    finally:
        if fd != -1:
            os.close(fd)
    _chmod_private_file(path)


def _chmod_private_file(path: Path) -> None:
    if os.name != "nt":
        path.chmod(PRIVATE_FILE_MODE)


def _parse_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@contextmanager
def _ledger_write_lock(lock_path: Path):
    start = time.monotonic()
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            if _recover_stale_write_lock(lock_path):
                continue
            if time.monotonic() - start >= LOCK_TIMEOUT_SECONDS:
                raise TimeoutError(f"ledger write lock is held: {lock_path}") from exc
            time.sleep(LOCK_POLL_SECONDS)
        else:
            try:
                os.write(fd, _write_lock_payload())
                yield
            finally:
                os.close(fd)
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
            return


def _write_lock_payload() -> bytes:
    payload = {
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "token": uuid.uuid4().hex,
    }
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def _recover_stale_write_lock(lock_path: Path) -> bool:
    try:
        original = lock_path.read_bytes()
    except FileNotFoundError:
        return True
    try:
        payload = json.loads(original.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    pid = payload.get("pid")
    hostname = payload.get("hostname")
    if not isinstance(pid, int) or pid <= 0:
        return False
    if hostname != socket.gethostname():
        return False
    if _process_exists(pid):
        return False
    try:
        if lock_path.read_bytes() != original:
            return False
        lock_path.unlink()
    except FileNotFoundError:
        return True
    return True


def _process_exists(pid: int) -> bool:
    if os.name == "nt":
        return _windows_process_exists(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _windows_process_exists(pid: int) -> bool:
    try:
        import ctypes
    except Exception:  # noqa: BLE001 - if process probing is unavailable, keep the lock.
        return True

    process_query_limited_information = 0x1000
    error_invalid_parameter = 87
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if handle:
        kernel32.CloseHandle(handle)
        return True
    return ctypes.get_last_error() != error_invalid_parameter


def _latest_sequence_by_content_path(raw_lines: list[str]) -> dict[str, int]:
    latest: dict[str, int] = {}
    for line in raw_lines:
        try:
            event = Event(**json.loads(line))
        except Exception:  # noqa: BLE001 - malformed rows are reported in the verifier loop.
            continue
        latest[event.content_path] = max(latest.get(event.content_path, 0), event.sequence)
    return latest


def _normalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_json_value(metadata)
    if not isinstance(normalized, dict):
        raise TypeError("metadata must normalize to a JSON object")
    return normalized


def _normalize_scope_paths(root: Path, paths: list[Union[Path, str]]) -> list[str]:
    normalized: list[str] = []
    for path_value in paths:
        path = Path(path_value)
        candidate = path if path.is_absolute() else root / path
        resolved = candidate.resolve()
        try:
            relative = resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"scope path outside ledger workspace: {resolved}") from exc
        if relative == Path("."):
            value = "."
        else:
            value = relative.as_posix()
        if value == LEDGER_DIR or value.startswith(f"{LEDGER_DIR}/"):
            raise ValueError("scope cannot include internal ledger files")
        if value not in normalized:
            normalized.append(value)
    return normalized


def _resolve_existing_working_path(root: Path, relative_path: str) -> Path:
    exact_path = root / relative_path
    if exact_path.exists():
        return exact_path

    current = root
    for part in Path(relative_path).parts:
        candidate = current / part
        if candidate.exists():
            current = candidate
            continue
        normalized_part = unicodedata.normalize("NFC", part)
        try:
            match = next(
                child
                for child in current.iterdir()
                if unicodedata.normalize("NFC", child.name) == normalized_part
            )
        except (FileNotFoundError, NotADirectoryError, StopIteration):
            return exact_path
        current = match
    return current


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _public_key_b64(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode("ascii")


def _key_id(public_key_b64: str) -> str:
    digest = hash_bytes(base64.b64decode(public_key_b64)).removeprefix("sha256:")
    return f"ed25519-sha256:{digest}"


def _sign_b64(private_key: Ed25519PrivateKey, payload: bytes) -> str:
    return base64.b64encode(private_key.sign(payload)).decode("ascii")


def _verify_signature(public_key_b64: str, signature_b64: str, payload: bytes) -> None:
    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
    public_key.verify(base64.b64decode(signature_b64), payload)
