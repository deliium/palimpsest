"""Unit tests for benchmark memory-layer and durable-record cases."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from experiments.civilization_benchmark_evidence import (
    BenchmarkBoundaryProbe,
    evaluate_durable_records,
)
from experiments.civilization_benchmark_execution import (
    CivilizationBenchmarkContext,
    CivilizationBenchmarkRecipe,
    execute_civilization_benchmark,
)
from experiments.civilization_benchmark_memory import (
    MEMORY_BENCHMARK_IDS,
    build_memory_benchmark,
    memory_benchmark_arbiter,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheckStatus,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkExecutionStatus,
    V3BenchmarkLane,
    V3BenchmarkProfile,
    V3BenchmarkRunResult,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_05_MEMORY_LAYERS,
    V3_BENCH_06_RECORD_AFTER_WITNESSES,
    V3_BENCH_07_FALSE_RECORD,
)
from experiments.coordinator import ExperimentAssignment
from experiments.generational_archive import GenerationalExecutionRecipe
from experiments.generational_execution import (
    PLAIN_RECIPE_ID,
    GenerationalExecutionContext,
)
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories
from simulation.runner_models import PopulationLifecycleSpec, SimulationRunnerConfig
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold


def _short_config(
    config: SimulationRunnerConfig, *, max_ticks: int, lifespan: int = 6
) -> SimulationRunnerConfig:
    lifecycle = config.population_lifecycle
    assert isinstance(lifecycle, PopulationLifecycleSpec)
    short = replace(
        lifecycle,
        lifespan_ticks=lifespan,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 1),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 2),
            LifecycleStageThreshold(
                LifecycleStageId("adult"), max(3, lifespan - 1)
            ),
        ),
        demographic_policy_params={
            **dict(lifecycle.demographic_policy_params),
            "interval_ticks": 1,
            "generation_length_ticks": 1,
        },
        max_population=8,
    )
    return replace(
        config,
        population_lifecycle=short,
        stop_policy=replace(config.stop_policy, max_ticks=max_ticks),
    )


def _context(
    tmp_path: Path, probe: BenchmarkBoundaryProbe, arbiter: object = None
) -> GenerationalExecutionContext:
    return GenerationalExecutionContext(
        artifact_root=tmp_path,
        source_identity={"code_revision": "deadbeef", "source_clean": True},
        recipe=GenerationalExecutionRecipe(
            recipe_id=PLAIN_RECIPE_ID, version="1", params={}
        ),
        factories=RunnerDependencyFactories(),
        attempt_id="attempt-1",
        boundary_observer=probe,
    )


def _assignment(config: SimulationRunnerConfig, run_id: str) -> ExperimentAssignment:
    return ExperimentAssignment(
        experiment_id="v3-benchmark-memory",
        condition_id="memory-case",
        condition_ordinal=0,
        seed=config.seed,
        seed_ordinal=0,
        replicate_index=0,
        run_id=RunId(run_id),
        runner_config=config,
    )


async def _dispatch(
    tmp_path: Path,
    scenario_id: str,
    config: SimulationRunnerConfig,
    probe: BenchmarkBoundaryProbe,
    *,
    arbiter: object = None,
) -> V3BenchmarkRunResult:
    recipe = CivilizationBenchmarkRecipe(
        scenario_id=scenario_id,
        lane=V3BenchmarkLane.RESEARCH,
        profile=V3BenchmarkProfile.SMOKE,
        seed=23,
        arm_id="observation",
    )
    context = CivilizationBenchmarkContext(
        assignment=_assignment(config, f"run-{scenario_id}"),
        execution_context=_context(tmp_path, probe),
        probe=probe,
        arbiter=arbiter,
    )
    return await execute_civilization_benchmark(recipe, context)


def test_all_memory_cases_build_exact_specs() -> None:
    for scenario_id in MEMORY_BENCHMARK_IDS:
        build = build_memory_benchmark(scenario_id)
        config = build.arms[0].config
        assert config.historical_memory_layers is not None
        if scenario_id == V3_BENCH_05_MEMORY_LAYERS:
            assert config.durable_records is None
        else:
            assert config.durable_records is not None
            assert config.new_agent_initialization is not None
            assert (
                config.new_agent_initialization.species_defaults_id
                == "species_default_developmental_v1"
            )
        assert decode_runner_config(encode_runner_config(config)) == config


def test_non_record_cases_have_no_arbiter() -> None:
    build = build_memory_benchmark(V3_BENCH_05_MEMORY_LAYERS)
    assert memory_benchmark_arbiter(
        V3_BENCH_05_MEMORY_LAYERS, build.arms[0].config
    ) is None


@pytest.mark.asyncio
async def test_memory_layers_measure_retained_owner_memory(tmp_path: Path) -> None:
    build = build_memory_benchmark(V3_BENCH_05_MEMORY_LAYERS)
    config = _short_config(build.arms[0].config, max_ticks=3)
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(tmp_path, V3_BENCH_05_MEMORY_LAYERS, config, probe)
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    assert result.evidence is V3BenchmarkEvidenceAvailability.COMPLETE
    statuses = {check.selector_id: check for check in result.checks}
    memory = statuses["historical_memory_evidence"]
    assert memory.status is V3BenchmarkCheckStatus.PASS
    assert memory.reason_code == "memory_window_complete"
    assert memory.denominator is not None
    assert memory.denominator >= 1


@pytest.mark.asyncio
async def test_accurate_record_survives_its_author(tmp_path: Path) -> None:
    build = build_memory_benchmark(V3_BENCH_06_RECORD_AFTER_WITNESSES)
    config = _short_config(build.arms[0].config, max_ticks=8)
    arbiter = memory_benchmark_arbiter(
        V3_BENCH_06_RECORD_AFTER_WITNESSES, config
    )
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(
        tmp_path,
        V3_BENCH_06_RECORD_AFTER_WITNESSES,
        config,
        probe,
        arbiter=arbiter,
    )
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    assert result.evidence is V3BenchmarkEvidenceAvailability.COMPLETE
    statuses = {check.selector_id: check for check in result.checks}
    records = statuses["durable_record_evidence"]
    assert records.status is V3BenchmarkCheckStatus.PASS
    assert records.reason_code == "record_persisted"
    final = probe.observations[-1].owners
    founder = next(owner for owner in final if owner.owner_id == "agent-origin")
    assert founder.living is False
    assert any(owner.owner_id.startswith("entrant") for owner in final)
    event_kinds = dict(probe.observations[-1].event_kind_counts)
    assert event_kinds.get("ArtifactCreated", 0) >= 1
    assert event_kinds.get("ArtifactDestroyed", 0) == 0


@pytest.mark.asyncio
async def test_false_record_is_physically_legal(tmp_path: Path) -> None:
    build = build_memory_benchmark(V3_BENCH_07_FALSE_RECORD)
    config = _short_config(build.arms[0].config, max_ticks=8)
    arbiter = memory_benchmark_arbiter(V3_BENCH_07_FALSE_RECORD, config)
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(
        tmp_path, V3_BENCH_07_FALSE_RECORD, config, probe, arbiter=arbiter
    )
    statuses = {check.selector_id: check for check in result.checks}
    assert statuses["durable_record_evidence"].status is V3BenchmarkCheckStatus.PASS
    assert result.evidence is V3BenchmarkEvidenceAvailability.COMPLETE


@pytest.mark.asyncio
async def test_unexercised_record_mechanism_is_not_a_pass(tmp_path: Path) -> None:
    build = build_memory_benchmark(V3_BENCH_06_RECORD_AFTER_WITNESSES)
    config = _short_config(build.arms[0].config, max_ticks=3)
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(
        tmp_path, V3_BENCH_06_RECORD_AFTER_WITNESSES, config, probe
    )
    statuses = {check.selector_id: check for check in result.checks}
    records = statuses["durable_record_evidence"]
    assert records.status is V3BenchmarkCheckStatus.UNEXECUTED
    assert records.reason_code == "no_record_observed"
    assert result.evidence is V3BenchmarkEvidenceAvailability.PARTIAL


def test_durable_record_disabled_is_unexecuted() -> None:
    probe = BenchmarkBoundaryProbe()
    check = evaluate_durable_records(
        probe, boundary_end_tick=0, mechanism_available=False
    )
    assert check.status is V3BenchmarkCheckStatus.UNEXECUTED
    assert check.reason_code == "durable_records_disabled"


@pytest.mark.asyncio
async def test_interpretation_disabled_control_preserves_record_only(
    tmp_path: Path,
) -> None:
    from simulation.new_agent_initialization import (
        default_new_agent_initialization_spec,
    )

    build = build_memory_benchmark(V3_BENCH_06_RECORD_AFTER_WITNESSES)
    config = _short_config(build.arms[0].config, max_ticks=3)
    config = replace(
        config,
        new_agent_initialization=default_new_agent_initialization_spec(),
    )
    arbiter = memory_benchmark_arbiter(
        V3_BENCH_06_RECORD_AFTER_WITNESSES, config
    )
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(
        tmp_path,
        V3_BENCH_06_RECORD_AFTER_WITNESSES,
        config,
        probe,
        arbiter=arbiter,
    )
    statuses = {check.selector_id: check for check in result.checks}
    assert statuses["durable_record_evidence"].status is V3BenchmarkCheckStatus.PASS
    interpretations = sum(
        owner.artifact_interpretations
        for observation in probe.observations
        for owner in observation.owners
    )
    assert interpretations == 0


@pytest.mark.asyncio
async def test_legal_destruction_removes_physical_record(tmp_path: Path) -> None:
    from experiments.interventions import (
        MilestoneInterventionArbiter,
        MilestoneOverride,
    )
    from simulation.runner import SimulationRunner
    from world.actions import DamageRecord
    from world.events import ArtifactCreated, ArtifactDestroyed

    build = build_memory_benchmark(V3_BENCH_06_RECORD_AFTER_WITNESSES)
    config = _short_config(build.arms[0].config, max_ticks=3)
    inscribe = memory_benchmark_arbiter(
        V3_BENCH_06_RECORD_AFTER_WITNESSES, config
    )
    assert inscribe is not None
    founder = config.agents[0].agent_id
    async with await SimulationRunner.from_config(config) as runner:
        runner.set_intervention_arbiter(inscribe)
        await runner.initialize_finalized_boundary()
        await runner.run_tick()
        created = [
            event.details
            for event in runner.engine.export_events().events
            if type(event.details) is ArtifactCreated
        ]
        assert len(created) == 1
        artifact_id = created[0].artifact_id
        destroyer = MilestoneInterventionArbiter(
            (
                MilestoneOverride(
                    milestone_id="v3-bench-destroy-record",
                    tick=1,
                    agent_id=founder,
                    build_command=lambda: DamageRecord(
                        artifact_id=artifact_id, mode="destroy"
                    ),
                ),
            ),
            override_budget=1,
        )
        runner.set_intervention_arbiter(destroyer)
        await runner.run_tick()
        events = runner.engine.export_events().events
        destroyed = [
            event.details
            for event in events
            if type(event.details) is ArtifactDestroyed
        ]
        assert destroyed
        assert destroyed[0].artifact_id == artifact_id
