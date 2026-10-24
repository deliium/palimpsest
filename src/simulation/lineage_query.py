"""Deterministic bounded neighborhood traversal over indexed lineage reads."""

from __future__ import annotations

import logging
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Final

from simulation.lineage_models import (
    LineageCoverage,
    LineageCoverageState,
    LineageDirection,
    LineageEdge,
    LineageError,
    LineageNode,
    LineageNodeState,
    LineagePage,
    LineageQuery,
    LineageSnapshotRef,
)
from simulation.lineage_ports import (
    LineageNeighborPage,
    LineageNeighborRow,
    LineageReadBudget,
    LineageReadPort,
    LineageReadSession,
)

__all__ = ["LineageQueryService"]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.lineage_query")
_NEIGHBOR_PAGE: Final[int] = 128


@dataclass(slots=True)
class _Record:
    kind: str
    key: str


class LineageQueryService:
    """Pure graph selection over one pinned, budgeted read session."""

    __slots__ = ("_reader",)

    def __init__(self, reader: LineageReadPort) -> None:
        self._reader = reader

    async def traverse(
        self,
        query: LineageQuery,
        *,
        session: LineageReadSession | None = None,
        record_offset: int = 0,
    ) -> LineagePage:
        if query.root is None:
            raise LineageError("invalid_lineage_scope")
        if record_offset < 0:
            raise LineageError("invalid_lineage_budget")
        context: AbstractAsyncContextManager[LineageReadSession] | None = None
        if session is None:
            context = self._reader.open_read(
                run_id=query.scope.run_id,
                budget=LineageReadBudget.for_query(),
            )
            session = await context.__aenter__()
        try:
            return await self._traverse(query, session, record_offset=record_offset)
        finally:
            if context is not None:
                await context.__aexit__(None, None, None)

    async def _traverse(
        self,
        query: LineageQuery,
        session: LineageReadSession,
        *,
        record_offset: int,
    ) -> LineagePage:
        root_ref = query.root
        assert root_ref is not None
        snapshot = query.snapshot or await session.resolve_snapshot(query.scope)
        root = await session.get_node(snapshot, root_ref.key)
        if root is None:
            raise LineageError("lineage_root_not_found")
        visited: dict[str, LineageNode] = {root.key: root}
        admitted_edges: dict[str, LineageEdge] = {}
        records: list[_Record] = [_Record("node", root.key)]
        frontier: list[tuple[int, str]] = [(0, root.key)]
        stop_reasons: list[str] = []
        traversal_partial = False

        while frontier:
            frontier.sort(key=lambda item: (item[0], item[1]))
            depth, key = frontier.pop(0)
            if depth >= query.max_depth:
                try:
                    probe = await self._read_neighbors(
                        session, snapshot, key, query.direction, query, visited
                    )
                except LineageError as exc:
                    if exc.code == "lineage_source_budget" and visited:
                        traversal_partial = True
                        stop_reasons.append(_budget_reason(session))
                        break
                    raise
                if any(row.edge.edge_key not in admitted_edges for row in probe.rows):
                    stop_reasons.append("depth_limit")
                continue
            try:
                page = await self._read_neighbors(
                    session, snapshot, key, query.direction, query, visited
                )
            except LineageError as exc:
                if exc.code == "lineage_source_budget" and visited:
                    traversal_partial = True
                    stop_reasons.append(_budget_reason(session))
                    break
                raise
            for row in page.rows:
                edge = row.edge
                if edge.edge_key in admitted_edges:
                    continue
                if len(admitted_edges) >= query.max_edges:
                    if "edge_limit" not in stop_reasons:
                        stop_reasons.append("edge_limit")
                    break
                next_key = self._next_key(edge, key, query.direction)
                if next_key is None:
                    next_key = row.node.key
                if next_key not in visited:
                    if len(visited) >= query.max_nodes:
                        if "node_limit" not in stop_reasons:
                            stop_reasons.append("node_limit")
                        continue
                    visited[next_key] = row.node
                    records.append(_Record("node", next_key))
                    frontier.append((depth + 1, next_key))
                admitted_edges[edge.edge_key] = edge
                records.append(_Record("edge", edge.edge_key))
                if row.node.state is LineageNodeState.UNRESOLVED:
                    if "unresolved_parent" not in stop_reasons:
                        stop_reasons.append("unresolved_parent")

        if record_offset > len(records) or (
            record_offset == len(records) and record_offset != 0
        ):
            raise LineageError("invalid_lineage_cursor")
        source_coverage = await _source_coverage(session, snapshot)
        if source_coverage is not None and source_coverage.pruned_count > 0:
            if "source_pruned" not in stop_reasons:
                stop_reasons.append("source_pruned")
        selected = records[record_offset : record_offset + query.page_size]
        has_more = record_offset + len(selected) < len(records)
        page_nodes: dict[str, LineageNode] = {}
        page_edges: list[LineageEdge] = []
        for record in selected:
            if record.kind == "node":
                page_nodes[record.key] = visited[record.key]
            else:
                edge = admitted_edges[record.key]
                page_edges.append(edge)
                page_nodes.setdefault(edge.source_key, visited[edge.source_key])
                page_nodes.setdefault(edge.target_key, visited[edge.target_key])
        if root.key not in page_nodes:
            page_nodes[root.key] = root
        matched = tuple(
            sorted(
                node.key
                for node in page_nodes.values()
                if not query.living_only or (node.living is True)
            )
        )
        context_only = tuple(
            sorted(key for key in page_nodes if key not in set(matched))
        )
        return LineagePage(
            root=root.ref,
            snapshot=snapshot,
            nodes=tuple(page_nodes[key] for key in sorted(page_nodes)),
            edges=tuple(page_edges),
            coverage=_merge_coverage(
                source_coverage,
                snapshot,
                partial=traversal_partial or bool(stop_reasons),
            ),
            visited_node_count=len(visited),
            visited_edge_count=len(admitted_edges),
            matched_node_keys=matched,
            context_only_node_keys=context_only,
            stop_reasons=tuple(dict.fromkeys(stop_reasons)),
            continuation=(str(record_offset + len(selected)) if has_more else None),
        )

    async def _read_neighbors(
        self,
        session: LineageReadSession,
        snapshot: LineageSnapshotRef,
        key: str,
        direction: LineageDirection,
        query: LineageQuery,
        visited: dict[str, LineageNode],
    ) -> LineageNeighborPage:
        rows: list[LineageNeighborRow] = []
        after: str | None = None
        declared = 0
        while True:
            page = await session.neighbors(
                snapshot, key, direction, after, _NEIGHBOR_PAGE
            )
            declared += page.declared_count
            rows.extend(page.rows)
            if page.continuation is None:
                break
            after = page.continuation
            if len(rows) >= query.max_edges:
                break
        if direction is LineageDirection.BOTH:
            incoming = sorted(
                (row for row in rows if row.edge.target_key == key),
                key=lambda row: row.edge.edge_key,
            )
            outgoing = sorted(
                (row for row in rows if row.edge.source_key == key),
                key=lambda row: row.edge.edge_key,
            )
            rows = [*incoming, *outgoing]
        else:
            rows.sort(key=lambda row: row.edge.edge_key)
        return LineageNeighborPage(
            rows=tuple(rows),
            declared_count=declared,
        )

    def _next_key(
        self, edge: LineageEdge, current: str, direction: LineageDirection
    ) -> str | None:
        if direction is LineageDirection.ANCESTORS:
            return edge.source_key
        if direction is LineageDirection.DESCENDANTS:
            return edge.target_key
        if edge.source_key == current:
            return edge.target_key
        if edge.target_key == current:
            return edge.source_key
        return None


def _budget_reason(session: LineageReadSession) -> str:
    budget = getattr(session, "budget", None)
    reason = getattr(budget, "exhausted_reason", None)
    if reason in {"source_read_limit", "source_byte_limit"}:
        return str(reason)
    return "source_read_limit"


async def _source_coverage(
    session: LineageReadSession, snapshot: LineageSnapshotRef
) -> LineageCoverage | None:
    reader = getattr(session, "coverage", None)
    if not callable(reader):
        return None
    try:
        value = await reader(snapshot)
    except LineageError:
        return None
    return value if type(value) is LineageCoverage else None


def _merge_coverage(
    source: LineageCoverage | None,
    snapshot: LineageSnapshotRef,
    *,
    partial: bool,
) -> LineageCoverage:
    if source is None:
        return LineageCoverage(
            state=(
                LineageCoverageState.PARTIAL
                if partial
                else LineageCoverageState.COMPLETE
            ),
            capture_end_tick=snapshot.boundary_tick,
            policy_version="lineage-traversal-v1",
        )
    state = source.state
    if partial and state is LineageCoverageState.COMPLETE:
        state = LineageCoverageState.PARTIAL
    return LineageCoverage(
        state=state,
        reason_codes=source.reason_codes,
        capture_start_tick=source.capture_start_tick,
        capture_end_tick=source.capture_end_tick or snapshot.boundary_tick,
        missing_prefix_tick=source.missing_prefix_tick,
        pruned_count=source.pruned_count,
        unresolved_count=source.unresolved_count,
        policy_version=source.policy_version or "lineage-traversal-v1",
    )
