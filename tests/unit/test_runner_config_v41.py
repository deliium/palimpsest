"""runner-config-v41 resource_exchange_profile encode/decode and gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V40,
    RUNNER_SCHEMA_VERSION_V41,
    AgentCognitionSpec,
    AgentRunnerSpec,
    ResourceExchangeProfileSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
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
        seed=41,
        stochastic_identity="cmp-v41-exchange",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v41"),
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


def _v41(**extra):
    fields = {
        "schema_version": RUNNER_SCHEMA_VERSION_V41,
        "subjective_valuation": example_subjective_valuation_spec(),
        "resource_exchange_profile": example_resource_exchange_profile_spec(),
    }
    fields.update(extra)
    return replace(_plain_base(), **fields)


def _v40(**extra):
    fields = {
        "schema_version": RUNNER_SCHEMA_VERSION_V40,
        "subjective_valuation": example_subjective_valuation_spec(),
    }
    fields.update(extra)
    return replace(_plain_base(), **fields)


def test_v41_flags_off_round_trip() -> None:
    config = _v41()
    assert not config.v3_capability_flags.any_enabled()
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V41
    assert round_trip.subjective_valuation is not None
    assert round_trip.resource_exchange_profile is not None
    assert (
        round_trip.resource_exchange_profile.policy_id == "resource-exchange-profile-v1"
    )
    assert round_trip.resource_exchange_profile.acceptance_window_ticks == 32
    assert round_trip.structured_commitments is None
    assert not round_trip.v3_capability_flags.any_enabled()


def test_v40_valuation_config_still_loads() -> None:
    round_trip = decode_runner_config(encode_runner_config(_v40()))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V40
    assert round_trip.subjective_valuation is not None
    assert round_trip.resource_exchange_profile is None


def test_v41_requires_profile_object() -> None:
    with pytest.raises(ValueError, match="v41_requires_resource_exchange_profile"):
        _v41(resource_exchange_profile=None)


def test_v41_requires_subjective_valuation() -> None:
    with pytest.raises(
        ValueError, match="resource_exchange_profile_requires_subjective_valuation"
    ):
        _v41(subjective_valuation=None)


def test_profile_requires_v41() -> None:
    with pytest.raises(ValueError, match="resource_exchange_profile_requires_v41"):
        _v40(resource_exchange_profile=example_resource_exchange_profile_spec())


def test_window_outside_range() -> None:
    with pytest.raises(ValueError, match="resource_exchange_profile_window_invalid"):
        ResourceExchangeProfileSpec(acceptance_window_ticks=0)
    with pytest.raises(ValueError, match="resource_exchange_profile_window_invalid"):
        ResourceExchangeProfileSpec(acceptance_window_ticks=257)


def test_rejects_mode_disabled_and_money_aliases() -> None:
    document = json.loads(encode_runner_config(_v41()))
    disabled = json.loads(json.dumps(document))
    disabled["resource_exchange_profile"]["mode"] = "disabled"
    with pytest.raises(
        RunnerSerializationError, match="resource_exchange_profile_mode_invalid"
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
        "money",
        "coin",
        "currency_kind",
        "legal_tender",
        "is_money",
        "medium_of_exchange",
        "store_of_value",
        "unit_of_account",
    )
    for alias in aliases:
        tainted = json.loads(json.dumps(document))
        tainted["resource_exchange_profile"][alias] = 1
        with pytest.raises(
            RunnerSerializationError,
            match="resource_exchange_profile_money_forbidden",
        ):
            decode_runner_config(json.dumps(tainted).encode())


def test_v41_does_not_imply_a_new_capability_flag() -> None:
    config = _v41(v3_capability_flags=V3CapabilityFlags())
    assert config.resource_exchange_profile is not None
    assert config.v3_capability_flags.enabled_names() == ()


def test_v41_allows_optional_possession_and_commitments() -> None:
    config = _v41(
        possession_succession=example_possession_succession_spec(),
        structured_commitments=example_structured_commitments_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.possession_succession is not None
    assert round_trip.structured_commitments is not None
    assert round_trip.resource_exchange_profile is not None
