"""API service facade over neutral lineage catalogue/query/read ports."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from api.lineage_cursor import LineageCursorCodec
from persistence.lineage_filesystem import create_lineage_reader
from simulation.lineage_catalog import LineageCatalogService, LineageFamilyDescriptor
from simulation.lineage_identity import LineageNativeKind
from simulation.lineage_models import (
    LineageCoverage,
    LineageDirection,
    LineageError,
    LineageNode,
    LineagePage,
    LineageQuery,
    LineageScope,
    LineageSnapshotRef,
)
from simulation.lineage_participants import (
    LineageParticipantCard,
    order_participant_cards,
    project_participant_card,
)
from simulation.lineage_ports import (
    LineageNodeCataloguePage,
    LineageReadBudget,
    LineageReadPort,
    LineageSnapshotCataloguePage,
)
from simulation.lineage_query import LineageQueryService
from simulation.models import RunId

__all__ = [
    "MAX_PARTICIPANT_SCAN",
    "ArtifactLineageApiService",
    "LineageApiService",
    "LineageParticipantPage",
    "participant_filter_fingerprint",
]

MAX_PARTICIPANT_SCAN = 200


@dataclass(frozen=True, slots=True)
class LineageParticipantPage:
    """Bounded participant scan result for one pinned publication."""

    snapshot: LineageSnapshotRef
    items: tuple[LineageParticipantCard, ...]
    scanned_count: int
    unprojectable_count: int
    scan_limited: bool
    has_more: bool
    last_examined_key: str | None
    coverage: LineageCoverage
    run_commit_ref: str


class LineageApiService(Protocol):
    def families(self) -> tuple[LineageFamilyDescriptor, ...]: ...

    async def snapshots(
        self,
        scope: LineageScope,
        *,
        after: str | None,
        limit: int,
        catalogue_ref: str | None,
    ) -> tuple[LineageSnapshotCataloguePage, str]: ...

    async def nodes(
        self,
        scope: LineageScope,
        *,
        snapshot: LineageSnapshotRef | None,
        boundary_tick: int | None,
        after: str | None,
        limit: int,
        native_kind: LineageNativeKind | None,
        native_id: str | None,
        catalogue_ref: str | None,
    ) -> tuple[LineageNodeCataloguePage, LineageSnapshotRef, str]: ...

    async def traverse(
        self,
        query: LineageQuery,
        *,
        catalogue_ref: str | None,
        record_offset: int,
    ) -> LineagePage: ...

    async def traverse_scope(
        self,
        scope: LineageScope,
        *,
        boundary_tick: int | None,
        root_key: str,
        direction: str,
        max_depth: int,
        max_nodes: int,
        max_edges: int,
        living_only: bool,
        page_size: int,
        record_offset: int,
    ) -> tuple[LineageSnapshotRef, LineageNode | None, LineagePage | None]: ...

    async def resolve_snapshot(
        self, scope: LineageScope, boundary_tick: int | None
    ) -> tuple[LineageSnapshotRef, str]: ...

    async def get_node(
        self, scope: LineageScope, snapshot: LineageSnapshotRef, key: str
    ) -> LineageNode | None: ...

    async def participants(
        self,
        scope: LineageScope,
        *,
        agent_id: str,
        role: str,
        snapshot: LineageSnapshotRef | None,
        boundary_tick: int | None,
        after: str | None,
        limit: int,
    ) -> LineageParticipantPage: ...


class ArtifactLineageApiService:
    """Inject reader/cursor; opens one shared session per authenticated call."""

    def __init__(self, *, root: Path, codec: LineageCursorCodec) -> None:
        self._root = root
        self._codec = codec
        self._reader: LineageReadPort | None = None
        self._catalog: LineageCatalogService | None = None
        self._query: LineageQueryService | None = None

    def _services(self) -> tuple[LineageCatalogService, LineageQueryService]:
        if self._reader is None:
            self._reader = create_lineage_reader(self._root)
            self._catalog = LineageCatalogService(self._reader)
            self._query = LineageQueryService(self._reader)
        assert self._catalog is not None and self._query is not None
        return self._catalog, self._query

    @property
    def _read_port(self) -> LineageReadPort:
        self._services()
        assert self._reader is not None
        return self._reader

    def _require_run(self, run_id: RunId) -> None:
        probe = getattr(self._read_port, "has_run", None)
        if callable(probe) and not probe(run_id):
            raise LineageError("lineage_run_not_found")

    def families(self) -> tuple[LineageFamilyDescriptor, ...]:
        catalog, _query = self._services()
        return catalog.families()

    async def snapshots(
        self,
        scope: LineageScope,
        *,
        after: str | None,
        limit: int,
        catalogue_ref: str | None,
    ) -> tuple[LineageSnapshotCataloguePage, str]:
        self._require_run(scope.run_id)
        budget = LineageReadBudget.for_query()
        async with self._read_port.open_read(
            run_id=scope.run_id, budget=budget, commit_ref=catalogue_ref
        ) as session:
            page = await session.snapshot_page(scope, after, limit)
            return page, session.run_commit_ref

    async def nodes(
        self,
        scope: LineageScope,
        *,
        snapshot: LineageSnapshotRef | None,
        boundary_tick: int | None,
        after: str | None,
        limit: int,
        native_kind: LineageNativeKind | None,
        native_id: str | None,
        catalogue_ref: str | None,
    ) -> tuple[LineageNodeCataloguePage, LineageSnapshotRef, str]:
        self._require_run(scope.run_id)
        budget = LineageReadBudget.for_query()
        async with self._read_port.open_read(
            run_id=scope.run_id, budget=budget, commit_ref=catalogue_ref
        ) as session:
            resolved = snapshot or await session.resolve_snapshot(scope, boundary_tick)
            if native_kind is not None and native_id is not None:
                page = await session.lookup_nodes(
                    resolved, native_kind, native_id, after, limit
                )
            else:
                page = await session.node_page(resolved, after, limit)
            return page, resolved, session.run_commit_ref

    async def traverse(
        self,
        query: LineageQuery,
        *,
        catalogue_ref: str | None,
        record_offset: int,
    ) -> LineagePage:
        self._require_run(query.scope.run_id)
        budget = LineageReadBudget.for_query()
        async with self._read_port.open_read(
            run_id=query.scope.run_id, budget=budget, commit_ref=catalogue_ref
        ) as session:
            _catalog, query_service = self._services()
            return await query_service.traverse(
                query, session=session, record_offset=record_offset
            )

    async def get_node(
        self, scope: LineageScope, snapshot: LineageSnapshotRef, key: str
    ) -> LineageNode | None:
        self._require_run(scope.run_id)
        budget = LineageReadBudget.for_query()
        async with self._read_port.open_read(
            run_id=scope.run_id, budget=budget
        ) as session:
            return await session.get_node(snapshot, key)

    async def traverse_scope(
        self,
        scope: LineageScope,
        *,
        boundary_tick: int | None,
        root_key: str,
        direction: str,
        max_depth: int,
        max_nodes: int,
        max_edges: int,
        living_only: bool,
        page_size: int,
        record_offset: int,
    ) -> tuple[LineageSnapshotRef, LineageNode | None, LineagePage | None]:
        self._require_run(scope.run_id)
        budget = LineageReadBudget.for_query()
        async with self._read_port.open_read(
            run_id=scope.run_id, budget=budget
        ) as session:
            snapshot = await session.resolve_snapshot(scope, boundary_tick)
            root = await session.get_node(snapshot, root_key)
            if root is None:
                return snapshot, None, None
            query = LineageQuery(
                scope=scope,
                snapshot=snapshot,
                root=root.ref,
                direction=LineageDirection(direction),
                max_depth=max_depth,
                max_nodes=max_nodes,
                max_edges=max_edges,
                living_only=living_only,
                page_size=page_size,
            )
            _catalog, query_service = self._services()
            page = await query_service.traverse(
                query, session=session, record_offset=record_offset
            )
            return snapshot, root, page

    async def participants(
        self,
        scope: LineageScope,
        *,
        agent_id: str,
        role: str,
        snapshot: LineageSnapshotRef | None,
        boundary_tick: int | None,
        after: str | None,
        limit: int,
    ) -> LineageParticipantPage:
        """Scan one bounded catalogue window for native participant cards."""
        if scope.family.value != "mentorship":
            raise LineageError("invalid_lineage_scope")
        self._require_run(scope.run_id)
        budget = LineageReadBudget.for_query()
        async with self._read_port.open_read(
            run_id=scope.run_id, budget=budget
        ) as session:
            resolved = snapshot or await session.resolve_snapshot(scope, boundary_tick)
            page = await session.node_page(resolved, after, MAX_PARTICIPANT_SCAN)
            rows = page.rows
            if not rows and page.continuation is not None:
                raise LineageError("lineage_snapshot_corrupt")
            if after is not None and rows and rows[0].key <= after:
                raise LineageError("lineage_snapshot_corrupt")
            cards: list[LineageParticipantCard] = []
            scanned = 0
            unprojectable = 0
            last_examined: str | None = None
            for node in rows:
                scanned += 1
                last_examined = node.key
                card = project_participant_card(node, agent_id=agent_id, role=role)
                if card is None:
                    if node.mentorship_record is None:
                        unprojectable += 1
                    continue
                cards.append(card)
                if len(cards) >= limit:
                    break
            has_more = scanned < len(rows) or page.continuation is not None
            if (
                page.continuation is not None
                and after is not None
                and page.continuation <= after
            ):
                raise LineageError("lineage_snapshot_corrupt")
            coverage = page.coverage
            if coverage is None:
                coverage = await session.coverage(resolved)
            return LineageParticipantPage(
                snapshot=resolved,
                items=order_participant_cards(cards),
                scanned_count=scanned,
                unprojectable_count=unprojectable,
                scan_limited=has_more and scanned >= MAX_PARTICIPANT_SCAN,
                has_more=has_more,
                last_examined_key=last_examined,
                coverage=coverage,
                run_commit_ref=session.run_commit_ref,
            )

    async def resolve_snapshot(
        self, scope: LineageScope, boundary_tick: int | None
    ) -> tuple[LineageSnapshotRef, str]:
        self._require_run(scope.run_id)
        budget = LineageReadBudget.for_query()
        async with self._read_port.open_read(
            run_id=scope.run_id, budget=budget
        ) as session:
            return (
                await session.resolve_snapshot(scope, boundary_tick),
                session.run_commit_ref,
            )


def node_filter_fingerprint(
    native_kind: LineageNativeKind | None, native_id: str | None
) -> str:
    payload = f"{native_kind.value if native_kind else '-'}|{native_id or '-'}".encode()
    return hashlib.sha256(payload).hexdigest()


def participant_filter_fingerprint(*, agent_id: str, role: str, page_size: int) -> str:
    payload = f"{agent_id}|{role}|{page_size}".encode()
    return hashlib.sha256(payload).hexdigest()
