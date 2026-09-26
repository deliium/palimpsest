"""Unit tests for runner configuration canonical codecs."""

from __future__ import annotations

import json

import pytest

from agents.models import AgentId, DriveKind
from simulation.models import StochasticIdentity
from simulation.runner_models import (
    COGNITION_POLICY_VERSION,
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V5,
    RUNNER_SCHEMA_VERSION_V6,
    RUNNER_SCHEMA_VERSION_V7,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CognitionTraceDetail,
    CognitionTraceSpec,
    ConsolidationMode,
    DriveOverrideSpec,
    MemoryMode,
    MortalityMode,
    ProspectiveImaginationMode,
    ReflectionMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    cognition_fingerprint,
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


def test_reconstructive_v2_memory_mode_round_trips() -> None:
    base = _config()
    agent = base.agents[0]
    config = SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=(
            AgentRunnerSpec(
                agent_id=agent.agent_id,
                entity_id=agent.entity_id,
                cognition=AgentCognitionSpec(
                    agent_id=agent.agent_id,
                    memory_mode=MemoryMode.RECONSTRUCTIVE_V2,
                ),
            ),
        ),
        stop_policy=base.stop_policy,
    )
    encoded = encode_runner_config(config)
    document = json.loads(encoded.decode("utf-8"))
    assert document["agents"][0]["cognition"]["memory_mode"] == "reconstructive_v2"
    decoded = decode_runner_config(encoded)
    assert decoded.agents[0].cognition.memory_mode is MemoryMode.RECONSTRUCTIVE_V2


def test_unknown_memory_mode_string_fails_closed() -> None:
    document = json.loads(encode_runner_config(_config()).decode("utf-8"))
    document["agents"][0]["cognition"]["memory_mode"] = "perfect_recall"
    with pytest.raises(RunnerSerializationError) as rejected:
        decode_runner_config(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
    assert rejected.value.code == "invalid_model"


def test_default_memory_mode_still_encodes_reconstructive() -> None:
    agent_id = AgentId("agent-default")
    body = alive_body()
    config = SimulationRunnerConfig(
        seed=1,
        stochastic_identity=StochasticIdentity("default-mem"),
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
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        stop_policy=RunnerStopPolicy(max_ticks=3),
    )
    document = json.loads(encode_runner_config(config).decode("utf-8"))
    assert document["agents"][0]["cognition"]["memory_mode"] == "reconstructive"
    assert (
        AgentCognitionSpec(agent_id=agent_id).memory_mode is MemoryMode.RECONSTRUCTIVE
    )


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
        "short_term_emotional_state": False,
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


def test_v4_omits_consolidation_mode_and_rejects_the_key() -> None:
    config = _config()
    encoded = encode_runner_config(config)
    document = json.loads(encoded.decode("utf-8"))
    assert "consolidation_mode" not in document["agents"][0]["cognition"]
    decoded = decode_runner_config(encoded)
    assert decoded.agents[0].cognition.consolidation_mode is ConsolidationMode.DISABLED
    assert cognition_fingerprint(decoded) == cognition_fingerprint(config)
    document["agents"][0]["cognition"]["consolidation_mode"] = "disabled"
    with pytest.raises(RunnerSerializationError) as rejected:
        decode_runner_config(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
    assert rejected.value.code == "invalid_fields"


def test_v5_round_trips_consolidation_mode() -> None:
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V5

    base = _config()
    agent = base.agents[0]
    enabled = SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=(
            AgentRunnerSpec(
                agent_id=agent.agent_id,
                entity_id=agent.entity_id,
                cognition=AgentCognitionSpec(
                    agent_id=agent.agent_id,
                    memory_mode=MemoryMode.REFERENCE,
                    drive_overrides=agent.cognition.drive_overrides,
                    consolidation_mode=ConsolidationMode.DETERMINISTIC,
                ),
                name=agent.name,
                initial_goals=agent.initial_goals,
            ),
        ),
        stop_policy=base.stop_policy,
        schema_version=RUNNER_SCHEMA_VERSION_V5,
    )
    encoded = encode_runner_config(enabled)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == RUNNER_SCHEMA_VERSION_V5
    assert document["agents"][0]["cognition"]["consolidation_mode"] == "deterministic"
    decoded = decode_runner_config(encoded)
    assert decoded == enabled
    document["agents"][0]["cognition"]["consolidation_mode"] = "scripted"
    with pytest.raises(RunnerSerializationError) as rejected:
        decode_runner_config(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
    assert rejected.value.code == "invalid_enum"


def test_v4_rejects_non_disabled_consolidation_mode() -> None:
    base = _config()
    agent = base.agents[0]
    with pytest.raises(ValueError, match="consolidation_mode_requires_v5"):
        SimulationRunnerConfig(
            seed=base.seed,
            stochastic_identity=base.stochastic_identity,
            scenario=base.scenario,
            agents=(
                AgentRunnerSpec(
                    agent_id=agent.agent_id,
                    entity_id=agent.entity_id,
                    cognition=AgentCognitionSpec(
                        agent_id=agent.agent_id,
                        consolidation_mode=ConsolidationMode.LLM_ASSISTED,
                    ),
                ),
            ),
            stop_policy=base.stop_policy,
        )


def _configured(
    *,
    schema_version: str,
    consolidation_mode: ConsolidationMode = ConsolidationMode.DISABLED,
    reflection_mode: ReflectionMode = ReflectionMode.DISABLED,
    prospective_mode: ProspectiveImaginationMode = (
        ProspectiveImaginationMode.DISABLED
    ),
    name: str = "Ada",
) -> SimulationRunnerConfig:
    base = _config()
    agent = base.agents[0]
    return SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=(
            AgentRunnerSpec(
                agent_id=agent.agent_id,
                entity_id=agent.entity_id,
                cognition=AgentCognitionSpec(
                    agent_id=agent.agent_id,
                    memory_mode=MemoryMode.REFERENCE,
                    drive_overrides=agent.cognition.drive_overrides,
                    consolidation_mode=consolidation_mode,
                    reflection_mode=reflection_mode,
                    prospective_mode=prospective_mode,
                ),
                name=name,
                initial_goals=agent.initial_goals,
            ),
        ),
        stop_policy=base.stop_policy,
        capability_flags=V2CapabilityFlags(short_term_emotional_state=True),
        cognition_trace=CognitionTraceSpec(
            enabled=True,
            detail=CognitionTraceDetail.SUMMARY,
            sample_every_n_ticks=1,
        ),
        schema_version=schema_version,
    )


def test_v4_omits_reflection_mode_and_keeps_policy_version() -> None:
    config = _config()
    document = json.loads(encode_runner_config(config).decode("utf-8"))
    cognition = document["agents"][0]["cognition"]
    assert "reflection_mode" not in cognition
    assert "consolidation_mode" not in cognition
    assert cognition["policy_version"] == "cognition-policy-v1"
    assert RUNNER_SCHEMA_VERSION == RUNNER_SCHEMA_VERSION_V4
    assert COGNITION_POLICY_VERSION == "cognition-policy-v1"
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V4


def test_v5_rejects_reflection_mode_key() -> None:
    enabled = _configured(
        schema_version=RUNNER_SCHEMA_VERSION_V5,
        consolidation_mode=ConsolidationMode.DETERMINISTIC,
    )
    encoded = encode_runner_config(enabled)
    document = json.loads(encoded.decode("utf-8"))
    assert "reflection_mode" not in document["agents"][0]["cognition"]
    decoded = decode_runner_config(encoded)
    assert decoded.agents[0].cognition.reflection_mode is ReflectionMode.DISABLED
    document["agents"][0]["cognition"]["reflection_mode"] = "deterministic"
    with pytest.raises(RunnerSerializationError) as rejected:
        decode_runner_config(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
    assert rejected.value.code == "invalid_fields"
    with pytest.raises(ValueError, match="v5_requires_consolidation"):
        _configured(schema_version=RUNNER_SCHEMA_VERSION_V5)


def test_v6_round_trips_reflection_names_flags_and_trace() -> None:
    enabled = _configured(
        schema_version=RUNNER_SCHEMA_VERSION_V6,
        reflection_mode=ReflectionMode.DETERMINISTIC,
    )
    encoded = encode_runner_config(enabled)
    document = json.loads(encoded.decode("utf-8"))
    assert document["schema_version"] == "runner-config-v6"
    cognition = document["agents"][0]["cognition"]
    assert cognition["reflection_mode"] == "deterministic"
    assert cognition["consolidation_mode"] == "disabled"
    assert document["agents"][0]["name"] == "Ada"
    assert document["capability_flags"]["short_term_emotional_state"] is True
    assert document["cognition_trace"]["enabled"] is True
    assert decode_runner_config(encoded) == enabled
    both = _configured(
        schema_version=RUNNER_SCHEMA_VERSION_V6,
        consolidation_mode=ConsolidationMode.DETERMINISTIC,
        reflection_mode=ReflectionMode.LLM_ASSISTED,
    )
    assert decode_runner_config(encode_runner_config(both)) == both


def test_reflection_schema_fails_closed() -> None:
    with pytest.raises(ValueError, match="reflection_mode_requires_v6"):
        _configured(
            schema_version=RUNNER_SCHEMA_VERSION_V4,
            reflection_mode=ReflectionMode.DETERMINISTIC,
        )
    with pytest.raises(ValueError, match="reflection_mode_requires_v6"):
        _configured(
            schema_version=RUNNER_SCHEMA_VERSION_V5,
            consolidation_mode=ConsolidationMode.DETERMINISTIC,
            reflection_mode=ReflectionMode.DETERMINISTIC,
        )
    with pytest.raises(ValueError, match="v6_requires_reflection"):
        _configured(schema_version=RUNNER_SCHEMA_VERSION_V6)
    document = json.loads(
        encode_runner_config(
            _configured(
                schema_version=RUNNER_SCHEMA_VERSION_V6,
                reflection_mode=ReflectionMode.DETERMINISTIC,
            )
        ).decode("utf-8")
    )
    document["agents"][0]["cognition"]["reflection_mode"] = "scripted"
    with pytest.raises(RunnerSerializationError) as rejected:
        decode_runner_config(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
    assert rejected.value.code == "invalid_enum"


def test_cognition_config_for_builds_reflection_policy_from_mode() -> None:
    from simulation.runner import _cognition_config_for

    spec = _configured(
        schema_version=RUNNER_SCHEMA_VERSION_V6,
        reflection_mode=ReflectionMode.LLM_ASSISTED,
    ).agents[0].cognition
    assisted = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert assisted.reflection_mode.value == "llm_assisted"
    assert assisted.reflection_policy is not None
    assert assisted.reflection_policy.allow_provider is True
    assert assisted.reflection_policy.version == "reflection-v1"
    disabled = _cognition_config_for(
        _config().agents[0].cognition,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert disabled.reflection_mode.value == "disabled"
    assert disabled.reflection_policy is None
    assert disabled.prospective_mode.value == "disabled"
    assert disabled.prospective_policy is None


def test_prospective_mode_requires_v7_and_round_trips() -> None:
    with pytest.raises(ValueError, match="prospective_mode_requires_v7"):
        _configured(
            schema_version=RUNNER_SCHEMA_VERSION_V4,
            prospective_mode=ProspectiveImaginationMode.DETERMINISTIC,
        )
    with pytest.raises(ValueError, match="v7_requires_prospective"):
        _configured(schema_version=RUNNER_SCHEMA_VERSION_V7)
    enabled = _configured(
        schema_version=RUNNER_SCHEMA_VERSION_V7,
        prospective_mode=ProspectiveImaginationMode.DETERMINISTIC,
    )
    encoded = encode_runner_config(enabled)
    document = json.loads(encoded.decode("utf-8"))
    cognition = document["agents"][0]["cognition"]
    assert cognition["prospective_mode"] == "deterministic"
    assert "horizon" not in cognition
    assert "max_branches" not in cognition
    assert decode_runner_config(encoded) == enabled
    reflected = _configured(
        schema_version=RUNNER_SCHEMA_VERSION_V7,
        reflection_mode=ReflectionMode.DETERMINISTIC,
        prospective_mode=ProspectiveImaginationMode.LLM_ASSISTED,
    )
    assert decode_runner_config(encode_runner_config(reflected)) == reflected
    shallow = _configured(
        schema_version=RUNNER_SCHEMA_VERSION_V6,
        reflection_mode=ReflectionMode.DETERMINISTIC,
    )
    shallow_doc = json.loads(encode_runner_config(shallow).decode("utf-8"))
    assert "prospective_mode" not in shallow_doc["agents"][0]["cognition"]
    assert decode_runner_config(encode_runner_config(shallow)) == shallow


def test_cognition_config_for_builds_prospective_policy_from_mode(caplog) -> None:
    import logging

    from simulation.runner import _cognition_config_for

    caplog.set_level(logging.DEBUG, logger="simulation.runner")
    spec = _configured(
        schema_version=RUNNER_SCHEMA_VERSION_V7,
        prospective_mode=ProspectiveImaginationMode.LLM_ASSISTED,
    ).agents[0].cognition
    assisted = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.ENABLED,
        capability_flags=V2CapabilityFlags(),
    )
    assert assisted.prospective_mode.value == "llm_assisted"
    assert assisted.prospective_policy is not None
    assert assisted.prospective_policy.allow_provider is True
    assert assisted.prospective_policy.version == "prospective-v1"
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert (
        "cognition_config_prospective_mode mode=llm_assisted "
        "policy_version=prospective-v1" in messages
    )
