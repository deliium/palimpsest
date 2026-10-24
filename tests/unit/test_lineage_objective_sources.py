"""Objective genealogy and physical-record lineage projections."""

from __future__ import annotations

import dataclasses

import pytest

from agents.models import AgentId
from simulation.lineage_models import (
    LineageCoverage,
    LineageCoverageState,
    LineageError,
)
from simulation.lineage_objective import (
    extract_agent_lifecycle_facts,
    extract_kinship_source_edges,
    extract_record_source_artifacts,
    extract_record_source_events,
    project_genealogy_lineage,
    project_record_lineage,
)
from simulation.lineage_ports import (
    AgentLifecycleFact,
    KinshipSourceEdge,
    RecordSourceEvent,
)
from simulation.models import RunId
from world import ActionCause
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    InformationArtifact,
    RecordIntegrity,
)
from world.events import (
    EVENT_SCHEMA_REPLAY_V13,
    ArtifactCopied,
    ArtifactDestroyed,
    OccurrenceContext,
    WorldEvent,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.kinship import (
    KinshipGraph,
    descendants_of,
    parents_of,
    stable_kinship_edge_id,
)
from world.models import LifeStatus

_RUN = RunId("run-lineage")
_BOUNDARY = 5


def _coverage(
    state: LineageCoverageState = LineageCoverageState.COMPLETE,
) -> LineageCoverage:
    return LineageCoverage(
        state=state, capture_start_tick=0, capture_end_tick=_BOUNDARY
    )


def _edge(parent: str, child: str, tick: int) -> KinshipSourceEdge:
    return KinshipSourceEdge(
        parent_id=parent,
        child_id=child,
        established_tick=tick,
        edge_id=stable_kinship_edge_id(
            parent_agent_id=AgentId(parent),
            child_agent_id=AgentId(child),
            established_tick=tick,
        ),
    )


def _fact(
    agent: str, status: LifeStatus, *, entry_tick: int = 0, observed: int = _BOUNDARY
) -> AgentLifecycleFact:
    return extract_agent_lifecycle_facts(
        bodies=((agent, f"body-{agent}", status),),
        lifecycle_entry_ticks={agent: entry_tick},
        observed_tick=observed,
    )[0]


def _artifact(
    artifact_id: str,
    *,
    parent: str | None = None,
    generation: int = 0,
    integrity: RecordIntegrity = RecordIntegrity.INTACT,
    created_tick: int = 0,
    lost_mark_count: int = 0,
    annotation_revisions: int = 0,
) -> InformationArtifact:
    return InformationArtifact(
        artifact_id=EntityId(artifact_id),
        kind=ArtifactKind.RECORD,
        author_id=EntityId("body-1"),
        created_tick=created_tick,
        content=ArtifactContent(marks=("private_mark",)),
        location_id=EntityId("loc-1"),
        parent_artifact_id=EntityId(parent) if parent is not None else None,
        source_artifact_id=EntityId(parent) if parent is not None else None,
        copy_generation=generation,
        integrity=integrity,
        annotation_revisions=annotation_revisions,
        lost_mark_count=lost_mark_count,
    )


def _graph(edges: tuple[KinshipSourceEdge, ...]) -> KinshipGraph:
    from world.kinship import KinshipEdge

    return KinshipGraph(
        edges=tuple(
            KinshipEdge(
                parent_agent_id=AgentId(edge.parent_id),
                child_agent_id=AgentId(edge.child_id),
                established_tick=edge.established_tick,
                edge_id=edge.edge_id,
            )
            for edge in edges
        )
    )


def test_two_parent_dag_agrees_with_native_queries() -> None:
    edges = (_edge("p1", "c", 0), _edge("p2", "c", 0), _edge("c", "g", 1))
    graph = _graph(edges)
    assert parents_of(graph, AgentId("c")) == (AgentId("p1"), AgentId("p2"))
    assert descendants_of(graph, AgentId("p1"), max_depth=8, config_max_depth=8) == (
        AgentId("c"),
        AgentId("g"),
    )
    facts = tuple(_fact(agent, LifeStatus.ALIVE) for agent in ("p1", "p2", "c", "g"))
    projection = project_genealogy_lineage(
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
        source_edges=extract_kinship_source_edges(graph),
        lifecycle_facts=facts,
        coverage=_coverage(),
    )
    assert len(projection.nodes) == 4
    assert len(projection.edges) == 3
    projected_pairs = {
        (
            next(
                node.ref.native_id
                for node in projection.nodes
                if node.key == edge.source_key
            ),
            next(
                node.ref.native_id
                for node in projection.nodes
                if node.key == edge.target_key
            ),
        )
        for edge in projection.edges
    }
    assert projected_pairs == {
        ("p1", "c"),
        ("p2", "c"),
        ("c", "g"),
    }
    assert all(edge.relation == "parent_of" for edge in projection.edges)
    assert all(node.living is True for node in projection.nodes)


def test_dead_intermediate_parent_keeps_living_grandchild_reachable() -> None:
    graph = _graph((_edge("p", "c", 0), _edge("c", "g", 0)))
    facts = (
        _fact("p", LifeStatus.DEAD),
        _fact("c", LifeStatus.DEAD),
        _fact("g", LifeStatus.ALIVE),
    )
    projection = project_genealogy_lineage(
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
        source_edges=extract_kinship_source_edges(graph),
        lifecycle_facts=facts,
        coverage=_coverage(),
    )
    by_id = {node.ref.native_id: node for node in projection.nodes}
    assert by_id["p"].living is False
    assert by_id["c"].living is False
    assert by_id["g"].living is True
    assert len(projection.edges) == 2


def test_future_birth_and_edge_fail_publication() -> None:
    with pytest.raises(LineageError, match="snapshot_corrupt"):
        project_genealogy_lineage(
            run_id=_RUN,
            boundary_tick=4,
            source_edges=(),
            lifecycle_facts=(_fact("newborn", LifeStatus.ALIVE, entry_tick=5),),
            coverage=_coverage(),
        )
    with pytest.raises(LineageError, match="snapshot_corrupt"):
        project_genealogy_lineage(
            run_id=_RUN,
            boundary_tick=4,
            source_edges=(_edge("p", "c", 5),),
            lifecycle_facts=(),
            coverage=_coverage(),
        )


def test_initial_boundary_zero_includes_bootstrap_edges_and_facts() -> None:
    graph = _graph((_edge("p", "c", 0),))
    projection = project_genealogy_lineage(
        run_id=_RUN,
        boundary_tick=0,
        source_edges=extract_kinship_source_edges(graph),
        lifecycle_facts=(
            _fact("p", LifeStatus.ALIVE, entry_tick=0, observed=0),
            _fact("c", LifeStatus.ALIVE, entry_tick=0, observed=0),
        ),
        coverage=_coverage(),
    )
    assert len(projection.edges) == 1
    assert len(projection.nodes) == 2


def test_disabled_channel_differs_from_enabled_empty_graph() -> None:
    disabled = project_genealogy_lineage(
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
        source_edges=(),
        lifecycle_facts=(),
        coverage=_coverage(LineageCoverageState.DISABLED),
    )
    enabled_empty = project_genealogy_lineage(
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
        source_edges=(),
        lifecycle_facts=(),
        coverage=_coverage(),
    )
    assert disabled.coverage.state is LineageCoverageState.DISABLED
    assert disabled.nodes == ()
    assert enabled_empty.coverage.state is LineageCoverageState.COMPLETE
    assert enabled_empty.nodes == ()


def test_record_copy_chain_and_branch_preserve_physical_ancestry() -> None:
    artifacts = (
        _artifact("root"),
        _artifact(
            "copy-1", parent="root", generation=1, integrity=RecordIntegrity.DAMAGED
        ),
        _artifact("copy-2", parent="copy-1", generation=2),
        _artifact("copy-3", parent="root", generation=1),
    )
    projection = project_record_lineage(
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
        artifacts=extract_record_source_artifacts(artifacts, observed_tick=_BOUNDARY),
        events=(),
        coverage=_coverage(),
    )
    by_id = {node.ref.native_id: node for node in projection.nodes}
    by_key = {node.key: node for node in projection.nodes}
    assert by_id["copy-1"].status_code == "damaged"
    assert len(projection.nodes) == 4
    assert len(projection.edges) == 3
    assert all(edge.relation == "copied_from" for edge in projection.edges)
    pairs = {
        (
            by_key[edge.source_key].ref.native_id,
            by_key[edge.target_key].ref.native_id,
        )
        for edge in projection.edges
    }
    assert pairs == {("root", "copy-1"), ("copy-1", "copy-2"), ("root", "copy-3")}


def test_destroyed_ancestor_and_missing_source_are_retained_honestly() -> None:
    artifacts = (
        _artifact("destroyed-root", integrity=RecordIntegrity.DESTROYED),
        _artifact("orphan-copy", parent="never-observed", generation=1),
    )
    projection = project_record_lineage(
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
        artifacts=extract_record_source_artifacts(artifacts, observed_tick=_BOUNDARY),
        events=(),
        coverage=_coverage(),
    )
    by_id = {node.ref.native_id: node for node in projection.nodes}
    assert by_id["destroyed-root"].state.value == "archived"
    assert by_id["never-observed"].state.value == "unresolved"
    assert by_id["never-observed"].unresolved_reason == "source_not_observed"
    assert len(projection.edges) == 1


def test_event_only_destruction_retains_tombstone_without_marks() -> None:
    artifacts = (_artifact("art-1", created_tick=1),)
    event = RecordSourceEvent(
        artifact_id="art-1",
        tick=3,
        sequence=1,
        event_kind="artifact_destroyed",
        integrity="destroyed",
    )
    projection = project_record_lineage(
        run_id=_RUN,
        boundary_tick=_BOUNDARY,
        artifacts=extract_record_source_artifacts(artifacts, observed_tick=_BOUNDARY),
        events=(event,),
        coverage=_coverage(),
    )
    node = projection.nodes[0]
    assert node.state.value == "archived"
    assert node.status_code == "destroyed"
    assert node.observed_tick == 5
    assert "private_mark" not in repr(node)


def test_future_record_event_fails_publication() -> None:
    with pytest.raises(LineageError, match="snapshot_corrupt"):
        project_record_lineage(
            run_id=_RUN,
            boundary_tick=2,
            artifacts=(),
            events=(
                RecordSourceEvent(
                    artifact_id="art-1",
                    tick=2,
                    sequence=0,
                    event_kind="artifact_modified",
                ),
            ),
            coverage=_coverage(),
        )


def test_real_artifact_and_event_extractors_drop_content() -> None:
    artifact = _artifact(
        "art-1",
        created_tick=2,
        annotation_revisions=2,
        lost_mark_count=1,
    )
    rows = extract_record_source_artifacts((artifact,), observed_tick=5)
    assert len(rows) == 1
    assert rows[0].annotation_revisions == 2
    assert rows[0].lost_mark_count == 1
    field_names = {field.name for field in dataclasses.fields(rows[0])}
    assert "content" not in field_names
    assert "marks" not in field_names

    request = RequestId("request-1")
    event = WorldEvent(
        event_id=EventId("event-1"),
        run_id=_RUN.value,
        world_id=WorldId("world-1"),
        tick=3,
        sequence=0,
        request_id=request,
        resulting_revision=WorldRevision(1),
        schema_version=EVENT_SCHEMA_REPLAY_V13,
        details=ArtifactCopied(
            child_artifact_id=EntityId("child"),
            parent_artifact_id=EntityId("parent"),
            source_artifact_id=EntityId("root"),
            fidelity_mode="lossy",
            copy_generation=1,
            content_revision=0,
            record_genre="story",
        ),
        actor_id=EntityId("body-1"),
        target_id=EntityId("child"),
        cause=ActionCause(request, EntityId("body-1")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )
    destroy_request = RequestId("request-2")
    destroyed = WorldEvent(
        event_id=EventId("event-2"),
        run_id=_RUN.value,
        world_id=WorldId("world-1"),
        tick=4,
        sequence=1,
        request_id=destroy_request,
        resulting_revision=WorldRevision(2),
        schema_version=EVENT_SCHEMA_REPLAY_V13,
        details=ArtifactDestroyed(
            artifact_id=EntityId("parent"),
            artifact_kind=ArtifactKind.RECORD,
            content_revision=1,
            tombstone=True,
        ),
        actor_id=EntityId("body-1"),
        target_id=EntityId("parent"),
        cause=ActionCause(destroy_request, EntityId("body-1")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )
    extracted = extract_record_source_events((event, destroyed))
    assert [row.event_kind for row in extracted] == [
        "artifact_copied",
        "artifact_destroyed",
    ]
    assert extracted[0].parent_artifact_id == "parent"
    assert extracted[1].integrity == "destroyed"


def test_lifecycle_extractor_keeps_entry_ticks_and_observed_boundary() -> None:
    facts = extract_agent_lifecycle_facts(
        bodies=(("a", "body-a", LifeStatus.ALIVE), ("b", "body-b", LifeStatus.DEAD)),
        lifecycle_entry_ticks={"a": 1, "b": 2},
        observed_tick=5,
    )
    assert [(fact.agent_id, fact.entry_tick) for fact in facts] == [("a", 1), ("b", 2)]
    assert all(fact.observed_tick == 5 for fact in facts)
