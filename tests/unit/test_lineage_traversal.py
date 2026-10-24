"""Deterministic bounded traversal over indexed session fakes and filesystem."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from pathlib import Path

import pytest

from persistence.lineage_filesystem import (
    create_lineage_publisher,
    create_lineage_reader,
)
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageEvidenceRef,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
    lineage_edge_key,
)
from simulation.lineage_models import (
    LineageCoverage,
    LineageCoverageState,
    LineageDirection,
    LineageEdge,
    LineageError,
    LineageNode,
    LineageNodeState,
    LineageQuery,
    LineageScope,
    LineageSnapshotRef,
)
from simulation.lineage_ports import (
    LineageBoundaryFrame,
    LineageNeighborPage,
    LineageNeighborRow,
    LineageNodeCataloguePage,
    LineagePublication,
    LineageReadBudget,
    LineageSnapshotCataloguePage,
)
from simulation.lineage_query import LineageQueryService
from simulation.models import RunId

_RUN = RunId("run-traversal")
_SCOPE = LineageScope(
    run_id=_RUN,
    family=LineageFamily.GENEALOGY,
    evidence_class=LineageEvidenceClass.OBJECTIVE,
)
_SNAPSHOT = LineageSnapshotRef(
    publication_id="publication-1", digest="a" * 64, boundary_tick=5
)


def _node(name: str, *, living: bool | None = True) -> LineageNode:
    return LineageNode(
        ref=LineageNodeRef(
            run_id=_RUN,
            family=LineageFamily.GENEALOGY,
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.AGENT,
            native_id=name,
        ),
        state=LineageNodeState.OBSERVED,
        living=living,
    )


def _edge(source: str, target: str, *, suffix: str = "") -> LineageEdge:
    source_key = _node(source).key
    target_key = _node(target).key
    evidence = LineageEvidenceRef(
        evidence_class=LineageEvidenceClass.OBJECTIVE,
        native_kind=LineageNativeKind.AGENT,
        native_id=f"{source}-{target}{suffix}",
        observed_tick=1,
    )
    return LineageEdge(
        edge_key=lineage_edge_key(
            relation="parent_of",
            source_key=source_key,
            target_key=target_key,
            native_kind=LineageNativeKind.AGENT,
            native_id=f"{source}-{target}{suffix}",
            evidence_keys=(evidence.key,),
        ),
        source_key=source_key,
        target_key=target_key,
        relation="parent_of",
        native_kind=LineageNativeKind.AGENT,
        native_id=f"{source}-{target}{suffix}",
        evidence_refs=(evidence,),
        observed_tick=1,
    )


class _FakeSession:
    def __init__(
        self,
        nodes: tuple[LineageNode, ...],
        edges: tuple[LineageEdge, ...],
        *,
        budget: LineageReadBudget | None = None,
    ) -> None:
        self.nodes: dict[str, LineageNode] = {node.key: node for node in nodes}
        self.edges: dict[str, list[LineageEdge]] = {
            node.ref.native_id: [] for node in nodes
        }
        self.incoming: dict[str, list[LineageEdge]] = {
            node.ref.native_id: [] for node in nodes
        }
        for edge in edges:
            source = self._by_key(edge.source_key)
            target = self._by_key(edge.target_key)
            self.edges[source.ref.native_id].append(edge)
            self.incoming[target.ref.native_id].append(edge)
        self.budget = budget or LineageReadBudget.for_query()
        self.run_commit_ref = "commit-1"
        self.calls: list[str] = []

    def _by_key(self, key: str) -> LineageNode:
        return self.nodes[key]

    def _charge(self) -> None:
        self.budget.reserve(1)

    async def resolve_snapshot(
        self, scope: LineageScope, boundary_tick: int | None = None
    ) -> LineageSnapshotRef:
        self._charge()
        if boundary_tick is not None and boundary_tick != _SNAPSHOT.boundary_tick:
            raise LineageError("snapshot_unavailable")
        return _SNAPSHOT

    async def get_node(
        self, snapshot: LineageSnapshotRef, key: str
    ) -> LineageNode | None:
        self._charge()
        return self.nodes.get(key)

    async def neighbors(
        self,
        snapshot: LineageSnapshotRef,
        key: str,
        direction: LineageDirection,
        after: str | None,
        limit: int,
    ) -> LineageNeighborPage:
        self._charge()
        node = self.nodes[key]
        rows: list[LineageNeighborRow] = []
        if direction in (LineageDirection.ANCESTORS, LineageDirection.BOTH):
            rows.extend(
                LineageNeighborRow(edge=edge, node=self._by_key(edge.source_key))
                for edge in self.incoming[node.ref.native_id]
            )
        if direction in (LineageDirection.DESCENDANTS, LineageDirection.BOTH):
            rows.extend(
                LineageNeighborRow(edge=edge, node=self._by_key(edge.target_key))
                for edge in self.edges[node.ref.native_id]
            )
        rows.sort(key=lambda row: row.edge.edge_key)
        if after is not None:
            rows = [row for row in rows if row.edge.edge_key > after]
        selected = rows[:limit]
        return LineageNeighborPage(
            rows=tuple(selected),
            declared_count=len(rows),
            continuation=selected[-1].edge.edge_key if len(rows) > limit else None,
        )

    async def node_page(
        self, snapshot: LineageSnapshotRef, after: str | None, limit: int
    ) -> LineageNodeCataloguePage:
        self._charge()
        return LineageNodeCataloguePage(rows=(), declared_count=0)

    async def lookup_nodes(
        self,
        snapshot: LineageSnapshotRef,
        native_kind: LineageNativeKind,
        native_id: str,
        after: str | None,
        limit: int,
    ) -> LineageNodeCataloguePage:
        self._charge()
        return LineageNodeCataloguePage(rows=(), declared_count=0)

    async def snapshot_page(
        self, scope: LineageScope, after: str | None, limit: int
    ) -> LineageSnapshotCataloguePage:
        self._charge()
        return LineageSnapshotCataloguePage(rows=(), declared_count=0)


class _Reader:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    def open_read(
        self,
        *,
        run_id: RunId,
        budget: LineageReadBudget,
        commit_ref: str | None = None,
    ) -> AbstractAsyncContextManager[_FakeSession]:
        session = self.session

        class _Context:
            async def __aenter__(self) -> _FakeSession:
                return session

            async def __aexit__(self, *_exc: object) -> None:
                return None

        return _Context()


def _query(root: str, **overrides: object) -> LineageQuery:
    values = {
        "scope": _SCOPE,
        "snapshot": _SNAPSHOT,
        "root": _node(root).ref,
        "direction": LineageDirection.DESCENDANTS,
        "max_depth": 4,
        "max_nodes": 200,
        "max_edges": 500,
        "living_only": False,
        "page_size": 100,
    }
    values.update(overrides)
    return LineageQuery(**values)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_chain_diamond_cycle_and_depth_zero() -> None:
    nodes = (_node("a"), _node("b"), _node("c"), _node("d"))
    edges = (
        _edge("a", "b"),
        _edge("a", "c"),
        _edge("b", "d"),
        _edge("c", "d"),
        _edge("d", "a", suffix="cycle"),
    )
    service = LineageQueryService(_Reader(_FakeSession(nodes, edges)))
    page = await service.traverse(_query("a"))
    ids = {node.ref.native_id for node in page.nodes}
    assert ids == {"a", "b", "c", "d"}
    assert page.visited_edge_count == 5
    zero = await service.traverse(_query("a", max_depth=0))
    assert {node.ref.native_id for node in zero.nodes} == {"a"}
    assert "depth_limit" in zero.stop_reasons


@pytest.mark.asyncio
async def test_living_only_marks_context_and_pagination_union() -> None:
    nodes = (_node("a", living=True), _node("b", living=False), _node("c", living=True))
    edges = (_edge("a", "b"), _edge("b", "c"))
    service = LineageQueryService(_Reader(_FakeSession(nodes, edges)))
    page = await service.traverse(_query("a", living_only=True))
    assert {node.ref.native_id for node in page.nodes} == {"a", "b", "c"}
    assert {
        node.ref.native_id for node in page.nodes if node.key in page.matched_node_keys
    } == {"a", "c"}
    assert {
        node.ref.native_id
        for node in page.nodes
        if node.key in page.context_only_node_keys
    } == {"b"}

    seen: set[str] = set()
    offset = 0
    while True:
        paged = await service.traverse(_query("a", page_size=1), record_offset=offset)
        seen.update(node.ref.native_id for node in paged.nodes)
        if paged.continuation is None:
            break
        offset = int(paged.continuation)
    assert seen == {"a", "b", "c"}


@pytest.mark.asyncio
async def test_budget_before_root_is_not_an_empty_graph() -> None:
    budget = (
        LineageReadBudget(max_physical_reads=0, max_source_bytes=0)
        if False
        else LineageReadBudget(max_physical_reads=1, max_source_bytes=1)
    )
    session = _FakeSession((_node("a"),), (), budget=budget)
    service = LineageQueryService(_Reader(session))
    with pytest.raises(LineageError, match="lineage_source_budget"):
        await service.traverse(_query("a", snapshot=None))


@pytest.mark.asyncio
async def test_real_filesystem_reads_are_charged(tmp_path: Path) -> None:
    source = _node("a")
    child = _node("b")
    edge = _edge("a", "b")
    publisher = create_lineage_publisher(tmp_path)
    await publisher.publish(
        LineagePublication(
            snapshot=LineageSnapshotRef(
                publication_id="placeholder", digest="a" * 64, boundary_tick=5
            ),
            frame=LineageBoundaryFrame(
                run_id=_RUN,
                scope=_SCOPE,
                boundary_tick=5,
                observed_boundary=5,
                nodes=(source, child),
                edges=(edge,),
                coverage=LineageCoverage(
                    state=LineageCoverageState.COMPLETE,
                    capture_start_tick=0,
                    capture_end_tick=5,
                ),
                source_revision="rev-1",
            ),
        )
    )
    reader = create_lineage_reader(tmp_path)
    budget = LineageReadBudget.for_query()
    async with reader.open_read(run_id=_RUN, budget=budget) as session:
        snapshot = await session.resolve_snapshot(_SCOPE)
        page = await LineageQueryService(reader).traverse(
            _query("a", snapshot=snapshot), session=session
        )
    assert page.visited_node_count == 2
    assert budget.physical_reads_charged >= 3
    assert budget.source_bytes_charged > 0


try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ImportError:  # pragma: no cover - hypothesis is a test dependency
    given = None  # type: ignore[assignment]


def _oracle_descendants(
    edges: Sequence[tuple[str, str]], root: str, max_depth: int, max_nodes: int
) -> set[str]:
    visited = {root}
    frontier = [root]
    for _depth in range(max_depth):
        next_frontier: list[str] = []
        for source in frontier:
            for edge_source, target in edges:
                if edge_source != source or target in visited:
                    continue
                if len(visited) >= max_nodes:
                    return visited
                visited.add(target)
                next_frontier.append(target)
        if not next_frontier:
            break
        frontier = next_frontier
    return visited


if given is not None:

    @given(
        edge_pairs=st.lists(
            st.tuples(
                st.sampled_from(("a", "b", "c", "d", "e")),
                st.sampled_from(("a", "b", "c", "d", "e")),
            ),
            unique=True,
            max_size=8,
        ),
        max_depth=st.integers(min_value=0, max_value=3),
    )
    @settings(max_examples=25, deadline=None)
    def test_hypothesis_traversal_matches_small_oracle(
        edge_pairs: list[tuple[str, str]],
        max_depth: int,
    ) -> None:
        import asyncio

        names = tuple(dict.fromkeys(name for pair in edge_pairs for name in pair))
        if not names:
            names = ("a",)
        nodes = tuple(_node(name) for name in names)
        edges = tuple(
            _edge(source, target, suffix=f"-{index}")
            for index, (source, target) in enumerate(edge_pairs)
            if source != target or source in names
        )
        session = _FakeSession(nodes, edges)
        service = LineageQueryService(_Reader(session))
        page = asyncio.run(
            service.traverse(
                _query(
                    names[0],
                    max_depth=max_depth,
                    max_nodes=5,
                    page_size=200,
                ),
                session=session,
            )
        )
        assert {node.ref.native_id for node in page.nodes} == _oracle_descendants(
            edge_pairs, names[0], max_depth, 5
        )
        keys = {node.key for node in page.nodes}
        assert len({edge.edge_key for edge in page.edges}) == len(page.edges)
        for edge in page.edges:
            assert edge.source_key in keys
            assert edge.target_key in keys
