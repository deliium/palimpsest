"""Outer production composition for civilization benchmark CLI runs.

Builds bounded v55 assignments, executes them through the trusted benchmark
dispatcher, and publishes immutable sibling artifacts. Never imports API and
never starts HTTP.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.civilization_benchmark_artifacts import (
    BenchmarkArtifactStore,
    BenchmarkRunReference,
    build_run_document,
)
from experiments.civilization_benchmark_evidence import BenchmarkBoundaryProbe
from experiments.civilization_benchmark_execution import (
    CivilizationBenchmarkContext,
    CivilizationBenchmarkRecipe,
    execute_civilization_benchmark,
)
from experiments.civilization_benchmark_forks import (
    build_fork_benchmark_spec,
    execute_grouped_benchmark,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkCoverage,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkExecutionStatus,
    V3BenchmarkLane,
    V3BenchmarkPhenomenon,
    V3BenchmarkProfile,
    V3BenchmarkRunResult,
)
from experiments.civilization_benchmark_suite import get_v3_benchmark_scenario
from experiments.civilization_benchmark_visual import (
    VISUAL_BENCHMARK_RECIPE_ID,
    build_v3_visual_benchmark,
)
from experiments.coordinator import ExperimentAssignment
from experiments.generational_archive import GenerationalExecutionRecipe
from experiments.generational_execution import (
    BENCHMARK_RECIPE_ID,
    GenerationalExecutionContext,
)
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories
from simulation.runner_models import SimulationRunnerConfig, runner_stop_is_failure
from simulation.runner_serialization import runner_config_fingerprint

_LOG: Final[logging.Logger] = logging.getLogger(
    "research_runner.civilization_benchmark_composition"
)


class BenchmarkCompositionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class BenchmarkSelectionItem:
    scenario_id: str
    lane: V3BenchmarkLane
    profile: V3BenchmarkProfile
    seed: int
    arm_id: str


def _independent_case_config(
    item: BenchmarkSelectionItem,
) -> SimulationRunnerConfig:
    """Materialize the domain-specific bounded world for one independent case."""
    from experiments.civilization_benchmark_coordination import (
        COORDINATION_BENCHMARK_IDS,
        build_coordination_benchmark,
    )
    from experiments.civilization_benchmark_exchange import (
        EXCHANGE_BENCHMARK_IDS,
        build_exchange_benchmark,
    )
    from experiments.civilization_benchmark_institutions import (
        INSTITUTIONS_BENCHMARK_IDS,
        build_institutions_benchmark,
    )
    from experiments.civilization_benchmark_language import (
        LANGUAGE_BENCHMARK_IDS,
        build_language_benchmark,
    )
    from experiments.civilization_benchmark_memory import (
        MEMORY_BENCHMARK_IDS,
        build_memory_benchmark,
    )
    from experiments.civilization_benchmark_population import (
        POPULATION_BENCHMARK_IDS,
        build_population_benchmark,
    )
    from experiments.civilization_benchmark_regions import (
        REGION_BENCHMARK_IDS,
        build_region_benchmark,
    )
    from experiments.civilization_benchmark_technology import (
        TECHNOLOGY_BENCHMARK_IDS,
        build_technology_benchmark,
    )

    scenario_id = item.scenario_id
    build: object
    if scenario_id in POPULATION_BENCHMARK_IDS:
        build = build_population_benchmark(
            scenario_id,
            seed=item.seed,
            profile=item.profile,
            lane=item.lane,
        )
    elif scenario_id in MEMORY_BENCHMARK_IDS:
        build = build_memory_benchmark(
            scenario_id,
            seed=item.seed,
            profile=item.profile,
            lane=item.lane,
        )
    elif scenario_id in TECHNOLOGY_BENCHMARK_IDS:
        build = build_technology_benchmark(
            scenario_id,
            seed=item.seed,
            profile=item.profile,
            lane=item.lane,
        )
    elif scenario_id in EXCHANGE_BENCHMARK_IDS:
        build = build_exchange_benchmark(
            scenario_id,
            seed=item.seed,
            profile=item.profile,
            lane=item.lane,
        )
    elif scenario_id in COORDINATION_BENCHMARK_IDS:
        build = build_coordination_benchmark(
            scenario_id,
            seed=item.seed,
            profile=item.profile,
            lane=item.lane,
        )
    elif scenario_id in REGION_BENCHMARK_IDS:
        build = build_region_benchmark(
            scenario_id,
            seed=item.seed,
            profile=item.profile,
            lane=item.lane,
        )
    elif scenario_id in LANGUAGE_BENCHMARK_IDS:
        build = build_language_benchmark(
            scenario_id,
            seed=item.seed,
            profile=item.profile,
            lane=item.lane,
        )
    elif scenario_id in INSTITUTIONS_BENCHMARK_IDS:
        build = build_institutions_benchmark(
            scenario_id,
            seed=item.seed,
            profile=item.profile,
            lane=item.lane,
        )
    else:
        raise BenchmarkCompositionError("unknown_case_builder")
    from experiments.civilization_benchmark_base import V3BenchmarkScenarioBuild

    if type(build) is not V3BenchmarkScenarioBuild:
        raise BenchmarkCompositionError("case_builder_result_invalid")
    for arm in build.arms:
        if arm.arm_id == item.arm_id:
            return arm.config
    raise BenchmarkCompositionError("case_arm_missing")


def _case_arbiter(
    scenario_id: str,
    config: SimulationRunnerConfig,
    *,
    run_id: RunId,
) -> object | None:
    """Return the declared mechanism arbiter; research lanes stay unassisted."""
    from experiments.civilization_benchmark_coordination import (
        COORDINATION_BENCHMARK_IDS,
        coordination_benchmark_arbiter,
    )
    from experiments.civilization_benchmark_exchange import (
        EXCHANGE_BENCHMARK_IDS,
        exchange_benchmark_arbiter,
    )
    from experiments.civilization_benchmark_institutions import (
        INSTITUTIONS_BENCHMARK_IDS,
        institutions_benchmark_arbiter,
    )
    from experiments.civilization_benchmark_language import (
        LANGUAGE_BENCHMARK_IDS,
        language_benchmark_arbiter,
    )
    from experiments.civilization_benchmark_memory import (
        MEMORY_BENCHMARK_IDS,
        memory_benchmark_arbiter,
    )
    from experiments.civilization_benchmark_regions import (
        REGION_BENCHMARK_IDS,
        region_benchmark_arbiter,
    )
    from experiments.civilization_benchmark_technology import (
        TECHNOLOGY_BENCHMARK_IDS,
        technology_benchmark_arbiter,
    )

    if scenario_id in MEMORY_BENCHMARK_IDS:
        return memory_benchmark_arbiter(scenario_id, config)
    if scenario_id in TECHNOLOGY_BENCHMARK_IDS:
        return technology_benchmark_arbiter(scenario_id, config)
    if scenario_id in EXCHANGE_BENCHMARK_IDS:
        return exchange_benchmark_arbiter(scenario_id, config)
    if scenario_id in COORDINATION_BENCHMARK_IDS:
        return coordination_benchmark_arbiter(scenario_id, config, run_id=run_id)
    if scenario_id in REGION_BENCHMARK_IDS:
        return region_benchmark_arbiter(scenario_id, config)
    if scenario_id in LANGUAGE_BENCHMARK_IDS:
        return language_benchmark_arbiter(scenario_id, config)
    if scenario_id in INSTITUTIONS_BENCHMARK_IDS:
        return institutions_benchmark_arbiter(scenario_id, config)
    return None


def _case_required_milestones(
    scenario_id: str, config: SimulationRunnerConfig
) -> tuple[str, ...]:
    """Declared mechanism acknowledgements required by the controlled lane."""
    from experiments.civilization_benchmark_coordination import (
        COORDINATION_BENCHMARK_IDS,
        required_coordination_milestones,
    )
    from experiments.civilization_benchmark_exchange import (
        EXCHANGE_BENCHMARK_IDS,
        required_exchange_milestones,
    )
    from experiments.civilization_benchmark_institutions import (
        INSTITUTIONS_BENCHMARK_IDS,
        required_institutions_milestones,
    )
    from experiments.civilization_benchmark_language import (
        LANGUAGE_BENCHMARK_IDS,
        required_language_milestones,
    )
    from experiments.civilization_benchmark_regions import (
        REGION_BENCHMARK_IDS,
        required_region_milestones,
    )
    from experiments.civilization_benchmark_technology import (
        TECHNOLOGY_BENCHMARK_IDS,
        required_technology_milestones,
    )

    if scenario_id in COORDINATION_BENCHMARK_IDS:
        return required_coordination_milestones(scenario_id)
    if scenario_id in EXCHANGE_BENCHMARK_IDS:
        return required_exchange_milestones(scenario_id)
    if scenario_id in INSTITUTIONS_BENCHMARK_IDS:
        return required_institutions_milestones(scenario_id, config)
    if scenario_id in LANGUAGE_BENCHMARK_IDS:
        return required_language_milestones(scenario_id, config)
    if scenario_id in REGION_BENCHMARK_IDS:
        return required_region_milestones(scenario_id)
    if scenario_id in TECHNOLOGY_BENCHMARK_IDS:
        return required_technology_milestones(scenario_id)
    return ()


def _run_id(item: BenchmarkSelectionItem, revision: str) -> RunId:
    """Build a bounded, deterministic run identity (safe archive segment)."""
    from simulation.generational_seeds import canonical_sha256

    digest = canonical_sha256(
        {
            "scenario_id": item.scenario_id,
            "lane": item.lane.value,
            "arm_id": item.arm_id,
            "seed": item.seed,
            "revision": revision,
        }
    )[:12]
    scenario = item.scenario_id.removeprefix("v3-bench-")[:20]
    lane = item.lane.value[:4]
    arm = item.arm_id[:4]
    return RunId(f"v3b-{scenario}-{lane}-{arm}-s{item.seed}-{digest}")


async def execute_selection(
    items: Sequence[BenchmarkSelectionItem],
    *,
    output_root: Path,
    source_identity: Mapping[str, object],
    timeout_seconds: int,
) -> tuple[dict[str, object], ...]:
    """Execute selected independent attempts and publish verified artifacts."""
    store = BenchmarkArtifactStore(
        output_root,
        profile=items[0].profile if items else V3BenchmarkProfile.SMOKE,
    )
    documents: list[dict[str, object]] = []
    references: list[BenchmarkRunReference] = []
    for item in items:
        visual = item.scenario_id == VISUAL_BENCHMARK_RECIPE_ID
        if visual:
            config = build_v3_visual_benchmark(seed=item.seed).config
        else:
            spec = get_v3_benchmark_scenario(item.scenario_id)
            if spec.recipe.arm_count > 1:
                config = build_fork_benchmark_spec(
                    item.scenario_id, seed=item.seed, profile=item.profile
                ).base
            else:
                config = _independent_case_config(item)
        assignment = ExperimentAssignment(
            experiment_id="v3-generational-civilization-benchmark",
            condition_id=item.scenario_id,
            condition_ordinal=0,
            seed=item.seed,
            seed_ordinal=0,
            replicate_index=0,
            run_id=_run_id(item, str(source_identity.get("code_revision", ""))),
            runner_config=config,
        )
        probe = BenchmarkBoundaryProbe()
        try:
            if visual:
                result = await asyncio.wait_for(
                    _execute_visual_attempt(
                        item,
                        assignment,
                        probe,
                        store_root=store.root,
                        source_identity=source_identity,
                    ),
                    timeout=timeout_seconds,
                )
            elif get_v3_benchmark_scenario(item.scenario_id).recipe.arm_count > 1:
                recipe = CivilizationBenchmarkRecipe(
                    scenario_id=item.scenario_id,
                    lane=item.lane,
                    profile=item.profile,
                    seed=item.seed,
                    arm_id=item.arm_id,
                    command_plan_id="v3-benchmark-grouped-v1",
                    command_plan_version="1",
                )
                captured: dict[str, object] = {}

                async def _finalize_child(
                    child: object,
                    slot: object,
                    *,
                    rows: dict[str, object] = captured,
                ) -> None:
                    try:
                        boundary = await child.export_finalized_research_boundary()  # type: ignore[attr-defined]
                    except Exception:
                        rows[slot.child_run_id] = "unavailable"  # type: ignore[attr-defined]
                        return
                    rows[slot.child_run_id] = boundary  # type: ignore[attr-defined]

                async def _grouped_runner(
                    grouped_recipe: CivilizationBenchmarkRecipe,
                    grouped_context: CivilizationBenchmarkContext,
                ) -> V3BenchmarkRunResult:
                    del grouped_context
                    return await execute_grouped_benchmark(
                        grouped_recipe.scenario_id,
                        lane=grouped_recipe.lane,
                        profile=grouped_recipe.profile,
                        seed=grouped_recipe.seed,
                        child_finalizer=_finalize_child,
                        factories=RunnerDependencyFactories(),
                        source_identity=str(
                            source_identity.get("code_revision", "unspecified")
                        ),
                    )

                context = CivilizationBenchmarkContext(
                    assignment=assignment,
                    probe=probe,
                    grouped_runner=_grouped_runner,
                )
                result = await asyncio.wait_for(
                    execute_civilization_benchmark(recipe, context),
                    timeout=timeout_seconds,
                )
            else:
                recipe = CivilizationBenchmarkRecipe(
                    scenario_id=item.scenario_id,
                    lane=item.lane,
                    profile=item.profile,
                    seed=item.seed,
                    arm_id=item.arm_id,
                )
                execution_context = GenerationalExecutionContext(
                    artifact_root=(
                        store.root
                        / "archives"
                        / item.scenario_id
                        / item.lane.value
                        / f"s{item.seed}"
                    ),
                    source_identity=dict(source_identity),
                    recipe=_execution_recipe(item),
                    factories=RunnerDependencyFactories(),
                    attempt_id=(
                        f"{item.scenario_id}-{item.lane.value}-s{item.seed}"
                    ),
                )
                context = CivilizationBenchmarkContext(
                    assignment=assignment,
                    execution_context=execution_context,
                    probe=probe,
                    arbiter=(
                        _case_arbiter(
                            item.scenario_id,
                            config,
                            run_id=assignment.run_id,
                        )
                        if item.lane is V3BenchmarkLane.MECHANISM
                        else None
                    ),
                    required_milestone_ids=(
                        _case_required_milestones(item.scenario_id, config)
                        if item.lane is V3BenchmarkLane.MECHANISM
                        else ()
                    ),
                )
                result = await asyncio.wait_for(
                    execute_civilization_benchmark(recipe, context),
                    timeout=timeout_seconds,
                )
        except TimeoutError:
            result = _timed_out_result(item, config)
            _LOG.warning(
                "benchmark_attempt_timed_out scenario_id=%s arm_id=%s",
                item.scenario_id,
                item.arm_id,
            )
        document = build_run_document(
            scenario_id=item.scenario_id,
            lane=item.lane,
            profile=item.profile,
            arm_id=item.arm_id,
            seed=item.seed,
            source_identity=dict(source_identity),
            config_fingerprint=runner_config_fingerprint(config),
            recipe={
                "recipe_id": BENCHMARK_RECIPE_ID,
                "version": "1",
                "scenario_id": item.scenario_id,
                "lane": item.lane.value,
                "profile": item.profile.value,
                "arm_id": item.arm_id,
            },
            run_id=assignment.run_id.value,
            result=result,
        )
        documents.append(document)
        references.append(store.publish_run(document))
    required = tuple((item.scenario_id, item.lane.value) for item in items)
    store.publish_suite(
        source_identity=source_identity,
        run_references=tuple(references),
        required=required,
    )
    return tuple(documents)


async def _execute_visual_attempt(
    item: BenchmarkSelectionItem,
    assignment: ExperimentAssignment,
    probe: BenchmarkBoundaryProbe,
    *,
    store_root: Path,
    source_identity: Mapping[str, object],
) -> V3BenchmarkRunResult:
    from experiments.civilization_benchmark_evidence import evaluate_event_journal
    from experiments.generational_archive import GenerationalExecutionRecipe
    from experiments.generational_execution import (
        PLAIN_RECIPE_ID,
        execute_generational_assignment,
    )

    context = GenerationalExecutionContext(
        artifact_root=store_root / "archives",
        source_identity=dict(source_identity),
        recipe=GenerationalExecutionRecipe(
            recipe_id=PLAIN_RECIPE_ID, version="1", params={}
        ),
        factories=RunnerDependencyFactories(),
        attempt_id=f"{item.scenario_id}-{item.arm_id}",
        boundary_observer=probe,
    )
    arm = await execute_generational_assignment(assignment, context)
    runner_result = arm.runner_result
    horizon = assignment.runner_config.stop_policy.max_ticks or 1
    check = evaluate_event_journal(probe)
    complete = (
        runner_result.ticks_committed == horizon
        and check.status.value == "pass"
        and not runner_stop_is_failure(runner_result.stop_reason)
    )
    return V3BenchmarkRunResult(
        scenario_id=item.scenario_id,
        lane=item.lane,
        execution_status=(
            V3BenchmarkExecutionStatus.COMPLETED
            if not runner_stop_is_failure(runner_result.stop_reason)
            else V3BenchmarkExecutionStatus.FAILED
        ),
        declared_horizon=horizon,
        ticks_committed=runner_result.ticks_committed,
        coverage=V3BenchmarkCoverage.EXERCISED,
        evidence=(
            V3BenchmarkEvidenceAvailability.COMPLETE
            if complete
            else V3BenchmarkEvidenceAvailability.PARTIAL
        ),
        phenomenon=V3BenchmarkPhenomenon.UNKNOWN,
        checks=(check,),
    )


def _execution_recipe(
    item: BenchmarkSelectionItem,
) -> GenerationalExecutionRecipe:
    return GenerationalExecutionRecipe(
        recipe_id=BENCHMARK_RECIPE_ID,
        version="1",
        params={
            "scenario_id": item.scenario_id,
            "lane": item.lane.value,
            "profile": item.profile.value,
            "command_plan_id": None,
            "command_plan_version": None,
        },
    )


def _timed_out_result(
    item: BenchmarkSelectionItem, config: object
) -> V3BenchmarkRunResult:
    horizon = getattr(getattr(config, "stop_policy", None), "max_ticks", None)
    return V3BenchmarkRunResult(
        scenario_id=item.scenario_id,
        lane=item.lane,
        execution_status=V3BenchmarkExecutionStatus.TIMED_OUT,
        declared_horizon=int(horizon) if horizon else 1,
        ticks_committed=0,
        coverage=V3BenchmarkCoverage.NOT_EXERCISED,
        evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
        phenomenon=V3BenchmarkPhenomenon.UNKNOWN,
        checks=(),
        publication_status="not_requested",
    )


__all__ = [
    "BenchmarkCompositionError",
    "BenchmarkSelectionItem",
    "execute_selection",
]
