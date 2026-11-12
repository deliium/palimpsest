"""Off-gate experiment ``emergent_prices@1``.

Four arms differ only by declared seams: ``markets_credit``, the V3-18
``subjective_valuation`` spec, the V3-19 ``resource_exchange_profile`` spec, and
an optional communication-strategy treatment. No command, event, schema, or
price object is added.
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
    RESOURCE_EXCHANGE_PROFILE_POLICY_ID,
    RUNNER_SCHEMA_VERSION_V56,
    SUBJECTIVE_VALUATION_POLICY_ID,
    CommunicationStrategyMode,
    ResourceExchangeProfileSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    SubjectiveValuationSpec,
)

__all__ = ["EMERGENT_PRICES_EXPERIMENT_ID", "emergent_prices_scenario"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.emergent_prices_scenario"
)

EMERGENT_PRICES_EXPERIMENT_ID: Final[str] = "emergent_prices@1"


def _exchange(
    config: SimulationRunnerConfig, *, enabled: bool
) -> SimulationRunnerConfig:
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        resource_exchange_profile=(
            ResourceExchangeProfileSpec(
                policy_id=RESOURCE_EXCHANGE_PROFILE_POLICY_ID,
                acceptance_window_ticks=32,
            )
            if enabled
            else None
        ),
        subjective_valuation=(
            SubjectiveValuationSpec(
                policy_id=SUBJECTIVE_VALUATION_POLICY_ID,
                horizon_ticks=8,
                max_bundle=8,
            )
            if enabled
            else None
        ),
    )


def _markets(
    config: SimulationRunnerConfig, *, enabled: bool
) -> SimulationRunnerConfig:
    return replace(
        config,
        v4_capability_flags=replace(
            config.v4_capability_flags, markets_credit=enabled
        ),
    )


def _quotes(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    return replace(
        config,
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    communication_strategy_mode=(
                        CommunicationStrategyMode.DETERMINISTIC
                    ),
                ),
            )
            for agent in config.agents
        ),
    )


def emergent_prices_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 96,
) -> ExperimentDefinition:
    """Four arms over existing exchange, valuation, and market seams."""

    if max_ticks < 96:
        raise ValueError("emergent_prices_requires_three_windows")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    stop = RunnerStopPolicy(max_ticks=max_ticks)
    flag_off = replace(_exchange(base, enabled=False), stop_policy=stop)
    valuation_only = replace(_exchange(base, enabled=True), stop_policy=stop)
    prices_on = replace(_markets(valuation_only, enabled=True), stop_policy=stop)
    prices_quotes = replace(_quotes(prices_on), stop_policy=stop)
    conditions = (
        ExperimentCondition(
            condition_id="ep-flag-off",
            label_code="emergent_prices_flag_off",
            runner_config=flag_off,
        ),
        ExperimentCondition(
            condition_id="ep-valuation-only",
            label_code="emergent_prices_valuation_only",
            runner_config=valuation_only,
        ),
        ExperimentCondition(
            condition_id="ep-prices-on",
            label_code="emergent_prices_on",
            runner_config=prices_on,
        ),
        ExperimentCondition(
            condition_id="ep-prices-quotes",
            label_code="emergent_prices_quotes",
            runner_config=prices_quotes,
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s off_gate=true",
        EMERGENT_PRICES_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=EMERGENT_PRICES_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{EMERGENT_PRICES_EXPERIMENT_ID}-world",
    )
