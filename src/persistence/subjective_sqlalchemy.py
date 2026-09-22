"""SQLAlchemy adapter for atomic owner-scoped subjective state commits.

Persists episodic memory mutations (via ``SqlAlchemyMemoryService``), semantic
belief revisions, and directed relationship revisions in one transaction with
idempotent operation receipts. Keyset pagination for inspection/debug is owned
by ``persistence.inspection_sqlalchemy``. Never logs claims, values, dimensions,
or ``exc_info``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.database import session_scope
from memory.belief_formation import (
    DEFAULT_BELIEF_FORMATION_POLICY,
    BeliefFormationPolicy,
    belief_id_for_claim,
    merge_revision,
)
from memory.beliefs import (
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefEvidenceBundle,
    BeliefEvidenceContribution,
    BeliefPolicyRef,
    BeliefRevision,
    BeliefRevisionId,
    BeliefRevisionRequest,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    EvidenceStance,
    SemanticBelief,
    SemanticBeliefHistory,
    SemanticClaim,
)
from memory.errors import MemoryServiceError
from memory.models import (
    AgentId,
    BeliefId,
    EntityId,
    MemoryId,
    MemoryMutationBatch,
    MemoryScope,
)
from persistence.errors import PersistenceAdapterError
from persistence.memory_sqlalchemy import SqlAlchemyMemoryService
from persistence.subjective_orm import (
    DirectedRelationshipOrm,
    RelationshipDimensionEvidenceOrm,
    RelationshipDimensionStateOrm,
    RelationshipRevisionOrm,
    SemanticBeliefEvidenceOrm,
    SemanticBeliefOrm,
    SemanticBeliefRevisionOrm,
    SubjectiveOperationOrm,
)
from persistence.transmission_mapping import (
    applied_factors_from_row,
    applied_factors_to_columns,
)
from simulation.subjective_state import (
    SubjectiveApplyReceipt,
    SubjectiveMutationBatch,
    SubjectiveStateError,
    SubjectiveStateErrorCode,
)
from social.models import RelationshipId
from social.relationships import (
    DEFAULT_RELATIONSHIP_POLICY,
    DirectedRelationshipProfile,
    RelationshipActivationState,
    RelationshipConfidence,
    RelationshipDimension,
    RelationshipDimensionState,
    RelationshipEvidenceItem,
    RelationshipFormationPolicy,
    RelationshipHistory,
    RelationshipPolicyRef,
    RelationshipRevision,
    RelationshipRevisionId,
    RelationshipRevisionRequest,
    merge_relationship_revision,
    profile_id_for,
)

__all__ = [
    "SqlAlchemySubjectiveStateService",
    "create_sqlalchemy_subjective_state_service",
]

_LOG: Final[logging.Logger] = logging.getLogger("persistence.subjective")


def create_sqlalchemy_subjective_state_service(
    *,
    scope: MemoryScope,
    session_factory: async_sessionmaker[AsyncSession],
    memory_service: SqlAlchemyMemoryService,
    belief_policy: BeliefFormationPolicy | None = None,
    relationship_policy: RelationshipFormationPolicy | None = None,
) -> SqlAlchemySubjectiveStateService:
    """Construct an owner-scoped durable subjective state service."""
    if type(scope) is not MemoryScope:
        raise PersistenceAdapterError(
            "invalid_scope", operation="create_subjective_state_service"
        )
    if session_factory is None:
        raise PersistenceAdapterError(
            "missing_session_factory", operation="create_subjective_state_service"
        )
    if type(memory_service) is not SqlAlchemyMemoryService:
        raise PersistenceAdapterError(
            "invalid_memory_service", operation="create_subjective_state_service"
        )
    if belief_policy is not None and type(belief_policy) is not BeliefFormationPolicy:
        raise PersistenceAdapterError(
            "invalid_belief_policy", operation="create_subjective_state_service"
        )
    if (
        relationship_policy is not None
        and type(relationship_policy) is not RelationshipFormationPolicy
    ):
        raise PersistenceAdapterError(
            "invalid_relationship_policy",
            operation="create_subjective_state_service",
        )
    return SqlAlchemySubjectiveStateService(
        scope=scope,
        session_factory=session_factory,
        memory_service=memory_service,
        belief_policy=belief_policy,
        relationship_policy=relationship_policy,
    )


def _batch_fingerprint(batch: SubjectiveMutationBatch) -> str:
    parts = [
        batch.operation_id,
        str(batch.logical_tick),
        str(batch.expected_revision),
        str(len(batch.memory_writes)),
        str(len(batch.memory_accesses)),
        str(len(batch.reconstructions)),
        str(len(batch.belief_revisions)),
        str(len(batch.relationship_revisions)),
    ]
    for write in batch.memory_writes:
        parts.append(write.memory_id.value)
    for access in batch.memory_accesses:
        parts.append(f"{access.memory_id.value}:{access.operation_id}")
    for reconstruction in batch.reconstructions:
        parts.append(reconstruction.reconstruction_id.value)
    for belief_rev in batch.belief_revisions:
        parts.append(belief_rev.operation_id)
    for relationship_rev in batch.relationship_revisions:
        parts.append(relationship_rev.operation_id)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _encode_claim_subject(subject: ClaimSubject) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": subject.kind.value}
    if subject.kind is ClaimSubjectKind.AGENT:
        assert subject.agent_id is not None
        payload["agent_id"] = subject.agent_id.value
    elif subject.kind is ClaimSubjectKind.ENTITY:
        assert subject.entity_id is not None
        payload["entity_id"] = subject.entity_id.value
    else:
        assert subject.concept is not None
        payload["concept"] = subject.concept
    return payload


def _encode_claim_value(value: ClaimValue) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": value.kind.value}
    if value.kind is BeliefValueKind.BOOL:
        payload["bool_value"] = value.bool_value
    elif value.kind is BeliefValueKind.NUMBER:
        payload["number_value"] = value.number_value
    elif value.kind is BeliefValueKind.TEXT:
        payload["text_value"] = value.text_value
    elif value.kind is BeliefValueKind.AGENT:
        assert value.agent_id is not None
        payload["agent_id"] = value.agent_id.value
    else:
        assert value.entity_id is not None
        payload["entity_id"] = value.entity_id.value
    return payload


def _encode_claim_json(claim: SemanticClaim) -> str:
    return json.dumps(
        {
            "predicate": claim.predicate,
            "subject": _encode_claim_subject(claim.subject),
            "value": _encode_claim_value(claim.value),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _decode_claim_subject(raw: dict[str, Any]) -> ClaimSubject:
    kind = ClaimSubjectKind(str(raw["kind"]))
    if kind is ClaimSubjectKind.AGENT:
        return ClaimSubject(kind=kind, agent_id=AgentId(str(raw["agent_id"])))
    if kind is ClaimSubjectKind.ENTITY:
        return ClaimSubject(kind=kind, entity_id=EntityId(str(raw["entity_id"])))
    return ClaimSubject(kind=kind, concept=str(raw["concept"]))


def _decode_claim_value(raw: dict[str, Any]) -> ClaimValue:
    kind = BeliefValueKind(str(raw["kind"]))
    if kind is BeliefValueKind.BOOL:
        return ClaimValue(kind=kind, bool_value=bool(raw["bool_value"]))
    if kind is BeliefValueKind.NUMBER:
        return ClaimValue(kind=kind, number_value=float(raw["number_value"]))
    if kind is BeliefValueKind.TEXT:
        return ClaimValue(kind=kind, text_value=str(raw["text_value"]))
    if kind is BeliefValueKind.AGENT:
        return ClaimValue(kind=kind, agent_id=AgentId(str(raw["agent_id"])))
    return ClaimValue(kind=kind, entity_id=EntityId(str(raw["entity_id"])))


def _decode_claim_json(text: str) -> SemanticClaim:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("claim_canonical: invalid_json")
    return SemanticClaim(
        subject=_decode_claim_subject(payload["subject"]),
        predicate=str(payload["predicate"]),
        value=_decode_claim_value(payload["value"]),
    )


def _claim_from_belief_row(row: SemanticBeliefOrm) -> SemanticClaim:
    kind = ClaimSubjectKind(row.subject_kind)
    if kind is ClaimSubjectKind.AGENT:
        assert row.subject_agent_id is not None
        subject = ClaimSubject(kind=kind, agent_id=AgentId(row.subject_agent_id))
    elif kind is ClaimSubjectKind.ENTITY:
        assert row.subject_entity_id is not None
        subject = ClaimSubject(kind=kind, entity_id=EntityId(row.subject_entity_id))
    else:
        assert row.subject_concept is not None
        subject = ClaimSubject(kind=kind, concept=row.subject_concept)
    value_kind = BeliefValueKind(row.value_kind)
    if value_kind is BeliefValueKind.BOOL:
        assert row.value_bool is not None
        value = ClaimValue(kind=value_kind, bool_value=row.value_bool)
    elif value_kind is BeliefValueKind.NUMBER:
        assert row.value_number is not None
        value = ClaimValue(kind=value_kind, number_value=float(row.value_number))
    elif value_kind is BeliefValueKind.TEXT:
        assert row.value_text is not None
        value = ClaimValue(kind=value_kind, text_value=row.value_text)
    elif value_kind is BeliefValueKind.AGENT:
        assert row.value_agent_id is not None
        value = ClaimValue(kind=value_kind, agent_id=AgentId(row.value_agent_id))
    else:
        assert row.value_entity_id is not None
        value = ClaimValue(kind=value_kind, entity_id=EntityId(row.value_entity_id))
    return SemanticClaim(subject=subject, predicate=row.predicate, value=value)


def _belief_claim_columns(claim: SemanticClaim) -> dict[str, Any]:
    subject = claim.subject
    value = claim.value
    return {
        "subject_kind": subject.kind.value,
        "subject_agent_id": (
            None if subject.agent_id is None else subject.agent_id.value
        ),
        "subject_entity_id": (
            None if subject.entity_id is None else subject.entity_id.value
        ),
        "subject_concept": subject.concept,
        "predicate": claim.predicate,
        "value_kind": value.kind.value,
        "value_bool": value.bool_value,
        "value_number": value.number_value,
        "value_text": value.text_value,
        "value_agent_id": None if value.agent_id is None else value.agent_id.value,
        "value_entity_id": None if value.entity_id is None else value.entity_id.value,
    }


class SqlAlchemySubjectiveStateService:
    """Async PostgreSQL subjective commit service bound to one ``MemoryScope``."""

    __slots__ = (
        "_belief_policy",
        "_lock",
        "_memory",
        "_relationship_policy",
        "_revision",
        "_scope",
        "_session_factory",
    )

    def __init__(
        self,
        *,
        scope: MemoryScope,
        session_factory: async_sessionmaker[AsyncSession],
        memory_service: SqlAlchemyMemoryService,
        belief_policy: BeliefFormationPolicy | None = None,
        relationship_policy: RelationshipFormationPolicy | None = None,
    ) -> None:
        if type(scope) is not MemoryScope:
            raise TypeError("SqlAlchemySubjectiveStateService requires MemoryScope")
        if type(memory_service) is not SqlAlchemyMemoryService:
            raise TypeError("memory_service must be SqlAlchemyMemoryService")
        if memory_service.scope != scope:
            raise ValueError("memory_service scope mismatch")
        if memory_service._session_factory is not session_factory:
            raise ValueError("memory_service session_factory mismatch")
        if belief_policy is None:
            belief_policy = DEFAULT_BELIEF_FORMATION_POLICY
        elif type(belief_policy) is not BeliefFormationPolicy:
            raise TypeError("invalid BeliefFormationPolicy")
        if relationship_policy is None:
            relationship_policy = DEFAULT_RELATIONSHIP_POLICY
        elif type(relationship_policy) is not RelationshipFormationPolicy:
            raise TypeError("invalid RelationshipFormationPolicy")
        self._scope = scope
        self._session_factory = session_factory
        self._memory = memory_service
        self._belief_policy = belief_policy
        self._relationship_policy = relationship_policy
        self._revision = 0
        self._lock = asyncio.Lock()
        _LOG.info(
            "subjective_service_created",
            extra={
                "operation": "create",
                "run_id": scope.run_id.value,
                "owner_id": scope.owner_id.value,
                "belief_policy_id": belief_policy.policy_id,
                "belief_policy_version": belief_policy.version,
                "relationship_policy_id": relationship_policy.policy_id,
                "relationship_policy_version": relationship_policy.version,
            },
        )

    @property
    def scope(self) -> MemoryScope:
        return self._scope

    @property
    def revision(self) -> int:
        return self._revision

    async def commit(self, batch: SubjectiveMutationBatch) -> SubjectiveApplyReceipt:
        if type(batch) is not SubjectiveMutationBatch:
            raise SubjectiveStateError(
                SubjectiveStateErrorCode.INVALID_REQUEST,
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
            )
        async with self._lock:
            return await self._commit_locked(batch)

    async def _commit_locked(
        self, batch: SubjectiveMutationBatch
    ) -> SubjectiveApplyReceipt:
        owner = self._scope.owner_id
        run_id = self._scope.run_id.value
        fingerprint = _batch_fingerprint(batch)

        async with session_scope(self._session_factory) as session:
            prior_op = await session.get(
                SubjectiveOperationOrm,
                (run_id, owner.value, batch.operation_id),
            )
            if prior_op is not None:
                if prior_op.fingerprint != fingerprint:
                    _LOG.warning(
                        "subjective_commit_idempotency_conflict",
                        extra={
                            "operation": "commit",
                            "run_id": run_id,
                            "owner_id": owner.value,
                            "operation_id": batch.operation_id,
                            "reason_code": (
                                SubjectiveStateErrorCode.IDEMPOTENCY_CONFLICT.value
                            ),
                        },
                    )
                    raise SubjectiveStateError(
                        SubjectiveStateErrorCode.IDEMPOTENCY_CONFLICT,
                        run_id=run_id,
                        owner_id=owner.value,
                        operation_id=batch.operation_id,
                    )
                receipt = SubjectiveApplyReceipt(
                    operation_id=prior_op.operation_id,
                    revision=int(prior_op.revision),
                    memory_written_count=int(prior_op.memory_written_count),
                    memory_access_count=0,
                    reconstruction_written_count=0,
                    belief_revision_count=int(prior_op.belief_revision_count),
                    relationship_revision_count=int(
                        prior_op.relationship_revision_count
                    ),
                    idempotent=True,
                )
                self._revision = max(self._revision, receipt.revision)
                _LOG.debug(
                    "subjective_commit_idempotent",
                    extra={
                        "operation": "commit",
                        "run_id": run_id,
                        "owner_id": owner.value,
                        "operation_id": batch.operation_id,
                        "revision": receipt.revision,
                        "status": "idempotent",
                    },
                )
                return receipt

            current_revision = await self._max_revision(session)
            self._revision = current_revision
            if (
                batch.expected_revision is not None
                and batch.expected_revision != current_revision
            ):
                _LOG.warning(
                    "subjective_commit_conflict",
                    extra={
                        "operation": "commit",
                        "run_id": run_id,
                        "owner_id": owner.value,
                        "operation_id": batch.operation_id,
                        "expected_revision": batch.expected_revision,
                        "actual_revision": current_revision,
                        "reason_code": SubjectiveStateErrorCode.CONFLICT.value,
                    },
                )
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.CONFLICT,
                    run_id=run_id,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                )

            self._prevalidate(batch)

            _LOG.debug(
                "subjective_commit_start",
                extra={
                    "operation": "commit",
                    "run_id": run_id,
                    "owner_id": owner.value,
                    "operation_id": batch.operation_id,
                    "expected_revision": batch.expected_revision,
                    "tick": batch.logical_tick,
                    "memory_write_count": len(batch.memory_writes),
                    "memory_access_count": len(batch.memory_accesses),
                    "reconstruction_count": len(batch.reconstructions),
                    "belief_revision_count": len(batch.belief_revisions),
                    "relationship_revision_count": len(batch.relationship_revisions),
                    "status": "start",
                },
            )

            belief_activated = 0
            belief_retired = 0
            try:
                memory_result = await self._memory.apply_in_session(
                    session,
                    MemoryMutationBatch(
                        writes=batch.memory_writes,
                        accesses=batch.memory_accesses,
                        reconstructions=batch.reconstructions,
                        operation_id=batch.operation_id,
                    ),
                    commit=False,
                )
                for belief_request in batch.belief_revisions:
                    created, retired = await self._apply_belief_revision(
                        session, belief_request
                    )
                    if created:
                        belief_activated += 1
                    if retired:
                        belief_retired += 1
                for relationship_request in batch.relationship_revisions:
                    await self._apply_relationship_revision(
                        session, relationship_request
                    )

                new_revision = current_revision + 1
                receipt = SubjectiveApplyReceipt(
                    operation_id=batch.operation_id,
                    revision=new_revision,
                    memory_written_count=int(memory_result.written_count),
                    memory_access_count=int(memory_result.access_applied_count),
                    reconstruction_written_count=int(
                        memory_result.reconstruction_written_count
                    ),
                    belief_revision_count=len(batch.belief_revisions),
                    relationship_revision_count=len(batch.relationship_revisions),
                    belief_activated_count=belief_activated,
                    belief_retired_count=belief_retired,
                    idempotent=False,
                )
                session.add(
                    SubjectiveOperationOrm(
                        run_id=run_id,
                        owner_id=owner.value,
                        operation_id=batch.operation_id,
                        fingerprint=fingerprint,
                        revision=new_revision,
                        logical_tick=batch.logical_tick,
                        memory_written_count=receipt.memory_written_count,
                        belief_revision_count=receipt.belief_revision_count,
                        relationship_revision_count=(
                            receipt.relationship_revision_count
                        ),
                    )
                )
                await session.commit()
            except SubjectiveStateError:
                raise
            except MemoryServiceError:
                _LOG.error(
                    "subjective_commit_adapter_failed",
                    extra={
                        "operation": "commit",
                        "run_id": run_id,
                        "owner_id": owner.value,
                        "operation_id": batch.operation_id,
                        "adapter": "memory",
                        "reason_code": SubjectiveStateErrorCode.ADAPTER_FAILED.value,
                    },
                )
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.ADAPTER_FAILED,
                    run_id=run_id,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="memory",
                ) from None
            except IntegrityError:
                _LOG.error(
                    "subjective_commit_adapter_failed",
                    extra={
                        "operation": "commit",
                        "run_id": run_id,
                        "owner_id": owner.value,
                        "operation_id": batch.operation_id,
                        "adapter": "persistence",
                        "reason_code": SubjectiveStateErrorCode.ADAPTER_FAILED.value,
                    },
                )
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.ADAPTER_FAILED,
                    run_id=run_id,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="persistence",
                ) from None
            except Exception as exc:
                adapter = type(exc).__module__.split(".")[0]
                _LOG.error(
                    "subjective_commit_adapter_failed",
                    extra={
                        "operation": "commit",
                        "run_id": run_id,
                        "owner_id": owner.value,
                        "operation_id": batch.operation_id,
                        "adapter": adapter,
                        "reason_code": SubjectiveStateErrorCode.ADAPTER_FAILED.value,
                    },
                )
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.ADAPTER_FAILED,
                    run_id=run_id,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter=adapter,
                ) from None

            self._revision = receipt.revision
            _LOG.debug(
                "subjective_commit_complete",
                extra={
                    "operation": "commit",
                    "run_id": run_id,
                    "owner_id": owner.value,
                    "operation_id": batch.operation_id,
                    "revision": receipt.revision,
                    "tick": batch.logical_tick,
                    "memory_write_count": receipt.memory_written_count,
                    "belief_revision_count": receipt.belief_revision_count,
                    "relationship_revision_count": (
                        receipt.relationship_revision_count
                    ),
                    "status": "complete",
                },
            )
            if belief_activated or belief_retired:
                _LOG.info(
                    "subjective_commit_activation",
                    extra={
                        "operation": "commit",
                        "run_id": run_id,
                        "owner_id": owner.value,
                        "operation_id": batch.operation_id,
                        "belief_activated_count": belief_activated,
                        "belief_retired_count": belief_retired,
                    },
                )
            return receipt

    def _prevalidate(self, batch: SubjectiveMutationBatch) -> None:
        owner = self._scope.owner_id
        for write in batch.memory_writes:
            if write.owner_id != owner:
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.OWNERSHIP,
                    run_id=self._scope.run_id.value,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="memory",
                )
            if write.created_tick != batch.logical_tick:
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.INVALID_REQUEST,
                    run_id=self._scope.run_id.value,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="memory",
                )
        for reconstruction in batch.reconstructions:
            if reconstruction.owner_id != owner:
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.OWNERSHIP,
                    run_id=self._scope.run_id.value,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="memory",
                )
        for belief_request in batch.belief_revisions:
            if belief_request.owner_id != owner:
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.OWNERSHIP,
                    run_id=self._scope.run_id.value,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="belief",
                )
            if belief_request.logical_tick != batch.logical_tick:
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.INVALID_REQUEST,
                    run_id=self._scope.run_id.value,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="belief",
                )
        for relationship_request in batch.relationship_revisions:
            if relationship_request.source_id != owner:
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.OWNERSHIP,
                    run_id=self._scope.run_id.value,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="relationship",
                )
            if relationship_request.logical_tick != batch.logical_tick:
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.INVALID_REQUEST,
                    run_id=self._scope.run_id.value,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="relationship",
                )

    async def _max_revision(self, session: AsyncSession) -> int:
        stmt = select(func.max(SubjectiveOperationOrm.revision)).where(
            SubjectiveOperationOrm.run_id == self._scope.run_id.value,
            SubjectiveOperationOrm.owner_id == self._scope.owner_id.value,
        )
        value = (await session.execute(stmt)).scalar_one_or_none()
        return 0 if value is None else int(value)

    async def _apply_belief_revision(
        self, session: AsyncSession, request: BeliefRevisionRequest
    ) -> tuple[bool, bool]:
        belief_id = request.belief_id or belief_id_for_claim(
            owner_id=request.owner_id, claim=request.claim
        )
        prior = await self._load_belief_history(session, belief_id)
        if (
            request.expected_revision_ordinal is not None
            and prior is not None
            and prior.belief.revision_ordinal != request.expected_revision_ordinal
        ):
            _LOG.warning(
                "subjective_belief_conflict",
                extra={
                    "operation": "commit",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "belief_id": belief_id.value,
                    "reason_code": SubjectiveStateErrorCode.CONFLICT.value,
                },
            )
            raise SubjectiveStateError(
                SubjectiveStateErrorCode.CONFLICT,
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
                operation_id=request.operation_id,
                adapter="belief",
            )
        try:
            history, created, retired, _material = merge_revision(
                owner_id=request.owner_id,
                claim=request.claim,
                new_evidence=request.evidence,
                prior=prior,
                logical_tick=request.logical_tick,
                operation_id=request.operation_id,
                policy=self._belief_policy,
            )
        except ValueError:
            _LOG.error(
                "subjective_belief_rejected",
                extra={
                    "operation": "commit",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "belief_id": belief_id.value,
                    "reason_code": SubjectiveStateErrorCode.ADAPTER_FAILED.value,
                },
            )
            raise SubjectiveStateError(
                SubjectiveStateErrorCode.ADAPTER_FAILED,
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
                operation_id=request.operation_id,
                adapter="belief",
            ) from None
        await self._persist_belief_history(session, history, prior=prior)
        return created, retired

    async def _load_belief_history(
        self, session: AsyncSession, belief_id: BeliefId
    ) -> SemanticBeliefHistory | None:
        head = await session.get(
            SemanticBeliefOrm,
            (
                self._scope.run_id.value,
                self._scope.owner_id.value,
                belief_id.value,
            ),
        )
        if head is None:
            return None
        rev_rows = list(
            (
                await session.execute(
                    select(SemanticBeliefRevisionOrm)
                    .where(
                        SemanticBeliefRevisionOrm.run_id == self._scope.run_id.value,
                        SemanticBeliefRevisionOrm.owner_id
                        == self._scope.owner_id.value,
                        SemanticBeliefRevisionOrm.belief_id == belief_id.value,
                    )
                    .order_by(SemanticBeliefRevisionOrm.ordinal)
                )
            )
            .scalars()
            .all()
        )
        if not rev_rows:
            return None
        ev_rows = list(
            (
                await session.execute(
                    select(SemanticBeliefEvidenceOrm)
                    .where(
                        SemanticBeliefEvidenceOrm.run_id == self._scope.run_id.value,
                        SemanticBeliefEvidenceOrm.owner_id
                        == self._scope.owner_id.value,
                        SemanticBeliefEvidenceOrm.belief_id == belief_id.value,
                    )
                    .order_by(
                        SemanticBeliefEvidenceOrm.revision_id,
                        SemanticBeliefEvidenceOrm.ordinal,
                    )
                )
            )
            .scalars()
            .all()
        )
        evidence_by_rev: dict[str, list[SemanticBeliefEvidenceOrm]] = {}
        for evidence_row in ev_rows:
            evidence_by_rev.setdefault(evidence_row.revision_id, []).append(
                evidence_row
            )

        revisions: list[BeliefRevision] = []
        for rev_row in rev_rows:
            claim = _decode_claim_json(rev_row.claim_canonical)
            evidence = _evidence_bundle_from_rows(
                evidence_by_rev.get(rev_row.revision_id, [])
            )
            revisions.append(
                BeliefRevision(
                    revision_id=BeliefRevisionId(rev_row.revision_id),
                    belief_id=BeliefId(rev_row.belief_id),
                    owner_id=AgentId(rev_row.owner_id),
                    ordinal=int(rev_row.ordinal),
                    logical_tick=int(rev_row.logical_tick),
                    claim=claim,
                    confidence=BeliefConfidenceState(
                        confidence=float(rev_row.confidence),
                        support_mass=float(rev_row.support_mass),
                        contradiction_mass=float(rev_row.contradiction_mass),
                    ),
                    evidence=evidence,
                    activation_state=BeliefActivationState(rev_row.activation_state),
                    policy=BeliefPolicyRef(
                        policy_id=rev_row.policy_id, version=rev_row.policy_version
                    ),
                    previous_revision_id=(
                        None
                        if rev_row.previous_revision_id is None
                        else BeliefRevisionId(rev_row.previous_revision_id)
                    ),
                )
            )
        belief = SemanticBelief(
            belief_id=BeliefId(head.belief_id),
            owner_id=AgentId(head.owner_id),
            claim=_claim_from_belief_row(head),
            confidence=BeliefConfidenceState(
                confidence=float(head.confidence),
                support_mass=float(head.support_mass),
                contradiction_mass=float(head.contradiction_mass),
            ),
            activation_state=BeliefActivationState(head.activation_state),
            current_revision_id=BeliefRevisionId(head.current_revision_id),
            revision_ordinal=int(head.revision_ordinal),
            created_tick=int(head.created_tick),
            updated_tick=int(head.updated_tick),
            policy=BeliefPolicyRef(
                policy_id=head.policy_id, version=head.policy_version
            ),
            evidence_support_count=int(head.evidence_support_count),
            evidence_contradiction_count=int(head.evidence_contradiction_count),
        )
        return SemanticBeliefHistory(belief=belief, revisions=tuple(revisions))

    async def _persist_belief_history(
        self,
        session: AsyncSession,
        history: SemanticBeliefHistory,
        *,
        prior: SemanticBeliefHistory | None,
    ) -> None:
        belief = history.belief
        claim_cols = _belief_claim_columns(belief.claim)
        values = {
            "run_id": self._scope.run_id.value,
            "owner_id": self._scope.owner_id.value,
            "belief_id": belief.belief_id.value,
            **claim_cols,
            "confidence": belief.confidence.confidence,
            "support_mass": belief.confidence.support_mass,
            "contradiction_mass": belief.confidence.contradiction_mass,
            "activation_state": belief.activation_state.value,
            "current_revision_id": belief.current_revision_id.value,
            "revision_ordinal": belief.revision_ordinal,
            "created_tick": belief.created_tick,
            "updated_tick": belief.updated_tick,
            "policy_id": belief.policy.policy_id,
            "policy_version": belief.policy.version,
            "evidence_support_count": belief.evidence_support_count,
            "evidence_contradiction_count": belief.evidence_contradiction_count,
        }
        stmt = pg_insert(SemanticBeliefOrm).values(**values)
        update_cols = {
            key: stmt.excluded[key]
            for key in values
            if key not in ("run_id", "owner_id", "belief_id", "created_tick")
        }
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["run_id", "owner_id", "belief_id"],
                set_=update_cols,
            )
        )
        await session.flush()

        new_revision = history.revisions[-1]
        if prior is not None and prior.belief.current_revision_id == (
            new_revision.revision_id
        ):
            return
        session.add(
            SemanticBeliefRevisionOrm(
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
                belief_id=new_revision.belief_id.value,
                revision_id=new_revision.revision_id.value,
                ordinal=new_revision.ordinal,
                logical_tick=new_revision.logical_tick,
                activation_state=new_revision.activation_state.value,
                confidence=new_revision.confidence.confidence,
                support_mass=new_revision.confidence.support_mass,
                contradiction_mass=new_revision.confidence.contradiction_mass,
                previous_revision_id=(
                    None
                    if new_revision.previous_revision_id is None
                    else new_revision.previous_revision_id.value
                ),
                policy_id=new_revision.policy.policy_id,
                policy_version=new_revision.policy.version,
                claim_canonical=_encode_claim_json(new_revision.claim),
            )
        )
        await session.flush()
        for item in (
            *new_revision.evidence.supporting,
            *new_revision.evidence.contradicting,
        ):
            session.add(
                SemanticBeliefEvidenceOrm(
                    run_id=self._scope.run_id.value,
                    owner_id=self._scope.owner_id.value,
                    belief_id=new_revision.belief_id.value,
                    revision_id=new_revision.revision_id.value,
                    ordinal=item.ordinal,
                    memory_id=item.memory_id.value,
                    lineage_root_id=item.lineage_root_id.value,
                    stance=item.stance.value,
                    contribution=item.contribution,
                    **applied_factors_to_columns(item.applied_factors),
                )
            )
        await session.flush()

    async def _apply_relationship_revision(
        self, session: AsyncSession, request: RelationshipRevisionRequest
    ) -> None:
        relationship_id = profile_id_for(
            source_id=request.source_id, target_id=request.target_id
        )
        prior = await self._load_relationship_history(session, relationship_id)
        if (
            request.expected_revision_ordinal is not None
            and prior is not None
            and prior.profile.revision_ordinal != request.expected_revision_ordinal
        ):
            _LOG.warning(
                "subjective_relationship_conflict",
                extra={
                    "operation": "commit",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "relationship_id": relationship_id.value,
                    "reason_code": SubjectiveStateErrorCode.CONFLICT.value,
                },
            )
            raise SubjectiveStateError(
                SubjectiveStateErrorCode.CONFLICT,
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
                operation_id=request.operation_id,
                adapter="relationship",
            )
        try:
            history, _created, _changed, _evidence = merge_relationship_revision(
                source_id=request.source_id,
                target_id=request.target_id,
                signals=request.signals,
                prior=prior,
                logical_tick=request.logical_tick,
                operation_id=request.operation_id,
                policy=self._relationship_policy,
            )
        except ValueError:
            _LOG.error(
                "subjective_relationship_rejected",
                extra={
                    "operation": "commit",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reason_code": SubjectiveStateErrorCode.ADAPTER_FAILED.value,
                },
            )
            raise SubjectiveStateError(
                SubjectiveStateErrorCode.ADAPTER_FAILED,
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
                operation_id=request.operation_id,
                adapter="relationship",
            ) from None
        await self._persist_relationship_history(session, history, prior=prior)

    async def _load_relationship_history(
        self, session: AsyncSession, relationship_id: RelationshipId
    ) -> RelationshipHistory | None:
        head = await session.get(
            DirectedRelationshipOrm,
            (
                self._scope.run_id.value,
                self._scope.owner_id.value,
                relationship_id.value,
            ),
        )
        if head is None:
            return None
        rev_rows = list(
            (
                await session.execute(
                    select(RelationshipRevisionOrm)
                    .where(
                        RelationshipRevisionOrm.run_id == self._scope.run_id.value,
                        RelationshipRevisionOrm.source_id == self._scope.owner_id.value,
                        RelationshipRevisionOrm.relationship_id
                        == relationship_id.value,
                    )
                    .order_by(RelationshipRevisionOrm.ordinal)
                )
            )
            .scalars()
            .all()
        )
        if not rev_rows:
            return None
        dim_rows = list(
            (
                await session.execute(
                    select(RelationshipDimensionStateOrm).where(
                        RelationshipDimensionStateOrm.run_id
                        == self._scope.run_id.value,
                        RelationshipDimensionStateOrm.source_id
                        == self._scope.owner_id.value,
                        RelationshipDimensionStateOrm.relationship_id
                        == relationship_id.value,
                    )
                )
            )
            .scalars()
            .all()
        )
        ev_rows = list(
            (
                await session.execute(
                    select(RelationshipDimensionEvidenceOrm)
                    .where(
                        RelationshipDimensionEvidenceOrm.run_id
                        == self._scope.run_id.value,
                        RelationshipDimensionEvidenceOrm.source_id
                        == self._scope.owner_id.value,
                        RelationshipDimensionEvidenceOrm.relationship_id
                        == relationship_id.value,
                    )
                    .order_by(
                        RelationshipDimensionEvidenceOrm.revision_id,
                        RelationshipDimensionEvidenceOrm.dimension,
                        RelationshipDimensionEvidenceOrm.ordinal,
                    )
                )
            )
            .scalars()
            .all()
        )
        dims_by_rev: dict[str, list[RelationshipDimensionStateOrm]] = {}
        for dim_row in dim_rows:
            dims_by_rev.setdefault(dim_row.revision_id, []).append(dim_row)
        evidence_by_key: dict[
            tuple[str, str], list[RelationshipDimensionEvidenceOrm]
        ] = {}
        for evidence_row in ev_rows:
            evidence_by_key.setdefault(
                (evidence_row.revision_id, evidence_row.dimension), []
            ).append(evidence_row)

        revisions: list[RelationshipRevision] = []
        for rev_row in rev_rows:
            dimensions = _dimensions_from_rows(
                dims_by_rev.get(rev_row.revision_id, []),
                evidence_by_key,
                revision_id=rev_row.revision_id,
            )
            revisions.append(
                RelationshipRevision(
                    revision_id=RelationshipRevisionId(rev_row.revision_id),
                    relationship_id=RelationshipId(rev_row.relationship_id),
                    source_id=AgentId(rev_row.source_id),
                    target_id=AgentId(rev_row.target_id),
                    ordinal=int(rev_row.ordinal),
                    logical_tick=int(rev_row.logical_tick),
                    dimensions=dimensions,
                    activation_state=RelationshipActivationState(
                        rev_row.activation_state
                    ),
                    policy=RelationshipPolicyRef(
                        policy_id=rev_row.policy_id, version=rev_row.policy_version
                    ),
                    previous_revision_id=(
                        None
                        if rev_row.previous_revision_id is None
                        else RelationshipRevisionId(rev_row.previous_revision_id)
                    ),
                )
            )
        head_dims = revisions[-1].dimensions
        profile = DirectedRelationshipProfile(
            relationship_id=RelationshipId(head.relationship_id),
            source_id=AgentId(head.source_id),
            target_id=AgentId(head.target_id),
            dimensions=head_dims,
            activation_state=RelationshipActivationState(head.activation_state),
            current_revision_id=RelationshipRevisionId(head.current_revision_id),
            revision_ordinal=int(head.revision_ordinal),
            created_tick=int(head.created_tick),
            updated_tick=int(head.updated_tick),
            policy=RelationshipPolicyRef(
                policy_id=head.policy_id, version=head.policy_version
            ),
        )
        return RelationshipHistory(profile=profile, revisions=tuple(revisions))

    async def _persist_relationship_history(
        self,
        session: AsyncSession,
        history: RelationshipHistory,
        *,
        prior: RelationshipHistory | None,
    ) -> None:
        profile = history.profile
        values = {
            "run_id": self._scope.run_id.value,
            "source_id": profile.source_id.value,
            "relationship_id": profile.relationship_id.value,
            "target_id": profile.target_id.value,
            "activation_state": profile.activation_state.value,
            "current_revision_id": profile.current_revision_id.value,
            "revision_ordinal": profile.revision_ordinal,
            "created_tick": profile.created_tick,
            "updated_tick": profile.updated_tick,
            "policy_id": profile.policy.policy_id,
            "policy_version": profile.policy.version,
        }
        stmt = pg_insert(DirectedRelationshipOrm).values(**values)
        update_cols = {
            key: stmt.excluded[key]
            for key in values
            if key not in ("run_id", "source_id", "relationship_id", "created_tick")
        }
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["run_id", "source_id", "relationship_id"],
                set_=update_cols,
            )
        )
        await session.flush()

        new_revision = history.revisions[-1]
        if prior is not None and prior.profile.current_revision_id == (
            new_revision.revision_id
        ):
            return
        session.add(
            RelationshipRevisionOrm(
                run_id=self._scope.run_id.value,
                source_id=new_revision.source_id.value,
                relationship_id=new_revision.relationship_id.value,
                revision_id=new_revision.revision_id.value,
                target_id=new_revision.target_id.value,
                ordinal=new_revision.ordinal,
                logical_tick=new_revision.logical_tick,
                activation_state=new_revision.activation_state.value,
                previous_revision_id=(
                    None
                    if new_revision.previous_revision_id is None
                    else new_revision.previous_revision_id.value
                ),
                policy_id=new_revision.policy.policy_id,
                policy_version=new_revision.policy.version,
            )
        )
        await session.flush()
        for dim in new_revision.dimensions:
            session.add(
                RelationshipDimensionStateOrm(
                    run_id=self._scope.run_id.value,
                    source_id=new_revision.source_id.value,
                    relationship_id=new_revision.relationship_id.value,
                    revision_id=new_revision.revision_id.value,
                    dimension=dim.dimension.value,
                    value=dim.value,
                    confidence=dim.confidence.confidence,
                    support_mass=dim.confidence.support_mass,
                    contradiction_mass=dim.confidence.contradiction_mass,
                    logical_tick=dim.logical_tick,
                    policy_id=dim.policy.policy_id,
                    policy_version=dim.policy.version,
                )
            )
        await session.flush()
        for dim in new_revision.dimensions:
            for item in dim.evidence:
                session.add(
                    RelationshipDimensionEvidenceOrm(
                        run_id=self._scope.run_id.value,
                        source_id=new_revision.source_id.value,
                        relationship_id=new_revision.relationship_id.value,
                        revision_id=new_revision.revision_id.value,
                        dimension=dim.dimension.value,
                        ordinal=item.ordinal,
                        memory_ref=item.memory_ref,
                        lineage_root_ref=item.lineage_root_ref,
                        contribution=item.contribution,
                    )
                )
        await session.flush()


def _evidence_bundle_from_rows(
    rows: list[SemanticBeliefEvidenceOrm],
) -> BeliefEvidenceBundle:
    supporting: list[BeliefEvidenceContribution] = []
    contradicting: list[BeliefEvidenceContribution] = []
    for row in sorted(rows, key=lambda item: item.ordinal):
        contribution = BeliefEvidenceContribution(
            memory_id=MemoryId(row.memory_id),
            stance=EvidenceStance(row.stance),
            contribution=float(row.contribution),
            ordinal=int(row.ordinal),
            lineage_root_id=MemoryId(row.lineage_root_id),
            applied_factors=applied_factors_from_row(row),
        )
        if contribution.stance is EvidenceStance.SUPPORTING:
            supporting.append(contribution)
        else:
            contradicting.append(contribution)
    return BeliefEvidenceBundle(
        supporting=tuple(supporting), contradicting=tuple(contradicting)
    )


def _dimensions_from_rows(
    dim_rows: list[RelationshipDimensionStateOrm],
    evidence_by_key: dict[tuple[str, str], list[RelationshipDimensionEvidenceOrm]],
    *,
    revision_id: str,
) -> tuple[RelationshipDimensionState, ...]:
    dimensions: list[RelationshipDimensionState] = []
    for row in dim_rows:
        evidence_rows = evidence_by_key.get((revision_id, row.dimension), [])
        evidence = tuple(
            RelationshipEvidenceItem(
                memory_ref=item.memory_ref,
                contribution=float(item.contribution),
                ordinal=int(item.ordinal),
                lineage_root_ref=item.lineage_root_ref,
            )
            for item in sorted(evidence_rows, key=lambda entry: entry.ordinal)
        )
        dimensions.append(
            RelationshipDimensionState(
                dimension=RelationshipDimension(row.dimension),
                value=float(row.value),
                confidence=RelationshipConfidence(
                    confidence=float(row.confidence),
                    support_mass=float(row.support_mass),
                    contradiction_mass=float(row.contradiction_mass),
                ),
                evidence=evidence,
                logical_tick=int(row.logical_tick),
                policy=RelationshipPolicyRef(
                    policy_id=row.policy_id, version=row.policy_version
                ),
            )
        )
    return tuple(sorted(dimensions, key=lambda item: item.dimension.value))
