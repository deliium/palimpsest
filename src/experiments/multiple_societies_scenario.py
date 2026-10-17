"""Experiment AZ: region-separated populations for candidate-society analysis.

This scenario adds no world behavior. It composes existing region, journey, and
communication channels so a post-run analysis can detect candidate communities.
All society labels remain analytical and never reach cognition.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Final

from agents.models import AgentId
from experiments.interventions import MilestoneInterventionArbiter, MilestoneOverride
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
    require_stochastic,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V44,
    AgentCognitionSpec,
    AgentRunnerSpec,
    ArtifactInterpretationMode,
    CommunicationStrategyMode,
    CulturalNarrativeMode,
    MortalityMode,
    RunnerStopPolicy,
    SemanticNamingMode,
    SimulationRunnerConfig,
    SocialConventionMode,
    SocialNormMode,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_collective_projects_spec,
    example_public_goods_spec,
    example_resource_exchange_profile_spec,
    example_subjective_valuation_spec,
)
from world.actions import AgentCommand, Move, Talk, Wait
from world.communications import origin_utterance
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import (
    AgentBody,
    LifeStatus,
    Location,
    Weather,
    default_physical_rules,
)
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
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

__all__ = ["multiple_societies_arbiter", "multiple_societies_scenario"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.multiple_societies_scenario"
)

_AGENTS: Final[tuple[tuple[str, str], ...]] = (
    ("agent-a", "body-a"),
    ("agent-b", "body-b"),
    ("agent-e", "body-e"),
    ("agent-c", "body-c"),
    ("agent-d", "body-d"),
)
_NORTH_BODIES: Final[tuple[str, ...]] = ("body-b", "body-e")
_SOUTH_BODIES: Final[tuple[str, ...]] = ("body-c", "body-d")


def multiple_societies_arbiter(
    condition_id: str, config: SimulationRunnerConfig
) -> MilestoneInterventionArbiter | None:
    """Deterministic co-located talk plus one optional interregional visit."""
    if condition_id not in {"az-isolated", "az-contact"}:
        return None
    horizon = config.stop_policy.max_ticks
    assert horizon is not None
    commands: dict[tuple[int, str], AgentCommand] = {}
    for tick in range(horizon):
        for agent in config.agents:
            commands[tick, agent.agent_id.value] = Wait()
    for tick in range(horizon):
        _talk(commands, tick, "body-b", "body-e")
        _talk(commands, tick, "body-c", "body-d")
    if condition_id == "az-contact" and horizon > 6:
        commands[0, "agent-a"] = Move(EntityId("loc-north-hill"))
        commands[2, "agent-a"] = Move(EntityId("loc-south-grove"))
        commands[4, "agent-a"] = Move(EntityId("loc-south"))
        for tick in range(6, horizon):
            _talk(commands, tick, "body-a", "body-c", suffix="cross")
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
    _LOG.debug(
        "multiple_societies_arbiter_built condition_id=%s override_count=%s",
        condition_id,
        len(milestones),
    )
    return MilestoneInterventionArbiter(milestones, override_budget=len(milestones))


def _talk(
    commands: dict[tuple[int, str], AgentCommand],
    tick: int,
    speaker: str,
    recipient: str,
    *,
    suffix: str = "local",
) -> None:
    agent_id = f"agent-{speaker.removeprefix('body-')}"
    commands[tick, agent_id] = Talk(
        recipient_id=EntityId(recipient),
        utterance=origin_utterance(
            speaker_id=EntityId(speaker),
            communication_id=f"az-{suffix}-{tick}",
            text="We share this place.",
            concepts=("place:shared",),
            sender_confidence=0.7,
        ),
    )


def _command_factory(command: AgentCommand) -> Callable[[], AgentCommand]:
    def build() -> AgentCommand:
        return command

    return build


def _location(
    name: str,
    *,
    neighbors: tuple[str, ...],
    capacity: int,
    temperature: float,
) -> Location:
    return Location(
        entity_id=EntityId(name),
        name=name,
        adjacent=tuple(EntityId(item) for item in neighbors),
        body_capacity=BodyCapacity(capacity),
        item_capacity=ItemCapacity(24),
        base_temperature=TemperatureCelsius(temperature),
        shelter_factor=UnitInterval(0.1),
        visibility_factor=UnitInterval(1.0),
    )


def _body(name: str, location: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(name),
        location_id=EntityId(location),
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
    locations = (
        _location(
            "loc-north",
            neighbors=("loc-north-hill",),
            capacity=4,
            temperature=18.0,
        ),
        _location(
            "loc-north-hill",
            neighbors=("loc-north", "loc-south-grove"),
            capacity=2,
            temperature=12.0,
        ),
        _location(
            "loc-south",
            neighbors=("loc-south-grove",),
            capacity=3,
            temperature=26.0,
        ),
        _location(
            "loc-south-grove",
            neighbors=("loc-south", "loc-north-hill"),
            capacity=2,
            temperature=29.0,
        ),
    )
    return WorldScenarioSpec(
        world_id=WorldId("world-multiple-societies-az"),
        revision=WorldRevision(0),
        physical_rules=default_physical_rules(),
        locations=locations,
        bodies=(
            _body("body-a", "loc-north"),
            _body("body-b", "loc-north"),
            _body("body-e", "loc-north"),
            _body("body-c", "loc-south"),
            _body("body-d", "loc-south"),
        ),
        weather=tuple(
            Weather(location.entity_id, WeatherCondition.CLEAR)
            for location in locations
        ),
    )


def _regions(*, cognition_mode: CognitionMode) -> RegionsMigrationSpec:
    return RegionsMigrationSpec(
        regions=(
            RegionDefinition("north", "North"),
            RegionDefinition("south", "South"),
        ),
        location_regions=(
            LocationRegion(EntityId("loc-north"), "north"),
            LocationRegion(EntityId("loc-north-hill"), "north"),
            LocationRegion(EntityId("loc-south"), "south"),
            LocationRegion(EntityId("loc-south-grove"), "south"),
        ),
        routes=(
            RouteSpec(EntityId("loc-north"), EntityId("loc-north-hill"), 1, 2.0),
            RouteSpec(EntityId("loc-north-hill"), EntityId("loc-south-grove"), 1, 4.0),
            RouteSpec(EntityId("loc-south-grove"), EntityId("loc-south"), 1, 2.0),
        ),
        max_arrival_wait_ticks=1,
        residence_min_ticks=2,
        destination_memory_limit=3,
        destination_hop_limit=3,
        cognition_mode=cognition_mode,
    )


def multiple_societies_scenario(
    *,
    seed: int = 23,
    max_ticks: int = 16,
    seed_matrix: ExperimentSeedMatrix | None = None,
    base: SimulationRunnerConfig | None = None,
) -> ExperimentDefinition:
    """Return off and region-separated arms on a shared deterministic world."""
    if base is not None and type(base) is not SimulationRunnerConfig:
        raise TypeError("base must be SimulationRunnerConfig or None")
    active_seed = seed if base is None else base.seed
    stochastic_identity = (
        require_stochastic("multiple-societies-az")
        if base is None
        else base.stochastic_identity
    )
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(active_seed,))
    scenario = _scenario()

    def config(*, regions: RegionsMigrationSpec | None) -> SimulationRunnerConfig:
        agents = tuple(
            AgentRunnerSpec(
                agent_id=AgentId(agent_id),
                entity_id=EntityId(body_id),
                cognition=AgentCognitionSpec(
                    agent_id=AgentId(agent_id),
                    communication_strategy_mode=(
                        CommunicationStrategyMode.DISABLED
                        if regions is None
                        else CommunicationStrategyMode.DETERMINISTIC
                    ),
                    semantic_naming_mode=(
                        SemanticNamingMode.DISABLED
                        if regions is None
                        else SemanticNamingMode.DETERMINISTIC
                    ),
                    social_norm_mode=(
                        SocialNormMode.DISABLED
                        if regions is None
                        else SocialNormMode.DETERMINISTIC
                    ),
                    social_convention_mode=(
                        SocialConventionMode.DISABLED
                        if regions is None
                        else SocialConventionMode.DETERMINISTIC
                    ),
                    cultural_narrative_mode=(
                        CulturalNarrativeMode.DISABLED
                        if regions is None
                        else CulturalNarrativeMode.DETERMINISTIC
                    ),
                    artifact_interpretation_mode=(
                        ArtifactInterpretationMode.DISABLED
                        if regions is None
                        else ArtifactInterpretationMode.DETERMINISTIC
                    ),
                ),
                initial_goals=(),
            )
            for agent_id, body_id in _AGENTS
        )
        return SimulationRunnerConfig(
            seed=active_seed,
            stochastic_identity=stochastic_identity,
            scenario=scenario,
            agents=agents,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            mortality_mode=(
                MortalityMode.DISABLED if base is None else base.mortality_mode
            ),
            schema_version=(
                RUNNER_SCHEMA_VERSION_V4
                if regions is None
                else RUNNER_SCHEMA_VERSION_V44
            ),
            v3_capability_flags=(
                V3CapabilityFlags()
                if regions is None
                else V3CapabilityFlags(multi_polity_migration=True)
            ),
            regions_migration=regions,
            subjective_valuation=(
                None if regions is None else example_subjective_valuation_spec()
            ),
            resource_exchange_profile=(
                None if regions is None else example_resource_exchange_profile_spec()
            ),
            collective_projects=(
                None if regions is None else example_collective_projects_spec()
            ),
            public_goods=None if regions is None else example_public_goods_spec(),
        )

    off = config(regions=None)
    isolated = config(regions=_regions(cognition_mode=CognitionMode.DETERMINISTIC))
    contact = config(regions=_regions(cognition_mode=CognitionMode.DETERMINISTIC))
    conditions = (
        ("az-channel-off", "multiple_societies_off", off),
        ("az-isolated", "region_separated_populations", isolated),
        ("az-contact", "journey_bridged_contact", contact),
    )
    _LOG.info(
        "multiple_societies_experiment_built arms=%s ticks=%s agents=%s",
        len(conditions),
        max_ticks,
        len(_AGENTS),
    )
    return ExperimentDefinition(
        experiment_id="multiple_societies@1",
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=tuple(
            ExperimentCondition(
                condition_id=condition_id,
                label_code=label,
                runner_config=item,
            )
            for condition_id, label, item in conditions
        ),
        paired_world_group="multiple-societies-az-world",
    )
