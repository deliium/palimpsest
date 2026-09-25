"""Deterministic reflection-v1 pattern policy."""

from __future__ import annotations

from agents.cognition.models import GoalTransitionIntentReason
from agents.cognition.reflection import (
    DecisionOutcomeCode,
    ReflectionConclusionKind,
    ReflectionContext,
    ReflectionPatternCode,
    ReflectionPolicy,
    SubjectiveDecisionRecord,
    materialize_reflection_candidates,
)
from agents.models import (
    AgentId,
    Goal,
    GoalId,
    GoalOutcome,
    GoalOutcomeKind,
    GoalStatus,
)
from memory.beliefs import BeliefActivationState
from memory.models import (
    EntityMention,
    MemoryId,
    MemoryProvenance,
    MemoryRelation,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
    RelationEndpoint,
    RelationEndpointKind,
)
from simulation.agent_runtime import _intent_reason_to_receipt_code
from simulation.runner_models import GoalTransitionReasonCode
from world.identifiers import EntityId, WorldRevision


def _trace(
    memory_id: str,
    *,
    owner: str = "agent-1",
    predicate: str,
    subject_id: str,
    object_id: str,
) -> MemoryTrace:
    subject = MentionId(f"s-{memory_id}")
    obj = MentionId(f"o-{memory_id}")
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId(owner),
        world_revision=WorldRevision(0),
        concepts=(),
        entities=(
            EntityMention(
                mention_id=subject,
                label="subject",
                entity_id=EntityId(subject_id),
            ),
            EntityMention(
                mention_id=obj,
                label="object",
                entity_id=EntityId(object_id),
            ),
        ),
        relations=(
            MemoryRelation(
                relation_id=MentionId(f"r-{memory_id}"),
                predicate=predicate,
                subject=RelationEndpoint(
                    kind=RelationEndpointKind.ENTITY, mention_id=subject
                ),
                object=RelationEndpoint(
                    kind=RelationEndpointKind.ENTITY, mention_id=obj
                ),
            ),
        ),
        context=MemorySituationContext(),
        emotional_salience=0.2,
        confidence=0.8,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=1,
        ),
        created_tick=1,
        source_tick=1,
        last_access_tick=1,
        access_count=1,
    )


def _context(**kwargs: object) -> ReflectionContext:
    owner = AgentId("agent-1")
    base: dict[str, object] = {
        "owner_id": owner,
        "tick": 9,
        "policy": ReflectionPolicy(min_pattern_count=3),
        "owner_entity_id": EntityId("agent-1"),
    }
    base.update(kwargs)
    return ReflectionContext(**base)  # type: ignore[arg-type]


def test_identical_inputs_yield_identical_candidates() -> None:
    context = _context()
    assert materialize_reflection_candidates(context) == ()
    again = materialize_reflection_candidates(context)
    assert again == materialize_reflection_candidates(context)


def test_three_help_traces_copy_predicate_into_one_hypothesis() -> None:
    traces = tuple(
        _trace(
            f"mem-{index}",
            predicate="help_received",
            subject_id="bob",
            object_id="agent-1",
        )
        for index in range(3)
    )
    candidates = materialize_reflection_candidates(_context(memories=traces))
    beliefs = [
        item
        for item in candidates
        if item.kind is ReflectionConclusionKind.NEW_HYPOTHESIS
    ]
    assert len(beliefs) == 1
    belief = beliefs[0]
    assert belief.pattern_code is ReflectionPatternCode.REPEATED_HELP
    assert belief.evidence_ids == ("mem-0", "mem-1", "mem-2")
    assert belief.belief_request is not None
    assert belief.belief_request.claim.predicate == "help_received"
    assert (
        belief.belief_request.activation_state is BeliefActivationState.CANDIDATE
    )
    assert belief.belief_request.claim.value.number_value == 3
    relations = [
        item
        for item in candidates
        if item.kind is ReflectionConclusionKind.RELATIONSHIP_REASSESSMENT
    ]
    assert len(relations) == 1
    request = relations[0].relationship_request
    assert request is not None
    assert request.target_id == AgentId("bob")
    assert request.source_id == AgentId("agent-1")
    assert {signal.memory_ref for signal in request.signals} == {
        "mem-0",
        "mem-1",
        "mem-2",
    }
    again = materialize_reflection_candidates(_context(memories=traces))
    assert again == candidates


def test_repeated_failure_adopts_and_abandons_without_a_belief() -> None:
    records = tuple(
        SubjectiveDecisionRecord(
            record_id=f"decision-{index}",
            owner_id=AgentId("agent-1"),
            tick=index,
            command_kind="SearchCommand",
            outcome_code=DecisionOutcomeCode.NO_PROGRESS,
            day_phase="night",
            place_id="forest",
        )
        for index in range(3)
    )
    unknown = SubjectiveDecisionRecord(
        record_id="decision-open",
        owner_id=AgentId("agent-1"),
        tick=8,
        command_kind="SearchCommand",
        outcome_code=DecisionOutcomeCode.UNKNOWN,
        day_phase="night",
    )
    goal = Goal(
        goal_id=GoalId("goal-search"),
        owner_id=AgentId("agent-1"),
        description="search",
        priority=0.4,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.ACHIEVE_CODE,
            outcome_code="SearchCommand",
        ),
    )
    candidates = materialize_reflection_candidates(
        _context(decisions=(*records, unknown), goals=(goal,))
    )
    assert all(item.belief_request is None for item in candidates)
    failures = [
        item
        for item in candidates
        if item.pattern_code is ReflectionPatternCode.REPEATED_FAILURE
    ]
    adopted = [
        item
        for item in failures
        if item.kind is ReflectionConclusionKind.NEW_LONG_TERM_GOAL
    ]
    abandoned = [
        item
        for item in failures
        if item.kind is ReflectionConclusionKind.ABANDONED_GOAL
    ]
    assert len(adopted) == 1
    assert adopted[0].goal_intent is not None
    assert adopted[0].goal_intent.reason_code is GoalTransitionIntentReason.ADOPTED
    assert adopted[0].goal_intent.resulting_goal is not None
    assert adopted[0].goal_intent.resulting_goal.description == "repeated_failure"
    assert adopted[0].goal_intent.resulting_goal.horizon.value == "long_term"
    assert "decision-open" not in adopted[0].evidence_ids
    assert len(abandoned) == 1
    assert abandoned[0].goal_intent is not None
    assert abandoned[0].goal_intent.to_status is GoalStatus.ABANDONED
    assert (
        _intent_reason_to_receipt_code(GoalTransitionIntentReason.ADOPTED)
        is GoalTransitionReasonCode.REVISED
    )


def test_unknown_outcome_does_not_meet_the_failure_minimum() -> None:
    records = (
        SubjectiveDecisionRecord(
            record_id="decision-1",
            owner_id=AgentId("agent-1"),
            tick=1,
            command_kind="SearchCommand",
            outcome_code=DecisionOutcomeCode.NO_PROGRESS,
            day_phase="night",
        ),
        SubjectiveDecisionRecord(
            record_id="decision-2",
            owner_id=AgentId("agent-1"),
            tick=2,
            command_kind="SearchCommand",
            outcome_code=DecisionOutcomeCode.UNKNOWN,
            day_phase="night",
        ),
        SubjectiveDecisionRecord(
            record_id="decision-3",
            owner_id=AgentId("agent-1"),
            tick=3,
            command_kind="SearchCommand",
            outcome_code=DecisionOutcomeCode.UNKNOWN,
            day_phase="night",
        ),
    )
    assert materialize_reflection_candidates(_context(decisions=records)) == ()


def test_unrelated_predicate_is_not_invented() -> None:
    traces = tuple(
        _trace(
            f"mem-{index}",
            predicate="shared_food",
            subject_id="agent-1",
            object_id="alice",
        )
        for index in range(3)
    )
    candidates = materialize_reflection_candidates(_context(memories=traces))
    predicates = {
        item.belief_request.claim.predicate
        for item in candidates
        if item.belief_request is not None
    }
    assert predicates == {"shared_food"}
    assert "is_friend" not in predicates


def test_foreign_owner_fails_closed() -> None:
    foreign = _trace(
        "mem-x",
        owner="agent-2",
        predicate="help_received",
        subject_id="bob",
        object_id="agent-2",
    )
    try:
        _context(memories=(foreign,))
    except ValueError as exc:
        assert "owner_mismatch" in str(exc)
    else:
        raise AssertionError("expected owner_mismatch")


def test_context_rejects_world_state_shaped_input() -> None:
    class WorldState:
        pass

    try:
        _context(memories=(WorldState(),))  # type: ignore[arg-type]
    except ValueError as exc:
        assert "forbidden_input" in str(exc)
    else:
        raise AssertionError("expected forbidden_input")
