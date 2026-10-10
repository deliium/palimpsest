"""Replay v17 / codec v14 selection for structured commitments."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.configuration import build_cognitive_loop
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.persistence import (
    EVENT_SCHEMA_REPLAY_V16,
    EVENT_SCHEMA_REPLAY_V17,
    checkpoint_schema_for_production,
)
from simulation.runner import _structured_commitments_loop_kwargs
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V38,
    RUNNER_SCHEMA_VERSION_V39,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
    example_possession_succession_spec,
    example_structured_commitments_spec,
)
from simulation.serialization import DomainSerializationError, _decode_event_details
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.events import EVENT_SCHEMA_REPLAY_V17 as WORLD_REPLAY_V17
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _plain_base():
    body_a = alive_body("body-a")
    agent_a = AgentId("agent-a")
    return base_runner_config_from_scenario(
        seed=39,
        stochastic_identity="cmp-v39-replay",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v39-replay"),
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


def test_channel_off_keeps_previous_pair() -> None:
    idle = checkpoint_schema_for_production(production_active=False)
    assert idle[0] != EVENT_SCHEMA_REPLAY_V17
    assert idle[1] != "v14"


def test_possession_without_commitments_stays_v16() -> None:
    pair = checkpoint_schema_for_production(
        production_active=False,
        possession_succession_active=True,
        structured_commitments_active=False,
    )
    assert pair == (EVENT_SCHEMA_REPLAY_V16, "v13")


def test_commitments_select_v17_ahead_of_possession() -> None:
    alone = checkpoint_schema_for_production(
        production_active=False,
        structured_commitments_active=True,
    )
    assert alone == (EVENT_SCHEMA_REPLAY_V17, "v14")
    both = checkpoint_schema_for_production(
        production_active=False,
        possession_succession_active=True,
        structured_commitments_active=True,
    )
    assert both == (WORLD_REPLAY_V17, "v14")


def test_replay_v16_rejects_commitment_declared() -> None:
    with pytest.raises(DomainSerializationError, match="invalid_event_schema_version"):
        _decode_event_details(
            {"kind": "commitment_declared"},
            path="$.details",
            schema_version=EVENT_SCHEMA_REPLAY_V16,
        )


def test_v39_loop_kwargs_carry_cap_and_v38_does_not() -> None:
    v39 = replace(
        _plain_base(),
        schema_version=RUNNER_SCHEMA_VERSION_V39,
        structured_commitments=example_structured_commitments_spec(),
    )
    kwargs = _structured_commitments_loop_kwargs(v39)
    assert kwargs["structured_commitments_active"] is True
    assert kwargs["max_open_interpretations"] == 8
    loop = build_cognitive_loop(**kwargs)
    assert loop._structured_commitments_active is True
    assert loop._max_open_interpretations == 8

    v38 = replace(
        _plain_base(),
        schema_version=RUNNER_SCHEMA_VERSION_V38,
        possession_succession=example_possession_succession_spec(),
    )
    off = _structured_commitments_loop_kwargs(v38)
    assert off == {"structured_commitments_active": False}
    off_loop = build_cognitive_loop(**off)
    assert off_loop._structured_commitments_active is False
    assert off_loop._max_open_interpretations is None
