"""Pure byte-aware keyset selection; filters never hide source progress."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from simulation.civilization_codec import encode_civilization_value
from simulation.civilization_models import CivilizationError, _id
from simulation.civilization_ports import CivilizationReadBudget
from simulation.civilization_rows import CivilizationRow

__all__ = ["CivilizationRowSelection", "select_civilization_rows"]


@dataclass(frozen=True, slots=True)
class CivilizationRowSelection:
    rows: tuple[CivilizationRow, ...]
    continuation_after: str | None
    truncated: bool


def select_civilization_rows(
    source: Sequence[CivilizationRow],
    *,
    budget: CivilizationReadBudget,
    after_key: str | None = None,
    matches: Callable[[CivilizationRow], bool] | None = None,
) -> CivilizationRowSelection:
    """Input is sorted/indexed by the adapter; pending rows are never consumed.

    Caller reserves serialized envelope bytes before selection. Source adapters
    separately reserve physical reads before supplying each indexed shard.
    """
    if after_key is not None:
        _id(after_key)
    retained: list[CivilizationRow] = []
    last_scanned = after_key
    previous: str | None = None
    for row in source:
        key = row.context.row_id
        if previous is not None and key <= previous:
            raise CivilizationError("civilization_storage_corrupt")
        previous = key
        if after_key is not None and key <= after_key:
            continue
        try:
            budget.reserve_scan(1)
        except CivilizationError:
            return CivilizationRowSelection(tuple(retained), last_scanned, True)
        if matches is not None and not matches(row):
            last_scanned = key
            continue
        # Oversized rows fail explicitly, rather than returning the same empty
        # continuation forever. Serialization errors must not become budget gaps.
        encoded = encode_civilization_value(row)
        try:
            budget.reserve_response(len(encoded) + 1, rows=1)
        except CivilizationError:
            if last_scanned == after_key and not retained:
                raise
            return CivilizationRowSelection(tuple(retained), last_scanned, True)
        retained.append(row)
        last_scanned = key
    return CivilizationRowSelection(tuple(retained), None, False)
