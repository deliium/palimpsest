"""runner-config-v38 possession_succession encode/decode and gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.persistence import (
    EVENT_SCHEMA_REPLAY_V15,
    EVENT_SCHEMA_REPLAY_V16,
    checkpoint_schema_for_production,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V37,
    RUNNER_SCHEMA_VERSION_V38,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_bounded_experimentation_spec,
    example_cultural_feature_provenance_spec,
    example_kinship_spec,
    example_knowledge_genealogy_spec,
    example_possession_succession_spec,
    example_technique_lifecycle_spec,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
)
from simulation.serialization import (
    DomainSerializationError,
    _decode_event_details,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules
from world.production import example_production_catalog


def _plain_base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    agent_a = AgentId("agent-a")
    agent_b = AgentId("agent-b")
    return base_runner_config_from_scenario(
        seed=38,
        stochastic_identity="cmp-v38-succession",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v38"),
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


def _with_catalog(config):
    catalog = example_production_catalog()
    agents = tuple(
        replace(
            agent,
            cognition=replace(agent.cognition, production_catalog=catalog),
        )
        for agent in config.agents
    )
    return replace(config, agents=agents)


def _v38(**extra):
    fields = {
        "schema_version": RUNNER_SCHEMA_VERSION_V38,
        "possession_succession": example_possession_succession_spec(),
    }
    fields.update(extra)
    return replace(_plain_base(), **fields)


def test_v38_flags_off_round_trip() -> None:
    config = _v38()
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V38
    assert round_trip.possession_succession is not None
    assert round_trip.possession_succession.custody_mechanism == "corpse"
    assert round_trip.possession_succession.policy_id == "possession-succession-v1"
    assert round_trip.cultural_feature_provenance is None
    assert round_trip.technique_lifecycle is None
    assert round_trip.bounded_experimentation is None
    assert not round_trip.v3_capability_flags.any_enabled()


def test_v37_decodes_without_possession_succession() -> None:
    config = replace(
        _plain_base(),
        schema_version=RUNNER_SCHEMA_VERSION_V37,
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        knowledge_genealogy=example_knowledge_genealogy_spec(),
        technique_lifecycle=example_technique_lifecycle_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.possession_succession is None
    assert round_trip.technique_lifecycle is not None


def test_v38_requires_object() -> None:
    with pytest.raises(ValueError, match="v38_requires_possession_succession"):
        _v38(possession_succession=None)


def test_object_requires_v38() -> None:
    with pytest.raises(ValueError, match="possession_succession_requires_v38"):
        replace(
            _plain_base(),
            schema_version=RUNNER_SCHEMA_VERSION_V37,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            knowledge_genealogy=example_knowledge_genealogy_spec(),
            technique_lifecycle=example_technique_lifecycle_spec(),
            possession_succession=example_possession_succession_spec(),
        )


def test_rejects_mode_disabled_and_heir_alias_and_location() -> None:
    config = _v38()
    document = json.loads(encode_runner_config(config))
    disabled = json.loads(json.dumps(document))
    disabled["possession_succession"]["mode"] = "disabled"
    with pytest.raises(
        RunnerSerializationError, match="possession_succession_mode_invalid"
    ):
        decode_runner_config(json.dumps(disabled).encode())
    heir = json.loads(json.dumps(document))
    heir["possession_succession"]["heir"] = "agent-a"
    with pytest.raises(
        RunnerSerializationError, match="possession_succession_law_forbidden"
    ):
        decode_runner_config(json.dumps(heir).encode())
    location = json.loads(json.dumps(document))
    location["possession_succession"]["custody_mechanism"] = "location"
    with pytest.raises(RunnerSerializationError, match="custody_mechanism_unsupported"):
        decode_runner_config(json.dumps(location).encode())


def test_kinship_on_v38_is_not_an_heir_table() -> None:
    config = _v38(
        v3_capability_flags=V3CapabilityFlags(kinship_inheritance=True),
        kinship=example_kinship_spec(
            parent_agent_id="agent-a", child_agent_id="agent-b"
        ),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.kinship is not None
    assert round_trip.possession_succession is not None
    assert round_trip.possession_succession.custody_mechanism == "corpse"


def test_succession_write_pair_beats_experimentation() -> None:
    active = checkpoint_schema_for_production(
        production_active=False,
        bounded_experimentation_active=True,
        possession_succession_active=True,
    )
    assert active == (EVENT_SCHEMA_REPLAY_V16, "v13")
    experiment_only = checkpoint_schema_for_production(
        production_active=False,
        bounded_experimentation_active=True,
    )
    assert experiment_only == (EVENT_SCHEMA_REPLAY_V15, "v12")
    idle = checkpoint_schema_for_production(production_active=False)
    assert idle[0] != EVENT_SCHEMA_REPLAY_V16


def test_replay_v15_rejects_succession_event_kinds() -> None:
    for kind in (
        "corpse_custody_opened",
        "taken_from_corpse",
        "possession_claim_asserted",
    ):
        with pytest.raises(
            DomainSerializationError, match="invalid_event_schema_version"
        ):
            _decode_event_details(
                {"kind": kind},
                path="$.details",
                schema_version=EVENT_SCHEMA_REPLAY_V15,
            )


def test_cultural_siblings_optional_on_v38() -> None:
    config = _with_catalog(
        _v38(
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            knowledge_genealogy=example_knowledge_genealogy_spec(),
            technique_lifecycle=example_technique_lifecycle_spec(),
            bounded_experimentation=example_bounded_experimentation_spec(),
        )
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.technique_lifecycle is not None
    assert round_trip.bounded_experimentation is not None
    assert round_trip.knowledge_genealogy is not None
    assert round_trip.possession_succession is not None
