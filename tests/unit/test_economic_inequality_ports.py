# mypy: ignore-errors
"""Purpose-bound cursor tests for economic-inequality reads."""

from __future__ import annotations

import pytest

from simulation.economic_inequality_ports import (
    ECONOMIC_INEQUALITY_CURSOR_TOKEN,
    ECONOMIC_INEQUALITY_PURPOSES,
    EconomicInequalityCursor,
    economic_inequality_query_fingerprint,
)


def test_purposes_are_closed_and_exact() -> None:
    assert ECONOMIC_INEQUALITY_PURPOSES == (
        "summary",
        "dimensions",
        "possession",
        "access",
        "claims",
        "cohorts",
        "societies",
    )
    assert ECONOMIC_INEQUALITY_CURSOR_TOKEN.startswith("palimpsest.economic_inequality")


def test_fingerprint_binds_window_and_purpose() -> None:
    first = economic_inequality_query_fingerprint(
        run_id="run-1",
        publication_id="econ-pub-1",
        digest="sha256:abc",
        purpose="possession",
        limit=100,
        window_index=0,
    )
    second = economic_inequality_query_fingerprint(
        run_id="run-1",
        publication_id="econ-pub-1",
        digest="sha256:abc",
        purpose="possession",
        limit=100,
        window_index=1,
    )
    assert first != second


def test_cursor_rejects_unknown_purpose_or_window() -> None:
    with pytest.raises(ValueError, match="cursor_invalid"):
        EconomicInequalityCursor(
            purpose="unknown",
            fingerprint="f",
            after_key="",
            window_index=None,
        )
    with pytest.raises(ValueError, match="cursor_invalid"):
        EconomicInequalityCursor(
            purpose="dimensions",
            fingerprint="f",
            after_key="",
            window_index=512,
        )
