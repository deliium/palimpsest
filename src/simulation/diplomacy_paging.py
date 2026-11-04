"""Pure bounded selection over one canonical diplomacy snapshot."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from simulation.diplomacy_models import (
    MAX_DETAIL_ROWS,
    DiplomacyArtifactError,
    DiplomacySnapshot,
)

__all__ = [
    "DiplomacyRowSelection",
    "select_diplomacy_instrument",
    "select_diplomacy_instruments",
    "select_diplomacy_lineage",
    "select_diplomacy_relation",
    "select_diplomacy_relations",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.diplomacy_paging")


@dataclass(frozen=True, slots=True)
class DiplomacyRowSelection:
    rows: tuple[object, ...]
    next_key: str | None = None
    truncated: bool = False


def _clamp(limit: int) -> int:
    if type(limit) is not int or isinstance(limit, bool):
        raise TypeError("limit must be int")
    return max(1, min(limit, MAX_DETAIL_ROWS))


def _page(rows: tuple, *, after_key: str | None, limit: int, id_name: str):
    ordered = tuple(sorted(rows, key=lambda row: getattr(row, id_name)))
    start = 0
    if after_key is not None:
        ids = [getattr(row, id_name) for row in ordered]
        if after_key in ids:
            start = ids.index(after_key) + 1
        else:
            start = len(ordered)
    page = ordered[start : start + _clamp(limit)]
    next_key = (
        getattr(page[-1], id_name)
        if page and start + len(page) < len(ordered)
        else None
    )
    _LOG.debug("diplomacy_page rows=%s next=%s", len(page), next_key is not None)
    return page, next_key


def select_diplomacy_relations(
    snapshot: DiplomacySnapshot,
    *,
    after_key: str | None = None,
    limit: int = MAX_DETAIL_ROWS,
) -> DiplomacyRowSelection:
    rows, next_key = _page(
        snapshot.relations, after_key=after_key, limit=limit, id_name="relation_id"
    )
    return DiplomacyRowSelection(rows=rows, next_key=next_key)


def select_diplomacy_relation(
    snapshot: DiplomacySnapshot,
    relation_id: str,
    *,
    limit: int = MAX_DETAIL_ROWS,
) -> DiplomacyRowSelection:
    relation = next(
        (row for row in snapshot.relations if row.relation_id == relation_id), None
    )
    if relation is None:
        raise DiplomacyArtifactError("diplomacy_not_found")
    parties = tuple(
        row for row in snapshot.parties if row.party_token in relation.party_tokens
    )
    contacts = tuple(row for row in snapshot.contacts if row.relation_id == relation_id)
    envoys = tuple(row for row in snapshot.envoys if row.relation_id == relation_id)
    negotiations = tuple(
        row for row in snapshot.negotiations if row.relation_id == relation_id
    )
    instruments = tuple(
        row for row in snapshot.instruments if row.relation_id == relation_id
    )
    instrument_ids = {row.instrument_id for row in instruments}
    declarations = tuple(
        row for row in snapshot.declarations if row.instrument_id in instrument_ids
    )
    misrepresentations = tuple(
        row
        for row in snapshot.misrepresentations
        if row.instrument_id in instrument_ids
    )
    terminations = tuple(
        row
        for row in snapshot.terminations
        if row.target_ref == relation_id or row.target_ref in instrument_ids
    )
    rows = (
        relation,
        *parties,
        *contacts,
        *envoys,
        *negotiations,
        *instruments,
        *declarations,
        *misrepresentations,
        *terminations,
    )
    clipped = rows[: _clamp(limit)]
    return DiplomacyRowSelection(
        rows=clipped,
        next_key=None,
        truncated=len(clipped) < len(rows),
    )


def select_diplomacy_instruments(
    snapshot: DiplomacySnapshot,
    *,
    after_key: str | None = None,
    limit: int = MAX_DETAIL_ROWS,
) -> DiplomacyRowSelection:
    rows, next_key = _page(
        snapshot.instruments,
        after_key=after_key,
        limit=limit,
        id_name="instrument_id",
    )
    return DiplomacyRowSelection(rows=rows, next_key=next_key)


def select_diplomacy_instrument(
    snapshot: DiplomacySnapshot,
    instrument_id: str,
    *,
    limit: int = MAX_DETAIL_ROWS,
) -> DiplomacyRowSelection:
    instrument = next(
        (row for row in snapshot.instruments if row.instrument_id == instrument_id),
        None,
    )
    if instrument is None:
        raise DiplomacyArtifactError("diplomacy_not_found")
    declarations = tuple(
        row for row in snapshot.declarations if row.instrument_id == instrument_id
    )
    misrepresentations = tuple(
        row for row in snapshot.misrepresentations if row.instrument_id == instrument_id
    )
    terminations = tuple(
        row for row in snapshot.terminations if row.target_ref == instrument_id
    )
    rows = (instrument, *declarations, *misrepresentations, *terminations)
    clipped = rows[: _clamp(limit)]
    return DiplomacyRowSelection(
        rows=clipped,
        next_key=None,
        truncated=len(clipped) < len(rows),
    )


def select_diplomacy_lineage(
    snapshot: DiplomacySnapshot,
    *,
    after_key: str | None = None,
    limit: int = MAX_DETAIL_ROWS,
) -> DiplomacyRowSelection:
    rows, next_key = _page(
        snapshot.lineage, after_key=after_key, limit=limit, id_name="edge_id"
    )
    return DiplomacyRowSelection(rows=rows, next_key=next_key)
