"""Unit tests for MotivationAppraisal drive/goal appraisal."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.imagination import ImaginationEngine
from agents.cognition.models import (
    ActionDirection,
    CognitiveLoopInput,
    DriveEffect,
    ImaginedFuture,
    InternalAgentState,
    PossibleFutures,
    RetrievedMemoryContext,
    SelfModel,
    SituationClaimCode,
    SituationModel,
    SubjectiveRisk,
    SubjectiveRiskKind,
    SubjectiveSnapshot,
    SubjectiveUncertainty,
)
from agents.cognition.motivation import (
    POLICY_VERSION,
    MotivationAppraisal,
    activate_drives,
    derive_need_pressures,
)
from agents.models import (
    REQUIRED_DRIVE_KINDS,
    AgentId,
    DriveDisposition,
    DriveKind,
    DriveProfile,
    Goal,
    GoalId,
    GoalOutcome,
    GoalOutcomeKind,
    GoalProgress,
    GoalStatus,
    default_drive_profile,
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


def _self(
    *, hunger: float = 0.0, thirst: float = 0.0, fatigue: float = 0.0
) -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(hunger),
        thirst=Thirst(thirst),
        fatigue=Fatigue(fatigue),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _loop_input(
    *,
    hunger: float = 0.0,
    thirst: float = 0.0,
    fatigue: float = 0.0,
    goals: tuple[Goal, ...] = (),
    drives: DriveProfile | None = None,
) -> CognitiveLoopInput:
    agent = AgentId("agent-1")
    snapshot = SubjectiveSnapshot(
        owner_id=agent,
        revision=1,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        goals=goals,
        drives=drives or default_drive_profile(agent),
    )
    return CognitiveLoopInput(
        agent_id=agent,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
            tick=2,
            self_body=_self(hunger=hunger, thirst=thirst, fatigue=fatigue),
        ),
        internal_state=InternalAgentState(owner_id=agent),
        snapshot=snapshot,
    )


def _situation(*claims: SituationClaimCode) -> SituationModel:
    return SituationModel(
        owner_id=AgentId("agent-1"),
        tick=2,
        claim_codes=claims or (SituationClaimCode.LOCAL_SCENE,),
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


def _future(
    future_id: str,
    direction: ActionDirection,
    *,
    harm: float = 0.0,
    drive_effects: tuple[DriveEffect, ...] = (),
) -> ImaginedFuture:
    risks = ()
    if harm > 0.0:
        risks = (
            SubjectiveRisk(
                kind=SubjectiveRiskKind.PHYSICAL_HARM,
                severity=harm,
                likelihood=harm,
                confidence=0.8,
            ),
        )
    return ImaginedFuture(
        future_id=future_id,
        claim_codes=(SituationClaimCode.LOCAL_SCENE,),
        confidence=0.6,
        direction=direction,
        drive_effects=drive_effects,
        risks=risks,
        uncertainty=SubjectiveUncertainty(),
        subjective_probability=0.6,
    )


def test_derive_need_pressures_from_physiology() -> None:
    pressures = derive_need_pressures(_self(hunger=50.0, thirst=80.0, fatigue=20.0))
    assert pressures.hunger == pytest.approx(0.5)
    assert pressures.thirst == pytest.approx(0.8)
    assert pressures.fatigue == pytest.approx(0.2)
    assert pressures.health == pytest.approx(0.0)


def test_all_eleven_drives_activate_independently() -> None:
    profile = DriveProfile(
        owner_id=AgentId("agent-1"),
        dispositions=tuple(
            DriveDisposition(
                kind=kind,
                baseline=0.9 if kind is DriveKind.BELONGING else 0.2,
                sensitivity=0.9 if kind is DriveKind.THIRST else 0.3,
            )
            for kind in REQUIRED_DRIVE_KINDS
        ),
    )
    pressures = derive_need_pressures(_self(thirst=90.0))
    state = activate_drives(
        profile=profile,
        pressures=pressures,
        situation=_situation(SituationClaimCode.SOCIAL_SIGNAL),
        danger_signal=0.2,
        social_signal=0.8,
    )
    assert len(state.activations) == 11
    assert [item.kind for item in state.activations] == list(REQUIRED_DRIVE_KINDS)
    thirst = next(item for item in state.activations if item.kind is DriveKind.THIRST)
    belonging = next(
        item for item in state.activations if item.kind is DriveKind.BELONGING
    )
    # Conflicting activations remain simultaneously visible.
    assert thirst.activation > 0.0
    assert belonging.activation > 0.0
    assert thirst.activation != belonging.activation


@pytest.mark.asyncio
async def test_appraisal_preserves_independent_vectors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.motivation")
    goals = (
        Goal(
            goal_id=GoalId("goal-thirst"),
            owner_id=AgentId("agent-1"),
            description="secret-drink",
            priority=0.9,
            status=GoalStatus.ACTIVE,
            outcome=GoalOutcome(
                kind=GoalOutcomeKind.SATISFY_DRIVE, drive_kind=DriveKind.THIRST
            ),
            progress=GoalProgress(estimate=0.1, confidence=0.8),
        ),
    )
    futures = PossibleFutures(
        owner_id=AgentId("agent-1"),
        futures=(
            _future(
                "drink",
                ActionDirection.DRINK,
                drive_effects=(
                    DriveEffect(kind=DriveKind.THIRST, delta=-0.7, confidence=0.8),
                ),
            ),
            _future(
                "wait",
                ActionDirection.WAIT,
                harm=0.4,
                drive_effects=(
                    DriveEffect(
                        kind=DriveKind.PREDICTABILITY, delta=0.2, confidence=0.8
                    ),
                ),
            ),
        ),
        confidence=1.0,
    )
    evaluation = await MotivationAppraisal().evaluate(
        _loop_input(thirst=80.0, goals=goals),
        _situation(SituationClaimCode.RESOURCE_PRESENT),
        _self_model(),
        futures,
    )
    assert len(evaluation.appraisals) == 2
    assert len(evaluation.active_drive_kinds) >= 1
    assert evaluation.active_goal_ids == (GoalId("goal-thirst"),)
    drink = next(item for item in evaluation.appraisals if item.future_id == "drink")
    wait = next(item for item in evaluation.appraisals if item.future_id == "wait")
    assert drink.support_goal_count >= 0
    assert wait.mortality is not None
    assert evaluation.scores  # lossy compatibility projection retained
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "motivation_complete" in messages
    assert POLICY_VERSION
    assert "secret-drink" not in messages


@pytest.mark.asyncio
async def test_motivation_deterministic_for_identical_inputs() -> None:
    loop_input = _loop_input(thirst=40.0)
    futures = await ImaginationEngine().imagine(
        loop_input,
        _situation(SituationClaimCode.LOCAL_SCENE),
        _self_model(),
        RetrievedMemoryContext(
            owner_id=AgentId("agent-1"),
            memory_ids=(),
            belief_ids=(),
            confidence=1.0,
        ),
    )
    first = await MotivationAppraisal().evaluate(
        loop_input, _situation(SituationClaimCode.LOCAL_SCENE), _self_model(), futures
    )
    second = await MotivationAppraisal().evaluate(
        loop_input, _situation(SituationClaimCode.LOCAL_SCENE), _self_model(), futures
    )
    assert [item.future_id for item in first.appraisals] == [
        item.future_id for item in second.appraisals
    ]
    assert [item.motive for item in first.scores] == [
        item.motive for item in second.scores
    ]
    assert [item.score for item in first.scores] == [
        item.score for item in second.scores
    ]
