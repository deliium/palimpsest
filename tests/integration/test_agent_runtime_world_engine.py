"""In-memory AgentRuntime ↔ WorldEngine observation/admission integration.

No PostgreSQL, Docker, network, or real LLM. Default cognition uses the
production subjective policies; intentional failure/injection cases still
constructor-inject placeholder stages and fixed planners.
"""

from __future__ import annotations

from agents.cognition.emotion import PassthroughEmotionalStateAppraiser

import logging

import pytest
from tests.simulation_helpers import make_location, weather_for_locations

from agents.cognition.defaults import (
        PassthroughGoalManager,
    DirectSelfStateProjector,
    DirectSituationModeler,
    EmptyMemoryRetriever,
    EmptyMemoryUpdateHook,
    LiteralPerceptionInterpreter,
    PlaceholderFutureImagination,
    StableIntentionSelector,
    StableMotivationEvaluator,
    default_cognitive_loop,
)
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import ActionPlan, CognitiveLoopInput
from agents.models import Agent, AgentId
from memory.models import BeliefStore, MemoryStore
from simulation.agent_runtime import (
    AgentRuntime,
    AgentRuntimeError,
    AgentRuntimeErrorCode,
    AgentRuntimeStatus,
)
from simulation.bootstrap import (
    AgentRegistration,
    WorldBootstrap,
    registration_translator,
)
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission, TickToken
from simulation.models import SimulationRunConfig
from world.actions import Attack, Move, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

pytestmark = pytest.mark.integration


def _alive(entity_id: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
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


def _bootstrap(*pairs: tuple[str, str]) -> WorldBootstrap:
    locations = (make_location("loc-1", name="Camp"),)
    return WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=tuple(_alive(body) for _, body in pairs),
        weather=weather_for_locations(locations),
        registrations=tuple(
            AgentRegistration(AgentId(agent), EntityId(body)) for agent, body in pairs
        ),
    )


def _runtime(
    agent_id: str,
    bootstrap: WorldBootstrap,
    *,
    loop: CognitiveLoop | None = None,
) -> AgentRuntime:
    owner = AgentId(agent_id)
    memories = MemoryStore(owner)
    beliefs = BeliefStore(owner)
    return AgentRuntime(
        agent=Agent(agent_id=owner, name=agent_id, goals=()),
        translator=registration_translator(bootstrap),
        cognitive_loop=loop or default_cognitive_loop(),
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )


class _FixedCommandPlanner:
    def __init__(self, command: object) -> None:
        self._command = command

    async def plan(
        self,
        loop_input: CognitiveLoopInput,
        intention: object,
        futures: object,
        memory: object | None = None,
    ) -> ActionPlan:
        _ = intention, futures, memory
        return ActionPlan(
            owner_id=loop_input.agent_id,
            command=self._command,  # type: ignore[arg-type]
            confidence=1.0,
        )


def _loop_with_command(command: object) -> CognitiveLoop:
    return CognitiveLoop(
        perception=LiteralPerceptionInterpreter(),
        memory=EmptyMemoryRetriever(),
        situation=DirectSituationModeler(),
        self_state=DirectSelfStateProjector(),
        goal_manager=PassthroughGoalManager(),
        emotional_state=PassthroughEmotionalStateAppraiser(),
        futures=PlaceholderFutureImagination(),
        motivation=StableMotivationEvaluator(),
        intention=StableIntentionSelector(),
        planner=_FixedCommandPlanner(command),
        memory_updates=EmptyMemoryUpdateHook(),
    )


@pytest.mark.asyncio
async def test_multi_agent_observe_process_resolve_in_registration_order(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from world.actions import require_agent_command

    bootstrap = _bootstrap(("agent-1", "body-1"), ("agent-2", "body-2"))
    engine = WorldEngine(config=SimulationRunConfig(seed=21), bootstrap=bootstrap)
    runtimes = {
        "agent-1": _runtime("agent-1", bootstrap),
        "agent-2": _runtime("agent-2", bootstrap),
    }
    for item in runtimes.values():
        item.start()

    caplog.set_level(logging.DEBUG, logger="simulation.agent_runtime")
    batch = engine.observe()
    submissions: list[ActionSubmission] = []
    for agent_key in ("agent-1", "agent-2"):
        observation = engine.observation_for(AgentId(agent_key))
        assert observation.observer_id.value.endswith(agent_key[-1])
        step = await runtimes[agent_key].process_observation(
            observation, token=batch.token
        )
        assert step.submission is not None
        # Production policies may Help/Talk/etc. when another body is visible;
        # admission still requires an exact closed AgentCommand.
        assert require_agent_command(step.submission.command) is step.submission.command
        submissions.append(step.submission)

    assert [item.agent_id.value for item in submissions] == ["agent-1", "agent-2"]
    tick_result = engine.resolve_tick(tuple(submissions))
    assert tick_result.tick.value == 0
    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "Observation(" not in joined
    assert "Camp" not in joined


@pytest.mark.asyncio
async def test_non_wait_command_and_stale_token_rejection() -> None:
    bootstrap = _bootstrap(("agent-1", "body-1"))
    engine = WorldEngine(config=SimulationRunConfig(seed=22), bootstrap=bootstrap)
    runtime = _runtime(
        "agent-1",
        bootstrap,
        loop=_loop_with_command(Move(destination_id=EntityId("loc-1"))),
    )
    runtime.start()
    batch = engine.observe()
    step = await runtime.process_observation(
        engine.observation_for(AgentId("agent-1")), token=batch.token
    )
    assert step.submission is not None
    assert type(step.submission.command) is Move
    engine.resolve_tick((step.submission,))

    engine.observe()
    stale = ActionSubmission(
        token=TickToken(value="stale-token", tick=Tick(0)),
        agent_id=AgentId("agent-1"),
        command=Wait(),
    )
    with pytest.raises(ValueError, match="token"):
        engine.resolve_tick((stale,))


@pytest.mark.asyncio
async def test_cross_agent_observation_rejected() -> None:
    bootstrap = _bootstrap(("agent-1", "body-1"), ("agent-2", "body-2"))
    engine = WorldEngine(config=SimulationRunConfig(seed=23), bootstrap=bootstrap)
    runtime = _runtime("agent-1", bootstrap)
    runtime.start()
    batch = engine.observe()
    foreign = engine.observation_for(AgentId("agent-2"))
    with pytest.raises(AgentRuntimeError) as exc_info:
        await runtime.process_observation(foreign, token=batch.token)
    assert exc_info.value.code is AgentRuntimeErrorCode.OWNERSHIP


@pytest.mark.asyncio
async def test_cognition_failure_yields_no_submission() -> None:
    class BoomPlanner:
        async def plan(self, loop_input, intention, futures, memory=None, goal_board=None):  # type: ignore[no-untyped-def]
            raise RuntimeError("secret planner boom")

    bootstrap = _bootstrap(("agent-1", "body-1"))
    engine = WorldEngine(config=SimulationRunConfig(seed=24), bootstrap=bootstrap)
    loop = CognitiveLoop(
        perception=LiteralPerceptionInterpreter(),
        memory=EmptyMemoryRetriever(),
        situation=DirectSituationModeler(),
        self_state=DirectSelfStateProjector(),
        goal_manager=PassthroughGoalManager(),
        emotional_state=PassthroughEmotionalStateAppraiser(),
        futures=PlaceholderFutureImagination(),
        motivation=StableMotivationEvaluator(),
        intention=StableIntentionSelector(),
        planner=BoomPlanner(),
        memory_updates=EmptyMemoryUpdateHook(),
    )
    runtime = _runtime("agent-1", bootstrap, loop=loop)
    runtime.start()
    batch = engine.observe()
    with pytest.raises(AgentRuntimeError) as exc_info:
        await runtime.process_observation(
            engine.observation_for(AgentId("agent-1")), token=batch.token
        )
    assert exc_info.value.code is AgentRuntimeErrorCode.COGNITION_FAILED
    assert "secret" not in str(exc_info.value)
    # Engine can still resolve empty submissions (autonomous progression).
    engine.resolve_tick(())


@pytest.mark.asyncio
async def test_death_at_n_becomes_terminal_at_n_plus_one() -> None:
    bootstrap = _bootstrap(("agent-1", "body-1"), ("agent-2", "body-2"))
    engine = WorldEngine(config=SimulationRunConfig(seed=25), bootstrap=bootstrap)
    attacker = _runtime(
        "agent-1",
        bootstrap,
        loop=_loop_with_command(Attack(target_id=EntityId("body-2"))),
    )
    victim = _runtime("agent-2", bootstrap)
    attacker.start()
    victim.start()

    victim_terminal = False
    for _ in range(40):
        batch = engine.observe()
        submissions: list[ActionSubmission] = []

        obs_attacker = engine.observation_for(AgentId("agent-1"))
        step_a = await attacker.process_observation(obs_attacker, token=batch.token)
        if step_a.submission is not None:
            submissions.append(step_a.submission)

        obs_victim = engine.observation_for(AgentId("agent-2"))
        step_v = await victim.process_observation(obs_victim, token=batch.token)
        if step_v.terminal:
            victim_terminal = True
            assert step_v.submission is None
            assert victim.status is AgentRuntimeStatus.TERMINAL
        elif step_v.submission is not None:
            submissions.append(step_v.submission)

        if victim_terminal and step_a.submission is None:
            break
        if submissions:
            engine.resolve_tick(tuple(submissions))
        else:
            break

    assert victim_terminal
    # All-terminal caller policy: omit terminal submissions; resolve remaining.
    batch = engine.observe()
    step_v = await victim.process_observation(
        engine.observation_for(AgentId("agent-2")), token=batch.token
    )
    assert step_v.submission is None
    step_a = await attacker.process_observation(
        engine.observation_for(AgentId("agent-1")), token=batch.token
    )
    if step_a.submission is not None:
        engine.resolve_tick((step_a.submission,))
    else:
        engine.resolve_tick(())
