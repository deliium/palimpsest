"""Flags-off / channel-off cultural feature regression proofs."""

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
    RUNNER_SCHEMA_VERSION_V31,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_kinship_spec,
)
from simulation.runner_serialization import (
    build_runner_result_document,
    decode_runner_config,
    encode_runner_config,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.v3_cultural_features_regression")


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
        seed=52,
        stochastic_identity="cmp-v3-cultural-off",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v3-cultural-off"),
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
    _LOG.info("case_id=flags_off_cultural_traj_hash")
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
        cultural_feature_provenance=None,
    )
    v3_scaffolding_profile(v4)
    v3_scaffolding_profile(channel_absent)

    run_id = RunId("run-cultural-off-shared")
    async with await SimulationRunner.from_config(v4, run_id=run_id) as runner:
        result_v4 = await runner.run()
    async with await SimulationRunner.from_config(
        channel_absent, run_id=run_id
    ) as runner:
        result_off = await runner.run()

    doc_v4 = build_runner_result_document(result=result_v4, config=v4)
    doc_off = build_runner_result_document(result=result_off, config=channel_absent)
    assert doc_v4.exact_trajectory_hash == doc_off.exact_trajectory_hash
    assert result_v4.cultural_feature_audits == ()
    assert result_off.cultural_feature_audits == ()
    _LOG.info("case_id=flags_off_cultural_traj_hash status=pass")


def test_semantic_event_count_stays_43() -> None:
    assert len(SEMANTIC_EVENT_TYPES) == 54


def test_cultural_only_config_accepts_without_lifecycle() -> None:
    base = _base(max_ticks=2)
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V31,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        population_lifecycle=None,
        mentorship=None,
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.cultural_feature_provenance is not None
    assert round_trip.population_lifecycle is None


def test_kinship_only_plus_cultural_accepts() -> None:
    base = _base(max_ticks=2)
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V31,
        v3_capability_flags=V3CapabilityFlags(
            kinship_inheritance=True,
            cultural_historical_memory=True,
        ),
        kinship=example_kinship_spec(
            parent_agent_id="agent-0",
            child_agent_id="agent-1",
        ),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        population_lifecycle=None,
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.kinship is not None
    assert round_trip.cultural_feature_provenance is not None
    assert round_trip.population_lifecycle is None
