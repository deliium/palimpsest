"""Unit tests for prepare/bind/finalize runtime boundary."""

from __future__ import annotations

import pytest

from agents.cognition.defaults import default_cognitive_loop
from agents.models import Agent, AgentId
from memory.models import BeliefStore, MemoryStore
from simulation.agent_runtime import (
    AgentRuntime,
    AgentRuntimeError,
    AgentRuntimeErrorCode,
    PendingRuntimeFinalization,
    PreparedObservation,
)
from simulation.bootstrap import (
    AgentRegistration,
    WorldBootstrap,
    registration_translator,
)
from simulation.clock import Tick
from simulation.lifecycle import TickToken
from tests.simulation_helpers import make_location, weather_for_locations
from world.actions import Move
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus
from world.observations import Observation, ObservedSelf
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _body() -> AgentBody:
    return AgentBody(
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


def _runtime() -> tuple[AgentRuntime, MemoryStore]:
    locations = (make_location("loc-1", name="Camp"),)
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(_body(),),
        weather=weather_for_locations(locations),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
    )
    memories = MemoryStore(AgentId("agent-1"))
    beliefs = BeliefStore(AgentId("agent-1"))
    runtime = AgentRuntime(
        agent=Agent(agent_id=AgentId("agent-1"), name="agent-1", goals=()),
        translator=registration_translator(bootstrap),
        cognitive_loop=default_cognitive_loop(),
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )
    return runtime, memories


def _obs(*, tick: int = 0) -> Observation:
    body = _body()
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=body.entity_id,
            location_id=body.location_id,
            health=body.health,
            hunger=body.hunger,
            thirst=body.thirst,
            fatigue=body.fatigue,
            temperature=body.temperature,
            inventory=body.inventory,
            life_status=body.life_status,
            carry_capacity=body.carry_capacity,
        ),
    )


def _token(tick: int = 0) -> TickToken:
    return TickToken(value=f"tok-{tick}", tick=Tick(tick))


@pytest.mark.asyncio
async def test_prepare_does_not_mutate_and_bind_uses_effective_command() -> None:
    runtime, memories = _runtime()
    runtime.start()
    prepared = await runtime.prepare_observation(_obs(tick=0), token=_token(0))
    assert isinstance(prepared, PreparedObservation)
    assert runtime.internal_state.invocation_count == 0
    assert len(memories.snapshot()) == 0

    pending = await runtime.bind_effective_command(
        prepared, effective_command=Move(destination_id=EntityId("loc-2"))
    )
    assert isinstance(pending, PendingRuntimeFinalization)
    assert pending.effective_command_kind == "move"
    assert type(pending.submission.command) is Move
    assert runtime.internal_state.invocation_count == 0

    result = await runtime.finalize_pending(pending)
    assert result.submission is not None
    assert type(result.submission.command) is Move
    assert runtime.internal_state.invocation_count == 1
    assert runtime.internal_state.last_command_kind == "move"


@pytest.mark.asyncio
async def test_abort_pending_allows_retry() -> None:
    runtime, _ = _runtime()
    runtime.start()
    prepared = await runtime.prepare_observation(_obs(tick=1), token=_token(1))
    assert isinstance(prepared, PreparedObservation)
    pending = await runtime.bind_effective_command(prepared)
    runtime.abort_pending(pending)
    with pytest.raises(AgentRuntimeError) as exc_info:
        await runtime.finalize_pending(pending)
    assert exc_info.value.code is AgentRuntimeErrorCode.PENDING_MISSING

    prepared2 = await runtime.prepare_observation(_obs(tick=1), token=_token(1))
    pending2 = await runtime.bind_effective_command(prepared2)
    result = await runtime.finalize_pending(pending2)
    assert result.invocation_id == pending2.invocation_id
