"""Mypy fixtures for semantic belief contracts."""

from __future__ import annotations

from agents.models import AgentId
from memory.beliefs import (
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefEvidenceBundle,
    BeliefPolicyRef,
    BeliefRevisionId,
    BeliefRevisionRequest,
    BeliefRevisionResult,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    SemanticBelief,
    SemanticBeliefHistory,
    SemanticClaim,
)
from memory.contracts import (
    SemanticBeliefReader,
    SemanticBeliefService,
    SemanticBeliefWriter,
)
from memory.models import BeliefId


def _claim() -> SemanticClaim:
    return SemanticClaim(
        subject=ClaimSubject(
            kind=ClaimSubjectKind.AGENT,
            agent_id=AgentId("agent-1"),
        ),
        predicate="finds_food",
        value=ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )


def _belief() -> SemanticBelief:
    return SemanticBelief(
        belief_id=BeliefId("belief-1"),
        owner_id=AgentId("agent-1"),
        claim=_claim(),
        confidence=BeliefConfidenceState(
            confidence=0.5,
            support_mass=0.5,
            contradiction_mass=0.0,
        ),
        activation_state=BeliefActivationState.ACTIVE,
        current_revision_id=BeliefRevisionId("rev-0"),
        revision_ordinal=0,
        created_tick=0,
        updated_tick=0,
        policy=BeliefPolicyRef(policy_id="semantic-v1", version="1"),
        evidence_support_count=0,
        evidence_contradiction_count=0,
    )


class _StubSemanticBeliefService:
    async def revise(self, request: BeliefRevisionRequest) -> BeliefRevisionResult:
        _ = request
        return BeliefRevisionResult(
            belief_id=BeliefId("belief-1"),
            revision_id=BeliefRevisionId("rev-0"),
            revision_ordinal=0,
            activation_state=BeliefActivationState.ACTIVE,
            idempotent=False,
            created=True,
            retired=False,
            materially_changed=True,
            support_count=0,
            contradiction_count=0,
        )

    async def get(self, belief_id: BeliefId) -> SemanticBelief | None:
        _ = belief_id
        return _belief()

    async def history(self, belief_id: BeliefId) -> SemanticBeliefHistory | None:
        _ = belief_id
        return None

    async def snapshot(self) -> tuple[SemanticBelief, ...]:
        return (_belief(),)


class _StubSemanticBeliefStore:
    def snapshot(self) -> tuple[SemanticBelief, ...]:
        return ()

    def history(self, belief_id: BeliefId) -> SemanticBeliefHistory | None:
        _ = belief_id
        return None

    def write(self, history: SemanticBeliefHistory) -> None:
        _ = history


def _service_is_protocol() -> SemanticBeliefService:
    return _StubSemanticBeliefService()


def _reader_is_protocol() -> SemanticBeliefReader:
    return _StubSemanticBeliefStore()


def _writer_is_protocol() -> SemanticBeliefWriter:
    return _StubSemanticBeliefStore()


def _request() -> BeliefRevisionRequest:
    return BeliefRevisionRequest(
        owner_id=AgentId("agent-1"),
        operation_id="op-1",
        logical_tick=0,
        claim=_claim(),
        evidence=BeliefEvidenceBundle(supporting=(), contradicting=()),
        policy=BeliefPolicyRef(policy_id="semantic-v1", version="1"),
    )
