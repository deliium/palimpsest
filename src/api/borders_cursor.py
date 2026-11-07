"""Purpose-bound HMAC cursors for border reads."""

from __future__ import annotations

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "BORDERS_CURSOR_TTL_SECONDS",
    "BordersCursorCodec",
    "BordersCursorError",
]

BORDERS_CURSOR_TTL_SECONDS = 900
BordersCursorCodec = DiplomacyCursorCodec
BordersCursorError = DiplomacyCursorError
