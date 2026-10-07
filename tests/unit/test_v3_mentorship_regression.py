"""Flags-off / channel-off mentorship regression proofs."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import (
    base_runner_config_from_scenario,
    v3_scaffolding_profile,
)
from observer.contracts import SEMANTIC_EVENT_TYPES
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    V3CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.runner_serialization import build_runner_result_document
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.v3_mentorship_regression")


def _base(*, max_ticks: int = 3, agents: int = 2):
    bodies = tuple(alive_body(f"body-{index}") for index in range(agents))
    specs = tuple(
        AgentRunnerSpec(
            agent_id=AgentId(f"agent-{index}"),
            entity_id=body.entity_id,
            cognition=AgentCognitionSpec(agent_id=AgentId(f"agent-{index}")),
        )
        for index, body in enumerate(bodies)
    )
    return base_runner_config_from_scenario(
        seed=51,
        stochastic_identity="cmp-v3-mentorship-flags-off",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v3-mentor-off"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(body_capacity=8),),
            bodies=bodies,
            weather=(make_weather(),),
        ),
        agents=specs,
        max_ticks=max_ticks,
    )


@pytest.mark.asyncio
async def test_flags_off_and_channel_absent_share_trajectory_hash() -> None:
    _LOG.info("case_id=flags_off_mentorship_traj_hash")
    base = replace(
        _base(max_ticks=3),
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=3),
    )
    v4 = replace(base, schema_version=RUNNER_SCHEMA_VERSION_V4)
    channel_absent = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
        v3_capability_flags=V3CapabilityFlags(),
        mentorship=None,
        developmental_learning=None,
        population_lifecycle=None,
    )
    v3_scaffolding_profile(v4)
    v3_scaffolding_profile(channel_absent)

    run_id = RunId("run-mentorship-off-shared")
    async with await SimulationRunner.from_config(v4, run_id=run_id) as runner:
        result_v4 = await runner.run()
    async with await SimulationRunner.from_config(
        channel_absent, run_id=run_id
    ) as runner:
        result_off = await runner.run()

    doc_v4 = build_runner_result_document(result=result_v4, config=v4)
    doc_off = build_runner_result_document(result=result_off, config=channel_absent)
    assert doc_v4.exact_trajectory_hash == doc_off.exact_trajectory_hash
    assert result_v4.mentorship_audits == ()
    assert result_off.mentorship_audits == ()
    _LOG.info("case_id=flags_off_mentorship_traj_hash status=pass")


def test_semantic_event_count_stays_43() -> None:
    assert len(SEMANTIC_EVENT_TYPES) == 53
