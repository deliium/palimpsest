# mypy: ignore-errors

"""Paired commons-governance experiment layouts and catalog registration."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    base_runner_config_from_scenario,
    experiment_commons_governance,
    experiment_commons_governance_two_pools,
)
from experiments.commons_governance_scenario import (
    COMMONS_GOVERNANCE_DEFAULT_SEEDS,
    COMMONS_GOVERNANCE_EXPERIMENT_ID,
    COMMONS_GOVERNANCE_TWO_POOLS_EXPERIMENT_ID,
    SHARED_POOL_STOCK_ID,
    TWO_POOLS_ANALYTICAL_COHORTS,
    TWO_POOLS_STOCK_IDS,
    commons_governance_scenario,
    commons_governance_two_pools_scenario,
)
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
)
from simulation.commons_governance_config import COMMONS_GOVERNANCE_POLICY_ID
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V61,
    RUNNER_SCHEMA_VERSION_V62,
    AgentCognitionSpec,
    AgentRunnerSpec,
    InstitutionConceptMode,
    SocialNormMode,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.values import ResourceKind

pytestmark = pytest.mark.unit


def _base():
    body = alive_body("body-seed")
    agent_id = AgentId("agent-seed")
    return base_runner_config_from_scenario(
        seed=7,
        stochastic_identity="commons-governance-pair",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-commons-seed"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location("loc-seed"),),
            bodies=(body,),
            weather=(make_weather("loc-seed"),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=8,
    )


def _strip_selector(config):
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V61,
        commons_governance=None,
    )


def test_both_definitions_registered_off_gate() -> None:
    assert COMMONS_GOVERNANCE_EXPERIMENT_ID == "commons_governance@1"
    assert (
        COMMONS_GOVERNANCE_TWO_POOLS_EXPERIMENT_ID
        == "commons_governance_two_pools@1"
    )
    assert "commons_governance@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "commons_governance_two_pools@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    shared = experiment_commons_governance(_base())
    two = experiment_commons_governance_two_pools(_base())
    assert shared.experiment_id == COMMONS_GOVERNANCE_EXPERIMENT_ID
    assert two.experiment_id == COMMONS_GOVERNANCE_TWO_POOLS_EXPERIMENT_ID


def test_shared_pool_pair_equality_and_stock() -> None:
    definition = commons_governance_scenario(_base())
    assert definition.seed_matrix.seeds == COMMONS_GOVERNANCE_DEFAULT_SEEDS
    assert len(definition.conditions) == 2
    assert definition.paired_world_group == f"{COMMONS_GOVERNANCE_EXPERIMENT_ID}-world"
    by_id = {
        condition.condition_id: condition.runner_config
        for condition in definition.conditions
    }
    off = by_id["shared-pool-off"]
    on = by_id["shared-pool-on"]
    assert off.schema_version == RUNNER_SCHEMA_VERSION_V61
    assert on.schema_version == RUNNER_SCHEMA_VERSION_V62
    assert off.commons_governance is None
    assert on.commons_governance is not None
    assert on.commons_governance.policy_id == COMMONS_GOVERNANCE_POLICY_ID
    assert on.commons_governance.stock_ids == (SHARED_POOL_STOCK_ID,)
    assert _strip_selector(off) == _strip_selector(on)
    assert off.scenario == on.scenario
    assert off.seed == on.seed == 34
    assert off.stochastic_identity == on.stochastic_identity
    assert off.stop_policy.max_ticks == 64
    assert len(off.scenario.bodies) == 4
    assert len(off.scenario.locations) == 1
    assert len(off.scenario.resources) == 1
    resource = off.scenario.resources[0]
    assert resource.kind is ResourceKind.WATER
    assert resource.quantity == 4.0
    assert resource.maximum_quantity == 4.0
    assert resource.regeneration_per_tick == 1.0
    node = off.ecological_resources.nodes[0]
    assert node.minimum_capacity_tenths == 5
    assert node.recovery_tenths_per_idle_tick == 1
    assert node.withdrawal_allowance_tenths == 0
    assert off.environmental_dynamics.shortage_windows == ()
    for config in (off, on):
        assert config.v4_capability_flags.formal_rules is True
        assert config.v4_capability_flags.ecological_feedback is True
        assert config.v4_capability_flags.supply_chains is True
        assert config.overexploitation is not None
        for agent in config.agents:
            assert agent.cognition.social_norm_mode is SocialNormMode.DETERMINISTIC
            assert (
                agent.cognition.institution_concept_mode
                is InstitutionConceptMode.DETERMINISTIC
            )
            assert agent.initial_goals == ()
        for body in config.scenario.bodies:
            assert body.thirst.value == 20.0


def test_two_pools_layout_cohorts_and_travel() -> None:
    definition = commons_governance_two_pools_scenario(_base())
    assert definition.paired_world_group == (
        f"{COMMONS_GOVERNANCE_TWO_POOLS_EXPERIMENT_ID}-world"
    )
    by_id = {
        condition.condition_id: condition.runner_config
        for condition in definition.conditions
    }
    off = by_id["two-pools-off"]
    on = by_id["two-pools-on"]
    assert off.schema_version == RUNNER_SCHEMA_VERSION_V61
    assert on.schema_version == RUNNER_SCHEMA_VERSION_V62
    assert on.commons_governance.stock_ids == TWO_POOLS_STOCK_IDS
    assert _strip_selector(off) == _strip_selector(on)
    locations = {loc.entity_id.value: loc for loc in off.scenario.locations}
    assert set(locations) == {"loc-a", "loc-b"}
    assert EntityId("loc-b") in locations["loc-a"].adjacent
    assert EntityId("loc-a") in locations["loc-b"].adjacent
    assert len(off.scenario.resources) == 2
    assert all(row.regeneration_per_tick == 1.0 for row in off.scenario.resources)
    start_locations = {
        body.entity_id.value: body.location_id.value
        for body in off.scenario.bodies
    }
    for location_id, members in TWO_POOLS_ANALYTICAL_COHORTS.items():
        assert len(members) == 2
        for body_id in members:
            assert start_locations[body_id] == location_id
    # Cohort labels stay detached from runner config.
    encoded_agents = tuple(
        (agent.agent_id.value, agent.entity_id.value) for agent in off.agents
    )
    assert "cohort" not in str(encoded_agents).lower()
    assert definition.seed_matrix.seeds == COMMONS_GOVERNANCE_DEFAULT_SEEDS


def test_combining_layouts_fails_experiment_validation() -> None:
    shared = commons_governance_scenario(_base())
    two = commons_governance_two_pools_scenario(_base())
    with pytest.raises(ValueError, match="identical scenario"):
        ExperimentDefinition(
            experiment_id="commons_governance_mixed@1",
            schema_version=EXPERIMENT_SCHEMA_VERSION,
            seed_matrix=shared.seed_matrix,
            conditions=(
                shared.conditions[0],
                ExperimentCondition(
                    condition_id="two-pools-on",
                    label_code="commons_governance_two_pools_on",
                    runner_config=two.conditions[1].runner_config,
                ),
            ),
            paired_world_group="commons-governance-mixed-world",
        )


@pytest.mark.asyncio
async def test_all_four_arms_construct_runners() -> None:
    shared = commons_governance_scenario(_base())
    two = commons_governance_two_pools_scenario(_base())
    configs = [condition.runner_config for condition in shared.conditions] + [
        condition.runner_config for condition in two.conditions
    ]
    for index, config in enumerate(configs):
        runner = await SimulationRunner.from_config(
            replace(config, stop_policy=replace(config.stop_policy, max_ticks=1)),
            run_id=RunId(f"run-commons-arm-{index}"),
            factories=RunnerDependencyFactories(),
        )
        async with runner:
            result = await runner.run()
        assert result is not None
