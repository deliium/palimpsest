"""Flags-off and v24 lifecycle compat for NewAgentInitialization (no provenance)."""

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
    RUNNER_SCHEMA_VERSION_V24,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_population_lifecycle_spec,
)
from simulation.runner_serialization import build_runner_result_document
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.events import AgentCreated, AgentEnteredWorld, AgentInitializationRecorded
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.v3_new_agent_flags_off_compat")


def _base(*, max_ticks: int = 4):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=47,
        stochastic_identity="cmp-v3-nai-flags-off",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v3-nai-off"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(body_capacity=8),),
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
        max_ticks=max_ticks,
    )


@pytest.mark.asyncio
async def test_flags_off_v4_matches_v24_all_off_trajectory() -> None:
    _LOG.info("case_id=nai_flags_off_traj experiment_id=v3-nai-compat")
    base = replace(
        _base(max_ticks=3),
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=3),
    )
    v4 = replace(base, schema_version=RUNNER_SCHEMA_VERSION_V4)
    v24_off = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        v3_capability_flags=V3CapabilityFlags(),
        population_lifecycle=example_population_lifecycle_spec(
            lifespan_ticks=20,
            policy_id="fixed_interval_entry",
        ),
    )
    v3_scaffolding_profile(v4)
    v3_scaffolding_profile(v24_off)
    run_id = RunId("run-nai-off-shared")
    async with await SimulationRunner.from_config(v4, run_id=run_id) as runner:
        result_v4 = await runner.run()
        assert runner.engine.new_agent_provenance_active is False
    async with await SimulationRunner.from_config(v24_off, run_id=run_id) as runner:
        result_v24 = await runner.run()
        assert runner.engine.new_agent_provenance_active is False
    doc_v4 = build_runner_result_document(result=result_v4, config=v4)
    doc_v24 = build_runner_result_document(result=result_v24, config=v24_off)
    _LOG.info(
        "case_id=nai_flags_off_traj hash_prefix=%s",
        doc_v4.exact_trajectory_hash[:12],
    )
    assert doc_v4.exact_trajectory_hash == doc_v24.exact_trajectory_hash


@pytest.mark.asyncio
async def test_v24_lifecycle_on_emits_no_initialization_recorded() -> None:
    _LOG.info("case_id=v24_lifecycle_no_init_event")
    config = replace(
        _base(max_ticks=8),
        mortality_mode=MortalityMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(
            lifespan_ticks=40,
            max_population=4,
            policy_id="fixed_interval_entry",
        ),
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-v24-no-init")
    ) as runner:
        await runner.run()
        assert runner.engine.new_agent_provenance_active is False
        kinds = {
            type(event.details)
            for event in runner.engine._snapshot.event_history
        }
    assert AgentInitializationRecorded not in kinds
    # v24 may still emit Created/Entered without init provenance.
    _ = (AgentCreated, AgentEnteredWorld)
