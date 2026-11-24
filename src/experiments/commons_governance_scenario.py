"""Paired shared-stock commons-governance experiment layouts (off-gate)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import replace
from typing import Final

from agents.models import AgentId
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
    require_stochastic,
)
from experiments.reference_scenario import _alive_body
from simulation.commons_governance_config import (
    COMMONS_GOVERNANCE_POLICY_ID,
    CommonsGovernanceSpec,
)
from simulation.ecological_resources_config import (
    ECOLOGICAL_RESOURCES_POLICY_ID,
    EcologicalResourceNodeSpec,
    EcologicalResourcesSpec,
)
from simulation.overexploitation_config import (
    OVEREXPLOITATION_POLICY_ID,
    OverexploitationSpec,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V61,
    RUNNER_SCHEMA_VERSION_V62,
    AgentCognitionSpec,
    AgentRunnerSpec,
    InstitutionConceptMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    SocialNormMode,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from world.environment import example_environmental_dynamics
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import Location, Resource, Weather, default_physical_rules
from world.production import example_production_catalog
from world.supply_chain import supply_chain_production_catalog
from world.values import (
    BodyCapacity,
    ItemCapacity,
    ResourceKind,
    TemperatureCelsius,
    UnitInterval,
    WeatherCondition,
)

__all__ = [
    "COMMONS_GOVERNANCE_DEFAULT_MAX_TICKS",
    "COMMONS_GOVERNANCE_DEFAULT_SEEDS",
    "COMMONS_GOVERNANCE_EXPERIMENT_ID",
    "COMMONS_GOVERNANCE_TWO_POOLS_EXPERIMENT_ID",
    "SHARED_POOL_STOCK_ID",
    "TWO_POOLS_ANALYTICAL_COHORTS",
    "TWO_POOLS_STOCK_IDS",
    "commons_governance_scenario",
    "commons_governance_two_pools_scenario",
    "experiment_commons_governance",
    "experiment_commons_governance_two_pools",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.commons_governance_scenario"
)

COMMONS_GOVERNANCE_EXPERIMENT_ID: Final[str] = "commons_governance@1"
COMMONS_GOVERNANCE_TWO_POOLS_EXPERIMENT_ID: Final[str] = (
    "commons_governance_two_pools@1"
)
COMMONS_GOVERNANCE_DEFAULT_SEEDS: Final[tuple[int, ...]] = (34, 35, 36, 37, 38)
COMMONS_GOVERNANCE_DEFAULT_MAX_TICKS: Final[int] = 64

SHARED_POOL_STOCK_ID: Final[EntityId] = EntityId("res-water")
TWO_POOLS_STOCK_IDS: Final[tuple[EntityId, ...]] = (
    EntityId("res-water-a"),
    EntityId("res-water-b"),
)

# Detached research labels by start location. Never passed to the runner.
TWO_POOLS_ANALYTICAL_COHORTS: Final[Mapping[str, tuple[str, ...]]] = {
    "loc-a": ("body-a", "body-b"),
    "loc-b": ("body-c", "body-d"),
}

_LOC_COMMON: Final[str] = "loc-common"
_LOC_A: Final[str] = "loc-a"
_LOC_B: Final[str] = "loc-b"
_BODY_IDS: Final[tuple[str, ...]] = ("body-a", "body-b", "body-c", "body-d")
_NONURGENT_THIRST: Final[float] = 20.0
_STOCK_QUANTITY: Final[float] = 4.0
_STOCK_RENEWAL: Final[float] = 1.0
_ECOLOGY_FLOOR_TENTHS: Final[int] = 5
_ECOLOGY_RECOVERY_TENTHS: Final[int] = 1
_ECOLOGY_ALLOWANCE_TENTHS: Final[int] = 0


def _location(
    entity_id: str,
    name: str,
    *,
    adjacent: tuple[str, ...] = (),
    body_capacity: int = 8,
) -> Location:
    return Location(
        entity_id=EntityId(entity_id),
        name=name,
        adjacent=tuple(EntityId(item) for item in adjacent),
        body_capacity=BodyCapacity(body_capacity),
        item_capacity=ItemCapacity(16),
        base_temperature=TemperatureCelsius(20.0),
        shelter_factor=UnitInterval(0.0),
        visibility_factor=UnitInterval(1.0),
    )


def _weather(location_id: str) -> Weather:
    return Weather(
        location_id=EntityId(location_id),
        condition=WeatherCondition.CLEAR,
    )


def _water_resource(
    resource_id: EntityId,
    *,
    location_id: str,
    name: str,
) -> Resource:
    return Resource(
        entity_id=resource_id,
        name=name,
        kind=ResourceKind.WATER,
        location_id=EntityId(location_id),
        quantity=_STOCK_QUANTITY,
        maximum_quantity=_STOCK_QUANTITY,
        regeneration_per_tick=_STOCK_RENEWAL,
        unit="liters",
    )


def _ecology_node(resource_id: EntityId) -> EcologicalResourceNodeSpec:
    return EcologicalResourceNodeSpec(
        resource_id=resource_id,
        minimum_capacity_tenths=_ECOLOGY_FLOOR_TENTHS,
        withdrawal_allowance_tenths=_ECOLOGY_ALLOWANCE_TENTHS,
        recovery_tenths_per_idle_tick=_ECOLOGY_RECOVERY_TENTHS,
    )


def _ecology_spec(
    stock_ids: tuple[EntityId, ...],
) -> EcologicalResourcesSpec:
    nodes = tuple(
        sorted(
            (_ecology_node(stock_id) for stock_id in stock_ids),
            key=lambda node: node.resource_id.value,
        )
    )
    return EcologicalResourcesSpec(
        policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
        nodes=nodes,
    )


def _commons_spec(stock_ids: tuple[EntityId, ...]) -> CommonsGovernanceSpec:
    ordered = tuple(
        EntityId(value)
        for value in sorted(stock_id.value for stock_id in stock_ids)
    )
    return CommonsGovernanceSpec(
        policy_id=COMMONS_GOVERNANCE_POLICY_ID,
        stock_ids=ordered,
    )


def _agents_for(bodies: tuple[object, ...]) -> tuple[AgentRunnerSpec, ...]:
    catalog = supply_chain_production_catalog(example_production_catalog())
    agents: list[AgentRunnerSpec] = []
    for index, body in enumerate(bodies):
        agent_id = AgentId(f"agent-{index + 1}")
        agents.append(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,  # type: ignore[attr-defined]
                cognition=AgentCognitionSpec(
                    agent_id=agent_id,
                    production_catalog=catalog,
                    social_norm_mode=SocialNormMode.DETERMINISTIC,
                    institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
                ),
            )
        )
    return tuple(agents)


def _shared_pool_scenario(*, world_id: WorldId) -> WorldScenarioSpec:
    bodies = tuple(
        _alive_body(
            body_id,
            location_id=_LOC_COMMON,
            hunger=0.0,
            thirst=_NONURGENT_THIRST,
        )
        for body_id in _BODY_IDS
    )
    return WorldScenarioSpec(
        world_id=world_id,
        revision=WorldRevision(0),
        physical_rules=default_physical_rules(),
        locations=(_location(_LOC_COMMON, "Commons", body_capacity=8),),
        bodies=bodies,
        weather=(_weather(_LOC_COMMON),),
        items=(),
        resources=(
            _water_resource(
                SHARED_POOL_STOCK_ID,
                location_id=_LOC_COMMON,
                name="Shared Water",
            ),
        ),
        artifacts=(),
    )


def _two_pools_scenario(*, world_id: WorldId) -> WorldScenarioSpec:
    bodies = (
        _alive_body(
            "body-a", location_id=_LOC_A, hunger=0.0, thirst=_NONURGENT_THIRST
        ),
        _alive_body(
            "body-b", location_id=_LOC_A, hunger=0.0, thirst=_NONURGENT_THIRST
        ),
        _alive_body(
            "body-c", location_id=_LOC_B, hunger=0.0, thirst=_NONURGENT_THIRST
        ),
        _alive_body(
            "body-d", location_id=_LOC_B, hunger=0.0, thirst=_NONURGENT_THIRST
        ),
    )
    return WorldScenarioSpec(
        world_id=world_id,
        revision=WorldRevision(0),
        physical_rules=default_physical_rules(),
        locations=(
            _location(_LOC_A, "Pool A", adjacent=(_LOC_B,), body_capacity=8),
            _location(_LOC_B, "Pool B", adjacent=(_LOC_A,), body_capacity=8),
        ),
        bodies=bodies,
        weather=(_weather(_LOC_A), _weather(_LOC_B)),
        items=(),
        resources=(
            _water_resource(
                TWO_POOLS_STOCK_IDS[0],
                location_id=_LOC_A,
                name="Pool A Water",
            ),
            _water_resource(
                TWO_POOLS_STOCK_IDS[1],
                location_id=_LOC_B,
                name="Pool B Water",
            ),
        ),
        artifacts=(),
    )


def _paired_arm(
    *,
    seed: int,
    stochastic_identity: str,
    scenario: WorldScenarioSpec,
    stock_ids: tuple[EntityId, ...],
    max_ticks: int,
    enabled: bool,
) -> SimulationRunnerConfig:
    shared = SimulationRunnerConfig(
        seed=seed,
        stochastic_identity=require_stochastic(stochastic_identity),
        scenario=scenario,
        agents=_agents_for(scenario.bodies),
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        schema_version=RUNNER_SCHEMA_VERSION_V61,
        environmental_dynamics=example_environmental_dynamics(),
        ecological_resources=_ecology_spec(stock_ids),
        overexploitation=OverexploitationSpec(
            policy_id=OVEREXPLOITATION_POLICY_ID
        ),
        commons_governance=None,
        v4_capability_flags=V4CapabilityFlags(
            supply_chains=True,
            ecological_feedback=True,
            formal_rules=True,
        ),
    )
    if not enabled:
        return shared
    return replace(
        shared,
        schema_version=RUNNER_SCHEMA_VERSION_V62,
        commons_governance=_commons_spec(stock_ids),
    )


def _resolve_matrix(
    seed_matrix: ExperimentSeedMatrix | None,
) -> ExperimentSeedMatrix:
    if seed_matrix is None:
        return ExperimentSeedMatrix(seeds=COMMONS_GOVERNANCE_DEFAULT_SEEDS)
    if type(seed_matrix) is not ExperimentSeedMatrix:
        raise TypeError("commons_governance_seed_matrix_invalid")
    return seed_matrix


def _require_base(base: SimulationRunnerConfig, *, experiment_id: str) -> None:
    if type(base) is not SimulationRunnerConfig:
        _LOG.warning(
            "commons_governance_invalid reason_code=base_type experiment_id=%s",
            experiment_id,
        )
        raise TypeError("commons_governance_scenario_base_invalid")


def _require_horizon(max_ticks: int, *, experiment_id: str) -> None:
    if isinstance(max_ticks, bool) or type(max_ticks) is not int or max_ticks < 1:
        _LOG.warning(
            "commons_governance_invalid reason_code=max_ticks experiment_id=%s",
            experiment_id,
        )
        raise ValueError("commons_governance_scenario_max_ticks_invalid")


def commons_governance_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = COMMONS_GOVERNANCE_DEFAULT_MAX_TICKS,
) -> ExperimentDefinition:
    """Paired shared-pool off (v61) / on (v62) arms over one managed WATER stock."""
    _require_base(base, experiment_id=COMMONS_GOVERNANCE_EXPERIMENT_ID)
    _require_horizon(max_ticks, experiment_id=COMMONS_GOVERNANCE_EXPERIMENT_ID)
    matrix = _resolve_matrix(seed_matrix)
    seed = matrix.seeds[0]
    stochastic = (
        base.stochastic_identity.value
        if hasattr(base.stochastic_identity, "value")
        else str(base.stochastic_identity)
    )
    scenario = _shared_pool_scenario(
        world_id=WorldId("world-commons-shared-pool")
    )
    stocks = (SHARED_POOL_STOCK_ID,)
    off = _paired_arm(
        seed=seed,
        stochastic_identity=stochastic,
        scenario=scenario,
        stock_ids=stocks,
        max_ticks=max_ticks,
        enabled=False,
    )
    on = _paired_arm(
        seed=seed,
        stochastic_identity=stochastic,
        scenario=scenario,
        stock_ids=stocks,
        max_ticks=max_ticks,
        enabled=True,
    )
    conditions = (
        ExperimentCondition(
            condition_id="shared-pool-off",
            label_code="commons_governance_shared_pool_off",
            runner_config=off,
        ),
        ExperimentCondition(
            condition_id="shared-pool-on",
            label_code="commons_governance_shared_pool_on",
            runner_config=on,
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s layout=%s horizon=%s",
        COMMONS_GOVERNANCE_EXPERIMENT_ID,
        len(conditions),
        "shared-pool",
        max_ticks,
    )
    return ExperimentDefinition(
        experiment_id=COMMONS_GOVERNANCE_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{COMMONS_GOVERNANCE_EXPERIMENT_ID}-world",
    )


def commons_governance_two_pools_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = COMMONS_GOVERNANCE_DEFAULT_MAX_TICKS,
) -> ExperimentDefinition:
    """Paired two-pools off (v61) / on (v62) arms; cohorts are analyst-only."""
    _require_base(base, experiment_id=COMMONS_GOVERNANCE_TWO_POOLS_EXPERIMENT_ID)
    _require_horizon(
        max_ticks, experiment_id=COMMONS_GOVERNANCE_TWO_POOLS_EXPERIMENT_ID
    )
    matrix = _resolve_matrix(seed_matrix)
    seed = matrix.seeds[0]
    stochastic = (
        base.stochastic_identity.value
        if hasattr(base.stochastic_identity, "value")
        else str(base.stochastic_identity)
    )
    scenario = _two_pools_scenario(world_id=WorldId("world-commons-two-pools"))
    stocks = TWO_POOLS_STOCK_IDS
    off = _paired_arm(
        seed=seed,
        stochastic_identity=stochastic,
        scenario=scenario,
        stock_ids=stocks,
        max_ticks=max_ticks,
        enabled=False,
    )
    on = _paired_arm(
        seed=seed,
        stochastic_identity=stochastic,
        scenario=scenario,
        stock_ids=stocks,
        max_ticks=max_ticks,
        enabled=True,
    )
    conditions = (
        ExperimentCondition(
            condition_id="two-pools-off",
            label_code="commons_governance_two_pools_off",
            runner_config=off,
        ),
        ExperimentCondition(
            condition_id="two-pools-on",
            label_code="commons_governance_two_pools_on",
            runner_config=on,
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s layout=%s horizon=%s",
        COMMONS_GOVERNANCE_TWO_POOLS_EXPERIMENT_ID,
        len(conditions),
        "two-pools",
        max_ticks,
    )
    return ExperimentDefinition(
        experiment_id=COMMONS_GOVERNANCE_TWO_POOLS_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{COMMONS_GOVERNANCE_TWO_POOLS_EXPERIMENT_ID}-world",
    )


def experiment_commons_governance(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = COMMONS_GOVERNANCE_DEFAULT_MAX_TICKS,
) -> ExperimentDefinition:
    return commons_governance_scenario(
        base, seed_matrix=seed_matrix, max_ticks=max_ticks
    )


def experiment_commons_governance_two_pools(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = COMMONS_GOVERNANCE_DEFAULT_MAX_TICKS,
) -> ExperimentDefinition:
    return commons_governance_two_pools_scenario(
        base, seed_matrix=seed_matrix, max_ticks=max_ticks
    )
