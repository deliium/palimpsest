"""Bounded historical lineage discovery over a reader capability."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageFamily,
    LineageNativeKind,
)
from simulation.lineage_models import (
    MAX_LINEAGE_MAX_DEPTH,
    MAX_LINEAGE_MAX_EDGES,
    MAX_LINEAGE_MAX_NODES,
    MAX_LINEAGE_PAGE_SIZE,
    LineageDirection,
    LineageError,
    LineageScope,
    LineageSnapshotRef,
)
from simulation.lineage_ports import (
    LineageNodeCataloguePage,
    LineageReadBudget,
    LineageReadPort,
    LineageSnapshotCataloguePage,
)
from simulation.models import RunId
from world.identifiers import require_exact_nonneg_int

__all__ = [
    "LineageCatalogService",
    "LineageFamilyDescriptor",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.lineage_catalog")


@dataclass(frozen=True, slots=True)
class LineageFamilyDescriptor:
    family: LineageFamily
    available_classes: tuple[LineageEvidenceClass, ...]
    owner_required: bool
    directions: tuple[LineageDirection, ...] = (
        LineageDirection.ANCESTORS,
        LineageDirection.DESCENDANTS,
        LineageDirection.BOTH,
    )
    max_depth: int = MAX_LINEAGE_MAX_DEPTH
    max_nodes: int = MAX_LINEAGE_MAX_NODES
    max_edges: int = MAX_LINEAGE_MAX_EDGES
    max_page_size: int = MAX_LINEAGE_PAGE_SIZE


_FAMILY_CLASSES: Final[dict[LineageFamily, tuple[LineageEvidenceClass, ...]]] = {
    LineageFamily.GENEALOGY: (LineageEvidenceClass.OBJECTIVE,),
    LineageFamily.RECORD: (LineageEvidenceClass.OBJECTIVE,),
    LineageFamily.INSTITUTION: (LineageEvidenceClass.ANALYTICAL,),
    LineageFamily.MENTORSHIP: (
        LineageEvidenceClass.SUBJECTIVE,
        LineageEvidenceClass.ANALYTICAL,
    ),
    LineageFamily.KNOWLEDGE: (
        LineageEvidenceClass.SUBJECTIVE,
        LineageEvidenceClass.ANALYTICAL,
    ),
    LineageFamily.TECHNOLOGY: (
        LineageEvidenceClass.SUBJECTIVE,
        LineageEvidenceClass.ANALYTICAL,
    ),
    LineageFamily.NARRATIVE: (
        LineageEvidenceClass.SUBJECTIVE,
        LineageEvidenceClass.ANALYTICAL,
    ),
    LineageFamily.OFFICE_SUCCESSION: (LineageEvidenceClass.SUBJECTIVE,),
}


class LineageCatalogService:
    """Read-only family/snapshot/root discovery; never builds or repairs."""

    __slots__ = ("_reader",)

    def __init__(self, reader: LineageReadPort) -> None:
        self._reader = reader

    def families(self) -> tuple[LineageFamilyDescriptor, ...]:
        return tuple(
            LineageFamilyDescriptor(
                family=family,
                available_classes=classes,
                owner_required=classes == (LineageEvidenceClass.SUBJECTIVE,),
            )
            for family, classes in _FAMILY_CLASSES.items()
        )

    async def snapshots(
        self,
        scope: LineageScope,
        *,
        catalogue_ref: str | None = None,
        after: str | None = None,
        limit: int = 100,
    ) -> LineageSnapshotCataloguePage:
        _validate_limit(limit)
        _ensure_known_run(self._reader, scope.run_id)
        budget = LineageReadBudget.for_query()
        async with self._reader.open_read(
            run_id=scope.run_id, budget=budget, commit_ref=catalogue_ref
        ) as session:
            return await session.snapshot_page(scope, after, limit)

    async def roots(
        self,
        scope: LineageScope,
        snapshot: LineageSnapshotRef,
        *,
        after: str | None = None,
        limit: int = 100,
        native_kind: LineageNativeKind | None = None,
        native_id: str | None = None,
        catalogue_ref: str | None = None,
    ) -> LineageNodeCataloguePage:
        _validate_limit(limit)
        if (native_kind is None) != (native_id is None):
            raise LineageError("invalid_lineage_scope")
        _ensure_known_run(self._reader, scope.run_id)
        budget = LineageReadBudget.for_query()
        async with self._reader.open_read(
            run_id=scope.run_id, budget=budget, commit_ref=catalogue_ref
        ) as session:
            if native_kind is not None and native_id is not None:
                return await session.lookup_nodes(
                    snapshot, native_kind, native_id, after, limit
                )
            return await session.node_page(snapshot, after, limit)


def _ensure_known_run(reader: LineageReadPort, run_id: RunId) -> None:
    has_run = getattr(reader, "has_run", None)
    if callable(has_run) and not has_run(run_id):
        raise LineageError("lineage_run_not_found")


def _validate_limit(limit: int) -> int:
    value = require_exact_nonneg_int("limit", limit)
    if value < 1 or value > MAX_LINEAGE_PAGE_SIZE:
        raise LineageError("invalid_lineage_budget")
    return value
