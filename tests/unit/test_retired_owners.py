"""Retired-owner freeze, graph release and read-only export parity."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest

from agents.cognition.budget import (
    BudgetDimension,
    CognitiveBudgetPolicy,
    TickBudgetLedger,
)
from agents.models import AgentId
from simulation.agent_runtime import AgentRuntimeStatus
from simulation.branch_service import rematerialize_snapshot
from simulation.engine import WorldEngine
from simulation.fork_checkpoint import AUDIT_FIELD_NAMES
from simulation.models import RunId
from simulation.persistence import SnapshotId
from simulation.retired_owners import (
    ReadOnlyMemoryService,
    RetiredOwnerBundle,
    RetiredOwnerError,
    RuntimeRetentionPolicy,
)
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    RunnerPersistenceSpec,
    RunnerStopPolicy,
)
from tests.benchmarks.v3_workloads import V3ScaleLane, build_workload
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold


def _active_config(*, ticks: int) -> tuple[Any, Any]:
    workload = build_workload(V3ScaleLane.GENERATIONAL, ticks=ticks)
    config = replace(
        workload.config, persistence=RunnerPersistenceSpec(durable=False)
    )
    lifecycle = config.population_lifecycle
    assert lifecycle is not None
    params = dict(lifecycle.demographic_policy_params)
    params.update(
        {
            "interval_ticks": 2,
            "entries_per_interval": 1,
            "generation_length_ticks": 2,
        }
    )
    lifecycle = replace(
        lifecycle,
        lifespan_ticks=4,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 1),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 2),
            LifecycleStageThreshold(LifecycleStageId("adult"), 3),
        ),
        demographic_policy_params=params,
        max_population=6,
    )
    generational = config.generational_run
    assert generational is not None
    return workload, replace(
        config,
        population_lifecycle=lifecycle,
        generational_run=replace(
            generational, max_generation_index=None, stop_on_extinction=False
        ),
        stop_policy=RunnerStopPolicy(
            max_ticks=ticks, stop_on_all_agents_terminal=False
        ),
    )


def test_retention_policy_is_composition_only_and_survives_clones() -> None:
    policy = RuntimeRetentionPolicy(retire_dead_owners=True)
    factories = RunnerDependencyFactories(retention_policy=policy)
    assert factories.retention_policy is policy
    assert (
        factories.with_generational_control(
            boundary_observer=None, recording_usage_sink=None
        ).retention_policy
        is policy
    )
    assert factories.with_criterion_factory(None).retention_policy is policy
    with pytest.raises(TypeError):
        RunnerDependencyFactories(
            retention_policy=True  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_retired_owner_freezes_exports_and_releases_graph() -> None:
    workload, config = _active_config(ticks=14)
    policy = RuntimeRetentionPolicy(retire_dead_owners=True)
    factories = RunnerDependencyFactories(retention_policy=policy)
    captured: list[tuple[object, object, object]] = []
    original_freeze = SimulationRunner._freeze_retired_owner

    async def capture_then_freeze(self: SimulationRunner, ordinal: int) -> None:
        runtime = self._runtimes[ordinal]
        bundle = self._agents[ordinal]
        captured.append((runtime._loop, bundle.bundle, bundle.memory_service))
        await original_freeze(self, ordinal)

    SimulationRunner._freeze_retired_owner = capture_then_freeze  # type: ignore[method-assign]
    runner = await SimulationRunner.from_config(
        config, run_id=workload.run_id, factories=factories
    )
    try:
        for _ in range(14):
            await runner.run_tick()
            if runner.retired_owner_count:
                break
        assert runner.retired_owner_count > 0
        assert runner.retirement_unsupported_count == 0
        ordinal = next(
            index
            for index, runtime in enumerate(runner.runtimes)
            if runtime.retired_record is not None
        )
        runtime = runner.runtimes[ordinal]
        bundle = runner._agents[ordinal]
        record = runtime.retired_record
        assert record is not None
        assert runtime.status is AgentRuntimeStatus.TERMINAL
        assert runtime._loop is None
        assert runtime._memory_service is None
        assert isinstance(bundle.memory_service, ReadOnlyMemoryService)
        assert isinstance(bundle.bundle, RetiredOwnerBundle)
        assert all(
            captured_loop is not runtime._loop
            for captured_loop, _, _ in captured
        )
        assert bundle.bundle is not captured[0][1]
        assert bundle.memory_service is not captured[0][2]
        assert runtime.export_runtime_checkpoint() is record.runtime_checkpoint
        assert runtime.export_fork_state() is record.runtime_fork_state
        assert {name for name, _ in record.audits} == set(AUDIT_FIELD_NAMES)
        cultural = runtime.export_cultural_owner_state(
            generation_index=0, living=False
        )
        assert all(
            channel.enabled == (channel.channel in record.cultural_channels)
            for channel in cultural.channels
        )
        civilization = runtime.export_civilization_owner_state(
            generation_index=0, living=False
        )
        assert civilization.owner_id == runtime.agent_id.value
        snapshot = await bundle.bundle.snapshot()
        active = tuple(
            trace
            for trace in record.subjective_state.memory.traces
            if trace.forgotten_at_tick is None
        )
        assert snapshot.memories == active
        assert tuple(await bundle.memory_service.snapshot()) == active
        with pytest.raises(RetiredOwnerError):
            await bundle.memory_service.apply(object())
        checkpoint = await runner.capture_fork_checkpoint()
        assert checkpoint.owner_state(record.agent_id) == record.subjective_state
        runtime.freeze_terminal(record)
        assert runtime.retired_record is record
    finally:
        SimulationRunner._freeze_retired_owner = original_freeze  # type: ignore[method-assign]
        await runner.aclose()


class _UnsupportedBundle:
    """Delegating bundle that deliberately hides fork-capable methods."""

    def __init__(self, inner: object) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> object:
        if name in {"export_fork_state", "restore_fork_state"}:
            raise AttributeError(name)
        return getattr(self._inner, name)


@pytest.mark.asyncio
async def test_unsupported_owner_bundle_keeps_live_graph() -> None:
    workload, config = _active_config(ticks=10)
    base = RunnerDependencyFactories()

    def bundle_factory(scope: object, **kwargs: object) -> object:
        inner = base.create_subjective_bundle(scope, **kwargs)  # type: ignore[arg-type]
        return _UnsupportedBundle(inner)

    factories = RunnerDependencyFactories(
        bundle_factory=cast(Any, bundle_factory),
        retention_policy=RuntimeRetentionPolicy(retire_dead_owners=True),
    )
    runner = await SimulationRunner.from_config(
        config, run_id=workload.run_id, factories=factories
    )
    try:
        for _ in range(10):
            await runner.run_tick()
        assert runner.retirement_unsupported_count > 0
        assert runner.retired_owner_count == 0
        for runtime in runner.runtimes:
            if runtime.status is AgentRuntimeStatus.TERMINAL:
                assert runtime.retired_record is None
                assert runtime._loop is not None
                break
        else:
            raise AssertionError("expected a terminal owner")
    finally:
        await runner.aclose()


def test_budget_fork_state_is_detached_and_clock_free() -> None:
    calls = 0

    def clock() -> float:
        nonlocal calls
        calls += 1
        return 12.0

    policy = CognitiveBudgetPolicy(
        max_llm_calls_per_tick=2,
        max_tokens_per_tick=10,
        timeout_seconds=5.0,
        clock=clock,
    )
    ledger = TickBudgetLedger(owner_id=AgentId("agent-1"), tick=3, policy=policy)
    assert calls == 1
    ledger._used[BudgetDimension.LLM] = 1
    ledger._warned.add(BudgetDimension.LLM)
    state = ledger.export_fork_state()
    assert calls == 1
    restored = TickBudgetLedger.from_fork_state(state, policy=policy)
    assert calls == 1
    restored._used[BudgetDimension.LLM] = 2
    assert ledger._used[BudgetDimension.LLM] == 1
    restored._warned.add(BudgetDimension.TOKENS)
    assert ledger._warned == {BudgetDimension.LLM}
    other = CognitiveBudgetPolicy(
        max_llm_calls_per_tick=3,
        max_tokens_per_tick=10,
        timeout_seconds=5.0,
    )
    with pytest.raises(ValueError):
        TickBudgetLedger.from_fork_state(state, policy=other)


@pytest.mark.asyncio
async def test_metadata_only_recovery_does_not_fabricate_retired_record() -> None:
    workload, config = _active_config(ticks=14)
    factories = RunnerDependencyFactories(
        retention_policy=RuntimeRetentionPolicy(retire_dead_owners=True)
    )
    parent = await SimulationRunner.from_config(
        config, run_id=workload.run_id, factories=factories
    )
    try:
        for _ in range(14):
            await parent.run_tick()
            if parent.retired_owner_count:
                break
        checkpoint = parent.export_runtime_checkpoint()
    finally:
        await parent.aclose()
    restored = await SimulationRunner.from_config(
        config, run_id=workload.run_id
    )
    try:
        restored.apply_runtime_checkpoint(checkpoint)
        terminal = [
            runtime
            for runtime in restored.runtimes
            if runtime.status is AgentRuntimeStatus.TERMINAL
        ]
        assert terminal
        assert all(runtime.retired_record is None for runtime in terminal)
        assert all(runtime._loop is not None for runtime in terminal)
        assert restored.active_ordinals == ()
    finally:
        await restored.aclose()


@pytest.mark.asyncio
async def test_fork_capture_restore_preserves_retired_owner_state() -> None:
    workload, config = _active_config(ticks=14)
    factories = RunnerDependencyFactories(
        retention_policy=RuntimeRetentionPolicy(retire_dead_owners=True)
    )
    parent = await SimulationRunner.from_config(
        config, run_id=workload.run_id, factories=factories
    )
    try:
        for _ in range(14):
            await parent.run_tick()
            if parent.retired_owner_count:
                break
        checkpoint = await parent.capture_fork_checkpoint()
        retired = next(
            runtime
            for runtime in parent.runtimes
            if runtime.retired_record is not None
        )
        parent_owner = checkpoint.owner_state(retired.agent_id)
        child_run = RunId("retired-fork-child")
        child_snapshot = rematerialize_snapshot(
            checkpoint.snapshot,
            child_run_id=child_run,
            snapshot_id=SnapshotId("retired-fork-snapshot"),
            predecessor_commit_hash=None,
            next_tick=checkpoint.boundary_tick,
        )
        child_engine = WorldEngine.restore_from_snapshot(
            child_snapshot,
            population_lifecycle=config.population_lifecycle,
            new_agent_initialization=config.new_agent_initialization,
            kinship_spec=config.kinship,
            environmental_dynamics=config.environmental_dynamics,
            artifacts_enabled=config.artifacts_enabled,
        )
        child = await SimulationRunner.from_fork_checkpoint(
            config,
            run_id=child_run,
            checkpoint=checkpoint,
            restored_engine=child_engine,
        )
        try:
            restored = await child.capture_fork_checkpoint()
            child_owner = restored.owner_state(retired.agent_id)
            assert child_owner.memory.traces == parent_owner.memory.traces
            assert child_owner.belief.beliefs == parent_owner.belief.beliefs
            assert (
                child_owner.relationship.profiles
                == parent_owner.relationship.profiles
            )
            assert child_owner.commit.revision == parent_owner.commit.revision
        finally:
            await child.aclose()
    finally:
        await parent.aclose()


__all__: tuple[str, ...] = ()
