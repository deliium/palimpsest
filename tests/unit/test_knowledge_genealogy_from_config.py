"""Knowledge genealogy channel wiring from SimulationRunner.from_config."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation import runner as runner_mod
from simulation.models import RunId
from simulation.runner import SimulationRunner, _knowledge_genealogy_loop_kwargs
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V34,
    RUNNER_SCHEMA_VERSION_V35,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_durable_records_spec,
    example_knowledge_genealogy_spec,
    example_knowledge_repositories_spec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOGGER_NAME = "simulation.runner"


@pytest.fixture
def isolate_cultural_loop_bind(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid pre-existing cultural_features_spec bind gap in build_cognitive_loop."""

    monkeypatch.setattr(
        runner_mod, "_cultural_features_loop_kwargs", lambda _config: {}
    )


def _plain_base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    agent_a = AgentId("agent-a")
    agent_b = AgentId("agent-b")
    return base_runner_config_from_scenario(
        seed=3511,
        stochastic_identity="cmp-v35-from-config",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v35-from-config"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_a,
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_a),
            ),
            AgentRunnerSpec(
                agent_id=agent_b,
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_b),
            ),
        ),
        max_ticks=1,
    )


def _genealogy_config(**extra):
    base = _plain_base()
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V35,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=1),
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        knowledge_genealogy=example_knowledge_genealogy_spec(),
        **extra,
    )


def test_knowledge_genealogy_loop_kwargs_bind_spec_and_seed() -> None:
    config = _genealogy_config()
    kwargs = _knowledge_genealogy_loop_kwargs(config)
    assert kwargs["knowledge_genealogy_spec"] is config.knowledge_genealogy
    assert kwargs["knowledge_genealogy_seed_material"] == config.seed


def test_knowledge_genealogy_loop_kwargs_absent() -> None:
    base = _plain_base()
    assert _knowledge_genealogy_loop_kwargs(base) == {}


@pytest.mark.asyncio
async def test_knowledge_genealogy_channel_enabled_logs(
    caplog: pytest.LogCaptureFixture,
    isolate_cultural_loop_bind: None,
) -> None:
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        async with await SimulationRunner.from_config(
            _genealogy_config(), run_id=RunId("run-genealogy-on")
        ) as runner:
            for runtime in runner._runtimes:
                loop = runtime._loop
                assert loop._knowledge_genealogy_spec is not None
                assert loop._knowledge_genealogy_seed_material == 3511
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "knowledge_genealogy_enabled" in messages


@pytest.mark.asyncio
async def test_knowledge_genealogy_channel_off_when_absent(
    caplog: pytest.LogCaptureFixture,
    isolate_cultural_loop_bind: None,
) -> None:
    base = _plain_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V34,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=1),
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        durable_records=example_durable_records_spec(),
        knowledge_repositories=example_knowledge_repositories_spec(),
    )
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        async with await SimulationRunner.from_config(
            config, run_id=RunId("run-genealogy-off")
        ) as runner:
            for runtime in runner._runtimes:
                assert runtime._loop._knowledge_genealogy_spec is None
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "knowledge_genealogy_skip" in messages
