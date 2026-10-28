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
from experiments.civilization_benchmark_base import build_v3_benchmark_scenario
from experiments.civilization_benchmark_evidence import BenchmarkBoundaryProbe
from experiments.civilization_benchmark_execution import (
    CivilizationBenchmarkContext,
    CivilizationBenchmarkRecipe,
    execute_civilization_benchmark,
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
from simulation.runner_models import runner_stop_is_failure
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


def _run_id(item: BenchmarkSelectionItem, revision: str) -> RunId:
    suffix = revision[:16] if revision else "unknown"
    return RunId(
        f"v3bench-{item.scenario_id}-{item.lane.value}-{item.arm_id}"
        f"-s{item.seed}-{suffix}"
    )


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
                raise BenchmarkCompositionError("grouped_case_not_supported")
            build = build_v3_benchmark_scenario(
                item.scenario_id,
                seed=item.seed,
                profile=item.profile,
                lane=item.lane,
            )
            config = next(arm.config for arm in build.arms if arm.arm_id == item.arm_id)
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
            else:
                recipe = CivilizationBenchmarkRecipe(
                    scenario_id=item.scenario_id,
                    lane=item.lane,
                    profile=item.profile,
                    seed=item.seed,
                    arm_id=item.arm_id,
                )
                context = CivilizationBenchmarkContext(
                    assignment=assignment,
                    execution_context=GenerationalExecutionContext(
                        artifact_root=store.root / "archives",
                        source_identity=dict(source_identity),
                        recipe=_execution_recipe(item),
                        factories=RunnerDependencyFactories(),
                        attempt_id=f"{item.scenario_id}-{item.arm_id}",
                    ),
                    probe=probe,
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
