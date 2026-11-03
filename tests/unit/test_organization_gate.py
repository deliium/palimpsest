"""V4-03 ownership gate: ``organizations`` is the one owned V4 flag."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V55,
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
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

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

V4_FLAG_NAMES = (
    "organizations",
    "formal_rules",
    "legal_disputes",
    "diplomacy",
    "organized_conflict",
    "infrastructure_networks",
    "supply_chains",
    "markets_credit",
    "science",
    "epidemics",
    "ecological_feedback",
    "disasters",
)


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-organization-gate",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-organization-gate"),
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


def test_organizations_is_owned_and_other_unowned_v4_flags_fail_closed() -> None:
    flags = V4CapabilityFlags(organizations=True)
    assert flags.any_enabled() is True
    assert flags.enabled_names() == ("organizations",)
    assert flags.owned_enabled_names() == ("organizations",)
    assert flags.unimplemented_enabled_names() == ()

    formal = V4CapabilityFlags(formal_rules=True)
    assert formal.owned_enabled_names() == ("formal_rules",)
    assert formal.unimplemented_enabled_names() == ()

    disputes = V4CapabilityFlags(legal_disputes=True)
    assert disputes.owned_enabled_names() == ("legal_disputes",)
    assert disputes.unimplemented_enabled_names() == ()

    for name in V4_FLAG_NAMES:
        if name in {"organizations", "formal_rules", "legal_disputes"}:
            continue
        other = V4CapabilityFlags(**{name: True})
        assert other.owned_enabled_names() == ()
        assert other.unimplemented_enabled_names() == (name,)


@pytest.mark.parametrize(
    "schema_version",
    (RUNNER_SCHEMA_VERSION_V4, RUNNER_SCHEMA_VERSION_V55),
)
def test_enabling_organizations_below_v56_fails_closed(schema_version: str) -> None:
    config = _base()
    with pytest.raises(ValueError, match="code=v4_capability_requires_v56"):
        replace(
            config,
            schema_version=schema_version,
            v4_capability_flags=V4CapabilityFlags(organizations=True),
        )


def test_v56_is_accepted_and_v57_stays_absent() -> None:
    assert RUNNER_SCHEMA_VERSION_V56 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS


def test_organization_modules_do_not_reference_the_v4_flag_seam() -> None:
    for path in sorted(SRC.rglob("organization_*.py")):
        assert "v4_capability_flags" not in path.read_text(encoding="utf-8"), path
