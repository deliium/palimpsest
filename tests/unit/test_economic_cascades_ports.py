# mypy: ignore-errors
"""Cursor purposes, fingerprints, and read/publication protocols."""

from __future__ import annotations

import pytest

from simulation.economic_cascades_ports import (
    ECONOMIC_CASCADES_CURSOR_PURPOSES,
    ECONOMIC_CASCADES_CURSOR_TOKEN,
    EconomicCascadesCursor,
    economic_cascades_query_fingerprint,
)

pytestmark = pytest.mark.unit


def test_cursor_purposes_are_closed() -> None:
    assert ECONOMIC_CASCADES_CURSOR_TOKEN.endswith(".v1")
    assert ECONOMIC_CASCADES_CURSOR_PURPOSES == (
        "disruptions",
        "dependencies",
        "chains",
        "propagation",
        "coverage",
        "windows",
    )


def test_fingerprint_is_sensitive_to_every_query_dimension() -> None:
    base = dict(
        run_id="run-1",
        publication_id="ecasc-1",
        digest="sha256:abc",
        purpose="chains",
        window_index=0,
        limit=100,
    )
    value = economic_cascades_query_fingerprint(**base)
    for change in (
        {"purpose": "disruptions"},
        {"window_index": 1},
        {"limit": 50},
        {"publication_id": "ecasc-2"},
    ):
        assert economic_cascades_query_fingerprint(**{**base, **change}) != value


def test_cursor_validation() -> None:
    cursor = EconomicCascadesCursor(
        purpose="chains",
        window_index=None,
        after="0001|casc-1",
        query_fingerprint="abc",
    )
    assert cursor.purpose == "chains"
    with pytest.raises(ValueError):
        EconomicCascadesCursor(
            purpose="summary",
            window_index=None,
            after="",
            query_fingerprint="abc",
        )
    with pytest.raises(ValueError):
        EconomicCascadesCursor(
            purpose="chains",
            window_index=512,
            after="",
            query_fingerprint="abc",
        )
