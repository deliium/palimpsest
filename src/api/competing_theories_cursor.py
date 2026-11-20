"""Purpose-bound cursor codec alias for competing-theory reads."""

from __future__ import annotations

from typing import Final

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "COMPETING_THEORIES_CURSOR_TTL_SECONDS",
    "CompetingTheoriesCursorCodec",
    "CompetingTheoriesCursorError",
]

CompetingTheoriesCursorCodec = DiplomacyCursorCodec
CompetingTheoriesCursorError = DiplomacyCursorError
COMPETING_THEORIES_CURSOR_TTL_SECONDS: Final[int] = 900
