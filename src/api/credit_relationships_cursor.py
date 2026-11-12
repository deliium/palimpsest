"""Purpose-bound cursor codec alias for credit relationship reads."""

from __future__ import annotations

from typing import Final

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "CREDIT_RELATIONSHIPS_CURSOR_TTL_SECONDS",
    "CreditRelationshipsCursorCodec",
    "CreditRelationshipsCursorError",
]

CreditRelationshipsCursorCodec = DiplomacyCursorCodec
CreditRelationshipsCursorError = DiplomacyCursorError
CREDIT_RELATIONSHIPS_CURSOR_TTL_SECONDS: Final[int] = 900
