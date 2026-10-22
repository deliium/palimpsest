"""Experiment BL: real regional world with a generational entry calendar."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
    require_stochastic,
)
from experiments.regional_migration_scenario import (
    regional_migration_arbiter,
    regional_migration_scenario,
)
from simulation.generational_models import GenerationalRunSpec
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V55,
    MortalityMode,
    PopulationLifecycleSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V3CapabilityFlags,
    default_lifespan_distribution_spec,
)
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.generational_runner_scenario"
)

EXPERIMENT_ID: Final[str] = "generational_runner@1"
_SPAWN_LOCATIONS: Final[tuple[str, ...]] = (
    "loc-origin",
    "loc-spring",
    "loc-grain",
    "loc-remote",
)


def _lifecycle(*, enabled: bool, lifespan_ticks: int) -> PopulationLifecycleSpec:
    return PopulationLifecycleSpec(
        lifespan_ticks=lifespan_ticks,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 2),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 5),
            LifecycleStageThreshold(
                LifecycleStageId("adult"), lifespan_ticks - 1
            ),
        ),
        dependent_until_stage=LifecycleStageId("juvenile"),
        demographic_policy_id=(
            "generational_interval_entry" if enabled else "disabled"
        ),
        demographic_policy_params=(
            {
                "interval_ticks": 2,
                "entries_per_interval": 1,
                "generation_length_ticks": 4,
                "name_prefix": "entrant",
                "cohort_id_prefix": "cohort",
                "spawn_location_ids": list(_SPAWN_LOCATIONS),
            }
            if enabled
            else {}
        ),
        max_population=8,
        natural_death_on_lifespan=True,
        lifespan_distribution=default_lifespan_distribution_spec(),
    )


def _config(
    base: SimulationRunnerConfig,
    *,
    enabled: bool,
    max_ticks: int,
) -> SimulationRunnerConfig:
    if base.regions_migration is None:
        raise ValueError("BL requires the AY regional configuration")
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V55,
        mortality_mode=MortalityMode.ENABLED,
        stop_policy=RunnerStopPolicy(
            max_ticks=max_ticks, stop_on_all_agents_terminal=False
        ),
        v3_capability_flags=V3CapabilityFlags(
            generational_population=True,
            multi_polity_migration=True,
        ),
        population_lifecycle=_lifecycle(
            enabled=enabled, lifespan_ticks=min(12, max_ticks + 4)
        ),
        new_agent_initialization=default_new_agent_initialization_spec(),
        generational_run=GenerationalRunSpec(
            max_generation_index=None,
            stop_on_extinction=False,
            criterion_cadence_ticks=1,
        ),
    )


def generational_runner_scenario(
    *,
    seed: int = 23,
    max_ticks: int = 12,
    base: SimulationRunnerConfig | None = None,
) -> ExperimentDefinition:
    """Build BL's single-cohort, unassisted, and contact conditions."""
    if max_ticks < 4:
        raise ValueError("BL requires at least four ticks")
    if base is None:
        source = regional_migration_scenario(seed=seed, max_ticks=max_ticks)
        by_id = {item.condition_id: item for item in source.conditions}
        seed_config = by_id["ay-accurate-evidence"].runner_config
        active_seed = seed
        stochastic = require_stochastic("regional-migration-ay")
    else:
        if type(base) is not SimulationRunnerConfig:
            raise TypeError("base must be SimulationRunnerConfig or None")
        seed_config = base
        active_seed = base.seed
        stochastic = base.stochastic_identity
    single = _config(seed_config, enabled=False, max_ticks=max_ticks)
    unassisted = _config(seed_config, enabled=True, max_ticks=max_ticks)
    contact = replace(unassisted, stochastic_identity=stochastic)
    conditions = (
        ("bl-single-cohort", "generational_demography_disabled", single),
        (
            "bl-generational-unassisted",
            "generational_entries_unassisted",
            replace(unassisted, seed=active_seed),
        ),
        (
            "bl-generational-contact",
            "generational_entries_contact",
            replace(contact, seed=active_seed),
        ),
    )
    _LOG.info(
        "generational_runner_experiment_built arms=%s ticks=%s spawns=%s",
        len(conditions),
        max_ticks,
        len(_SPAWN_LOCATIONS),
    )
    return ExperimentDefinition(
        experiment_id=EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=ExperimentSeedMatrix(seeds=(active_seed,)),
        conditions=tuple(
            ExperimentCondition(
                condition_id=condition_id,
                label_code=label,
                runner_config=config,
            )
            for condition_id, label, config in conditions
        ),
        paired_world_group="generational-runner-bl-world",
    )


def generational_runner_arbiter(
    condition_id: str, config: SimulationRunnerConfig
) -> object | None:
    """Only the contact condition receives the existing AY diagnostic treatment."""
    if condition_id != "bl-generational-contact":
        return None
    return regional_migration_arbiter("ay-visit-return", config)


__all__ = [
    "EXPERIMENT_ID",
    "generational_runner_arbiter",
    "generational_runner_scenario",
]
