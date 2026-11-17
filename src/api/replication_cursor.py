"""Purpose-bound cursor codec alias for scientific-replication reads."""

from __future__ import annotations

from typing import Final

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "REPLICATION_CURSOR_TTL_SECONDS",
    "ReplicationCursorCodec",
    "ReplicationCursorError",
]

ReplicationCursorCodec = DiplomacyCursorCodec
ReplicationCursorError = DiplomacyCursorError
REPLICATION_CURSOR_TTL_SECONDS: Final[int] = 900
