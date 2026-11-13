"""Off-gate ``economic_inequality@1`` registration and arm discipline."""

# mypy: ignore-errors

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.catalog import (
    EXPERIMENT_A_V1_CONDITION_IDS,
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    base_runner_config_from_scenario,
    experiment_economic_inequality,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _base():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=13,
        stochastic_identity="cmp-v4-economic-inequality",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-economic-inequality"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=96,
    )


def test_experiment_is_registered_once_and_off_gate() -> None:
    definition = experiment_economic_inequality(_base())
    assert definition.experiment_id == "economic_inequality@1"
    assert "economic_inequality@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "economic_inequality@1" not in EXPERIMENT_A_V1_CONDITION_IDS


def test_three_arms_differ_by_declared_channels() -> None:
    definition = experiment_economic_inequality(_base())
    assert [condition.condition_id for condition in definition.conditions] == [
        "ei-baseline",
        "ei-access",
        "ei-full",
    ]
    baseline, access, full = (
        condition.runner_config for condition in definition.conditions
    )
    assert baseline.schema_version == RUNNER_SCHEMA_VERSION_V56
    assert baseline.v4_capability_flags.organizations is False
    assert baseline.v4_capability_flags.markets_credit is False
    assert baseline.v4_capability_flags.infrastructure_networks is False
    assert baseline.durable_records is None
    assert baseline.structured_commitments is None
    assert baseline.subjective_valuation is None

    assert access.v4_capability_flags.infrastructure_networks is True
    assert access.durable_records is not None
    assert access.knowledge_repositories is not None
    assert access.collective_projects is not None

    assert full.v4_capability_flags.organizations is True
    assert full.v4_capability_flags.markets_credit is True
    assert full.structured_commitments is not None
    assert full.subjective_valuation is not None


def test_every_arm_keeps_a_finite_horizon() -> None:
    definition = experiment_economic_inequality(_base())
    for condition in definition.conditions:
        stop = condition.runner_config.stop_policy
        assert stop.max_ticks is not None
        assert stop.max_ticks >= 96


def test_short_horizon_is_rejected() -> None:
    with pytest.raises(ValueError, match="three_windows"):
        experiment_economic_inequality(_base(), max_ticks=32)
