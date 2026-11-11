"""V4-20 owns the declared ``markets_credit`` flag without a new schema."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from agents.models import AgentId
from experiments import v4_scaffolding_profile
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src"
TESTS = Path(__file__).resolve().parents[1]


def _config() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    base = base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-market-owned",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-market"),
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
        max_ticks=2,
    )
    return replace(base, schema_version=RUNNER_SCHEMA_VERSION_V56)


def test_markets_credit_is_owned_and_nothing_else_changes() -> None:
    flags = V4CapabilityFlags(markets_credit=True)
    assert flags.owned_enabled_names() == ("markets_credit",)
    assert flags.unimplemented_enabled_names() == ()
    assert flags.enabled_names() == ("markets_credit",)


def test_scaffolding_profile_still_rejects_enabled_flags() -> None:
    config = replace(
        _config(),
        v4_capability_flags=V4CapabilityFlags(markets_credit=True),
    )
    with pytest.raises(ValueError, match="code=v4_scaffolding_flags_enabled"):
        v4_scaffolding_profile(config)


def test_no_runner_config_v57_string_exists() -> None:
    for path in SRC.rglob("*"):
        if path.suffix not in {".py", ".md", ".json", ".yaml"}:
            continue
        if ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        if "runner-config-v57" in path.read_text(encoding="utf-8", errors="ignore"):
            pytest.fail(f"unexpected runner-config-v57 in {path}")
