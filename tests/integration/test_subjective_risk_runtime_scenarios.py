"""In-memory WorldEngine admission for subjectively divergent commands.

No PostgreSQL, Docker, network, or live LLM. Holds objective world seed/bootstrap
constant while varying only beliefs/goals, then admits resulting commands.
"""

from __future__ import annotations

import pytest
from tests.cognition_helpers import (
    FixedMemoryRetriever,
    build_belief,
    build_drive_profile,
    build_goal,
    build_loop_input,
    production_cognitive_loop,
)
from tests.simulation_helpers import (
    alive_body,
    connected_locations,
    make_resource,
    weather_for_locations,
)

from agents.cognition.models import InternalAgentState
from agents.models import AgentId, DriveKind, GoalOutcome, GoalOutcomeKind
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import SimulationRunConfig
from world.actions import Drink, Flee, Help, Move, Search, Talk, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.values import ResourceKind

_SEED = 41
_COMMAND_TYPES = {Drink, Flee, Help, Move, Search, Talk, Wait}


def _bootstrap() -> WorldBootstrap:
    locations = connected_locations(("loc-1", "Camp"), ("loc-2", "Ridge"))
    return WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("body-2", location_id="loc-1"),
        ),
        resources=(
            make_resource(
                "water-1",
                name="Spring",
                kind=ResourceKind.WATER,
                location_id="loc-1",
                quantity=5.0,
            ),
        ),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )


def _engine() -> WorldEngine:
    return WorldEngine(config=SimulationRunConfig(seed=_SEED), bootstrap=_bootstrap())


@pytest.mark.asyncio
async def test_divergent_beliefs_yield_different_admitted_commands() -> None:
    engine_a = _engine()
    engine_b = _engine()
    batch_a = engine_a.observe()
    batch_b = engine_b.observe()
    observation = engine_a.observation_for(AgentId("agent-1"))

    danger = build_belief(
        predicate="is_dangerous", confidence=0.9, belief_id="belief-danger"
    )
    safety = build_belief(
        predicate="is_safe", confidence=0.9, belief_id="belief-safe"
    )

    result_danger = await production_cognitive_loop(
        memory=FixedMemoryRetriever(beliefs=(danger,))
    ).run(
        build_loop_input(observation, beliefs=(danger,)),
        invocation_id="inv-danger",
    )
    result_safety = await production_cognitive_loop(
        memory=FixedMemoryRetriever(beliefs=(safety,))
    ).run(
        build_loop_input(observation, beliefs=(safety,)),
        invocation_id="inv-safety",
    )

    assert type(result_danger.command) is not type(result_safety.command)
    assert type(result_danger.command) is Search
    assert type(result_safety.command) is Move

    tick_a = engine_a.resolve_tick(
        (
            ActionSubmission(
                token=batch_a.token,
                agent_id=AgentId("agent-1"),
                command=result_danger.command,
            ),
        )
    )
    tick_b = engine_b.resolve_tick(
        (
            ActionSubmission(
                token=batch_b.token,
                agent_id=AgentId("agent-1"),
                command=result_safety.command,
            ),
        )
    )
    assert tick_a.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert tick_b.resolutions[0].status is ActionResolutionStatus.APPLIED


@pytest.mark.asyncio
async def test_identical_submissions_on_seeded_engines_match() -> None:
    engine_a = _engine()
    engine_b = _engine()
    batch_a = engine_a.observe()
    batch_b = engine_b.observe()
    observation = engine_a.observation_for(AgentId("agent-1"))

    danger = build_belief(
        predicate="is_dangerous", confidence=0.9, belief_id="belief-danger"
    )
    result = await production_cognitive_loop(
        memory=FixedMemoryRetriever(beliefs=(danger,))
    ).run(
        build_loop_input(observation, beliefs=(danger,)),
        invocation_id="inv-same",
    )
    assert type(result.command) is Search

    tick_a = engine_a.resolve_tick(
        (
            ActionSubmission(
                token=batch_a.token,
                agent_id=AgentId("agent-1"),
                command=result.command,
            ),
        )
    )
    tick_b = engine_b.resolve_tick(
        (
            ActionSubmission(
                token=batch_b.token,
                agent_id=AgentId("agent-1"),
                command=result.command,
            ),
        )
    )
    assert tick_a.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert tick_b.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert tick_a.tick == tick_b.tick
    assert tick_a.resulting_revision == tick_b.resulting_revision
    assert len(tick_a.events) == len(tick_b.events)

    engine_a.observe()
    engine_b.observe()
    body_a = engine_a.observation_for(AgentId("agent-1")).self_body
    body_b = engine_b.observation_for(AgentId("agent-1")).self_body
    assert body_a is not None and body_b is not None
    assert body_a.location_id == body_b.location_id
    assert body_a.thirst.value == body_b.thirst.value


@pytest.mark.asyncio
async def test_two_agents_different_goals_different_commands_both_admitted() -> None:
    engine = _engine()
    batch = engine.observe()
    obs_1 = engine.observation_for(AgentId("agent-1"))
    obs_2 = engine.observation_for(AgentId("agent-2"))

    danger = build_belief(
        predicate="is_dangerous",
        confidence=0.9,
        belief_id="belief-d",
        owner="agent-1",
    )
    explore_goal = build_goal(
        owner="agent-2",
        goal_id="goal-explore",
        description="secret-explore",
        outcome=GoalOutcome(
            kind=GoalOutcomeKind.GATHER_INFORMATION, outcome_code="scan"
        ),
    )
    pred = build_drive_profile(
        owner="agent-2",
        boosts={
            DriveKind.PREDICTABILITY: (0.95, 0.95),
            DriveKind.NOVELTY: (0.05, 0.05),
            DriveKind.CURIOSITY: (0.05, 0.05),
            DriveKind.THIRST: (0.05, 0.05),
            DriveKind.SAFETY: (0.2, 0.2),
        },
    )

    result_1 = await production_cognitive_loop(
        memory=FixedMemoryRetriever(beliefs=(danger,))
    ).run(
        build_loop_input(obs_1, owner="agent-1", beliefs=(danger,)),
        invocation_id="inv-a1",
    )
    result_2 = await production_cognitive_loop().run(
        build_loop_input(
            obs_2,
            owner="agent-2",
            goals=(explore_goal,),
            drives=pred,
        ),
        invocation_id="inv-a2",
    )

    assert type(result_1.command) is not type(result_2.command)
    assert type(result_1.command) in _COMMAND_TYPES
    assert type(result_2.command) in _COMMAND_TYPES

    tick = engine.resolve_tick(
        (
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-1"),
                command=result_1.command,
            ),
            ActionSubmission(
                token=batch.token,
                agent_id=AgentId("agent-2"),
                command=result_2.command,
            ),
        )
    )
    assert all(
        resolution.status is ActionResolutionStatus.APPLIED
        for resolution in tick.resolutions
    )


@pytest.mark.asyncio
async def test_cognitive_loop_input_uses_internal_state_owner() -> None:
    engine = _engine()
    engine.observe()
    observation = engine.observation_for(AgentId("agent-1"))
    loop_input = build_loop_input(observation)
    assert loop_input.agent_id == AgentId("agent-1")
    assert type(loop_input.internal_state) is InternalAgentState
    assert loop_input.internal_state.owner_id == AgentId("agent-1")
