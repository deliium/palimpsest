# mypy: ignore-errors
"""Strict codec tests for economic-inequality snapshots."""

from __future__ import annotations

import pytest

from simulation.economic_inequality_codec import (
    decode_economic_inequality_snapshot,
    economic_inequality_digest,
    encode_economic_inequality_snapshot,
    finalize_economic_inequality_snapshot,
)
from tests.unit.test_economic_inequality_snapshot import _snapshot


def test_digest_is_stable_and_finalization_is_idempotent() -> None:
    snapshot = _snapshot()
    first = finalize_economic_inequality_snapshot(snapshot)
    second = finalize_economic_inequality_snapshot(first)
    assert first == second
    assert economic_inequality_digest(first) == first.digest


def test_digest_mismatch_is_rejected() -> None:
    snapshot = finalize_economic_inequality_snapshot(_snapshot())
    payload = encode_economic_inequality_snapshot(snapshot)
    tampered = payload.replace(b'"gini_milli":200', b'"gini_milli":201', 1)
    with pytest.raises(ValueError, match="digest_mismatch"):
        decode_economic_inequality_snapshot(tampered)


def test_duplicate_keys_are_rejected() -> None:
    payload = b'{"run_id":"a","run_id":"b"}'
    with pytest.raises(ValueError, match="corrupt"):
        decode_economic_inequality_snapshot(payload)


def test_wrong_run_id_is_rejected() -> None:
    snapshot = finalize_economic_inequality_snapshot(_snapshot())
    payload = encode_economic_inequality_snapshot(snapshot)
    with pytest.raises(ValueError, match="run_mismatch"):
        decode_economic_inequality_snapshot(payload, run_id="run-2")


def test_non_bytes_payload_is_rejected() -> None:
    with pytest.raises(ValueError, match="oversize"):
        decode_economic_inequality_snapshot("not-bytes")  # type: ignore[arg-type]
