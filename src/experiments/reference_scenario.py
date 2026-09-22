"""Canonical five-agent reference scenario (input fixture for metrics).

Builds a reusable 48-tick / two-day world with structured goals, connected
locations, extractable food/water, survival needs, communication, reconstructive
memory, relationships, imagination, and sparse milestone arbitration. This
module never imports analysis metrics.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import (
    AgentId,
    Goal,
    GoalId,
    GoalOutcome,
    GoalOutcomeKind,
    GoalStatus,
)
from experiments.interventions import (
    DEFAULT_OVERRIDE_BUDGET,
    MILESTONE_ARBITER_POLICY_VERSION,
    MilestoneInterventionArbiter,
    MilestoneOverride,
)
from simulation.models import StochasticIdentity
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    ImaginationMode,
    MemoryMode,
    MortalityMode,
    RecordingPolicy,
    RunnerProviderSettings,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from simulation.runner_serialization import (
    runner_config_fingerprint,
    scenario_fingerprint,
)
from world.actions import AgentCommand, Attack, Drink, Eat, Move, Search, Tell
from world.communications import origin_utterance
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import (
    AgentBody,
    Item,
    LifeStatus,
    Location,
    PhysicalRules,
    Resource,
    Weather,
)
from world.values import (
    BodyCapacity,
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemCapacity,
    ItemKind,
    ItemLoad,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
    UnitInterval,
    WeatherCondition,
)

_LOG: Final[logging.Logger] = logging.getLogger("experiments.reference_scenario")

REFERENCE_SCENARIO_ID: Final[str] = "reference-five-agent-v1"
REFERENCE_SCENARIO_VERSION: Final[str] = "reference-scenario-v1"
REFERENCE_MAX_TICKS: Final[int] = 48
REFERENCE_DEFAULT_SEED: Final[int] = 20260922
REFERENCE_STOCHASTIC_IDENTITY: Final[str] = "reference-five-agent-stoch-v1"
REFERENCE_WORLD_ID: Final[str] = "world-reference-v1"
REFERENCE_DEATH_TICK: Final[int] = 12
REFERENCE_DEFAULT_OVERRIDE_BUDGET: Final[int] = DEFAULT_OVERRIDE_BUDGET

AGENT_MIRA: Final[str] = "agent-mira"
AGENT_KAI: Final[str] = "agent-kai"
AGENT_ROWAN: Final[str] = "agent-rowan"
AGENT_SOREN: Final[str] = "agent-soren"
AGENT_NYX: Final[str] = "agent-nyx"

BODY_MIRA: Final[str] = "body-mira"
BODY_KAI: Final[str] = "body-kai"
BODY_ROWAN: Final[str] = "body-rowan"
BODY_SOREN: Final[str] = "body-soren"
BODY_NYX: Final[str] = "body-nyx"

LOC_CAMP: Final[str] = "loc-camp"
LOC_SPRING: Final[str] = "loc-spring"
LOC_GROVE: Final[str] = "loc-grove"
LOC_RIDGE: Final[str] = "loc-ridge"

RES_WATER: Final[str] = "res-spring-water"
RES_FOOD: Final[str] = "res-grove-food"
ITEM_FOOD_MIRA: Final[str] = "item-food-mira"

MILESTONE_EXTRACT_WATER: Final[str] = "ms-extract-water"
MILESTONE_DRINK_WATER: Final[str] = "ms-drink-water"
MILESTONE_EXTRACT_FOOD: Final[str] = "ms-extract-food"
MILESTONE_EAT_FOOD: Final[str] = "ms-eat-food"
MILESTONE_TELL_OBSERVE: Final[str] = "ms-tell-observe"
MILESTONE_COLOCATE_ATTACKER: Final[str] = "ms-colocate-attacker"
MILESTONE_COLOCATE_VICTIM: Final[str] = "ms-colocate-victim"
MILESTONE_LETHAL_ATTACK: Final[str] = "ms-lethal-attack"

_AGENT_SPECS: Final[tuple[tuple[str, str, str], ...]] = (
    (AGENT_MIRA, BODY_MIRA, "Mira"),
    (AGENT_KAI, BODY_KAI, "Kai"),
    (AGENT_ROWAN, BODY_ROWAN, "Rowan"),
    (AGENT_SOREN, BODY_SOREN, "Soren"),
    (AGENT_NYX, BODY_NYX, "Nyx"),
)


class ScenarioErrorCode(StrEnum):
    """Stable ERROR codes for scenario construction (no payloads)."""

    INVALID_BUDGET = "scenario_invalid_budget"
    INVALID_TICKS = "scenario_invalid_ticks"
    INVALID_DEATH_TICK = "scenario_invalid_death_tick"


@dataclass(frozen=True, slots=True)
class ReferenceScenarioBundle:
    """Detached scenario fixture: runner config plus typed milestone arbiter."""

    scenario_id: str
    scenario_version: str
    config: SimulationRunnerConfig
    arbiter: MilestoneInterventionArbiter
    death_tick: int
    death_agent_id: AgentId
    death_body_id: EntityId
    attacker_agent_id: AgentId
    config_fingerprint: str
    scenario_fingerprint: str
    milestone_ids: tuple[str, ...]
    override_budget: int

    def __post_init__(self) -> None:
        if type(self.config) is not SimulationRunnerConfig:
            raise TypeError("config must be SimulationRunnerConfig")
        if type(self.arbiter) is not MilestoneInterventionArbiter:
            raise TypeError("arbiter must be MilestoneInterventionArbiter")


def _location(
    entity_id: str,
    *,
    name: str,
    adjacent: Sequence[str],
) -> Location:
    return Location(
        entity_id=EntityId(entity_id),
        name=name,
        adjacent=tuple(EntityId(item) for item in adjacent),
        body_capacity=BodyCapacity(8),
        item_capacity=ItemCapacity(16),
        base_temperature=TemperatureCelsius(20.0),
        shelter_factor=UnitInterval(0.25 if entity_id == LOC_CAMP else 0.0),
        visibility_factor=UnitInterval(1.0),
    )


def _alive_body(
    entity_id: str,
    *,
    location_id: str,
    health: float = 100.0,
    hunger: float = 20.0,
    thirst: float = 20.0,
    inventory: tuple[EntityId, ...] = (),
) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(health),
        hunger=Hunger(hunger),
        thirst=Thirst(thirst),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=inventory,
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _goal(
    *,
    goal_id: str,
    owner_id: AgentId,
    description: str,
    priority: float,
    outcome: GoalOutcome,
) -> Goal:
    return Goal(
        goal_id=GoalId(goal_id),
        owner_id=owner_id,
        description=description,
        priority=priority,
        status=GoalStatus.ACTIVE,
        outcome=outcome,
    )


def _reference_physical_rules() -> PhysicalRules:
    """Deterministic search/attack outcomes for sparse milestone guarantees.

    Attack damage is one-shot lethal. Exposure and metabolism are moderated so
    the surviving cohort can complete the full 48-tick window outdoors at night
    without collapsing before the scheduled lethal milestone.
    """
    return PhysicalRules(
        attack_hit_probability=1.0,
        search_base_probability=1.0,
        search_visibility_weight=0.0,
        resource_extraction_amount=1.0,
        attack_damage_min=200,
        attack_damage_max_exclusive=201,
        exposure_damage=0.5,
        metabolism_hunger=0.4,
        metabolism_thirst=0.4,
        hunger_damage=0.5,
        thirst_damage=0.5,
    )


def _build_locations() -> tuple[Location, ...]:
    # Connected diamond: camp hub with spring/grove/ridge spokes.
    return (
        _location(LOC_CAMP, name="Camp", adjacent=(LOC_SPRING, LOC_GROVE, LOC_RIDGE)),
        _location(LOC_SPRING, name="Spring", adjacent=(LOC_CAMP,)),
        _location(LOC_GROVE, name="Grove", adjacent=(LOC_CAMP,)),
        _location(LOC_RIDGE, name="Ridge", adjacent=(LOC_CAMP,)),
    )


def _build_resources() -> tuple[Resource, ...]:
    return (
        Resource(
            entity_id=EntityId(RES_WATER),
            name="SpringWater",
            kind=ResourceKind.WATER,
            location_id=EntityId(LOC_SPRING),
            quantity=6.0,
            maximum_quantity=8.0,
            regeneration_per_tick=0.25,
            unit="liters",
        ),
        Resource(
            entity_id=EntityId(RES_FOOD),
            name="BerryBush",
            kind=ResourceKind.FOOD,
            location_id=EntityId(LOC_GROVE),
            quantity=5.0,
            maximum_quantity=8.0,
            regeneration_per_tick=0.5,
            unit="portions",
        ),
    )


def _build_items() -> tuple[Item, ...]:
    return (
        Item(
            entity_id=EntityId(ITEM_FOOD_MIRA),
            name="StoredBerries",
            kind=ItemKind.FOOD,
            load=ItemLoad(1),
            location_id=None,
            holder_id=EntityId(BODY_MIRA),
        ),
    )


def _build_bodies() -> tuple[AgentBody, ...]:
    return (
        _alive_body(
            BODY_MIRA,
            location_id=LOC_GROVE,
            hunger=40.0,
            inventory=(EntityId(ITEM_FOOD_MIRA),),
        ),
        _alive_body(BODY_KAI, location_id=LOC_SPRING, thirst=45.0),
        _alive_body(BODY_ROWAN, location_id=LOC_RIDGE),
        _alive_body(BODY_SOREN, location_id=LOC_CAMP),
        # Healthy enough to survive moderated night exposure until the scheduled
        # one-shot lethal attack; health is not the kill mechanism.
        _alive_body(
            BODY_NYX,
            location_id=LOC_CAMP,
            health=80.0,
            hunger=10.0,
            thirst=10.0,
        ),
    )


def _build_weather(locations: Sequence[Location]) -> tuple[Weather, ...]:
    return tuple(
        Weather(location_id=location.entity_id, condition=WeatherCondition.CLEAR)
        for location in locations
    )


def _build_agent_specs() -> tuple[AgentRunnerSpec, ...]:
    mira = AgentId(AGENT_MIRA)
    kai = AgentId(AGENT_KAI)
    rowan = AgentId(AGENT_ROWAN)
    soren = AgentId(AGENT_SOREN)
    nyx = AgentId(AGENT_NYX)
    goals_by_agent: dict[str, tuple[Goal, ...]] = {
        AGENT_MIRA: (
            _goal(
                goal_id="goal-mira-food",
                owner_id=mira,
                description="secure-food-stores",
                priority=0.85,
                outcome=GoalOutcome(
                    kind=GoalOutcomeKind.OBTAIN_ENTITY,
                    entity_id=ITEM_FOOD_MIRA,
                ),
            ),
            _goal(
                goal_id="goal-mira-survive",
                owner_id=mira,
                description="preserve-life",
                priority=0.95,
                outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
            ),
        ),
        AGENT_KAI: (
            _goal(
                goal_id="goal-kai-water",
                owner_id=kai,
                description="tend-spring-water",
                priority=0.8,
                outcome=GoalOutcome(
                    kind=GoalOutcomeKind.REACH_PLACE,
                    place_id=LOC_SPRING,
                ),
            ),
            _goal(
                goal_id="goal-kai-survive",
                owner_id=kai,
                description="preserve-life",
                priority=0.95,
                outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
            ),
        ),
        AGENT_ROWAN: (
            _goal(
                goal_id="goal-rowan-scout",
                owner_id=rowan,
                description="scout-ridge",
                priority=0.7,
                outcome=GoalOutcome(
                    kind=GoalOutcomeKind.REACH_PLACE,
                    place_id=LOC_RIDGE,
                ),
            ),
            _goal(
                goal_id="goal-rowan-info",
                owner_id=rowan,
                description="gather-local-information",
                priority=0.6,
                outcome=GoalOutcome(
                    kind=GoalOutcomeKind.GATHER_INFORMATION,
                    outcome_code="scout-ridge-report",
                ),
            ),
        ),
        AGENT_SOREN: (
            _goal(
                goal_id="goal-soren-belong",
                owner_id=soren,
                description="maintain-camp-ties",
                priority=0.75,
                outcome=GoalOutcome(
                    kind=GoalOutcomeKind.RELATE_TO_AGENT,
                    counterpart_id=mira,
                ),
            ),
            _goal(
                goal_id="goal-soren-survive",
                owner_id=soren,
                description="preserve-life",
                priority=0.95,
                outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
            ),
        ),
        AGENT_NYX: (
            _goal(
                goal_id="goal-nyx-survive",
                owner_id=nyx,
                description="preserve-life",
                priority=1.0,
                outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
            ),
        ),
    }
    agents: list[AgentRunnerSpec] = []
    for agent_id_value, body_id_value, name in _AGENT_SPECS:
        agent_id = AgentId(agent_id_value)
        agents.append(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=EntityId(body_id_value),
                cognition=AgentCognitionSpec(
                    agent_id=agent_id,
                    memory_mode=MemoryMode.RECONSTRUCTIVE,
                    imagination_mode=ImaginationMode.ENABLED,
                ),
                name=name,
                initial_goals=goals_by_agent[agent_id_value],
            )
        )
    return tuple(agents)


def _fresh_tell(*, milestone_id: str, tick: int) -> Callable[[], AgentCommand]:
    """Build a Tell with a fresh deterministic communication id on each select."""

    def _build() -> AgentCommand:
        utterance = origin_utterance(
            text="spring-holds-water",
            speaker_id=EntityId(BODY_SOREN),
            communication_id=f"{milestone_id}-t{tick}-comm",
            concepts=("water", "spring"),
        )
        return Tell(
            recipient_id=EntityId(BODY_NYX),
            utterance=utterance,
        )

    return _build


def _build_milestones(*, death_tick: int) -> tuple[MilestoneOverride, ...]:
    kai = AgentId(AGENT_KAI)
    mira = AgentId(AGENT_MIRA)
    soren = AgentId(AGENT_SOREN)
    return (
        MilestoneOverride(
            milestone_id=MILESTONE_EXTRACT_WATER,
            tick=2,
            agent_id=kai,
            build_command=lambda: Search(target_id=EntityId(RES_WATER)),
        ),
        MilestoneOverride(
            milestone_id=MILESTONE_DRINK_WATER,
            tick=3,
            agent_id=kai,
            build_command=lambda: Drink(source_id=EntityId(RES_WATER)),
        ),
        MilestoneOverride(
            milestone_id=MILESTONE_EXTRACT_FOOD,
            tick=4,
            agent_id=mira,
            build_command=lambda: Search(target_id=EntityId(RES_FOOD)),
        ),
        MilestoneOverride(
            milestone_id=MILESTONE_EAT_FOOD,
            tick=5,
            agent_id=mira,
            build_command=lambda: Eat(item_id=EntityId(ITEM_FOOD_MIRA)),
        ),
        MilestoneOverride(
            milestone_id=MILESTONE_TELL_OBSERVE,
            tick=8,
            agent_id=soren,
            build_command=_fresh_tell(milestone_id=MILESTONE_TELL_OBSERVE, tick=8),
        ),
        # Co-locate before the lethal strike so Attack admits (same location).
        MilestoneOverride(
            milestone_id=MILESTONE_COLOCATE_ATTACKER,
            tick=max(0, death_tick - 1),
            agent_id=soren,
            build_command=lambda: Move(destination_id=EntityId(LOC_CAMP)),
        ),
        MilestoneOverride(
            milestone_id=MILESTONE_COLOCATE_VICTIM,
            tick=max(0, death_tick - 1),
            agent_id=AgentId(AGENT_NYX),
            build_command=lambda: Move(destination_id=EntityId(LOC_CAMP)),
        ),
        MilestoneOverride(
            milestone_id=MILESTONE_LETHAL_ATTACK,
            tick=death_tick,
            agent_id=soren,
            build_command=lambda: Attack(target_id=EntityId(BODY_NYX)),
        ),
    )


def _identity_fingerprint(
    *,
    scenario_id: str,
    scenario_version: str,
    max_ticks: int,
    death_tick: int,
    override_budget: int,
    milestone_ids: Sequence[str],
    agent_count: int,
    location_count: int,
    resource_count: int,
) -> str:
    payload = {
        "agent_count": agent_count,
        "death_tick": death_tick,
        "location_count": location_count,
        "max_ticks": max_ticks,
        "milestone_ids": list(milestone_ids),
        "override_budget": override_budget,
        "policy_version": MILESTONE_ARBITER_POLICY_VERSION,
        "resource_count": resource_count,
        "scenario_id": scenario_id,
        "scenario_version": scenario_version,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_reference_scenario(
    *,
    seed: int = REFERENCE_DEFAULT_SEED,
    max_ticks: int = REFERENCE_MAX_TICKS,
    death_tick: int = REFERENCE_DEATH_TICK,
    override_budget: int = REFERENCE_DEFAULT_OVERRIDE_BUDGET,
    stochastic_identity: str = REFERENCE_STOCHASTIC_IDENTITY,
) -> ReferenceScenarioBundle:
    """Build the canonical five-agent reference scenario and milestone arbiter."""
    if type(max_ticks) is not int or max_ticks < 1:
        _LOG.error(
            "scenario_invalid_ticks code=%s",
            ScenarioErrorCode.INVALID_TICKS.value,
        )
        raise ValueError("max_ticks must be a positive int")
    if type(death_tick) is not int or death_tick < 0 or death_tick >= max_ticks:
        _LOG.error(
            "scenario_invalid_death_tick code=%s",
            ScenarioErrorCode.INVALID_DEATH_TICK.value,
        )
        raise ValueError("death_tick must be in [0, max_ticks)")
    if death_tick > max_ticks // 2:
        _LOG.error(
            "scenario_invalid_death_tick code=%s",
            ScenarioErrorCode.INVALID_DEATH_TICK.value,
        )
        raise ValueError("death_tick must be within the first half of the run")
    if type(override_budget) is not int or override_budget < 0:
        _LOG.error(
            "scenario_invalid_budget code=%s",
            ScenarioErrorCode.INVALID_BUDGET.value,
        )
        raise ValueError("override_budget must be a non-negative int")

    locations = _build_locations()
    bodies = _build_bodies()
    items = _build_items()
    resources = _build_resources()
    weather = _build_weather(locations)
    agents = _build_agent_specs()
    milestones = _build_milestones(death_tick=death_tick)
    milestone_ids = tuple(item.milestone_id for item in milestones)

    scenario = WorldScenarioSpec(
        world_id=WorldId(REFERENCE_WORLD_ID),
        revision=WorldRevision(0),
        physical_rules=_reference_physical_rules(),
        locations=locations,
        bodies=bodies,
        items=items,
        resources=resources,
        weather=weather,
    )
    config = SimulationRunnerConfig(
        seed=seed,
        stochastic_identity=StochasticIdentity(stochastic_identity),
        scenario=scenario,
        agents=agents,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        mortality_mode=MortalityMode.ENABLED,
        provider=RunnerProviderSettings(
            recording_policy=RecordingPolicy.DETERMINISTIC_FAKE,
        ),
    )
    arbiter = MilestoneInterventionArbiter(
        milestones,
        override_budget=override_budget,
    )
    config_fp = runner_config_fingerprint(config)
    scenario_fp = scenario_fingerprint(config)
    identity_fp = _identity_fingerprint(
        scenario_id=REFERENCE_SCENARIO_ID,
        scenario_version=REFERENCE_SCENARIO_VERSION,
        max_ticks=max_ticks,
        death_tick=death_tick,
        override_budget=override_budget,
        milestone_ids=milestone_ids,
        agent_count=len(agents),
        location_count=len(locations),
        resource_count=len(resources),
    )
    _LOG.info(
        "reference_scenario_built scenario_id=%s scenario_version=%s "
        "agent_count=%s location_count=%s resource_count=%s milestone_count=%s "
        "max_ticks=%s override_budget=%s config_fingerprint_prefix=%s "
        "scenario_fingerprint_prefix=%s identity_fingerprint_prefix=%s",
        REFERENCE_SCENARIO_ID,
        REFERENCE_SCENARIO_VERSION,
        len(agents),
        len(locations),
        len(resources),
        len(milestones),
        max_ticks,
        override_budget,
        config_fp[:12],
        scenario_fp[:12],
        identity_fp[:12],
    )
    return ReferenceScenarioBundle(
        scenario_id=REFERENCE_SCENARIO_ID,
        scenario_version=REFERENCE_SCENARIO_VERSION,
        config=config,
        arbiter=arbiter,
        death_tick=death_tick,
        death_agent_id=AgentId(AGENT_NYX),
        death_body_id=EntityId(BODY_NYX),
        attacker_agent_id=AgentId(AGENT_SOREN),
        config_fingerprint=config_fp,
        scenario_fingerprint=scenario_fp,
        milestone_ids=milestone_ids,
        override_budget=override_budget,
    )
