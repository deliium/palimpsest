"""Purpose-bound cursor codec alias for scientific-institution reads."""

from __future__ import annotations

from typing import Final

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "SCIENTIFIC_INSTITUTIONS_CURSOR_TTL_SECONDS",
    "ScientificInstitutionsCursorCodec",
    "ScientificInstitutionsCursorError",
]

ScientificInstitutionsCursorCodec = DiplomacyCursorCodec
ScientificInstitutionsCursorError = DiplomacyCursorError
SCIENTIFIC_INSTITUTIONS_CURSOR_TTL_SECONDS: Final[int] = 900
