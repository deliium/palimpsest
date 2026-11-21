"""Purpose-bound cursor codec alias for science-diffusion reads."""

from __future__ import annotations

from typing import Final

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "SCIENCE_DIFFUSION_CURSOR_TTL_SECONDS",
    "ScienceDiffusionCursorCodec",
    "ScienceDiffusionCursorError",
]

ScienceDiffusionCursorCodec = DiplomacyCursorCodec
ScienceDiffusionCursorError = DiplomacyCursorError
SCIENCE_DIFFUSION_CURSOR_TTL_SECONDS: Final[int] = 900
