"""Purpose-bound cursor codec alias for economic-cascade reads."""

from __future__ import annotations

from typing import Final

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "ECONOMIC_CASCADES_CURSOR_TTL_SECONDS",
    "EconomicCascadesCursorCodec",
    "EconomicCascadesCursorError",
]

EconomicCascadesCursorCodec = DiplomacyCursorCodec
EconomicCascadesCursorError = DiplomacyCursorError
ECONOMIC_CASCADES_CURSOR_TTL_SECONDS: Final[int] = 900
