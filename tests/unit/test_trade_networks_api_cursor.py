# mypy: ignore-errors
"""Purpose-bound trade-network cursor codec."""

from __future__ import annotations

import pytest

from api.trade_networks_cursor import (
    TRADE_NETWORKS_CURSOR_TTL_SECONDS,
    TradeNetworksCursorCodec,
    TradeNetworksCursorError,
)


def _encode(codec: TradeNetworksCursorCodec, purpose: str = "corridors") -> str:
    return codec.encode(
        purpose=purpose,
        run_id="run-1",
        publication_id="trd-pub-00000000000000000000000000000000",
        snapshot_digest="a" * 64,
        query_fingerprint="b" * 64,
        after_key="00000000000000000001|trd-cor-0000000000000001",
    )


def test_cursor_ttl_and_purpose() -> None:
    clock = [0.0]
    codec = TradeNetworksCursorCodec(b"k" * 32, now=lambda: clock[0])
    token = _encode(codec)
    payload = codec.decode(token, purpose="corridors")
    assert payload["purpose"] == "corridors"
    clock[0] = TRADE_NETWORKS_CURSOR_TTL_SECONDS + 1
    with pytest.raises(TradeNetworksCursorError) as excinfo:
        codec.decode(token, purpose="corridors")
    assert excinfo.value.reason_code == "diplomacy_cursor_expired"


def test_tampered_cursor_rejected() -> None:
    codec = TradeNetworksCursorCodec(b"k" * 32, now=lambda: 0.0)
    token = _encode(codec)
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    with pytest.raises(TradeNetworksCursorError):
        codec.decode(tampered, purpose="corridors")
    with pytest.raises(TradeNetworksCursorError):
        codec.decode(token, purpose="flows")
