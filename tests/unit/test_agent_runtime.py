"""AgentRuntime lifecycle and memory-update tests."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.defaults import default_cognitive_loop
from agents.cognition.models import (
    MemoryUpdateIntent,
    MemoryUpdateKind,
)
from agents.models import Agent, AgentId
from memory.models import (
    Belief,
    BeliefId,
    BeliefStore,
    MemoryId,
    MemoryStore,
    MemoryTrace,
)
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
from simulation.lifecycle import ActionSubmission, TickToken
from tests.simulation_helpers import make_location, weather_for_locations
from world.actions import Wait
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


def _body(entity_id: str, *, dead: bool = False) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId("loc-1"),
        health=Health(0 if dead else 100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.DEAD if dead else LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _bootstrap() -> WorldBootstrap:
    locations = (make_location("loc-1", name="Camp"),)
    return WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(_body("body-1"), _body("body-2")),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )


def _agent(agent_id: str = "agent-1") -> Agent:
    return Agent(agent_id=AgentId(agent_id), name=agent_id, goals=())


def _self(*, dead: bool = False, tick: int = 0) -> Observation:
    body = _body("body-1", dead=dead)
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


def _runtime() -> tuple[AgentRuntime, MemoryStore, BeliefStore]:
    bootstrap = _bootstrap()
    memories = MemoryStore(AgentId("agent-1"))
    beliefs = BeliefStore(AgentId("agent-1"))
    runtime = AgentRuntime(
        agent=_agent(),
        translator=registration_translator(bootstrap),
        cognitive_loop=default_cognitive_loop(),
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )
    return runtime, memories, beliefs


@pytest.mark.asyncio
async def test_lifecycle_start_process_and_submission(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runtime, _, _ = _runtime()
    assert runtime.status.value == AgentRuntimeStatus.CREATED.value
    with pytest.raises(AgentRuntimeError) as not_started:
        await runtime.process_observation(_self(), token=_token())
    assert not_started.value.code is AgentRuntimeErrorCode.NOT_STARTED

    caplog.set_level(logging.INFO, logger="simulation.agent_runtime")
    runtime.start()
    assert runtime.status.value == AgentRuntimeStatus.ACTIVE.value
    with pytest.raises(AgentRuntimeError) as again:
        runtime.start()
    assert again.value.code is AgentRuntimeErrorCode.ALREADY_STARTED

    result = await runtime.process_observation(_self(tick=0), token=_token(0))
    assert result.submission is not None
    assert type(result.submission) is ActionSubmission
    assert result.submission.agent_id == AgentId("agent-1")
    assert type(result.submission.command) is Wait
    assert result.submission.token == _token(0)
    assert result.loop_result is not None
    assert result.terminal is False
    assert "runtime_started" in " ".join(r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_rejects_cross_agent_observation() -> None:
    runtime, _, _ = _runtime()
    runtime.start()
    foreign = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-2"),
        revision=WorldRevision(0),
        tick=0,
    )
    with pytest.raises(AgentRuntimeError) as exc_info:
        await runtime.process_observation(foreign, token=_token())
    assert exc_info.value.code is AgentRuntimeErrorCode.OWNERSHIP


@pytest.mark.asyncio
async def test_duplicate_observation_rejected() -> None:
    runtime, _, _ = _runtime()
    runtime.start()
    obs = _self(tick=1)
    await runtime.process_observation(obs, token=_token(1))
    with pytest.raises(AgentRuntimeError) as exc_info:
        await runtime.process_observation(obs, token=_token(1))
    assert exc_info.value.code is AgentRuntimeErrorCode.DUPLICATE_OBSERVATION


@pytest.mark.asyncio
async def test_dead_self_becomes_terminal_without_submission(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runtime, _, _ = _runtime()
    runtime.start()
    caplog.set_level(logging.INFO, logger="simulation.agent_runtime")
    result = await runtime.process_observation(
        _self(dead=True, tick=2), token=_token(2)
    )
    assert result.terminal is True
    assert result.submission is None
    assert result.loop_result is None
    assert runtime.status is AgentRuntimeStatus.TERMINAL
    skipped = await runtime.process_observation(_self(tick=3), token=_token(3))
    assert skipped.terminal is True
    assert skipped.submission is None
    assert "runtime_terminal" in " ".join(r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_cognition_failure_does_not_mutate_memory() -> None:
    from agents.cognition.defaults import (
        DirectSelfStateProjector,
        DirectSituationModeler,
        EmptyMemoryRetriever,
        EmptyMemoryUpdateHook,
        LiteralPerceptionInterpreter,
        PlaceholderFutureImagination,
        StableIntentionSelector,
        StableMotivationEvaluator,
        WaitFallbackPlanner,
    )
    from agents.cognition.loop import CognitiveLoop

    class BoomMotivation(StableMotivationEvaluator):
        async def evaluate(self, loop_input, situation, self_state, futures):  # type: ignore[no-untyped-def]
            raise RuntimeError("secret motivation")

    bootstrap = _bootstrap()
    memories = MemoryStore(AgentId("agent-1"))
    beliefs = BeliefStore(AgentId("agent-1"))
    runtime = AgentRuntime(
        agent=_agent(),
        translator=registration_translator(bootstrap),
        cognitive_loop=CognitiveLoop(
            perception=LiteralPerceptionInterpreter(),
            memory=EmptyMemoryRetriever(),
            situation=DirectSituationModeler(),
            self_state=DirectSelfStateProjector(),
            futures=PlaceholderFutureImagination(),
            motivation=BoomMotivation(),
            intention=StableIntentionSelector(),
            planner=WaitFallbackPlanner(),
            memory_updates=EmptyMemoryUpdateHook(),
        ),
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )
    runtime.start()
    with pytest.raises(AgentRuntimeError) as exc_info:
        await runtime.process_observation(_self(tick=0), token=_token(0))
    assert exc_info.value.code is AgentRuntimeErrorCode.COGNITION_FAILED
    assert memories.snapshot() == ()
    assert beliefs.snapshot() == ()
    assert "secret" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_memory_updates_apply_after_success() -> None:
    from agents.cognition.defaults import (
        DirectSelfStateProjector,
        DirectSituationModeler,
        EmptyMemoryRetriever,
        LiteralPerceptionInterpreter,
        PlaceholderFutureImagination,
        StableIntentionSelector,
        StableMotivationEvaluator,
        WaitFallbackPlanner,
    )
    from agents.cognition.loop import CognitiveLoop
    from agents.cognition.models import (
        ActionPlan,
        CognitiveLoopInput,
        InterpretedPerception,
        RetrievedMemoryContext,
        SelectedIntention,
    )

    class WriteHook:
        async def propose_updates(
            self,
            loop_input: CognitiveLoopInput,
            plan: ActionPlan,
            perception: InterpretedPerception,
            memory: RetrievedMemoryContext,
            intention: SelectedIntention,
        ) -> tuple[MemoryUpdateIntent, ...]:
            _ = plan, perception, memory, intention
            return (
                MemoryUpdateIntent(
                    owner_id=loop_input.agent_id,
                    kind=MemoryUpdateKind.WRITE_MEMORY,
                    memory=MemoryTrace(
                        memory_id=MemoryId("mem-1"),
                        owner_id=loop_input.agent_id,
                        world_revision=WorldRevision(0),
                        content={"kind": "note"},
                    ),
                ),
                MemoryUpdateIntent(
                    owner_id=loop_input.agent_id,
                    kind=MemoryUpdateKind.WRITE_BELIEF,
                    belief=Belief(
                        belief_id=BeliefId("bel-1"),
                        owner_id=loop_input.agent_id,
                        proposition="camp is quiet",
                        confidence=0.5,
                        evidence_memory_ids=(MemoryId("mem-1"),),
                    ),
                ),
            )

    bootstrap = _bootstrap()
    memories = MemoryStore(AgentId("agent-1"))
    beliefs = BeliefStore(AgentId("agent-1"))
    runtime = AgentRuntime(
        agent=_agent(),
        translator=registration_translator(bootstrap),
        cognitive_loop=CognitiveLoop(
            perception=LiteralPerceptionInterpreter(),
            memory=EmptyMemoryRetriever(),
            situation=DirectSituationModeler(),
            self_state=DirectSelfStateProjector(),
            futures=PlaceholderFutureImagination(),
            motivation=StableMotivationEvaluator(),
            intention=StableIntentionSelector(),
            planner=WaitFallbackPlanner(),
            memory_updates=WriteHook(),
        ),
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
    )
    runtime.start()
    result = await runtime.process_observation(_self(tick=5), token=_token(5))
    assert result.submission is not None
    assert len(memories.snapshot()) == 1
    assert len(beliefs.snapshot()) == 1
    assert "camp is quiet" not in repr(result)
    assert "note" not in repr(result)


@pytest.mark.asyncio
async def test_logs_omit_payloads(caplog: pytest.LogCaptureFixture) -> None:
    runtime, _, _ = _runtime()
    runtime.start()
    caplog.set_level(logging.DEBUG, logger="simulation.agent_runtime")
    await runtime.process_observation(_self(tick=0), token=_token(0))
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "Observation(" not in messages
    assert "Camp" not in messages
    assert "Wait(" not in messages
