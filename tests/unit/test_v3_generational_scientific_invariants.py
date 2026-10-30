"""Executable generational invariants backed by real benchmark trajectories."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from experiments.civilization_benchmark_evidence import (
    GENERATIONAL_INVARIANT_IDS,
    BenchmarkBoundaryProbe,
    BoundaryObservation,
    OwnerStoreSnapshot,
    evaluate_blank_slate,
)
from experiments.civilization_benchmark_exchange import (
    build_exchange_benchmark,
    exchange_benchmark_arbiter,
    required_exchange_milestones,
)
from experiments.civilization_benchmark_execution import (
    CivilizationBenchmarkContext,
    CivilizationBenchmarkRecipe,
    execute_civilization_benchmark,
)
from experiments.civilization_benchmark_institutions import (
    build_institutions_benchmark,
    institutions_benchmark_arbiter,
    required_institutions_milestones,
)
from experiments.civilization_benchmark_memory import (
    build_memory_benchmark,
    memory_benchmark_arbiter,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheck,
    V3BenchmarkCheckStatus,
    V3BenchmarkExecutionStatus,
    V3BenchmarkLane,
    V3BenchmarkProfile,
    V3BenchmarkRunResult,
)
from experiments.civilization_benchmark_population import (
    build_population_benchmark,
)
from experiments.civilization_benchmark_regions import (
    build_region_benchmark,
    region_benchmark_arbiter,
    required_region_milestones,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_01_BLANK_SLATE,
    V3_BENCH_02_DEPENDENT_CARE,
    V3_BENCH_06_RECORD_AFTER_WITNESSES,
    V3_BENCH_07_FALSE_RECORD,
    V3_BENCH_10_TECHNOLOGY_LOSS,
    V3_BENCH_11_TECHNOLOGY_REDISCOVERY,
    V3_BENCH_12_INHERITANCE_PRACTICES,
    V3_BENCH_18_REGIONAL_MIGRATION,
    V3_BENCH_20_RECONTACT_EXCHANGE,
    V3_BENCH_24_NARRATIVE_AFTER_WITNESSES,
    V3_BENCH_25_PERSISTENT_ROLE,
)
from experiments.civilization_benchmark_technology import (
    build_technology_benchmark,
    required_technology_milestones,
    technology_benchmark_arbiter,
)
from experiments.coordinator import ExperimentAssignment
from experiments.generational_archive import GenerationalExecutionRecipe
from experiments.generational_execution import (
    PLAIN_RECIPE_ID,
    GenerationalExecutionContext,
)
from experiments.interventions import MilestoneInterventionArbiter
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories
from simulation.runner_models import (
    PopulationLifecycleSpec,
    SimulationRunnerConfig,
)
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold


def _milestones_for(
    scenario_id: str, config: SimulationRunnerConfig
) -> tuple[str, ...]:
    if scenario_id in {V3_BENCH_18_REGIONAL_MIGRATION, V3_BENCH_20_RECONTACT_EXCHANGE}:
        return required_region_milestones(scenario_id)
    if scenario_id in {
        V3_BENCH_10_TECHNOLOGY_LOSS,
        V3_BENCH_11_TECHNOLOGY_REDISCOVERY,
    }:
        return required_technology_milestones(scenario_id)
    if scenario_id == V3_BENCH_12_INHERITANCE_PRACTICES:
        return required_exchange_milestones(scenario_id)
    if scenario_id in {
        V3_BENCH_24_NARRATIVE_AFTER_WITNESSES,
        V3_BENCH_25_PERSISTENT_ROLE,
    }:
        return required_institutions_milestones(scenario_id, config)
    return ()


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
        max_population=12,
    )
    return replace(
        config,
        population_lifecycle=short,
        stop_policy=replace(config.stop_policy, max_ticks=max_ticks),
    )


def _builder(scenario_id: str) -> Callable[..., Any]:
    if scenario_id in {V3_BENCH_01_BLANK_SLATE, V3_BENCH_02_DEPENDENT_CARE}:
        return build_population_benchmark
    if scenario_id in {V3_BENCH_06_RECORD_AFTER_WITNESSES, V3_BENCH_07_FALSE_RECORD}:
        return build_memory_benchmark
    if scenario_id in {
        V3_BENCH_10_TECHNOLOGY_LOSS,
        V3_BENCH_11_TECHNOLOGY_REDISCOVERY,
    }:
        return build_technology_benchmark
    if scenario_id in {
        V3_BENCH_12_INHERITANCE_PRACTICES,
    }:
        return build_exchange_benchmark
    if scenario_id in {
        V3_BENCH_18_REGIONAL_MIGRATION,
        V3_BENCH_20_RECONTACT_EXCHANGE,
    }:
        return build_region_benchmark
    if scenario_id in {
        V3_BENCH_24_NARRATIVE_AFTER_WITNESSES,
        V3_BENCH_25_PERSISTENT_ROLE,
    }:
        return build_institutions_benchmark
    raise AssertionError(f"no builder for {scenario_id}")


def _arbiter(
    scenario_id: str, config: SimulationRunnerConfig
) -> MilestoneInterventionArbiter | None:
    if scenario_id in {V3_BENCH_06_RECORD_AFTER_WITNESSES, V3_BENCH_07_FALSE_RECORD}:
        return memory_benchmark_arbiter(scenario_id, config)
    if scenario_id in {
        V3_BENCH_10_TECHNOLOGY_LOSS,
        V3_BENCH_11_TECHNOLOGY_REDISCOVERY,
    }:
        return technology_benchmark_arbiter(scenario_id, config)
    if scenario_id == V3_BENCH_12_INHERITANCE_PRACTICES:
        return exchange_benchmark_arbiter(scenario_id, config)
    if scenario_id in {
        V3_BENCH_18_REGIONAL_MIGRATION,
        V3_BENCH_20_RECONTACT_EXCHANGE,
    }:
        return region_benchmark_arbiter(scenario_id, config)
    if scenario_id in {
        V3_BENCH_24_NARRATIVE_AFTER_WITNESSES,
        V3_BENCH_25_PERSISTENT_ROLE,
    }:
        return institutions_benchmark_arbiter(scenario_id, config)
    return None


async def _run(
    tmp_path: Path,
    scenario_id: str,
    *,
    max_ticks: int = 10,
    lifespan: int = 24,
    interval: int = 8,
    assist: bool = True,
) -> tuple[V3BenchmarkRunResult, BenchmarkBoundaryProbe]:
    build = _builder(scenario_id)(scenario_id)
    config = _short_config(
        build.arms[0].config,
        max_ticks=max_ticks,
        lifespan=lifespan,
        interval=interval,
    )
    arbiter = _arbiter(scenario_id, config) if assist else None
    probe = BenchmarkBoundaryProbe()
    recipe = CivilizationBenchmarkRecipe(
        scenario_id=scenario_id,
        lane=V3BenchmarkLane.RESEARCH,
        profile=V3BenchmarkProfile.SMOKE,
        seed=23,
        arm_id="observation",
    )
    context = CivilizationBenchmarkContext(
        assignment=ExperimentAssignment(
            experiment_id="v3-invariants",
            condition_id=scenario_id,
            condition_ordinal=0,
            seed=config.seed,
            seed_ordinal=0,
            replicate_index=0,
            run_id=RunId(f"inv-{scenario_id}"),
            runner_config=config,
        ),
        execution_context=GenerationalExecutionContext(
            artifact_root=tmp_path / f"{scenario_id}-{'assist' if assist else 'plain'}",
            source_identity={"code_revision": "deadbeef", "source_clean": True},
            recipe=GenerationalExecutionRecipe(
                recipe_id=PLAIN_RECIPE_ID, version="1", params={}
            ),
            factories=RunnerDependencyFactories(),
            attempt_id=f"{scenario_id}-{'assist' if assist else 'plain'}",
        ),
        probe=probe,
        arbiter=arbiter,
        required_milestone_ids=_milestones_for(scenario_id, config),
    )
    return await execute_civilization_benchmark(recipe, context), probe


def _check(result: V3BenchmarkRunResult, selector: str) -> V3BenchmarkCheck:
    return {check.selector_id: check for check in result.checks}[selector]


async def _blank_slate(tmp_path: Path) -> None:
    result, probe = await _run(
        tmp_path, V3_BENCH_01_BLANK_SLATE, max_ticks=16, interval=8
    )
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    assert probe.new_owners()
    check = _check(result, "new_agent_initialization_evidence")
    assert check.status is V3BenchmarkCheckStatus.PASS
    # Negative control: a populated "newborn" store must fail the same check.
    leaked = OwnerStoreSnapshot(
        owner_id="poisoned",
        entity_id="body-poisoned",
        generation_index=0,
        living=True,
        invocation_count=1,
        counts=(("episodic_memory", 1),),
        measured_stores=("episodic_memory",),
        unmeasured_stores=(),
    )
    failed = evaluate_blank_slate((leaked,), boundary_end_tick=1)
    assert failed.status is V3BenchmarkCheckStatus.FAIL


async def _valid_historical_channels(tmp_path: Path) -> None:
    assisted, _ = await _run(tmp_path, V3_BENCH_24_NARRATIVE_AFTER_WITNESSES)
    assert (
        _check(assisted, "generational_narrative_evidence").status
        is V3BenchmarkCheckStatus.PASS
    )
    # Negative control: no delivered story and no retained ledger is not a
    # surviving narrative, even with the mechanism available.
    from types import SimpleNamespace

    from experiments.civilization_benchmark_institutions import (
        evaluate_generational_narratives,
    )

    empty_probe = BenchmarkBoundaryProbe()
    empty_probe._observations.append(
        BoundaryObservation(boundary_tick=10, owners=(), new_owners=())
    )
    empty = evaluate_generational_narratives(
        empty_probe,
        SimpleNamespace(cultural_narrative_ledgers=()),
        boundary_end_tick=10,
        mechanism_available=True,
    )
    assert empty.status is V3BenchmarkCheckStatus.UNEXECUTED
    assert empty.reason_code == "no_narrative_lineage_observed"


async def _dead_stop_acting(tmp_path: Path) -> None:
    result, probe = await _run(
        tmp_path,
        V3_BENCH_02_DEPENDENT_CARE,
        max_ticks=10,
        lifespan=6,
        interval=2,
    )
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    assert probe.death_ticks_by_body
    for owner in probe.observations[-1].owners:
        if owner.living:
            continue
        history = [
            snapshot
            for observation in probe.observations
            for snapshot in observation.owners
            if snapshot.owner_id == owner.owner_id
        ]
        dead = [item for item in history if not item.living]
        assert dead
        if len(dead) >= 2:
            assert dead[-2].invocation_count == dead[-1].invocation_count


async def _physical_record_persistence(tmp_path: Path) -> None:
    result, _ = await _run(tmp_path, V3_BENCH_06_RECORD_AFTER_WITNESSES)
    assert (
        _check(result, "durable_record_evidence").status is V3BenchmarkCheckStatus.PASS
    )


async def _false_records_legal(tmp_path: Path) -> None:
    result, _ = await _run(tmp_path, V3_BENCH_07_FALSE_RECORD)
    assert (
        _check(result, "durable_record_evidence").status is V3BenchmarkCheckStatus.PASS
    )


async def _technology_loss_possible(tmp_path: Path) -> None:
    result, _ = await _run(tmp_path, V3_BENCH_10_TECHNOLOGY_LOSS)
    assert (
        _check(result, "technique_lifecycle_evidence").status
        is V3BenchmarkCheckStatus.PASS
    )


async def _auditable_knowledge_lineage(tmp_path: Path) -> None:
    result, _ = await _run(tmp_path, V3_BENCH_11_TECHNOLOGY_REDISCOVERY)
    assert (
        _check(result, "knowledge_genealogy_evidence").status
        is V3BenchmarkCheckStatus.PASS
    )


async def _subjective_roles(tmp_path: Path) -> None:
    result, probe = await _run(tmp_path, V3_BENCH_25_PERSISTENT_ROLE)
    assert (
        _check(result, "institution_concept_evidence").status
        is V3BenchmarkCheckStatus.PASS
    )
    assert not any(
        "Office" in kind or "Institution" in kind for kind, _ in probe.event_kind_totals
    )


async def _possession_not_legitimacy(tmp_path: Path) -> None:
    result, probe = await _run(
        tmp_path,
        V3_BENCH_12_INHERITANCE_PRACTICES,
        max_ticks=10,
        lifespan=6,
        interval=2,
    )
    assert (
        _check(result, "possession_succession_evidence").status
        is V3BenchmarkCheckStatus.PASS
    )
    assert not any("Legitima" in kind for kind, _ in probe.event_kind_totals)


async def _isolated_knowledge(tmp_path: Path) -> None:
    result, _ = await _run(tmp_path, V3_BENCH_20_RECONTACT_EXCHANGE)
    assert (
        _check(result, "knowledge_genealogy_evidence").status
        is V3BenchmarkCheckStatus.PASS
    )


async def _engine_migration(tmp_path: Path) -> None:
    result, probe = await _run(tmp_path, V3_BENCH_18_REGIONAL_MIGRATION)
    assert _check(result, "migration_evidence").status is V3BenchmarkCheckStatus.PASS
    assert probe.event_total("JourneyStarted") >= 1
    assert probe.event_total("JourneyArrived") >= 1


def _module_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _imported_modules(path: Path) -> set[str]:
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _check_coordinates_nonsemantic() -> None:
    for path in Path("src/simulation").glob("*.py"):
        assert not any(
            name == "observer" or name.startswith("observer.")
            for name in _imported_modules(path)
        )


def _check_observer_read_only() -> None:
    observer = Path("src/observer")
    forbidden = ("run_tick(", ".admit_", "commit_tick(", "ActionSubmission(")
    for path in observer.glob("*.py"):
        text = _module_text(path)
        for token in forbidden:
            assert token not in text


async def _coordinates_nonsemantic(tmp_path: Path) -> None:
    del tmp_path
    _check_coordinates_nonsemantic()


async def _observer_read_only(tmp_path: Path) -> None:
    del tmp_path
    _check_observer_read_only()


INVARIANT_CHECKS: dict[str, Callable[[Path], Awaitable[None]]] = {
    "blank_slate": _blank_slate,
    "valid_historical_channels": _valid_historical_channels,
    "dead_stop_acting": _dead_stop_acting,
    "physical_record_persistence": _physical_record_persistence,
    "false_records_legal": _false_records_legal,
    "technology_loss_possible": _technology_loss_possible,
    "auditable_knowledge_lineage": _auditable_knowledge_lineage,
    "subjective_roles": _subjective_roles,
    "possession_not_legitimacy": _possession_not_legitimacy,
    "isolated_knowledge": _isolated_knowledge,
    "engine_migration": _engine_migration,
    "coordinates_nonsemantic": _coordinates_nonsemantic,
    "observer_read_only": _observer_read_only,
}


def test_all_required_invariants_are_declared() -> None:
    assert set(INVARIANT_CHECKS) == set(GENERATIONAL_INVARIANT_IDS)


@pytest.mark.asyncio
@pytest.mark.parametrize("invariant_id", GENERATIONAL_INVARIANT_IDS)
async def test_generational_invariant(invariant_id: str, tmp_path: Path) -> None:
    await INVARIANT_CHECKS[invariant_id](tmp_path)
