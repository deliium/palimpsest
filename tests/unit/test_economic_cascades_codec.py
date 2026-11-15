# mypy: ignore-errors
"""Canonical round-trip and strict decode for cascade snapshots."""

from __future__ import annotations

import json

import pytest

from simulation.economic_cascades_codec import (
    canonical_economic_cascades_json,
    decode_economic_cascades_snapshot,
    economic_cascades_digest,
    encode_economic_cascades_snapshot,
    finalize_economic_cascades_snapshot,
)
from simulation.economic_cascades_models import (
    MAX_ECONOMIC_CASCADES_SNAPSHOT_BYTES,
    empty_economic_cascades_snapshot,
)

pytestmark = pytest.mark.unit


def test_round_trip_is_byte_identical_after_one_finalize() -> None:
    snapshot = finalize_economic_cascades_snapshot(
        empty_economic_cascades_snapshot("run-1")
    )
    first = encode_economic_cascades_snapshot(snapshot)
    decoded = decode_economic_cascades_snapshot(first)
    assert decoded == snapshot
    assert encode_economic_cascades_snapshot(decoded) == first
    assert canonical_economic_cascades_json(snapshot) == first


def test_digest_and_publication_id_are_content_addressed() -> None:
    snapshot = finalize_economic_cascades_snapshot(
        empty_economic_cascades_snapshot("run-1")
    )
    assert snapshot.internal_digest.startswith("sha256:")
    assert snapshot.publication_id.startswith("ecasc-")
    assert snapshot.publication_id == (
        "ecasc-" + snapshot.internal_digest.removeprefix("sha256:")[:16]
    )
    assert snapshot.internal_digest == economic_cascades_digest(
        empty_economic_cascades_snapshot("run-1")
    )


def test_tampered_payload_is_rejected() -> None:
    snapshot = finalize_economic_cascades_snapshot(
        empty_economic_cascades_snapshot("run-1")
    )
    payload = encode_economic_cascades_snapshot(snapshot)
    tampered = payload.replace(b'"window_count":0', b'"window_count":1')
    with pytest.raises(ValueError):
        decode_economic_cascades_snapshot(tampered)


def test_unknown_field_is_rejected() -> None:
    snapshot = finalize_economic_cascades_snapshot(
        empty_economic_cascades_snapshot("run-1")
    )
    parsed = json.loads(encode_economic_cascades_snapshot(snapshot))
    parsed["severity"] = 3
    payload = json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError):
        decode_economic_cascades_snapshot(payload + b"\n")


def test_oversize_payload_is_rejected() -> None:
    with pytest.raises(ValueError):
        decode_economic_cascades_snapshot(
            b" " * (MAX_ECONOMIC_CASCADES_SNAPSHOT_BYTES + 1)
        )


def test_run_mismatch_is_rejected() -> None:
    snapshot = finalize_economic_cascades_snapshot(
        empty_economic_cascades_snapshot("run-1")
    )
    payload = encode_economic_cascades_snapshot(snapshot)
    with pytest.raises(ValueError):
        decode_economic_cascades_snapshot(payload, run_id="run-2")
