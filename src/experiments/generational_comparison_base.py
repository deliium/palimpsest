"""Canonical generational comparison base and comparability gate."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Final, NoReturn

from experiments.regional_migration_scenario import regional_migration_scenario
from simulation.generational_models import GenerationalRunSpec
from simulation.new_agent_initialization import (
    NewAgentInitializationSpec,
    default_new_agent_initialization_spec,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V55,
    CommunicationStrategyMode,
    MortalityMode,
    PopulationLifecycleSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    SkillLearningMode,
    TeachingInteractionMode,
    V3CapabilityFlags,
    WorldScenarioSpec,
    default_lifespan_distribution_spec,
    example_cultural_feature_provenance_spec,
)
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.generational_comparison_base"
)

_CANONICAL_SPAWNS: Final[tuple[str, ...]] = (
    "loc-origin",
    "loc-spring",
    "loc-grain",
    "loc-remote",
)


def _spawn_locations(scenario: WorldScenarioSpec) -> tuple[str, ...]:
    known = tuple(location.entity_id.value for location in scenario.locations)
    if not known:
        raise ValueError("generational_base_spawn_locations_required")
    if all(item in known for item in _CANONICAL_SPAWNS):
        return _CANONICAL_SPAWNS
    return known[:4]


def _base_lifecycle(spawn_location_ids: tuple[str, ...]) -> PopulationLifecycleSpec:
    return PopulationLifecycleSpec(
        lifespan_ticks=12,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 2),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 4),
            LifecycleStageThreshold(LifecycleStageId("adult"), 11),
        ),
        dependent_until_stage=LifecycleStageId("juvenile"),
        demographic_policy_id="generational_interval_entry",
        demographic_policy_params={
            "interval_ticks": 2,
            "entries_per_interval": 1,
            "generation_length_ticks": 4,
            "name_prefix": "entrant",
            "cohort_id_prefix": "cohort",
            "spawn_location_ids": list(spawn_location_ids),
        },
        max_population=9,
        natural_death_on_lifespan=True,
        lifespan_distribution=default_lifespan_distribution_spec(),
    )


def generational_comparison_base(
    *,
    seed: int = 23,
    max_ticks: int = 12,
    base: SimulationRunnerConfig | None = None,
) -> SimulationRunnerConfig:
    """Build one rich v55 base shared by every requested comparison."""
    if max_ticks < 8:
        raise ValueError("generational_base_horizon_too_short")
    if base is None:
        source = regional_migration_scenario(seed=seed, max_ticks=max_ticks)
        by_id = {item.condition_id: item for item in source.conditions}
        seed_config = by_id["ay-accurate-evidence"].runner_config
        seed_status = "ay"
    else:
        if type(base) is not SimulationRunnerConfig:
            raise ValueError("generational_base_scenario_required")
        if base.regions_migration is None:
            raise ValueError("generational_base_scenario_required")
        seed_config = base
        seed_status = "provided"

    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                skill_learning_mode=SkillLearningMode.DETERMINISTIC,
                teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
                communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC,
            ),
        )
        for agent in seed_config.agents
    )
    spawns = _spawn_locations(seed_config.scenario)
    config = replace(
        seed_config,
        agents=agents,
        schema_version=RUNNER_SCHEMA_VERSION_V55,
        mortality_mode=MortalityMode.ENABLED,
        stop_policy=RunnerStopPolicy(
            max_ticks=max_ticks, stop_on_all_agents_terminal=False
        ),
        v3_capability_flags=V3CapabilityFlags(
            generational_population=True,
            multi_polity_migration=True,
            cultural_historical_memory=True,
        ),
        population_lifecycle=_base_lifecycle(spawns),
        new_agent_initialization=default_new_agent_initialization_spec(),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        durable_records=None,
        generational_run=GenerationalRunSpec(
            max_generation_index=6,
            stop_on_extinction=False,
            criterion_cadence_ticks=1,
        ),
    )
    _LOG.info(
        "generational_comparison_base_built seed_status=%s max_ticks=%s "
        "agent_count=%s resource_count=%s",
        seed_status,
        max_ticks,
        len(config.agents),
        len(config.scenario.resources),
    )
    _LOG.debug(
        "generational_comparison_base_fields seed_status=%s lifespan_ticks=%s "
        "max_population=%s durable_records=%s",
        seed_status,
        config.population_lifecycle.lifespan_ticks
        if config.population_lifecycle is not None
        else 0,
        config.population_lifecycle.max_population
        if config.population_lifecycle is not None
        else 0,
        config.durable_records is not None,
    )
    return config


def _fail(code: str) -> NoReturn:
    raise ValueError(code)


def _require_comparable_inputs(
    conditions: Sequence[SimulationRunnerConfig],
) -> tuple[SimulationRunnerConfig, ...]:
    if isinstance(conditions, (str, bytes)) or not isinstance(conditions, Sequence):
        raise TypeError("conditions must be an ordered sequence")
    items = tuple(conditions)
    if len(items) < 2:
        _fail("comparison_requires_two_conditions")
    for item in items:
        if type(item) is not SimulationRunnerConfig:
            raise TypeError("conditions entries must be SimulationRunnerConfig")
        if item.schema_version != RUNNER_SCHEMA_VERSION_V55:
            _fail("comparison_generational_base_required")
        if item.generational_run is None:
            _fail("comparison_generational_base_required")
    return items


def _require_deterministic_distributions(
    lifecycle: PopulationLifecycleSpec,
    initialization: NewAgentInitializationSpec,
) -> None:
    if not lifecycle.lifespan_distribution.is_passthrough_default():
        _fail("comparison_lifespan_distribution_not_passthrough")
    distributions = initialization.parameter_distributions
    if distributions.distribution_id != "none" or distributions.params:
        _fail("comparison_initialization_not_deterministic")


def _schedule_identity(
    policy_id: str, params: Mapping[str, object]
) -> tuple[object, ...]:
    """Stable schedule projection; capacity fields are compared separately."""
    if policy_id == "generational_interval_entry":
        return (
            policy_id,
            params.get("interval_ticks"),
            params.get("generation_length_ticks"),
            params.get("name_prefix"),
            params.get("cohort_id_prefix"),
            tuple(params.get("spawn_location_ids", ())),  # type: ignore[arg-type]
        )
    return (
        policy_id,
        tuple(
            sorted(
                (key, value)
                for key, value in params.items()
                if key != "entries_per_interval"
            )
        ),
    )


def assert_comparable_generational_conditions(
    conditions: Sequence[SimulationRunnerConfig],
    *,
    allow_population_size: bool = False,
) -> None:
    """Fail closed unless every arm shares the declared initial conditions."""
    items = _require_comparable_inputs(conditions)
    first = items[0]
    first_lifecycle = first.population_lifecycle
    first_initialization = first.new_agent_initialization
    if first_lifecycle is None or first_initialization is None:
        _fail("comparison_generational_base_required")
    _require_deterministic_distributions(first_lifecycle, first_initialization)

    resource_identity = tuple(
        (
            resource.entity_id,
            resource.name,
            resource.kind,
            resource.location_id,
            resource.unit,
        )
        for resource in first.scenario.resources
    )
    roster = tuple(
        (agent.agent_id, agent.entity_id, agent.name, agent.initial_goals)
        for agent in first.agents
    )
    params = first_lifecycle.demographic_policy_params
    schedule = _schedule_identity(first_lifecycle.demographic_policy_id, params)
    capacity = (
        first_lifecycle.max_population,
        params.get("entries_per_interval"),
    )
    lifecycle_fixed = (
        first_lifecycle.dependent_until_stage,
        first_lifecycle.natural_death_on_lifespan,
        first_lifecycle.stage_capability_effects,
        first_lifecycle.gradual_aging,
    )

    for current in items[1:]:
        scenario = current.scenario
        if current.seed != first.seed:
            _fail("comparison_seed_mismatch")
        if (
            current.stochastic_identity != first.stochastic_identity
            or current.derivation_version != first.derivation_version
        ):
            _fail("comparison_identity_mismatch")
        if (
            scenario.world_id != first.scenario.world_id
            or scenario.revision != first.scenario.revision
            or scenario.physical_rules != first.scenario.physical_rules
            or scenario.locations != first.scenario.locations
            or scenario.bodies != first.scenario.bodies
            or scenario.weather != first.scenario.weather
            or scenario.items != first.scenario.items
            or scenario.artifacts != first.scenario.artifacts
        ):
            _fail("comparison_scenario_mismatch")
        current_resources = tuple(
            (
                resource.entity_id,
                resource.name,
                resource.kind,
                resource.location_id,
                resource.unit,
            )
            for resource in scenario.resources
        )
        if current_resources != resource_identity:
            _fail("comparison_resource_identity_mismatch")
        current_roster = tuple(
            (agent.agent_id, agent.entity_id, agent.name, agent.initial_goals)
            for agent in current.agents
        )
        if current_roster != roster:
            _fail("comparison_roster_mismatch")
        if current.stop_policy != first.stop_policy:
            _fail("comparison_stop_policy_mismatch")
        lifecycle = current.population_lifecycle
        initialization = current.new_agent_initialization
        if lifecycle is None or initialization is None:
            _fail("comparison_generational_base_required")
        current_params: dict[str, object] = dict(
            lifecycle.demographic_policy_params
        )
        current_schedule = _schedule_identity(
            lifecycle.demographic_policy_id, current_params
        )
        if current_schedule != schedule:
            _fail("comparison_schedule_mismatch")
        current_capacity = (
            lifecycle.max_population,
            current_params.get("entries_per_interval"),
        )
        if current_capacity != capacity and not allow_population_size:
            _fail("comparison_population_capacity_mismatch")
        current_fixed = (
            lifecycle.dependent_until_stage,
            lifecycle.natural_death_on_lifespan,
            lifecycle.stage_capability_effects,
            lifecycle.gradual_aging,
        )
        if current_fixed != lifecycle_fixed:
            _fail("comparison_lifecycle_mismatch")
        if current.generational_run != first.generational_run:
            _fail("comparison_generational_run_mismatch")
        _require_deterministic_distributions(lifecycle, initialization)
        if initialization != first_initialization:
            _fail("comparison_initialization_mismatch")

    _LOG.info(
        "generational_comparison_comparable condition_count=%s",
        len(items),
    )


def assert_comparable_generational_pair(
    control: SimulationRunnerConfig,
    treatment: SimulationRunnerConfig,
    *,
    allow_population_size: bool = False,
) -> None:
    assert_comparable_generational_conditions(
        (control, treatment), allow_population_size=allow_population_size
    )


__all__ = [
    "assert_comparable_generational_conditions",
    "assert_comparable_generational_pair",
    "generational_comparison_base",
]
