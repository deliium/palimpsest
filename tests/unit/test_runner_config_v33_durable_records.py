"""runner-config-v33 durable_records encode/decode and gates."""

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
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_durable_records_spec,
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
        seed=33,
        stochastic_identity="cmp-v33-durable",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v33"),
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


def _durable_only_config(**extra):
    base = _plain_base()
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V33,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        durable_records=example_durable_records_spec(),
        **extra,
    )


def test_v33_cultural_only_round_trip() -> None:
    config = _durable_only_config()
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V33
    assert round_trip.cultural_feature_provenance is not None
    assert round_trip.durable_records is not None
    assert round_trip.historical_memory_layers is None
    assert round_trip.v3_capability_flags.cultural_historical_memory is True
    assert round_trip.population_lifecycle is None
    assert len(round_trip.durable_records.enabled_genres) == 8


def test_v33_durable_plus_layers_round_trip() -> None:
    config = _durable_only_config(
        historical_memory_layers=example_historical_memory_layers_spec()
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V33
    assert round_trip.durable_records is not None
    assert round_trip.historical_memory_layers is not None
    assert round_trip.historical_memory_layers.max_communicative_hops == 2


def test_durable_without_cultural_flag_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="durable_records_without_cultural_flag"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V33,
            v3_capability_flags=V3CapabilityFlags(),
            durable_records=example_durable_records_spec(),
        )


def test_durable_without_provenance_rejected() -> None:
    base = _plain_base()
    with pytest.raises(
        ValueError, match="durable_records_requires_cultural_provenance"
    ):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V33,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            durable_records=example_durable_records_spec(),
        )


def test_durable_on_v32_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="durable_records_requires_v33"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V32,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            historical_memory_layers=example_historical_memory_layers_spec(),
            durable_records=example_durable_records_spec(),
        )


def test_durable_on_v31_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="durable_records_requires_v33"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V31,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            durable_records=example_durable_records_spec(),
        )


def test_v33_without_durable_rejected() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="v33_requires_durable_records"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V33,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        )


def test_decode_v32_synthesizes_durable_none() -> None:
    base = _plain_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V32,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        historical_memory_layers=example_historical_memory_layers_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V32
    assert round_trip.durable_records is None
    assert round_trip.historical_memory_layers is not None


def test_forbidden_alias_under_durable_rejected() -> None:
    config = _durable_only_config()
    document = json.loads(encode_runner_config(config).decode("utf-8"))
    document["durable_records"]["canonical_archive"] = True
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    with pytest.raises(
        RunnerSerializationError, match="durable_records_forbidden_alias"
    ):
        decode_runner_config(payload)


def test_kinship_plus_cultural_plus_durable_on_v33() -> None:
    base = _plain_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V33,
        v3_capability_flags=V3CapabilityFlags(
            cultural_historical_memory=True,
            kinship_inheritance=True,
        ),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        durable_records=example_durable_records_spec(),
        kinship=example_kinship_spec(
            parent_agent_id="agent-a",
            child_agent_id="agent-b",
        ),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.kinship is not None
    assert round_trip.cultural_feature_provenance is not None
    assert round_trip.durable_records is not None
    assert round_trip.population_lifecycle is None


def test_layers_on_v33_without_durable_still_requires_durable_object() -> None:
    base = _plain_base()
    with pytest.raises(ValueError, match="v33_requires_durable_records"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V33,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            historical_memory_layers=example_historical_memory_layers_spec(),
        )
