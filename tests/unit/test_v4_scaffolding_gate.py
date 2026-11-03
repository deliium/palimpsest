"""V4 scaffolding profiles: V4 flags off, V3 regression composition, fail closed."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments import v3_regression_profile, v4_scaffolding_profile
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.runner import (
    RunnerConstructionError,
    RunnerConstructionErrorCode,
    SimulationRunner,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CognitionTraceSpec,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.runner_serialization import decode_runner_config, encode_runner_config
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit

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
        stochastic_identity="cmp-v4-scaffolding-gate",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-gate"),
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


def _v56_config() -> SimulationRunnerConfig:
    return replace(_base(), schema_version=RUNNER_SCHEMA_VERSION_V56)


def test_base_v4_config_passes_both_profiles_unchanged() -> None:
    config = _base()
    assert v4_scaffolding_profile(config) is config
    assert v3_regression_profile(config) is config


def test_v56_all_flags_off_passes_both_profiles_unchanged() -> None:
    config = _v56_config()
    assert v4_scaffolding_profile(config) is config
    assert v3_regression_profile(config) is config


@pytest.mark.parametrize("flag_name", V4_FLAG_NAMES)
def test_each_enabled_flag_fails_the_profile(flag_name: str) -> None:
    config = replace(
        _v56_config(),
        v4_capability_flags=V4CapabilityFlags(**{flag_name: True}),
    )
    decoded = decode_runner_config(encode_runner_config(config))
    assert getattr(decoded.v4_capability_flags, flag_name) is True

    with pytest.raises(ValueError, match="code=v4_scaffolding_flags_enabled"):
        v4_scaffolding_profile(config)
    with pytest.raises(ValueError, match="code=v4_scaffolding_flags_enabled"):
        v3_regression_profile(config)


def test_v4_flag_on_a_v4_config_fails_before_the_profile() -> None:
    with pytest.raises(ValueError, match="code=v4_capability_requires_v56"):
        replace(_base(), v4_capability_flags=V4CapabilityFlags(science=True))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "flag_name",
    tuple(
        name
        for name in V4_FLAG_NAMES
        if name not in {"organizations", "formal_rules", "legal_disputes"}
    ),
)
async def test_each_unowned_enabled_flag_fails_closed_at_construction(
    flag_name: str,
) -> None:
    config = replace(
        _v56_config(),
        v4_capability_flags=V4CapabilityFlags(**{flag_name: True}),
    )
    with pytest.raises(RunnerConstructionError) as excinfo:
        await SimulationRunner.from_config(
            config, run_id=RunId(f"run-v4-profile-{flag_name}")
        )
    assert excinfo.value.code is RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED
    assert excinfo.value.stage == "v4_capability_flags"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "flag_name", ("organizations", "formal_rules", "legal_disputes")
)
async def test_owned_v4_flag_constructs_but_stays_scaffolding_off(
    flag_name: str,
) -> None:
    config = replace(
        _v56_config(),
        v4_capability_flags=V4CapabilityFlags(**{flag_name: True}),
    )
    with pytest.raises(ValueError, match="code=v4_scaffolding_flags_enabled"):
        v4_scaffolding_profile(config)

    runner = await SimulationRunner.from_config(
        config, run_id=RunId(f"run-v4-profile-{flag_name}")
    )
    assert runner.config.v4_capability_flags.owned_enabled_names() == (flag_name,)
    assert runner.config.v4_capability_flags.unimplemented_enabled_names() == ()


def test_v3_regression_profile_keeps_v1_rules() -> None:
    invalid = replace(_base(), cognition_trace=CognitionTraceSpec(enabled=True))
    assert invalid.schema_version == RUNNER_SCHEMA_VERSION_V4
    with pytest.raises(ValueError, match="code=v1_regression_trace_enabled"):
        v3_regression_profile(invalid)
