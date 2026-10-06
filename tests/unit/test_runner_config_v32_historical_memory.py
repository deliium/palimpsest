"""runner-config-v32 historical_memory_layers encode/decode and gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_historical_memory_layers_spec,
    example_kinship_spec,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _plain_base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    agent_a = AgentId("agent-a")
    agent_b = AgentId("agent-b")
    return base_runner_config_from_scenario(
        seed=32,
        stochastic_identity="cmp-v32-historical",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v32"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
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
        max_ticks=2,
    )


def _layers_only_config(**extra):
    base = _plain_base()
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V32,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        historical_memory_layers=example_historical_memory_layers_spec(),
        **extra,
    )


def test_v32_cultural_only_round_trip() -> None:
    config = _layers_only_config()
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V32
    assert round_trip.cultural_feature_provenance is not None
    assert round_trip.historical_memory_layers is not None
    assert round_trip.v3_capability_flags.cultural_historical_memory is True
    assert round_trip.population_lifecycle is None
    assert round_trip.historical_memory_layers.max_communicative_hops == 2


def test_layers_without_cultural_flag_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="historical_memory_without_cultural_flag"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V32,
            v3_capability_flags=V3CapabilityFlags(),
            historical_memory_layers=example_historical_memory_layers_spec(),
        )


def test_layers_without_provenance_rejected() -> None:
    base = _plain_base()
    with pytest.raises(
        ValueError, match="historical_memory_requires_cultural_provenance"
    ):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V32,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            historical_memory_layers=example_historical_memory_layers_spec(),
        )


def test_layers_on_v31_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="historical_memory_requires_v32"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V31,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            historical_memory_layers=example_historical_memory_layers_spec(),
        )


def test_v32_without_layers_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="v32_requires_historical_memory_layers"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V32,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        )


def test_cultural_only_on_v32_allowed() -> None:
    config = _layers_only_config()
    assert config.population_lifecycle is None
    assert config.new_agent_initialization is None
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V32
    assert round_trip.historical_memory_layers is not None


def test_kinship_plus_cultural_plus_layers_on_v32() -> None:
    base = _plain_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V32,
        v3_capability_flags=V3CapabilityFlags(
            cultural_historical_memory=True,
            kinship_inheritance=True,
        ),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        historical_memory_layers=example_historical_memory_layers_spec(),
        kinship=example_kinship_spec(
            parent_agent_id="agent-a",
            child_agent_id="agent-b",
        ),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.kinship is not None
    assert round_trip.cultural_feature_provenance is not None
    assert round_trip.historical_memory_layers is not None
    assert round_trip.population_lifecycle is None


def test_decode_v31_synthesizes_layers_none() -> None:
    base = _plain_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V31,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V31
    assert round_trip.historical_memory_layers is None
    assert round_trip.cultural_feature_provenance is not None


def test_forbidden_alias_under_layers_rejected() -> None:
    config = _layers_only_config()
    document = json.loads(encode_runner_config(config).decode("utf-8"))
    document["historical_memory_layers"]["inject_into_agents"] = True
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    with pytest.raises(
        RunnerSerializationError, match="historical_memory_forbidden_alias"
    ):
        decode_runner_config(payload)


def test_assmann_prefix_alias_rejected() -> None:
    config = _layers_only_config()
    document = json.loads(encode_runner_config(config).decode("utf-8"))
    document["historical_memory_layers"]["assmann_tier"] = "living"
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    with pytest.raises(
        RunnerSerializationError, match="historical_memory_forbidden_alias"
    ):
        decode_runner_config(payload)


def test_cultural_feature_requires_v31_code_id_covers_v32_message() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="cultural_feature_requires_v31"):
        replace(
            base,
            schema_version="runner-config-v23",
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        )
