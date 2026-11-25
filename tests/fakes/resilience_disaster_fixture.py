# mypy: ignore-errors
"""Shared V4-39 drought stock fixture for societal-resilience qualification."""

from __future__ import annotations

from dataclasses import replace

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.disasters_config import DISASTERS_POLICY_ID, DisastersSpec
from simulation.ecological_resources_config import (
    ECOLOGICAL_RESOURCES_POLICY_ID,
    EcologicalResourceNodeSpec,
    EcologicalResourcesSpec,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V63,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_resource,
    make_weather,
)
from world.disasters import (
    DisasterKind,
    DisasterLossEffect,
    DisasterResourceTarget,
    DisasterRule,
    DisasterScheduleEntry,
)
from world.environment import example_environmental_dynamics
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.production import example_production_catalog
from world.supply_chain import supply_chain_production_catalog
from world.values import ResourceKind, WeatherCondition

DROUGHT_INJECT_TICK = 2
DROUGHT_RULE_ID = "drought-a"
DROUGHT_SEED = 34
DROUGHT_MAX_TICKS = 8


def drought_loss_rule(
    *,
    rule_id: str = DROUGHT_RULE_ID,
    resource_id: str = "res-target",
    chance_ppm: int = 0,
    loss_tenths: int = 10,
) -> DisasterRule:
    return DisasterRule(
        rule_id=rule_id,
        kind=DisasterKind.DROUGHT,
        chance_ppm=chance_ppm,
        target=DisasterResourceTarget(resource_id=EntityId(resource_id)),
        effect=DisasterLossEffect(loss_tenths=loss_tenths),
    )


def drought_schedule_entry(
    *, tick: int = DROUGHT_INJECT_TICK, rule_id: str = DROUGHT_RULE_ID
) -> DisasterScheduleEntry:
    return DisasterScheduleEntry(tick=tick, rule_id=rule_id)


def drought_stock_base(
    *,
    seed: int = DROUGHT_SEED,
    max_ticks: int = DROUGHT_MAX_TICKS,
    rule: DisasterRule | None = None,
) -> SimulationRunnerConfig:
    """Exact V4-39 drought stock arm base (seed 34, water target, clear weather)."""

    active_rule = drought_loss_rule() if rule is None else rule
    body = alive_body("body-a", location_id="loc-a")
    agent_id = AgentId("agent-1")
    target = make_resource(
        "res-target",
        name="Target",
        kind=ResourceKind.WATER,
        location_id="loc-a",
        quantity=4.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    other = make_resource(
        "res-other",
        name="Other",
        kind=ResourceKind.FOOD,
        location_id="loc-a",
        quantity=3.0,
        maximum_quantity=3.0,
        regeneration_per_tick=0.5,
    )
    catalog = supply_chain_production_catalog(example_production_catalog())
    base = base_runner_config_from_scenario(
        seed=seed,
        stochastic_identity="disasters-pair",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-disasters-stock"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location("loc-a"),),
            bodies=(body,),
            weather=(make_weather("loc-a", condition=WeatherCondition.CLEAR),),
            resources=(target, other),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=max_ticks,
    )
    agent = base.agents[0]
    nodes = tuple(
        sorted(
            (
                EcologicalResourceNodeSpec(
                    resource_id=EntityId(resource_id),
                    minimum_capacity_tenths=5,
                    withdrawal_allowance_tenths=0,
                    recovery_tenths_per_idle_tick=1,
                )
                for resource_id in ("res-target", "res-other")
            ),
            key=lambda node: node.resource_id.value,
        )
    )
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V63,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(
            max_ticks=max_ticks, stop_on_all_agents_terminal=False
        ),
        environmental_dynamics=example_environmental_dynamics(),
        ecological_resources=EcologicalResourcesSpec(
            policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
            nodes=nodes,
        ),
        disasters=DisastersSpec(
            policy_id=DISASTERS_POLICY_ID,
            rules=(active_rule,),
            schedule=(),
        ),
        v4_capability_flags=V4CapabilityFlags(
            supply_chains=True,
            ecological_feedback=True,
            disasters=True,
        ),
        agents=(
            replace(
                agent,
                cognition=replace(agent.cognition, production_catalog=catalog),
            ),
        ),
    )
