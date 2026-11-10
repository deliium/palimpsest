"""Purpose-bound HMAC cursors for trade-network reads."""

from __future__ import annotations

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "TRADE_NETWORKS_CURSOR_TTL_SECONDS",
    "TradeNetworksCursorCodec",
    "TradeNetworksCursorError",
]

TRADE_NETWORKS_CURSOR_TTL_SECONDS = 900
TradeNetworksCursorCodec = DiplomacyCursorCodec
TradeNetworksCursorError = DiplomacyCursorError
