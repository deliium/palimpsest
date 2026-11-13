"""Purpose-bound cursor codec alias for economic-inequality reads."""

from __future__ import annotations

from typing import Final

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "ECONOMIC_INEQUALITY_CURSOR_TTL_SECONDS",
    "EconomicInequalityCursorCodec",
    "EconomicInequalityCursorError",
]

EconomicInequalityCursorCodec = DiplomacyCursorCodec
EconomicInequalityCursorError = DiplomacyCursorError
ECONOMIC_INEQUALITY_CURSOR_TTL_SECONDS: Final[int] = 900
