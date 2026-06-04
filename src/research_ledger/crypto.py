"""Cryptographic primitives for Research Ledger.

Provides canonical JSON serialization, SHA-256 hashing, streaming file
hashing, and a domain-separated Merkle tree implementation used for
tamper-evident research event records.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


def normalize_json_value(value: Any) -> Any:
    """Recursively normalize a Python value for canonical JSON serialization.

    Normalization rules (per ``research-ledger-c14n-v1``):
    - **str**: CRLF and CR line endings are converted to LF.
    - **datetime / date**: converted to ISO 8601 string; timezone-aware
      datetimes are normalized to UTC with a ``Z`` suffix.
    - **Path**: converted to POSIX path string.
    - **list / tuple**: each element is recursively normalized; tuples
      become lists.
    - **dict**: keys must all be ``str``; the returned dict is sorted by
      key with each value recursively normalized.
    - **float**: ``NaN``, ``Infinity``, and ``-Infinity`` are rejected.
    - All other types (int, bool, None) are returned as-is.

    Args:
        value: The Python value to normalize.

    Returns:
        The normalized value suitable for ``json.dumps``.

    Raises:
        TypeError: If a dict key is not a string.
        ValueError: If a float is NaN or Infinity.
    """
    if isinstance(value, str):
        return value.replace("\r\n", "\n").replace("\r", "\n")
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, list):
        return [normalize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_json_value(item) for item in value]
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise TypeError("canonical JSON only supports string object keys")
        return {key: normalize_json_value(value[key]) for key in sorted(value)}
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("canonical JSON does not support NaN or Infinity")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a Python value to deterministic canonical JSON bytes.

    The value is first normalized via :func:`normalize_json_value`, then
    serialized with sorted keys, compact separators (``","`` / ``":"``),
    no ASCII escaping, and ``allow_nan=False``.  The result is encoded
    as UTF-8.

    Args:
        value: The Python value to serialize.

    Returns:
        UTF-8 encoded canonical JSON bytes.
    """
    normalized = normalize_json_value(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def hash_bytes(payload: bytes) -> str:
    """Compute a SHA-256 hash of the given bytes.

    Args:
        payload: Raw bytes to hash.

    Returns:
        Hash string in the format ``"sha256:<hex_digest>"``.
    """
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def hash_file(path: Path) -> str:
    """Compute a SHA-256 hash of a file using streaming I/O.

    Reads the file in 1 MB chunks to avoid loading large files entirely
    into memory.

    Args:
        path: Path to the file to hash.

    Returns:
        Hash string in the format ``"sha256:<hex_digest>"``.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def merkle_root(event_hashes: list[str]) -> str:
    """Compute a Merkle root over a list of event hashes.

    Uses domain separation to prevent second-preimage attacks:

    - Leaf nodes are prefixed with ``\\x00`` before hashing.
    - Internal nodes are prefixed with ``\\x01`` before hashing.

    When a layer has an odd number of nodes, the unpaired last node is
    promoted to the next layer without duplication (avoiding the
    Bitcoin CVE-2012-2459 vulnerability).

    Args:
        event_hashes: Non-empty list of hash strings in
            ``"sha256:<hex>"`` format.

    Returns:
        Merkle root in ``"sha256:<hex_digest>"`` format.

    Raises:
        ValueError: If *event_hashes* is empty or contains an
            unsupported hash format.
    """
    if not event_hashes:
        raise ValueError("cannot seal an empty ledger")
    layer = [hashlib.sha256(b"\x00" + _hash_to_bytes(item)).digest() for item in event_hashes]
    while len(layer) > 1:
        next_layer = []
        for index in range(0, len(layer), 2):
            if index + 1 == len(layer):
                next_layer.append(layer[index])
            else:
                digest = hashlib.sha256(b"\x01" + layer[index] + layer[index + 1]).digest()
                next_layer.append(digest)
        layer = next_layer
    return f"sha256:{layer[0].hex()}"


def _hash_to_bytes(value: str) -> bytes:
    """Convert a ``"sha256:<hex>"`` string to raw hash bytes.

    Args:
        value: Hash string with ``sha256:`` prefix.

    Returns:
        Raw 32-byte SHA-256 digest.

    Raises:
        ValueError: If the hash format is not ``sha256:``.
    """
    if not value.startswith("sha256:"):
        raise ValueError(f"unsupported hash format: {value}")
    return bytes.fromhex(value.removeprefix("sha256:"))
