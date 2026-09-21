"""Unit tests for multi-criteria intention selection."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.deliberation import (
    DELIBERATION_POLICY_VERSION,
    MultiCriteriaIntentionSelector,
)
from agents.cognition.models import (
    ActionDirection,
    CognitiveLoopInput,
    DriveEffect,
    FutureAppraisal,
    ImaginedFuture,
    IntentionCode,
    InternalAgentState,
    MortalityOpportunityForeclosure,
    MotivationCode,
    MotivationEvaluation,
    MotivationScore,
    OptionSpaceChange,
    PossibleFutures,
    SituationClaimCode,
    SubjectiveRisk,
    SubjectiveRiskKind,
    SubjectiveUncertainty,
)
from agents.models import AgentId, DriveKind
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    CoarseHealth,
    Observation,
    ObservedResource,
    ObservedSelf,
    VisibleBody,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
)


def _self(*, thirst: float = 0.0) -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(thirst),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _loop_input(
    *, thirst: float = 0.0, with_water: bool = False, with_threat: bool = False
) -> CognitiveLoopInput:
    agent = AgentId("agent-1")
    resources = ()
    bodies = ()
    if with_water:
        resources = (
            ObservedResource(
                entity_id=EntityId("water-1"),
                name="spring",
                kind=ResourceKind.WATER,
                quantity=3.0,
                unit="L",
            ),
        )
    if with_threat:
        bodies = (
            VisibleBody(
                entity_id=EntityId("body-2"),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.INJURED,
            ),
        )
    return CognitiveLoopInput(
        agent_id=agent,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
            tick=5,
            self_body=_self(thirst=thirst),
            resources=resources,
            visible_bodies=bodies,
        ),
        internal_state=InternalAgentState(owner_id=agent),
    )


def _future(
    future_id: str,
    direction: ActionDirection,
    *,
    target: str | None = None,
    thirst_relief: float = 0.0,
    safety: float = 0.0,
    harm: float = 0.0,
    death_probability: float = 0.0,
) -> ImaginedFuture:
    drives = []
    if thirst_relief:
        drives.append(
            DriveEffect(kind=DriveKind.THIRST, delta=-thirst_relief, confidence=0.9)
        )
    if safety:
        drives.append(DriveEffect(kind=DriveKind.SAFETY, delta=safety, confidence=0.9))
    if direction is ActionDirection.WAIT:
        drives.append(
            DriveEffect(kind=DriveKind.PREDICTABILITY, delta=0.2, confidence=0.8)
        )
    risks = ()
    if harm > 0.0:
        risks = (
            SubjectiveRisk(
                kind=SubjectiveRiskKind.PHYSICAL_HARM,
                severity=harm,
                likelihood=harm,
                confidence=0.9,
            ),
        )
    mortality = None
    if death_probability > 0.0:
        mortality = MortalityOpportunityForeclosure(
            death_probability=death_probability,
            outstanding_goal_value=0.5,
            attachment_loss=0.2,
            safety_activation=0.6,
            autonomy_loss=0.2,
            option_space=OptionSpaceChange(
                retained_options_ratio=0.5, foreclosed_ratio=0.4
            ),
        )
    return ImaginedFuture(
        future_id=future_id,
        claim_codes=(SituationClaimCode.LOCAL_SCENE,),
        confidence=0.7,
        direction=direction,
        target_entity_id=target,
        drive_effects=tuple(drives),
        risks=risks,
        uncertainty=SubjectiveUncertainty(),
        mortality=mortality,
        subjective_probability=0.7,
    )


def _appraisal(future: ImaginedFuture) -> FutureAppraisal:
    support_drives = 0
    for item in future.drive_effects:
        if item.kind in {DriveKind.HUNGER, DriveKind.THIRST, DriveKind.FATIGUE}:
            if item.delta < 0.0:
                support_drives += 1
        elif item.delta > 0.0:
            support_drives += 1
    return FutureAppraisal(
        future_id=future.future_id,
        drive_effects=future.drive_effects,
        goal_effects=future.goal_effects,
        risks=future.risks,
        mortality=future.mortality,
        uncertainty=future.uncertainty,
        support_drive_count=support_drives,
        support_goal_count=0,
        support_social_count=0,
    )


def _motivation(
    futures: tuple[ImaginedFuture, ...], *, active_drives: tuple[DriveKind, ...] = ()
) -> MotivationEvaluation:
    return MotivationEvaluation(
        owner_id=AgentId("agent-1"),
        scores=(MotivationScore(motive=MotivationCode.WAIT, score=0.5),),
        confidence=0.7,
        appraisals=tuple(_appraisal(future) for future in futures),
        active_drive_kinds=active_drives
        or (DriveKind.SAFETY, DriveKind.THIRST, DriveKind.PREDICTABILITY),
    )


@pytest.mark.asyncio
async def test_critical_thirst_prefers_drink_over_wait(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.deliberation")
    futures = (
        _future("wait", ActionDirection.WAIT),
        _future("drink", ActionDirection.DRINK, target="water-1", thirst_relief=0.8),
        _future("search", ActionDirection.SEARCH),
    )
    selected = await MultiCriteriaIntentionSelector().select(
        _loop_input(thirst=90.0, with_water=True),
        _motivation(futures, active_drives=(DriveKind.THIRST, DriveKind.SAFETY)),
        PossibleFutures(owner_id=AgentId("agent-1"), futures=futures, confidence=1.0),
    )
    assert selected.direction is ActionDirection.DRINK
    assert selected.intention is IntentionCode.DRINK
    assert selected.selected_future_id == "drink"
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "deliberation_complete" in messages
    assert DELIBERATION_POLICY_VERSION
    assert "water-1" not in messages


@pytest.mark.asyncio
async def test_high_harm_vetoes_wait_when_flee_available() -> None:
    futures = (
        _future("wait", ActionDirection.WAIT, harm=0.8, death_probability=0.7),
        _future(
            "flee",
            ActionDirection.FLEE,
            target="body-2",
            safety=0.7,
            harm=0.2,
            death_probability=0.2,
        ),
    )
    selected = await MultiCriteriaIntentionSelector().select(
        _loop_input(with_threat=True),
        _motivation(futures, active_drives=(DriveKind.SAFETY, DriveKind.AUTONOMY)),
        PossibleFutures(owner_id=AgentId("agent-1"), futures=futures, confidence=1.0),
    )
    assert selected.direction is ActionDirection.FLEE
    assert selected.intention is IntentionCode.FLEE


@pytest.mark.asyncio
async def test_pareto_and_tie_break_are_stable() -> None:
    futures = (
        _future("wait-a", ActionDirection.WAIT),
        _future("wait-b", ActionDirection.WAIT),
    )
    motivation = _motivation(futures, active_drives=(DriveKind.PREDICTABILITY,))
    possible = PossibleFutures(
        owner_id=AgentId("agent-1"), futures=futures, confidence=1.0
    )
    selector = MultiCriteriaIntentionSelector()
    first = await selector.select(_loop_input(), motivation, possible)
    second = await selector.select(_loop_input(), motivation, possible)
    assert first.selected_future_id == second.selected_future_id
    assert first.decision_metadata.tie_break_applied is True


@pytest.mark.asyncio
async def test_infeasible_targets_fall_back_to_wait() -> None:
    futures = (
        _future(
            "drink", ActionDirection.DRINK, target="missing-water", thirst_relief=0.9
        ),
    )
    selected = await MultiCriteriaIntentionSelector().select(
        _loop_input(thirst=90.0, with_water=False),
        _motivation(futures, active_drives=(DriveKind.THIRST,)),
        PossibleFutures(owner_id=AgentId("agent-1"), futures=futures, confidence=1.0),
    )
    assert selected.direction is ActionDirection.WAIT
    assert selected.intention is IntentionCode.WAIT
