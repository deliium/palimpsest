# mypy: ignore-errors
"""V4-18 off-gate trade_networks@1 registration and scenario shape."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import (
    EXPERIMENT_A_V1_CONDITION_IDS,
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    base_runner_config_from_scenario,
    experiment_trade_networks,
)
from experiments.trade_network_scenario import (
    TRADE_NETWORKS_EXPERIMENT_ID,
    trade_network_scenario,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V3CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)

pytestmark = pytest.mark.unit


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    regions = RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(
            LocationRegion(EntityId("loc-a"), "west"),
            LocationRegion(EntityId("loc-b"), "east"),
        ),
        routes=(RouteSpec(EntityId("loc-a"), EntityId("loc-b"), 2, 3.0),),
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    base = base_runner_config_from_scenario(
        seed=19,
        stochastic_identity="trade-networks",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-trade-experiment"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(
                make_location("loc-a", adjacent=("loc-b",)),
                make_location("loc-b", adjacent=("loc-a",)),
            ),
            bodies=(body,),
            weather=(make_weather("loc-a"), make_weather("loc-b")),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=4,
    )
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v3_capability_flags=V3CapabilityFlags(multi_polity_migration=True),
        regions_migration=regions,
    )


def test_experiment_id_is_off_gate() -> None:
    assert TRADE_NETWORKS_EXPERIMENT_ID == "trade_networks@1"
    assert "trade_networks@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert not any("trade" in item for item in EXPERIMENT_A_V1_CONDITION_IDS)


def test_scenario_has_control_and_treatment() -> None:
    definition = experiment_trade_networks(_base())
    assert definition.experiment_id == "trade_networks@1"
    assert len(definition.conditions) == 2
    control, treatment = definition.conditions
    assert control.condition_id == "trade-networks-control"
    assert treatment.condition_id == "trade-networks-treatment"
    assert control.label_code == "trade_networks_control"
    assert treatment.label_code == "trade_networks_treatment"
    assert control.runner_config.regions_migration is not None
    assert treatment.runner_config.regions_migration is not None


def test_scenario_adds_exchange_and_valuation_specs() -> None:
    control, treatment = experiment_trade_networks(_base()).conditions
    for condition in (control, treatment):
        assert condition.runner_config.resource_exchange_profile is not None
        assert condition.runner_config.subjective_valuation is not None
        assert (
            condition.runner_config.resource_exchange_profile.acceptance_window_ticks
            == 8
        )
        assert condition.runner_config.subjective_valuation.max_bundle == 2


def test_scenario_is_deterministic() -> None:
    assert experiment_trade_networks(_base()) == experiment_trade_networks(_base())


def test_scenario_requires_regions() -> None:
    with pytest.raises(ValueError, match="trade_networks_requires_regions"):
        trade_network_scenario(
            replace(
                _base(),
                regions_migration=None,
                v3_capability_flags=V3CapabilityFlags(),
            )
        )


def test_v1_gate_profile_does_not_include_trade() -> None:
    definition = experiment_trade_networks(_base())
    assert definition.experiment_id not in EXPERIMENT_A_V1_CONDITION_IDS
    assert not any("trade" in item for item in EXPERIMENT_A_V1_CONDITION_IDS)


def test_no_runner_config_v57() -> None:
    from pathlib import Path

    for path in (
        Path("src/experiments/trade_network_scenario.py"),
        Path("src/experiments/trade_networks_completed_run.py"),
        Path("src/experiments/trade_networks_publication.py"),
        Path("src/analysis/trade_networks_analysis.py"),
        Path("src/simulation/trade_networks_models.py"),
    ):
        assert "runner-config-v57" not in path.read_text(encoding="utf-8")
