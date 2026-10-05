"""Flags-off V3 population/lifecycle must match V2-equivalent trajectories."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario, v3_scaffolding_profile
from simulation.lifecycle import ActionSubmission
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
from world.actions import Wait
from world.effects import DeathCause
from world.events import AgentCreated, AgentEnteredWorld, Died, LifecycleStageChanged
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.v3_population_flags_off_compat")


def _base(*, max_ticks: int = 4):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=41,
        stochastic_identity="cmp-v3-pop-flags-off",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v3-pop-off"),
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
async def test_flags_off_v4_and_all_off_v24_share_exact_trajectory_hash() -> None:
    _LOG.info("case_id=flags_off_traj_hash experiment_id=v3-pop-compat")
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

    run_id = RunId("run-pop-off-shared")
    async with await SimulationRunner.from_config(v4, run_id=run_id) as runner:
        result_v4 = await runner.run()
        assert runner.engine.lifecycle_channel_active is False
        assert runner.engine.lifecycle_records == ()
    async with await SimulationRunner.from_config(v24_off, run_id=run_id) as runner:
        result_v24 = await runner.run()
        assert runner.engine.lifecycle_channel_active is False
        assert runner.engine.lifecycle_records == ()

    doc_v4 = build_runner_result_document(result=result_v4, config=v4)
    doc_v24 = build_runner_result_document(result=result_v24, config=v24_off)
    _LOG.info(
        "case_id=flags_off_traj_hash hash_prefix=%s",
        doc_v4.exact_trajectory_hash[:12],
    )
    assert doc_v4.exact_trajectory_hash == doc_v24.exact_trajectory_hash
    assert (
        doc_v4.replica_normalized_trajectory_hash
        == doc_v24.replica_normalized_trajectory_hash
    )


@pytest.mark.asyncio
async def test_flags_off_emits_no_lifecycle_event_kinds() -> None:
    _LOG.info("case_id=flags_off_no_lifecycle_events")
    config = replace(
        _base(max_ticks=6),
        mortality_mode=MortalityMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        v3_capability_flags=V3CapabilityFlags(),
        population_lifecycle=example_population_lifecycle_spec(
            lifespan_ticks=20,
            policy_id="fixed_interval_entry",
        ),
    )
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("run-pop-off-events")
    )
    assert runner.engine.lifecycle_channel_active is False
    for _ in range(6):
        batch = runner.engine.observe()
        submissions = tuple(
            ActionSubmission(
                batch.token,
                runner.engine.registration_translator.to_agent_id(
                    observation.observer_id
                ),
                Wait(),
            )
            for observation in batch.observations
        )
        result = runner.engine.resolve_tick(submissions)
        forbidden = (AgentCreated, AgentEnteredWorld, LifecycleStageChanged)
        for record in result.events:
            assert type(record.event.details) not in forbidden
            if type(record.event.details) is Died:
                assert record.event.details.death_cause is not DeathCause.LIFESPAN
    assert len(runner.engine.ordered_registrations) == 1
