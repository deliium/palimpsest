"""runner-config-v39 structured_commitments encode/decode and gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V38,
    RUNNER_SCHEMA_VERSION_V39,
    AgentCognitionSpec,
    AgentRunnerSpec,
    StructuredCommitmentsSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_possession_succession_spec,
    example_structured_commitments_spec,
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
        seed=39,
        stochastic_identity="cmp-v39-commitments",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v39"),
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


def _v39(**extra):
    fields = {
        "schema_version": RUNNER_SCHEMA_VERSION_V39,
        "structured_commitments": example_structured_commitments_spec(),
    }
    fields.update(extra)
    return replace(_plain_base(), **fields)


def test_v39_flags_off_round_trip() -> None:
    config = _v39()
    assert not config.v3_capability_flags.any_enabled()
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V39
    assert round_trip.structured_commitments is not None
    assert round_trip.structured_commitments.policy_id == "structured-commitments-v1"
    assert round_trip.structured_commitments.horizon_ticks == 8
    assert round_trip.structured_commitments.max_open_interpretations == 8
    assert round_trip.possession_succession is None
    assert not round_trip.v3_capability_flags.any_enabled()


def test_v38_still_loads_without_structured_commitments() -> None:
    config = replace(
        _plain_base(),
        schema_version=RUNNER_SCHEMA_VERSION_V38,
        possession_succession=example_possession_succession_spec(),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.possession_succession is not None
    assert round_trip.structured_commitments is None


def test_v39_requires_object() -> None:
    with pytest.raises(ValueError, match="v39_requires_structured_commitments"):
        _v39(structured_commitments=None)


def test_object_requires_v39() -> None:
    with pytest.raises(ValueError, match="structured_commitments_requires_v39"):
        replace(
            _plain_base(),
            schema_version=RUNNER_SCHEMA_VERSION_V38,
            possession_succession=example_possession_succession_spec(),
            structured_commitments=example_structured_commitments_spec(),
        )


def test_horizon_outside_range() -> None:
    with pytest.raises(ValueError, match="structured_commitments_horizon_invalid"):
        StructuredCommitmentsSpec(horizon_ticks=0)
    with pytest.raises(ValueError, match="structured_commitments_horizon_invalid"):
        StructuredCommitmentsSpec(horizon_ticks=65)
    with pytest.raises(ValueError, match="structured_commitments_cap_invalid"):
        StructuredCommitmentsSpec(max_open_interpretations=17)


def test_rejects_mode_disabled_and_enforcement_aliases() -> None:
    document = json.loads(encode_runner_config(_v39()))
    disabled = json.loads(json.dumps(document))
    disabled["structured_commitments"]["mode"] = "disabled"
    with pytest.raises(
        RunnerSerializationError, match="structured_commitments_mode_invalid"
    ):
        decode_runner_config(json.dumps(disabled).encode())
    aliases = (
        "enforced_contract",
        "auto_collect",
        "breach_damage",
        "contract_law",
        "shared_ledger",
        "canonical_terms",
        "court",
        "institution_enforces",
        "obligation_rejects_command",
    )
    for alias in aliases:
        tainted = json.loads(json.dumps(document))
        tainted["structured_commitments"][alias] = True
        with pytest.raises(
            RunnerSerializationError,
            match="structured_commitments_enforcement_forbidden",
        ):
            decode_runner_config(json.dumps(tainted).encode())


def test_v39_does_not_imply_a_new_capability_flag() -> None:
    config = _v39(
        v3_capability_flags=V3CapabilityFlags(),
    )
    assert config.structured_commitments is not None
    assert config.v3_capability_flags.enabled_names() == ()
