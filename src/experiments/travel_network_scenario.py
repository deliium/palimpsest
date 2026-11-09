"""Off-gate experiment ``travel_network@1``.

Control keeps the travel-network channel inert; treatment activates the owned
``infrastructure_networks`` context together with a regions spec so derived
route conditions, movement enforcement, and owner beliefs can be observed.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from experiments.infrastructure_networks_scenario import (
    infrastructure_networks_scenario,
)
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.runner_models import SimulationRunnerConfig, V3CapabilityFlags
from world.environment import scarcity_scenario_dynamics
from world.regions import RegionsMigrationSpec

__all__ = ["TRAVEL_NETWORK_EXPERIMENT_ID", "travel_network_scenario"]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.travel_network_scenario")

TRAVEL_NETWORK_EXPERIMENT_ID: Final[str] = "travel_network@1"


def _with_regions(
    config: SimulationRunnerConfig,
    regions: RegionsMigrationSpec | None,
) -> SimulationRunnerConfig:
    if regions is None:
        raise ValueError("travel_network_requires_regions")
    flags = replace(config.v3_capability_flags, multi_polity_migration=True)
    return replace(
        config,
        v3_capability_flags=flags,
        regions_migration=regions,
        environmental_dynamics=scarcity_scenario_dynamics(),
    )


def travel_network_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 24,
) -> ExperimentDefinition:
    """Control vs treatment for objective route conditions and beliefs."""
    if base.regions_migration is None:
        raise ValueError("travel_network_requires_regions")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    infrastructure = infrastructure_networks_scenario(
        replace(
            base,
            regions_migration=None,
            v3_capability_flags=V3CapabilityFlags(),
        ),
        seed_matrix=matrix,
        max_ticks=max_ticks,
    )
    conditions = tuple(
        ExperimentCondition(
            condition_id=(
                "travel-network-control"
                if condition.condition_id == "infra-channel-off"
                else "travel-network-treatment"
            ),
            label_code=(
                "travel_network_control"
                if condition.condition_id == "infra-channel-off"
                else "travel_network_treatment"
            ),
            runner_config=_with_regions(
                condition.runner_config, base.regions_migration
            ),
        )
        for condition in infrastructure.conditions
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s off_gate=true",
        TRAVEL_NETWORK_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=TRAVEL_NETWORK_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{TRAVEL_NETWORK_EXPERIMENT_ID}-world",
    )
