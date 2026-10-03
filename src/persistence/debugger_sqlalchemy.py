"""SQLAlchemy adapters for causal-debugger event lookup and lineage reads.

Implements simulation debugger ports without importing ``world``, ``agents``,
``observer``, or ``api``. Uses existing ``world_events`` indexes
(``uq_world_events_event_id``, PK ``(run_id, tick, sequence)``) — no Alembic
revision in this plan.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.database import session_scope
from infrastructure.logging import get_logger
from persistence.memory_orm import MemoryDerivationSourceOrm, MemoryTraceOrm
from persistence.orm import WorldEventOrm
from persistence.readers import event_from_orm
from persistence.subjective_orm import SemanticBeliefEvidenceOrm
from simulation.causal_debugger import (
    CausalTraceAvailability,
    DebuggerEventLookupPort,
    DebuggerEventRecord,
    DebuggerFocusHandle,
    DebuggerLineageKind,
    semantic_type_for_detail_kind,
)
from simulation.cognition_trace import AgentId, CognitionTraceInvocation
from simulation.debugger_lineage import (
    BeliefEvidenceLineage,
    CommunicationLineage,
    DebuggerLineageEntry,
    DebuggerLineageResponse,
    GoalAncestryLineage,
    MemoryDerivationLineage,
    NarrativeLineage,
    PredictionProvenance,
    assemble_prediction_provenance,
    project_goal_ancestry_from_checkpoint,
    project_narrative_lineage_from_checkpoint,
)
from simulation.models import RunId

_LOGGER = get_logger("persistence.debugger_sqlalchemy")

CheckpointLookup = Callable[[str, str], object | None]

__all__ = [
    "SqlAlchemyBeliefEvidenceLineage",
    "SqlAlchemyCommunicationLineage",
    "SqlAlchemyDebuggerEventLookup",
    "SqlAlchemyGoalAncestryLineage",
    "SqlAlchemyMemoryDerivationLineage",
    "SqlAlchemyNarrativeLineage",
    "SqlAlchemyPredictionProvenance",
    "create_debugger_event_lookup",
    "create_debugger_lineage_ports",
]


def create_debugger_event_lookup(
    session_factory: async_sessionmaker[AsyncSession],
) -> DebuggerEventLookupPort:
    return SqlAlchemyDebuggerEventLookup(session_factory)


def create_debugger_lineage_ports(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    checkpoint_lookup: CheckpointLookup | None = None,
) -> dict[str, object]:
    """Factory map of lineage kind → port implementation.

    Narrative and goal ancestry use the same owner runtime checkpoint path as
    observer narrative-hops / inspection subjective routes. When
    ``checkpoint_lookup`` is omitted, those kinds fail closed with
    ``checkpoint_unavailable``.
    """
    lookup: CheckpointLookup = checkpoint_lookup or (lambda _run, _owner: None)
    return {
        DebuggerLineageKind.BELIEF_EVIDENCE.value: SqlAlchemyBeliefEvidenceLineage(
            session_factory
        ),
        DebuggerLineageKind.MEMORY_DERIVATION.value: SqlAlchemyMemoryDerivationLineage(
            session_factory
        ),
        DebuggerLineageKind.COMMUNICATION.value: SqlAlchemyCommunicationLineage(
            session_factory
        ),
        DebuggerLineageKind.NARRATIVE.value: SqlAlchemyNarrativeLineage(lookup),
        DebuggerLineageKind.GOAL_ANCESTRY.value: SqlAlchemyGoalAncestryLineage(lookup),
        DebuggerLineageKind.PREDICTION.value: SqlAlchemyPredictionProvenance(),
    }


def _record_from_row(row: WorldEventOrm) -> DebuggerEventRecord:
    decoded = event_from_orm(row)
    details = getattr(decoded, "details", None)
    detail_kind = str(getattr(details, "kind", None) or row.event_type)
    detail_type_name = type(details).__name__ if details is not None else None
    semantic = semantic_type_for_detail_kind(detail_kind)
    actor = row.actor_id
    return DebuggerEventRecord(
        event_id=row.event_id,
        tick=int(row.tick),
        sequence=int(row.sequence),
        actor_id=actor,
        agent_id=actor,
        detail_kind=detail_kind,
        semantic_type=semantic,
        detail_type_name=detail_type_name,
    )


class SqlAlchemyDebuggerEventLookup:
    """Direct indexed lookup over ``world_events`` (no full keyset scan)."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_event_id(
        self, *, run_id: RunId, event_id: str
    ) -> DebuggerEventRecord | None:
        _LOGGER.debug(
            "debugger_event_lookup",
            key="event_id",
            run_id=run_id.value,
            event_id=event_id,
        )
        async with session_scope(self._session_factory) as session:
            result = await session.execute(
                select(WorldEventOrm).where(
                    WorldEventOrm.run_id == run_id.value,
                    WorldEventOrm.event_id == event_id,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                _LOGGER.warning(
                    "debugger_event_lookup",
                    reason_code="event_not_found",
                    run_id=run_id.value,
                    event_id=event_id,
                )
                return None
            return _record_from_row(row)

    async def get_by_tick_sequence(
        self, *, run_id: RunId, tick: int, sequence: int
    ) -> DebuggerEventRecord | None:
        _LOGGER.debug(
            "debugger_event_lookup",
            key="tick_sequence",
            run_id=run_id.value,
            tick=tick,
            sequence=sequence,
        )
        async with session_scope(self._session_factory) as session:
            row = await session.get(
                WorldEventOrm, (run_id.value, tick, sequence)
            )
            if row is None:
                _LOGGER.warning(
                    "debugger_event_lookup",
                    reason_code="event_not_found",
                    run_id=run_id.value,
                    tick=tick,
                    sequence=sequence,
                )
                return None
            return _record_from_row(row)


class SqlAlchemyBeliefEvidenceLineage:
    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def belief_evidence(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> BeliefEvidenceLineage:
        _LOGGER.debug(
            "debugger_lineage_query",
            kind="belief_evidence",
            run_id=run_id.value,
            owner_id=owner_id.value,
            subject_id=subject_id,
        )
        async with session_scope(self._session_factory) as session:
            rows = (
                await session.execute(
                    select(SemanticBeliefEvidenceOrm)
                    .where(
                        SemanticBeliefEvidenceOrm.run_id == run_id.value,
                        SemanticBeliefEvidenceOrm.owner_id == owner_id.value,
                        SemanticBeliefEvidenceOrm.belief_id == subject_id,
                    )
                    .order_by(
                        SemanticBeliefEvidenceOrm.revision_id,
                        SemanticBeliefEvidenceOrm.ordinal,
                    )
                )
            ).scalars().all()
            if not rows:
                _LOGGER.warning(
                    "debugger_lineage_query",
                    kind="belief_evidence",
                    reason_code="lineage_not_found",
                    subject_id=subject_id,
                )
                return DebuggerLineageResponse(
                    run_id=run_id,
                    owner_id=owner_id,
                    kind=DebuggerLineageKind.BELIEF_EVIDENCE,
                    subject_id=subject_id,
                    availability=CausalTraceAvailability.UNAVAILABLE,
                    reason_code="lineage_not_found",
                )
            memory_ids = tuple(dict.fromkeys(row.memory_id for row in rows))
            return DebuggerLineageResponse(
                run_id=run_id,
                owner_id=owner_id,
                kind=DebuggerLineageKind.BELIEF_EVIDENCE,
                subject_id=subject_id,
                availability=CausalTraceAvailability.AVAILABLE,
                entries=(
                    DebuggerLineageEntry(
                        entry_id=subject_id,
                        kind=DebuggerLineageKind.BELIEF_EVIDENCE,
                        related_ids=memory_ids,
                        counts={"evidence_count": len(memory_ids)},
                    ),
                ),
            )


class SqlAlchemyMemoryDerivationLineage:
    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def memory_derivation(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> MemoryDerivationLineage:
        _LOGGER.debug(
            "debugger_lineage_query",
            kind="memory_derivation",
            run_id=run_id.value,
            owner_id=owner_id.value,
            subject_id=subject_id,
        )
        async with session_scope(self._session_factory) as session:
            sources = (
                await session.execute(
                    select(MemoryDerivationSourceOrm)
                    .where(
                        MemoryDerivationSourceOrm.run_id == run_id.value,
                        MemoryDerivationSourceOrm.owner_id == owner_id.value,
                        MemoryDerivationSourceOrm.derived_memory_id == subject_id,
                    )
                    .order_by(MemoryDerivationSourceOrm.source_memory_id)
                )
            ).scalars().all()
            if not sources:
                _LOGGER.warning(
                    "debugger_lineage_query",
                    kind="memory_derivation",
                    reason_code="lineage_not_found",
                    subject_id=subject_id,
                )
                return DebuggerLineageResponse(
                    run_id=run_id,
                    owner_id=owner_id,
                    kind=DebuggerLineageKind.MEMORY_DERIVATION,
                    subject_id=subject_id,
                    availability=CausalTraceAvailability.UNAVAILABLE,
                    reason_code="lineage_not_found",
                )
            related = tuple(row.source_memory_id for row in sources)
            reconstruction_ids = tuple(
                dict.fromkeys(
                    row.reconstruction_id
                    for row in sources
                    if row.reconstruction_id is not None
                )
            )
            return DebuggerLineageResponse(
                run_id=run_id,
                owner_id=owner_id,
                kind=DebuggerLineageKind.MEMORY_DERIVATION,
                subject_id=subject_id,
                availability=CausalTraceAvailability.AVAILABLE,
                entries=(
                    DebuggerLineageEntry(
                        entry_id=subject_id,
                        kind=DebuggerLineageKind.MEMORY_DERIVATION,
                        related_ids=related,
                        parent_ids=reconstruction_ids,
                        counts={"source_count": len(related)},
                    ),
                ),
            )


class SqlAlchemyCommunicationLineage:
    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def communication_lineage(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> CommunicationLineage:
        _LOGGER.debug(
            "debugger_lineage_query",
            kind="communication",
            run_id=run_id.value,
            owner_id=owner_id.value,
            subject_id=subject_id,
        )
        async with session_scope(self._session_factory) as session:
            result = await session.execute(
                select(MemoryTraceOrm).where(
                    MemoryTraceOrm.run_id == run_id.value,
                    MemoryTraceOrm.owner_id == owner_id.value,
                    MemoryTraceOrm.transmission_communication_id == subject_id,
                )
            )
            row = result.scalars().first()
            if row is None or row.transmission_communication_id is None:
                _LOGGER.warning(
                    "debugger_lineage_query",
                    kind="communication",
                    reason_code="lineage_not_found",
                    subject_id=subject_id,
                )
                return DebuggerLineageResponse(
                    run_id=run_id,
                    owner_id=owner_id,
                    kind=DebuggerLineageKind.COMMUNICATION,
                    subject_id=subject_id,
                    availability=CausalTraceAvailability.UNAVAILABLE,
                    reason_code="lineage_not_found",
                )
            related = []
            if row.transmission_parent_communication_id:
                related.append(row.transmission_parent_communication_id)
            if row.transmission_root_id:
                related.append(row.transmission_root_id)
            handles: tuple[DebuggerFocusHandle, ...] = ()
            # Delivery correlation uses opaque event id when stored as request/event.
            return DebuggerLineageResponse(
                run_id=run_id,
                owner_id=owner_id,
                kind=DebuggerLineageKind.COMMUNICATION,
                subject_id=subject_id,
                availability=CausalTraceAvailability.AVAILABLE,
                entries=(
                    DebuggerLineageEntry(
                        entry_id=subject_id,
                        kind=DebuggerLineageKind.COMMUNICATION,
                        related_ids=tuple(dict.fromkeys(related)),
                        reason_codes=(
                            ()
                            if row.transmission_action_kind is None
                            else (row.transmission_action_kind,)
                        ),
                        counts={
                            "hop_count": int(row.transmission_hop_count or 0),
                        },
                        focus_handles=handles,
                        status_code=row.transmission_action_kind,
                    ),
                ),
            )


class SqlAlchemyNarrativeLineage:
    """Narrative lineage from owner runtime checkpoint (inspection/observer path)."""

    __slots__ = ("_checkpoint_lookup",)

    def __init__(self, checkpoint_lookup: CheckpointLookup) -> None:
        self._checkpoint_lookup = checkpoint_lookup

    async def narrative_lineage(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> NarrativeLineage:
        checkpoint = self._checkpoint_lookup(run_id.value, owner_id.value)
        _LOGGER.debug(
            "debugger_lineage_query",
            kind="narrative",
            run_id=run_id.value,
            owner_id=owner_id.value,
            subject_id=subject_id,
            has_checkpoint=checkpoint is not None,
        )
        return project_narrative_lineage_from_checkpoint(
            run_id=run_id,
            owner_id=owner_id,
            subject_id=subject_id,
            checkpoint=checkpoint,
        )


class SqlAlchemyGoalAncestryLineage:
    """Goal ancestry from checkpoint ``goals`` / ``parent_goal_id`` chain."""

    __slots__ = ("_checkpoint_lookup",)

    def __init__(self, checkpoint_lookup: CheckpointLookup) -> None:
        self._checkpoint_lookup = checkpoint_lookup

    async def goal_ancestry(
        self, *, run_id: RunId, owner_id: AgentId, subject_id: str
    ) -> GoalAncestryLineage:
        checkpoint = self._checkpoint_lookup(run_id.value, owner_id.value)
        _LOGGER.debug(
            "debugger_lineage_query",
            kind="goal_ancestry",
            run_id=run_id.value,
            owner_id=owner_id.value,
            subject_id=subject_id,
            has_checkpoint=checkpoint is not None,
        )
        return project_goal_ancestry_from_checkpoint(
            run_id=run_id,
            owner_id=owner_id,
            subject_id=subject_id,
            checkpoint=checkpoint,
        )


class SqlAlchemyPredictionProvenance:
    """Prediction provenance uses Task 1c assemble helper (no hypothesis tables)."""

    __slots__ = ()

    async def prediction_provenance(
        self,
        *,
        run_id: RunId,
        owner_id: AgentId,
        subject_id: str,
        invocation: CognitionTraceInvocation | None = None,
        harvest=None,
    ) -> PredictionProvenance:
        return assemble_prediction_provenance(
            run_id=run_id,
            owner_id=owner_id,
            subject_id=subject_id,
            invocation=invocation,
            harvest=harvest,
        )
