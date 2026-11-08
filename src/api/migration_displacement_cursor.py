# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
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
