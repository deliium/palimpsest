"""Experiment AY: reproducible optional regional travel and migration evidence."""

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
    CommunicationStrategyMode,
    MortalityMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V3CapabilityFlags,
    WorldScenarioSpec,
)
from world.actions import AgentCommand, Move, Tell, Wait
from world.communications import origin_utterance
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import (
    AgentBody,
    LifeStatus,
    Location,
    Resource,
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
    ResourceKind,
    TemperatureCelsius,
    Thirst,
    UnitInterval,
    WeatherCondition,
)

__all__ = ["regional_migration_arbiter", "regional_migration_scenario"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.regional_migration_scenario"
)


def regional_migration_arbiter(
    condition_id: str, config: SimulationRunnerConfig
) -> MilestoneInterventionArbiter | None:
    """Diagnostic interventions only; the accurate arm uses production cognition.

    Commands pass ordinary admission. In the testimony arm only the encounter
    and utterances are controlled; the recipient's later choices are cognitive.
    Collectors never select commands or supply evidence to agents.
    """
    if condition_id not in {
        "ay-visit-return",
        "ay-blocked-arrival",
        "ay-false-stale-testimony",
    }:
        return None
    commands: dict[tuple[int, str], AgentCommand] = {}
    horizon = config.stop_policy.max_ticks
    assert horizon is not None
    if condition_id in {"ay-visit-return", "ay-blocked-arrival"}:
        for tick in range(horizon):
            for runner_agent in config.agents:
                commands[tick, runner_agent.agent_id.value] = Wait()
        if condition_id == "ay-blocked-arrival":
            commands[0, "agent-origin"] = Move(EntityId("loc-spring"))
        else:
            for tick, agent, destination in (
                (0, "agent-spring", "loc-crossroads"),
                (1, "agent-origin", "loc-spring"),
                (3, "agent-origin", "loc-crossroads"),
                (4, "agent-origin", "loc-spring"),
                (5, "agent-origin", "loc-origin"),
            ):
                commands[tick, agent] = Move(EntityId(destination))
    else:
        report_tick = config.scenario.physical_rules.day_start_hour
        for tick in range(min(report_tick + 1, horizon)):
            commands[tick, "agent-origin"] = Wait()
            commands[tick, "agent-spring"] = Wait()
        commands[0, "agent-spring"] = Move(EntityId("loc-origin"))
        commands[report_tick, "agent-spring"] = Tell(
            recipient_id=EntityId("body-origin"),
            utterance=origin_utterance(
                speaker_id=EntityId("body-spring"),
                communication_id="ay-fallible-report",
                text="I remember water at the crossroads long ago.",
                concepts=(
                    "destination_id:loc-crossroads",
                    "resource:water",
                    "reported_tick:0",
                ),
                sender_confidence=0.8,
            ),
        )
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
        "regional_diagnostic_built condition_id=%s override_count=%s",
        condition_id,
        len(milestones),
    )
    return MilestoneInterventionArbiter(milestones, override_budget=len(milestones))


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
        visibility_factor=UnitInterval(0.8),
    )


def _body(
    name: str,
    location: str,
    *,
    hunger: float = 0.0,
    thirst: float = 0.0,
) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(name),
        location_id=EntityId(location),
        health=Health(100.0),
        hunger=Hunger(hunger),
        thirst=Thirst(thirst),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(12),
    )


def _scenario() -> WorldScenarioSpec:
    locations = (
        _location(
            "loc-origin",
            neighbors=("loc-spring",),
            capacity=3,
            temperature=27.0,
        ),
        _location(
            "loc-spring",
            neighbors=("loc-origin", "loc-crossroads"),
            capacity=1,
            temperature=21.0,
        ),
        _location(
            "loc-crossroads",
            neighbors=("loc-spring", "loc-grain"),
            capacity=2,
            temperature=39.0,
        ),
        _location(
            "loc-grain",
            neighbors=("loc-crossroads", "loc-remote"),
            capacity=2,
            temperature=31.0,
        ),
        _location(
            "loc-remote",
            neighbors=("loc-grain",),
            capacity=1,
            temperature=12.0,
        ),
    )
    spring, grain, remote = (
        EntityId("loc-spring"),
        EntityId("loc-grain"),
        EntityId("loc-remote"),
    )
    return WorldScenarioSpec(
        world_id=WorldId("world-regional-migration-ay"),
        revision=WorldRevision(0),
        physical_rules=default_physical_rules(),
        locations=locations,
        bodies=(
            _body("body-origin", "loc-origin", hunger=72.0, thirst=78.0),
            _body("body-spring", "loc-spring", thirst=8.0),
            _body("body-grain", "loc-grain", hunger=12.0),
            _body("body-remote", "loc-remote", hunger=8.0),
        ),
        resources=(
            Resource(
                entity_id=EntityId("resource-water-spring"),
                name="Spring water",
                kind=ResourceKind.WATER,
                location_id=spring,
                quantity=7.0,
                maximum_quantity=7.0,
                regeneration_per_tick=0.0,
                unit="litres",
            ),
            Resource(
                entity_id=EntityId("resource-food-grain"),
                name="Local grain",
                kind=ResourceKind.FOOD,
                location_id=grain,
                quantity=8.0,
                maximum_quantity=8.0,
                regeneration_per_tick=0.0,
                unit="portions",
            ),
            Resource(
                entity_id=EntityId("resource-food-remote"),
                name="Remote food",
                kind=ResourceKind.FOOD,
                location_id=remote,
                quantity=10.0,
                maximum_quantity=10.0,
                regeneration_per_tick=0.0,
                unit="portions",
            ),
        ),
        weather=tuple(
            Weather(location.entity_id, WeatherCondition.CLEAR)
            for location in locations
        ),
    )


def _regions(
    *, cognition_mode: CognitionMode, arrival_wait: int = 1
) -> RegionsMigrationSpec:
    return RegionsMigrationSpec(
        regions=(
            RegionDefinition("north", "North"),
            RegionDefinition("dryland", "Dryland"),
            RegionDefinition("far", "Far"),
        ),
        location_regions=(
            LocationRegion(EntityId("loc-origin"), "north"),
            LocationRegion(EntityId("loc-spring"), "north"),
            LocationRegion(EntityId("loc-crossroads"), "dryland"),
            LocationRegion(EntityId("loc-grain"), "dryland"),
            LocationRegion(EntityId("loc-remote"), "far"),
        ),
        routes=(
            RouteSpec(EntityId("loc-origin"), EntityId("loc-spring"), 2, 3.0),
            RouteSpec(EntityId("loc-spring"), EntityId("loc-crossroads"), 1, 2.0),
            RouteSpec(EntityId("loc-crossroads"), EntityId("loc-grain"), 3, 5.0),
            RouteSpec(EntityId("loc-grain"), EntityId("loc-remote"), 4, 7.0),
        ),
        max_arrival_wait_ticks=arrival_wait,
        residence_min_ticks=4,
        destination_memory_limit=3,
        destination_hop_limit=4,
        cognition_mode=cognition_mode,
    )


def regional_migration_scenario(
    *,
    seed: int = 11,
    max_ticks: int = 32,
    seed_matrix: ExperimentSeedMatrix | None = None,
    base: SimulationRunnerConfig | None = None,
) -> ExperimentDefinition:
    """Return off, physics, evidence, testimony, visit, and blocked-arrival arms."""
    if base is not None and type(base) is not SimulationRunnerConfig:
        raise TypeError("base must be SimulationRunnerConfig or None")
    active_seed = seed if base is None else base.seed
    stochastic_identity = (
        require_stochastic("regional-migration-ay")
        if base is None
        else base.stochastic_identity
    )
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(active_seed,))
    scenario = _scenario()
    agent_ids = (
        (AgentId("agent-origin"), EntityId("body-origin")),
        (AgentId("agent-spring"), EntityId("body-spring")),
        (AgentId("agent-grain"), EntityId("body-grain")),
        (AgentId("agent-remote"), EntityId("body-remote")),
    )

    def config(
        *,
        regions: RegionsMigrationSpec | None,
        schema_version: str,
        communication: bool = False,
    ) -> SimulationRunnerConfig:
        agents = tuple(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body_id,
                cognition=AgentCognitionSpec(
                    agent_id=agent_id,
                    communication_strategy_mode=(
                        CommunicationStrategyMode.DETERMINISTIC
                        if communication
                        else CommunicationStrategyMode.DISABLED
                    ),
                ),
                initial_goals=(),
            )
            for agent_id, body_id in agent_ids
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
            schema_version=schema_version,
            v3_capability_flags=(
                V3CapabilityFlags()
                if regions is None
                else V3CapabilityFlags(multi_polity_migration=True)
            ),
            regions_migration=regions,
        )

    off = config(regions=None, schema_version=RUNNER_SCHEMA_VERSION_V4)
    physics_only = config(
        regions=_regions(cognition_mode=CognitionMode.DISABLED),
        schema_version=RUNNER_SCHEMA_VERSION_V44,
    )
    accurate = config(
        regions=_regions(cognition_mode=CognitionMode.DETERMINISTIC),
        schema_version=RUNNER_SCHEMA_VERSION_V44,
    )
    testimony = config(
        regions=_regions(cognition_mode=CognitionMode.DETERMINISTIC),
        schema_version=RUNNER_SCHEMA_VERSION_V44,
        communication=True,
    )
    visit_return = config(
        regions=_regions(cognition_mode=CognitionMode.DETERMINISTIC),
        schema_version=RUNNER_SCHEMA_VERSION_V44,
    )
    blocked_arrival = config(
        regions=_regions(cognition_mode=CognitionMode.DISABLED, arrival_wait=0),
        schema_version=RUNNER_SCHEMA_VERSION_V44,
    )
    conditions = (
        ("ay-channel-off", "multi_polity_migration_off", off),
        ("ay-physics-only", "regional_physics_only", physics_only),
        ("ay-accurate-evidence", "private_direct_evidence", accurate),
        ("ay-false-stale-testimony", "fallible_communicated_evidence", testimony),
        ("ay-visit-return", "visit_and_return", visit_return),
        ("ay-blocked-arrival", "capacity_wait_and_timeout", blocked_arrival),
    )
    _LOG.info(
        "regional_migration_experiment_built arms=%s ticks=%s "
        "region_count=%s route_count=%s",
        len(conditions),
        max_ticks,
        len(_regions(cognition_mode=CognitionMode.DISABLED).regions),
        len(_regions(cognition_mode=CognitionMode.DISABLED).routes),
    )
    return ExperimentDefinition(
        experiment_id="regional_migration@1",
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
        paired_world_group="regional-migration-ay-world",
    )
