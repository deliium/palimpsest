"""Perspective / snapshot carry for owner-scoped cultural feature ledgers."""

from __future__ import annotations

import logging
from types import MappingProxyType

import pytest

from agents.cognition.contracts import Perspective
from agents.cognition.cultural_features import (
    empty_cultural_feature_ledger,
    form_or_reinforce_cultural_belief,
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

_LOG = logging.getLogger("tests.cultural_feature_perspective_plumb")

_CHANNELS = ("observation", "teaching")


def _observation(entity_id: EntityId) -> Observation:
    return Observation(
        world_id=WorldId("world-cultural-perspective"),
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


def test_build_perspective_accepts_cultural_features_and_snapshots(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _LOG.debug("case_id=perspective_cultural_features_plumb")
    agent_id = AgentId("bob")
    entity_id = EntityId("body-bob")
    ledger = form_or_reinforce_cultural_belief(
        empty_cultural_feature_ledger(agent_id),
        feature_kind="term",
        content_key="term-a",
        content_fingerprint="tokaaaaa",
        channel="observation",
        confidence=0.7,
        tick=1,
        enabled_provenance_channels=_CHANNELS,
        evidence_refs=("evt-1",),
    )
    with caplog.at_level(logging.DEBUG, logger="simulation.perception"):
        perspective = build_perspective(
            agent_id=agent_id,
            observation=_observation(entity_id),
            translator=_translator(agent_id, entity_id),
            cultural_features=ledger,
        )
    assert isinstance(perspective, Perspective)
    assert perspective.cultural_features is ledger
    snapshot = perspective.to_snapshot()
    assert snapshot.cultural_features is ledger
    assert "cultural_beliefs=1" in caplog.text
