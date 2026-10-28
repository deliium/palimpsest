"""V3 benchmark language cases: owner-local symbols, sense and translation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from experiments.civilization_benchmark_evidence import BenchmarkBoundaryProbe
from experiments.civilization_benchmark_execution import (
    CivilizationBenchmarkContext,
    CivilizationBenchmarkRecipe,
    execute_civilization_benchmark,
    execute_stepped_benchmark_runner,
)
from experiments.civilization_benchmark_language import (
    LANGUAGE_BENCHMARK_IDS,
    build_language_benchmark,
    evaluate_semantic_drift,
    evaluate_symbolic_language,
    evaluate_translation,
    language_benchmark_arbiter,
    required_language_milestones,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheckStatus,
    V3BenchmarkExecutionStatus,
    V3BenchmarkLane,
    V3BenchmarkProfile,
    V3BenchmarkRunResult,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_21_VOCABULARY_DIVERGENCE,
    V3_BENCH_22_GENERATIONAL_SEMANTIC_DRIFT,
    V3_BENCH_23_CROSS_CULTURAL_MISTRANSLATION,
)
from experiments.coordinator import ExperimentAssignment
from experiments.generational_archive import GenerationalExecutionRecipe
from experiments.generational_execution import (
    PLAIN_RECIPE_ID,
    GenerationalExecutionContext,
)
from experiments.interventions import MilestoneInterventionArbiter
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    PopulationLifecycleSpec,
    SemanticNamingMode,
    SimulationRunnerConfig,
    SymbolicLanguageMode,
    TranslationMode,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold


def _short_config(
    config: SimulationRunnerConfig,
    *,
    max_ticks: int,
    lifespan: int = 24,
    interval: int = 8,
) -> SimulationRunnerConfig:
    lifecycle = config.population_lifecycle
    assert isinstance(lifecycle, PopulationLifecycleSpec)
    short = replace(
        lifecycle,
        lifespan_ticks=lifespan,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 1),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 2),
            LifecycleStageThreshold(LifecycleStageId("adult"), max(3, lifespan - 1)),
        ),
        demographic_policy_params={
            **dict(lifecycle.demographic_policy_params),
            "interval_ticks": interval,
            "generation_length_ticks": interval,
        },
        max_population=10,
    )
    return replace(
        config,
        population_lifecycle=short,
        stop_policy=replace(config.stop_policy, max_ticks=max_ticks),
    )


def _context(
    tmp_path: Path, probe: BenchmarkBoundaryProbe
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
        experiment_id="v3-benchmark-language",
        condition_id="language-case",
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
    arbiter: MilestoneInterventionArbiter | None,
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
        required_milestone_ids=required_language_milestones(scenario_id, config),
    )
    return await execute_civilization_benchmark(recipe, context)


def test_language_cases_build_exact_modes() -> None:
    for scenario_id in LANGUAGE_BENCHMARK_IDS:
        build = build_language_benchmark(scenario_id)
        config = build.arms[0].config
        assert all(
            agent.cognition.semantic_naming_mode is SemanticNamingMode.DETERMINISTIC
            for agent in config.agents
        )
        assert all(
            agent.cognition.symbolic_language_mode is SymbolicLanguageMode.DETERMINISTIC
            for agent in config.agents
        )
        assert decode_runner_config(encode_runner_config(config)) == config
        translation = {agent.cognition.translation_mode for agent in config.agents}
        if scenario_id == V3_BENCH_23_CROSS_CULTURAL_MISTRANSLATION:
            assert translation == {TranslationMode.DETERMINISTIC}
        else:
            assert translation == {TranslationMode.DISABLED}


@pytest.mark.asyncio
async def test_vocabulary_divergence_keeps_owner_ledgers_separate(
    tmp_path: Path,
) -> None:
    scenario_id = V3_BENCH_21_VOCABULARY_DIVERGENCE
    build = build_language_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=10)
    arbiter = language_benchmark_arbiter(scenario_id, config)
    assert arbiter is not None
    async with await SimulationRunner.from_config(config) as runner:
        runner.set_intervention_arbiter(arbiter)
        probe = BenchmarkBoundaryProbe()
        stepped = await execute_stepped_benchmark_runner(
            runner, boundary_observer=probe
        )
        ledgers = tuple(stepped.result.symbolic_ledgers)
    owners = {
        cast(Any, ledger).owner_id.value
        for ledger in ledgers
        if getattr(ledger, "interpretations", ())
    }
    assert {"agent-extra-1", "agent-extra-2"} <= owners
    assert not any(owner in {"agent-spring", "agent-remote"} for owner in owners)
    check = evaluate_symbolic_language(
        probe,
        stepped.result,
        boundary_end_tick=stepped.result.ticks_committed,
        mechanism_available=True,
    )
    assert check.status is V3BenchmarkCheckStatus.PASS
    assert check.reason_code == "symbolic_interpretations_observed"
    assert (check.numerator or 0) > 0


@pytest.mark.asyncio
async def test_semantic_drift_requires_retained_sense_history(
    tmp_path: Path,
) -> None:
    scenario_id = V3_BENCH_22_GENERATIONAL_SEMANTIC_DRIFT
    build = build_language_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=10, interval=1)
    arbiter = language_benchmark_arbiter(scenario_id, config)
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(tmp_path, scenario_id, config, probe, arbiter=arbiter)
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    checks = {check.selector_id: check for check in result.checks}
    drift = checks["semantic_drift_evidence"]
    assert drift.status is V3BenchmarkCheckStatus.PASS
    assert drift.reason_code == "sense_history_observed"
    assert (drift.numerator or 0) > 0
    assert checks["symbolic_language_evidence"].status is V3BenchmarkCheckStatus.PASS


@pytest.mark.asyncio
async def test_translation_is_owner_local_hypothesis_evidence(tmp_path: Path) -> None:
    scenario_id = V3_BENCH_23_CROSS_CULTURAL_MISTRANSLATION
    build = build_language_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=10)
    arbiter = language_benchmark_arbiter(scenario_id, config)
    assert arbiter is not None
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(tmp_path, scenario_id, config, probe, arbiter=arbiter)
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    checks = {check.selector_id: check for check in result.checks}
    translation = checks["translation_evidence"]
    assert translation.status is V3BenchmarkCheckStatus.PASS
    assert translation.reason_code == "translation_hypotheses_observed"
    assert (translation.numerator or 0) >= 1


def test_missing_evidence_and_disabled_modes_never_pass() -> None:
    from types import SimpleNamespace

    class _Probe:
        observations = [SimpleNamespace(boundary_tick=1, owners=())]
        failures: tuple[str, ...] = ()

    class _Result:
        symbolic_ledgers: tuple[object, ...] = ()
        terminology_ledgers: tuple[object, ...] = ()
        translation_ledgers: tuple[object, ...] = ()

    probe = _Probe()
    result = _Result()
    symbolic = evaluate_symbolic_language(
        probe,  # type: ignore[arg-type]
        result,
        boundary_end_tick=1,
        mechanism_available=True,
    )
    assert symbolic.status is V3BenchmarkCheckStatus.UNEXECUTED
    assert symbolic.reason_code == "no_symbolic_evidence_observed"
    drift = evaluate_semantic_drift(
        probe,  # type: ignore[arg-type]
        result,
        boundary_end_tick=1,
        mechanism_available=True,
    )
    assert drift.reason_code == "no_sense_history_observed"
    translation = evaluate_translation(
        probe,  # type: ignore[arg-type]
        result,
        boundary_end_tick=1,
        mechanism_available=False,
    )
    assert translation.status is V3BenchmarkCheckStatus.UNEXECUTED
    assert translation.reason_code == "translation_evidence_disabled"
