"""Benchmark builders for scenarios 4–6 (ToM detectability, deception+reputation)."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from experiments.benchmark_scenarios._common import filter_conditions, with_seed_matrix
from experiments.benchmark_suite import (
    BENCH_04_TOM_SOCIAL_FAILURE,
    BENCH_05_TOM_COOPERATION,
    BENCH_06_DECEPTION_REPUTATION,
)
from experiments.catalog import experiment_l_theory_of_mind
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V9,
    RUNNER_SCHEMA_VERSION_V10,
    CommunicationStrategyMode,
    ReputationMode,
    SimulationRunnerConfig,
)

from . import BenchmarkBuildResult, register_benchmark_builder

_LOG: Final[logging.Logger] = logging.getLogger("experiments.benchmark_scenarios")


def _with_strategy_reputation(
    base: SimulationRunnerConfig,
    *,
    strategy: CommunicationStrategyMode,
    reputation: ReputationMode,
    schema_version: str,
) -> SimulationRunnerConfig:
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                communication_strategy_mode=strategy,
                reputation_mode=reputation,
            ),
        )
        for agent in base.agents
    )
    return replace(base, agents=agents, schema_version=schema_version)


def _build_tom_pair(
    base: SimulationRunnerConfig,
    *,
    scenario_id: str,
    seed_matrix: ExperimentSeedMatrix | None,
    matrix_factors: tuple[str, ...],
) -> BenchmarkBuildResult:
    full = experiment_l_theory_of_mind(base, seed_matrix=seed_matrix)
    definition = filter_conditions(
        full,
        ("l-enabled", "l-disabled"),
        experiment_id=scenario_id,
        seed_matrix=seed_matrix or full.seed_matrix,
    )
    enabled = definition.conditions[0].runner_config
    _LOG.debug(
        "bench_tom_modes scenario_id=%s advanced_social_inference=%s",
        scenario_id,
        enabled.capability_flags.advanced_social_inference,
    )
    return BenchmarkBuildResult(
        scenario_id=scenario_id,
        definition=definition,
        matrix_factors=matrix_factors,
    )


def build_bench_04_tom_social_failure(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    """Shared-world ToM detectability for mismatch indicators when present."""
    return _build_tom_pair(
        base,
        scenario_id=BENCH_04_TOM_SOCIAL_FAILURE,
        seed_matrix=seed_matrix,
        matrix_factors=("tom",),
    )


def build_bench_05_tom_cooperation(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    """Same L world/seed matrix as bench-04; cooperation detectability when present."""
    return _build_tom_pair(
        base,
        scenario_id=BENCH_05_TOM_COOPERATION,
        seed_matrix=seed_matrix,
        matrix_factors=("tom", "cooperation"),
    )


def build_bench_06_deception_reputation(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    """Compose strategy+reputation on runner-config-v10 with strategy-only / disabled controls."""
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    strategy_reputation = _with_strategy_reputation(
        base,
        strategy=CommunicationStrategyMode.DETERMINISTIC,
        reputation=ReputationMode.DETERMINISTIC,
        schema_version=RUNNER_SCHEMA_VERSION_V10,
    )
    strategy_only = _with_strategy_reputation(
        base,
        strategy=CommunicationStrategyMode.DETERMINISTIC,
        reputation=ReputationMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V9,
    )
    q_disabled = _with_strategy_reputation(
        base,
        strategy=CommunicationStrategyMode.DISABLED,
        reputation=ReputationMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
    )
    definition = ExperimentDefinition(
        experiment_id=BENCH_06_DECEPTION_REPUTATION,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=(
            ExperimentCondition(
                condition_id="o-strategy-reputation",
                label_code="strategy_and_reputation_deterministic",
                runner_config=strategy_reputation,
            ),
            ExperimentCondition(
                condition_id="o-strategy-only",
                label_code="strategy_deterministic_reputation_disabled",
                runner_config=strategy_only,
            ),
            ExperimentCondition(
                condition_id="q-disabled",
                label_code="reputation_disabled",
                runner_config=q_disabled,
            ),
        ),
        paired_world_group=f"{BENCH_06_DECEPTION_REPUTATION}-world",
    )
    definition = with_seed_matrix(definition, seed_matrix)
    _LOG.debug(
        "bench_06_modes strategy=%s reputation=%s",
        strategy_reputation.agents[0].cognition.communication_strategy_mode.value,
        strategy_reputation.agents[0].cognition.reputation_mode.value,
    )
    return BenchmarkBuildResult(
        scenario_id=BENCH_06_DECEPTION_REPUTATION,
        definition=definition,
        matrix_factors=("communication_strategy", "reputation"),
    )


def register_social_scenario_builders() -> None:
    register_benchmark_builder(
        BENCH_04_TOM_SOCIAL_FAILURE, build_bench_04_tom_social_failure
    )
    register_benchmark_builder(BENCH_05_TOM_COOPERATION, build_bench_05_tom_cooperation)
    register_benchmark_builder(
        BENCH_06_DECEPTION_REPUTATION, build_bench_06_deception_reputation
    )


register_social_scenario_builders()
