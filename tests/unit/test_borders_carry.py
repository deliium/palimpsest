# mypy: ignore-errors
"""Owner-scoped border ledger carry through cognition, checkpoints, and export."""

from __future__ import annotations

import dataclasses

import pytest

from agents.cognition.borders import (
    BorderLedger,
    empty_border_ledger,
    require_owner_borders,
)
from agents.cognition.configuration import (
    CognitionBordersMode,
    build_cognitive_loop,
    production_cognition_config,
)
from agents.cognition.contracts import Perspective
from agents.cognition.fork_state import CognitiveLoopForkState
from agents.cognition.models import CognitiveLoopProposal, CognitiveLoopResult
from agents.models import Agent, AgentId
from memory.models import BeliefStore, MemoryStore
from simulation.agent_runtime import AgentRuntime
from simulation.bootstrap import registration_translator
from simulation.clock import Tick
from simulation.lifecycle import TickToken
from simulation.runner_models import SimulationRunnerResult
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

OWNER = AgentId("agent-1")
OWNER_ENTITY = EntityId("body-1")


def _observation(tick: int = 0) -> Observation:
    body = AgentBody(
        entity_id=OWNER_ENTITY,
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
    return Observation(
        world_id=WorldId("world-carry"),
        observer_id=OWNER_ENTITY,
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


def _bootstrap():
    from tests.unit.test_agent_runtime import _bootstrap as helper

    return helper()


def _loop(*, borders: bool):
    config = production_cognition_config()
    if borders:
        config = dataclasses.replace(
            config,
            borders_mode=CognitionBordersMode.DETERMINISTIC,
        )
    return build_cognitive_loop(config)


def _runtime(*, borders: bool) -> AgentRuntime:
    bootstrap = _bootstrap()
    memories = MemoryStore(OWNER)
    beliefs = BeliefStore(OWNER)
    return AgentRuntime(
        agent=Agent(agent_id=OWNER, name="agent-1", goals=()),
        translator=registration_translator(bootstrap),
        cognitive_loop=_loop(borders=borders),
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )


def _token(tick: int = 0) -> TickToken:
    return TickToken(value=f"tok-{tick}", tick=Tick(tick))


@pytest.mark.asyncio
async def test_disabled_mode_carries_none() -> None:
    runtime = _runtime(borders=False)
    runtime.start()
    result = await runtime.process_observation(_observation(), token=_token())
    assert result.loop_result is not None
    assert result.loop_result.borders is None
    assert runtime.export_runtime_checkpoint().borders is None


@pytest.mark.asyncio
async def test_enabled_mode_carries_an_empty_ledger() -> None:
    runtime = _runtime(borders=True)
    runtime.start()
    result = await runtime.process_observation(_observation(), token=_token())
    assert result.loop_result is not None
    ledger = result.loop_result.borders
    assert type(ledger) is BorderLedger
    assert ledger.owner_id == OWNER
    assert runtime.export_runtime_checkpoint().borders == ledger


@pytest.mark.asyncio
async def test_checkpoint_restore_and_export_round_trip() -> None:
    runtime = _runtime(borders=True)
    runtime.start()
    await runtime.process_observation(_observation(), token=_token())
    checkpoint = runtime.export_runtime_checkpoint()
    restored = _runtime(borders=True)
    restored.restore_runtime_checkpoint(checkpoint)
    reexported = restored.export_runtime_checkpoint()
    assert reexported.borders == checkpoint.borders


def test_perspective_rejects_a_foreign_ledger() -> None:
    foreign = empty_border_ledger(AgentId("agent-2"))
    with pytest.raises(ValueError):
        Perspective(
            agent_id=OWNER,
            observation=_observation(),
            memories=(),
            beliefs=(),
            inbox=(),
            borders=foreign,
        )
    own = empty_border_ledger(OWNER)
    perspective = Perspective(
        agent_id=OWNER,
        observation=_observation(),
        memories=(),
        beliefs=(),
        inbox=(),
        borders=own,
    )
    assert perspective.to_snapshot().borders == own


def test_snapshot_proposal_and_result_require_owner_identity() -> None:
    for model in (CognitiveLoopProposal, CognitiveLoopResult):
        fields = {item.name for item in dataclasses.fields(model)}
        assert "borders" in fields
    require_owner_borders(empty_border_ledger(OWNER), OWNER, field_name="x")
    with pytest.raises(ValueError):
        require_owner_borders(
            empty_border_ledger(AgentId("agent-2")), OWNER, field_name="x"
        )


def test_fork_state_carries_prepared_borders() -> None:
    fields = {item.name for item in dataclasses.fields(CognitiveLoopForkState)}
    assert "prepared_borders" in fields


def test_runner_result_exports_owner_ordered_ledgers() -> None:
    fields = {item.name for item in dataclasses.fields(SimulationRunnerResult)}
    assert "border_ledgers" in fields


def test_world_and_observer_do_not_receive_border_fields() -> None:
    from agents.cognition import contracts
    from simulation import perception

    assert "borders" in {
        item.name for item in dataclasses.fields(contracts.Perspective)
    }
    assert "borders" in perception.build_perspective.__code__.co_varnames
