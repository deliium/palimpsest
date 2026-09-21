"""Unit tests for opportunity-based fear of death (no death_penalty)."""

from __future__ import annotations

import pytest

from agents.cognition.models import (
    ActionDirection,
    CognitiveLoopInput,
    ImaginedFuture,
    InternalAgentState,
    PossibleFutures,
    SelfModel,
    SituationClaimCode,
    SituationModel,
    SubjectiveRisk,
    SubjectiveRiskKind,
    SubjectiveSnapshot,
    SubjectiveUncertainty,
)
from agents.cognition.motivation import MotivationAppraisal
from agents.models import (
    AgentId,
    Goal,
    GoalId,
    GoalOutcome,
    GoalOutcomeKind,
    GoalProgress,
    GoalStatus,
    default_drive_profile,
)
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipActivationState,
    RelationshipConfidence,
    RelationshipDimension,
    RelationshipDimensionState,
    RelationshipId,
    RelationshipPolicyRef,
    RelationshipRevisionId,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation, ObservedSelf
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _relationship(
    *, dependency: float, affection: float
) -> DirectedRelationshipProfile:
    policy = RelationshipPolicyRef(policy_id="rel-v1", version="1")
    confidence = RelationshipConfidence(
        confidence=0.9, support_mass=0.9, contradiction_mass=0.0
    )
    return DirectedRelationshipProfile(
        relationship_id=RelationshipId("rel-1"),
        source_id=AgentId("agent-1"),
        target_id=AgentId("agent-2"),
        dimensions=(
            RelationshipDimensionState(
                dimension=RelationshipDimension.DEPENDENCY,
                value=dependency,
                confidence=confidence,
                evidence=(),
                logical_tick=1,
                policy=policy,
            ),
            RelationshipDimensionState(
                dimension=RelationshipDimension.AFFECTION,
                value=affection,
                confidence=confidence,
                evidence=(),
                logical_tick=1,
                policy=policy,
            ),
        ),
        activation_state=RelationshipActivationState.ACTIVE,
        current_revision_id=RelationshipRevisionId("rrev-1"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=1,
        policy=policy,
    )


def _loop_input(
    *,
    goals: tuple[Goal, ...] = (),
    relationships: tuple[DirectedRelationshipProfile, ...] = (),
) -> CognitiveLoopInput:
    agent = AgentId("agent-1")
    return CognitiveLoopInput(
        agent_id=agent,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
            tick=4,
            self_body=_self(),
        ),
        internal_state=InternalAgentState(owner_id=agent),
        snapshot=SubjectiveSnapshot(
            owner_id=agent,
            revision=1,
            memories=(),
            legacy_beliefs=(),
            semantic_beliefs=(),
            relationships=relationships,
            goals=goals,
            drives=default_drive_profile(agent),
        ),
    )


def _risky_futures(*, harm: float) -> PossibleFutures:
    wait = ImaginedFuture(
        future_id="wait",
        claim_codes=(SituationClaimCode.THREAT_SIGNAL,),
        confidence=0.5,
        direction=ActionDirection.WAIT,
        risks=(
            SubjectiveRisk(
                kind=SubjectiveRiskKind.PHYSICAL_HARM,
                severity=harm,
                likelihood=harm,
                confidence=0.9,
            ),
        ),
        uncertainty=SubjectiveUncertainty(),
        subjective_probability=0.4,
    )
    flee = ImaginedFuture(
        future_id="flee",
        claim_codes=(SituationClaimCode.THREAT_SIGNAL,),
        confidence=0.6,
        direction=ActionDirection.FLEE,
        target_entity_id="body-2",
        risks=(
            SubjectiveRisk(
                kind=SubjectiveRiskKind.PHYSICAL_HARM,
                severity=harm * 0.4,
                likelihood=harm * 0.4,
                confidence=0.8,
            ),
        ),
        uncertainty=SubjectiveUncertainty(),
        subjective_probability=0.7,
    )
    return PossibleFutures(
        owner_id=AgentId("agent-1"), futures=(wait, flee), confidence=1.0
    )


def _situation() -> SituationModel:
    return SituationModel(
        owner_id=AgentId("agent-1"),
        tick=4,
        claim_codes=(SituationClaimCode.THREAT_SIGNAL, SituationClaimCode.LOCAL_SCENE),
        confidence=1.0,
    )


def _self_model() -> SelfModel:
    return SelfModel(
        owner_id=AgentId("agent-1"),
        policy_id="self-model-projection",
        policy_version="1",
        life_status=LifeStatus.ALIVE,
        beliefs=(),
        goal_ids=(),
        confidence=1.0,
        candidate_count=0,
    )


@pytest.mark.asyncio
async def test_fear_of_death_scales_with_outstanding_goals_and_attachments() -> None:
    low_goals = (
        Goal(
            goal_id=GoalId("goal-minor"),
            owner_id=AgentId("agent-1"),
            description="secret-minor",
            priority=0.1,
            status=GoalStatus.ACTIVE,
            outcome=GoalOutcome(
                kind=GoalOutcomeKind.ACHIEVE_CODE, outcome_code="minor"
            ),
            progress=GoalProgress(estimate=0.8, confidence=0.7),
        ),
    )
    high_goals = (
        Goal(
            goal_id=GoalId("goal-life"),
            owner_id=AgentId("agent-1"),
            description="secret-life",
            priority=1.0,
            status=GoalStatus.ACTIVE,
            outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
            progress=GoalProgress(estimate=0.0, confidence=0.9),
        ),
    )
    low = await MotivationAppraisal().evaluate(
        _loop_input(
            goals=low_goals,
            relationships=(_relationship(dependency=0.1, affection=0.1),),
        ),
        _situation(),
        _self_model(),
        _risky_futures(harm=0.8),
    )
    high = await MotivationAppraisal().evaluate(
        _loop_input(
            goals=high_goals,
            relationships=(_relationship(dependency=0.9, affection=0.8),),
        ),
        _situation(),
        _self_model(),
        _risky_futures(harm=0.8),
    )
    low_wait = next(item for item in low.appraisals if item.future_id == "wait")
    high_wait = next(item for item in high.appraisals if item.future_id == "wait")
    assert low_wait.mortality is not None
    assert high_wait.mortality is not None
    assert high_wait.mortality.composite > low_wait.mortality.composite
    assert (
        high_wait.mortality.outstanding_goal_value
        > low_wait.mortality.outstanding_goal_value
    )
    assert high_wait.mortality.attachment_loss > low_wait.mortality.attachment_loss
    # Components are inspectable; no hard-coded death_penalty field/constant.
    assert hasattr(high_wait.mortality, "death_probability")
    assert not hasattr(high_wait.mortality, "death_penalty")


@pytest.mark.asyncio
async def test_same_physiology_different_danger_changes_death_probability() -> None:
    mild = await MotivationAppraisal().evaluate(
        _loop_input(),
        _situation(),
        _self_model(),
        _risky_futures(harm=0.2),
    )
    severe = await MotivationAppraisal().evaluate(
        _loop_input(),
        _situation(),
        _self_model(),
        _risky_futures(harm=0.9),
    )
    mild_wait = next(item for item in mild.appraisals if item.future_id == "wait")
    severe_wait = next(item for item in severe.appraisals if item.future_id == "wait")
    assert mild_wait.mortality is not None
    assert severe_wait.mortality is not None
    assert (
        severe_wait.mortality.death_probability > mild_wait.mortality.death_probability
    )
    # Flee reduces subjective death probability relative to waiting under severe harm.
    severe_flee = next(item for item in severe.appraisals if item.future_id == "flee")
    assert severe_flee.mortality is not None
    assert (
        severe_flee.mortality.death_probability
        < severe_wait.mortality.death_probability
    )


@pytest.mark.asyncio
async def test_mortality_composite_is_derived_not_fixed_penalty() -> None:
    evaluation = await MotivationAppraisal().evaluate(
        _loop_input(
            goals=(
                Goal(
                    goal_id=GoalId("goal-1"),
                    owner_id=AgentId("agent-1"),
                    description="secret",
                    priority=0.8,
                    status=GoalStatus.ACTIVE,
                    outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
                ),
            )
        ),
        _situation(),
        _self_model(),
        _risky_futures(harm=0.7),
    )
    wait = next(item for item in evaluation.appraisals if item.future_id == "wait")
    assert wait.mortality is not None
    assert 0.0 <= wait.mortality.composite <= 1.0
    # Composite tracks components rather than a universal huge constant.
    assert wait.mortality.composite < 1.0
    assert "death_penalty" not in repr(wait.mortality)
