"""Canonical credit snapshot codec, digest, and strict decoding."""

# mypy: ignore-errors


from __future__ import annotations

from dataclasses import replace

import pytest

from simulation.credit_relationships_codec import (
    credit_relationships_artifact_digest,
    decode_credit_relationships_snapshot,
    encode_credit_relationships_snapshot,
    finalize_credit_relationships_snapshot,
)
from tests.unit.credit_relationships_snapshot_helpers import snapshot

pytestmark = pytest.mark.unit


def test_finalize_assigns_digest_and_publication_id() -> None:
    value = finalize_credit_relationships_snapshot(snapshot())
    assert value.digest.startswith("sha256:")
    assert len(value.digest) == len("sha256:") + 64
    assert value.publication_id.startswith("cred-pub-")
    assert len(value.publication_id) == len("cred-pub-") + 16


def test_round_trip_is_byte_identical() -> None:
    value = finalize_credit_relationships_snapshot(snapshot())
    encoded = encode_credit_relationships_snapshot(value)
    assert encoded.endswith(b"\n")
    decoded = decode_credit_relationships_snapshot(encoded)
    assert decoded == value
    assert encode_credit_relationships_snapshot(decoded) == encoded


def test_digest_ignores_digest_and_publication_fields() -> None:
    unfinalized = snapshot()
    finalized = finalize_credit_relationships_snapshot(unfinalized)
    assert credit_relationships_artifact_digest(
        unfinalized
    ) == credit_relationships_artifact_digest(finalized)


def test_digest_changes_when_a_row_changes() -> None:
    first = finalize_credit_relationships_snapshot(snapshot())
    changed_row = replace(first.relationships[0], status="defaulted")
    changed = replace(first, relationships=(changed_row,))
    assert credit_relationships_artifact_digest(first) != (
        credit_relationships_artifact_digest(changed)
    )


def test_due_tick_none_round_trips() -> None:
    value = finalize_credit_relationships_snapshot(snapshot())
    row = replace(value.relationships[0], due_tick=None)
    changed = finalize_credit_relationships_snapshot(
        replace(value, relationships=(row,))
    )
    decoded = decode_credit_relationships_snapshot(
        encode_credit_relationships_snapshot(changed)
    )
    assert decoded.relationships[0].due_tick is None


def test_duplicate_key_is_rejected() -> None:
    data = encode_credit_relationships_snapshot(
        finalize_credit_relationships_snapshot(snapshot())
    )
    corrupted = data.replace(
        b'"run_id":"run-credit-1"',
        b'"run_id":"run-credit-1","run_id":"run-credit-1"',
        1,
    )
    with pytest.raises(ValueError):
        decode_credit_relationships_snapshot(corrupted)


def test_unknown_field_is_rejected() -> None:
    data = encode_credit_relationships_snapshot(
        finalize_credit_relationships_snapshot(snapshot())
    )
    corrupted = data.replace(b'"summary":', b'"unknown":1,"summary":', 1)
    with pytest.raises(ValueError):
        decode_credit_relationships_snapshot(corrupted)


def test_schema_mismatch_is_rejected() -> None:
    data = encode_credit_relationships_snapshot(
        finalize_credit_relationships_snapshot(snapshot())
    )
    corrupted = data.replace(
        b'"credit-relationships-snapshot-v1"',
        b'"credit-relationships-snapshot-v2"',
    )
    with pytest.raises(ValueError):
        decode_credit_relationships_snapshot(corrupted)


def test_digest_mismatch_is_rejected() -> None:
    value = finalize_credit_relationships_snapshot(snapshot())
    data = encode_credit_relationships_snapshot(value)
    corrupted = data.replace(value.digest.encode(), b"sha256:" + b"0" * 64)
    with pytest.raises(ValueError):
        decode_credit_relationships_snapshot(corrupted)


def test_oversize_and_noncanonical_are_rejected() -> None:
    with pytest.raises(ValueError):
        decode_credit_relationships_snapshot(b"x" * 8_388_609)
    value = finalize_credit_relationships_snapshot(snapshot())
    data = encode_credit_relationships_snapshot(value)
    with pytest.raises(ValueError):
        decode_credit_relationships_snapshot(data + b" ")


def test_run_id_filter_is_enforced() -> None:
    data = encode_credit_relationships_snapshot(
        finalize_credit_relationships_snapshot(snapshot())
    )
    with pytest.raises(ValueError):
        decode_credit_relationships_snapshot(data, run_id="run-other")
