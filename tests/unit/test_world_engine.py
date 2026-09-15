"""WorldEngine observation and resolution lifecycle."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import EnginePhase, WorldEngine
from simulation.lifecycle import (
    ActionResolutionStatus,
    ActionSubmission,
)
from simulation.models import SimulationRunConfig
from world.actions import Take, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, Item, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst


def _alive(entity_id: str, location_id: str = "loc-1") -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
    )


def _bootstrap() -> WorldBootstrap:
    return WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
        items=(
            Item(
                entity_id=EntityId("item-1"),
                name="Rock",
                location_id=EntityId("loc-1"),
            ),
        ),
        bodies=(_alive("body-1"), _alive("body-2")),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )


def test_observe_is_idempotent_within_open_tick() -> None:
    engine = WorldEngine(config=SimulationRunConfig(seed=1), bootstrap=_bootstrap())
    assert engine.phase is EnginePhase.AWAITING_OBSERVATION
    first = engine.observe()
    second = engine.observe()
    assert first == second
    assert engine.phase.value == EnginePhase.AWAITING_SUBMISSIONS.value
    assert first.token.tick.value == 0


def test_resolve_wait_and_take_advances_tick_and_revision(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = WorldEngine(config=SimulationRunConfig(seed=2), bootstrap=_bootstrap())
    batch = engine.observe()
    caplog.set_level(logging.DEBUG, logger="simulation.engine")
    result = engine.resolve_tick(
        (
            ActionSubmission(batch.token, AgentId("agent-1"), Take(EntityId("item-1"))),
            ActionSubmission(batch.token, AgentId("agent-2"), Wait()),
        )
    )
    assert result.tick.value == 0
    assert result.resulting_tick.value == 1
    assert result.base_revision == WorldRevision(0)
    assert result.resulting_revision == WorldRevision(1)
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert result.resolutions[1].status is ActionResolutionStatus.APPLIED
    assert engine.tick.value == 1
    assert engine.revision == WorldRevision(1)
    assert engine.phase is EnginePhase.AWAITING_OBSERVATION
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "tick_committed" in messages
    assert "Rock" not in messages


def test_duplicate_submission_and_stale_token() -> None:
    engine = WorldEngine(config=SimulationRunConfig(seed=3), bootstrap=_bootstrap())
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(batch.token, AgentId("agent-1"), Wait()),
            ActionSubmission(batch.token, AgentId("agent-1"), Wait()),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert result.resolutions[1].status is ActionResolutionStatus.DUPLICATE

    batch2 = engine.observe()
    with pytest.raises(ValueError, match=r"stale|mismatch"):
        engine.resolve_tick(
            (ActionSubmission(batch.token, AgentId("agent-1"), Wait()),)
        )
    # Engine remains usable after failed resolve with prior snapshot preserved.
    engine.resolve_tick(
        (ActionSubmission(batch2.token, AgentId("agent-2"), Wait()),)
    )
