"""Benchmark builder for scenario 15 (cognitive architecture matrix)."""

from __future__ import annotations

import logging
from typing import Final

from experiments.benchmark_scenarios._common import with_seed_matrix
from experiments.benchmark_suite import BENCH_15_ARCHITECTURE_MATRIX
from experiments.catalog import experiment_ac_cognitive_architectures
from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import SimulationRunnerConfig
from simulation.runner_serialization import scenario_fingerprint

from . import BenchmarkBuildResult, register_benchmark_builder

_LOG: Final[logging.Logger] = logging.getLogger("experiments.benchmark_scenarios")


def build_bench_15_architecture_matrix(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    """Wrap Experiment AC ``ac-<architecture_id>`` arms on a shared world/seed."""
    definition = experiment_ac_cognitive_architectures(base, seed_matrix=seed_matrix)
    definition = with_seed_matrix(definition, seed_matrix)
    # Re-stamp experiment_id for the suite while keeping AC arm condition ids.
    from experiments.models import EXPERIMENT_SCHEMA_VERSION, ExperimentDefinition

    definition = ExperimentDefinition(
        experiment_id=BENCH_15_ARCHITECTURE_MATRIX,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=definition.seed_matrix,
        conditions=definition.conditions,
        paired_world_group=f"{BENCH_15_ARCHITECTURE_MATRIX}-world",
    )
    fingerprints = {
        scenario_fingerprint(item.runner_config) for item in definition.conditions
    }
    if len(fingerprints) != 1:
        raise ValueError("architecture_arms_require_identical_scenario")
    _LOG.debug(
        "bench_15_modes architecture_count=%s schema=%s",
        len(definition.conditions),
        definition.conditions[0].runner_config.schema_version,
    )
    return BenchmarkBuildResult(
        scenario_id=BENCH_15_ARCHITECTURE_MATRIX,
        definition=definition,
        matrix_factors=("architecture",),
    )


def register_architecture_scenario_builders() -> None:
    register_benchmark_builder(
        BENCH_15_ARCHITECTURE_MATRIX, build_bench_15_architecture_matrix
    )


register_architecture_scenario_builders()
