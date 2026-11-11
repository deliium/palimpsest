"""Purpose-bound cursor codec alias for market-institution reads."""

from __future__ import annotations

from typing import Final

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "MARKET_INSTITUTIONS_CURSOR_TTL_SECONDS",
    "MarketInstitutionsCursorCodec",
    "MarketInstitutionsCursorError",
]

MarketInstitutionsCursorCodec = DiplomacyCursorCodec
MarketInstitutionsCursorError = DiplomacyCursorError
MARKET_INSTITUTIONS_CURSOR_TTL_SECONDS: Final[int] = 900
