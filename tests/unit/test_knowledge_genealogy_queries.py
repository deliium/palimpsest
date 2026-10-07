"""Analysis-only knowledge genealogy DAG queries."""

from __future__ import annotations

import logging
from types import SimpleNamespace

from analysis.knowledge_genealogy import (
    KnowledgeGenealogyEdgeKind,
    KnowledgeGenealogyQueryId,
    build_knowledge_genealogy_graph,
    query_independent_emergence_count,
    query_oldest_surviving_lineage_origin,
    query_who_currently_knows,
    query_who_taught,
    run_knowledge_genealogy_query,
)

_LOG = logging.getLogger("tests.knowledge_genealogy_queries")


def _audit(
    *,
    owner: str,
    entry_id: str,
    content_key: str = "tech:foraging",
    origin: str = "independent_discovery",
    parents: tuple[str, ...] = (),
    root: str | None = None,
    hop: int = 0,
    mutated: bool = False,
    acquired: int = 0,
    tick: int = 0,
    active: bool = True,
    source: str | None = None,
    teacher: str | None = None,
    kind: str = "foraging_method",
) -> SimpleNamespace:
    return SimpleNamespace(
        owner_id=owner,
        entry_id=entry_id,
        kind=kind,
        content_key=content_key,
        origin=origin,
        parent_entry_ids=parents,
        lineage_root_id=root or f"root:{owner}:foraging_method:{content_key}",
        hop_index=hop,
        mutated=mutated,
        acquired_tick=acquired,
        tick=tick,
        active=active,
        source_agent_id=source,
        teacher_agent_id=teacher,
        capability_anchor="foraging",
        reason_code="formed",
    )


def test_empty_audits_build_absent_friendly_graph() -> None:
    _LOG.debug("case_id=empty_graph")
    graph = build_knowledge_genealogy_graph((), as_of_tick=0)
    assert graph.nodes == ()
    assert graph.edges == ()
    assert graph.unresolved_transmission_count == 0
    assert graph.censoring_policy == "analysis_only_never_cognition"
    result = query_who_currently_knows(graph, content_key="tech:foraging")
    assert result.count == 0
    assert result.items == ()


def test_who_currently_knows_filters_dead_holders() -> None:
    audits = (
        _audit(owner="alice", entry_id="e1", acquired=1, tick=1),
        _audit(owner="bob", entry_id="e2", acquired=2, tick=2),
    )
    graph = build_knowledge_genealogy_graph(
        audits, as_of_tick=5, death_ticks={"alice": 3}
    )
    result = query_who_currently_knows(graph, content_key="tech:foraging")
    assert result.query_id is KnowledgeGenealogyQueryId.WHO_CURRENTLY_KNOWS
    assert [agent for _, agent in result.items] == ["bob"]


def test_who_taught_resolves_peer_transmission() -> None:
    audits = (
        _audit(owner="alice", entry_id="e-alice", acquired=1, tick=1),
        _audit(
            owner="bob",
            entry_id="e-bob",
            origin="teaching",
            hop=1,
            acquired=2,
            tick=2,
            source="alice",
            teacher="alice",
        ),
    )
    graph = build_knowledge_genealogy_graph(audits, as_of_tick=3)
    tx = [
        edge
        for edge in graph.edges
        if edge.kind is KnowledgeGenealogyEdgeKind.TRANSMITTED_FROM
        and "e-alice" in edge.edge_id
    ]
    assert tx
    result = query_who_taught(graph, content_key="tech:foraging", holder_agent_id="bob")
    assert "alice" in [agent for _, agent in result.items]


def test_unresolved_transmission_counted() -> None:
    audits = (
        _audit(
            owner="bob",
            entry_id="e-bob",
            origin="teaching",
            hop=1,
            acquired=2,
            tick=2,
            source="ghost",
            teacher="ghost",
        ),
    )
    graph = build_knowledge_genealogy_graph(audits, as_of_tick=3)
    assert graph.unresolved_transmission_count == 1
    kinds = {edge.kind for edge in graph.edges}
    assert KnowledgeGenealogyEdgeKind.UNRESOLVED_TRANSMISSION in kinds


def test_dual_independent_emergence() -> None:
    audits = (
        _audit(owner="alice", entry_id="e1", acquired=1, tick=1),
        _audit(owner="carol", entry_id="e2", acquired=2, tick=2),
    )
    graph = build_knowledge_genealogy_graph(audits, as_of_tick=4)
    result = query_independent_emergence_count(graph, content_key="tech:foraging")
    assert result.count == 2
    assert result.emerged_independently_twice is True


def test_oldest_surviving_lineage_origin() -> None:
    audits = (
        _audit(
            owner="alice",
            entry_id="e1",
            acquired=1,
            tick=1,
            root="root:alice:foraging_method:tech:foraging",
        ),
        _audit(
            owner="bob",
            entry_id="e2",
            origin="teaching",
            hop=1,
            acquired=3,
            tick=3,
            source="alice",
            teacher="alice",
            root="root:alice:foraging_method:tech:foraging",
        ),
        _audit(
            owner="carol",
            entry_id="e3",
            acquired=5,
            tick=5,
            root="root:carol:foraging_method:tech:foraging",
        ),
    )
    graph = build_knowledge_genealogy_graph(
        audits, as_of_tick=10, death_ticks={"carol": 6}
    )
    result = query_oldest_surviving_lineage_origin(
        graph, content_key="tech:foraging"
    )
    assert result.count == 1
    assert result.items[0][1] == "root:alice:foraging_method:tech:foraging"
    assert result.items[0][0] == 1


def test_run_dispatcher_covers_all_query_ids() -> None:
    audits = (_audit(owner="alice", entry_id="e1"),)
    graph = build_knowledge_genealogy_graph(audits, as_of_tick=1)
    for query_id in KnowledgeGenealogyQueryId:
        result = run_knowledge_genealogy_query(
            graph, query_id, content_key="tech:foraging"
        )
        assert result.query_id is query_id


def test_combined_from_edges_for_multi_parent() -> None:
    audits = (
        _audit(owner="bob", entry_id="p1", acquired=1, tick=1),
        _audit(
            owner="bob",
            entry_id="p2",
            content_key="tech:healing",
            kind="healing_technique",
            acquired=1,
            tick=1,
            root="root:bob:healing_technique:tech:healing",
        ),
        _audit(
            owner="bob",
            entry_id="combo",
            content_key="tech:combo",
            origin="combination",
            parents=("p1", "p2"),
            hop=2,
            acquired=2,
            tick=2,
            root="root:bob:foraging_method:tech:foraging",
        ),
    )
    graph = build_knowledge_genealogy_graph(audits, as_of_tick=3)
    combined = [
        edge
        for edge in graph.edges
        if edge.kind is KnowledgeGenealogyEdgeKind.COMBINED_FROM
    ]
    assert len(combined) == 2
