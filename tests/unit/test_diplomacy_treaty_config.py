# mypy: ignore-errors
"""V4-11 activates treaties only through the owned diplomacy flag."""

from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path

import pytest

from agents.cognition import (
    TREATY_CONTRACT_VERSION,
    TREATY_POLICY_VERSION,
    DiplomacyLedger,
    empty_diplomacy_ledger,
    treaty_extension_enabled,
)
from agents.cognition.configuration import CognitionDiplomacyMode
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.runner import (
    RunnerConstructionError,
    RunnerConstructionErrorCode,
    SimulationRunner,
    _cognition_config_for,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.runner_serialization import decode_runner_config, encode_runner_config
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-treaty-config",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-treaty-config"),
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


def _v56_config(*, flags: V4CapabilityFlags | None = None) -> SimulationRunnerConfig:
    return replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=flags if flags is not None else V4CapabilityFlags(),
    )


def test_treaty_extension_requires_a_diplomacy_ledger() -> None:
    assert treaty_extension_enabled(None) is False
    ledger = empty_diplomacy_ledger("owner-1", tick=0)
    assert type(ledger) is DiplomacyLedger
    assert treaty_extension_enabled(ledger) is True
    assert TREATY_CONTRACT_VERSION == "diplomacy-treaties-v1"
    assert TREATY_POLICY_VERSION == "treaty.v1"


@pytest.mark.asyncio
async def test_diplomacy_flag_constructs_and_yields_the_extension() -> None:
    config = _v56_config(flags=V4CapabilityFlags(diplomacy=True))
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.v4_capability_flags.diplomacy is True
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("run-v4-treaty-construct")
    )
    assert runner.config.v4_capability_flags.owned_enabled_names() == ("diplomacy",)
    cognition = _cognition_config_for(
        AgentCognitionSpec(agent_id=AgentId("agent-1")),
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        organizations_enabled=False,
        formal_rules_enabled=False,
        legal_disputes_enabled=False,
        diplomacy_enabled=True,
    )
    assert cognition.diplomacy_mode is CognitionDiplomacyMode.DETERMINISTIC
    assert not hasattr(cognition, "treaty_mode")
    assert not hasattr(cognition, "treaty_policy")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "flag_name", ("organizations", "formal_rules", "legal_disputes")
)
async def test_other_owned_flags_do_not_activate_treaties(flag_name: str) -> None:
    config = _v56_config(flags=V4CapabilityFlags(**{flag_name: True}))
    runner = await SimulationRunner.from_config(
        config, run_id=RunId(f"run-v4-treaty-{flag_name}")
    )
    assert runner.config.v4_capability_flags.diplomacy is False


@pytest.mark.asyncio
async def test_diplomacy_runs_without_organizations() -> None:
    config = _v56_config(flags=V4CapabilityFlags(diplomacy=True))
    assert config.v4_capability_flags.organizations is False
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("run-v4-treaty-without-organizations")
    )
    assert runner.config.v4_capability_flags.enabled_names() == ("diplomacy",)


@pytest.mark.asyncio
async def test_unowned_v4_flag_still_fails_closed() -> None:
    config = _v56_config(flags=V4CapabilityFlags(science=True))
    with pytest.raises(RunnerConstructionError) as exc:
        await SimulationRunner.from_config(
            config, run_id=RunId("run-v4-treaty-unowned")
        )
    assert exc.value.code is RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED
    assert exc.value.stage == "v4_capability_flags"


def test_no_v57_runner_schema_exists() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src"
    for path in source_root.rglob("*.py"):
        assert "runner-config-v57" not in path.read_text(encoding="utf-8")


def test_no_treaty_key_exists_in_runner_or_agent_specs() -> None:
    runner_fields = {field.name for field in fields(SimulationRunnerConfig)}
    assert "treaty" not in runner_fields
    assert "treaty_mode" not in runner_fields
    assert "treaties" not in runner_fields
    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))
    assert not hasattr(spec, "treaty_mode")
    assert not hasattr(spec, "treaty")
    assert not hasattr(spec, "treaties")
