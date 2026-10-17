"""Replay v18 / codec v15 selection for subjective valuation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.configuration import build_cognitive_loop
from agents.cognition.structured_commitments import empty_structured_commitments
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine, _bind_subjective_valuation_channel
from simulation.models import SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_REPLAY_V16,
    EVENT_SCHEMA_REPLAY_V17,
    EVENT_SCHEMA_REPLAY_V18,
    checkpoint_schema_for_production,
)
from simulation.runner import _subjective_valuation_loop_kwargs
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V39,
    RUNNER_SCHEMA_VERSION_V40,
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
    example_structured_commitments_spec,
    example_subjective_valuation_spec,
)
from simulation.serialization import (
    DomainSerializationError,
    _decode_event_details,
    decode_structured_commitments_checkpoint,
    structured_commitments_checkpoint_payload,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules


def _plain_base():
    body_a = alive_body("body-a")
    agent_a = AgentId("agent-a")
    return base_runner_config_from_scenario(
        seed=40,
        stochastic_identity="cmp-v40-replay",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v40-replay"),
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
    assert idle[0] != EVENT_SCHEMA_REPLAY_V18
    assert idle[1] != "v15"


def test_commitments_without_valuation_stay_v17() -> None:
    pair = checkpoint_schema_for_production(
        production_active=False,
        structured_commitments_active=True,
        subjective_valuation_active=False,
    )
    assert pair == (EVENT_SCHEMA_REPLAY_V17, "v14")


def test_valuation_selects_v18_ahead_of_commitments() -> None:
    alone = checkpoint_schema_for_production(
        production_active=False,
        subjective_valuation_active=True,
    )
    assert alone == (EVENT_SCHEMA_REPLAY_V18, "v15")
    both = checkpoint_schema_for_production(
        production_active=False,
        structured_commitments_active=True,
        subjective_valuation_active=True,
    )
    assert both == (EVENT_SCHEMA_REPLAY_V18, "v15")
    possession = checkpoint_schema_for_production(
        production_active=False,
        possession_succession_active=True,
        subjective_valuation_active=False,
    )
    assert possession == (EVENT_SCHEMA_REPLAY_V16, "v13")


def test_v15_codec_keeps_commitment_payload_and_v13_rejects_it() -> None:
    owner = AgentId("agent-a")
    ledgers = {owner.value: empty_structured_commitments(owner)}
    v15 = structured_commitments_checkpoint_payload(ledgers, codec="v15")
    v14 = structured_commitments_checkpoint_payload(ledgers, codec="v14")
    assert "structured_commitments" in v15
    assert "structured_commitments" in v14
    assert decode_structured_commitments_checkpoint(v15, codec="v15")
    assert structured_commitments_checkpoint_payload(ledgers, codec="v13") == {}
    with pytest.raises(
        DomainSerializationError, match="structured_commitments_requires_codec_v14"
    ):
        decode_structured_commitments_checkpoint(v14, codec="v13")


def test_replay_v17_rejects_exchange_proposed() -> None:
    with pytest.raises(DomainSerializationError, match="invalid_event_schema_version"):
        _decode_event_details(
            {"kind": "exchange_proposed"},
            path="$.details",
            schema_version=EVENT_SCHEMA_REPLAY_V17,
        )


def test_v40_loop_kwargs_carry_horizon_and_v39_stays_off() -> None:
    spec = example_subjective_valuation_spec()
    v40 = replace(
        _plain_base(),
        schema_version=RUNNER_SCHEMA_VERSION_V40,
        subjective_valuation=replace(spec, horizon_ticks=12, max_bundle=4),
    )
    kwargs = _subjective_valuation_loop_kwargs(v40)
    assert kwargs["subjective_valuation_active"] is True
    assert kwargs["horizon_ticks"] == 12
    assert kwargs["max_bundle"] == 4
    loop = build_cognitive_loop(**kwargs)
    assert loop._subjective_valuation_active is True
    assert loop._subjective_valuation_horizon == 12
    assert loop._subjective_valuation_max_bundle == 4

    v39 = replace(
        _plain_base(),
        schema_version=RUNNER_SCHEMA_VERSION_V39,
        structured_commitments=example_structured_commitments_spec(),
    )
    off = _subjective_valuation_loop_kwargs(v39)
    assert off == {"subjective_valuation_active": False}
    off_loop = build_cognitive_loop(**off)
    assert off_loop._subjective_valuation_active is False


def test_engine_init_and_restore_keep_horizon() -> None:
    body = alive_body("body-a")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-v40-engine"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-a"), EntityId("body-a")),),
    )
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=40,
            physical_rules=default_physical_rules(),
        ),
        bootstrap=bootstrap,
        subjective_valuation_active=True,
        subjective_valuation_horizon=12,
        subjective_valuation_max_bundle=4,
    )
    assert engine.subjective_valuation_active is True
    assert engine._subjective_valuation_horizon == 12
    assert engine._subjective_valuation_max_bundle == 4

    class _Restored:
        pass

    restored = _Restored()
    spec = replace(example_subjective_valuation_spec(), horizon_ticks=9, max_bundle=3)

    class _Config:
        subjective_valuation = spec

    _bind_subjective_valuation_channel(restored, _Config())
    assert restored._subjective_valuation_active is True
    assert restored._subjective_valuation_horizon == 9
    assert restored._subjective_valuation_max_bundle == 3
