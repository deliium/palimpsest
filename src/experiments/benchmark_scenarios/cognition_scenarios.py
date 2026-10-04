"""Benchmark builders for scenarios 1–3 (planning, memory, reflection)."""

from __future__ import annotations

import logging
from typing import Final

from experiments.benchmark_scenarios._common import filter_conditions, with_seed_matrix

from . import BenchmarkBuildResult, register_benchmark_builder
from experiments.benchmark_suite import (
    BENCH_01_SEASONAL_PLANNING,
    BENCH_02_MEMORY_INTERFERENCE,
    BENCH_03_REFLECTION_REVISION,
)
from experiments.catalog import (
    experiment_a_memory,
    experiment_g_reflection,
    experiment_u_seasonal_scarcity,
)
from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import SimulationRunnerConfig

_LOG: Final[logging.Logger] = logging.getLogger("experiments.benchmark_scenarios")


def build_bench_01_seasonal_planning(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    """Wrap Experiment U ``u-learned`` / ``u-naive`` (LONG_TERM goals already on arms)."""
    seed = base.seed if seed_matrix is None else seed_matrix.seeds[0]
    max_ticks = min(base.stop_policy.max_ticks, 64)
    definition = experiment_u_seasonal_scarcity(seed=seed, max_ticks=max_ticks)
    definition = with_seed_matrix(definition, seed_matrix)
    definition = filter_conditions(
        definition,
        ("u-learned", "u-naive"),
        experiment_id=BENCH_01_SEASONAL_PLANNING,
    )
    _LOG.debug(
        "bench_01_modes predictive_world_model=%s initial_goals=%s",
        definition.conditions[0].runner_config.capability_flags.predictive_world_model,
        len(definition.conditions[0].runner_config.agents[0].initial_goals),
    )
    return BenchmarkBuildResult(
        scenario_id=BENCH_01_SEASONAL_PLANNING,
        definition=definition,
        matrix_factors=("seasonality", "predictive_world_model"),
    )


def build_bench_02_memory_interference(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    """Wrap Experiment A reconstructive-V2 vs reconstructive (shared seed)."""
    full = experiment_a_memory(base, seed_matrix=seed_matrix)
    definition = filter_conditions(
        full,
        ("a-reconstructive-v2", "a-reconstructive"),
        experiment_id=BENCH_02_MEMORY_INTERFERENCE,
        seed_matrix=seed_matrix or full.seed_matrix,
    )
    _LOG.debug(
        "bench_02_modes memory_modes=%s",
        ",".join(
            item.runner_config.agents[0].cognition.memory_mode.value
            for item in definition.conditions
        ),
    )
    return BenchmarkBuildResult(
        scenario_id=BENCH_02_MEMORY_INTERFERENCE,
        definition=definition,
        matrix_factors=("memory_type",),
    )


def build_bench_03_reflection_revision(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    """Wrap Experiment G deterministic vs disabled reflection."""
    full = experiment_g_reflection(base, seed_matrix=seed_matrix)
    definition = filter_conditions(
        full,
        ("g-deterministic", "g-disabled"),
        experiment_id=BENCH_03_REFLECTION_REVISION,
        seed_matrix=seed_matrix or full.seed_matrix,
    )
    _LOG.debug(
        "bench_03_modes reflection_modes=%s",
        ",".join(
            item.runner_config.agents[0].cognition.reflection_mode.value
            for item in definition.conditions
        ),
    )
    return BenchmarkBuildResult(
        scenario_id=BENCH_03_REFLECTION_REVISION,
        definition=definition,
        matrix_factors=("reflection",),
    )


def register_cognition_scenario_builders() -> None:
    """Install builders for bench-01…bench-03."""
    register_benchmark_builder(BENCH_01_SEASONAL_PLANNING, build_bench_01_seasonal_planning)
    register_benchmark_builder(
        BENCH_02_MEMORY_INTERFERENCE, build_bench_02_memory_interference
    )
    register_benchmark_builder(
        BENCH_03_REFLECTION_REVISION, build_bench_03_reflection_revision
    )


register_cognition_scenario_builders()
