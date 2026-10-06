"""Perspective / snapshot carry for owner-scoped mentorship ledgers."""

from __future__ import annotations

import logging
from types import MappingProxyType

import pytest

from agents.cognition.contracts import Perspective
from agents.cognition.mentorship import (
    MentorshipBondRole,
    MentorshipContentKindId,
    empty_mentorship_ledger,
    form_or_reinforce_mentorship_bond,
)
from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, RegistrationTranslator
from simulation.perception import build_perspective
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

_LOG = logging.getLogger("tests.mentorship_perspective_plumb")


def _observation(entity_id: EntityId) -> Observation:
    return Observation(
        world_id=WorldId("world-mentor-perspective"),
        observer_id=entity_id,
        revision=WorldRevision(0),
        tick=1,
        self_body=ObservedSelf(
            entity_id=entity_id,
            location_id=EntityId("clearing"),
            health=Health(100),
            hunger=Hunger(0),
            thirst=Thirst(0),
            fatigue=Fatigue(0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
    )


def _translator(agent_id: AgentId, entity_id: EntityId) -> RegistrationTranslator:
    registration = AgentRegistration(agent_id, entity_id)
    return RegistrationTranslator(
        _forward=MappingProxyType({agent_id: entity_id}),
        _reverse=MappingProxyType({entity_id: agent_id}),
        _order=(registration,),
    )


def test_build_perspective_accepts_mentorship_and_snapshots(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _LOG.debug("case_id=perspective_mentorship_plumb")
    agent_id = AgentId("bob")
    entity_id = EntityId("body-bob")
    ledger = form_or_reinforce_mentorship_bond(
        empty_mentorship_ledger(agent_id),
        partner_agent_id=AgentId("alice"),
        owner_role=MentorshipBondRole.APPRENTICE,
        content_kinds=(MentorshipContentKindId.PRACTICAL_SKILLS,),
        tick=1,
        successful_act_count=2,
        projected_trust=0.8,
        form_after_successful_acts=1,
        min_trust=0.1,
        reinforce_on_learning_evidence=True,
    )
    with caplog.at_level(logging.DEBUG, logger="simulation.perception"):
        perspective = build_perspective(
            agent_id=agent_id,
            observation=_observation(entity_id),
            translator=_translator(agent_id, entity_id),
            mentorship=ledger,
        )
    assert type(perspective) is Perspective
    assert perspective.mentorship is ledger
    snapshot = perspective.to_snapshot()
    assert snapshot.mentorship is ledger
    assert "mentorship_bonds=1" in caplog.text


def test_build_perspective_flags_off_mentorship_none() -> None:
    _LOG.debug("case_id=perspective_mentorship_absent")
    agent_id = AgentId("carol")
    entity_id = EntityId("body-carol")
    perspective = build_perspective(
        agent_id=agent_id,
        observation=_observation(entity_id),
        translator=_translator(agent_id, entity_id),
    )
    assert perspective.mentorship is None
    assert perspective.to_snapshot().mentorship is None
