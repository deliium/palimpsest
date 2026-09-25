"""Deterministic identity appraisal from cited owner memories."""

from __future__ import annotations

import logging

import pytest

from agents.cognition import (
    IdentityAspect,
    SelfModel,
    appraise_identity,
    build_identity_claim,
)
from agents.models import AgentId, Goal, GoalHorizon, GoalId, GoalStatus
from memory.beliefs import (
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefPolicyRef,
    BeliefRevisionId,
    BeliefValueKind,
    ClaimValue,
    SemanticBelief,
)
from memory.models import (
    BeliefId,
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    WorldRevision,
)
from world.identifiers import EntityId, EventId
from world.models import LifeStatus
from world.observations import (
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)


def _self(owner: AgentId) -> SelfModel:
    return SelfModel(
        owner_id=owner,
        policy_id="self-model-projection",
        policy_version="1",
        life_status=LifeStatus.ALIVE,
        beliefs=(),
        goal_ids=(),
        confidence=1.0,
        candidate_count=0,
    )


def _memory(owner: AgentId, memory_id: str, *, tick: int, concept: str) -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=owner,
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


def _occurrence(kind: str, *, tick: int, success: bool) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=tick,
            source_event_id=EventId(f"event-{kind}-{tick}"),
        ),
        kind=kind,
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId("body-1"),
        success=success,
    )


def test_no_memory_emits_nothing(caplog: pytest.LogCaptureFixture) -> None:
    owner = AgentId("agent-1")
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.identity"):
        appraisal = appraise_identity(
            owner_id=owner,
            tick=2,
            memories=(),
            occurrences=(_occurrence("move", tick=2, success=True),),
            goals=(),
            relationships=(),
            futures=None,
            beliefs=(),
            self_model=_self(owner),
        )
    assert appraisal.requests == ()
    assert ("no_memory_evidence", 1) in appraisal.reason_counts
    assert "move" not in caplog.text


def test_success_emits_bool_true_claims_and_stable_ids() -> None:
    owner = AgentId("agent-1")
    memory = _memory(owner, "mem-1", tick=2, concept="trail")
    kwargs = dict(
        owner_id=owner,
        tick=2,
        memories=(memory,),
        occurrences=(_occurrence("move", tick=2, success=True),),
        goals=(),
        relationships=(),
        futures=None,
        beliefs=(),
        self_model=_self(owner),
    )
    first = appraise_identity(**kwargs)
    second = appraise_identity(**kwargs)
    assert [item.operation_id for item in first.requests] == [
        item.operation_id for item in second.requests
    ]
    aspects = {item.claim.predicate.split(".")[1] for item in first.requests}
    assert aspects == {"ability", "competence", "reliability"}
    for request in first.requests:
        assert request.claim.value.bool_value is True
        assert request.claim.value.kind is BeliefValueKind.BOOL
        assert request.policy.policy_id == "semantic-belief-formation"
        assert request.activation_state is None
        assert request.evidence.supporting[0].memory_id == MemoryId("mem-1")
        assert "repeated_action" not in request.claim.predicate
        assert "decision" not in request.evidence.supporting[0].memory_id.value


def test_failure_and_repeat_and_second_tick_keeps_the_claim() -> None:
    owner = AgentId("agent-1")
    memory = _memory(owner, "mem-1", tick=3, concept="move")
    failed = appraise_identity(
        owner_id=owner,
        tick=3,
        memories=(memory,),
        occurrences=(
            _occurrence("move", tick=3, success=False),
            _occurrence("move", tick=3, success=False),
        ),
        goals=(
            Goal(
                goal_id=GoalId("goal-water"),
                owner_id=owner,
                description="find water",
                priority=0.4,
                status=GoalStatus.ACTIVE,
                horizon=GoalHorizon.LONG_TERM,
            ),
        ),
        relationships=(),
        futures=None,
        beliefs=(),
        self_model=_self(owner),
    )
    predicates = {item.claim.predicate for item in failed.requests}
    assert "identity.weakness.observed_outcome.move" in predicates
    assert "identity.recurring_behavior.own_choice.move" in predicates
    assert "identity.commitment.goal_outcome.goal-water" in predicates
    assert "identity.ability.observed_outcome.move" not in predicates
    prior_claim = build_identity_claim(
        owner,
        "identity.weakness.observed_outcome.move",
        ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )
    prior = SemanticBelief(
        belief_id=BeliefId("belief-weak"),
        owner_id=owner,
        claim=prior_claim,
        confidence=BeliefConfidenceState(
            confidence=0.4, support_mass=0.4, contradiction_mass=0.0
        ),
        activation_state=BeliefActivationState.CANDIDATE,
        current_revision_id=BeliefRevisionId("rev-0"),
        revision_ordinal=0,
        created_tick=3,
        updated_tick=3,
        policy=BeliefPolicyRef(policy_id="semantic-belief-formation", version="1"),
        evidence_support_count=1,
        evidence_contradiction_count=0,
    )
    later = appraise_identity(
        owner_id=owner,
        tick=4,
        memories=(
            memory,
            _memory(owner, "mem-2", tick=4, concept="move"),
        ),
        occurrences=(_occurrence("move", tick=4, success=False),),
        goals=(),
        relationships=(),
        futures=None,
        beliefs=(prior,),
        self_model=_self(owner),
    )
    revised = next(
        item
        for item in later.requests
        if item.claim.predicate == "identity.weakness.observed_outcome.move"
    )
    assert revised.claim.value.bool_value is True
    assert revised.belief_id == BeliefId("belief-weak")
    assert revised.expected_revision_ordinal == 0
    assert {item.memory_id.value for item in revised.evidence.supporting} >= {
        "mem-2"
    }


def test_forbidden_token_is_not_requested() -> None:
    owner = AgentId("agent-1")
    appraisal = appraise_identity(
        owner_id=owner,
        tick=1,
        memories=(_memory(owner, "mem-1", tick=1, concept="trail"),),
        occurrences=(_occurrence("leader", tick=1, success=True),),
        goals=(),
        relationships=(),
        futures=None,
        beliefs=(),
        self_model=_self(owner),
    )
    assert all("leader" not in item.claim.predicate for item in appraisal.requests)
    assert ("forbidden_identity_token", 1) in appraisal.reason_counts or any(
        code == "forbidden_identity_token" for code, _count in appraisal.reason_counts
    )
    assert IdentityAspect.ABILITY.value not in {
        item.claim.predicate.split(".")[1] for item in appraisal.requests
    }
