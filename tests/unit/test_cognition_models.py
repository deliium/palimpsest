"""Validation and privacy tests for cognition models."""

from __future__ import annotations

import math

import pytest

from agents.cognition.models import (
    BOUNDARY_SCHEMA_VERSION,
    ActionPlan,
    CognitionFailureReason,
    CognitiveLoopInput,
    CognitiveLoopResult,
    ComponentBoundaryRecord,
    ComponentKind,
    ComponentStatus,
    DecisionMetadata,
    ImaginedFuture,
    IntentionCode,
    InternalAgentState,
    InterpretedPerception,
    MemoryUpdateIntent,
    MemoryUpdateKind,
    MotivationCode,
    MotivationEvaluation,
    MotivationScore,
    PerceptionClaimCode,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
    SelfBeliefState,
    SituationClaimCode,
    SituationModel,
    diagnostic_projection,
    require_confidence,
)
from agents.models import AgentId, GoalId
from memory.models import (
    Belief,
    BeliefId,
    ConceptMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryTrace,
    MentionId,
)
from world.actions import Wait, require_agent_command
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation


def _observation(*, tick: int = 0) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=tick,
    )


def _internal(agent_id: AgentId | None = None) -> InternalAgentState:
    return InternalAgentState(owner_id=agent_id or AgentId("agent-1"))


def _perception(agent_id: AgentId | None = None) -> InterpretedPerception:
    owner = agent_id or AgentId("agent-1")
    return InterpretedPerception(
        owner_id=owner,
        observer_id=EntityId("body-1"),
        tick=0,
        revision=WorldRevision(0),
        life_status=LifeStatus.ALIVE,
        location_id=EntityId("loc-1"),
        claim_codes=(PerceptionClaimCode.SELF_ALIVE, PerceptionClaimCode.HAS_LOCATION),
        counts={"exits": 1, "items": 0},
        confidence=1.0,
    )


def test_require_confidence_bounds() -> None:
    assert require_confidence("c", 0) == 0.0
    assert require_confidence("c", 1.0) == 1.0
    assert require_confidence("c", 0.5) == 0.5
    with pytest.raises(ValueError):
        require_confidence("c", -0.1)
    with pytest.raises(ValueError):
        require_confidence("c", 1.1)
    with pytest.raises(ValueError):
        require_confidence("c", math.nan)
    with pytest.raises(ValueError):
        require_confidence("c", True)


def test_internal_state_and_loop_input_ownership() -> None:
    agent = AgentId("agent-1")
    state = _internal(agent)
    loop_input = CognitiveLoopInput(
        agent_id=agent,
        observation=_observation(),
        internal_state=state,
    )
    assert loop_input.agent_id == agent
    with pytest.raises(ValueError):
        CognitiveLoopInput(
            agent_id=agent,
            observation=_observation(),
            internal_state=InternalAgentState(owner_id=AgentId("other")),
        )


def test_interpreted_perception_rejects_duplicate_claims_and_bad_counts() -> None:
    with pytest.raises(ValueError):
        InterpretedPerception(
            owner_id=AgentId("agent-1"),
            observer_id=EntityId("body-1"),
            tick=0,
            revision=WorldRevision(0),
            life_status=None,
            location_id=None,
            claim_codes=(
                PerceptionClaimCode.SELF_ALIVE,
                PerceptionClaimCode.SELF_ALIVE,
            ),
            counts={},
            confidence=1.0,
        )
    with pytest.raises(ValueError):
        InterpretedPerception(
            owner_id=AgentId("agent-1"),
            observer_id=EntityId("body-1"),
            tick=0,
            revision=WorldRevision(0),
            life_status=None,
            location_id=None,
            claim_codes=(),
            counts={"exits": -1},
            confidence=1.0,
        )


def test_memory_context_and_situation_are_immutable() -> None:
    ctx = RetrievedMemoryContext(
        owner_id=AgentId("agent-1"),
        memory_ids=(MemoryId("mem-1"),),
        belief_ids=(BeliefId("bel-1"),),
        confidence=0.8,
    )
    with pytest.raises(AttributeError):
        ctx.confidence = 0.1  # type: ignore[misc]
    situation = SituationModel(
        owner_id=AgentId("agent-1"),
        tick=2,
        claim_codes=(SituationClaimCode.LOCAL_SCENE,),
        confidence=0.9,
    )
    assert "LOCAL_SCENE" not in repr(situation) or "claim_count=1" in repr(situation)
    assert "mem-1" not in repr(ctx)


def test_futures_motivation_intention_plan_pipeline_shapes() -> None:
    agent = AgentId("agent-1")
    futures = PossibleFutures(
        owner_id=agent,
        futures=(
            ImaginedFuture(
                future_id="f1",
                claim_codes=(SituationClaimCode.IDLE,),
                confidence=0.5,
            ),
        ),
        confidence=0.5,
    )
    motives = MotivationEvaluation(
        owner_id=agent,
        scores=(
            MotivationScore(motive=MotivationCode.WAIT, score=0.9),
            MotivationScore(motive=MotivationCode.EXPLORE, score=0.1),
        ),
        confidence=0.9,
    )
    intention = SelectedIntention(
        owner_id=agent,
        intention=IntentionCode.WAIT,
        source_motive=MotivationCode.WAIT,
        confidence=0.9,
        decision_metadata=DecisionMetadata(
            selection_codes=("wait",),
            candidate_count=2,
            tie_break_applied=False,
        ),
    )
    plan = ActionPlan(owner_id=agent, command=Wait(), confidence=1.0)
    assert require_agent_command(plan.command) is plan.command
    assert futures.futures[0].future_id == "f1"
    assert motives.scores[0].motive is MotivationCode.WAIT
    assert intention.intention is IntentionCode.WAIT


def test_action_plan_rejects_mappings_and_subclasses() -> None:
    class FakeWait(Wait):
        pass

    with pytest.raises(TypeError):
        ActionPlan(
            owner_id=AgentId("agent-1"),
            command={"kind": "wait"},  # type: ignore[arg-type]
            confidence=1.0,
        )
    with pytest.raises(TypeError):
        ActionPlan(owner_id=AgentId("agent-1"), command=FakeWait(), confidence=1.0)


def _memory_trace(*, owner: AgentId, memory_id: str = "mem-1") -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=owner,
        world_revision=WorldRevision(0),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept="note"),),
        entities=(),
        relations=(),
        context=MemorySituationContext(),
        emotional_salience=0.0,
        confidence=1.0,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=0,
        ),
        created_tick=0,
        source_tick=0,
        last_access_tick=0,
        access_count=0,
    )


def test_memory_update_intent_owner_and_kind() -> None:
    agent = AgentId("agent-1")
    memory = _memory_trace(owner=agent)
    intent = MemoryUpdateIntent(
        owner_id=agent,
        kind=MemoryUpdateKind.WRITE_MEMORY,
        memory=memory,
    )
    assert "note" not in repr(intent)
    with pytest.raises(ValueError):
        MemoryUpdateIntent(
            owner_id=agent,
            kind=MemoryUpdateKind.WRITE_MEMORY,
            memory=_memory_trace(owner=AgentId("other"), memory_id="mem-2"),
        )
    belief = Belief(
        belief_id=BeliefId("bel-1"),
        owner_id=agent,
        proposition="sky is blue",
        confidence=0.5,
        evidence_memory_ids=(),
    )
    belief_intent = MemoryUpdateIntent(
        owner_id=agent,
        kind=MemoryUpdateKind.WRITE_BELIEF,
        belief=belief,
    )
    assert belief_intent.belief is not None
    with pytest.raises(TypeError):
        MemoryUpdateIntent(
            owner_id=agent,
            kind=MemoryUpdateKind.WRITE_BELIEF,
            memory=memory,
        )


def test_boundary_record_completed_and_failed() -> None:
    perception = _perception()
    completed = ComponentBoundaryRecord(
        invocation_id="inv-1",
        component_kind=ComponentKind.PERCEPTION,
        component_version="v1",
        ordinal=0,
        status=ComponentStatus.COMPLETED,
        confidence=1.0,
        input_artifact=_observation(),
        output_artifact=perception,
        decision_metadata=DecisionMetadata(),
        schema_version=BOUNDARY_SCHEMA_VERSION,
    )
    assert completed.output_artifact is perception
    failed = ComponentBoundaryRecord(
        invocation_id="inv-1",
        component_kind=ComponentKind.SITUATION,
        component_version="v1",
        ordinal=2,
        status=ComponentStatus.FAILED,
        confidence=0.0,
        input_artifact=perception,
        output_artifact=None,
        decision_metadata=DecisionMetadata(),
        failure_reason=CognitionFailureReason.INVALID_OUTPUT,
    )
    assert failed.failure_reason is CognitionFailureReason.INVALID_OUTPUT
    with pytest.raises(ValueError):
        ComponentBoundaryRecord(
            invocation_id="inv-1",
            component_kind=ComponentKind.PERCEPTION,
            component_version="v1",
            ordinal=0,
            status=ComponentStatus.COMPLETED,
            confidence=1.0,
            input_artifact=_observation(),
            output_artifact=None,
            decision_metadata=DecisionMetadata(),
        )


def test_loop_result_requires_exact_command_and_matching_owners() -> None:
    agent = AgentId("agent-1")
    plan = ActionPlan(owner_id=agent, command=Wait(), confidence=1.0)
    record = ComponentBoundaryRecord(
        invocation_id="inv-1",
        component_kind=ComponentKind.PLANNING,
        component_version="v1",
        ordinal=7,
        status=ComponentStatus.COMPLETED,
        confidence=1.0,
        input_artifact=SelectedIntention(
            owner_id=agent,
            intention=IntentionCode.WAIT,
            source_motive=MotivationCode.WAIT,
            confidence=1.0,
        ),
        output_artifact=plan,
        decision_metadata=DecisionMetadata(
            selection_codes=("wait",), candidate_count=1
        ),
    )
    result = CognitiveLoopResult(
        invocation_id="inv-1",
        agent_id=agent,
        command=Wait(),
        boundary_records=(record,),
        memory_update_intents=(),
        final_confidence=1.0,
        internal_state=_internal(agent),
    )
    assert type(result.command) is Wait
    with pytest.raises(ValueError):
        CognitiveLoopResult(
            invocation_id="inv-1",
            agent_id=agent,
            command=Wait(),
            boundary_records=(record,),
            memory_update_intents=(
                MemoryUpdateIntent(
                    owner_id=AgentId("other"),
                    kind=MemoryUpdateKind.WRITE_BELIEF,
                    belief=Belief(
                        belief_id=BeliefId("bel-x"),
                        owner_id=AgentId("other"),
                        proposition="x",
                        confidence=0.1,
                        evidence_memory_ids=(),
                    ),
                ),
            ),
            final_confidence=1.0,
            internal_state=_internal(agent),
        )


def test_repr_and_diagnostic_projection_omit_payloads() -> None:
    agent = AgentId("agent-1")
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=3,
    )
    loop_input = CognitiveLoopInput(
        agent_id=agent,
        observation=observation,
        internal_state=_internal(agent),
    )
    perception = _perception(agent)
    record = ComponentBoundaryRecord(
        invocation_id="inv-9",
        component_kind=ComponentKind.PERCEPTION,
        component_version="v1",
        ordinal=0,
        status=ComponentStatus.COMPLETED,
        confidence=0.75,
        input_artifact=observation,
        output_artifact=perception,
        decision_metadata=DecisionMetadata(
            selection_codes=("self_alive",),
            candidate_count=1,
        ),
    )
    result = CognitiveLoopResult(
        invocation_id="inv-9",
        agent_id=agent,
        command=Wait(),
        boundary_records=(record,),
        memory_update_intents=(),
        final_confidence=0.75,
        internal_state=InternalAgentState(
            owner_id=agent,
            invocation_count=1,
            last_intention=IntentionCode.WAIT,
            last_command_kind="wait",
        ),
    )
    texts = [
        repr(loop_input),
        repr(perception),
        repr(record),
        repr(result),
        str(dict(diagnostic_projection(loop_input))),
        str(dict(diagnostic_projection(record))),
        str(dict(diagnostic_projection(result))),
    ]
    joined = "\n".join(texts)
    forbidden = (
        "Observation(",
        "self_body",
        "communications",
        "proposition",
        "content",
        "chain_of_thought",
        "rationale",
        "prompt",
        "sky is blue",
    )
    for token in forbidden:
        assert token not in joined
    projection = diagnostic_projection(record)
    assert projection["component_kind"] == "perception"
    assert projection["ordinal"] == 0
    assert projection["input_type"] == "Observation"
    assert projection["output_type"] == "InterpretedPerception"
    assert "selection_codes" not in projection


def test_self_belief_state_goal_ids() -> None:
    state = SelfBeliefState(
        owner_id=AgentId("agent-1"),
        life_status=LifeStatus.ALIVE,
        belief_ids=(BeliefId("bel-1"),),
        goal_ids=(GoalId("goal-1"),),
        confidence=1.0,
    )
    assert state.goal_ids[0] == GoalId("goal-1")
    assert "bel-1" not in repr(state)


def test_self_model_repr_omits_claim_payload() -> None:
    from agents.cognition.models import SelfModel, SelfRelevantBelief
    from memory.beliefs import (
        BeliefValueKind,
        ClaimSubject,
        ClaimSubjectKind,
        ClaimValue,
        SemanticClaim,
    )

    secret = "finds-food-effectively"
    model = SelfModel(
        owner_id=AgentId("agent-1"),
        policy_id="self-model-projection",
        policy_version="1",
        life_status=LifeStatus.ALIVE,
        beliefs=(
            SelfRelevantBelief(
                belief_id=BeliefId("bel-1"),
                claim=SemanticClaim(
                    subject=ClaimSubject(
                        kind=ClaimSubjectKind.AGENT, agent_id=AgentId("agent-1")
                    ),
                    predicate=secret,
                    value=ClaimValue(kind=BeliefValueKind.TEXT, text_value="yes"),
                ),
                confidence=0.8,
            ),
        ),
        goal_ids=(GoalId("goal-1"),),
        confidence=0.8,
        candidate_count=1,
    )
    assert secret not in repr(model)
    assert "yes" not in repr(model)
