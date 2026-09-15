"""WorldEngine admission uses canonical ordinal-scoped identifiers."""

from __future__ import annotations

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from world.actions import Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst


def _body(entity_id: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId("loc-1"),
        health=Health(10),
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
        bodies=(_body("body-1"), _body("body-2")),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )


def test_request_ids_depend_on_ordinal_not_prior_outcomes() -> None:
    engine_a = WorldEngine(config=SimulationRunConfig(seed=11), bootstrap=_bootstrap())
    engine_b = WorldEngine(config=SimulationRunConfig(seed=11), bootstrap=_bootstrap())
    token_a = engine_a.observe().token
    token_b = engine_b.observe().token
    result_a = engine_a.resolve_tick(
        (
            ActionSubmission(token_a, AgentId("agent-1"), Wait()),
            ActionSubmission(token_a, AgentId("agent-2"), Wait()),
        )
    )
    result_b = engine_b.resolve_tick(
        (
            ActionSubmission(token_b, AgentId("agent-2"), Wait()),
            ActionSubmission(token_b, AgentId("agent-1"), Wait()),
        )
    )
    assert result_a.resolutions[0].request_id != result_b.resolutions[0].request_id
    by_agent_a = {item.agent_id: item.request_id for item in result_a.resolutions}
    by_agent_b = {item.agent_id: item.request_id for item in result_b.resolutions}
    assert by_agent_a[AgentId("agent-1")] != by_agent_b[AgentId("agent-1")]
