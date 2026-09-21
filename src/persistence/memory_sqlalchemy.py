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
    RelationEndpoint,
    RelationEndpointKind,
    WorldRevision,
)
from memory.scoring import rank_traces, should_forget
from memory.service import MemoryServiceError, MemoryServiceErrorCode
from persistence.errors import PersistenceAdapterError
from persistence.memory_orm import (
    MemoryAccessOpOrm,
    MemoryConceptOrm,
    MemoryEntityMentionOrm,
    MemoryRelationOrm,
    MemoryTraceOrm,
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
            for write in batch.writes:
                existing = await session.get(
                    MemoryTraceOrm,
                    (
                        self._scope.run_id.value,
                        self._scope.owner_id.value,
                        write.memory_id.value,
                    ),
                )
                if existing is not None:
                    _LOG.error(
                        "memory_apply_conflict",
                        extra={
                            "operation": "apply",
                            "run_id": self._scope.run_id.value,
                            "owner_id": self._scope.owner_id.value,
                            "reason_code": MemoryServiceErrorCode.CONFLICT.value,
                        },
                    )
                    raise MemoryServiceError(MemoryServiceErrorCode.CONFLICT)
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
                if access.access_tick < row.created_tick:
                    raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)

            written = 0
            applied = 0
            idempotent = 0
            try:
                for write in batch.writes:
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
                await session.commit()
            except MemoryServiceError:
                await session.rollback()
                raise
            except IntegrityError:
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
                "status": "ok",
            },
        )
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
                    ),
                    embedding=embedding,
                )
            )
        return tuple(assembled)

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
