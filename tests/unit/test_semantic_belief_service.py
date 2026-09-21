"""Unit tests for in-memory semantic belief service."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from memory.belief_formation import BeliefFormationPolicy
from memory.belief_service import BeliefFormationBatch, InMemorySemanticBeliefService
from memory.beliefs import (
    BeliefActivationState,
    BeliefEvidenceBundle,
    BeliefEvidenceContribution,
    BeliefRevisionRequest,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    EvidenceStance,
    SemanticClaim,
)
from memory.errors import BeliefServiceError, BeliefServiceErrorCode
from memory.models import (
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemoryRunId,
    MemoryScope,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    WorldRevision,
)


def _scope() -> MemoryScope:
    return MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))


def _policy() -> BeliefFormationPolicy:
    return BeliefFormationPolicy(
        policy_id="svc",
        version="1",
        min_independent_observations=2,
        activate_confidence_threshold=0.3,
    )


def _claim(text: str = "food") -> SemanticClaim:
    return SemanticClaim(
        subject=ClaimSubject(kind=ClaimSubjectKind.AGENT, agent_id=AgentId("agent-1")),
        predicate="experienced_concept",
        value=ClaimValue(kind=BeliefValueKind.TEXT, text_value=text),
    )


def _trace(memory_id: str, *, tick: int, concept: str = "food") -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept=concept),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.0,
        confidence=1.0,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION, source_tick=tick
        ),
        created_tick=tick,
        source_tick=tick,
        last_access_tick=tick,
        access_count=0,
    )


@pytest.mark.asyncio
async def test_revise_is_idempotent_for_same_operation_id() -> None:
    service = InMemorySemanticBeliefService(_scope(), policy=_policy())
    request = BeliefRevisionRequest(
        owner_id=AgentId("agent-1"),
        operation_id="op-same",
        logical_tick=1,
        claim=_claim(),
        evidence=BeliefEvidenceBundle(
            supporting=(
                BeliefEvidenceContribution(
                    memory_id=MemoryId("m-1"),
                    stance=EvidenceStance.SUPPORTING,
                    contribution=0.5,
                    ordinal=0,
                    lineage_root_id=MemoryId("m-1"),
                ),
            ),
            contradicting=(),
        ),
        policy=_policy().as_ref(),
    )
    first = await service.revise(request)
    second = await service.revise(request)
    assert first.belief_id == second.belief_id
    assert second.idempotent is True
    assert len(await service.snapshot()) == 1


@pytest.mark.asyncio
async def test_conflicting_operation_id_reuse_fails() -> None:
    service = InMemorySemanticBeliefService(_scope(), policy=_policy())
    base = dict(
        owner_id=AgentId("agent-1"),
        operation_id="op-conflict",
        logical_tick=1,
        evidence=BeliefEvidenceBundle(
            supporting=(
                BeliefEvidenceContribution(
                    memory_id=MemoryId("m-1"),
                    stance=EvidenceStance.SUPPORTING,
                    contribution=0.5,
                    ordinal=0,
                    lineage_root_id=MemoryId("m-1"),
                ),
            ),
            contradicting=(),
        ),
        policy=_policy().as_ref(),
    )
    await service.revise(BeliefRevisionRequest(claim=_claim("food"), **base))
    with pytest.raises(BeliefServiceError) as excinfo:
        await service.revise(BeliefRevisionRequest(claim=_claim("water"), **base))
    assert excinfo.value.code is BeliefServiceErrorCode.IDEMPOTENCY_CONFLICT


@pytest.mark.asyncio
async def test_form_from_traces_activates_after_threshold(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = InMemorySemanticBeliefService(_scope(), policy=_policy())
    batch = BeliefFormationBatch(
        owner_id=AgentId("agent-1"),
        operation_id="form-1",
        logical_tick=5,
        traces=(_trace("m-1", tick=1), _trace("m-2", tick=2)),
    )
    with caplog.at_level(logging.DEBUG, logger="memory.belief_service"):
        results = await service.form_from_traces(batch)
    assert results
    active = [
        item
        for item in await service.snapshot()
        if item.activation_state is BeliefActivationState.ACTIVE
    ]
    assert active
    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "food" not in joined
    for record in caplog.records:
        extra = getattr(record, "__dict__", {})
        for key, value in extra.items():
            if key in {"msg", "args", "message"}:
                continue
            assert "food" not in str(value)


@pytest.mark.asyncio
async def test_foreign_owner_rejected() -> None:
    service = InMemorySemanticBeliefService(_scope(), policy=_policy())
    with pytest.raises(BeliefServiceError) as excinfo:
        await service.revise(
            BeliefRevisionRequest(
                owner_id=AgentId("agent-2"),
                operation_id="op-x",
                logical_tick=1,
                claim=_claim(),
                evidence=BeliefEvidenceBundle(supporting=(), contradicting=()),
                policy=_policy().as_ref(),
            )
        )
    assert excinfo.value.code is BeliefServiceErrorCode.OWNERSHIP
    assert "food" not in str(excinfo.value)
