"""Lifecycle observation fields: channel gating and live/restored parity."""

from __future__ import annotations

import json
import logging

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.observations import Observation

_LOG = logging.getLogger("tests.lifecycle_observation_parity")


def _engine(*, channel_on: bool) -> WorldEngine:
    body = alive_body("body-1")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-lifecycle-obs"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )
    if not channel_on:
        return WorldEngine(
            config=SimulationRunConfig(
                seed=9, physical_rules=non_lethal_physical_rules()
            ),
            bootstrap=bootstrap,
        )
    spec = example_population_lifecycle_spec(lifespan_ticks=20)
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=spec
    )
    return WorldEngine(
        config=SimulationRunConfig(seed=9, physical_rules=non_lethal_physical_rules()),
        bootstrap=bootstrap,
        population_lifecycle=spec,
        lifecycle_records=records,
    )


def test_flag_off_observation_has_no_lifecycle_keys() -> None:
    _LOG.debug("case_id=obs_channel_off")
    engine = _engine(channel_on=False)
    batch = engine.observe()
    observation = batch.observations[0]
    assert observation.self_body is not None
    assert observation.self_body.lifecycle is None
    encoded = json.loads(encode_domain(observation))
    assert "lifecycle" not in encoded["data"].get("self_body", {})


def test_flag_on_observation_exposes_lifecycle_object() -> None:
    _LOG.debug("case_id=obs_channel_on")
    engine = _engine(channel_on=True)
    batch = engine.observe()
    observation = batch.observations[0]
    assert observation.self_body is not None
    assert observation.self_body.lifecycle is not None
    assert observation.self_body.lifecycle.chronological_age == 0
    assert observation.self_body.lifecycle.stage == "infant"
    assert observation.self_body.lifecycle.dependency_status == "dependent"


def test_lifecycle_observation_round_trip_parity() -> None:
    _LOG.debug("case_id=obs_encode_decode_parity")
    engine = _engine(channel_on=True)
    live = engine.observe().observations[0]
    restored = decode_domain(encode_domain(live))
    assert type(restored) is Observation
    assert restored.self_body is not None
    assert live.self_body is not None
    assert restored.self_body.lifecycle == live.self_body.lifecycle
    payload = json.loads(encode_domain(live))["data"]["self_body"]
    assert set(payload["lifecycle"]) == {
        "chronological_age",
        "stage",
        "dependency_status",
    }
