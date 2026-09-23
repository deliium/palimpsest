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


def test_v2_round_trip_includes_name_and_goals() -> None:
    from agents.models import Goal, GoalId, GoalOutcome, GoalOutcomeKind, GoalStatus
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V2

    base = _config()
    agent = base.agents[0]
    goal = Goal(
        goal_id=GoalId("goal-reach"),
        owner_id=agent.agent_id,
        description="reach place",
        priority=0.7,
        status=GoalStatus.ACTIVE,
        outcome=GoalOutcome(kind=GoalOutcomeKind.REACH_PLACE, place_id="loc-1"),
    )
    config = SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=(
            AgentRunnerSpec(
                agent_id=agent.agent_id,
                entity_id=agent.entity_id,
                cognition=agent.cognition,
                name="scout",
                initial_goals=(goal,),
            ),
        ),
        stop_policy=base.stop_policy,
        schema_version=RUNNER_SCHEMA_VERSION_V2,
    )
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V2
    assert decoded.agents[0].name == "scout"
    assert len(decoded.agents[0].initial_goals) == 1
    assert decoded.agents[0].initial_goals[0].goal_id.value == "goal-reach"


def test_v1_decode_explicitly_upgrades_missing_name_and_goals() -> None:
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V1

    config = _config()
    v1 = SimulationRunnerConfig(
        seed=config.seed,
        stochastic_identity=config.stochastic_identity,
        scenario=config.scenario,
        agents=config.agents,
        stop_policy=config.stop_policy,
        schema_version=RUNNER_SCHEMA_VERSION_V1,
    )
    encoded = encode_runner_config(v1)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V1
    assert "name" not in document["agents"][0]
    assert "initial_goals" not in document["agents"][0]
    decoded = decode_runner_config(encoded)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V1
    assert decoded.agents[0].name == decoded.agents[0].agent_id.value
    assert decoded.agents[0].initial_goals == ()


def test_v2_rejects_missing_name_field() -> None:
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V2

    base = _config()
    v2 = SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=base.agents,
        stop_policy=base.stop_policy,
        schema_version=RUNNER_SCHEMA_VERSION_V2,
    )
    document = json.loads(encode_runner_config(v2).decode("utf-8"))
    del document["agents"][0]["name"]
    with pytest.raises(RunnerSerializationError) as rejected:
        decode_runner_config(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
    assert rejected.value.code == "missing_field"


def test_v4_round_trip_includes_default_off_trace_and_flags() -> None:
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        CognitionTraceSpec,
        V2CapabilityFlags,
    )

    config = _config()
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V4
    encoded = encode_runner_config(config)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V4
    assert document["capability_flags"] == {
        "advanced_social_inference": False,
        "extended_self_model": False,
        "multi_hop_testimony_tracking": False,
        "predictive_world_model": False,
    }
    assert document["cognition_trace"] == {
        "detail": "summary",
        "enabled": False,
        "max_bytes_per_invocation": None,
        "sample_every_n_ticks": None,
    }
    decoded = decode_runner_config(encoded)
    assert decoded.capability_flags == V2CapabilityFlags()
    assert decoded.cognition_trace == CognitionTraceSpec()
    assert runner_config_fingerprint(decoded) == runner_config_fingerprint(config)


def test_v3_decode_upgrades_to_disabled_cognition_trace() -> None:
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V3,
        CognitionTraceSpec,
        V2CapabilityFlags,
    )

    base = _config()
    v3 = SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=base.agents,
        stop_policy=base.stop_policy,
        mortality_mode=base.mortality_mode,
        cognition_failure_policy=base.cognition_failure_policy,
        provider=base.provider,
        persistence=base.persistence,
        experiment=base.experiment,
        capability_flags=V2CapabilityFlags(),
        schema_version=RUNNER_SCHEMA_VERSION_V3,
    )
    encoded = encode_runner_config(v3)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V3
    assert "cognition_trace" not in document
    decoded = decode_runner_config(encoded)
    assert decoded.cognition_trace == CognitionTraceSpec()
    assert not decoded.cognition_trace.enabled


def test_v2_decode_upgrades_to_default_off_flags() -> None:
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V2, V2CapabilityFlags

    base = _config()
    v2 = SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=base.agents,
        stop_policy=base.stop_policy,
        schema_version=RUNNER_SCHEMA_VERSION_V2,
    )
    encoded = encode_runner_config(v2)
    document = json.loads(encoded.decode("utf-8"))
    assert "capability_flags" not in document
    decoded = decode_runner_config(encoded)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V2
    assert decoded.capability_flags == V2CapabilityFlags()
    assert not decoded.capability_flags.any_enabled()


def test_v3_rejects_extra_capability_flag_field() -> None:
    document = json.loads(encode_runner_config(_config()).decode("utf-8"))
    document["capability_flags"]["extra_flag"] = False
    with pytest.raises(RunnerSerializationError) as rejected:
        decode_runner_config(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
    assert rejected.value.code == "invalid_fields"
