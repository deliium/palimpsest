# mypy: ignore-errors
"""Purpose-bound cursor alias tests for economic-inequality reads."""

from __future__ import annotations

from api.diplomacy_cursor import DiplomacyCursorCodec
from api.economic_inequality_cursor import (
    ECONOMIC_INEQUALITY_CURSOR_TTL_SECONDS,
    EconomicInequalityCursorCodec,
)


def test_cursor_alias_and_ttl_are_locked() -> None:
    assert EconomicInequalityCursorCodec is DiplomacyCursorCodec
    assert ECONOMIC_INEQUALITY_CURSOR_TTL_SECONDS == 900


def test_cursor_round_trip_is_purpose_bound() -> None:
    codec = EconomicInequalityCursorCodec(b"k" * 32)
    token = codec.encode(
        purpose="possession",
        run_id="run-1",
        publication_id="econ-pub-1",
        snapshot_digest="sha256:abc",
        query_fingerprint="fingerprint",
        after_key="000|resource_possession|observed_item_count",
    )
    payload = codec.decode(token, purpose="possession")
    assert payload["run_id"] == "run-1"
    assert payload["after_key"].startswith("000|")
