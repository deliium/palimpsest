"""runner-config-v40 subjective_valuation encode/decode and gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V39,
    RUNNER_SCHEMA_VERSION_V40,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SubjectiveValuationSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_possession_succession_spec,
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
        seed=40,
        stochastic_identity="cmp-v40-valuation",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v40"),
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


def _v40(**extra):
    fields = {
        "schema_version": RUNNER_SCHEMA_VERSION_V40,
        "subjective_valuation": example_subjective_valuation_spec(),
    }
    fields.update(extra)
    return replace(_plain_base(), **fields)


def test_v40_flags_off_round_trip() -> None:
    config = _v40()
    assert not config.v3_capability_flags.any_enabled()
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V40
    assert round_trip.subjective_valuation is not None
    assert round_trip.subjective_valuation.policy_id == "subjective-valuation-v1"
    assert round_trip.subjective_valuation.horizon_ticks == 8
    assert round_trip.subjective_valuation.max_bundle == 8
    assert round_trip.structured_commitments is None
    assert round_trip.possession_succession is None
    assert not round_trip.v3_capability_flags.any_enabled()


def test_v39_commitment_config_still_loads() -> None:
    config = replace(
        _plain_base(),
        schema_version=RUNNER_SCHEMA_VERSION_V39,
        structured_commitments=example_structured_commitments_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.structured_commitments is not None
    assert round_trip.subjective_valuation is None


def test_v40_requires_object() -> None:
    with pytest.raises(ValueError, match="v40_requires_subjective_valuation"):
        _v40(subjective_valuation=None)


def test_object_requires_v40() -> None:
    with pytest.raises(ValueError, match="subjective_valuation_requires_v40"):
        replace(
            _plain_base(),
            schema_version=RUNNER_SCHEMA_VERSION_V39,
            structured_commitments=example_structured_commitments_spec(),
            subjective_valuation=example_subjective_valuation_spec(),
        )


def test_horizon_and_bundle_outside_range() -> None:
    with pytest.raises(ValueError, match="subjective_valuation_horizon_invalid"):
        SubjectiveValuationSpec(horizon_ticks=0)
    with pytest.raises(ValueError, match="subjective_valuation_horizon_invalid"):
        SubjectiveValuationSpec(horizon_ticks=65)
    with pytest.raises(ValueError, match="subjective_valuation_bundle_invalid"):
        SubjectiveValuationSpec(max_bundle=0)
    with pytest.raises(ValueError, match="subjective_valuation_bundle_invalid"):
        SubjectiveValuationSpec(max_bundle=9)


def test_rejects_mode_disabled_and_price_aliases() -> None:
    document = json.loads(encode_runner_config(_v40()))
    disabled = json.loads(json.dumps(document))
    disabled["subjective_valuation"]["mode"] = "disabled"
    with pytest.raises(
        RunnerSerializationError, match="subjective_valuation_mode_invalid"
    ):
        decode_runner_config(json.dumps(disabled).encode())
    aliases = (
        "world_price",
        "market_price",
        "price_table",
        "exchange_rate",
        "currency",
        "posted_price",
        "clearing_price",
        "numeraire",
    )
    for alias in aliases:
        tainted = json.loads(json.dumps(document))
        tainted["subjective_valuation"][alias] = 1
        with pytest.raises(
            RunnerSerializationError,
            match="subjective_valuation_price_forbidden",
        ):
            decode_runner_config(json.dumps(tainted).encode())


def test_v40_does_not_imply_a_new_capability_flag() -> None:
    config = _v40(v3_capability_flags=V3CapabilityFlags())
    assert config.subjective_valuation is not None
    assert config.v3_capability_flags.enabled_names() == ()


def test_v40_allows_optional_possession_and_commitments() -> None:
    config = _v40(
        possession_succession=example_possession_succession_spec(),
        structured_commitments=example_structured_commitments_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.possession_succession is not None
    assert round_trip.structured_commitments is not None
    assert round_trip.subjective_valuation is not None
