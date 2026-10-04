"""Benchmark builders for scenarios 8–14 (territory through rumor/narrative)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Final

from experiments.benchmark_scenarios._common import filter_conditions, with_seed_matrix
from experiments.benchmark_suite import (
    BENCH_08_TERRITORIAL,
    BENCH_09_SOCIAL_CLUSTERS,
    BENCH_10_NORMS,
    BENCH_11_CONVENTIONS,
    BENCH_12_ARTIFACTS,
    BENCH_13_NAMING_DRIFT,
    BENCH_14_RUMOR_NARRATIVE,
)
from experiments.catalog import (
    experiment_aa_emergent_naming,
    experiment_ab_cultural_narratives,
    experiment_v_territorial_claims,
    experiment_w_emergent_groups,
    experiment_x_social_norms,
    experiment_y_social_conventions,
    experiment_z_external_artifacts,
)
from experiments.models import ExperimentDefinition, ExperimentSeedMatrix
from simulation.runner_models import SimulationRunnerConfig

from . import BenchmarkBuildResult, register_benchmark_builder

_LOG: Final[logging.Logger] = logging.getLogger("experiments.benchmark_scenarios")

_CatalogBuilder = Callable[..., ExperimentDefinition]


def _seed_catalog_build(
    base: SimulationRunnerConfig,
    *,
    catalog_builder: _CatalogBuilder,
    condition_ids: tuple[str, ...],
    scenario_id: str,
    seed_matrix: ExperimentSeedMatrix | None,
    matrix_factors: tuple[str, ...],
) -> BenchmarkBuildResult:
    seed = base.seed if seed_matrix is None else seed_matrix.seeds[0]
    max_ticks = min(base.stop_policy.max_ticks, 64)
    definition = catalog_builder(seed=seed, max_ticks=max_ticks)
    definition = with_seed_matrix(definition, seed_matrix)
    definition = filter_conditions(
        definition,
        condition_ids,
        experiment_id=scenario_id,
        seed_matrix=seed_matrix or definition.seed_matrix,
    )
    _LOG.debug(
        "bench_culture_built scenario_id=%s condition_ids=%s",
        scenario_id,
        ",".join(condition_ids),
    )
    return BenchmarkBuildResult(
        scenario_id=scenario_id,
        definition=definition,
        matrix_factors=matrix_factors,
    )


def build_bench_08_territorial(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    return _seed_catalog_build(
        base,
        catalog_builder=experiment_v_territorial_claims,
        condition_ids=("v-scarce", "v-abundant"),
        scenario_id=BENCH_08_TERRITORIAL,
        seed_matrix=seed_matrix,
        matrix_factors=("resource_scarcity",),
    )


def build_bench_09_social_clusters(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    return _seed_catalog_build(
        base,
        catalog_builder=experiment_w_emergent_groups,
        condition_ids=("w-enabled", "w-disabled"),
        scenario_id=BENCH_09_SOCIAL_CLUSTERS,
        seed_matrix=seed_matrix,
        matrix_factors=("group_formation",),
    )


def build_bench_10_norms(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    return _seed_catalog_build(
        base,
        catalog_builder=experiment_x_social_norms,
        condition_ids=("x-enabled", "x-disabled"),
        scenario_id=BENCH_10_NORMS,
        seed_matrix=seed_matrix,
        matrix_factors=("social_norms",),
    )


def build_bench_11_conventions(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    return _seed_catalog_build(
        base,
        catalog_builder=experiment_y_social_conventions,
        condition_ids=("y-enabled", "y-disabled"),
        scenario_id=BENCH_11_CONVENTIONS,
        seed_matrix=seed_matrix,
        matrix_factors=("social_conventions",),
    )


def build_bench_12_artifacts(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    return _seed_catalog_build(
        base,
        catalog_builder=experiment_z_external_artifacts,
        condition_ids=("artifact_channel", "memory_only"),
        scenario_id=BENCH_12_ARTIFACTS,
        seed_matrix=seed_matrix,
        matrix_factors=("external_artifacts",),
    )


def build_bench_13_naming_drift(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    return _seed_catalog_build(
        base,
        catalog_builder=experiment_aa_emergent_naming,
        condition_ids=("aa-enabled", "aa-disabled"),
        scenario_id=BENCH_13_NAMING_DRIFT,
        seed_matrix=seed_matrix,
        matrix_factors=("semantic_naming",),
    )


def build_bench_14_rumor_narrative(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    return _seed_catalog_build(
        base,
        catalog_builder=experiment_ab_cultural_narratives,
        condition_ids=("ab-enabled", "ab-disabled"),
        scenario_id=BENCH_14_RUMOR_NARRATIVE,
        seed_matrix=seed_matrix,
        matrix_factors=("cultural_narrative",),
    )


def register_culture_scenario_builders() -> None:
    register_benchmark_builder(BENCH_08_TERRITORIAL, build_bench_08_territorial)
    register_benchmark_builder(BENCH_09_SOCIAL_CLUSTERS, build_bench_09_social_clusters)
    register_benchmark_builder(BENCH_10_NORMS, build_bench_10_norms)
    register_benchmark_builder(BENCH_11_CONVENTIONS, build_bench_11_conventions)
    register_benchmark_builder(BENCH_12_ARTIFACTS, build_bench_12_artifacts)
    register_benchmark_builder(BENCH_13_NAMING_DRIFT, build_bench_13_naming_drift)
    register_benchmark_builder(BENCH_14_RUMOR_NARRATIVE, build_bench_14_rumor_narrative)


register_culture_scenario_builders()
