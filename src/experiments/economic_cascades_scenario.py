"""Off-gate experiment ``economic_cascades@1``.

Three arms share the accepted V56 seam. The baseline arm keeps the supply-chain
channel off and is provably inert; the production arm enables the chain catalog;
the full arm adds infrastructure, regional movement, and route conditions while
keeping mortality enabled so population-loss evidence remains possible.
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
from experiments.supply_chain_scenario import supply_chain_scenario
from experiments.travel_network_scenario import travel_network_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    MortalityMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V4CapabilityFlags,
)
from world.production import ProductionCatalog, example_production_catalog
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)
from world.supply_chain import supply_chain_production_catalog

__all__ = ["ECONOMIC_CASCADES_EXPERIMENT_ID", "economic_cascades_scenario"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.economic_cascades_scenario"
)

ECONOMIC_CASCADES_EXPERIMENT_ID: Final[str] = "economic_cascades@1"


def _with_catalog(
    config: SimulationRunnerConfig, catalog: ProductionCatalog
) -> SimulationRunnerConfig:
    return replace(
        config,
        agents=tuple(
            replace(
                agent,
                cognition=replace(agent.cognition, production_catalog=catalog),
            )
            for agent in config.agents
        ),
    )


def _with_regions(base: SimulationRunnerConfig) -> SimulationRunnerConfig:
    locations = tuple(location.entity_id for location in base.scenario.locations)
    if len(locations) < 2:
        raise ValueError("economic_cascades_requires_two_locations")
    origin, destination = locations[0], locations[1]
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("origin", "Origin"),),
        location_regions=(
            LocationRegion(origin, "origin"),
            LocationRegion(destination, "origin"),
        ),
        routes=(RouteSpec(origin, destination, 2, 3.0),),
        max_arrival_wait_ticks=1,
        residence_min_ticks=4,
        destination_memory_limit=3,
        destination_hop_limit=2,
        cognition_mode=CognitionMode.DETERMINISTIC,
    )
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        regions_migration=spec,
        v3_capability_flags=replace(
            base.v3_capability_flags, multi_polity_migration=True
        ),
    )


def economic_cascades_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 96,
) -> ExperimentDefinition:
    """Three arms over existing production, infrastructure, and route seams."""

    if max_ticks < 96:
        raise ValueError("economic_cascades_min_ticks")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    supply = supply_chain_scenario(base, seed_matrix=matrix, max_ticks=max_ticks)
    production = next(
        condition
        for condition in supply.conditions
        if condition.condition_id == "supply-chain-on"
    )
    baseline = next(
        condition
        for condition in supply.conditions
        if condition.condition_id == "supply-chain-off"
    )
    travel = travel_network_scenario(
        _with_regions(base), seed_matrix=matrix, max_ticks=max_ticks
    )
    full_source = next(
        condition
        for condition in travel.conditions
        if condition.condition_id == "travel-network-treatment"
    )
    chain = supply_chain_production_catalog(example_production_catalog())
    full_config = replace(
        full_source.runner_config,
        mortality_mode=MortalityMode.ENABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v4_capability_flags=replace(
            full_source.runner_config.v4_capability_flags,
            supply_chains=True,
        ),
    )
    full_config = _with_catalog(full_config, chain)
    if full_config.mortality_mode is MortalityMode.DISABLED:
        raise ValueError("economic_cascades_mortality_required")

    conditions = (
        ExperimentCondition(
            condition_id="cascade-baseline",
            label_code="economic_cascades_baseline",
            runner_config=replace(
                baseline.runner_config,
                stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            ),
        ),
        ExperimentCondition(
            condition_id="cascade-production",
            label_code="economic_cascades_production",
            runner_config=replace(
                production.runner_config,
                stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            ),
        ),
        ExperimentCondition(
            condition_id="cascade-full",
            label_code="economic_cascades_full",
            runner_config=full_config,
        ),
    )
    for condition in conditions:
        flags = condition.runner_config.v4_capability_flags
        if not isinstance(flags, V4CapabilityFlags):
            raise ValueError("economic_cascades_invalid_flags")
    _LOG.info(
        "economic_cascades_experiment_registered arms=%s", len(conditions)
    )
    return ExperimentDefinition(
        experiment_id=ECONOMIC_CASCADES_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{ECONOMIC_CASCADES_EXPERIMENT_ID}-world",
    )
