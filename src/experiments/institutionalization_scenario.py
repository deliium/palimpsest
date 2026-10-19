"""Experiment BF: analytical institution emergence and persistence.

No institution type exists. The scenario only composes already-owned objective
and owner-scoped channels; the analysis candidates and persistence
classifications are researcher-facing output.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import Final

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.interventions import MilestoneInterventionArbiter, MilestoneOverride
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
    require_stochastic,
)
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V43,
    RUNNER_SCHEMA_VERSION_V48,
    RUNNER_SCHEMA_VERSION_V49,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CulturalNarrativeMode,
    InstitutionConceptMode,
    KinshipSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    SkillLearningMode,
    SocialConventionMode,
    SocialNormMode,
    TeachingInteractionMode,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_collective_projects_spec,
    example_cultural_feature_provenance_spec,
    example_mentorship_spec,
    example_population_lifecycle_spec,
    example_public_goods_spec,
    example_resource_exchange_profile_spec,
    example_structured_commitments_spec,
    example_subjective_valuation_spec,
)
from world.actions import AgentCommand, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import (
    AgentBody,
    LifeStatus,
    Location,
    Weather,
    default_physical_rules,
)
from world.values import (
    BodyCapacity,
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemCapacity,
    TemperatureCelsius,
    Thirst,
    UnitInterval,
    WeatherCondition,
)

__all__ = [
    "assert_institution_structure",
    "bf_unsupported_config",
    "institutionalization_arbiter",
    "institutionalization_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.institutionalization_scenario"
)

_AGENTS: Final[tuple[tuple[str, str], ...]] = (
    ("agent-a", "body-a"),
    ("agent-b", "body-b"),
    ("agent-c", "body-c"),
    ("agent-d", "body-d"),
)
_ENABLED_ARMS: Final[frozenset[str]] = frozenset({"bf-institution-on"})


def _agent_specs(*, institution: bool, modes: bool) -> tuple[AgentRunnerSpec, ...]:
    return tuple(
        AgentRunnerSpec(
            agent_id=AgentId(agent_id),
            entity_id=EntityId(body_id),
            cognition=AgentCognitionSpec(
                agent_id=AgentId(agent_id),
                institution_concept_mode=(
                    InstitutionConceptMode.DETERMINISTIC
                    if institution
                    else InstitutionConceptMode.DISABLED
                ),
                cultural_narrative_mode=CulturalNarrativeMode.DISABLED,
                social_norm_mode=(
                    SocialNormMode.DETERMINISTIC if modes else SocialNormMode.DISABLED
                ),
                social_convention_mode=(
                    SocialConventionMode.DETERMINISTIC
                    if modes
                    else SocialConventionMode.DISABLED
                ),
                teaching_interaction_mode=(
                    TeachingInteractionMode.DETERMINISTIC
                    if modes
                    else TeachingInteractionMode.DISABLED
                ),
                skill_learning_mode=(
                    SkillLearningMode.DETERMINISTIC
                    if modes
                    else SkillLearningMode.DISABLED
                ),
            ),
            initial_goals=(),
        )
        for agent_id, body_id in _AGENTS
    )


def _location() -> Location:
    return Location(
        entity_id=EntityId("loc-clearing"),
        name="clearing",
        adjacent=(),
        body_capacity=BodyCapacity(8),
        item_capacity=ItemCapacity(24),
        base_temperature=TemperatureCelsius(20.0),
        shelter_factor=UnitInterval(0.1),
        visibility_factor=UnitInterval(1.0),
    )


def _body(name: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(name),
        location_id=EntityId("loc-clearing"),
        health=Health(100.0),
        hunger=Hunger(0.0),
        thirst=Thirst(0.0),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(12),
    )


def _scenario() -> WorldScenarioSpec:
    location = _location()
    return WorldScenarioSpec(
        world_id=WorldId("world-bf"),
        revision=WorldRevision(0),
        physical_rules=default_physical_rules(),
        locations=(location,),
        bodies=tuple(_body(body_id) for _, body_id in _AGENTS),
        weather=(Weather(location.entity_id, WeatherCondition.CLEAR),),
    )


def _base_config(
    *,
    seed: int,
    stochastic_identity: str,
    max_ticks: int,
    modes: bool,
) -> SimulationRunnerConfig:
    scenario = _scenario()
    agents = _agent_specs(institution=False, modes=False)
    return base_runner_config_from_scenario(
        seed=seed,
        stochastic_identity=stochastic_identity,
        scenario=scenario,
        agents=agents,
        max_ticks=max_ticks,
    )


def _composed_channels(
    config: SimulationRunnerConfig,
    *,
    schema_version: str,
    institution: bool,
) -> SimulationRunnerConfig:
    return replace(
        config,
        schema_version=schema_version,
        agents=_agent_specs(institution=institution, modes=True),
        v3_capability_flags=V3CapabilityFlags(
            generational_population=True,
            cultural_historical_memory=True,
            kinship_inheritance=True,
        ),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        kinship=KinshipSpec(),
        mentorship=example_mentorship_spec(),
        collective_projects=example_collective_projects_spec(),
        public_goods=example_public_goods_spec(),
        structured_commitments=example_structured_commitments_spec(),
        subjective_valuation=example_subjective_valuation_spec(),
        resource_exchange_profile=example_resource_exchange_profile_spec(),
    )


def institutionalization_scenario(
    *,
    seed: int = 23,
    max_ticks: int = 16,
    seed_matrix: ExperimentSeedMatrix | None = None,
    base: SimulationRunnerConfig | None = None,
) -> ExperimentDefinition:
    """Build the three BF arms: v4 baseline, v48 mode-off, v49 mode-on."""
    if base is not None and type(base) is not SimulationRunnerConfig:
        raise TypeError("base must be SimulationRunnerConfig or None")
    active_seed = seed if base is None else base.seed
    stochastic_identity = (
        require_stochastic("institutionalization-bf")
        if base is None
        else base.stochastic_identity
    )
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(active_seed,))

    baseline = replace(
        _base_config(
            seed=active_seed,
            stochastic_identity=stochastic_identity.value,
            max_ticks=max_ticks,
            modes=False,
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V4,
    )
    base_arm = _base_config(
        seed=active_seed,
        stochastic_identity=stochastic_identity.value,
        max_ticks=max_ticks,
        modes=False,
    )
    off_arm = _composed_channels(
        base_arm,
        schema_version=RUNNER_SCHEMA_VERSION_V43,
        institution=False,
    )
    on_arm = _composed_channels(
        base_arm,
        schema_version=RUNNER_SCHEMA_VERSION_V49,
        institution=True,
    )
    if base is not None:
        baseline = replace(
            base,
            agents=_agent_specs(institution=False, modes=False),
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            schema_version=RUNNER_SCHEMA_VERSION_V4,
        )
    arms = (
        ("bf-baseline", "institutionalization_flags_off", baseline),
        ("bf-institution-off", "institutionalization_mode_off", off_arm),
        ("bf-institution-on", "institutionalization_mode_on", on_arm),
    )
    _LOG.info(
        "institutionalization_experiment_built arms=%s ticks=%s agents=%s",
        len(arms),
        max_ticks,
        len(_AGENTS),
    )
    return ExperimentDefinition(
        experiment_id="institutionalization@1",
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=tuple(
            ExperimentCondition(
                condition_id=condition_id,
                label_code=label,
                runner_config=config,
            )
            for condition_id, label, config in arms
        ),
        paired_world_group="institutionalization-bf-world",
    )


def bf_unsupported_config() -> SimulationRunnerConfig:
    """Non-run fixture: institution mode on a v48 config fails closed."""
    config = institutionalization_scenario().conditions[2].runner_config
    return replace(config, schema_version=RUNNER_SCHEMA_VERSION_V48)


def institutionalization_arbiter(
    condition_id: str, config: SimulationRunnerConfig
) -> MilestoneInterventionArbiter | None:
    """Drive a deterministic long-lived world with repeated functions."""
    if condition_id not in _ENABLED_ARMS:
        return None
    horizon = config.stop_policy.max_ticks
    assert horizon is not None
    commands: dict[tuple[int, str], AgentCommand] = {}
    for tick in range(horizon):
        for agent in config.agents:
            commands[tick, agent.agent_id.value] = Wait()
    milestones = tuple(
        MilestoneOverride(
            milestone_id=f"{condition_id}-{tick}-{agent}",
            tick=tick,
            agent_id=AgentId(agent),
            build_command=_command_factory(command),
        )
        for (tick, agent), command in sorted(commands.items())
        if tick < horizon
    )
    return MilestoneInterventionArbiter(milestones, override_budget=len(milestones))


def _command_factory(command: AgentCommand) -> Callable[[], AgentCommand]:
    def build() -> AgentCommand:
        return command

    return build


def assert_institution_structure(
    *,
    candidate_count: int,
    persistence_row_count: int,
    concept_ledgers: Sequence[object],
    deterministic_owner_ids: Sequence[str],
    owner_concept_ids: Mapping[str, set[str]] | None = None,
    restored_owner_concept_ids: Mapping[str, set[str]] | None = None,
) -> None:
    """Structural arbiter assertions shared by BF tests."""
    if candidate_count < 1:
        raise AssertionError("institution_candidate_required")
    if persistence_row_count < candidate_count:
        raise AssertionError("persistence_row_missing")
    if len(concept_ledgers) != len(deterministic_owner_ids):
        raise AssertionError("owner_ledger_count_mismatch")
    if owner_concept_ids is not None:
        seen: set[str] = set()
        for owner, ids in owner_concept_ids.items():
            if seen & ids:
                raise AssertionError("cross_owner_concept_leakage")
            seen.update(ids)
            if restored_owner_concept_ids is not None and ids != set(
                restored_owner_concept_ids.get(owner, set())
            ):
                raise AssertionError("checkpoint_ledger_mismatch")
