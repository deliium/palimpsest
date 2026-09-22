"""Owner-bound in-memory semantic belief service.

Deterministic, wall-clock-free, and metadata-only in operational logs. Never logs
claim text, typed values, memory contents, or evidence payloads.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from agents.models import AgentId
from memory.belief_formation import (
    DEFAULT_BELIEF_FORMATION_POLICY,
    BeliefEvidenceCandidate,
    BeliefFormationPolicy,
    belief_id_for_claim,
    bundle_from_candidates,
    extract_evidence_candidates,
    merge_revision,
)
from memory.beliefs import (
    BeliefActivationState,
    BeliefRevisionRequest,
    BeliefRevisionResult,
    SemanticBelief,
    SemanticBeliefHistory,
    SemanticBeliefStore,
    SemanticClaim,
    canonical_claim_identity,
    canonical_subject_predicate_key,
)
from memory.errors import BeliefServiceError, BeliefServiceErrorCode
from memory.models import BeliefId, MemoryScope, MemoryTrace

__all__ = [
    "BeliefFormationBatch",
    "BeliefServiceError",
    "BeliefServiceErrorCode",
    "InMemorySemanticBeliefService",
]


class _SemanticBeliefServiceReader:
    """Sync ``SemanticBeliefReader`` facade over an in-memory belief service."""

    __slots__ = ("_service",)

    def __init__(self, service: InMemorySemanticBeliefService) -> None:
        self._service = service

    def snapshot(self) -> tuple[SemanticBelief, ...]:
        return self._service.sync_snapshot()

    def history(self, belief_id: BeliefId) -> SemanticBeliefHistory | None:
        return self._service.history_sync(belief_id)

_LOG: Final[logging.Logger] = logging.getLogger("memory.belief_service")


class BeliefFormationBatch:
    """Owner-scoped batch of traces proposing belief revisions."""

    __slots__ = ("logical_tick", "operation_id", "owner_id", "traces")

    def __init__(
        self,
        *,
        owner_id: AgentId,
        operation_id: str,
        logical_tick: int,
        traces: Sequence[MemoryTrace],
    ) -> None:
        from world.identifiers import require_bounded_text, require_exact_nonneg_int

        if type(owner_id) is not AgentId:
            raise TypeError("BeliefFormationBatch.owner_id: invalid_type")
        self.owner_id = owner_id
        self.operation_id = require_bounded_text(
            "BeliefFormationBatch.operation_id", operation_id, max_length=128
        )
        self.logical_tick = require_exact_nonneg_int(
            "BeliefFormationBatch.logical_tick", logical_tick
        )
        if isinstance(traces, (str, bytes, bytearray)) or not isinstance(
            traces, Sequence
        ):
            raise TypeError("BeliefFormationBatch.traces: not_ordered_sequence")
        items = tuple(traces)
        for item in items:
            if type(item) is not MemoryTrace:
                raise TypeError("BeliefFormationBatch.traces: invalid_item_type")
        self.traces = items

    def __repr__(self) -> str:
        return (
            f"BeliefFormationBatch(owner_id={self.owner_id.value!r}, "
            f"operation_id={self.operation_id!r}, "
            f"logical_tick={self.logical_tick}, "
            f"trace_count={len(self.traces)})"
        )


def _request_fingerprint(request: BeliefRevisionRequest) -> str:
    """Deterministic payload fingerprint for idempotency conflict detection."""
    import hashlib

    material = (
        f"{request.owner_id.value}|{request.logical_tick}|"
        f"{canonical_claim_identity(request.claim)}|"
        f"{request.evidence.total_count}|"
        f"{request.belief_id.value if request.belief_id else ''}|"
        f"{request.expected_revision_ordinal}"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class InMemorySemanticBeliefService:
    """Pure in-process semantic belief service bound to one :class:`MemoryScope`."""

    __slots__ = ("_ops", "_policy", "_scope", "_store")

    def __init__(
        self,
        scope: MemoryScope,
        *,
        policy: BeliefFormationPolicy | None = None,
    ) -> None:
        if type(scope) is not MemoryScope:
            raise TypeError("InMemorySemanticBeliefService requires MemoryScope")
        if policy is None:
            policy = DEFAULT_BELIEF_FORMATION_POLICY
        elif type(policy) is not BeliefFormationPolicy:
            raise TypeError("InMemorySemanticBeliefService: invalid_policy")
        self._scope = scope
        self._policy = policy
        self._store = SemanticBeliefStore(scope.owner_id)
        self._ops: dict[str, tuple[str, BeliefRevisionResult]] = {}
        _LOG.info(
            "belief_service_created",
            extra={
                "operation": "create",
                "run_id": scope.run_id.value,
                "owner_id": scope.owner_id.value,
                "policy_id": policy.policy_id,
                "policy_version": policy.version,
            },
        )

    @property
    def scope(self) -> MemoryScope:
        return self._scope

    @property
    def policy(self) -> BeliefFormationPolicy:
        return self._policy

    def capture_transaction_state(self) -> object:
        """Return a deep-enough copy of mutable state for copy-then-swap."""
        return (
            dict(self._store._beliefs),
            dict(self._store._histories),
            dict(self._ops),
        )

    def restore_transaction_state(self, state: object) -> None:
        """Restore mutable state captured by :meth:`capture_transaction_state`."""
        from typing import Any, cast

        beliefs, histories, ops = cast(tuple[Any, Any, Any], state)
        self._store._beliefs = dict(beliefs)
        self._store._histories = dict(histories)
        self._ops = dict(ops)

    async def revise(self, request: BeliefRevisionRequest) -> BeliefRevisionResult:
        if type(request) is not BeliefRevisionRequest:
            _LOG.error(
                "belief_revise_invalid",
                extra={
                    "operation": "revise",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reason_code": BeliefServiceErrorCode.INVALID_REQUEST.value,
                },
            )
            raise BeliefServiceError(BeliefServiceErrorCode.INVALID_REQUEST)
        if request.owner_id != self._scope.owner_id:
            _LOG.warning(
                "belief_revise_ownership",
                extra={
                    "operation": "revise",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reason_code": BeliefServiceErrorCode.OWNERSHIP.value,
                },
            )
            raise BeliefServiceError(BeliefServiceErrorCode.OWNERSHIP)

        prior_entry = self._ops.get(request.operation_id)
        if prior_entry is not None:
            prior_fp, prior_result = prior_entry
            fingerprint = _request_fingerprint(request)
            if prior_fp != fingerprint:
                _LOG.warning(
                    "belief_revise_idempotency_conflict",
                    extra={
                        "operation": "revise",
                        "run_id": self._scope.run_id.value,
                        "owner_id": self._scope.owner_id.value,
                        "reason_code": (
                            BeliefServiceErrorCode.IDEMPOTENCY_CONFLICT.value
                        ),
                    },
                )
                raise BeliefServiceError(BeliefServiceErrorCode.IDEMPOTENCY_CONFLICT)
            _LOG.debug(
                "belief_revise_idempotent",
                extra={
                    "operation": "revise",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "belief_id": prior_result.belief_id.value,
                    "tick": request.logical_tick,
                    "policy_version": self._policy.version,
                    "support_count": prior_result.support_count,
                    "contradiction_count": prior_result.contradiction_count,
                    "status": "idempotent",
                },
            )
            return prior_result

        belief_id = request.belief_id or belief_id_for_claim(
            owner_id=request.owner_id, claim=request.claim
        )
        prior = self._store.history(belief_id)
        if (
            request.expected_revision_ordinal is not None
            and prior is not None
            and prior.belief.revision_ordinal != request.expected_revision_ordinal
        ):
            _LOG.warning(
                "belief_revise_conflict",
                extra={
                    "operation": "revise",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "belief_id": belief_id.value,
                    "reason_code": BeliefServiceErrorCode.CONFLICT.value,
                },
            )
            raise BeliefServiceError(BeliefServiceErrorCode.CONFLICT)

        _LOG.debug(
            "belief_revise_start",
            extra={
                "operation": "revise",
                "run_id": self._scope.run_id.value,
                "owner_id": self._scope.owner_id.value,
                "belief_id": belief_id.value,
                "tick": request.logical_tick,
                "policy_version": self._policy.version,
                "support_count": len(request.evidence.supporting),
                "contradiction_count": len(request.evidence.contradicting),
                "status": "start",
            },
        )
        try:
            history, created, retired, materially_changed = merge_revision(
                owner_id=request.owner_id,
                claim=request.claim,
                new_evidence=request.evidence,
                prior=prior,
                logical_tick=request.logical_tick,
                operation_id=request.operation_id,
                policy=self._policy,
            )
        except ValueError as exc:
            reason = str(exc)
            code = BeliefServiceErrorCode.INVALID_REQUEST
            if reason.endswith("ownership"):
                code = BeliefServiceErrorCode.OWNERSHIP
            elif reason.endswith("chronology"):
                code = BeliefServiceErrorCode.CHRONOLOGY
            _LOG.error(
                "belief_revise_rejected",
                extra={
                    "operation": "revise",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "belief_id": belief_id.value,
                    "reason_code": code.value,
                },
            )
            raise BeliefServiceError(code) from None

        self._store.write(history)
        result = BeliefRevisionResult(
            belief_id=history.belief.belief_id,
            revision_id=history.belief.current_revision_id,
            revision_ordinal=history.belief.revision_ordinal,
            activation_state=history.belief.activation_state,
            idempotent=False,
            created=created,
            retired=retired,
            materially_changed=materially_changed,
            support_count=history.belief.evidence_support_count,
            contradiction_count=history.belief.evidence_contradiction_count,
        )
        self._ops[request.operation_id] = (
            _request_fingerprint(request),
            BeliefRevisionResult(
                belief_id=result.belief_id,
                revision_id=result.revision_id,
                revision_ordinal=result.revision_ordinal,
                activation_state=result.activation_state,
                idempotent=True,
                created=result.created,
                retired=result.retired,
                materially_changed=result.materially_changed,
                support_count=result.support_count,
                contradiction_count=result.contradiction_count,
            ),
        )
        if (
            created
            or retired
            or materially_changed
            or (
                history.belief.activation_state is BeliefActivationState.ACTIVE
                and (
                    prior is None
                    or prior.belief.activation_state is not BeliefActivationState.ACTIVE
                )
            )
        ):
            _LOG.info(
                "belief_revise_material",
                extra={
                    "operation": "revise",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "belief_id": result.belief_id.value,
                    "tick": request.logical_tick,
                    "policy_version": self._policy.version,
                    "activation_state": result.activation_state.value,
                    "belief_created": created,
                    "belief_retired": retired,
                    "status": "material",
                },
            )
        _LOG.debug(
            "belief_revise_complete",
            extra={
                "operation": "revise",
                "run_id": self._scope.run_id.value,
                "owner_id": self._scope.owner_id.value,
                "belief_id": result.belief_id.value,
                "tick": request.logical_tick,
                "policy_version": self._policy.version,
                "support_count": result.support_count,
                "contradiction_count": result.contradiction_count,
                "status": "complete",
            },
        )
        return result

    async def form_from_traces(
        self, batch: BeliefFormationBatch
    ) -> tuple[BeliefRevisionResult, ...]:
        if type(batch) is not BeliefFormationBatch:
            raise BeliefServiceError(BeliefServiceErrorCode.INVALID_REQUEST)
        if batch.owner_id != self._scope.owner_id:
            _LOG.warning(
                "belief_form_ownership",
                extra={
                    "operation": "form_from_traces",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reason_code": BeliefServiceErrorCode.OWNERSHIP.value,
                },
            )
            raise BeliefServiceError(BeliefServiceErrorCode.OWNERSHIP)

        prior_ops = [
            (key, value)
            for key, value in self._ops.items()
            if key.startswith(f"{batch.operation_id}:")
        ]
        if prior_ops:
            ordered = tuple(
                item[1][1] for item in sorted(prior_ops, key=lambda pair: pair[0])
            )
            _LOG.debug(
                "belief_form_idempotent",
                extra={
                    "operation": "form_from_traces",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "tick": batch.logical_tick,
                    "policy_version": self._policy.version,
                    "result_count": len(ordered),
                    "status": "idempotent",
                },
            )
            return ordered

        index = {trace.memory_id: trace for trace in batch.traces}
        try:
            candidates = extract_evidence_candidates(
                batch.traces,
                owner_id=batch.owner_id,
                policy=self._policy,
                trace_index=index,
            )
        except ValueError as exc:
            code = (
                BeliefServiceErrorCode.OWNERSHIP
                if str(exc).endswith("ownership")
                else BeliefServiceErrorCode.INVALID_REQUEST
            )
            _LOG.error(
                "belief_form_rejected",
                extra={
                    "operation": "form_from_traces",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reason_code": code.value,
                },
            )
            raise BeliefServiceError(code) from None

        # Group by subject/predicate; pick canonical claim = first by identity sort.
        groups: dict[str, list[BeliefEvidenceCandidate]] = {}
        claim_for_key: dict[str, SemanticClaim] = {}
        for candidate in candidates:
            key = canonical_subject_predicate_key(candidate.claim)
            groups.setdefault(key, []).append(candidate)
            existing = claim_for_key.get(key)
            if existing is None:
                claim_for_key[key] = candidate.claim
            else:
                # Prefer the lexicographically first full identity as head claim.
                if canonical_claim_identity(candidate.claim) < canonical_claim_identity(
                    existing
                ):
                    claim_for_key[key] = candidate.claim

        results: list[BeliefRevisionResult] = []
        for index_key, key in enumerate(sorted(groups)):
            claim = claim_for_key[key]
            evidence = bundle_from_candidates(groups[key], target_claim=claim)
            if evidence.total_count == 0:
                continue
            belief_key = belief_id_for_claim(owner_id=batch.owner_id, claim=claim)
            op_id = f"{batch.operation_id}:{index_key}:{belief_key.value}"
            result = await self.revise(
                BeliefRevisionRequest(
                    owner_id=batch.owner_id,
                    operation_id=op_id,
                    logical_tick=batch.logical_tick,
                    claim=claim,
                    evidence=evidence,
                    policy=self._policy.as_ref(),
                    belief_id=belief_key,
                )
            )
            results.append(result)
        return tuple(results)

    async def get(self, belief_id: BeliefId) -> SemanticBelief | None:
        if type(belief_id) is not BeliefId:
            raise BeliefServiceError(BeliefServiceErrorCode.INVALID_REQUEST)
        for belief in self._store.snapshot():
            if belief.belief_id == belief_id:
                return belief
        return None

    async def history(self, belief_id: BeliefId) -> SemanticBeliefHistory | None:
        if type(belief_id) is not BeliefId:
            raise BeliefServiceError(BeliefServiceErrorCode.INVALID_REQUEST)
        return self._store.history(belief_id)

    async def snapshot(self) -> tuple[SemanticBelief, ...]:
        return self.sync_snapshot()

    def sync_snapshot(self) -> tuple[SemanticBelief, ...]:
        """Synchronous belief snapshot for perspective assembly."""
        return self._store.snapshot()

    def history_sync(self, belief_id: BeliefId) -> SemanticBeliefHistory | None:
        """Synchronous history lookup for ``SemanticBeliefReader`` adapters."""
        if type(belief_id) is not BeliefId:
            raise BeliefServiceError(BeliefServiceErrorCode.INVALID_REQUEST)
        return self._store.history(belief_id)

    def as_reader(self) -> _SemanticBeliefServiceReader:
        """Return a sync ``SemanticBeliefReader`` bound to this service."""
        return _SemanticBeliefServiceReader(self)
