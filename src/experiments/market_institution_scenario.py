"""Off-gate experiment ``market_institutions@1``.

Control and treatment share exchange/valuation and regional seams; only the
owned ``markets_credit`` flag differs. No price, money, market object, or
scheduled exchange is installed.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    ResourceExchangeProfileSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    SubjectiveValuationSpec,
)

__all__ = ["MARKET_INSTITUTIONS_EXPERIMENT_ID", "market_institution_scenario"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.market_institution_scenario"
)

MARKET_INSTITUTIONS_EXPERIMENT_ID: Final[str] = "market_institutions@1"


def _with_exchange(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    return replace(
        config,
        resource_exchange_profile=ResourceExchangeProfileSpec(
            policy_id="resource-exchange-profile-v1",
            acceptance_window_ticks=8,
        ),
        subjective_valuation=SubjectiveValuationSpec(
            policy_id="subjective-valuation-v1",
            horizon_ticks=8,
            max_bundle=2,
        ),
    )


def _with_flag(
    config: SimulationRunnerConfig, *, enabled: bool
) -> SimulationRunnerConfig:
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=replace(
            config.v4_capability_flags, markets_credit=enabled
        ),
    )


def market_institution_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 96,
) -> ExperimentDefinition:
    """Control vs treatment over existing exchange and regional seams."""

    if base.regions_migration is None:
        _LOG.error(
            "market_institutions_scenario_invalid reason_code=requires_regions"
        )
        raise ValueError("market_institutions_requires_regions")
    if max_ticks < 96:
        raise ValueError("market_institutions_requires_three_windows")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    shared = replace(
        _with_exchange(base),
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
    )
    conditions = tuple(
        ExperimentCondition(
            condition_id=(
                "market-institutions-control"
                if index == 0
                else "market-institutions-treatment"
            ),
            label_code=(
                "market_institutions_control"
                if index == 0
                else "market_institutions_treatment"
            ),
            runner_config=_with_flag(shared, enabled=index == 1),
        )
        for index in range(2)
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s off_gate=true",
        MARKET_INSTITUTIONS_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=MARKET_INSTITUTIONS_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{MARKET_INSTITUTIONS_EXPERIMENT_ID}-world",
    )
