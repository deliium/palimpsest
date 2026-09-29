"""Ledger carry and the single reputation testimony command."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.configuration import CognitionReputationMode
from agents.cognition.deliberation import CommandPlanner
from agents.cognition.models import (
    ActionDirection,
    CognitiveLoopInput,
    CounterpartBinding,
    ImaginedFuture,
    IntentionCode,
    InternalAgentState,
    MotivationCode,
    OwnerSafeSocialIdentity,
    PossibleFutures,
    SelectedIntention,
    SituationClaimCode,
    SubjectiveSnapshot,
)
from agents.cognition.reputation import (
    ReputationDimensionState,
    ReputationLedger,
    ReputationProfile,
    default_reputation_policy,
    neutral_dimension_state,
    reputation_profile_id,
)
from agents.models import AgentId
from world.actions import Help, Tell, Wait
from world.communications import CommunicationSourceBasis
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    CoarseHealth,
    Observation,
    ObservedSelf,
    VisibleBody,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _owner() -> AgentId:
    return AgentId("agent-east")


def _identity() -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=_owner(),
        owner_entity_id=EntityId("body-east"),
        counterparts=(
            CounterpartBinding(
                agent_id=AgentId("agent-east-b"),
                entity_id=EntityId("body-east-b"),
            ),
            CounterpartBinding(
                agent_id=AgentId("agent-focal"),
                entity_id=EntityId("body-focal"),
            ),
        ),
    )


def _body() -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-east"),
        location_id=EntityId("east"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _observation() -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-east"),
        revision=WorldRevision(1),
        tick=4,
        self_body=_body(),
        visible_bodies=(
            VisibleBody(
                entity_id=EntityId("body-east-b"),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
            VisibleBody(
                entity_id=EntityId("body-focal"),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
        ),
        visibility=1.0,
    )


def _snapshot() -> SubjectiveSnapshot:
    return SubjectiveSnapshot(
        owner_id=_owner(),
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        social_identity=_identity(),
    )


def _ledger(generosity: float) -> ReputationLedger:
    owner = _owner()
    target = AgentId("agent-focal")
    return ReputationLedger(
        owner_id=owner,
        profiles=(
            ReputationProfile(
                profile_id=reputation_profile_id(owner, target),
                owner_id=owner,
                target_id=target,
                reliability=neutral_dimension_state(),
                harm=neutral_dimension_state(),
                generosity=ReputationDimensionState(
                    value=generosity,
                    support_mass=generosity,
                    contradiction_mass=0.0,
                ),
                competence=neutral_dimension_state(),
            ),
        ),
    )


def _input() -> CognitiveLoopInput:
    return CognitiveLoopInput(
        agent_id=_owner(),
        observation=_observation(),
        internal_state=InternalAgentState(owner_id=_owner()),
        snapshot=_snapshot(),
    )


def _selected(direction: ActionDirection, future_id: str) -> SelectedIntention:
    return SelectedIntention(
        owner_id=_owner(),
        intention=IntentionCode.WAIT,
        source_motive=MotivationCode.WAIT,
        confidence=0.8,
        selected_future_id=future_id,
        direction=direction,
        appraisal_future_ids=(future_id,),
    )


def _futures(direction: ActionDirection, future_id: str, target: str | None = None):
    return PossibleFutures(
        owner_id=_owner(),
        futures=(
            ImaginedFuture(
                future_id=future_id,
                claim_codes=(SituationClaimCode.IDLE,),
                confidence=1.0,
                direction=direction,
                target_entity_id=target,
            ),
        ),
        confidence=1.0,
    )


@pytest.mark.asyncio
async def test_enabled_wait_becomes_one_dimension_tell(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.deliberation")
    plan = await CommandPlanner().plan(
        _input(),
        _selected(ActionDirection.WAIT, "idle"),
        _futures(ActionDirection.WAIT, "idle"),
        reputation=_ledger(0.4),
        reputation_mode=CognitionReputationMode.DETERMINISTIC,
        reputation_policy=default_reputation_policy(),
    )
    command = plan.command
    assert type(command) is Tell
    assert command.recipient_id == EntityId("body-east-b")
    assert command.utterance.declared.source_basis is (
        CommunicationSourceBasis.UNREFERENCED
    )
    assert command.utterance.content.text == "generosity"
    relation = command.utterance.content.relations[0]
    assert relation.subject == "body-focal"
    assert relation.predicate == "generosity"
    assert relation.object == "0.4"
    assert "reputation_testimony_emitted" in caplog.text
    assert "0.4" not in caplog.text
    assert "trustworthy" not in caplog.text


@pytest.mark.asyncio
async def test_help_stays_when_reputation_would_speak(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.deliberation")
    plan = await CommandPlanner().plan(
        _input(),
        _selected(ActionDirection.HELP, "help"),
        _futures(ActionDirection.HELP, "help", "body-focal"),
        reputation=_ledger(0.4),
        reputation_mode=CognitionReputationMode.DETERMINISTIC,
        reputation_policy=default_reputation_policy(),
    )
    assert type(plan.command) is Help
    assert "command_already_selected" in caplog.text


@pytest.mark.asyncio
async def test_disabled_mode_does_not_emit_a_reputation_tell(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="agents.cognition.deliberation")
    plan = await CommandPlanner().plan(
        _input(),
        _selected(ActionDirection.WAIT, "idle"),
        _futures(ActionDirection.WAIT, "idle"),
        reputation=_ledger(0.4),
        reputation_mode=CognitionReputationMode.DISABLED,
    )
    assert type(plan.command) is Wait
    assert _input().snapshot is not None
    assert _input().snapshot.reputation is None
    assert "mode_disabled" in caplog.text


def test_runtime_checkpoint_copies_the_owner_ledger() -> None:
    from tests.unit.test_identity_runtime import _runtime

    runtime, _reader = _runtime()
    owner = runtime.agent.agent_id
    target = AgentId("agent-focal")
    ledger = ReputationLedger(
        owner_id=owner,
        profiles=(
            ReputationProfile(
                profile_id=reputation_profile_id(owner, target),
                owner_id=owner,
                target_id=target,
                reliability=neutral_dimension_state(),
                harm=neutral_dimension_state(),
                generosity=ReputationDimensionState(
                    value=0.4,
                    support_mass=0.4,
                    contradiction_mass=0.0,
                ),
                competence=neutral_dimension_state(),
            ),
        ),
    )
    runtime._reputation = ledger
    exported = runtime.export_runtime_checkpoint()
    assert exported.reputation == ledger
    other, _other_reader = _runtime()
    other.restore_runtime_checkpoint(exported)
    assert other._reputation == ledger
