"""Durable records channel wiring from SimulationRunner.from_config."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation import runner as runner_mod
from simulation.models import RunId
from simulation.runner import RunnerConstructionError, SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V33,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_durable_records_spec,
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
        seed=3311,
        stochastic_identity="cmp-v33-from-config",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v33-from-config"),
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


def _durable_config(**extra):
    base = _plain_base()
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V33,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=1),
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        durable_records=example_durable_records_spec(),
        artifacts_enabled=False,
        **extra,
    )


@pytest.mark.asyncio
async def test_durable_records_channel_active_and_artifacts_forced(
    caplog: pytest.LogCaptureFixture,
    isolate_cultural_loop_bind: None,
) -> None:
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        async with await SimulationRunner.from_config(
            _durable_config(), run_id=RunId("run-durable-on")
        ) as runner:
            assert runner.engine.durable_records_channel_active is True
            assert runner.engine.durable_records_spec is not None
            assert runner.engine._artifacts_enabled is True
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "durable_records_enabled" in messages
    assert "durable_artifacts_enabled_for_channel" in messages


@pytest.mark.asyncio
async def test_durable_records_channel_off_when_absent(
    isolate_cultural_loop_bind: None,
) -> None:
    base = _plain_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V31,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=1),
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
    )
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-durable-off")
    ) as runner:
        assert runner.engine.durable_records_channel_active is False
        assert runner.engine.durable_records_spec is None


@pytest.mark.asyncio
async def test_unowned_v3_flags_still_fail_closed_with_durable(
    isolate_cultural_loop_bind: None,
) -> None:
    config = replace(
        _durable_config(),
        v3_capability_flags=V3CapabilityFlags(
            cultural_historical_memory=True,
            multi_polity_migration=True,
        ),
    )
    with pytest.raises(RunnerConstructionError):
        await SimulationRunner.from_config(config)
