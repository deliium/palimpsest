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
    CounterpartBinding,
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
    OwnerSafeSocialIdentity,
    PerceptionClaimCode,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
    SelfBeliefState,
    SituationClaimCode,
    SituationModel,
    SubjectiveSnapshot,
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


def test_emotional_state_evaluation_and_component_kind() -> None:
    from agents.cognition.models import (
        AgentEmotionalState,
        EmotionalStateEvaluation,
        EmotionDriverCode,
        EmotionIntensity,
        EmotionKind,
        empty_emotional_state,
    )

    assert ComponentKind.EMOTIONAL_STATE.value == "emotional_state"
    owner = AgentId("agent-1")
    state = empty_emotional_state(owner, tick=2)
    evaluation = EmotionalStateEvaluation(
        owner_id=owner,
        tick=2,
        state=state,
        driver_codes=(EmotionDriverCode.PASSTHROUGH, EmotionDriverCode.DECAY),
        confidence=1.0,
        policy_version="emotion.v1",
    )
    assert "driver_count=2" in repr(evaluation)
    assert "afraid" not in repr(evaluation).lower()
    with pytest.raises(ValueError, match="owner_mismatch"):
        EmotionalStateEvaluation(
            owner_id=owner,
            tick=0,
            state=AgentEmotionalState(
                owner_id=AgentId("other"),
                tick=0,
                intensities=(
                    EmotionIntensity(kind=EmotionKind.FEAR, intensity=0.1),
                ),
                last_update_tick=0,
                policy_version="emotion.v1",
            ),
            driver_codes=(EmotionDriverCode.THREAT,),
            confidence=1.0,
            policy_version="emotion.v1",
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


def test_subjective_snapshot_carries_goals_drives_and_inbox() -> None:
    from agents.models import (
        DriveKind,
        Goal,
        GoalId,
        GoalOutcome,
        GoalOutcomeKind,
        GoalStatus,
        default_drive_profile,
    )
    from social.models import CommunicationEnvelope, EnvelopeId

    owner = AgentId("agent-1")
    goal = Goal(
        goal_id=GoalId("goal-1"),
        owner_id=owner,
        description="secret-goal-text",
        priority=0.7,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.THIRST
        ),
    )
    inbox = (
        CommunicationEnvelope(
            envelope_id=EnvelopeId("env-1"),
            sender_id=AgentId("agent-2"),
            recipient_id=owner,
            payload={"text": "secret-inbox"},
        ),
    )
    identity = OwnerSafeSocialIdentity(
        owner_id=owner,
        owner_entity_id=EntityId("body-1"),
        counterparts=(
            CounterpartBinding(
                agent_id=AgentId("agent-2"),
                entity_id=EntityId("body-2"),
            ),
        ),
    )
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=3,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        goals=(goal,),
        drives=default_drive_profile(owner),
        inbox=inbox,
        social_identity=identity,
    )
    assert snapshot.goals[0].goal_id == GoalId("goal-1")
    assert snapshot.drives is not None
    assert len(snapshot.drives.dispositions) == 11
    assert snapshot.inbox[0].envelope_id.value == "env-1"
    assert snapshot.social_identity is not None
    assert snapshot.social_identity.counterparts[0].agent_id.value == "agent-2"
    text = repr(snapshot)
    assert "secret-goal-text" not in text
    assert "secret-inbox" not in text


def test_subjective_snapshot_rejects_foreign_goals_and_drives() -> None:
    from agents.models import Goal, GoalId, GoalStatus, default_drive_profile

    owner = AgentId("agent-1")
    with pytest.raises(ValueError, match="ownership"):
        SubjectiveSnapshot(
            owner_id=owner,
            revision=0,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            goals=(
                Goal(
                    goal_id=GoalId("goal-x"),
                    owner_id=AgentId("agent-2"),
                    description="x",
                    priority=0.1,
                    status=GoalStatus.ACTIVE,
                ),
            ),
        )
    with pytest.raises(ValueError, match="ownership"):
        SubjectiveSnapshot(
            owner_id=owner,
            revision=0,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            drives=default_drive_profile(AgentId("agent-2")),
        )


def test_require_signed_unit_bounds() -> None:
    from agents.cognition.models import require_signed_unit

    assert require_signed_unit("d", -1) == -1.0
    assert require_signed_unit("d", 1.0) == 1.0
    assert require_signed_unit("d", 0) == 0.0
    with pytest.raises(ValueError, match="not_signed_unit"):
        require_signed_unit("d", -1.1)
    with pytest.raises(ValueError, match="not_signed_unit"):
        require_signed_unit("d", True)


def test_perceived_need_pressures_and_effect_vectors() -> None:
    from agents.cognition.models import (
        ActionDirection,
        DriveEffect,
        FutureAppraisal,
        FutureSourceRef,
        GoalEffect,
        MortalityOpportunityForeclosure,
        OptionSpaceChange,
        PerceivedNeedPressures,
        SocialEffect,
        SubjectiveRisk,
        SubjectiveRiskKind,
        SubjectiveUncertainty,
        UncertaintyBand,
        action_direction_for_intention,
        intention_for_action_direction,
    )
    from agents.models import DriveKind

    pressures = PerceivedNeedPressures(
        hunger=0.8,
        thirst=0.2,
        fatigue=0.1,
        health=0.9,
        confidence=0.7,
    )
    assert "0.8" not in repr(pressures) or "confidence=" in repr(pressures)
    assert pressures.hunger == 0.8

    drive = DriveEffect(kind=DriveKind.THIRST, delta=-0.5, confidence=0.9)
    goal = GoalEffect(goal_id=GoalId("goal-1"), progress_delta=0.25, confidence=0.8)
    social = SocialEffect(
        counterpart_id=AgentId("agent-2"), affinity_delta=0.1, confidence=0.6
    )
    risk = SubjectiveRisk(
        kind=SubjectiveRiskKind.PHYSICAL_HARM,
        severity=0.7,
        likelihood=0.4,
        confidence=0.5,
    )
    assert drive.kind is DriveKind.THIRST
    assert goal.goal_id.value == "goal-1"
    assert social.counterpart_id is not None
    assert risk.kind is SubjectiveRiskKind.PHYSICAL_HARM
    assert "delta" not in repr(drive)
    assert "-0.5" not in repr(drive)

    mortality = MortalityOpportunityForeclosure(
        death_probability=0.5,
        outstanding_goal_value=1.0,
        attachment_loss=0.0,
        safety_activation=0.0,
        autonomy_loss=0.0,
        option_space=OptionSpaceChange(
            retained_options_ratio=0.5, foreclosed_ratio=0.5
        ),
        composite=0.99,
    )
    # composite = 0.5 * (0.30*1 + 0.15*0.5) = 0.5 * 0.375 = 0.1875
    assert mortality.composite == pytest.approx(0.1875)
    assert "1.0" not in repr(mortality) or "death_probability" in repr(mortality)

    future = ImaginedFuture(
        future_id="drink-well",
        claim_codes=(SituationClaimCode.RESOURCE_PRESENT,),
        confidence=0.6,
        direction=ActionDirection.DRINK,
        target_entity_id="well-1",
        horizon_ticks=2,
        drive_effects=(drive,),
        goal_effects=(goal,),
        social_effects=(social,),
        risks=(risk,),
        uncertainty=SubjectiveUncertainty(
            epistemic=0.3, aleatory=0.1, band=UncertaintyBand.MEDIUM
        ),
        mortality=mortality,
        source_refs=FutureSourceRef(belief_ids=("bel-1",), memory_ids=("mem-1",)),
    )
    assert future.subjective_probability == 0.6
    assert future.direction is ActionDirection.DRINK
    text = repr(future)
    assert "drink-well" in text
    assert "well-1" not in text
    assert "-0.5" not in text
    assert "PHYSICAL_HARM" not in text or "risk_count=1" in text

    legacy = ImaginedFuture(
        future_id="idle",
        claim_codes=(SituationClaimCode.IDLE,),
        confidence=1.0,
    )
    assert legacy.direction is ActionDirection.WAIT
    assert legacy.subjective_probability == 1.0
    assert legacy.drive_effects == ()

    appraisal = FutureAppraisal(
        future_id="drink-well",
        drive_effects=(drive,),
        goal_effects=(goal,),
        risks=(risk,),
        mortality=mortality,
        support_drive_count=1,
        support_goal_count=1,
        support_social_count=1,
    )
    evaluation = MotivationEvaluation(
        owner_id=AgentId("agent-1"),
        scores=(MotivationScore(motive=MotivationCode.SURVIVE, score=0.8),),
        confidence=0.8,
        appraisals=(appraisal,),
        active_drive_kinds=(DriveKind.THIRST,),
        active_goal_ids=(GoalId("goal-1"),),
    )
    assert len(evaluation.appraisals) == 1
    assert "goal-1" not in repr(evaluation) or "active_goal_count=1" in repr(evaluation)
    assert "-0.5" not in repr(appraisal)

    selected = SelectedIntention(
        owner_id=AgentId("agent-1"),
        intention=IntentionCode.DRINK,
        source_motive=MotivationCode.SURVIVE,
        confidence=0.8,
        selected_future_id="drink-well",
        direction=ActionDirection.DRINK,
        appraisal_future_ids=("drink-well",),
    )
    assert selected.direction is ActionDirection.DRINK
    assert action_direction_for_intention(IntentionCode.REST) is ActionDirection.SLEEP
    assert intention_for_action_direction(ActionDirection.FLEE) is IntentionCode.FLEE


def test_imagined_future_rejects_duplicate_effects_and_bad_bounds() -> None:
    from agents.cognition.models import ActionDirection, DriveEffect
    from agents.models import DriveKind

    with pytest.raises(ValueError, match="duplicate_kind"):
        ImaginedFuture(
            future_id="f1",
            claim_codes=(SituationClaimCode.IDLE,),
            confidence=0.5,
            drive_effects=(
                DriveEffect(kind=DriveKind.HUNGER, delta=0.1, confidence=1.0),
                DriveEffect(kind=DriveKind.HUNGER, delta=-0.1, confidence=1.0),
            ),
        )
    with pytest.raises(ValueError, match="not_signed_unit"):
        DriveEffect(kind=DriveKind.HUNGER, delta=1.5, confidence=1.0)
    with pytest.raises(ValueError, match="must_be_positive"):
        ImaginedFuture(
            future_id="f1",
            claim_codes=(SituationClaimCode.IDLE,),
            confidence=0.5,
            direction=ActionDirection.WAIT,
            horizon_ticks=0,
        )
    with pytest.raises(ValueError, match="duplicate"):
        from agents.cognition.models import FutureSourceRef

        FutureSourceRef(belief_ids=("bel-1", "bel-1"))


def test_mortality_composite_has_no_death_penalty_constant() -> None:
    from agents.cognition.models import (
        MortalityOpportunityForeclosure,
        OptionSpaceChange,
    )

    low = MortalityOpportunityForeclosure(
        death_probability=1.0,
        outstanding_goal_value=0.0,
        attachment_loss=0.0,
        safety_activation=0.0,
        autonomy_loss=0.0,
        option_space=OptionSpaceChange(foreclosed_ratio=0.0),
    )
    high = MortalityOpportunityForeclosure(
        death_probability=1.0,
        outstanding_goal_value=1.0,
        attachment_loss=1.0,
        safety_activation=1.0,
        autonomy_loss=1.0,
        option_space=OptionSpaceChange(foreclosed_ratio=1.0),
    )
    assert low.composite == 0.0
    assert high.composite == pytest.approx(1.0)
    assert high.composite <= 1.0
    # Same death probability, different opportunity values => different fear.
    mid = MortalityOpportunityForeclosure(
        death_probability=1.0,
        outstanding_goal_value=1.0,
        attachment_loss=0.0,
        safety_activation=0.0,
        autonomy_loss=0.0,
        option_space=OptionSpaceChange(foreclosed_ratio=0.0),
    )
    assert mid.composite == pytest.approx(0.30)
    assert mid.composite != high.composite


def test_validation_errors_expose_field_and_reason_codes_only() -> None:
    from agents.cognition.models import DriveEffect, SocialEffect
    from agents.models import DriveKind

    with pytest.raises(ValueError) as exc_drive:
        DriveEffect(kind=DriveKind.HUNGER, delta=2.0, confidence=1.0)
    assert "DriveEffect.delta" in str(exc_drive.value)
    assert "not_signed_unit" in str(exc_drive.value)
    assert "2.0" not in str(exc_drive.value)

    with pytest.raises(TypeError) as exc_social:
        SocialEffect(counterpart_id="agent-2", affinity_delta=0.1, confidence=1.0)  # type: ignore[arg-type]
    assert "counterpart_id" in str(exc_social.value)
    assert "invalid_type" in str(exc_social.value)
