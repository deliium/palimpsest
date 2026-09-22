"""Read-only SQLAlchemy loader for experiment memory-drift analysis.

SELECT-only. Experiment membership is optional: when ``experiment_id`` is
provided, fail closed if membership is missing; when omitted, load by run/owner
only. Optional ``EvidenceManifest`` clamps sources under repeatable-read
semantics in one session. Does not import analysis types; callers map the
snapshot into analysis evidence sources via ``experiments.composition``. Never
logs event details, memory content, narratives, or SQL parameters.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Final, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from experiments.persistence import (
    PersistedAnalysisSnapshot,
    PersistedDerivationEdge,
    PersistedReconstructionRow,
)
from infrastructure.database import session_scope
from memory.models import (
    AgentId,
    ConceptMention,
    EntityId,
    EntityMention,
    EventId,
    MemoryEmbedding,
    MemoryId,
    MemoryLineage,
    MemoryProvenance,
    MemoryRelation,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    ReconstructionId,
    RelationEndpoint,
    RelationEndpointKind,
    WorldRevision,
)
from persistence.errors import PersistenceAdapterError, PersistenceNotFoundError
from persistence.memory_orm import (
    MemoryConceptOrm,
    MemoryDerivationSourceOrm,
    MemoryEntityMentionOrm,
    MemoryReconstructionOrm,
    MemoryReconstructionSourceOrm,
    MemoryRelationOrm,
    MemoryTraceOrm,
)
from persistence.orm import (
    ExperimentAssignmentOrm,
    ExperimentRunOrm,
    SimulationRunOrm,
    WorldEventOrm,
)
from persistence.readers import event_from_orm
from persistence.transmission_mapping import transmission_from_row
from simulation.evidence import (
    EvidenceManifest,
    clamp_sequence_to_high_water,
    manifest_hash_prefix,
)
from simulation.models import RunId

__all__ = [
    "PersistedAnalysisSnapshot",
    "PersistedDerivationEdge",
    "PersistedReconstructionRow",
    "SqlAlchemyAnalysisEvidenceLoader",
    "create_analysis_evidence_loader",
]

_LOG: Final[logging.Logger] = logging.getLogger("persistence.analysis_sqlalchemy")


class SqlAlchemyAnalysisEvidenceLoader:
    """Async read-only loader for run/owner scope; experiment membership optional."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def load(
        self,
        *,
        run_id: str,
        owner_id: str,
        experiment_id: str | None = None,
        manifest: EvidenceManifest | None = None,
    ) -> PersistedAnalysisSnapshot:
        run_id = RunId(run_id).value
        owner_id = AgentId(owner_id).value
        if experiment_id is not None:
            from simulation.persistence import ExperimentId

            experiment_id = ExperimentId(experiment_id).value
        if manifest is not None:
            if type(manifest) is not EvidenceManifest:
                raise TypeError("manifest must be EvidenceManifest")
            if manifest.run_id != run_id:
                _LOG.error(
                    "analysis_evidence_manifest_scope_mismatch",
                    extra={
                        "operation": "load",
                        "run_id": run_id,
                        "reason_code": "manifest_run_scope_mismatch",
                    },
                )
                raise PersistenceAdapterError(
                    "manifest_run_scope_mismatch", operation="load"
                )
        started = time.perf_counter()
        _LOG.debug(
            "analysis_evidence_load_start",
            extra={
                "operation": "load",
                "experiment_id": experiment_id,
                "run_id": run_id,
                "owner_id": owner_id,
                "has_manifest": manifest is not None,
                "manifest_hash_prefix": (
                    None if manifest is None else manifest_hash_prefix(manifest)
                ),
            },
        )
        async with session_scope(self._session_factory) as session:
            run_row = await session.get(SimulationRunOrm, run_id)
            if run_row is None:
                _LOG.error(
                    "analysis_evidence_run_missing",
                    extra={
                        "operation": "load",
                        "run_id": run_id,
                        "reason_code": "run_not_found",
                    },
                )
                raise PersistenceNotFoundError("run_not_found", operation="load")

            if experiment_id is not None:
                membership = await _has_canonical_membership(
                    session, experiment_id=experiment_id, run_id=run_id
                )
                if not membership:
                    _LOG.error(
                        "analysis_evidence_membership_missing",
                        extra={
                            "operation": "load",
                            "experiment_id": experiment_id,
                            "run_id": run_id,
                            "reason_code": "experiment_membership_not_found",
                        },
                    )
                    raise PersistenceNotFoundError(
                        "experiment_membership_not_found", operation="load"
                    )

            traces = await _load_traces(session, run_id=run_id, owner_id=owner_id)
            reconstructions = await _load_reconstructions(
                session, run_id=run_id, owner_id=owner_id
            )
            edges = await _load_derivation_edges(
                session, run_id=run_id, owner_id=owner_id
            )
            events = await _load_events(session, run_id=run_id)

            if manifest is not None:
                traces, reconstructions, edges = _clamp_to_manifest(
                    traces=traces,
                    reconstructions=reconstructions,
                    edges=edges,
                    manifest=manifest,
                )

        snapshot = PersistedAnalysisSnapshot(
            experiment_id=experiment_id or "",
            run_id=run_id,
            owner_id=owner_id,
            traces=traces,
            reconstructions=reconstructions,
            derivation_edges=edges,
            events=events,
        )
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        _LOG.debug(
            "analysis_evidence_load_complete",
            extra={
                "operation": "load",
                "experiment_id": experiment_id,
                "run_id": run_id,
                "owner_id": owner_id,
                "trace_count": len(traces),
                "reconstruction_count": len(reconstructions),
                "edge_count": len(edges),
                "event_count": len(events),
                "availability": "available",
                "duration_ms": duration_ms,
            },
        )
        _LOG.info(
            "analysis_evidence_loaded",
            extra={
                "operation": "load",
                "experiment_id": experiment_id,
                "run_id": run_id,
                "owner_id": owner_id,
                "trace_count": len(traces),
                "event_count": len(events),
            },
        )
        return snapshot


def _clamp_to_manifest(
    *,
    traces: tuple[MemoryTrace, ...],
    reconstructions: tuple[PersistedReconstructionRow, ...],
    edges: tuple[PersistedDerivationEdge, ...],
    manifest: EvidenceManifest,
) -> tuple[
    tuple[MemoryTrace, ...],
    tuple[PersistedReconstructionRow, ...],
    tuple[PersistedDerivationEdge, ...],
]:
    marks = manifest.high_water
    direct = tuple(
        trace
        for trace in traces
        if trace.provenance.kind is MemorySourceKind.DIRECT_OBSERVATION
    )
    communicated = tuple(
        trace
        for trace in traces
        if trace.provenance.kind is MemorySourceKind.COMMUNICATED
    )
    unknown = tuple(
        trace
        for trace in traces
        if trace.provenance.kind
        not in {
            MemorySourceKind.DIRECT_OBSERVATION,
            MemorySourceKind.COMMUNICATED,
        }
    )
    if unknown:
        _LOG.warning(
            "analysis_evidence_legacy_trace_kind",
            extra={
                "operation": "_clamp_to_manifest",
                "reason_code": "legacy_or_unknown_trace_kind",
                "run_id": manifest.run_id,
                "unknown_count": len(unknown),
            },
        )
    clamped_direct = clamp_sequence_to_high_water(
        direct, marks.direct_memories, source_label="direct_memories"
    )
    clamped_communicated = clamp_sequence_to_high_water(
        communicated,
        marks.communicated_memories,
        source_label="communicated_memories",
    )
    clamped_traces = clamped_direct + clamped_communicated
    clamped_reconstructions = clamp_sequence_to_high_water(
        reconstructions, marks.reconstructions, source_label="reconstructions"
    )
    kept_memory_ids = {trace.memory_id.value for trace in clamped_traces}
    kept_reconstruction_ids = {
        row.reconstruction_id for row in clamped_reconstructions
    }
    filtered_edges = tuple(
        edge
        for edge in edges
        if edge.derived_memory_id in kept_memory_ids
        or (
            edge.reconstruction_id is not None
            and edge.reconstruction_id in kept_reconstruction_ids
        )
    )
    return clamped_traces, clamped_reconstructions, filtered_edges


async def _has_canonical_membership(
    session: AsyncSession, *, experiment_id: str, run_id: str
) -> bool:
    """True when assignment or legacy experiment_runs membership exists."""
    assignment = (
        await session.execute(
            select(ExperimentAssignmentOrm)
            .where(
                ExperimentAssignmentOrm.experiment_id == experiment_id,
                ExperimentAssignmentOrm.run_id == run_id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if assignment is not None:
        return True
    legacy = await session.get(ExperimentRunOrm, (experiment_id, run_id))
    return legacy is not None


def create_analysis_evidence_loader(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> SqlAlchemyAnalysisEvidenceLoader:
    """Build a read-only analysis evidence loader."""
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_analysis_evidence_loader"
        )
    return SqlAlchemyAnalysisEvidenceLoader(session_factory)


async def _load_events(session: AsyncSession, *, run_id: str) -> tuple[object, ...]:
    rows = list(
        (
            await session.execute(
                select(WorldEventOrm)
                .where(WorldEventOrm.run_id == run_id)
                .order_by(WorldEventOrm.tick, WorldEventOrm.sequence)
            )
        )
        .scalars()
        .all()
    )
    return tuple(event_from_orm(row) for row in rows)


async def _load_derivation_edges(
    session: AsyncSession, *, run_id: str, owner_id: str
) -> tuple[PersistedDerivationEdge, ...]:
    rows = list(
        (
            await session.execute(
                select(MemoryDerivationSourceOrm)
                .where(
                    MemoryDerivationSourceOrm.run_id == run_id,
                    MemoryDerivationSourceOrm.owner_id == owner_id,
                )
                .order_by(
                    MemoryDerivationSourceOrm.derived_memory_id,
                    MemoryDerivationSourceOrm.ordinal,
                )
            )
        )
        .scalars()
        .all()
    )
    return tuple(
        PersistedDerivationEdge(
            derived_memory_id=row.derived_memory_id,
            source_memory_id=row.source_memory_id,
            ordinal=int(row.ordinal),
            reconstruction_id=row.reconstruction_id,
        )
        for row in rows
    )


async def _load_reconstructions(
    session: AsyncSession, *, run_id: str, owner_id: str
) -> tuple[PersistedReconstructionRow, ...]:
    rows = list(
        (
            await session.execute(
                select(MemoryReconstructionOrm)
                .where(
                    MemoryReconstructionOrm.run_id == run_id,
                    MemoryReconstructionOrm.owner_id == owner_id,
                )
                .order_by(
                    MemoryReconstructionOrm.created_tick,
                    MemoryReconstructionOrm.reconstruction_id,
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return ()
    reconstruction_ids = [row.reconstruction_id for row in rows]
    source_rows = list(
        (
            await session.execute(
                select(MemoryReconstructionSourceOrm)
                .where(
                    MemoryReconstructionSourceOrm.run_id == run_id,
                    MemoryReconstructionSourceOrm.owner_id == owner_id,
                    MemoryReconstructionSourceOrm.reconstruction_id.in_(
                        reconstruction_ids
                    ),
                )
                .order_by(
                    MemoryReconstructionSourceOrm.reconstruction_id,
                    MemoryReconstructionSourceOrm.ordinal,
                )
            )
        )
        .scalars()
        .all()
    )
    sources_by: dict[str, list[str]] = {item: [] for item in reconstruction_ids}
    for source in source_rows:
        sources_by[source.reconstruction_id].append(source.source_memory_id)
    return tuple(
        PersistedReconstructionRow(
            reconstruction_id=row.reconstruction_id,
            source_memory_ids=tuple(sources_by[row.reconstruction_id]),
            created_tick=int(row.created_tick),
            generation=int(row.generation),
            policy_id=row.policy_id,
            policy_version=row.policy_version,
            used_provider=bool(row.used_provider),
            fallback_used=bool(row.fallback_used),
            prompt_version=row.prompt_version,
            schema_version=row.schema_version,
            payload_sha256=row.payload_sha256,
        )
        for row in rows
    )


async def _load_traces(
    session: AsyncSession, *, run_id: str, owner_id: str
) -> tuple[MemoryTrace, ...]:
    rows = list(
        (
            await session.execute(
                select(MemoryTraceOrm)
                .where(
                    MemoryTraceOrm.run_id == run_id,
                    MemoryTraceOrm.owner_id == owner_id,
                )
                .order_by(MemoryTraceOrm.created_tick, MemoryTraceOrm.memory_id)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return ()
    return await _assemble_traces(session, rows, run_id=run_id, owner_id=owner_id)


async def _assemble_traces(
    session: AsyncSession,
    rows: Sequence[MemoryTraceOrm],
    *,
    run_id: str,
    owner_id: str,
) -> tuple[MemoryTrace, ...]:
    memory_ids = [row.memory_id for row in rows]
    concepts = list(
        (
            await session.execute(
                select(MemoryConceptOrm)
                .where(
                    MemoryConceptOrm.run_id == run_id,
                    MemoryConceptOrm.owner_id == owner_id,
                    MemoryConceptOrm.memory_id.in_(memory_ids),
                )
                .order_by(MemoryConceptOrm.memory_id, MemoryConceptOrm.ordinal)
            )
        )
        .scalars()
        .all()
    )
    entities = list(
        (
            await session.execute(
                select(MemoryEntityMentionOrm)
                .where(
                    MemoryEntityMentionOrm.run_id == run_id,
                    MemoryEntityMentionOrm.owner_id == owner_id,
                    MemoryEntityMentionOrm.memory_id.in_(memory_ids),
                )
                .order_by(
                    MemoryEntityMentionOrm.memory_id, MemoryEntityMentionOrm.ordinal
                )
            )
        )
        .scalars()
        .all()
    )
    relations = list(
        (
            await session.execute(
                select(MemoryRelationOrm)
                .where(
                    MemoryRelationOrm.run_id == run_id,
                    MemoryRelationOrm.owner_id == owner_id,
                    MemoryRelationOrm.memory_id.in_(memory_ids),
                )
                .order_by(MemoryRelationOrm.memory_id, MemoryRelationOrm.ordinal)
            )
        )
        .scalars()
        .all()
    )
    concepts_by: dict[str, list[ConceptMention]] = {mid: [] for mid in memory_ids}
    for concept_row in concepts:
        concepts_by[concept_row.memory_id].append(
            ConceptMention(
                mention_id=MentionId(concept_row.mention_id),
                concept=concept_row.concept,
            )
        )
    entities_by: dict[str, list[EntityMention]] = {mid: [] for mid in memory_ids}
    for entity_row in entities:
        entities_by[entity_row.memory_id].append(
            EntityMention(
                mention_id=MentionId(entity_row.mention_id),
                label=entity_row.label,
                entity_id=(
                    None
                    if entity_row.entity_id is None
                    else EntityId(entity_row.entity_id)
                ),
            )
        )
    relations_by: dict[str, list[MemoryRelation]] = {mid: [] for mid in memory_ids}
    for relation_row in relations:
        relations_by[relation_row.memory_id].append(
            MemoryRelation(
                relation_id=MentionId(relation_row.relation_id),
                predicate=relation_row.predicate,
                subject=RelationEndpoint(
                    kind=RelationEndpointKind(relation_row.subject_kind),
                    mention_id=MentionId(relation_row.subject_mention_id),
                ),
                object=RelationEndpoint(
                    kind=RelationEndpointKind(relation_row.object_kind),
                    mention_id=MentionId(relation_row.object_mention_id),
                ),
            )
        )
    derivation_rows = list(
        (
            await session.execute(
                select(MemoryDerivationSourceOrm)
                .where(
                    MemoryDerivationSourceOrm.run_id == run_id,
                    MemoryDerivationSourceOrm.owner_id == owner_id,
                    MemoryDerivationSourceOrm.derived_memory_id.in_(memory_ids),
                )
                .order_by(
                    MemoryDerivationSourceOrm.derived_memory_id,
                    MemoryDerivationSourceOrm.ordinal,
                )
            )
        )
        .scalars()
        .all()
    )
    sources_by: dict[str, list[MemoryId]] = {mid: [] for mid in memory_ids}
    reconstruction_by: dict[str, ReconstructionId | None] = {
        mid: None for mid in memory_ids
    }
    for edge in derivation_rows:
        sources_by[edge.derived_memory_id].append(MemoryId(edge.source_memory_id))
        if edge.reconstruction_id is not None:
            reconstruction_by[edge.derived_memory_id] = ReconstructionId(
                edge.reconstruction_id
            )

    assembled: list[MemoryTrace] = []
    for row in rows:
        embedding = None
        if row.embedding is not None:
            raw_embedding = cast(Sequence[float], row.embedding)
            vector = tuple(float(v) for v in raw_embedding)
            embedding = MemoryEmbedding(
                vector=vector,
                model=row.embedding_model or "",
                version=row.embedding_version or "",
            )
        source_memory_ids = tuple(sources_by[row.memory_id])
        reconstruction_id = reconstruction_by[row.memory_id]
        assembled.append(
            MemoryTrace(
                memory_id=MemoryId(row.memory_id),
                owner_id=AgentId(row.owner_id),
                world_revision=WorldRevision(int(row.world_revision)),
                concepts=tuple(concepts_by[row.memory_id]),
                entities=tuple(entities_by[row.memory_id]),
                relations=tuple(relations_by[row.memory_id]),
                context=MemorySituationContext(
                    location_id=(
                        None if row.location_id is None else EntityId(row.location_id)
                    ),
                    tags=tuple(row.context_tags or ()),
                ),
                emotional_salience=float(row.emotional_salience),
                confidence=float(row.confidence),
                provenance=MemoryProvenance(
                    kind=MemorySourceKind(row.source_kind),
                    source_tick=int(row.provenance_source_tick),
                    observed_source_id=(
                        None
                        if row.observed_source_id is None
                        else EventId(row.observed_source_id)
                    ),
                    speaker_id=(
                        None if row.speaker_id is None else EntityId(row.speaker_id)
                    ),
                    transmission=transmission_from_row(row),
                ),
                created_tick=int(row.created_tick),
                source_tick=int(row.source_tick),
                last_access_tick=int(row.last_access_tick),
                access_count=int(row.access_count),
                expires_at_tick=(
                    None if row.expires_at_tick is None else int(row.expires_at_tick)
                ),
                forgotten_at_tick=(
                    None
                    if row.forgotten_at_tick is None
                    else int(row.forgotten_at_tick)
                ),
                lineage=MemoryLineage(
                    supersedes_memory_id=(
                        None
                        if row.supersedes_memory_id is None
                        else MemoryId(row.supersedes_memory_id)
                    ),
                    generation=int(row.generation),
                    source_memory_ids=source_memory_ids,
                    reconstruction_id=reconstruction_id,
                ),
                embedding=embedding,
            )
        )
    return tuple(assembled)
