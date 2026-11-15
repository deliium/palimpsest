"""Purpose-bound cursor codec alias for social-mobility reads."""

from __future__ import annotations

from typing import Final

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "SOCIAL_MOBILITY_CURSOR_TTL_SECONDS",
    "SocialMobilityCursorCodec",
    "SocialMobilityCursorError",
]

SocialMobilityCursorCodec = DiplomacyCursorCodec
SocialMobilityCursorError = DiplomacyCursorError
SOCIAL_MOBILITY_CURSOR_TTL_SECONDS: Final[int] = 900
