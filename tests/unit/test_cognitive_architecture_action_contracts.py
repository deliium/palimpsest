"""Contract tests: each architecture yields a closed AgentCommand."""

from __future__ import annotations

import logging

import pytest

from agents.cognition import build_cognitive_loop
from agents.cognition.architectures import (
    ARCHITECTURES,
    compose_loop_config_from_snapshot,
)
from agents.cognition.models import CognitiveLoopInput, InternalAgentState
from agents.models import AgentId
from experiments.architectures import (
    expand_architecture,
    mode_snapshot_from_runner_config,
)
from simulation.runner import _cognition_config_for
from tests.unit.test_runner_models import _config
from world.actions import agent_command_tag, require_agent_command
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


def _alive_self() -> ObservedSelf:
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


def _loop_input() -> CognitiveLoopInput:
    agent = AgentId("agent-1")
    return CognitiveLoopInput(
        agent_id=agent,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
            tick=1,
            self_body=_alive_self(),
        ),
        internal_state=InternalAgentState(owner_id=agent),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("architecture_id", sorted(ARCHITECTURES))
async def test_each_architecture_emits_closed_agent_command(
    architecture_id: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    base = _config()
    expanded = expand_architecture(base, architecture_id)
    spec = expanded.agents[0].cognition
    runner_loop_config = _cognition_config_for(
        spec,
        mortality_mode=expanded.mortality_mode,
        capability_flags=expanded.capability_flags,
    )
    snapshot = mode_snapshot_from_runner_config(expanded)
    composed = compose_loop_config_from_snapshot(
        snapshot, architecture_id=architecture_id
    )
    # Authoritative expand → runner binding must agree with snapshot compose.
    assert composed.memory_mode is runner_loop_config.memory_mode
    assert composed.imagination_mode is runner_loop_config.imagination_mode
    assert composed.reflection_mode is runner_loop_config.reflection_mode
    assert composed.prospective_mode is runner_loop_config.prospective_mode
    assert composed.emotional_state_mode is runner_loop_config.emotional_state_mode
    assert composed.identity_mode is runner_loop_config.identity_mode
    assert composed.world_model_mode is runner_loop_config.world_model_mode
    assert composed.theory_of_mind_mode is runner_loop_config.theory_of_mind_mode

    loop = build_cognitive_loop(runner_loop_config)
    with caplog.at_level(logging.DEBUG):
        result = await loop.run(_loop_input(), invocation_id=f"arch-{architecture_id}")
    command = require_agent_command(result.command)
    assert command is result.command
    tag = agent_command_tag(command)
    assert isinstance(tag, str) and tag
    assert not hasattr(loop, "architecture_id")
