# mypy: ignore-errors
"""Cursor codec alias and fingerprint contract for hypothesis reads."""

from __future__ import annotations

import pytest

from api.scientific_hypotheses_cursor import (
    SCIENTIFIC_HYPOTHESES_CURSOR_TTL_SECONDS,
    ScientificHypothesesCursorCodec,
    ScientificHypothesesCursorError,
)
from simulation.scientific_hypotheses_ports import (
    scientific_hypotheses_query_fingerprint,
)

pytestmark = pytest.mark.unit


def test_ttl_and_round_trip() -> None:
    assert SCIENTIFIC_HYPOTHESES_CURSOR_TTL_SECONDS == 900
    codec = ScientificHypothesesCursorCodec(b"k" * 32)
    token = codec.encode(
        purpose="hypotheses",
        run_id="run-1",
        publication_id="schyp-1",
        snapshot_digest="sha256:abc",
        query_fingerprint="f" * 64,
        after_key="0000|schyp-1",
    )
    payload = codec.decode(token, purpose="hypotheses")
    assert payload["after_key"] == "0000|schyp-1"
    assert payload["run_id"] == "run-1"
    with pytest.raises(ScientificHypothesesCursorError):
        codec.decode(token, purpose="evidence")


def test_fingerprint_changes_with_every_bound_dimension() -> None:
    base = dict(
        run_id="run-1",
        publication_id="schyp-1",
        digest="sha256:abc",
        purpose="hypotheses",
        window_index=None,
        limit=100,
    )
    value = scientific_hypotheses_query_fingerprint(**base)
    for change in (
        {"run_id": "run-2"},
        {"publication_id": "schyp-2"},
        {"digest": "sha256:def"},
        {"purpose": "tests"},
        {"window_index": 0},
        {"limit": 50},
    ):
        assert scientific_hypotheses_query_fingerprint(**{**base, **change}) != value
