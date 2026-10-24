"""Pure objective lineage projections over detached kinship and record evidence.

No engine mutation, observation call, admission or storage access occurs here.
Source policies stay in their owning modules; this adapter only normalizes
already-detached evidence into the closed lineage contracts.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

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
    LineageEdge,
    LineageError,
    LineageNode,
    LineageNodeState,
)
from simulation.lineage_ports import (
    AgentLifecycleFact,
    KinshipSourceEdge,
    LineageSourceProjection,
    RecordSourceArtifact,
    RecordSourceEvent,
)
from simulation.models import RunId
from world.artifacts import InformationArtifact, RecordIntegrity
from world.events import (
    ArtifactAnnotated,
    ArtifactCopied,
    ArtifactCreated,
    ArtifactDamaged,
    ArtifactDestroyed,
    ArtifactModified,
    ArtifactMoved,
    ArtifactPartiallyLost,
    WorldEvent,
)
from world.kinship import KinshipGraph
from world.models import LifeStatus

__all__ = [
    "extract_agent_lifecycle_facts",
    "extract_kinship_source_edges",
    "extract_record_source_artifacts",
    "extract_record_source_events",
    "project_genealogy_lineage",
    "project_record_lineage",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.lineage_objective")

_INITIAL_TICK: Final[int] = 0


def _is_in_boundary(*, observed_tick: int, boundary_tick: int) -> bool:
    if observed_tick < boundary_tick:
        return True
    return boundary_tick == _INITIAL_TICK and observed_tick == _INITIAL_TICK


def extract_kinship_source_edges(
    graph: KinshipGraph,
) -> tuple[KinshipSourceEdge, ...]:
    """Detach native parent->child facts without changing genealogy policy."""
    if type(graph) is not KinshipGraph:
        raise TypeError("extract_kinship_source_edges requires KinshipGraph")
    edges = tuple(
        KinshipSourceEdge(
            parent_id=edge.parent_agent_id.value,
            child_id=edge.child_agent_id.value,
            established_tick=edge.established_tick,
            edge_id=edge.edge_id,
        )
        for edge in sorted(
            graph.edges,
            key=lambda item: (
                item.established_tick,
                item.parent_agent_id.value,
                item.child_agent_id.value,
                item.edge_id,
            ),
        )
    )
    _LOG.debug(
        "lineage_kinship_source_extracted edge_count=%s",
        len(edges),
    )
    return edges


def extract_agent_lifecycle_facts(
    *,
    bodies: Sequence[tuple[str, str, LifeStatus]],
    lifecycle_entry_ticks: Mapping[str, int],
    observed_tick: int,
) -> tuple[AgentLifecycleFact, ...]:
    """Build typed lifecycle facts from detached body status and entry ticks."""
    facts: list[AgentLifecycleFact] = []
    for agent_id, body_id, life_status in bodies:
        if type(life_status) is not LifeStatus:
            raise ValueError("life status must be LifeStatus")
        entry_tick = lifecycle_entry_ticks.get(agent_id, 0)
        facts.append(
            AgentLifecycleFact(
                agent_id=agent_id,
                body_id=body_id,
                entry_tick=entry_tick,
                life_status=life_status.value,
                observed_tick=observed_tick,
            )
        )
    facts.sort(key=lambda item: (item.agent_id, item.body_id))
    _LOG.debug("lineage_lifecycle_source_extracted fact_count=%s", len(facts))
    return tuple(facts)


def project_genealogy_lineage(
    *,
    run_id: RunId,
    boundary_tick: int,
    source_edges: Sequence[KinshipSourceEdge],
    lifecycle_facts: Sequence[AgentLifecycleFact],
    coverage: LineageCoverage,
) -> LineageSourceProjection:
    """Project objective parent->child descent with boundary-valid living facts."""
    if type(run_id) is not RunId:
        raise ValueError("run_id must be RunId")
    if type(coverage) is not LineageCoverage:
        raise ValueError("coverage must be LineageCoverage")
    if boundary_tick < 0:
        raise ValueError("boundary tick must be non-negative")
    if coverage.state is LineageCoverageState.DISABLED:
        return LineageSourceProjection(nodes=(), edges=(), coverage=coverage)

    facts_by_agent: dict[str, AgentLifecycleFact] = {}
    for lifecycle_fact in lifecycle_facts:
        if type(lifecycle_fact) is not AgentLifecycleFact:
            raise ValueError("lifecycle_facts entries must be AgentLifecycleFact")
        if not _is_in_boundary(
            observed_tick=lifecycle_fact.entry_tick, boundary_tick=boundary_tick
        ):
            raise LineageError("snapshot_corrupt")
        if lifecycle_fact.observed_tick > boundary_tick:
            raise LineageError("snapshot_corrupt")
        if lifecycle_fact.agent_id in facts_by_agent:
            raise LineageError("snapshot_corrupt")
        facts_by_agent[lifecycle_fact.agent_id] = lifecycle_fact

    edges: list[LineageEdge] = []
    node_refs: dict[str, LineageNodeRef] = {}
    seen_edge_ids: dict[str, tuple[str, str]] = {}
    for source in source_edges:
        if type(source) is not KinshipSourceEdge:
            raise ValueError("source_edges entries must be KinshipSourceEdge")
        if not _is_in_boundary(
            observed_tick=source.established_tick, boundary_tick=boundary_tick
        ):
            raise LineageError("snapshot_corrupt")
        existing_edge = seen_edge_ids.get(source.edge_id)
        if existing_edge is not None and existing_edge != (
            source.parent_id,
            source.child_id,
        ):
            raise LineageError("snapshot_corrupt")
        seen_edge_ids[source.edge_id] = (source.parent_id, source.child_id)
        parent_ref = LineageNodeRef(
            run_id=run_id,
            family=LineageFamily.GENEALOGY,
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.AGENT,
            native_id=source.parent_id,
        )
        child_ref = LineageNodeRef(
            run_id=run_id,
            family=LineageFamily.GENEALOGY,
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.AGENT,
            native_id=source.child_id,
        )
        node_refs[parent_ref.key] = parent_ref
        node_refs[child_ref.key] = child_ref
        evidence = LineageEvidenceRef(
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.AGENT,
            native_id=source.edge_id,
            observed_tick=source.established_tick,
        )
        edge_key = lineage_edge_key(
            relation="parent_of",
            source_key=parent_ref.key,
            target_key=child_ref.key,
            native_kind=LineageNativeKind.AGENT,
            native_id=source.edge_id,
            evidence_keys=(evidence.key,),
        )
        edges.append(
            LineageEdge(
                edge_key=edge_key,
                source_key=parent_ref.key,
                target_key=child_ref.key,
                relation="parent_of",
                native_kind=LineageNativeKind.AGENT,
                native_id=source.edge_id,
                evidence_refs=(evidence,),
                observed_tick=source.established_tick,
                status_code="established",
            )
        )

    for agent_id in facts_by_agent:
        ref = LineageNodeRef(
            run_id=run_id,
            family=LineageFamily.GENEALOGY,
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.AGENT,
            native_id=agent_id,
        )
        node_refs.setdefault(ref.key, ref)

    nodes: list[LineageNode] = []
    for ref in sorted(node_refs.values(), key=lambda item: item.key):
        fact = facts_by_agent.get(ref.native_id)
        if fact is None:
            nodes.append(
                LineageNode(
                    ref=ref,
                    state=LineageNodeState.UNRESOLVED,
                    unresolved_reason="lifecycle_fact_missing",
                )
            )
            continue
        evidence = LineageEvidenceRef(
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.AGENT,
            native_id=fact.body_id,
            observed_tick=fact.observed_tick,
        )
        nodes.append(
            LineageNode(
                ref=ref,
                state=LineageNodeState.OBSERVED,
                living=fact.life_status == LifeStatus.ALIVE.value,
                observed_tick=fact.observed_tick,
                status_code=fact.life_status,
                evidence_refs=(evidence,),
                source_observed_boundary=boundary_tick,
            )
        )

    _LOG.debug(
        "lineage_genealogy_projected run_id=%s boundary=%s node_count=%s "
        "edge_count=%s coverage=%s",
        run_id.value,
        boundary_tick,
        len(nodes),
        len(edges),
        coverage.state.value,
    )
    return LineageSourceProjection(
        nodes=tuple(nodes),
        edges=tuple(edges),
        coverage=coverage,
    )


def extract_record_source_artifacts(
    artifacts: Sequence[InformationArtifact],
    *,
    observed_tick: int,
) -> tuple[RecordSourceArtifact, ...]:
    """Detach physical metadata only; marks and content never cross this boundary."""
    rows: list[RecordSourceArtifact] = []
    for artifact in artifacts:
        if type(artifact) is not InformationArtifact:
            raise TypeError("artifacts entries must be InformationArtifact")
        rows.append(
            RecordSourceArtifact(
                artifact_id=artifact.artifact_id.value,
                kind=artifact.kind.value,
                author_id=artifact.author_id.value,
                created_tick=artifact.created_tick,
                content_revision=artifact.content_revision,
                integrity=artifact.integrity.value,
                annotation_revisions=artifact.annotation_revisions,
                lost_mark_count=artifact.lost_mark_count,
                copy_generation=artifact.copy_generation,
                observed_tick=observed_tick,
                parent_artifact_id=(
                    artifact.parent_artifact_id.value
                    if artifact.parent_artifact_id is not None
                    else None
                ),
                source_artifact_id=(
                    artifact.source_artifact_id.value
                    if artifact.source_artifact_id is not None
                    else None
                ),
                custodian_repository_id=(
                    artifact.custodian_repository_id.value
                    if artifact.custodian_repository_id is not None
                    else None
                ),
            )
        )
    rows.sort(key=lambda item: item.artifact_id)
    _LOG.debug("lineage_record_source_extracted artifact_count=%s", len(rows))
    return tuple(rows)


def extract_record_source_events(
    events: Sequence[WorldEvent],
) -> tuple[RecordSourceEvent, ...]:
    """Detach typed physical record events without parsing free-form fields."""
    rows: list[RecordSourceEvent] = []
    for event in events:
        if type(event) is not WorldEvent:
            raise TypeError("events entries must be WorldEvent")
        details = event.details
        row: RecordSourceEvent | None = None
        if type(details) is ArtifactCopied:
            row = RecordSourceEvent(
                artifact_id=details.child_artifact_id.value,
                tick=event.tick,
                sequence=event.sequence,
                event_kind="artifact_copied",
                parent_artifact_id=details.parent_artifact_id.value,
                source_artifact_id=details.source_artifact_id.value,
            )
        elif type(details) is ArtifactDestroyed:
            row = RecordSourceEvent(
                artifact_id=details.artifact_id.value,
                tick=event.tick,
                sequence=event.sequence,
                event_kind="artifact_destroyed",
                integrity=details.integrity,
            )
        elif type(details) is ArtifactDamaged:
            row = RecordSourceEvent(
                artifact_id=details.artifact_id.value,
                tick=event.tick,
                sequence=event.sequence,
                event_kind="artifact_damaged",
                integrity=details.next_integrity,
                lost_mark_count_delta=details.lost_mark_count_delta,
            )
        elif type(details) is ArtifactPartiallyLost:
            row = RecordSourceEvent(
                artifact_id=details.artifact_id.value,
                tick=event.tick,
                sequence=event.sequence,
                event_kind="artifact_partially_lost",
                integrity=details.integrity,
            )
        elif type(details) is ArtifactAnnotated:
            row = RecordSourceEvent(
                artifact_id=details.artifact_id.value,
                tick=event.tick,
                sequence=event.sequence,
                event_kind="artifact_annotated",
                integrity=details.integrity,
                annotation_revisions=details.annotation_revisions,
            )
        elif type(details) is ArtifactCreated:
            row = RecordSourceEvent(
                artifact_id=details.artifact_id.value,
                tick=event.tick,
                sequence=event.sequence,
                event_kind="artifact_created",
            )
        elif type(details) is ArtifactModified:
            row = RecordSourceEvent(
                artifact_id=details.artifact_id.value,
                tick=event.tick,
                sequence=event.sequence,
                event_kind="artifact_modified",
            )
        elif type(details) is ArtifactMoved:
            row = RecordSourceEvent(
                artifact_id=details.artifact_id.value,
                tick=event.tick,
                sequence=event.sequence,
                event_kind="artifact_moved",
            )
        if row is not None:
            rows.append(row)
    rows.sort(key=lambda item: (item.tick, item.sequence, item.artifact_id))
    _LOG.debug("lineage_record_events_extracted event_count=%s", len(rows))
    return tuple(rows)


def _record_ref(run_id: RunId, artifact_id: str) -> LineageNodeRef:
    return LineageNodeRef(
        run_id=run_id,
        family=LineageFamily.RECORD,
        evidence_class=LineageEvidenceClass.OBJECTIVE,
        native_kind=LineageNativeKind.ARTIFACT,
        native_id=artifact_id,
    )


def project_record_lineage(
    *,
    run_id: RunId,
    boundary_tick: int,
    artifacts: Sequence[RecordSourceArtifact],
    events: Sequence[RecordSourceEvent],
    coverage: LineageCoverage,
) -> LineageSourceProjection:
    """Project physical copy ancestry and retention without meaning or truth."""
    if type(run_id) is not RunId:
        raise ValueError("run_id must be RunId")
    if type(coverage) is not LineageCoverage:
        raise ValueError("coverage must be LineageCoverage")
    if boundary_tick < 0:
        raise ValueError("boundary tick must be non-negative")
    if coverage.state is LineageCoverageState.DISABLED:
        return LineageSourceProjection(nodes=(), edges=(), coverage=coverage)

    artifacts_by_id: dict[str, RecordSourceArtifact] = {}
    for artifact in artifacts:
        if type(artifact) is not RecordSourceArtifact:
            raise ValueError("artifacts entries must be RecordSourceArtifact")
        if not _is_in_boundary(
            observed_tick=artifact.created_tick, boundary_tick=boundary_tick
        ):
            raise LineageError("snapshot_corrupt")
        if artifact.observed_tick > boundary_tick:
            raise LineageError("snapshot_corrupt")
        if artifact.artifact_id in artifacts_by_id:
            raise LineageError("snapshot_corrupt")
        artifacts_by_id[artifact.artifact_id] = artifact

    events_by_artifact: dict[str, list[RecordSourceEvent]] = {}
    for event in events:
        if type(event) is not RecordSourceEvent:
            raise ValueError("events entries must be RecordSourceEvent")
        if not _is_in_boundary(observed_tick=event.tick, boundary_tick=boundary_tick):
            raise LineageError("snapshot_corrupt")
        events_by_artifact.setdefault(event.artifact_id, []).append(event)

    node_refs: dict[str, LineageNodeRef] = {}
    nodes: dict[str, LineageNode] = {}
    for artifact_id, artifact in artifacts_by_id.items():
        ref = _record_ref(run_id, artifact_id)
        node_refs[ref.key] = ref
        event_rows = events_by_artifact.get(artifact_id, ())
        integrity = artifact.integrity
        state = LineageNodeState.OBSERVED
        observed_tick = artifact.observed_tick
        lost_mark_count = artifact.lost_mark_count
        annotation_revisions = artifact.annotation_revisions
        for event in event_rows:
            observed_tick = max(observed_tick, event.tick)
            lost_mark_count += event.lost_mark_count_delta
            annotation_revisions = max(annotation_revisions, event.annotation_revisions)
            if event.integrity is not None:
                integrity = event.integrity
            if event.event_kind == "artifact_destroyed":
                state = LineageNodeState.ARCHIVED
                integrity = event.integrity or "destroyed"
        if integrity == RecordIntegrity.DESTROYED.value:
            state = LineageNodeState.ARCHIVED
        evidence = LineageEvidenceRef(
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.ARTIFACT,
            native_id=artifact_id,
            observed_tick=observed_tick,
        )
        nodes[ref.key] = LineageNode(
            ref=ref,
            state=state,
            observed_tick=observed_tick,
            status_code=integrity,
            native_revision=str(artifact.content_revision),
            evidence_refs=(evidence,),
            counts=(
                ("annotation_revisions", annotation_revisions),
                ("lost_mark_count", lost_mark_count),
            ),
            source_observed_boundary=boundary_tick,
            custodian_repository_id=artifact.custodian_repository_id,
        )

    for artifact_id, event_rows in events_by_artifact.items():
        if artifact_id in artifacts_by_id:
            continue
        ref = _record_ref(run_id, artifact_id)
        node_refs[ref.key] = ref
        last_event = event_rows[-1]
        destroyed = any(
            event.event_kind == "artifact_destroyed" for event in event_rows
        )
        integrity = next(
            (
                event.integrity
                for event in reversed(event_rows)
                if event.integrity is not None
            ),
            "unknown",
        )
        if destroyed:
            integrity = "destroyed"
        evidence = LineageEvidenceRef(
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.ARTIFACT,
            native_id=artifact_id,
            observed_tick=last_event.tick,
        )
        nodes[ref.key] = LineageNode(
            ref=ref,
            state=(
                LineageNodeState.ARCHIVED if destroyed else LineageNodeState.OBSERVED
            ),
            observed_tick=last_event.tick,
            status_code=integrity,
            evidence_refs=(evidence,),
            counts=(
                ("annotation_revisions", 0),
                ("lost_mark_count", 0),
            ),
            source_observed_boundary=boundary_tick,
        )

    copy_links: dict[tuple[str, str], tuple[str, int, int | None]] = {}
    for artifact_id, artifact in artifacts_by_id.items():
        if artifact.parent_artifact_id is None or artifact.copy_generation < 1:
            continue
        copy_links[(artifact.parent_artifact_id, artifact_id)] = (
            artifact_id,
            artifact.copy_generation,
            artifact.observed_tick,
        )
    for event in events:
        if event.event_kind != "artifact_copied" or event.parent_artifact_id is None:
            continue
        copy_links.setdefault(
            (event.parent_artifact_id, event.artifact_id),
            (event.artifact_id, 0, event.tick),
        )

    edges: list[LineageEdge] = []
    for (parent_id, child_id), (native_id, _generation, link_tick) in sorted(
        copy_links.items()
    ):
        parent_ref = _record_ref(run_id, parent_id)
        child_ref = _record_ref(run_id, child_id)
        if parent_ref.key not in nodes:
            node_refs[parent_ref.key] = parent_ref
            nodes[parent_ref.key] = LineageNode(
                ref=parent_ref,
                state=LineageNodeState.UNRESOLVED,
                unresolved_reason="source_not_observed",
            )
        if child_ref.key not in nodes:
            node_refs[child_ref.key] = child_ref
            nodes[child_ref.key] = LineageNode(
                ref=child_ref,
                state=LineageNodeState.UNRESOLVED,
                unresolved_reason="copy_child_not_observed",
            )
        evidence = LineageEvidenceRef(
            evidence_class=LineageEvidenceClass.OBJECTIVE,
            native_kind=LineageNativeKind.RECORD_REVISION,
            native_id=native_id,
            observed_tick=link_tick,
        )
        edge_key = lineage_edge_key(
            relation="copied_from",
            source_key=parent_ref.key,
            target_key=child_ref.key,
            native_kind=LineageNativeKind.RECORD_REVISION,
            native_id=native_id,
            evidence_keys=(evidence.key,),
        )
        edges.append(
            LineageEdge(
                edge_key=edge_key,
                source_key=parent_ref.key,
                target_key=child_ref.key,
                relation="copied_from",
                native_kind=LineageNativeKind.RECORD_REVISION,
                native_id=native_id,
                evidence_refs=(evidence,),
                observed_tick=link_tick,
                status_code="physical_copy",
            )
        )

    _LOG.debug(
        "lineage_record_projected run_id=%s boundary=%s node_count=%s "
        "edge_count=%s coverage=%s",
        run_id.value,
        boundary_tick,
        len(nodes),
        len(edges),
        coverage.state.value,
    )
    return LineageSourceProjection(
        nodes=tuple(nodes[key] for key in sorted(nodes)),
        edges=tuple(edges),
        coverage=coverage,
    )
