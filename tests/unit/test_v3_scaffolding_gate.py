"""Network-free V3 scaffolding gate under V3 flags off / fail-closed flags on."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments import v2_regression_profile, v3_scaffolding_profile
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.runner import (
    RunnerConstructionError,
    RunnerConstructionErrorCode,
    SimulationRunner,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V23,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.runner_serialization import decode_runner_config, encode_runner_config
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit

_LOG = logging.getLogger("tests.v3_scaffolding_gate")


def _base_config():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v3-scaffolding-gate",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v3-gate"),
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


def test_v3_scaffolding_and_v2_regression_profiles_on_base() -> None:
    _LOG.info("v3_scaffolding_gate_start experiment_id=base tick_count=2")
    config = _base_config()
    assert v3_scaffolding_profile(config) is config
    assert v2_regression_profile(config) is config
    _LOG.info(
        "v3_scaffolding_gate_end schema_version=%s v3_flag_count=0",
        config.schema_version,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "flag_name",
    (
        "multi_polity_migration",
        "institutional_economy",
    ),
)
async def test_unowned_v3_flag_fails_closed_at_from_config_while_encode_decode_ok(
    flag_name: str,
) -> None:
    base = _base_config()
    flags = V3CapabilityFlags(**{flag_name: True})
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V23,
        v3_capability_flags=flags,
    )
    encoded = encode_runner_config(config)
    decoded = decode_runner_config(encoded)
    assert getattr(decoded.v3_capability_flags, flag_name) is True
    with pytest.raises(RunnerConstructionError) as exc_info:
        await SimulationRunner.from_config(
            config, run_id=RunId(f"run-v3-gate-{flag_name}")
        )
    assert exc_info.value.code is RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED
    assert exc_info.value.stage == "v3_capability_flags"
    _LOG.info(
        "v3_scaffolding_gate_fail_closed flag=%s reason_code=%s",
        flag_name,
        RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED.value,
    )
