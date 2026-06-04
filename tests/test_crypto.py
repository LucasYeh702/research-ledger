import math

import pytest

from research_ledger.crypto import canonical_json_bytes, hash_bytes, hash_file, merkle_root


def test_canonical_json_is_stable_across_key_order_and_newlines(tmp_path):
    left = {"b": "line\r\nnext", "a": 1}
    right = {"a": 1, "b": "line\nnext"}

    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert hash_bytes(canonical_json_bytes(left)) == hash_bytes(canonical_json_bytes(right))


def test_canonical_json_rejects_nan_and_non_string_keys():
    with pytest.raises(ValueError):
        canonical_json_bytes({"value": math.nan})
    with pytest.raises(TypeError):
        canonical_json_bytes({1: "not allowed"})


def test_hash_file_uses_raw_bytes(tmp_path):
    note = tmp_path / "note.md"
    raw = "第一行\r\n第二行\r\n".encode("utf-8")
    note.write_bytes(raw)

    assert hash_file(note) == hash_bytes(raw)
    assert hash_file(note) != hash_bytes("第一行\n第二行\n".encode("utf-8"))


def test_merkle_root_distinguishes_odd_leaf_from_duplicated_last_leaf():
    first = hash_bytes(b"first")
    second = hash_bytes(b"second")
    third = hash_bytes(b"third")

    assert merkle_root([first, second, third]) != merkle_root([first, second, third, third])
