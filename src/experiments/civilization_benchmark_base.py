"""Bounded, comparable v55 worlds for the V3 civilization benchmark.

Composition-only: each benchmark recipe is materialized once, validated through
the real runner codecs, and shared by the controlled mechanism lane and the
autonomous research lane. This module never seeds subjective state, installs a
global registry, or weakens a stop condition to manufacture a horizon.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final

from agents.models import AgentId
from experiments.civilization_benchmark_models import (
    V3BenchmarkContrastKind,
    V3BenchmarkError,
    V3BenchmarkLane,
    V3BenchmarkProfile,
    V3BenchmarkSpec,
    V3BenchmarkTreatmentScope,
)
from experiments.civilization_benchmark_suite import (
    RESEARCH_HORIZON_TICKS,
    RESEARCH_SEEDS,
    SMOKE_HORIZON_TICKS,
    SMOKE_SEED,
    get_v3_benchmark_scenario,
)
from experiments.regional_migration_scenario import regional_migration_scenario
from simulation.generational_models import GenerationalRunSpec
from simulation.new_agent_initialization import (
    NewAgentInitializationSpec,
    default_new_agent_initialization_spec,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V55,
    AgentCognitionSpec,
    AgentRunnerSpec,
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
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)
from world.identifiers import EntityId
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold
from world.models import AgentBody, LifeStatus
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_base"
)

VISUAL_HORIZON_TICKS: Final[int] = 160
VISUAL_SEED: Final[int] = 23
VISUAL_FOUNDER_COUNT: Final[int] = 6

_ENTRY_INTERVAL_TICKS: Final[int] = 8
_GENERATION_LENGTH_TICKS: Final[int] = 16
_LIFESPAN_TICKS: Final[int] = 24
_CANONICAL_SPAWNS: Final[tuple[str, ...]] = (
    "loc-origin",
    "loc-spring",
    "loc-grain",
    "loc-remote",
)
_EXTRA_FOUNDERS: Final[tuple[tuple[str, str, str], ...]] = (
    ("agent-extra-1", "body-extra-1", "loc-origin"),
    ("agent-extra-2", "body-extra-2", "loc-origin"),
)


@dataclass(frozen=True, slots=True)
class V3BenchmarkProfileBudget:
    """Predeclared fixture budget; never a supported-scale claim."""

    profile: V3BenchmarkProfile
    horizon_ticks: int
    seeds: tuple[int, ...]
    founder_count: int
    entry_interval_ticks: int
    generation_length_ticks: int
    lifespan_ticks: int
    max_population: int

    def __post_init__(self) -> None:
        if type(self.profile) is not V3BenchmarkProfile:
            raise V3BenchmarkError("invalid_profile", "profile must be known")
        if type(self.horizon_ticks) is not int or self.horizon_ticks < 1:
            raise V3BenchmarkError(
                "invalid_horizon", "horizon_ticks must be a positive int"
            )
        if not self.seeds:
            raise V3BenchmarkError("empty_seeds", "seeds must be non-empty")
        if len(set(self.seeds)) != len(self.seeds):
            raise V3BenchmarkError("duplicate_seed", "seeds must be unique")
        if self.founder_count != 4 and self.founder_count != 6:
            raise V3BenchmarkError(
                "invalid_founder_count", "founder_count must be 4 or 6"
            )
        if self.generation_length_ticks % self.entry_interval_ticks != 0:
            raise V3BenchmarkError(
                "generational_policy_interval_indivisible",
                "generation_length_ticks must be divisible by interval_ticks",
            )
        if self.lifespan_ticks <= self.generation_length_ticks:
            raise V3BenchmarkError(
                "invalid_lifespan",
                "lifespan_ticks must exceed generation_length_ticks",
            )
        if self.max_population < self.founder_count:
            raise V3BenchmarkError(
                "invalid_capacity", "max_population must cover the founder count"
            )


V3_BENCHMARK_PROFILE_BUDGETS: Final[
    Mapping[V3BenchmarkProfile, V3BenchmarkProfileBudget]
] = {
    V3BenchmarkProfile.SMOKE: V3BenchmarkProfileBudget(
        profile=V3BenchmarkProfile.SMOKE,
        horizon_ticks=SMOKE_HORIZON_TICKS,
        seeds=(SMOKE_SEED,),
        founder_count=4,
        entry_interval_ticks=_ENTRY_INTERVAL_TICKS,
        generation_length_ticks=_GENERATION_LENGTH_TICKS,
        lifespan_ticks=_LIFESPAN_TICKS,
        max_population=12,
    ),
    V3BenchmarkProfile.RESEARCH: V3BenchmarkProfileBudget(
        profile=V3BenchmarkProfile.RESEARCH,
        horizon_ticks=RESEARCH_HORIZON_TICKS,
        seeds=RESEARCH_SEEDS,
        founder_count=4,
        entry_interval_ticks=_ENTRY_INTERVAL_TICKS,
        generation_length_ticks=_GENERATION_LENGTH_TICKS,
        lifespan_ticks=_LIFESPAN_TICKS,
        max_population=12,
    ),
    V3BenchmarkProfile.VISUAL: V3BenchmarkProfileBudget(
        profile=V3BenchmarkProfile.VISUAL,
        horizon_ticks=VISUAL_HORIZON_TICKS,
        seeds=(VISUAL_SEED,),
        founder_count=6,
        entry_interval_ticks=_ENTRY_INTERVAL_TICKS,
        generation_length_ticks=_GENERATION_LENGTH_TICKS,
        lifespan_ticks=_LIFESPAN_TICKS,
        max_population=16,
    ),
}


@dataclass(frozen=True, slots=True)
class V3BenchmarkBase:
    """One materialized v55 world shared by both lanes of a case."""

    scenario_id: str
    profile: V3BenchmarkProfile
    seed: int
    horizon_ticks: int
    schedule_id: str
    schedule_version: int
    founder_ids: tuple[str, ...]
    initializer_profile_id: str
    config: SimulationRunnerConfig

    def __post_init__(self) -> None:
        if type(self.config) is not SimulationRunnerConfig:
            raise V3BenchmarkError(
                "invalid_config", "config must be SimulationRunnerConfig"
            )
        if self.config.schema_version != RUNNER_SCHEMA_VERSION_V55:
            raise V3BenchmarkError(
                "schema_downgrade", "benchmark base requires runner-config-v55"
            )
        if self.config.generational_run is None:
            raise V3BenchmarkError(
                "missing_generational_run", "benchmark base requires generational_run"
            )
        if self.config.stop_policy.max_ticks != self.horizon_ticks:
            raise V3BenchmarkError(
                "horizon_mismatch", "stop_policy horizon must match the budget"
            )
        if self.config.stop_policy.stop_on_all_agents_terminal:
            raise V3BenchmarkError(
                "runtime_terminal_stop_enabled",
                "benchmark bases disable all-terminal stopping",
            )
        if not self.founder_ids:
            raise V3BenchmarkError("empty_founders", "founder_ids must be non-empty")


@dataclass(frozen=True, slots=True)
class V3BenchmarkArm:
    """One executable arm plus the exact declared treatment metadata."""

    arm_id: str
    config: SimulationRunnerConfig
    treatment_scope: V3BenchmarkTreatmentScope
    contrast_kind: V3BenchmarkContrastKind
    initializer_profile_id: str
    founder_ids: tuple[str, ...]
    manipulated_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class V3BenchmarkScenarioBuild:
    """Ordered arms for one case and lane; metadata stays outside runner JSON."""

    spec: V3BenchmarkSpec
    profile: V3BenchmarkProfile
    seed: int
    lane: V3BenchmarkLane
    arms: tuple[V3BenchmarkArm, ...]

    def __post_init__(self) -> None:
        if type(self.spec) is not V3BenchmarkSpec:
            raise V3BenchmarkError("invalid_spec", "spec must be a V3BenchmarkSpec")
        if type(self.profile) is not V3BenchmarkProfile:
            raise V3BenchmarkError("invalid_profile", "profile must be known")
        if type(self.lane) is not V3BenchmarkLane:
            raise V3BenchmarkError("invalid_lane", "lane must be known")
        if self.lane not in self.spec.lanes:
            raise V3BenchmarkError(
                "unsupported_lane", "lane is not declared by the scenario"
            )
        if not self.arms:
            raise V3BenchmarkError("empty_arms", "at least one arm is required")
        if len(self.arms) != self.spec.recipe.arm_count:
            raise V3BenchmarkError(
                "arm_count_mismatch", "arms must match the declared recipe"
            )


def _spawn_locations(scenario: WorldScenarioSpec) -> tuple[str, ...]:
    known = tuple(location.entity_id.value for location in scenario.locations)
    if not known:
        raise V3BenchmarkError(
            "generational_base_spawn_locations_required",
            "benchmark scenario requires locations",
        )
    if all(item in known for item in _CANONICAL_SPAWNS):
        return _CANONICAL_SPAWNS
    return known[:4]


def _benchmark_lifecycle(
    spawn_location_ids: tuple[str, ...],
    *,
    budget: V3BenchmarkProfileBudget,
) -> PopulationLifecycleSpec:
    return PopulationLifecycleSpec(
        lifespan_ticks=budget.lifespan_ticks,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 2),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 6),
            LifecycleStageThreshold(
                LifecycleStageId("adult"), budget.lifespan_ticks - 1
            ),
        ),
        dependent_until_stage=LifecycleStageId("juvenile"),
        demographic_policy_id="generational_interval_entry",
        demographic_policy_params={
            "interval_ticks": budget.entry_interval_ticks,
            "entries_per_interval": 1,
            "generation_length_ticks": budget.generation_length_ticks,
            "name_prefix": "entrant",
            "cohort_id_prefix": "cohort",
            "spawn_location_ids": list(spawn_location_ids),
        },
        max_population=budget.max_population,
        natural_death_on_lifespan=True,
        lifespan_distribution=default_lifespan_distribution_spec(),
    )


def _extra_body(entity_id: str, location_id: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(100.0),
        hunger=Hunger(0.0),
        thirst=Thirst(0.0),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(12),
    )


def _augment_visual_scenario(
    scenario: WorldScenarioSpec,
    agents: tuple[AgentRunnerSpec, ...],
) -> tuple[WorldScenarioSpec, tuple[AgentRunnerSpec, ...]]:
    if len(agents) >= VISUAL_FOUNDER_COUNT:
        return scenario, agents
    needed = VISUAL_FOUNDER_COUNT - len(agents)
    extras = _EXTRA_FOUNDERS[:needed]
    augmented = replace(
        scenario,
        bodies=scenario.bodies
        + tuple(_extra_body(body, loc) for _, body, loc in extras),
    )
    extra_agents = tuple(
        AgentRunnerSpec(
            agent_id=AgentId(agent_id),
            entity_id=EntityId(body_id),
            cognition=_founder_cognition(AgentId(agent_id)),
            initial_goals=(),
        )
        for agent_id, body_id, _ in extras
    )
    return augmented, agents + extra_agents


def _founder_cognition(agent_id: AgentId) -> AgentCognitionSpec:
    return AgentCognitionSpec(
        agent_id=agent_id,
        skill_learning_mode=SkillLearningMode.DETERMINISTIC,
        teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
        communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC,
    )


def _require_budget(profile: V3BenchmarkProfile) -> V3BenchmarkProfileBudget:
    if type(profile) is not V3BenchmarkProfile:
        raise V3BenchmarkError("invalid_profile", "profile must be a known profile")
    try:
        return V3_BENCHMARK_PROFILE_BUDGETS[profile]
    except KeyError as exc:  # pragma: no cover - enum keeps this closed
        raise V3BenchmarkError("invalid_profile", "unknown profile") from exc


def _seed_config(seed: int, horizon_ticks: int) -> SimulationRunnerConfig:
    source = regional_migration_scenario(seed=seed, max_ticks=horizon_ticks)
    by_id = {item.condition_id: item for item in source.conditions}
    return by_id["ay-accurate-evidence"].runner_config


def build_v3_benchmark_base(
    *,
    seed: int | None,
    profile: V3BenchmarkProfile,
    scenario_id: str,
) -> V3BenchmarkBase:
    """Materialize and codec-validate one bounded v55 benchmark world."""
    spec = get_v3_benchmark_scenario(scenario_id)
    budget = _require_budget(profile)
    active_seed = budget.seeds[0] if seed is None else seed
    if type(active_seed) is not int or isinstance(active_seed, bool):
        raise V3BenchmarkError("invalid_seed", "seed must be an int")
    if active_seed not in budget.seeds:
        raise V3BenchmarkError(
            "undeclared_seed",
            f"seed {active_seed} is not predeclared for profile {profile.value!r}",
        )
    source = _seed_config(active_seed, budget.horizon_ticks)
    scenario = source.scenario
    agents = tuple(
        replace(agent, cognition=_founder_cognition(agent.agent_id))
        for agent in source.agents
    )
    if budget.founder_count == VISUAL_FOUNDER_COUNT:
        scenario, agents = _augment_visual_scenario(scenario, agents)
    spawns = _spawn_locations(scenario)
    lifecycle = _benchmark_lifecycle(spawns, budget=budget)
    initialization = default_new_agent_initialization_spec()
    try:
        config = replace(
            source,
            scenario=scenario,
            agents=agents,
            experiment=None,
            schema_version=RUNNER_SCHEMA_VERSION_V55,
            mortality_mode=MortalityMode.ENABLED,
            stop_policy=RunnerStopPolicy(
                max_ticks=budget.horizon_ticks,
                stop_on_all_agents_terminal=False,
            ),
            v3_capability_flags=V3CapabilityFlags(
                generational_population=True,
                multi_polity_migration=True,
                cultural_historical_memory=True,
            ),
            population_lifecycle=lifecycle,
            new_agent_initialization=initialization,
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            durable_records=None,
            generational_run=GenerationalRunSpec(
                max_generation_index=None,
                stop_on_extinction=False,
                population_threshold=None,
                experiment_criteria=(),
                criterion_cadence_ticks=1,
            ),
        )
    except ValueError as exc:
        _LOG.error(
            "v3_benchmark_base_invalid scenario_id=%s profile=%s "
            "reason_code=%s",
            spec.scenario_id,
            profile.value,
            "invalid_composition",
        )
        raise V3BenchmarkError("invalid_composition", str(exc)) from exc
    try:
        decoded = decode_runner_config(encode_runner_config(config))
    except Exception as exc:
        raise V3BenchmarkError(
            "codec_roundtrip_failed", "runner codecs rejected the base config"
        ) from exc
    if decoded != config:
        raise V3BenchmarkError(
            "codec_roundtrip_mismatch",
            "decoded benchmark base does not match the encoded config",
        )
    _LOG.info(
        "v3_benchmark_base_built scenario_id=%s profile=%s seed=%s "
        "horizon_ticks=%s founder_count=%s max_population=%s",
        spec.scenario_id,
        profile.value,
        active_seed,
        budget.horizon_ticks,
        len(agents),
        budget.max_population,
    )
    _LOG.debug(
        "v3_benchmark_base_fields scenario_id=%s lifespan_ticks=%s "
        "entry_interval_ticks=%s generation_length_ticks=%s "
        "initializer_profile=%s",
        spec.scenario_id,
        lifecycle.lifespan_ticks,
        budget.entry_interval_ticks,
        budget.generation_length_ticks,
        initialization.species_defaults_id,
    )
    return V3BenchmarkBase(
        scenario_id=spec.scenario_id,
        profile=profile,
        seed=active_seed,
        horizon_ticks=budget.horizon_ticks,
        schedule_id=spec.recipe.schedule_id,
        schedule_version=spec.recipe.schedule_version,
        founder_ids=tuple(agent.agent_id.value for agent in agents),
        initializer_profile_id=initialization.species_defaults_id,
        config=config,
    )


def _arm(
    arm_id: str,
    base: V3BenchmarkBase,
    *,
    treatment_scope: V3BenchmarkTreatmentScope,
    contrast_kind: V3BenchmarkContrastKind,
    manipulated_fields: tuple[str, ...] = (),
) -> V3BenchmarkArm:
    initialization = base.config.new_agent_initialization
    assert isinstance(initialization, NewAgentInitializationSpec)
    return V3BenchmarkArm(
        arm_id=arm_id,
        config=base.config,
        treatment_scope=treatment_scope,
        contrast_kind=contrast_kind,
        initializer_profile_id=base.initializer_profile_id,
        founder_ids=base.founder_ids,
        manipulated_fields=manipulated_fields,
    )


def build_v3_benchmark_scenario(
    scenario_id: str,
    *,
    seed: int | None = None,
    profile: V3BenchmarkProfile = V3BenchmarkProfile.SMOKE,
    lane: V3BenchmarkLane = V3BenchmarkLane.RESEARCH,
) -> V3BenchmarkScenarioBuild:
    """Build the declared arms for one case; grouped cases keep a shared prefix."""
    spec = get_v3_benchmark_scenario(scenario_id)
    base = build_v3_benchmark_base(
        seed=seed, profile=profile, scenario_id=spec.scenario_id
    )
    arms: tuple[V3BenchmarkArm, ...]
    if spec.recipe.arm_count == 1:
        arms = (
            _arm(
                "observation",
                base,
                treatment_scope=V3BenchmarkTreatmentScope.NONE,
                contrast_kind=V3BenchmarkContrastKind.NONE,
            ),
        )
    else:
        # Grouped research cases fork a sealed prefix and apply an ordinary
        # command schedule at execution time; the materialized prefix is
        # identical and no config field is silently varied.
        arms = (
            _arm(
                "parent-prefix",
                base,
                treatment_scope=spec.recipe.treatment_scope,
                contrast_kind=spec.recipe.contrast_kind,
            ),
            _arm(
                "fork-child",
                base,
                treatment_scope=spec.recipe.treatment_scope,
                contrast_kind=spec.recipe.contrast_kind,
            ),
        )
    build = V3BenchmarkScenarioBuild(
        spec=spec,
        profile=profile,
        seed=base.seed,
        lane=lane,
        arms=arms,
    )
    assert_v3_benchmark_build_comparable(build)
    _LOG.debug(
        "v3_benchmark_scenario_built scenario_id=%s lane=%s profile=%s "
        "arm_count=%s seed=%s",
        scenario_id,
        lane.value,
        profile.value,
        len(arms),
        base.seed,
    )
    return build


def _config_identity(config: SimulationRunnerConfig) -> tuple[object, ...]:
    return (
        config.seed,
        config.stochastic_identity,
        config.derivation_version,
        config.scenario.world_id,
        config.scenario.revision,
        config.scenario.physical_rules,
        config.scenario.locations,
        config.scenario.bodies,
        config.scenario.resources,
        config.scenario.weather,
        config.scenario.items,
        config.scenario.artifacts,
        tuple(
            (agent.agent_id, agent.entity_id, agent.name, agent.initial_goals)
            for agent in config.agents
        ),
        config.stop_policy,
        config.mortality_mode,
        config.schema_version,
        config.v3_capability_flags,
        config.population_lifecycle,
        config.generational_run,
    )


def assert_v3_benchmark_build_comparable(build: V3BenchmarkScenarioBuild) -> None:
    """Fail closed unless arms share a common prefix and declared scope."""
    first = build.arms[0]
    scope = build.spec.recipe.treatment_scope
    first_initialization = first.config.new_agent_initialization
    if first_initialization is None:
        raise V3BenchmarkError(
            "missing_initialization", "benchmark arms require initialization"
        )
    identity = _config_identity(first.config)
    for arm in build.arms[1:]:
        if _config_identity(arm.config) != identity:
            raise V3BenchmarkError(
                "comparison_mismatch",
                "benchmark arms must share seed, identity, layout and schedule",
            )
        if arm.initializer_profile_id != first.initializer_profile_id:
            raise V3BenchmarkError(
                "initializer_profile_mismatch",
                "benchmark arms must share the initializer profile",
            )
        if arm.treatment_scope is not scope or arm.contrast_kind is not (
            build.spec.recipe.contrast_kind
        ):
            raise V3BenchmarkError(
                "comparison_scope_mismatch",
                "benchmark arms must declare the recipe treatment scope",
            )
    if scope is V3BenchmarkTreatmentScope.INITIALIZER_PROFILE:
        if build.spec.recipe.contrast_kind is not (
            V3BenchmarkContrastKind.COMPOSITE_PROFILE
        ):
            raise V3BenchmarkError(
                "composite_profile_required",
                "initializer comparisons are composite treatments",
            )
    _LOG.info(
        "v3_benchmark_build_comparable scenario_id=%s arm_count=%s scope=%s",
        build.spec.scenario_id,
        len(build.arms),
        scope.value,
    )


__all__ = [
    "V3_BENCHMARK_PROFILE_BUDGETS",
    "VISUAL_FOUNDER_COUNT",
    "VISUAL_HORIZON_TICKS",
    "VISUAL_SEED",
    "V3BenchmarkArm",
    "V3BenchmarkBase",
    "V3BenchmarkProfileBudget",
    "V3BenchmarkScenarioBuild",
    "assert_v3_benchmark_build_comparable",
    "build_v3_benchmark_base",
    "build_v3_benchmark_scenario",
]
