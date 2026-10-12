"""Replay v18 / codec v16 selection for the resource-exchange profile."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.cognition.acceptance_memory import empty_acceptance_memories
from agents.cognition.configuration import build_cognitive_loop
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.persistence import (
    EVENT_SCHEMA_REPLAY_V18,
    checkpoint_schema_for_production,
)
from simulation.runner import _resource_exchange_profile_loop_kwargs
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V41,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
    example_resource_exchange_profile_spec,
    example_subjective_valuation_spec,
)
from simulation.serialization import (
    DomainSerializationError,
    acceptance_memories_checkpoint_payload,
    decode_acceptance_memories_checkpoint,
    decode_subjective_valuation_checkpoint,
    subjective_valuation_checkpoint_payload,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _plain_base():
    body_a = alive_body("body-a")
    agent_a = AgentId("agent-a")
    return base_runner_config_from_scenario(
        seed=41,
        stochastic_identity="cmp-v41-replay",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v41-replay"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body_a,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_a,
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_a),
            ),
        ),
        max_ticks=1,
    )


def test_profile_selects_v16_ahead_of_valuation() -> None:
    pair = checkpoint_schema_for_production(
        production_active=False,
        subjective_valuation_active=True,
        resource_exchange_profile_active=True,
    )
    assert pair == (EVENT_SCHEMA_REPLAY_V18, "v16")


def test_valuation_without_profile_stays_v15() -> None:
    pair = checkpoint_schema_for_production(
        production_active=False,
        subjective_valuation_active=True,
        resource_exchange_profile_active=False,
    )
    assert pair == (EVENT_SCHEMA_REPLAY_V18, "v15")


def test_channel_off_does_not_select_v16() -> None:
    pair = checkpoint_schema_for_production(production_active=False)
    assert pair[1] != "v16"


def test_v15_omits_acceptance_memories_and_v16_round_trips(
    caplog: pytest.LogCaptureFixture,
) -> None:
    memories = {"agent-a": empty_acceptance_memories(AgentId("agent-a"))}
    with caplog.at_level(logging.DEBUG, logger="simulation.serialization"):
        omitted = acceptance_memories_checkpoint_payload(memories, codec="v15")
    assert omitted == {}
    assert any("acceptance_memories omitted" in rec.message for rec in caplog.records)
    payload = acceptance_memories_checkpoint_payload(memories, codec="v16")
    assert "acceptance_memories" in payload
    restored = decode_acceptance_memories_checkpoint(payload, codec="v16")
    assert "agent-a" in restored


def test_pre_v16_payload_rejects_acceptance_memories(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="simulation.serialization"):
        with pytest.raises(
            DomainSerializationError, match="acceptance_memories_requires_codec_v16"
        ):
            decode_acceptance_memories_checkpoint(
                {"acceptance_memories": {}}, codec="v15"
            )
    assert any("pre-v16" in rec.message for rec in caplog.records)


def test_v16_still_carries_valuation_ledgers() -> None:
    empty = subjective_valuation_checkpoint_payload({}, {}, codec="v16")
    assert "subjective_valuations" in empty
    assert "scarcity_beliefs" in empty
    restored = decode_subjective_valuation_checkpoint(empty, codec="v16")
    assert restored["subjective_valuations"] == {}


def test_loop_kwargs_carry_window_only() -> None:
    config = replace(
        _plain_base(),
        schema_version=RUNNER_SCHEMA_VERSION_V41,
        subjective_valuation=example_subjective_valuation_spec(),
        resource_exchange_profile=example_resource_exchange_profile_spec(),
    )
    kwargs = _resource_exchange_profile_loop_kwargs(config)
    assert kwargs == {
        "resource_exchange_profile_active": True,
        "acceptance_window_ticks": 32,
    }
    assert "horizon_ticks" not in kwargs
    loop = build_cognitive_loop(**kwargs)
    assert loop._resource_exchange_profile_active is True
    assert loop._acceptance_window_ticks == 32
