"""runner-config-v34 knowledge_repositories encode/decode and gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    RUNNER_SCHEMA_VERSION_V33,
    RUNNER_SCHEMA_VERSION_V34,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_durable_records_spec,
    example_historical_memory_layers_spec,
    example_knowledge_repositories_spec,
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
        seed=34,
        stochastic_identity="cmp-v34-repositories",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v34"),
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


def _repository_config(**extra):
    base = _plain_base()
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V34,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        durable_records=example_durable_records_spec(),
        knowledge_repositories=example_knowledge_repositories_spec(),
        **extra,
    )


def test_v34_cultural_repository_round_trip() -> None:
    config = _repository_config()
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V34
    assert round_trip.cultural_feature_provenance is not None
    assert round_trip.durable_records is not None
    assert round_trip.knowledge_repositories is not None
    assert round_trip.historical_memory_layers is None
    assert round_trip.v3_capability_flags.cultural_historical_memory is True
    assert (
        round_trip.knowledge_repositories.access_policy.default_access_mode
        == "open"
    )


def test_v34_repository_plus_layers_round_trip() -> None:
    config = _repository_config(
        historical_memory_layers=example_historical_memory_layers_spec()
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V34
    assert round_trip.knowledge_repositories is not None
    assert round_trip.historical_memory_layers is not None


def test_repository_without_cultural_flag_rejected() -> None:
    base = _plain_base()
    with pytest.raises(
        ValueError, match="knowledge_repositories_without_cultural_flag"
    ):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V34,
            v3_capability_flags=V3CapabilityFlags(),
            durable_records=example_durable_records_spec(),
            knowledge_repositories=example_knowledge_repositories_spec(),
        )


def test_repository_without_provenance_rejected() -> None:
    base = _plain_base()
    with pytest.raises(
        ValueError,
        match="knowledge_repositories_requires_cultural_provenance",
    ):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V34,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            durable_records=example_durable_records_spec(),
            knowledge_repositories=example_knowledge_repositories_spec(),
        )


def test_repository_without_durable_rejected() -> None:
    base = _plain_base()
    with pytest.raises(
        ValueError, match="knowledge_repositories_requires_durable_records"
    ):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V34,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            knowledge_repositories=example_knowledge_repositories_spec(),
        )


def test_repository_on_v33_rejected() -> None:
    base = _plain_base()
    with pytest.raises(
        ValueError, match="knowledge_repositories_requires_v34"
    ):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V33,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            durable_records=example_durable_records_spec(),
            knowledge_repositories=example_knowledge_repositories_spec(),
        )


def test_repository_on_v32_rejected() -> None:
    base = _plain_base()
    with pytest.raises(
        ValueError, match="knowledge_repositories_requires_v34"
    ):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V32,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            historical_memory_layers=example_historical_memory_layers_spec(),
            knowledge_repositories=example_knowledge_repositories_spec(),
        )


def test_repository_on_v31_rejected() -> None:
    base = _plain_base()
    with pytest.raises(
        ValueError, match="knowledge_repositories_requires_v34"
    ):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V31,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            knowledge_repositories=example_knowledge_repositories_spec(),
        )


def test_v34_without_repository_rejected() -> None:
    base = _plain_base()
    with pytest.raises(
        ValueError, match="v34_requires_knowledge_repositories"
    ):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V34,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            durable_records=example_durable_records_spec(),
        )


def test_v34_without_durable_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="v34_requires_durable_records"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V34,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        )


def test_durable_on_v34_with_repository_legal() -> None:
    config = _repository_config()
    assert config.durable_records is not None
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V34


def test_decode_v33_synthesizes_repository_none() -> None:
    base = _plain_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V33,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        durable_records=example_durable_records_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V33
    assert round_trip.durable_records is not None
    assert round_trip.knowledge_repositories is None


def test_forbidden_alias_under_repository_rejected() -> None:
    config = _repository_config()
    document = json.loads(encode_runner_config(config).decode("utf-8"))
    document["knowledge_repositories"]["library_institution"] = True
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    with pytest.raises(
        RunnerSerializationError, match="knowledge_repositories_forbidden_alias"
    ):
        decode_runner_config(payload)


def test_kinship_plus_cultural_plus_repository_on_v34() -> None:
    base = _plain_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V34,
        v3_capability_flags=V3CapabilityFlags(
            cultural_historical_memory=True,
            kinship_inheritance=True,
        ),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        durable_records=example_durable_records_spec(),
        knowledge_repositories=example_knowledge_repositories_spec(),
        kinship=example_kinship_spec(
            parent_agent_id="agent-a",
            child_agent_id="agent-b",
        ),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V34
    assert round_trip.kinship is not None
    assert round_trip.knowledge_repositories is not None
    assert round_trip.population_lifecycle is None
