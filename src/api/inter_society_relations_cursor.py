"""Purpose-bound HMAC cursors for inter-society-relations reads."""

from __future__ import annotations

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "INTER_SOCIETY_RELATIONS_CURSOR_TTL_SECONDS",
    "InterSocietyRelationsCursorCodec",
    "InterSocietyRelationsCursorError",
]

INTER_SOCIETY_RELATIONS_CURSOR_TTL_SECONDS = 900
InterSocietyRelationsCursorCodec = DiplomacyCursorCodec
InterSocietyRelationsCursorError = DiplomacyCursorError
