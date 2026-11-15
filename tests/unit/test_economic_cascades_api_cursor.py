# mypy: ignore-errors
"""Cursor codec alias and fingerprint binding for cascade reads."""

from __future__ import annotations

import pytest

from api.economic_cascades_cursor import (
    ECONOMIC_CASCADES_CURSOR_TTL_SECONDS,
    EconomicCascadesCursorCodec,
    EconomicCascadesCursorError,
)
from simulation.economic_cascades_ports import (
    economic_cascades_query_fingerprint,
)

pytestmark = pytest.mark.unit


def test_ttl_and_round_trip() -> None:
    assert ECONOMIC_CASCADES_CURSOR_TTL_SECONDS == 900
    codec = EconomicCascadesCursorCodec(b"k" * 32)
    token = codec.encode(
        purpose="chains",
        run_id="run-1",
        publication_id="ecasc-1",
        snapshot_digest="sha256:abc",
        query_fingerprint="fingerprint",
        after_key="0001|casc-1",
    )
    payload = codec.decode(token, purpose="chains")
    assert payload["after_key"] == "0001|casc-1"
    with pytest.raises(EconomicCascadesCursorError):
        codec.decode(token, purpose="disruptions")


def test_fingerprint_mismatch_is_visible() -> None:
    codec = EconomicCascadesCursorCodec(b"k" * 32)
    token = codec.encode(
        purpose="chains",
        run_id="run-1",
        publication_id="ecasc-1",
        snapshot_digest="sha256:abc",
        query_fingerprint="fingerprint",
        after_key="0001|casc-1",
    )
    payload = codec.decode(token, purpose="chains")
    assert payload["query_fingerprint"] == "fingerprint"
    assert economic_cascades_query_fingerprint(
        run_id="run-1",
        publication_id="ecasc-1",
        digest="sha256:abc",
        purpose="chains",
        window_index=None,
        limit=100,
    ) != economic_cascades_query_fingerprint(
        run_id="run-1",
        publication_id="ecasc-1",
        digest="sha256:abc",
        purpose="chains",
        window_index=1,
        limit=100,
    )
