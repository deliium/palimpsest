"""Off-gate ``emergent_prices@1`` registration and arm discipline."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.catalog import (
    EXPERIMENT_A_V1_CONDITION_IDS,
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    base_runner_config_from_scenario,
    experiment_emergent_prices,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CommunicationStrategyMode,
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
        stochastic_identity="cmp-v4-prices",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-prices"),
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
    definition = experiment_emergent_prices(_base())
    assert definition.experiment_id == "emergent_prices@1"
    assert "emergent_prices@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert "emergent_prices@1" not in EXPERIMENT_A_V1_CONDITION_IDS


def test_four_arms_differ_only_by_declared_seams() -> None:
    definition = experiment_emergent_prices(_base())
    assert [condition.condition_id for condition in definition.conditions] == [
        "ep-flag-off",
        "ep-valuation-only",
        "ep-prices-on",
        "ep-prices-quotes",
    ]
    flag_off, valuation_only, prices_on, prices_quotes = (
        condition.runner_config for condition in definition.conditions
    )
    assert flag_off.v4_capability_flags.markets_credit is False
    assert flag_off.subjective_valuation is None
    assert flag_off.resource_exchange_profile is None
    assert valuation_only.v4_capability_flags.markets_credit is False
    assert valuation_only.subjective_valuation is not None
    assert valuation_only.resource_exchange_profile is not None
    assert prices_on.v4_capability_flags.markets_credit is True
    assert (
        prices_quotes.agents[0].cognition.communication_strategy_mode
        is CommunicationStrategyMode.DETERMINISTIC
    )
    assert all(
        config.schema_version == RUNNER_SCHEMA_VERSION_V56
        for config in (flag_off, valuation_only, prices_on, prices_quotes)
    )


def test_no_runner_schema_bump_or_new_command() -> None:
    definition = experiment_emergent_prices(_base())
    assert all(
        condition.runner_config.schema_version != "runner-config-v57"
        for condition in definition.conditions
    )
    assert definition.paired_world_group == "emergent_prices@1-world"


def test_short_horizon_is_rejected() -> None:
    with pytest.raises(ValueError):
        experiment_emergent_prices(_base(), max_ticks=32)
