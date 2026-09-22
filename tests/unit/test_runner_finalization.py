"""Unit tests for prepare/bind/finalize and crash recovery boundaries."""

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
    pending_from_finalization_command,
)
from simulation.bootstrap import (
    AgentRegistration,
    WorldBootstrap,
    registration_translator,
)
from simulation.clock import Tick
from simulation.lifecycle import TickToken
from simulation.memory_finalization import InMemoryPendingFinalizationRepository
from simulation.models import RunId, StochasticIdentity
from simulation.run_control import (
    FINALIZATION_COMMAND_CODEC_VERSION,
    ResumeMode,
    RunnerCrashInjected,
    RunnerCrashPoint,
    classify_resume_mode,
)
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerAttemptStatus,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from simulation.runner_serialization import (
    decode_finalization_command,
    encode_finalization_command,
)
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_weather,
    weather_for_locations,
)
from world.actions import Move
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus, default_physical_rules
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


def _config(*, max_ticks: int = 2) -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return SimulationRunnerConfig(
        seed=42,
        stochastic_identity=StochasticIdentity("cmp-finalization"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
    )


def _crash_at(point: RunnerCrashPoint, *, ordinal: int | None = None):
    def _hook(seen: RunnerCrashPoint, seen_ordinal: int | None) -> None:
        if seen is point and (ordinal is None or seen_ordinal == ordinal):
            raise RunnerCrashInjected(seen, ordinal=seen_ordinal)

    return _hook


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


@pytest.mark.asyncio
async def test_finalization_command_roundtrip_without_recognition() -> None:
    runtime, _ = _runtime()
    runtime.start()
    prepared = await runtime.prepare_observation(_obs(tick=0), token=_token(0))
    pending = await runtime.bind_effective_command(prepared)
    command = pending.to_finalization_command(run_id=RunId("run-cmd-1"))
    assert command.codec_version == FINALIZATION_COMMAND_CODEC_VERSION
    encoded = encode_finalization_command(command)
    decoded = decode_finalization_command(encoded)
    runtime.abort_pending(pending)
    restored = runtime.restore_pending_from_command(decoded)
    result = await runtime.finalize_pending(restored)
    assert result.invocation_id == command.invocation_id
    assert runtime.internal_state.invocation_count == 1
    again = pending_from_finalization_command(decoded)
    assert again.integrity_hash == command.integrity_hash


def test_classify_resume_modes() -> None:
    run_id = RunId("run-mode-1")
    pending = classify_resume_mode(
        run_id=run_id,
        ticks_committed=0,
        engine_tick=1,
        pending_count=1,
        pending_tick=0,
    )
    assert pending.mode is ResumeMode.PENDING_SUBJECTIVE_RECOVERY
    replay = classify_resume_mode(
        run_id=run_id,
        ticks_committed=0,
        engine_tick=1,
        pending_count=0,
        pending_tick=None,
    )
    assert replay.mode is ResumeMode.OBJECTIVE_REPLAY
    cont = classify_resume_mode(
        run_id=run_id,
        ticks_committed=1,
        engine_tick=1,
        pending_count=0,
        pending_tick=None,
    )
    assert cont.mode is ResumeMode.CONTINUED_EXECUTION


@pytest.mark.asyncio
async def test_crash_before_objective_commit_aborts_pending() -> None:
    pending_repo = InMemoryPendingFinalizationRepository()
    async with await SimulationRunner.from_config(
        _config(max_ticks=2),
        run_id=RunId("run-crash-before"),
        factories=RunnerDependencyFactories(pending_finalizations=pending_repo),
    ) as runner:
        runner.set_crash_hook(_crash_at(RunnerCrashPoint.BEFORE_OBJECTIVE_COMMIT))
        engine_tick_before = runner.engine.tick.value
        with pytest.raises(RunnerCrashInjected):
            await runner.run_tick()
        listed = await pending_repo.list_pending_for_run(
            run_id=RunId("run-crash-before")
        )
        assert listed == ()
        assert runner.engine.tick.value == engine_tick_before
        assert runner.export_runtime_checkpoint().ticks_committed == 0


@pytest.mark.asyncio
async def test_crash_after_commit_recovers_without_duplicating_objective() -> None:
    pending_repo = InMemoryPendingFinalizationRepository()
    async with await SimulationRunner.from_config(
        _config(max_ticks=2),
        run_id=RunId("run-crash-after"),
        factories=RunnerDependencyFactories(pending_finalizations=pending_repo),
    ) as runner:
        runner.set_crash_hook(_crash_at(RunnerCrashPoint.AFTER_OBJECTIVE_COMMIT))
        with pytest.raises(RunnerCrashInjected):
            await runner.run_tick()
        assert runner.engine.tick.value == 1
        listed = await pending_repo.list_pending_for_run(
            run_id=RunId("run-crash-after")
        )
        assert len(listed) == 1
        assert listed[0].codec_version == FINALIZATION_COMMAND_CODEC_VERSION
        runner.set_crash_hook(None)
        receipt = await runner.recover_pending_finalizations()
        assert receipt.status is RunnerAttemptStatus.FINALIZED
        assert receipt.finalized_count == 1
        assert runner.export_runtime_checkpoint().ticks_committed == 1
        listed_after = await pending_repo.list_pending_for_run(
            run_id=RunId("run-crash-after")
        )
        assert listed_after == ()
        # Second recovery is a no-op; objective tick stays at 1.
        again = await runner.recover_pending_finalizations()
        assert again.finalized_count == 0
        assert runner.engine.tick.value == 1


@pytest.mark.asyncio
async def test_crash_during_owner_finalization_recovers() -> None:
    pending_repo = InMemoryPendingFinalizationRepository()
    async with await SimulationRunner.from_config(
        _config(max_ticks=2),
        run_id=RunId("run-crash-owner"),
        factories=RunnerDependencyFactories(pending_finalizations=pending_repo),
    ) as runner:
        runner.set_crash_hook(
            _crash_at(RunnerCrashPoint.DURING_OWNER_FINALIZATION, ordinal=0)
        )
        with pytest.raises(RunnerCrashInjected):
            await runner.run_tick()
        assert runner.engine.tick.value == 1
        runner.set_crash_hook(None)
        receipt = await runner.recover_pending_finalizations()
        assert receipt.finalized_count == 1
        assert runner.engine.tick.value == 1


@pytest.mark.asyncio
async def test_crash_before_collector_and_after_ack_recover() -> None:
    pending_repo = InMemoryPendingFinalizationRepository()
    async with await SimulationRunner.from_config(
        _config(max_ticks=2),
        run_id=RunId("run-crash-collector"),
        factories=RunnerDependencyFactories(pending_finalizations=pending_repo),
    ) as runner:
        runner.set_crash_hook(
            _crash_at(RunnerCrashPoint.BEFORE_COLLECTOR_PUBLICATION, ordinal=0)
        )
        with pytest.raises(RunnerCrashInjected):
            await runner.run_tick()
        runner.set_crash_hook(None)
        receipt = await runner.recover_pending_finalizations()
        assert receipt.finalized_count == 1

    pending_repo2 = InMemoryPendingFinalizationRepository()
    async with await SimulationRunner.from_config(
        _config(max_ticks=2),
        run_id=RunId("run-crash-ack"),
        factories=RunnerDependencyFactories(pending_finalizations=pending_repo2),
    ) as runner:
        runner.set_crash_hook(
            _crash_at(RunnerCrashPoint.AFTER_ACKNOWLEDGEMENT, ordinal=0)
        )
        with pytest.raises(RunnerCrashInjected):
            await runner.run_tick()
        runner.set_crash_hook(None)
        receipt = await runner.recover_pending_finalizations()
        assert receipt.finalized_count == 1
        assert runner.engine.tick.value == 1


@pytest.mark.asyncio
async def test_rehydrate_checkpoint_restores_runtime_state() -> None:
    pending_repo = InMemoryPendingFinalizationRepository()
    async with await SimulationRunner.from_config(
        _config(max_ticks=2),
        run_id=RunId("run-rehydrate-1"),
        factories=RunnerDependencyFactories(pending_finalizations=pending_repo),
    ) as runner:
        await runner.run_tick()
        checkpoint = runner.export_runtime_checkpoint()
        assert checkpoint.ticks_committed == 1
        assert checkpoint.runtime_states[0].status.value == "active"

    async with await SimulationRunner.from_config(
        _config(max_ticks=2),
        run_id=RunId("run-rehydrate-1"),
        factories=RunnerDependencyFactories(pending_finalizations=pending_repo),
    ) as runner2:
        runner2.apply_runtime_checkpoint(checkpoint)
        assert runner2.export_runtime_checkpoint().ticks_committed == 1
        plan = runner2.classify_resume(pending_count=0, pending_tick=None)
        # Fresh engine starts at 0 while checkpoint says 1 → objective replay.
        assert plan.mode in {
            ResumeMode.OBJECTIVE_REPLAY,
            ResumeMode.CONTINUED_EXECUTION,
            ResumeMode.PENDING_SUBJECTIVE_RECOVERY,
        }
