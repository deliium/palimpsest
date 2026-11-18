"""Purpose-bound cursor codec alias for scientific-model reads."""

from __future__ import annotations

from typing import Final

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "SCIENTIFIC_MODELS_CURSOR_TTL_SECONDS",
    "ScientificModelsCursorCodec",
    "ScientificModelsCursorError",
]

ScientificModelsCursorCodec = DiplomacyCursorCodec
ScientificModelsCursorError = DiplomacyCursorError
SCIENTIFIC_MODELS_CURSOR_TTL_SECONDS: Final[int] = 900
