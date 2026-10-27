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

from sqlalchemy import Subquery, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from experiments.persistence import (
    SUBJECTIVE_EVIDENCE_LANES,
    ObjectiveEventPage,
    PersistedAnalysisSnapshot,
    PersistedDerivationEdge,
    PersistedReconstructionRow,
    PersistedRegionalContext,
    SubjectiveEvidencePage,
    regional_context_from_snapshot,
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
from persistence.evidence_boundary import resolve_objective_evidence_boundary
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
    WorldSnapshotOrm,
)
from persistence.readers import event_from_orm, snapshot_from_canonical_payload
from persistence.transmission_mapping import transmission_from_row
from simulation.evidence import (
    EvidenceHighWaterMarks,
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

            bootstrap_row = await session.get(
                WorldSnapshotOrm, run_row.bootstrap_snapshot_id
            )
            if bootstrap_row is None:
                _LOG.error(
                    "analysis_evidence_bootstrap_missing",
                    extra={
                        "operation": "load",
                        "run_id": run_id,
                        "reason_code": "bootstrap_snapshot_not_found",
                    },
                )
                raise PersistenceNotFoundError(
                    "bootstrap_snapshot_not_found", operation="load"
                )
            bootstrap = snapshot_from_canonical_payload(
                bootstrap_row.canonical_payload,
                expected_integrity_hash=bootstrap_row.integrity_hash,
            )
            regional_context = regional_context_from_snapshot(bootstrap)

            boundary = await resolve_objective_evidence_boundary(
                session, run_id=run_id, manifest=manifest
            )
            complete_boundary = boundary.boundary_tick.value
            if manifest is None:
                events = await _load_events(session, run_id=run_id)
            elif boundary.bootstrap_only:
                events = ()
            else:
                assert boundary.through_tick is not None
                events = await _load_events(
                    session, run_id=run_id, through_tick=boundary.through_tick.value
                )

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
            regional_context=regional_context,
            objective_complete_through_boundary=complete_boundary,
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
                "regions_enabled": regional_context is not None,
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

    async def load_objective_event_page(
        self,
        *,
        run_id: str,
        manifest: EvidenceManifest | None = None,
        after_tick: int | None = None,
        after_sequence: int | None = None,
        limit: int = 1_000,
    ) -> ObjectiveEventPage:
        """Return one manifest-pinned keyset page of committed events."""
        run_id = RunId(run_id).value
        if manifest is not None and manifest.run_id != run_id:
            raise PersistenceAdapterError(
                "manifest_run_scope_mismatch", operation="load_event_page"
            )
        page_limit = _page_limit(limit)
        cursor_tick, cursor_sequence = _page_cursor(after_tick, after_sequence)
        async with session_scope(self._session_factory) as session:
            boundary = await resolve_objective_evidence_boundary(
                session, run_id=run_id, manifest=manifest
            )
            manifest_hash = None if manifest is None else manifest.manifest_hash
            if manifest is not None and boundary.bootstrap_only:
                _LOG.debug(
                    "analysis_event_page_complete",
                    extra={
                        "operation": "load_event_page",
                        "run_id": run_id,
                        "event_count": 0,
                        "exhausted": True,
                        "bootstrap_only": True,
                    },
                )
                return ObjectiveEventPage(
                    run_id=run_id,
                    events=(),
                    complete_through_boundary=boundary.boundary_tick.value,
                    next_tick=None,
                    next_sequence=None,
                    manifest_hash=manifest_hash,
                )
            statement = select(WorldEventOrm).where(WorldEventOrm.run_id == run_id)
            if boundary.through_tick is not None:
                statement = statement.where(
                    WorldEventOrm.tick <= boundary.through_tick.value
                )
            if cursor_tick is not None and cursor_sequence is not None:
                statement = statement.where(
                    or_(
                        WorldEventOrm.tick > cursor_tick,
                        and_(
                            WorldEventOrm.tick == cursor_tick,
                            WorldEventOrm.sequence > cursor_sequence,
                        ),
                    )
                )
            rows = list(
                (
                    await session.execute(
                        statement.order_by(
                            WorldEventOrm.tick, WorldEventOrm.sequence
                        ).limit(page_limit + 1)
                    )
                )
                .scalars()
                .all()
            )
        more = len(rows) > page_limit
        page_rows = rows[:page_limit]
        next_tick = None
        next_sequence = None
        if more and page_rows:
            next_tick = int(page_rows[-1].tick)
            next_sequence = int(page_rows[-1].sequence)
        _LOG.debug(
            "analysis_event_page_complete",
            extra={
                "operation": "load_event_page",
                "run_id": run_id,
                "event_count": len(page_rows),
                "exhausted": next_tick is None,
                "manifest_hash_prefix": (
                    None if manifest is None else manifest_hash_prefix(manifest)
                ),
            },
        )
        return ObjectiveEventPage(
            run_id=run_id,
            events=tuple(event_from_orm(row) for row in page_rows),
            complete_through_boundary=boundary.boundary_tick.value,
            next_tick=next_tick,
            next_sequence=next_sequence,
            manifest_hash=manifest_hash,
        )

    async def load_regional_context(
        self, *, run_id: str
    ) -> PersistedRegionalContext | None:
        """Return detached bootstrap regional context without loading evidence."""
        run_id = RunId(run_id).value
        async with session_scope(self._session_factory) as session:
            run_row = await session.get(SimulationRunOrm, run_id)
            if run_row is None:
                raise PersistenceNotFoundError(
                    "run_not_found", operation="load_regional_context"
                )
            bootstrap_row = await session.get(
                WorldSnapshotOrm, run_row.bootstrap_snapshot_id
            )
            if bootstrap_row is None:
                raise PersistenceNotFoundError(
                    "bootstrap_snapshot_not_found", operation="load_regional_context"
                )
            bootstrap = snapshot_from_canonical_payload(
                bootstrap_row.canonical_payload,
                expected_integrity_hash=bootstrap_row.integrity_hash,
            )
            context = regional_context_from_snapshot(bootstrap)
        _LOG.debug(
            "analysis_regional_context_loaded",
            extra={
                "operation": "load_regional_context",
                "run_id": run_id,
                "regions_enabled": context is not None,
                "owner_count": 0 if context is None else len(context.owner_ids),
            },
        )
        return context

    async def load_subjective_evidence_page(
        self,
        *,
        run_id: str,
        owner_id: str,
        manifest: EvidenceManifest | None = None,
        lane: str = "direct_traces",
        after_tick: int | None = None,
        after_id: str | None = None,
        after_ordinal: int | None = None,
        limit: int = 1_000,
    ) -> SubjectiveEvidencePage:
        """Return one manifest-clamped keyset page of a subjective lane."""
        run_id = RunId(run_id).value
        owner_id = AgentId(owner_id).value
        if lane not in SUBJECTIVE_EVIDENCE_LANES:
            raise PersistenceAdapterError(
                "invalid_subjective_lane", operation="load_subjective_page"
            )
        if manifest is not None:
            if type(manifest) is not EvidenceManifest:
                raise TypeError("manifest must be EvidenceManifest")
            if manifest.run_id != run_id:
                _LOG.error(
                    "analysis_subjective_page_scope_mismatch",
                    extra={
                        "operation": "load_subjective_page",
                        "run_id": run_id,
                        "reason_code": "manifest_run_scope_mismatch",
                    },
                )
                raise PersistenceAdapterError(
                    "manifest_run_scope_mismatch", operation="load_subjective_page"
                )
        page_limit = _page_limit(limit)
        _subjective_cursor(lane, after_tick, after_id, after_ordinal)
        manifest_hash = None if manifest is None else manifest.manifest_hash
        high_water = None if manifest is None else manifest.high_water
        started = time.perf_counter()
        async with session_scope(self._session_factory) as session:
            if lane in ("direct_traces", "communicated_traces"):
                kind = (
                    MemorySourceKind.DIRECT_OBSERVATION
                    if lane == "direct_traces"
                    else MemorySourceKind.COMMUNICATED
                )
                clamp = (
                    None
                    if high_water is None
                    else (
                        high_water.direct_memories
                        if lane == "direct_traces"
                        else high_water.communicated_memories
                    )
                )
                trace_rows, more = await _page_trace_rows(
                    session,
                    run_id=run_id,
                    owner_id=owner_id,
                    kind=kind,
                    high_water=clamp,
                    after_tick=after_tick,
                    after_id=after_id,
                    limit=page_limit,
                )
                traces = await _assemble_traces(
                    session, trace_rows, run_id=run_id, owner_id=owner_id
                )
                next_tick = None
                next_id = None
                next_ordinal = None
                if more and trace_rows:
                    next_tick = int(trace_rows[-1].created_tick)
                    next_id = trace_rows[-1].memory_id
                page = SubjectiveEvidencePage(
                    run_id=run_id,
                    owner_id=owner_id,
                    lane=lane,
                    traces=traces,
                    next_tick=next_tick,
                    next_id=next_id,
                    next_ordinal=next_ordinal,
                    manifest_hash=manifest_hash,
                )
            elif lane == "reconstructions":
                clamp = None if high_water is None else high_water.reconstructions
                recon_rows, more = await _page_reconstruction_rows(
                    session,
                    run_id=run_id,
                    owner_id=owner_id,
                    high_water=clamp,
                    after_tick=after_tick,
                    after_id=after_id,
                    limit=page_limit,
                )
                reconstructions = await _assemble_reconstructions(
                    session, recon_rows, run_id=run_id, owner_id=owner_id
                )
                next_tick = None
                next_id = None
                next_ordinal = None
                if more and recon_rows:
                    next_tick = int(recon_rows[-1].created_tick)
                    next_id = recon_rows[-1].reconstruction_id
                page = SubjectiveEvidencePage(
                    run_id=run_id,
                    owner_id=owner_id,
                    lane=lane,
                    reconstructions=reconstructions,
                    next_tick=next_tick,
                    next_id=next_id,
                    next_ordinal=next_ordinal,
                    manifest_hash=manifest_hash,
                )
            else:
                edge_rows, more = await _page_derivation_rows(
                    session,
                    run_id=run_id,
                    owner_id=owner_id,
                    high_water=high_water,
                    after_id=after_id,
                    after_ordinal=after_ordinal,
                    limit=page_limit,
                )
                edges = tuple(
                    PersistedDerivationEdge(
                        derived_memory_id=row.derived_memory_id,
                        source_memory_id=row.source_memory_id,
                        ordinal=int(row.ordinal),
                        reconstruction_id=row.reconstruction_id,
                    )
                    for row in edge_rows
                )
                next_id = None
                next_ordinal = None
                if more and edge_rows:
                    next_id = edge_rows[-1].derived_memory_id
                    next_ordinal = int(edge_rows[-1].ordinal)
                page = SubjectiveEvidencePage(
                    run_id=run_id,
                    owner_id=owner_id,
                    lane=lane,
                    derivation_edges=edges,
                    next_id=next_id,
                    next_ordinal=next_ordinal,
                    manifest_hash=manifest_hash,
                )
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        _LOG.debug(
            "analysis_subjective_page_complete",
            extra={
                "operation": "load_subjective_page",
                "run_id": run_id,
                "owner_id": owner_id,
                "lane": lane,
                "trace_count": len(page.traces),
                "reconstruction_count": len(page.reconstructions),
                "edge_count": len(page.derivation_edges),
                "exhausted": page.exhausted,
                "manifest_hash_prefix": (
                    None if manifest is None else manifest_hash_prefix(manifest)
                ),
                "duration_ms": duration_ms,
            },
        )
        return page


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
    kept_reconstruction_ids = {row.reconstruction_id for row in clamped_reconstructions}
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


async def _load_events(
    session: AsyncSession, *, run_id: str, through_tick: int | None = None
) -> tuple[object, ...]:
    statement = select(WorldEventOrm).where(WorldEventOrm.run_id == run_id)
    if through_tick is not None:
        statement = statement.where(WorldEventOrm.tick <= through_tick)
    rows = list(
        (
            await session.execute(
                statement.order_by(WorldEventOrm.tick, WorldEventOrm.sequence)
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
    return await _assemble_reconstructions(
        session, rows, run_id=run_id, owner_id=owner_id
    )


async def _assemble_reconstructions(
    session: AsyncSession,
    rows: Sequence[MemoryReconstructionOrm],
    *,
    run_id: str,
    owner_id: str,
) -> tuple[PersistedReconstructionRow, ...]:
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


MAX_ANALYSIS_PAGE_ROWS: Final[int] = 10_000


def _subjective_cursor(
    lane: str,
    after_tick: int | None,
    after_id: str | None,
    after_ordinal: int | None,
) -> None:
    def invalid() -> PersistenceAdapterError:
        return PersistenceAdapterError(
            "invalid_page_cursor", operation="load_subjective_page"
        )

    if lane == "derivation_edges":
        if after_tick is not None:
            raise invalid()
        if (after_id is None) != (after_ordinal is None):
            raise invalid()
        if after_ordinal is not None and (
            type(after_ordinal) is not int or after_ordinal < 0
        ):
            raise invalid()
    else:
        if after_ordinal is not None:
            raise invalid()
        if (after_tick is None) != (after_id is None):
            raise invalid()
        if after_tick is not None and (type(after_tick) is not int or after_tick < 0):
            raise invalid()
    if after_id is not None and (not isinstance(after_id, str) or not after_id):
        raise invalid()


def _clamped_memory_ids(
    *, run_id: str, owner_id: str, kind: MemorySourceKind, high_water: int
) -> Subquery:
    return (
        select(MemoryTraceOrm.memory_id.label("memory_id"))
        .where(
            MemoryTraceOrm.run_id == run_id,
            MemoryTraceOrm.owner_id == owner_id,
            MemoryTraceOrm.source_kind == kind.value,
        )
        .order_by(MemoryTraceOrm.created_tick, MemoryTraceOrm.memory_id)
        .limit(high_water)
        .subquery()
    )


def _clamped_reconstruction_ids(
    *, run_id: str, owner_id: str, high_water: int
) -> Subquery:
    return (
        select(MemoryReconstructionOrm.reconstruction_id.label("reconstruction_id"))
        .where(
            MemoryReconstructionOrm.run_id == run_id,
            MemoryReconstructionOrm.owner_id == owner_id,
        )
        .order_by(
            MemoryReconstructionOrm.created_tick,
            MemoryReconstructionOrm.reconstruction_id,
        )
        .limit(high_water)
        .subquery()
    )


async def _page_trace_rows(
    session: AsyncSession,
    *,
    run_id: str,
    owner_id: str,
    kind: MemorySourceKind,
    high_water: int | None,
    after_tick: int | None,
    after_id: str | None,
    limit: int,
) -> tuple[list[MemoryTraceOrm], bool]:
    statement = select(MemoryTraceOrm).where(
        MemoryTraceOrm.run_id == run_id,
        MemoryTraceOrm.owner_id == owner_id,
        MemoryTraceOrm.source_kind == kind.value,
    )
    if high_water is not None:
        clamped = _clamped_memory_ids(
            run_id=run_id, owner_id=owner_id, kind=kind, high_water=high_water
        )
        statement = statement.join(
            clamped, clamped.c.memory_id == MemoryTraceOrm.memory_id
        )
    if after_tick is not None and after_id is not None:
        statement = statement.where(
            or_(
                MemoryTraceOrm.created_tick > after_tick,
                and_(
                    MemoryTraceOrm.created_tick == after_tick,
                    MemoryTraceOrm.memory_id > after_id,
                ),
            )
        )
    rows = list(
        (
            await session.execute(
                statement.order_by(
                    MemoryTraceOrm.created_tick, MemoryTraceOrm.memory_id
                ).limit(limit + 1)
            )
        )
        .scalars()
        .all()
    )
    return rows[:limit], len(rows) > limit


async def _page_reconstruction_rows(
    session: AsyncSession,
    *,
    run_id: str,
    owner_id: str,
    high_water: int | None,
    after_tick: int | None,
    after_id: str | None,
    limit: int,
) -> tuple[list[MemoryReconstructionOrm], bool]:
    statement = select(MemoryReconstructionOrm).where(
        MemoryReconstructionOrm.run_id == run_id,
        MemoryReconstructionOrm.owner_id == owner_id,
    )
    if high_water is not None:
        clamped = _clamped_reconstruction_ids(
            run_id=run_id, owner_id=owner_id, high_water=high_water
        )
        statement = statement.join(
            clamped,
            clamped.c.reconstruction_id == MemoryReconstructionOrm.reconstruction_id,
        )
    if after_tick is not None and after_id is not None:
        statement = statement.where(
            or_(
                MemoryReconstructionOrm.created_tick > after_tick,
                and_(
                    MemoryReconstructionOrm.created_tick == after_tick,
                    MemoryReconstructionOrm.reconstruction_id > after_id,
                ),
            )
        )
    rows = list(
        (
            await session.execute(
                statement.order_by(
                    MemoryReconstructionOrm.created_tick,
                    MemoryReconstructionOrm.reconstruction_id,
                ).limit(limit + 1)
            )
        )
        .scalars()
        .all()
    )
    return rows[:limit], len(rows) > limit


async def _page_derivation_rows(
    session: AsyncSession,
    *,
    run_id: str,
    owner_id: str,
    high_water: EvidenceHighWaterMarks | None,
    after_id: str | None,
    after_ordinal: int | None,
    limit: int,
) -> tuple[list[MemoryDerivationSourceOrm], bool]:
    statement = select(MemoryDerivationSourceOrm).where(
        MemoryDerivationSourceOrm.run_id == run_id,
        MemoryDerivationSourceOrm.owner_id == owner_id,
    )
    if high_water is not None:
        direct = _clamped_memory_ids(
            run_id=run_id,
            owner_id=owner_id,
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            high_water=high_water.direct_memories,
        )
        communicated = _clamped_memory_ids(
            run_id=run_id,
            owner_id=owner_id,
            kind=MemorySourceKind.COMMUNICATED,
            high_water=high_water.communicated_memories,
        )
        reconstructions = _clamped_reconstruction_ids(
            run_id=run_id,
            owner_id=owner_id,
            high_water=high_water.reconstructions,
        )
        statement = statement.where(
            or_(
                MemoryDerivationSourceOrm.derived_memory_id.in_(
                    select(direct.c.memory_id)
                ),
                MemoryDerivationSourceOrm.derived_memory_id.in_(
                    select(communicated.c.memory_id)
                ),
                and_(
                    MemoryDerivationSourceOrm.reconstruction_id.is_not(None),
                    MemoryDerivationSourceOrm.reconstruction_id.in_(
                        select(reconstructions.c.reconstruction_id)
                    ),
                ),
            )
        )
    if after_id is not None and after_ordinal is not None:
        statement = statement.where(
            or_(
                MemoryDerivationSourceOrm.derived_memory_id > after_id,
                and_(
                    MemoryDerivationSourceOrm.derived_memory_id == after_id,
                    MemoryDerivationSourceOrm.ordinal > after_ordinal,
                ),
            )
        )
    rows = list(
        (
            await session.execute(
                statement.order_by(
                    MemoryDerivationSourceOrm.derived_memory_id,
                    MemoryDerivationSourceOrm.ordinal,
                ).limit(limit + 1)
            )
        )
        .scalars()
        .all()
    )
    return rows[:limit], len(rows) > limit


def _page_limit(limit: int) -> int:
    if type(limit) is not int or limit < 1 or limit > MAX_ANALYSIS_PAGE_ROWS:
        raise PersistenceAdapterError("invalid_page_limit", operation="page")
    return limit


def _page_cursor(
    after_tick: int | None, after_sequence: int | None
) -> tuple[int | None, int | None]:
    if (after_tick is None) != (after_sequence is None):
        raise PersistenceAdapterError("invalid_page_cursor", operation="page")
    for value in (after_tick, after_sequence):
        if value is not None and (type(value) is not int or value < 0):
            raise PersistenceAdapterError("invalid_page_cursor", operation="page")
    return after_tick, after_sequence
