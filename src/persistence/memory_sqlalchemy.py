"""Owner-scoped SQLAlchemy ``MemoryService`` for episodic traces.

Structured filters and ownership predicates run in SQL before ranking. Scoring
uses the pure ``memory.scoring`` helpers so PostgreSQL and in-memory results
share the same total order. This module must not import event ORM classes,
``world.events``, private world authority, or replay readers.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final, cast

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.database import session_scope
from memory.contracts import MemoryService
from memory.errors import MemoryServiceError, MemoryServiceErrorCode
from memory.models import (
    AgentId,
    ConceptMention,
    EntityId,
    EntityMention,
    EventId,
    MemoryAccessReceipt,
    MemoryApplyResult,
    MemoryEmbedding,
    MemoryForgetRequest,
    MemoryForgetResult,
    MemoryId,
    MemoryLineage,
    MemoryMutationBatch,
    MemoryProvenance,
    MemoryQueryFilters,
    MemoryRecallRequest,
    MemoryRecallResult,
    MemoryRelation,
    MemoryRetentionPolicy,
    MemoryRetrieveRequest,
    MemoryRetrieveResult,
    MemoryScope,
    MemoryScoringPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    ReconstructionId,
    ReconstructionRecord,
    RelationEndpoint,
    RelationEndpointKind,
    WorldRevision,
)
from memory.mutation import prepare_memory_mutation
from memory.scoring import rank_traces, should_forget
from persistence.errors import PersistenceAdapterError
from persistence.memory_orm import (
    MemoryAccessOpOrm,
    MemoryConceptOrm,
    MemoryDerivationSourceOrm,
    MemoryEntityMentionOrm,
    MemoryReconstructionOrm,
    MemoryReconstructionSourceOrm,
    MemoryRelationOrm,
    MemoryTraceOrm,
)
from persistence.transmission_mapping import (
    transmission_from_row,
    transmission_to_columns,
)

__all__ = [
    "SqlAlchemyMemoryService",
    "create_sqlalchemy_memory_service",
]

_LOG: Final[logging.Logger] = logging.getLogger("persistence.memory")
_MAX_OPERATION_ID_CHARS: Final[int] = 128


def create_sqlalchemy_memory_service(
    *,
    scope: MemoryScope,
    session_factory: async_sessionmaker[AsyncSession],
    scoring_policy: MemoryScoringPolicy,
    retention_policy: MemoryRetentionPolicy | None = None,
) -> MemoryService:
    """Construct an owner-scoped durable memory service."""
    if type(scope) is not MemoryScope:
        raise PersistenceAdapterError(
            "invalid_scope", operation="create_memory_service"
        )
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_memory_service"
        )
    if type(scoring_policy) is not MemoryScoringPolicy:
        raise PersistenceAdapterError(
            "invalid_scoring_policy", operation="create_memory_service"
        )
    if (
        retention_policy is not None
        and type(retention_policy) is not MemoryRetentionPolicy
    ):
        raise PersistenceAdapterError(
            "invalid_retention_policy", operation="create_memory_service"
        )
    return SqlAlchemyMemoryService(
        scope=scope,
        session_factory=session_factory,
        scoring_policy=scoring_policy,
        retention_policy=retention_policy,
    )


class SqlAlchemyMemoryService:
    """Async PostgreSQL episodic memory bound to one :class:`MemoryScope`."""

    __slots__ = (
        "_orchestrator",
        "_retention_policy",
        "_scope",
        "_scoring_policy",
        "_session_factory",
    )

    def __init__(
        self,
        *,
        scope: MemoryScope,
        session_factory: async_sessionmaker[AsyncSession],
        scoring_policy: MemoryScoringPolicy,
        retention_policy: MemoryRetentionPolicy | None,
    ) -> None:
        self._scope = scope
        self._session_factory = session_factory
        self._scoring_policy = scoring_policy
        self._retention_policy = retention_policy
        from memory.reconstruction import MemoryRecallOrchestrator

        self._orchestrator = MemoryRecallOrchestrator()
        _LOG.info(
            "memory_service_created",
            extra={
                "operation": "create",
                "run_id": scope.run_id.value,
                "owner_id": scope.owner_id.value,
                "policy_version": scoring_policy.version,
            },
        )

    @property
    def scope(self) -> MemoryScope:
        return self._scope

    @property
    def scoring_policy(self) -> MemoryScoringPolicy:
        return self._scoring_policy

    async def retrieve(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        if type(request) is not MemoryRetrieveRequest:
            _LOG.error(
                "memory_retrieve_invalid",
                extra={
                    "operation": "retrieve",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reason_code": MemoryServiceErrorCode.INVALID_REQUEST.value,
                },
            )
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_REQUEST)
        if request.query_embedding is not None:
            expected = request.scoring_policy.embedding_dimension
            if expected is not None and request.query_embedding.dimension != expected:
                raise MemoryServiceError(MemoryServiceErrorCode.INVALID_REQUEST)

        async with session_scope(self._session_factory) as session:
            candidates = await self._load_filtered_traces(session, request.filters)
            embeddings = {
                trace.memory_id.value: trace.embedding
                for trace in candidates
                if trace.embedding is not None
            }
            hits, candidate_count = rank_traces(
                candidates,
                policy=request.scoring_policy,
                current_tick=request.current_tick,
                filters=request.filters,
                context=request.context,
                query_embedding=request.query_embedding,
                embeddings=embeddings,
                limit=request.limit,
            )
        operation_id = request.operation_id or (
            f"retrieve:{request.current_tick}:{request.scoring_policy.version}"
        )
        pending = tuple(
            MemoryAccessReceipt(
                memory_id=hit.trace.memory_id,
                access_tick=request.current_tick,
                operation_id=operation_id,
            )
            for hit in hits
        )
        _LOG.debug(
            "memory_retrieve_complete",
            extra={
                "operation": "retrieve",
                "run_id": self._scope.run_id.value,
                "owner_id": self._scope.owner_id.value,
                "tick": request.current_tick,
                "policy_version": request.scoring_policy.version,
                "enabled_components": list(
                    request.scoring_policy.weights.enabled_components()
                ),
                "semantic_enabled": request.query_embedding is not None,
                "candidate_count": candidate_count,
                "result_count": len(hits),
            },
        )
        return MemoryRetrieveResult(
            hits=hits,
            pending_accesses=pending,
            candidate_count=candidate_count,
            retrieval_tick=request.current_tick,
            scoring_policy_version=request.scoring_policy.version,
        )

    async def recall(self, request: MemoryRecallRequest) -> MemoryRecallResult:
        if type(request) is not MemoryRecallRequest:
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_REQUEST)
        for belief in request.beliefs:
            if belief.owner_id != self._scope.owner_id:
                raise MemoryServiceError(MemoryServiceErrorCode.OWNERSHIP)
        return await self._orchestrator.recall(self, request)

    async def apply(self, batch: MemoryMutationBatch) -> MemoryApplyResult:
        if type(batch) is not MemoryMutationBatch:
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)
        for write in batch.writes:
            if write.owner_id != self._scope.owner_id:
                _LOG.error(
                    "memory_apply_ownership",
                    extra={
                        "operation": "apply",
                        "run_id": self._scope.run_id.value,
                        "owner_id": self._scope.owner_id.value,
                        "reason_code": MemoryServiceErrorCode.OWNERSHIP.value,
                    },
                )
                raise MemoryServiceError(MemoryServiceErrorCode.OWNERSHIP)
            if (
                self._scoring_policy.embedding_dimension is not None
                and write.embedding is not None
                and write.embedding.dimension
                != self._scoring_policy.embedding_dimension
            ):
                raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)

        async with session_scope(self._session_factory) as session:
            result = await self.apply_in_session(session, batch, commit=True)
        return result

    async def apply_in_session(
        self,
        session: AsyncSession,
        batch: MemoryMutationBatch,
        *,
        commit: bool = False,
    ) -> MemoryApplyResult:
        """Apply a mutation batch using an external session (optional commit)."""
        if type(batch) is not MemoryMutationBatch:
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)
        referenced_ids = {write.memory_id for write in batch.writes} | {
            access.memory_id for access in batch.accesses
        }
        for record in batch.reconstructions:
            referenced_ids.update(record.source_memory_ids)
        for write in batch.writes:
            referenced_ids.update(write.lineage.source_memory_ids)

        existing_traces = await self._load_traces_by_ids(session, referenced_ids)
        existing_hashes = await self._load_reconstruction_hashes(
            session,
            {item.reconstruction_id for item in batch.reconstructions}
            | {
                write.lineage.reconstruction_id
                for write in batch.writes
                if write.lineage.reconstruction_id is not None
            },
        )
        try:
            prepared = prepare_memory_mutation(
                batch,
                scope=self._scope,
                existing_traces=existing_traces,
                existing_reconstruction_hashes=existing_hashes,
            )
        except MemoryServiceError as exc:
            _LOG.error(
                "memory_apply_rejected",
                extra={
                    "operation": "apply",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reason_code": exc.code.value,
                    "write_count": len(batch.writes),
                    "reconstruction_count": len(batch.reconstructions),
                },
            )
            raise

        for access in batch.accesses:
            row = await session.get(
                MemoryTraceOrm,
                (
                    self._scope.run_id.value,
                    self._scope.owner_id.value,
                    access.memory_id.value,
                ),
                with_for_update=True,
            )
            if row is None:
                raise MemoryServiceError(MemoryServiceErrorCode.NOT_FOUND)

        written = 0
        applied = 0
        idempotent = 0
        reconstruction_written = 0
        try:
            source_needed: set[MemoryId] = set()
            for record in prepared.reconstructions_to_insert:
                source_needed.update(record.source_memory_ids)
            early_writes = [
                write
                for write in prepared.writes_to_insert
                if write.memory_id in source_needed
            ]
            late_writes = [
                write
                for write in prepared.writes_to_insert
                if write.memory_id not in source_needed
            ]
            for write in early_writes:
                await self._insert_trace(session, write)
                written += 1
            for record in prepared.reconstructions_to_insert:
                await self._insert_reconstruction(
                    session,
                    record,
                    payload_sha256=prepared.reconstruction_hashes[
                        record.reconstruction_id
                    ],
                )
                reconstruction_written += 1
            for write in late_writes:
                await self._insert_trace(session, write)
                written += 1
            for access in batch.accesses:
                inserted = await self._try_record_access(session, access)
                if inserted:
                    applied += 1
                else:
                    idempotent += 1
                    _LOG.warning(
                        "memory_access_idempotent",
                        extra={
                            "operation": "apply",
                            "run_id": self._scope.run_id.value,
                            "owner_id": self._scope.owner_id.value,
                            "reason_code": "duplicate_access",
                        },
                    )
            if commit:
                await session.commit()
        except MemoryServiceError:
            if commit:
                await session.rollback()
            raise
        except IntegrityError:
            if commit:
                await session.rollback()
            _LOG.error(
                "memory_apply_rollback",
                extra={
                    "operation": "apply",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reason_code": MemoryServiceErrorCode.CONFLICT.value,
                },
            )
            raise MemoryServiceError(MemoryServiceErrorCode.CONFLICT) from None

        _LOG.debug(
            "memory_apply_complete",
            extra={
                "operation": "apply",
                "run_id": self._scope.run_id.value,
                "owner_id": self._scope.owner_id.value,
                "write_count": written,
                "access_count": applied,
                "access_idempotent_count": idempotent,
                "reconstruction_written_count": reconstruction_written,
                "reconstruction_idempotent_count": (
                    prepared.reconstruction_idempotent_count
                ),
                "status": "ok",
            },
        )
        if reconstruction_written:
            _LOG.info(
                "memory_reconsolidation_committed",
                extra={
                    "operation": "apply",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reconstruction_written_count": reconstruction_written,
                    "write_count": written,
                },
            )
        elif prepared.reconstruction_idempotent_count:
            _LOG.warning(
                "memory_reconsolidation_idempotent",
                extra={
                    "operation": "apply",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reason_code": "duplicate_reconstruction",
                    "reconstruction_idempotent_count": (
                        prepared.reconstruction_idempotent_count
                    ),
                },
            )
        else:
            _LOG.info(
                "memory_apply_counts",
                extra={
                    "operation": "apply",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "write_count": written,
                    "access_count": applied,
                },
            )
        return MemoryApplyResult(
            written_count=written,
            access_applied_count=applied,
            access_idempotent_count=idempotent,
            reconstruction_written_count=reconstruction_written,
            reconstruction_idempotent_count=prepared.reconstruction_idempotent_count,
        )

    async def get(self, memory_id: MemoryId) -> MemoryTrace | None:
        if type(memory_id) is not MemoryId:
            raise TypeError("get requires MemoryId")
        async with session_scope(self._session_factory) as session:
            row = await session.get(
                MemoryTraceOrm,
                (
                    self._scope.run_id.value,
                    self._scope.owner_id.value,
                    memory_id.value,
                ),
            )
            if row is None:
                return None
            assembled = await self._assemble_traces(session, (row,))
            return assembled[0] if assembled else None

    async def snapshot(self) -> tuple[MemoryTrace, ...]:
        filters = MemoryQueryFilters(require_active=True)
        async with session_scope(self._session_factory) as session:
            return await self._load_filtered_traces(session, filters)

    async def forget(self, request: MemoryForgetRequest) -> MemoryForgetResult:
        if type(request) is not MemoryForgetRequest:
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_REQUEST)
        async with session_scope(self._session_factory) as session:
            stmt = select(MemoryTraceOrm).where(
                MemoryTraceOrm.run_id == self._scope.run_id.value,
                MemoryTraceOrm.owner_id == self._scope.owner_id.value,
            )
            rows = list((await session.execute(stmt)).scalars().all())
            traces = await self._assemble_traces(session, rows)
            examined = len(traces)
            forgotten = 0
            for trace in traces:
                if should_forget(
                    trace,
                    current_tick=request.current_tick,
                    policy=request.retention_policy,
                ):
                    await session.execute(
                        update(MemoryTraceOrm)
                        .where(
                            MemoryTraceOrm.run_id == self._scope.run_id.value,
                            MemoryTraceOrm.owner_id == self._scope.owner_id.value,
                            MemoryTraceOrm.memory_id == trace.memory_id.value,
                            MemoryTraceOrm.forgotten_at_tick.is_(None),
                        )
                        .values(forgotten_at_tick=request.current_tick)
                    )
                    forgotten += 1
            await session.commit()
        _LOG.info(
            "memory_forget_complete",
            extra={
                "operation": "forget",
                "run_id": self._scope.run_id.value,
                "owner_id": self._scope.owner_id.value,
                "tick": request.current_tick,
                "policy_version": request.retention_policy.version,
                "forgotten_count": forgotten,
                "examined_count": examined,
            },
        )
        return MemoryForgetResult(forgotten_count=forgotten, examined_count=examined)

    async def _load_filtered_traces(
        self, session: AsyncSession, filters: MemoryQueryFilters
    ) -> tuple[MemoryTrace, ...]:
        stmt = select(MemoryTraceOrm).where(
            MemoryTraceOrm.run_id == self._scope.run_id.value,
            MemoryTraceOrm.owner_id == self._scope.owner_id.value,
        )
        if filters.require_active:
            stmt = stmt.where(MemoryTraceOrm.forgotten_at_tick.is_(None))
        if filters.created_tick_min is not None:
            stmt = stmt.where(MemoryTraceOrm.created_tick >= filters.created_tick_min)
        if filters.created_tick_max is not None:
            stmt = stmt.where(MemoryTraceOrm.created_tick <= filters.created_tick_max)
        if filters.source_tick_min is not None:
            stmt = stmt.where(MemoryTraceOrm.source_tick >= filters.source_tick_min)
        if filters.source_tick_max is not None:
            stmt = stmt.where(MemoryTraceOrm.source_tick <= filters.source_tick_max)
        if filters.location_id is not None:
            stmt = stmt.where(MemoryTraceOrm.location_id == filters.location_id.value)
        if filters.provenance_kind is not None:
            stmt = stmt.where(
                MemoryTraceOrm.source_kind == filters.provenance_kind.value
            )
        if filters.min_confidence is not None:
            stmt = stmt.where(MemoryTraceOrm.confidence >= filters.min_confidence)
        if filters.min_salience is not None:
            stmt = stmt.where(MemoryTraceOrm.emotional_salience >= filters.min_salience)
        if filters.context_tags:
            stmt = stmt.where(
                MemoryTraceOrm.context_tags.contains(list(filters.context_tags))
            )
        if filters.concepts:
            for concept in filters.concepts:
                concept_exists = (
                    select(MemoryConceptOrm.mention_id)
                    .where(
                        MemoryConceptOrm.run_id == MemoryTraceOrm.run_id,
                        MemoryConceptOrm.owner_id == MemoryTraceOrm.owner_id,
                        MemoryConceptOrm.memory_id == MemoryTraceOrm.memory_id,
                        MemoryConceptOrm.concept == concept,
                    )
                    .exists()
                )
                stmt = stmt.where(concept_exists)
        if filters.entity_ids:
            for entity_id in filters.entity_ids:
                entity_exists = (
                    select(MemoryEntityMentionOrm.mention_id)
                    .where(
                        MemoryEntityMentionOrm.run_id == MemoryTraceOrm.run_id,
                        MemoryEntityMentionOrm.owner_id == MemoryTraceOrm.owner_id,
                        MemoryEntityMentionOrm.memory_id == MemoryTraceOrm.memory_id,
                        MemoryEntityMentionOrm.entity_id == entity_id.value,
                    )
                    .exists()
                )
                stmt = stmt.where(entity_exists)
        if filters.relation_predicates:
            for predicate in filters.relation_predicates:
                relation_exists = (
                    select(MemoryRelationOrm.relation_id)
                    .where(
                        MemoryRelationOrm.run_id == MemoryTraceOrm.run_id,
                        MemoryRelationOrm.owner_id == MemoryTraceOrm.owner_id,
                        MemoryRelationOrm.memory_id == MemoryTraceOrm.memory_id,
                        MemoryRelationOrm.predicate == predicate,
                    )
                    .exists()
                )
                stmt = stmt.where(relation_exists)

        rows = list((await session.execute(stmt)).scalars().all())
        return await self._assemble_traces(session, rows)

    async def _assemble_traces(
        self, session: AsyncSession, rows: Sequence[MemoryTraceOrm]
    ) -> tuple[MemoryTrace, ...]:
        if not rows:
            return ()
        memory_ids = [row.memory_id for row in rows]
        concepts: Sequence[MemoryConceptOrm] = (
            (
                await session.execute(
                    select(MemoryConceptOrm)
                    .where(
                        MemoryConceptOrm.run_id == self._scope.run_id.value,
                        MemoryConceptOrm.owner_id == self._scope.owner_id.value,
                        MemoryConceptOrm.memory_id.in_(memory_ids),
                    )
                    .order_by(MemoryConceptOrm.memory_id, MemoryConceptOrm.ordinal)
                )
            )
            .scalars()
            .all()
        )
        entities: Sequence[MemoryEntityMentionOrm] = (
            (
                await session.execute(
                    select(MemoryEntityMentionOrm)
                    .where(
                        MemoryEntityMentionOrm.run_id == self._scope.run_id.value,
                        MemoryEntityMentionOrm.owner_id == self._scope.owner_id.value,
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
        relations: Sequence[MemoryRelationOrm] = (
            (
                await session.execute(
                    select(MemoryRelationOrm)
                    .where(
                        MemoryRelationOrm.run_id == self._scope.run_id.value,
                        MemoryRelationOrm.owner_id == self._scope.owner_id.value,
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

        derivation_rows: Sequence[MemoryDerivationSourceOrm] = (
            (
                await session.execute(
                    select(MemoryDerivationSourceOrm)
                    .where(
                        MemoryDerivationSourceOrm.run_id == self._scope.run_id.value,
                        MemoryDerivationSourceOrm.owner_id
                        == self._scope.owner_id.value,
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
                            None
                            if row.location_id is None
                            else EntityId(row.location_id)
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
                        None
                        if row.expires_at_tick is None
                        else int(row.expires_at_tick)
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

    async def _load_traces_by_ids(
        self, session: AsyncSession, memory_ids: set[MemoryId]
    ) -> dict[MemoryId, MemoryTrace]:
        if not memory_ids:
            return {}
        stmt = select(MemoryTraceOrm).where(
            MemoryTraceOrm.run_id == self._scope.run_id.value,
            MemoryTraceOrm.owner_id == self._scope.owner_id.value,
            MemoryTraceOrm.memory_id.in_([item.value for item in memory_ids]),
        )
        rows = list((await session.execute(stmt)).scalars().all())
        assembled = await self._assemble_traces(session, rows)
        return {trace.memory_id: trace for trace in assembled}

    async def _load_reconstruction_hashes(
        self, session: AsyncSession, reconstruction_ids: set[ReconstructionId]
    ) -> dict[ReconstructionId, str]:
        if not reconstruction_ids:
            return {}
        stmt = select(MemoryReconstructionOrm).where(
            MemoryReconstructionOrm.run_id == self._scope.run_id.value,
            MemoryReconstructionOrm.owner_id == self._scope.owner_id.value,
            MemoryReconstructionOrm.reconstruction_id.in_(
                [item.value for item in reconstruction_ids]
            ),
        )
        rows = list((await session.execute(stmt)).scalars().all())
        return {
            ReconstructionId(row.reconstruction_id): row.payload_sha256 for row in rows
        }

    async def _insert_reconstruction(
        self,
        session: AsyncSession,
        record: ReconstructionRecord,
        *,
        payload_sha256: str,
    ) -> None:
        session.add(
            MemoryReconstructionOrm(
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
                reconstruction_id=record.reconstruction_id.value,
                created_tick=record.created_tick,
                generation=record.reconstructed.generation,
                policy_id=record.policy_id,
                policy_version=record.policy_version,
                used_provider=record.used_provider,
                fallback_used=record.fallback_used,
                prompt_version=record.prompt_version,
                schema_version=record.schema_version,
                payload_sha256=payload_sha256,
            )
        )
        await session.flush()
        for ordinal, source_id in enumerate(record.source_memory_ids):
            session.add(
                MemoryReconstructionSourceOrm(
                    run_id=self._scope.run_id.value,
                    owner_id=self._scope.owner_id.value,
                    reconstruction_id=record.reconstruction_id.value,
                    source_memory_id=source_id.value,
                    ordinal=ordinal,
                )
            )
        await session.flush()

    async def _insert_trace(self, session: AsyncSession, trace: MemoryTrace) -> None:
        embedding = None
        embedding_model = None
        embedding_version = None
        embedding_dimension = None
        if trace.embedding is not None:
            embedding = list(trace.embedding.vector)
            embedding_model = trace.embedding.model
            embedding_version = trace.embedding.version
            embedding_dimension = trace.embedding.dimension
        session.add(
            MemoryTraceOrm(
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
                memory_id=trace.memory_id.value,
                world_revision=trace.world_revision.value,
                emotional_salience=trace.emotional_salience,
                confidence=trace.confidence,
                source_kind=trace.provenance.kind.value,
                provenance_source_tick=trace.provenance.source_tick,
                observed_source_id=(
                    None
                    if trace.provenance.observed_source_id is None
                    else trace.provenance.observed_source_id.value
                ),
                speaker_id=(
                    None
                    if trace.provenance.speaker_id is None
                    else trace.provenance.speaker_id.value
                ),
                **transmission_to_columns(trace.provenance.transmission),
                created_tick=trace.created_tick,
                source_tick=trace.source_tick,
                last_access_tick=trace.last_access_tick,
                access_count=trace.access_count,
                expires_at_tick=trace.expires_at_tick,
                forgotten_at_tick=trace.forgotten_at_tick,
                location_id=(
                    None
                    if trace.context.location_id is None
                    else trace.context.location_id.value
                ),
                context_tags=list(trace.context.tags),
                supersedes_memory_id=(
                    None
                    if trace.lineage.supersedes_memory_id is None
                    else trace.lineage.supersedes_memory_id.value
                ),
                generation=trace.lineage.generation,
                embedding=embedding,
                embedding_model=embedding_model,
                embedding_version=embedding_version,
                embedding_dimension=embedding_dimension,
            )
        )
        await session.flush()
        for ordinal, concept in enumerate(trace.concepts):
            session.add(
                MemoryConceptOrm(
                    run_id=self._scope.run_id.value,
                    owner_id=self._scope.owner_id.value,
                    memory_id=trace.memory_id.value,
                    mention_id=concept.mention_id.value,
                    ordinal=ordinal,
                    concept=concept.concept,
                )
            )
        for ordinal, entity in enumerate(trace.entities):
            session.add(
                MemoryEntityMentionOrm(
                    run_id=self._scope.run_id.value,
                    owner_id=self._scope.owner_id.value,
                    memory_id=trace.memory_id.value,
                    mention_id=entity.mention_id.value,
                    ordinal=ordinal,
                    label=entity.label,
                    entity_id=(
                        None if entity.entity_id is None else entity.entity_id.value
                    ),
                )
            )
        await session.flush()
        for ordinal, relation in enumerate(trace.relations):
            session.add(
                MemoryRelationOrm(
                    run_id=self._scope.run_id.value,
                    owner_id=self._scope.owner_id.value,
                    memory_id=trace.memory_id.value,
                    relation_id=relation.relation_id.value,
                    ordinal=ordinal,
                    predicate=relation.predicate,
                    subject_kind=relation.subject.kind.value,
                    subject_mention_id=relation.subject.mention_id.value,
                    object_kind=relation.object.kind.value,
                    object_mention_id=relation.object.mention_id.value,
                )
            )
        if trace.lineage.source_memory_ids:
            reconstruction_value = (
                None
                if trace.lineage.reconstruction_id is None
                else trace.lineage.reconstruction_id.value
            )
            for ordinal, source_id in enumerate(trace.lineage.source_memory_ids):
                session.add(
                    MemoryDerivationSourceOrm(
                        run_id=self._scope.run_id.value,
                        owner_id=self._scope.owner_id.value,
                        derived_memory_id=trace.memory_id.value,
                        source_memory_id=source_id.value,
                        ordinal=ordinal,
                        reconstruction_id=reconstruction_value,
                    )
                )
        await session.flush()

    async def _try_record_access(
        self, session: AsyncSession, access: MemoryAccessReceipt
    ) -> bool:
        if len(access.operation_id) > _MAX_OPERATION_ID_CHARS:
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)
        stmt = (
            pg_insert(MemoryAccessOpOrm)
            .values(
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
                operation_id=access.operation_id,
                memory_id=access.memory_id.value,
                access_tick=access.access_tick,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "run_id",
                    "owner_id",
                    "operation_id",
                    "memory_id",
                ]
            )
            .returning(MemoryAccessOpOrm.memory_id)
        )
        result = await session.execute(stmt)
        inserted = result.scalar_one_or_none()
        if inserted is None:
            return False
        await session.execute(
            update(MemoryTraceOrm)
            .where(
                MemoryTraceOrm.run_id == self._scope.run_id.value,
                MemoryTraceOrm.owner_id == self._scope.owner_id.value,
                MemoryTraceOrm.memory_id == access.memory_id.value,
            )
            .values(
                access_count=MemoryTraceOrm.access_count + 1,
                last_access_tick=func.greatest(
                    MemoryTraceOrm.last_access_tick, access.access_tick
                ),
            )
        )
        return True
