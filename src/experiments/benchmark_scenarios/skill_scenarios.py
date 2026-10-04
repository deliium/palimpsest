"""Benchmark builders for scenario 7 (skill learning + specialization)."""

from __future__ import annotations

import logging
from typing import Final

from experiments.benchmark_scenarios._common import with_seed_matrix
from experiments.benchmark_suite import BENCH_07_SKILL_SPECIALIZATION
from experiments.catalog import experiment_r_skill_learning, experiment_t_skill_specialization
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.runner_models import SimulationRunnerConfig

from . import BenchmarkBuildResult, register_benchmark_builder

_LOG: Final[logging.Logger] = logging.getLogger("experiments.benchmark_scenarios")


def build_bench_07_skill_specialization(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    """Wrap Experiments R + T enabled/disabled peers on a shared world/seed."""
    r_def = experiment_r_skill_learning(base, seed_matrix=seed_matrix)
    t_def = experiment_t_skill_specialization(base, seed_matrix=seed_matrix)
    by_id = {
        item.condition_id: item
        for item in (*r_def.conditions, *t_def.conditions)
    }
    ordered_ids = ("r-enabled", "t-enabled", "r-disabled", "t-disabled")
    missing = [item for item in ordered_ids if item not in by_id]
    if missing:
        raise ValueError(f"missing_condition_ids:{','.join(missing)}")
    conditions: tuple[ExperimentCondition, ...] = tuple(by_id[item] for item in ordered_ids)
    definition = ExperimentDefinition(
        experiment_id=BENCH_07_SKILL_SPECIALIZATION,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=seed_matrix or r_def.seed_matrix,
        conditions=conditions,
        paired_world_group=f"{BENCH_07_SKILL_SPECIALIZATION}-world",
    )
    definition = with_seed_matrix(definition, seed_matrix)
    _LOG.debug(
        "bench_07_modes skill=%s teaching=%s",
        by_id["r-enabled"].runner_config.agents[0].cognition.skill_learning_mode.value,
        by_id["t-enabled"].runner_config.agents[0].cognition.teaching_interaction_mode.value,
    )
    return BenchmarkBuildResult(
        scenario_id=BENCH_07_SKILL_SPECIALIZATION,
        definition=definition,
        matrix_factors=("skill_learning", "teaching"),
    )


def register_skill_scenario_builders() -> None:
    register_benchmark_builder(
        BENCH_07_SKILL_SPECIALIZATION, build_bench_07_skill_specialization
    )


register_skill_scenario_builders()
