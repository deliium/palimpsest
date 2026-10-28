"""Unit tests for stepped benchmark execution and terminal research export."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.civilization_benchmark_base import build_v3_benchmark_base
from experiments.civilization_benchmark_evidence import (
    BenchmarkBoundaryProbe,
    OwnerStoreSnapshot,
    blank_slate_check,
    evaluate_blank_slate,
)
from experiments.civilization_benchmark_execution import (
    CivilizationBenchmarkContext,
    CivilizationBenchmarkExecutionError,
    CivilizationBenchmarkRecipe,
    execute_civilization_benchmark,
    execute_stepped_benchmark_runner,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheckStatus,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkExecutionStatus,
    V3BenchmarkLane,
    V3BenchmarkProfile,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_01_BLANK_SLATE,
    V3_BENCH_29_FOUNDER_CONTINGENCY,
)
from experiments.coordinator import ExperimentAssignment
from experiments.generational_archive import GenerationalExecutionRecipe
from experiments.generational_execution import (
    PLAIN_RECIPE_ID,
    GenerationalExecutionContext,
)
from simulation.fork_checkpoint import (
    FinalizedResearchBoundary,
    ForkCheckpointError,
)
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    PopulationLifecycleSpec,
    RunnerAttemptReceipt,
    RunnerStopReasonCode,
)
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold


def _config(max_ticks: int = 3):
    base = build_v3_benchmark_base(
        seed=None,
        profile=V3BenchmarkProfile.SMOKE,
        scenario_id=V3_BENCH_01_BLANK_SLATE,
    )
    lifecycle = base.config.population_lifecycle
    assert isinstance(lifecycle, PopulationLifecycleSpec)
    short_lifecycle = replace(
        lifecycle,
        lifespan_ticks=6,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 1),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 2),
            LifecycleStageThreshold(LifecycleStageId("adult"), 5),
        ),
        demographic_policy_params={
            **dict(lifecycle.demographic_policy_params),
            "interval_ticks": 1,
            "generation_length_ticks": 1,
        },
        max_population=8,
    )
    return replace(
        base.config,
        population_lifecycle=short_lifecycle,
        stop_policy=replace(base.config.stop_policy, max_ticks=max_ticks),
    )


@pytest.mark.asyncio
async def test_stepped_and_normal_execution_have_equal_stop_parity() -> None:
    config = _config(max_ticks=3)
    async with await SimulationRunner.from_config(config) as normal_runner:
        normal = await normal_runner.run()
    async with await SimulationRunner.from_config(config) as stepped_runner:
        stepped = await execute_stepped_benchmark_runner(stepped_runner)
    assert stepped.result.stop_reason is normal.stop_reason
    assert stepped.result.stop_reason is RunnerStopReasonCode.MAX_TICKS
    assert stepped.result.ticks_committed == normal.ticks_committed == 3
    assert stepped.result.objective_state_hash == normal.objective_state_hash
    assert len(stepped.attempt_receipts) == len(normal.attempt_receipts)


@pytest.mark.asyncio
async def test_boundary_observer_sequence_includes_initialized_and_ticks() -> None:
    config = _config(max_ticks=2)
    labels: list[str] = []
    receipt_ticks: list[int] = []

    async def observer(
        runner: SimulationRunner, receipt: RunnerAttemptReceipt | None
    ) -> None:
        assert runner.ticks_committed >= 0
        if receipt is None:
            labels.append("initialized")
        else:
            labels.append(f"tick:{receipt.tick}")
            receipt_ticks.append(receipt.tick)

    async with await SimulationRunner.from_config(config) as runner:
        stepped = await execute_stepped_benchmark_runner(
            runner, boundary_observer=observer
        )
    assert labels[0] == "initialized"
    assert receipt_ticks == [0, 1]
    assert stepped.probe_failures == ()
    assert stepped.result.ticks_committed == 2


@pytest.mark.asyncio
async def test_observer_failure_is_isolated_from_scientific_execution() -> None:
    config = _config(max_ticks=2)
    calls: list[int] = []

    async def observer(
        runner: SimulationRunner, receipt: RunnerAttemptReceipt | None
    ) -> None:
        calls.append(1 if receipt is None else 0)
        raise RuntimeError("probe exploded")

    async with await SimulationRunner.from_config(config) as runner:
        stepped = await execute_stepped_benchmark_runner(
            runner, boundary_observer=observer
        )
    assert calls
    assert stepped.probe_failures == ("initialized", "tick:0", "tick:1")
    assert stepped.result.ticks_committed == 2
    assert stepped.result.stop_reason is RunnerStopReasonCode.MAX_TICKS


@pytest.mark.asyncio
async def test_terminal_research_export_is_available_and_detached() -> None:
    config = _config(max_ticks=2)
    async with await SimulationRunner.from_config(config) as runner:
        result = await runner.run()
        boundary = await runner.export_finalized_research_boundary()
    assert isinstance(boundary, FinalizedResearchBoundary)
    assert boundary.boundary_tick.value == result.ticks_committed == 2
    assert boundary.run_id == result.run_id
    assert boundary.config_fingerprint
    assert boundary.owners
    for owner in boundary.owners:
        assert owner.owner_id is not None
        assert owner.runtime_checkpoint is not None
        assert owner.runtime_checkpoint.agent_id == owner.owner_id
    assert boundary.population_progress is not None
    assert boundary.population_progress.boundary_tick == 2
    assert boundary.schema_version == "finalized-research-boundary-v1"


@pytest.mark.asyncio
async def test_terminal_fork_capture_remains_rejected() -> None:
    config = _config(max_ticks=1)
    async with await SimulationRunner.from_config(config) as runner:
        await runner.run()
        with pytest.raises(ForkCheckpointError) as excinfo:
            await runner.capture_fork_checkpoint()
    assert excinfo.value.code == "fork_terminal_boundary"


@pytest.mark.asyncio
async def test_research_export_requires_an_initialized_runner() -> None:
    config = _config(max_ticks=1)
    async with await SimulationRunner.from_config(config) as runner:
        with pytest.raises(ForkCheckpointError) as excinfo:
            await runner.export_finalized_research_boundary()
    assert excinfo.value.code == "fork_boundary_not_finalized"


@pytest.mark.asyncio
async def test_nonterminal_research_export_matches_finalized_boundary() -> None:
    config = _config(max_ticks=2)
    async with await SimulationRunner.from_config(config) as runner:
        await runner.initialize_finalized_boundary()
        boundary = await runner.export_finalized_research_boundary()
        assert boundary.boundary_tick.value == 0
        await runner.run_tick()
        later = await runner.export_finalized_research_boundary()
        assert later.boundary_tick.value == 1
        checkpoint = await runner.capture_fork_checkpoint()
        assert checkpoint.boundary_tick.value == 1
        assert checkpoint.config_fingerprint == later.config_fingerprint


@pytest.mark.asyncio
async def test_stepped_runner_rejects_non_runner_objects() -> None:
    with pytest.raises(CivilizationBenchmarkExecutionError):
        await execute_stepped_benchmark_runner(object())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_real_entrant_is_measured_before_first_cognition() -> None:
    config = _config(max_ticks=3)
    probe = BenchmarkBoundaryProbe()
    async with await SimulationRunner.from_config(config) as runner:
        await execute_stepped_benchmark_runner(runner, boundary_observer=probe)
    new_owners = probe.new_owners()
    assert new_owners
    assert any(owner.owner_id.startswith("entrant") for owner in new_owners)
    for owner in new_owners:
        assert owner.invocation_count == 0
        assert set(owner.unmeasured_stores) <= {
            "self_model",
            "cognition_trace",
            "skill_ledger",
            "taught_content_lineage",
            "experiment_ledger",
        }
    check = blank_slate_check(probe, boundary_end_tick=3)
    assert check.status is V3BenchmarkCheckStatus.PASS
    assert check.reason_code == "blank_slate_measured"
    assert check.denominator == len(new_owners)


def test_synthetic_nonzero_owner_fails_the_blank_slate_gate() -> None:
    counts = tuple(
        (name, 1 if name == "episodic_memory" else 0)
        for name in (
            "episodic_memory",
            "semantic_beliefs",
            "relationships",
        )
    )
    poisoned = OwnerStoreSnapshot(
        owner_id="agent-poisoned",
        entity_id="body-poisoned",
        generation_index=1,
        living=True,
        invocation_count=0,
        counts=counts,
        measured_stores=("episodic_memory", "semantic_beliefs", "relationships"),
        unmeasured_stores=(),
    )
    check = evaluate_blank_slate((poisoned,), boundary_end_tick=4)
    assert check.status is V3BenchmarkCheckStatus.FAIL
    assert check.reason_code == "subjective_copy_forbidden"
    assert check.numerator == 0
    assert check.denominator == 1


def _assignment(config, run_id: str = "run-benchmark-dispatch") -> ExperimentAssignment:
    return ExperimentAssignment(
        experiment_id="v3-benchmark-test",
        condition_id="v3-bench-01-blank-slate",
        condition_ordinal=0,
        seed=config.seed,
        seed_ordinal=0,
        replicate_index=0,
        run_id=RunId(run_id),
        runner_config=config,
    )


def _execution_context(tmp_path) -> GenerationalExecutionContext:
    return GenerationalExecutionContext(
        artifact_root=tmp_path,
        source_identity={
            "code_revision": "deadbeef",
            "source_clean": True,
        },
        recipe=GenerationalExecutionRecipe(
            recipe_id=PLAIN_RECIPE_ID, version="1", params={}
        ),
        factories=RunnerDependencyFactories(),
        attempt_id="attempt-1",
    )


@pytest.mark.asyncio
async def test_independent_dispatch_reports_honest_partial_evidence(tmp_path) -> None:
    config = _config(max_ticks=2)
    probe = BenchmarkBoundaryProbe()
    recipe = CivilizationBenchmarkRecipe(
        scenario_id=V3_BENCH_01_BLANK_SLATE,
        lane=V3BenchmarkLane.RESEARCH,
        profile=V3BenchmarkProfile.SMOKE,
        seed=23,
        arm_id="observation",
    )
    context = CivilizationBenchmarkContext(
        assignment=_assignment(config),
        execution_context=_execution_context(tmp_path),
        probe=probe,
    )
    result = await execute_civilization_benchmark(recipe, context)
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    assert result.ticks_committed == 2
    assert result.declared_horizon == 2
    assert result.coverage.value == "exercised"
    # Unimplemented selector evaluators keep evidence honest and partial.
    assert result.evidence is V3BenchmarkEvidenceAvailability.PARTIAL
    assert result.phenomenon.value == "unknown"
    statuses = {check.selector_id: check.status for check in result.checks}
    assert statuses["new_agent_initialization_evidence"] is (
        V3BenchmarkCheckStatus.PASS
    )
    assert statuses["population_lifecycle_evidence"] is (
        V3BenchmarkCheckStatus.UNEXECUTED
    )


@pytest.mark.asyncio
async def test_grouped_case_fails_closed_without_grouped_executor() -> None:
    recipe = CivilizationBenchmarkRecipe(
        scenario_id=V3_BENCH_29_FOUNDER_CONTINGENCY,
        lane=V3BenchmarkLane.RESEARCH,
        profile=V3BenchmarkProfile.SMOKE,
        seed=23,
        arm_id="fork-child",
        command_plan_id="bn-smoke",
        command_plan_version="1",
    )
    with pytest.raises(CivilizationBenchmarkExecutionError) as excinfo:
        await execute_civilization_benchmark(recipe, CivilizationBenchmarkContext())
    assert excinfo.value.code == "grouped_executor_required"


def test_independent_recipe_rejects_a_command_plan() -> None:
    from experiments.civilization_benchmark_models import V3BenchmarkError

    with pytest.raises(V3BenchmarkError) as excinfo:
        CivilizationBenchmarkRecipe(
            scenario_id=V3_BENCH_01_BLANK_SLATE,
            lane=V3BenchmarkLane.RESEARCH,
            profile=V3BenchmarkProfile.SMOKE,
            seed=23,
            arm_id="observation",
            command_plan_id="planned",
            command_plan_version="1",
        )
    assert excinfo.value.code == "recipe_descriptor_mismatch"


def test_grouped_recipe_requires_a_command_plan() -> None:
    from experiments.civilization_benchmark_models import V3BenchmarkError

    with pytest.raises(V3BenchmarkError) as excinfo:
        CivilizationBenchmarkRecipe(
            scenario_id=V3_BENCH_29_FOUNDER_CONTINGENCY,
            lane=V3BenchmarkLane.RESEARCH,
            profile=V3BenchmarkProfile.SMOKE,
            seed=23,
            arm_id="fork-child",
        )
    assert excinfo.value.code == "recipe_descriptor_mismatch"
