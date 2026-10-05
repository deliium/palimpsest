"""Flags-off kinship must leave V1/V2 trajectories unchanged."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario, v3_scaffolding_profile
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V23,
    RUNNER_SCHEMA_VERSION_V27,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_kinship_spec,
)
from simulation.runner_serialization import build_runner_result_document
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.v3_kinship_flags_off_compat")


def _base(*, max_ticks: int = 3):
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    return base_runner_config_from_scenario(
        seed=47,
        stochastic_identity="cmp-v3-kinship-flags-off",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v3-kinship-off"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(body_capacity=8),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-a"),
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-a")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-b"),
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-b")),
            ),
        ),
        max_ticks=max_ticks,
    )


@pytest.mark.asyncio
async def test_flags_off_v4_and_v23_share_trajectory_hash() -> None:
    _LOG.info("case_id=flags_off_kinship_traj_hash")
    base = replace(
        _base(max_ticks=3),
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=3),
    )
    v4 = replace(base, schema_version=RUNNER_SCHEMA_VERSION_V4)
    v23_off = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V23,
        v3_capability_flags=V3CapabilityFlags(),
        kinship=None,
    )
    v3_scaffolding_profile(v4)
    v3_scaffolding_profile(v23_off)

    run_id = RunId("run-kinship-off-shared")
    async with await SimulationRunner.from_config(v4, run_id=run_id) as runner:
        result_v4 = await runner.run()
        assert runner.engine.kinship_channel_active is False
    async with await SimulationRunner.from_config(v23_off, run_id=run_id) as runner:
        result_v23 = await runner.run()
        assert runner.engine.kinship_channel_active is False

    doc_v4 = build_runner_result_document(result=result_v4, config=v4)
    doc_v23 = build_runner_result_document(result=result_v23, config=v23_off)
    _LOG.info(
        "case_id=flags_off_kinship_traj_hash hash_prefix=%s",
        doc_v4.exact_trajectory_hash[:12],
    )
    assert doc_v4.exact_trajectory_hash == doc_v23.exact_trajectory_hash


def test_kinship_config_without_flag_rejected() -> None:
    base = _base()
    with pytest.raises(ValueError, match="kinship_config_without_flag"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V27,
            v3_capability_flags=V3CapabilityFlags(),
            kinship=example_kinship_spec(
                parent_agent_id="agent-a",
                child_agent_id="agent-b",
            ),
        )


@pytest.mark.asyncio
async def test_unowned_v3_flags_still_fail_closed() -> None:
    base = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V23,
        mortality_mode=MortalityMode.DISABLED,
        v3_capability_flags=V3CapabilityFlags(multi_polity_migration=True),
    )
    with pytest.raises(Exception) as exc_info:
        await SimulationRunner.from_config(base, run_id=RunId("run-unowned"))
    message = str(exc_info.value).lower()
    assert "capability_unimplemented" in message or "unimplemented" in message
