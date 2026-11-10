"""Purpose-bound HMAC cursors for supply-chain reads."""

from __future__ import annotations

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "SUPPLY_CHAIN_CURSOR_TTL_SECONDS",
    "SupplyChainCursorCodec",
    "SupplyChainCursorError",
]

SUPPLY_CHAIN_CURSOR_TTL_SECONDS = 900
SupplyChainCursorCodec = DiplomacyCursorCodec
SupplyChainCursorError = DiplomacyCursorError
