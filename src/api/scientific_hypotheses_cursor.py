"""Purpose-bound cursor codec alias for scientific-hypothesis reads."""

from __future__ import annotations

from typing import Final

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "SCIENTIFIC_HYPOTHESES_CURSOR_TTL_SECONDS",
    "ScientificHypothesesCursorCodec",
    "ScientificHypothesesCursorError",
]

ScientificHypothesesCursorCodec = DiplomacyCursorCodec
ScientificHypothesesCursorError = DiplomacyCursorError
SCIENTIFIC_HYPOTHESES_CURSOR_TTL_SECONDS: Final[int] = 900
