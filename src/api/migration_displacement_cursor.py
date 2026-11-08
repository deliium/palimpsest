"""Purpose-bound HMAC cursors for migration-displacement reads."""

from __future__ import annotations

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "MIGRATION_DISPLACEMENT_CURSOR_TTL_SECONDS",
    "MigrationDisplacementCursorCodec",
    "MigrationDisplacementCursorError",
]

MIGRATION_DISPLACEMENT_CURSOR_TTL_SECONDS = 900
MigrationDisplacementCursorCodec = DiplomacyCursorCodec
MigrationDisplacementCursorError = DiplomacyCursorError
