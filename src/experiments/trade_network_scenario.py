"""Off-gate experiment ``trade_networks@1``.

Control and treatment keep the travel-network channel and add owner-scoped
exchange/valuation specs. No centralized routing, price, money, or new flag is
added.
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
from experiments.travel_network_scenario import travel_network_scenario
from simulation.runner_models import (
    ResourceExchangeProfileSpec,
    SimulationRunnerConfig,
    SubjectiveValuationSpec,
)

__all__ = ["TRADE_NETWORKS_EXPERIMENT_ID", "trade_network_scenario"]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.trade_network_scenario")

TRADE_NETWORKS_EXPERIMENT_ID: Final[str] = "trade_networks@1"


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


def trade_network_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 48,
) -> ExperimentDefinition:
    """Control vs treatment over existing travel and exchange seams."""
    if base.regions_migration is None:
        raise ValueError("trade_networks_requires_regions")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    travel = travel_network_scenario(base, seed_matrix=matrix, max_ticks=max_ticks)
    conditions = tuple(
        ExperimentCondition(
            condition_id=(
                "trade-networks-control"
                if condition.condition_id == "travel-network-control"
                else "trade-networks-treatment"
            ),
            label_code=(
                "trade_networks_control"
                if condition.condition_id == "travel-network-control"
                else "trade_networks_treatment"
            ),
            runner_config=_with_exchange(condition.runner_config),
        )
        for condition in travel.conditions
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s off_gate=true",
        TRADE_NETWORKS_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=TRADE_NETWORKS_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{TRADE_NETWORKS_EXPERIMENT_ID}-world",
    )
