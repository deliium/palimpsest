"""Deterministic, byte-bounded selection over snapshot rows."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from typing import Final

from simulation.macro_society_codec import encode_macro_society_value
from simulation.macro_society_models import MacroSocietyArtifactError

__all__ = [
    "MAX_PAGE_ROWS",
    "MacroSocietyRowSelection",
    "select_macro_society_rows",
]

MAX_PAGE_ROWS: Final[int] = 500


def _encode_row(value: object) -> bytes:
    if is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)  # type: ignore[arg-type]
    return encode_macro_society_value(value)


@dataclass(frozen=True, slots=True)
class MacroSocietyRowSelection:
    """One ordered page plus the next offset and encoded size."""

    rows: tuple[object, ...]
    next_offset: int | None
    bytes_used: int

    def __post_init__(self) -> None:
        if self.next_offset is not None and self.next_offset < 0:
            raise MacroSocietyArtifactError("macro_society_invalid_offset")
        if self.bytes_used < 0:
            raise MacroSocietyArtifactError("macro_society_invalid_value")


def select_macro_society_rows(
    rows: Sequence[object],
    *,
    offset: int,
    limit: int,
    max_bytes: int,
    encode: Callable[[object], bytes] = _encode_row,
) -> MacroSocietyRowSelection:
    """Select at most ``max_bytes`` of canonical rows from ``offset``.

    At least one row is returned even when it alone exceeds ``max_bytes``; the
    caller enforces the response cap. Order is preserved.
    """
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise MacroSocietyArtifactError("macro_society_invalid_offset")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise MacroSocietyArtifactError("macro_society_invalid_limit")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 1:
        raise MacroSocietyArtifactError("macro_society_invalid_limit")
    page_limit = min(limit, MAX_PAGE_ROWS)
    selected: list[object] = []
    bytes_used = 0
    index = offset
    total = len(rows)
    while index < total and len(selected) < page_limit:
        encoded = encode(rows[index])
        if selected and bytes_used + len(encoded) > max_bytes:
            break
        selected.append(rows[index])
        bytes_used += len(encoded)
        index += 1
    next_offset = index if index < total else None
    return MacroSocietyRowSelection(
        rows=tuple(selected), next_offset=next_offset, bytes_used=bytes_used
    )
