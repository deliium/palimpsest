"""Experiment BN recipes and the named food-opportunity fixture."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Final, Literal

from agents.models import AgentId
from experiments.generational_comparison_base import generational_comparison_base
from experiments.path_dependence_catalog import (
    BN_HISTORICAL_CONTINGENCY,
    GroupedExperimentRegistration,
    register_path_dependence_builder,
)
from experiments.path_dependence_models import (
    PATH_DEPENDENCE_EXPERIMENT_ID,
    ArmRole,
    CommonSetupCommand,
    ForkTickSchedule,
    GiveInterventionAction,
    OutcomeDomain,
    OutcomeSelector,
    OutcomeWindow,
    PathDependenceArm,
    PathDependenceSpec,
    ProtocolContrast,
    ScheduledCommandIntervention,
    WaitInterventionAction,
)
from simulation.clock import Tick
from simulation.fork_checkpoint import RunnerForkCheckpoint
from simulation.generational_models import GenerationalRunSpec
from simulation.models import RunId
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_DEVELOPMENTAL_V1,
    default_new_agent_initialization_spec,
)
from simulation.runner_models import (
    ArtifactInterpretationMode,
    CulturalNarrativeMode,
    InstitutionConceptMode,
    PopulationLifecycleSpec,
    RunnerStopPolicy,
    SemanticNamingMode,
    SimulationRunnerConfig,
    SocialConventionMode,
    SocialNormMode,
    default_lifespan_distribution_spec,
    example_knowledge_genealogy_spec,
)
from world.actions import Wait
from world.identifiers import EntityId
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold
from world.models import AgentBody, Item, LifeStatus, Location, Resource
from world.values import (
    BodyCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemCapacity,
    ItemKind,
    ItemLoad,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
)

_LOG: Final[logging.Logger] = logging.getLogger("experiments.path_dependence_scenario")

FIXTURE_ID: Final[str] = "bn-food-opportunity-v1"
FOUNDER_AGENT_ID: Final[str] = "agent-origin"
FOUNDER_BODY_ID: Final[str] = "body-origin"
RECIPIENT_BODY_ID: Final[str] = "body-spring"
RESERVED_FOOD_ID: Final[str] = "bn-reserved-food"
_HOME_LOCATION: Final[str] = "loc-origin"
_SPAWN_LOCATIONS: Final[tuple[str, ...]] = (
    "loc-origin",
    "loc-spring",
    "loc-grain",
    "loc-remote",
)
_SELECTOR_DOMAINS: Final[tuple[tuple[str, OutcomeDomain], ...]] = (
    ("norms.active_beliefs", OutcomeDomain.NORMS),
    ("norms.belief_persistence", OutcomeDomain.NORMS),
    ("relationships.mean_abs_delta", OutcomeDomain.RELATIONSHIPS),
    ("institutions.persistent_candidates", OutcomeDomain.INSTITUTIONS),
    ("technology.living_retention", OutcomeDomain.TECHNOLOGY),
    ("narratives.endpoint_persistence", OutcomeDomain.CULTURAL_NARRATIVES),
    ("inequality.resource_gini", OutcomeDomain.INEQUALITY),
    ("inequality.resource_theil", OutcomeDomain.INEQUALITY),
    ("cooperation.applied_rate", OutcomeDomain.COOPERATION),
)


class PrefixEligibilityError(ValueError):
    """Invalid eligibility request (not an ordinary ineligible prefix)."""


@dataclass(frozen=True, slots=True)
class FoodOpportunityWitness:
    """Frozen pre-treatment founder/item/recipient witness."""

    founder_agent_id: AgentId
    founder_body_id: EntityId
    recipient_body_id: EntityId
    item_id: EntityId
    item_name: str
    location_id: EntityId


@dataclass(frozen=True, slots=True)
class PrefixEligibility:
    """Scientific eligibility result for one parent boundary."""

    eligible: bool
    reason_code: str
    witness: FoodOpportunityWitness | None = None


def _fixture_lifecycle(
    *, lifespan_ticks: int, interval_ticks: int, generation_length_ticks: int
) -> PopulationLifecycleSpec:
    return PopulationLifecycleSpec(
        lifespan_ticks=lifespan_ticks,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 2),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 4),
            LifecycleStageThreshold(
                LifecycleStageId("adult"), max(5, lifespan_ticks - 1)
            ),
        ),
        dependent_until_stage=LifecycleStageId("juvenile"),
        demographic_policy_id="generational_interval_entry",
        demographic_policy_params={
            "interval_ticks": interval_ticks,
            "entries_per_interval": 1,
            "generation_length_ticks": generation_length_ticks,
            "name_prefix": "entrant",
            "cohort_id_prefix": "cohort",
            "spawn_location_ids": list(_SPAWN_LOCATIONS),
        },
        max_population=16,
        natural_death_on_lifespan=True,
        lifespan_distribution=default_lifespan_distribution_spec(),
    )


def _fixture_items(
    items: tuple[Item, ...], *, founder_body_id: EntityId
) -> tuple[Item, ...]:
    if any(item.entity_id == EntityId(RESERVED_FOOD_ID) for item in items):
        raise ValueError("reserved food id already exists")
    return (
        *items,
        Item(
            entity_id=EntityId(RESERVED_FOOD_ID),
            name="Reserved food",
            kind=ItemKind.FOOD,
            load=ItemLoad(1),
            holder_id=founder_body_id,
        ),
    )


def _fixture_bodies(
    bodies: tuple[AgentBody, ...], *, reserved_food_id: EntityId
) -> tuple[AgentBody, ...]:
    result: list[AgentBody] = []
    for body in bodies:
        inventory = tuple(body.inventory)
        if body.entity_id == EntityId(FOUNDER_BODY_ID):
            if reserved_food_id not in inventory:
                inventory = (*inventory, reserved_food_id)
            location = EntityId(_HOME_LOCATION)
        elif body.entity_id == EntityId(RECIPIENT_BODY_ID):
            location = EntityId(_HOME_LOCATION)
        else:
            location = body.location_id
        result.append(
            replace(
                body,
                location_id=location,
                health=Health(100.0),
                hunger=Hunger(0.0),
                thirst=Thirst(0.0),
                fatigue=Fatigue(0.0),
                temperature=TemperatureCelsius(37.0),
                inventory=inventory,
                life_status=LifeStatus.ALIVE,
            )
        )
    return tuple(result)


def _fixture_resources(
    resources: tuple[Resource, ...], locations: tuple[Location, ...]
) -> tuple[Resource, ...]:
    by_location: dict[str, dict[ResourceKind, Resource]] = {}
    for resource in resources:
        by_location.setdefault(resource.location_id.value, {})[resource.kind] = resource
    result: list[Resource] = []
    for location in locations:
        existing = by_location.get(location.entity_id.value, {})
        for kind, name, unit, prefix in (
            (ResourceKind.FOOD, "Regenerating food", "portions", "bn-food"),
            (ResourceKind.WATER, "Regenerating water", "litres", "bn-water"),
        ):
            existing_resource = existing.get(kind)
            if existing_resource is None:
                result.append(
                    Resource(
                        entity_id=EntityId(f"{prefix}-{location.entity_id.value}"),
                        name=name,
                        kind=kind,
                        location_id=location.entity_id,
                        quantity=100.0,
                        maximum_quantity=100.0,
                        regeneration_per_tick=10.0,
                        unit=unit,
                    )
                )
            else:
                result.append(
                    replace(
                        existing_resource,
                        quantity=100.0,
                        maximum_quantity=100.0,
                        regeneration_per_tick=10.0,
                        unit=unit,
                    )
                )
    return tuple(result)


def _fixture_config(
    *, seed: int, profile: Literal["long", "smoke"]
) -> SimulationRunnerConfig:
    if profile == "long":
        horizon, lifespan, interval, generation = 1100, 240, 20, 40
    elif profile == "smoke":
        horizon, lifespan, interval, generation = 36, 12, 2, 4
    else:
        raise ValueError("unknown path-dependence profile")
    base = generational_comparison_base(seed=seed, max_ticks=horizon)
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                social_norm_mode=SocialNormMode.DETERMINISTIC,
                social_convention_mode=SocialConventionMode.DETERMINISTIC,
                semantic_naming_mode=SemanticNamingMode.DETERMINISTIC,
                artifact_interpretation_mode=(
                    ArtifactInterpretationMode.DETERMINISTIC
                ),
                cultural_narrative_mode=CulturalNarrativeMode.DETERMINISTIC,
                institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
            ),
        )
        for agent in base.agents
    )
    locations = tuple(
        replace(
            location,
            body_capacity=BodyCapacity(16),
            item_capacity=ItemCapacity(24),
        )
        for location in base.scenario.locations
    )
    reserved_food_id = EntityId(RESERVED_FOOD_ID)
    scenario = replace(
        base.scenario,
        physical_rules=replace(
            base.scenario.physical_rules,
            metabolism_hunger=0.1,
            metabolism_thirst=0.1,
            metabolism_fatigue=0.1,
            temperature_lerp_factor=0.0,
        ),
        locations=locations,
        bodies=_fixture_bodies(
            base.scenario.bodies, reserved_food_id=reserved_food_id
        ),
        items=_fixture_items(
            base.scenario.items, founder_body_id=EntityId(FOUNDER_BODY_ID)
        ),
        resources=_fixture_resources(base.scenario.resources, locations),
    )
    return replace(
        base,
        agents=agents,
        scenario=scenario,
        stop_policy=RunnerStopPolicy(
            max_ticks=horizon, stop_on_all_agents_terminal=False
        ),
        population_lifecycle=_fixture_lifecycle(
            lifespan_ticks=lifespan,
            interval_ticks=interval,
            generation_length_ticks=generation,
        ),
        new_agent_initialization=replace(
            default_new_agent_initialization_spec(),
            species_defaults_id=SPECIES_DEFAULT_DEVELOPMENTAL_V1,
        ),
        generational_run=GenerationalRunSpec(
            max_generation_index=16 if profile == "smoke" else 40,
            stop_on_extinction=False,
            criterion_cadence_ticks=1,
        ),
        knowledge_genealogy=example_knowledge_genealogy_spec(),
    )


def historical_contingency_scenario(
    *,
    seed: int = 23,
    profile: Literal["long", "smoke"] = "smoke",
) -> PathDependenceSpec:
    """Build the explicit BN food-opportunity recipe for one profile."""
    config = _fixture_config(seed=seed, profile=profile)
    fork_tick = Tick(4 if profile == "smoke" else 100)
    horizon = Tick(36 if profile == "smoke" else 1100)
    founder = AgentId(FOUNDER_AGENT_ID)
    recipient = EntityId(RECIPIENT_BODY_ID)
    food = EntityId(RESERVED_FOOD_ID)
    setup = tuple(
        CommonSetupCommand(
            actor_id=actor,
            tick=Tick(tick),
            command=Wait(),
        )
        for actor in (founder, AgentId("agent-spring"))
        for tick in range(fork_tick.value)
    )
    arms = (
        PathDependenceArm(
            arm_id="share",
            label_code="SHARE",
            role=ArmRole.TREATMENT,
            schedule_by_fork_tick=(
                ForkTickSchedule(
                    fork_tick,
                    (
                        ScheduledCommandIntervention(
                            "share-food",
                            founder,
                            fork_tick,
                            GiveInterventionAction(food, recipient),
                        ),
                    ),
                ),
            ),
        ),
        PathDependenceArm(
            arm_id="withhold",
            label_code="WITHHOLD",
            role=ArmRole.CONTROL,
            schedule_by_fork_tick=(
                ForkTickSchedule(
                    fork_tick,
                    (
                        ScheduledCommandIntervention(
                            "withhold-food",
                            founder,
                            fork_tick,
                            WaitInterventionAction(),
                        ),
                    ),
                ),
            ),
        ),
    )
    return PathDependenceSpec(
        base=config,
        seeds=(seed,),
        replicates_per_seed=1,
        fork_ticks=(fork_tick,),
        horizon_tick=horizon,
        arms=arms,
        contrasts=(
            ProtocolContrast("share-vs-withhold", "withhold", "share"),
        ),
        windows=(
            OutcomeWindow(
                "post-fork", fork_tick, fork_tick, horizon
            ),
        ),
        selectors=tuple(
            OutcomeSelector(selector_id, domain, "post-fork")
            for selector_id, domain in _SELECTOR_DOMAINS
        ),
        assignment_seed=seed + 1,
        common_setup=setup,
        max_interventions_per_arm=4,
    )


def resolve_food_opportunity_eligibility(
    checkpoint: RunnerForkCheckpoint,
    *,
    founder_agent_id: str = FOUNDER_AGENT_ID,
    recipient_body_id: str = RECIPIENT_BODY_ID,
    item_id: str = RESERVED_FOOD_ID,
    run_id: str | None = None,
) -> PrefixEligibility:
    """Resolve the frozen pre-treatment witness without selecting outcomes."""
    if type(checkpoint) is not RunnerForkCheckpoint:
        raise TypeError("checkpoint must be RunnerForkCheckpoint")
    if run_id is not None and checkpoint.run_id != RunId(run_id):
        raise PrefixEligibilityError("run_id mismatch")
    founder = AgentId(founder_agent_id)
    registration = next(
        (
            item
            for item in checkpoint.registrations
            if item.agent_id == founder
        ),
        None,
    )
    if registration is None:
        return PrefixEligibility(False, "missing_founder")
    bodies = {body.entity_id: body for body in checkpoint.snapshot.bodies}
    founder_body = bodies.get(registration.entity_id)
    if founder_body is None:
        return PrefixEligibility(False, "missing_founder")
    if founder_body.life_status is not LifeStatus.ALIVE:
        return PrefixEligibility(False, "dead_founder")
    recipient_entity = EntityId(recipient_body_id)
    recipient_body = bodies.get(recipient_entity)
    if recipient_body is None:
        return PrefixEligibility(False, "missing_recipient")
    if recipient_body.life_status is not LifeStatus.ALIVE:
        return PrefixEligibility(False, "dead_recipient")
    if recipient_body.entity_id == founder_body.entity_id:
        return PrefixEligibility(False, "recipient_is_founder")
    if recipient_body.location_id != founder_body.location_id:
        return PrefixEligibility(False, "not_colocated")
    item_entity = EntityId(item_id)
    item = next(
        (
            value
            for value in checkpoint.snapshot.items
            if value.entity_id == item_entity
        ),
        None,
    )
    if item is None:
        return PrefixEligibility(False, "missing_item")
    if item.holder_id != founder_body.entity_id:
        return PrefixEligibility(False, "invalid_custody")
    if item.kind is not ItemKind.FOOD or item.load.value < 1:
        return PrefixEligibility(False, "non_transferable_food")
    witness = FoodOpportunityWitness(
        founder_agent_id=founder,
        founder_body_id=founder_body.entity_id,
        recipient_body_id=recipient_body.entity_id,
        item_id=item.entity_id,
        item_name=item.name,
        location_id=founder_body.location_id,
    )
    _LOG.info(
        "path_dependence_prefix_eligible fixture=%s founder=%s recipient=%s "
        "item=%s location=%s",
        FIXTURE_ID,
        founder.value,
        recipient_body_id,
        item_id,
        witness.location_id.value,
    )
    return PrefixEligibility(True, "eligible", witness)


def experiment_bn_historical_contingency() -> GroupedExperimentRegistration:
    """Return the grouped-only BN catalog registration."""
    return BN_HISTORICAL_CONTINGENCY


register_path_dependence_builder(
    PATH_DEPENDENCE_EXPERIMENT_ID, historical_contingency_scenario
)

__all__ = [
    "FIXTURE_ID",
    "FOUNDER_AGENT_ID",
    "FOUNDER_BODY_ID",
    "RECIPIENT_BODY_ID",
    "RESERVED_FOOD_ID",
    "FoodOpportunityWitness",
    "PrefixEligibility",
    "PrefixEligibilityError",
    "experiment_bn_historical_contingency",
    "historical_contingency_scenario",
    "resolve_food_opportunity_eligibility",
]
