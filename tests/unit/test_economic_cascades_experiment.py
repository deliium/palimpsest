# mypy: ignore-errors
"""Off-gate ``economic_cascades@1`` registration and arm discipline."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.catalog import (
    EXPERIMENT_A_V1_CONDITION_IDS,
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    base_runner_config_from_scenario,
    experiment_economic_cascades,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _base():
    bodies = tuple(alive_body(f"body-{index}") for index in range(2))
    specs = tuple(
        AgentRunnerSpec(
            agent_id=AgentId(f"agent-{index}"),
            entity_id=body.entity_id,
            cognition=AgentCognitionSpec(agent_id=AgentId(f"agent-{index}")),
        )
        for index, body in enumerate(bodies)
    )
    return base_runner_config_from_scenario(
        seed=17,
        stochastic_identity="cmp-v4-economic-cascades",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-economic-cascades"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location("loc-0"), make_location("loc-1")),
            bodies=bodies,
            weather=(make_weather("loc-0"), make_weather("loc-1")),
        ),
        agents=specs,
        max_ticks=96,
    )


def test_experiment_is_registered_once_and_off_gate() -> None:
    definition = experiment_economic_cascades(_base())
    assert definition.experiment_id == "economic_cascades@1"
    assert "economic_cascades@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "economic_cascades@1" not in EXPERIMENT_A_V1_CONDITION_IDS


def test_three_arms_are_ordered_and_valid_v56() -> None:
    definition = experiment_economic_cascades(_base())
    assert [condition.condition_id for condition in definition.conditions] == [
        "cascade-baseline",
        "cascade-production",
        "cascade-full",
    ]
    baseline, production, full = (
        condition.runner_config for condition in definition.conditions
    )
    for config in (baseline, production, full):
        assert config.schema_version == RUNNER_SCHEMA_VERSION_V56
        assert config.stop_policy.max_ticks == 96
        assert config.v4_capability_flags.science is False
        assert config.v4_capability_flags.epidemics is False
        assert config.v4_capability_flags.ecological_feedback is False
        assert config.v4_capability_flags.disasters is False

    assert baseline.v4_capability_flags.supply_chains is False
    assert production.v4_capability_flags.supply_chains is True
    assert full.v4_capability_flags.supply_chains is True
    assert full.v4_capability_flags.infrastructure_networks is True
    assert full.v3_capability_flags.multi_polity_migration is True
    assert full.regions_migration is not None
    assert full.mortality_mode is MortalityMode.ENABLED


def test_baseline_has_the_legacy_catalog_and_no_chain_evidence() -> None:
    baseline = experiment_economic_cascades(_base()).conditions[0].runner_config
    assert all(
        agent.cognition.production_catalog.recipe_count == 6
        for agent in baseline.agents
    )


def test_production_and_full_arms_use_the_chain_catalog() -> None:
    production, full = (
        condition.runner_config
        for condition in experiment_economic_cascades(_base()).conditions[1:]
    )
    for config in (production, full):
        assert all(
            agent.cognition.production_catalog.recipe_count == 12
            for agent in config.agents
        )


def test_short_horizon_is_rejected() -> None:
    with pytest.raises(ValueError, match="economic_cascades_min_ticks"):
        experiment_economic_cascades(_base(), max_ticks=95)
