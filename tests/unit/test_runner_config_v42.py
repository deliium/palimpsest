"""runner-config-v42 collective_projects encode/decode and gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V41,
    RUNNER_SCHEMA_VERSION_V42,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CollectiveProjectsSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_collective_projects_spec,
    example_possession_succession_spec,
    example_resource_exchange_profile_spec,
    example_structured_commitments_spec,
    example_subjective_valuation_spec,
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
        seed=42,
        stochastic_identity="cmp-v42-projects",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v42"),
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


def _v42(**extra):
    fields = {
        "schema_version": RUNNER_SCHEMA_VERSION_V42,
        "collective_projects": example_collective_projects_spec(),
    }
    fields.update(extra)
    return replace(_plain_base(), **fields)


def _v41(**extra):
    fields = {
        "schema_version": RUNNER_SCHEMA_VERSION_V41,
        "subjective_valuation": example_subjective_valuation_spec(),
        "resource_exchange_profile": example_resource_exchange_profile_spec(),
    }
    fields.update(extra)
    return replace(_plain_base(), **fields)


def test_v42_flags_off_round_trip() -> None:
    config = _v42()
    assert not config.v3_capability_flags.any_enabled()
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V42
    assert round_trip.collective_projects is not None
    assert round_trip.collective_projects.policy_id == "collective-projects-v1"
    assert round_trip.collective_projects.idle_ticks == 4
    assert round_trip.subjective_valuation is None
    assert round_trip.resource_exchange_profile is None
    assert not round_trip.v3_capability_flags.any_enabled()


def test_v41_exchange_config_still_loads() -> None:
    round_trip = decode_runner_config(encode_runner_config(_v41()))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V41
    assert round_trip.resource_exchange_profile is not None
    assert round_trip.collective_projects is None


def test_v42_requires_collective_projects_object() -> None:
    with pytest.raises(ValueError, match="v42_requires_collective_projects"):
        _v42(collective_projects=None)


def test_collective_projects_requires_v42() -> None:
    with pytest.raises(ValueError, match="collective_projects_requires_v42"):
        _v41(collective_projects=example_collective_projects_spec())


def test_idle_ticks_outside_range() -> None:
    with pytest.raises(ValueError, match="collective_projects_idle_ticks_invalid"):
        CollectiveProjectsSpec(idle_ticks=0)
    with pytest.raises(ValueError, match="collective_projects_idle_ticks_invalid"):
        CollectiveProjectsSpec(idle_ticks=65)


def test_rejects_mode_disabled_and_leader_aliases() -> None:
    document = json.loads(encode_runner_config(_v42()))
    disabled = json.loads(json.dumps(document))
    disabled["collective_projects"]["mode"] = "disabled"
    with pytest.raises(
        RunnerSerializationError, match="collective_projects_mode_invalid"
    ):
        decode_runner_config(json.dumps(disabled).encode())
    aliases = (
        "leader",
        "leader_id",
        "project_leader",
        "foreman",
        "chief",
        "manager",
        "coordinator_id",
        "crew_boss",
        "institution",
        "work_crew",
        "archive",
        "library",
    )
    for alias in aliases:
        tainted = json.loads(json.dumps(document))
        tainted["collective_projects"][alias] = 1
        with pytest.raises(
            RunnerSerializationError,
            match="collective_projects_leader_forbidden",
        ):
            decode_runner_config(json.dumps(tainted).encode())


def test_v42_does_not_imply_a_new_capability_flag() -> None:
    config = _v42(v3_capability_flags=V3CapabilityFlags())
    assert config.collective_projects is not None
    assert config.v3_capability_flags.enabled_names() == ()


def test_v42_allows_optional_neighbors_without_requiring_them() -> None:
    bare = decode_runner_config(encode_runner_config(_v42()))
    assert bare.subjective_valuation is None
    assert bare.possession_succession is None
    config = _v42(
        subjective_valuation=example_subjective_valuation_spec(),
        resource_exchange_profile=example_resource_exchange_profile_spec(),
        possession_succession=example_possession_succession_spec(),
        structured_commitments=example_structured_commitments_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.collective_projects is not None
    assert round_trip.subjective_valuation is not None
    assert round_trip.resource_exchange_profile is not None
    assert round_trip.possession_succession is not None
    assert round_trip.structured_commitments is not None
