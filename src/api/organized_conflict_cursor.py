# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Purpose-bound HMAC cursors for organized-conflict reads."""

from __future__ import annotations

from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError

__all__ = [
    "ORGANIZED_CONFLICT_CURSOR_TTL_SECONDS",
    "OrganizedConflictCursorCodec",
    "OrganizedConflictCursorError",
]

ORGANIZED_CONFLICT_CURSOR_TTL_SECONDS = 900
OrganizedConflictCursorCodec = DiplomacyCursorCodec
OrganizedConflictCursorError = DiplomacyCursorError
