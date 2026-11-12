"""Purpose-bound cursor codec alias for emergent-price reads."""

from __future__ import annotations

from typing import Final

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "EMERGENT_PRICES_CURSOR_TTL_SECONDS",
    "EmergentPricesCursorCodec",
    "EmergentPricesCursorError",
]

EmergentPricesCursorCodec = DiplomacyCursorCodec
EmergentPricesCursorError = DiplomacyCursorError
EMERGENT_PRICES_CURSOR_TTL_SECONDS: Final[int] = 900
