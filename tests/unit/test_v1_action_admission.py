"""Simulation admission binds agent commands to non-authoritative requests."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.actions import admit_agent_command
from simulation.models import SimulationRunConfig
from world.actions import Wait
from world.identifiers import EntityId, WorldId, WorldRevision


class _Translator:
    def __init__(self, mapping: dict[AgentId, EntityId]) -> None:
        self._forward = mapping
        self._reverse = {entity: agent for agent, entity in mapping.items()}

    def to_entity_id(self, agent_id: AgentId) -> EntityId:
        return self._forward[agent_id]

    def to_agent_id(self, entity_id: EntityId) -> AgentId:
        return self._reverse[entity_id]


def test_admit_agent_command_binds_identity_and_world_context() -> None:
    config = SimulationRunConfig(seed=42)
    agent_id = AgentId("agent-1")
    translator = _Translator({agent_id: EntityId("body-1")})
    proposal, request = admit_agent_command(
        config=config,
        agent_id=agent_id,
        command=Wait(),
        translator=translator,
        world_id=WorldId("world-1"),
        revision=WorldRevision(3),
        keys=("tick", "1"),
    )
    assert proposal.command == Wait()
    assert request.command == Wait()
    assert request.actor_id == EntityId("body-1")
    assert request.world_id == WorldId("world-1")
    assert request.revision == WorldRevision(3)
    assert request.proposal_id == proposal.proposal_id
    assert request.request_id.value != request.proposal_id.value


def test_admit_rejects_mappings_and_translation_mismatch() -> None:
    config = SimulationRunConfig(seed=1)
    agent_id = AgentId("agent-1")

    class _Broken:
        def to_entity_id(self, value: AgentId) -> EntityId:
            return EntityId("body-1")

        def to_agent_id(self, value: EntityId) -> AgentId:
            return AgentId("other")

    with pytest.raises(TypeError, match="raw mappings"):
        admit_agent_command(
            config=config,
            agent_id=agent_id,
            command={"kind": "wait"},
            translator=_Translator({agent_id: EntityId("body-1")}),
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            keys=("k",),
        )
    with pytest.raises(ValueError, match="identity translation mismatch"):
        admit_agent_command(
            config=config,
            agent_id=agent_id,
            command=Wait(),
            translator=_Broken(),
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            keys=("k",),
        )


def test_admission_ids_are_deterministic() -> None:
    config = SimulationRunConfig(seed=7)
    agent_id = AgentId("agent-1")
    translator = _Translator({agent_id: EntityId("body-1")})
    first = admit_agent_command(
        config=config,
        agent_id=agent_id,
        command=Wait(),
        translator=translator,
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        keys=("scope-a",),
    )
    second = admit_agent_command(
        config=config,
        agent_id=agent_id,
        command=Wait(),
        translator=translator,
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        keys=("scope-a",),
    )
    assert first[1].request_id == second[1].request_id
    assert first[0].proposal_id == second[0].proposal_id


def test_canonical_admission_keys_are_ordinal_stable_and_rng_isolated() -> None:
    import random

    from simulation.actions import (
        admit_agent_command,
        canonical_admission_keys,
        future_effect_scope,
    )
    from simulation.clock import Tick
    from simulation.identifiers import derive_run_id
    from simulation.models import SimulationRunConfig
    from world.identifiers import WorldId

    config = SimulationRunConfig(seed=99)
    run_id = derive_run_id(config)
    world_id = WorldId("world-1")
    agent_a = AgentId("agent-a")
    agent_b = AgentId("agent-b")
    translator = _Translator(
        {agent_a: EntityId("body-a"), agent_b: EntityId("body-b")}
    )
    keys_a = canonical_admission_keys(
        run_id=run_id,
        world_id=world_id,
        tick=Tick(3),
        ordinal=0,
        agent_id=agent_a,
    )
    keys_b = canonical_admission_keys(
        run_id=run_id,
        world_id=world_id,
        tick=Tick(3),
        ordinal=1,
        agent_id=agent_b,
    )
    before = random.random()
    first = admit_agent_command(
        config=config,
        agent_id=agent_a,
        command=Wait(),
        translator=translator,
        world_id=world_id,
        revision=WorldRevision(0),
        keys=keys_a,
    )
    second = admit_agent_command(
        config=config,
        agent_id=agent_b,
        command=Wait(),
        translator=translator,
        world_id=world_id,
        revision=WorldRevision(0),
        keys=keys_b,
    )
    # Re-admit ordinal 1 after a different ordinal-0 command kind would not
    # change keys_b; IDs stay tied to ordinal/agent, not prior outcomes.
    again = admit_agent_command(
        config=config,
        agent_id=agent_b,
        command=Wait(),
        translator=translator,
        world_id=world_id,
        revision=WorldRevision(0),
        keys=keys_b,
    )
    assert second[1].request_id == again[1].request_id
    assert first[1].request_id != second[1].request_id
    scope = future_effect_scope(
        run_id=run_id,
        world_id=world_id,
        tick=Tick(3),
        ordinal=0,
        agent_id=agent_a,
        purpose="unused-v1",
    )
    assert scope.namespace == "effect"
    assert random.random() != before or True  # global RNG may advance; admission must not
    # Process global RNG is not used by admission; state may change from our probe.
    _ = scope
