"""runner-config-v43 public_goods encode/decode and gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V42,
    RUNNER_SCHEMA_VERSION_V43,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CollectiveProjectsSpec,
    PublicGoodsSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_collective_projects_spec,
    example_possession_succession_spec,
    example_public_goods_spec,
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
        seed=43,
        stochastic_identity="cmp-v43-goods",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v43"),
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


def _v43(**extra):
    fields = {
        "schema_version": RUNNER_SCHEMA_VERSION_V43,
        "collective_projects": example_collective_projects_spec(),
        "public_goods": example_public_goods_spec(),
    }
    fields.update(extra)
    return replace(_plain_base(), **fields)


def _v42(**extra):
    fields = {
        "schema_version": RUNNER_SCHEMA_VERSION_V42,
        "collective_projects": example_collective_projects_spec(),
    }
    fields.update(extra)
    return replace(_plain_base(), **fields)


def test_v43_flags_off_round_trip() -> None:
    config = _v43(public_goods=PublicGoodsSpec(decay_millis=12))
    assert not config.v3_capability_flags.any_enabled()
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V43
    assert round_trip.collective_projects is not None
    assert round_trip.public_goods is not None
    assert round_trip.public_goods.policy_id == "public-goods-v1"
    assert round_trip.public_goods.decay_millis == 12
    assert round_trip.subjective_valuation is None
    assert not round_trip.v3_capability_flags.any_enabled()


def test_v42_collective_projects_still_loads_without_public_goods() -> None:
    round_trip = decode_runner_config(encode_runner_config(_v42()))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V42
    assert round_trip.collective_projects is not None
    assert round_trip.public_goods is None


def test_v43_requires_public_goods_object() -> None:
    with pytest.raises(ValueError, match="v43_requires_public_goods"):
        _v43(public_goods=None)


def test_v43_requires_collective_projects() -> None:
    with pytest.raises(ValueError, match="public_goods_requires_collective_projects"):
        _v43(collective_projects=None)


def test_public_goods_requires_v43() -> None:
    with pytest.raises(ValueError, match="public_goods_requires_v43"):
        _v42(public_goods=example_public_goods_spec())


def test_decay_millis_outside_range() -> None:
    with pytest.raises(ValueError, match="public_goods_decay_millis_invalid"):
        PublicGoodsSpec(decay_millis=251)


def test_rejects_mode_disabled_and_role_aliases() -> None:
    document = json.loads(encode_runner_config(_v43()))
    disabled = json.loads(json.dumps(document))
    disabled["public_goods"]["mode"] = "disabled"
    with pytest.raises(RunnerSerializationError, match="public_goods_mode_invalid"):
        decode_runner_config(json.dumps(disabled).encode())
    aliases = (
        "free_rider",
        "freerider",
        "free_rider_id",
        "cheater",
        "selfish",
        "guilty",
        "fair",
        "unfair",
        "deserved",
        "sanction",
        "punish",
        "punishment",
        "exclude",
        "exclusion",
        "toll",
        "wage",
        "membership",
        "leader",
        "leader_id",
        "archive",
        "library",
    )
    for alias in aliases:
        tainted = json.loads(json.dumps(document))
        tainted["public_goods"][alias] = 1
        with pytest.raises(
            RunnerSerializationError, match="public_goods_role_forbidden"
        ):
            decode_runner_config(json.dumps(tainted).encode())
    kind_token = json.loads(json.dumps(document))
    kind_token["public_goods"]["policy_id"] = "archive"
    with pytest.raises(RunnerSerializationError, match="public_goods_role_forbidden"):
        decode_runner_config(json.dumps(kind_token).encode())


def test_v43_does_not_imply_a_new_capability_flag() -> None:
    config = _v43(v3_capability_flags=V3CapabilityFlags())
    assert config.public_goods is not None
    assert config.v3_capability_flags.enabled_names() == ()


def test_v43_allows_optional_neighbors_without_requiring_them() -> None:
    bare = decode_runner_config(encode_runner_config(_v43()))
    assert bare.subjective_valuation is None
    assert bare.possession_succession is None
    config = _v43(
        subjective_valuation=example_subjective_valuation_spec(),
        resource_exchange_profile=example_resource_exchange_profile_spec(),
        possession_succession=example_possession_succession_spec(),
        structured_commitments=example_structured_commitments_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.public_goods is not None
    assert round_trip.collective_projects is not None
    assert round_trip.subjective_valuation is not None
    assert round_trip.resource_exchange_profile is not None
    assert round_trip.possession_succession is not None
    assert round_trip.structured_commitments is not None


def test_collective_projects_spec_type_is_unchanged() -> None:
    assert isinstance(example_collective_projects_spec(), CollectiveProjectsSpec)
