"""Owner-bound in-memory directed relationship service.

Metadata-only operational logs: source/target IDs, ticks, policy versions,
counts, and stable reason codes. Never logs dimension values or evidence.
"""

from __future__ import annotations

import hashlib
import logging
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from social.models import RelationshipId
from social.relationships import (
    DEFAULT_RELATIONSHIP_POLICY,
    DirectedRelationshipProfile,
    RelationshipFormationPolicy,
    RelationshipHistory,
    RelationshipProfileStore,
    RelationshipRevisionRequest,
    RelationshipRevisionResult,
    merge_relationship_revision,
    profile_id_for,
)

__all__ = [
    "InMemoryRelationshipService",
    "RelationshipServiceError",
    "RelationshipServiceErrorCode",
]

_LOG: Final[logging.Logger] = logging.getLogger("social.service")


class RelationshipServiceErrorCode(StrEnum):
    CONFLICT = "conflict"
    OWNERSHIP = "ownership"
    SELF_TARGET = "self_target"
    INVALID_REQUEST = "invalid_request"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    CHRONOLOGY = "chronology"


class RelationshipServiceError(ValueError):
    def __init__(self, code: RelationshipServiceErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def _fingerprint(request: RelationshipRevisionRequest) -> str:
    parts = [
        request.source_id.value,
        request.target_id.value,
        str(request.logical_tick),
        str(len(request.signals)),
    ]
    for signal in request.signals:
        parts.append(
            f"{signal.kind.value}:{signal.memory_ref}:{signal.lineage_root_ref}"
        )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


class InMemoryRelationshipService:
    """Directed relationship service bound to one source owner."""

    __slots__ = ("_ops", "_policy", "_source_id", "_store")

    def __init__(
        self,
        source_id: AgentId,
        *,
        policy: RelationshipFormationPolicy | None = None,
    ) -> None:
        if type(source_id) is not AgentId:
            raise TypeError("InMemoryRelationshipService: invalid_source")
        if policy is None:
            policy = DEFAULT_RELATIONSHIP_POLICY
        elif type(policy) is not RelationshipFormationPolicy:
            raise TypeError("InMemoryRelationshipService: invalid_policy")
        self._source_id = source_id
        self._policy = policy
        self._store = RelationshipProfileStore(source_id)
        self._ops: dict[str, tuple[str, RelationshipRevisionResult]] = {}
        _LOG.info(
            "relationship_service_created",
            extra={
                "operation": "create",
                "owner_id": source_id.value,
                "policy_id": policy.policy_id,
                "policy_version": policy.version,
            },
        )

    @property
    def source_id(self) -> AgentId:
        return self._source_id

    def capture_transaction_state(self) -> object:
        """Return a deep-enough copy of mutable state for copy-then-swap."""
        return (
            dict(self._store._profiles),
            dict(self._store._histories),
            dict(self._ops),
        )

    def restore_transaction_state(self, state: object) -> None:
        """Restore mutable state captured by :meth:`capture_transaction_state`."""
        from typing import Any, cast

        profiles, histories, ops = cast(tuple[Any, Any, Any], state)
        self._store._profiles = dict(profiles)
        self._store._histories = dict(histories)
        self._ops = dict(ops)

    async def revise(
        self, request: RelationshipRevisionRequest
    ) -> RelationshipRevisionResult:
        if type(request) is not RelationshipRevisionRequest:
            raise RelationshipServiceError(RelationshipServiceErrorCode.INVALID_REQUEST)
        if request.source_id != self._source_id:
            _LOG.warning(
                "relationship_revise_ownership",
                extra={
                    "operation": "revise",
                    "owner_id": self._source_id.value,
                    "reason_code": RelationshipServiceErrorCode.OWNERSHIP.value,
                },
            )
            raise RelationshipServiceError(RelationshipServiceErrorCode.OWNERSHIP)
        if request.source_id == request.target_id:
            raise RelationshipServiceError(RelationshipServiceErrorCode.SELF_TARGET)

        prior_entry = self._ops.get(request.operation_id)
        fingerprint = _fingerprint(request)
        if prior_entry is not None:
            prior_fp, prior_result = prior_entry
            if prior_fp != fingerprint:
                _LOG.warning(
                    "relationship_revise_idempotency_conflict",
                    extra={
                        "operation": "revise",
                        "owner_id": self._source_id.value,
                        "reason_code": (
                            RelationshipServiceErrorCode.IDEMPOTENCY_CONFLICT.value
                        ),
                    },
                )
                raise RelationshipServiceError(
                    RelationshipServiceErrorCode.IDEMPOTENCY_CONFLICT
                )
            _LOG.debug(
                "relationship_revise_idempotent",
                extra={
                    "operation": "revise",
                    "owner_id": self._source_id.value,
                    "target_id": request.target_id.value,
                    "tick": request.logical_tick,
                    "policy_version": self._policy.version,
                    "status": "idempotent",
                },
            )
            return prior_result

        relationship_id = profile_id_for(
            source_id=request.source_id, target_id=request.target_id
        )
        prior = self._store.history(relationship_id)
        if (
            request.expected_revision_ordinal is not None
            and prior is not None
            and prior.profile.revision_ordinal != request.expected_revision_ordinal
        ):
            raise RelationshipServiceError(RelationshipServiceErrorCode.CONFLICT)

        _LOG.debug(
            "relationship_revise_start",
            extra={
                "operation": "revise",
                "owner_id": self._source_id.value,
                "target_id": request.target_id.value,
                "tick": request.logical_tick,
                "policy_version": self._policy.version,
                "evidence_count": len(request.signals),
                "status": "start",
            },
        )
        try:
            history, created, changed, evidence_count = merge_relationship_revision(
                source_id=request.source_id,
                target_id=request.target_id,
                signals=request.signals,
                prior=prior,
                logical_tick=request.logical_tick,
                operation_id=request.operation_id,
                policy=self._policy,
            )
        except ValueError as exc:
            reason = str(exc)
            code = RelationshipServiceErrorCode.INVALID_REQUEST
            if reason.endswith("chronology"):
                code = RelationshipServiceErrorCode.CHRONOLOGY
            elif reason.endswith("self_target"):
                code = RelationshipServiceErrorCode.SELF_TARGET
            _LOG.error(
                "relationship_revise_rejected",
                extra={
                    "operation": "revise",
                    "owner_id": self._source_id.value,
                    "reason_code": code.value,
                },
            )
            raise RelationshipServiceError(code) from None

        self._store.write(history)
        result = RelationshipRevisionResult(
            relationship_id=history.profile.relationship_id,
            revision_id=history.profile.current_revision_id,
            revision_ordinal=history.profile.revision_ordinal,
            changed_dimension_count=changed,
            evidence_count=evidence_count,
            idempotent=False,
            created=created,
            activation_state=history.profile.activation_state,
        )
        self._ops[request.operation_id] = (
            fingerprint,
            RelationshipRevisionResult(
                relationship_id=result.relationship_id,
                revision_id=result.revision_id,
                revision_ordinal=result.revision_ordinal,
                changed_dimension_count=result.changed_dimension_count,
                evidence_count=result.evidence_count,
                idempotent=True,
                created=result.created,
                activation_state=result.activation_state,
            ),
        )
        _LOG.debug(
            "relationship_revise_complete",
            extra={
                "operation": "revise",
                "owner_id": self._source_id.value,
                "target_id": request.target_id.value,
                "tick": request.logical_tick,
                "policy_version": self._policy.version,
                "changed_dimension_count": changed,
                "evidence_count": evidence_count,
                "status": "complete",
            },
        )
        return result

    async def get(
        self, relationship_id: RelationshipId
    ) -> DirectedRelationshipProfile | None:
        for profile in self._store.snapshot():
            if profile.relationship_id == relationship_id:
                return profile
        return None

    async def get_directed(
        self, *, target_id: AgentId
    ) -> DirectedRelationshipProfile | None:
        relationship_id = profile_id_for(source_id=self._source_id, target_id=target_id)
        return await self.get(relationship_id)

    async def history(
        self, relationship_id: RelationshipId
    ) -> RelationshipHistory | None:
        return self._store.history(relationship_id)

    async def snapshot(self) -> tuple[DirectedRelationshipProfile, ...]:
        return self._store.snapshot()
