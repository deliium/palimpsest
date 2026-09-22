"""Unit tests for runner configuration canonical codecs."""

from __future__ import annotations

import json

import pytest

from agents.models import AgentId, DriveKind
from simulation.models import StochasticIdentity
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    DriveOverrideSpec,
    MemoryMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
    provider_fingerprint,
    runner_config_fingerprint,
    scenario_fingerprint,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _config(*, stochastic: str = "cmp-codec") -> SimulationRunnerConfig:
    agent_id = AgentId("agent-1")
    body = alive_body()
    return SimulationRunnerConfig(
        seed=99,
        stochastic_identity=StochasticIdentity(stochastic),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-1"),
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
                cognition=AgentCognitionSpec(
                    agent_id=agent_id,
                    memory_mode=MemoryMode.REFERENCE,
                    drive_overrides=(
                        DriveOverrideSpec(kind=DriveKind.SAFETY, baseline=0.9),
                    ),
                ),
            ),
        ),
        stop_policy=RunnerStopPolicy(max_ticks=5),
    )


def test_runner_config_round_trip_and_fingerprint_stability() -> None:
    config = _config()
    encoded = encode_runner_config(config)
    assert encode_runner_config(config) == encoded
    decoded = decode_runner_config(encoded)
    assert decoded == config
    assert runner_config_fingerprint(decoded) == runner_config_fingerprint(config)


def test_large_seed_round_trips() -> None:
    config = _config()
    large = SimulationRunnerConfig(
        seed=2**100,
        stochastic_identity=config.stochastic_identity,
        scenario=config.scenario,
        agents=config.agents,
        stop_policy=config.stop_policy,
    )
    decoded = decode_runner_config(encode_runner_config(large))
    assert decoded.seed == 2**100


def test_credentials_and_unknown_fields_rejected() -> None:
    document = json.loads(encode_runner_config(_config()).decode("utf-8"))
    document["provider"]["api_key"] = "secret"
    with pytest.raises(RunnerSerializationError) as rejected:
        decode_runner_config(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
    assert rejected.value.code in {"credentials_forbidden", "invalid_fields"}


def test_duplicate_keys_rejected() -> None:
    with pytest.raises(RunnerSerializationError) as rejected:
        decode_runner_config(b'{"seed":1,"seed":2}')
    assert rejected.value.code == "duplicate_key"


def test_scenario_fingerprint_stable_across_cognition() -> None:
    left = _config()
    right_agent = left.agents[0]
    right = SimulationRunnerConfig(
        seed=left.seed,
        stochastic_identity=left.stochastic_identity,
        scenario=left.scenario,
        agents=(
            AgentRunnerSpec(
                agent_id=right_agent.agent_id,
                entity_id=right_agent.entity_id,
                cognition=AgentCognitionSpec(
                    agent_id=right_agent.agent_id,
                    memory_mode=MemoryMode.RECONSTRUCTIVE,
                ),
            ),
        ),
        stop_policy=left.stop_policy,
    )
    assert scenario_fingerprint(left) == scenario_fingerprint(right)
    assert runner_config_fingerprint(left) != runner_config_fingerprint(right)
    assert provider_fingerprint(left) == provider_fingerprint(right)
