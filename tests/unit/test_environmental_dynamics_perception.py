"""Agents see the current season, band, and local hazards only."""

from __future__ import annotations

import json
import logging

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.models import SimulationRunConfig
from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_resource,
    make_weather,
    weather_for_locations,
)
from world._perception import project_observations
from world._state import ActiveHazard, WorldState
from world.environment import (
    HazardKind,
    Season,
    TemperatureBand,
    example_environmental_dynamics,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import (
    CONTENT_VISIBILITY_THRESHOLD,
    Observation,
    ObservationContext,
)
from world.values import ResourceKind, WeatherCondition

_FORBIDDEN = (
    "season_length_ticks",
    "multiplier",
    "windows",
    "next_season",
    "hazard_rules",
    "remaining_ticks",
)


def _state(*, tick_hazards: tuple[ActiveHazard, ...] = ()) -> WorldState:
    return WorldState(
        WorldRevision(1),
        locations=(make_location("loc-1"),),
        resources=(
            make_resource(
                "res-food",
                name="Food",
                kind=ResourceKind.FOOD,
                quantity=1.0,
                regeneration_per_tick=1.0,
            ),
        ),
        bodies=(alive_body(),),
        weather=(make_weather("loc-1", condition=WeatherCondition.CLEAR),),
        active_hazards=tick_hazards,
    )


def _payload(observation: Observation) -> dict[str, object]:
    document = json.loads(encode_domain(observation))
    data = document["data"]
    assert isinstance(data, dict)
    return data


def test_spec_off_omits_environment_keys_and_round_trips() -> None:
    observed = project_observations(
        world_id=WorldId("world-1"),
        state=_state(),
        observer_ids=(EntityId("body-1"),),
        context=ObservationContext(tick=6),
    )[0]
    assert observed.season is None
    assert observed.temperature_band is None
    assert observed.hazard_kinds is None
    payload = _payload(observed)
    assert "season" not in payload
    assert "temperature_band" not in payload
    assert "hazard_kinds" not in payload
    restored = decode_domain(encode_domain(observed))
    assert restored == observed


def test_spec_on_exposes_only_the_present(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="world._perception")
    hazard = ActiveHazard(EntityId("loc-1"), HazardKind.HEAT, 54, 6)
    observed = project_observations(
        world_id=WorldId("world-1"),
        state=_state(tick_hazards=(hazard,)),
        observer_ids=(EntityId("body-1"),),
        context=ObservationContext(tick=54),
        environmental_dynamics=example_environmental_dynamics(),
    )[0]
    assert observed.season is Season.SUMMER
    assert observed.temperature_band is TemperatureBand.HOT
    assert observed.hazard_kinds == (HazardKind.HEAT,)
    food = next(
        resource
        for resource in observed.resources
        if resource.entity_id == EntityId("res-food")
    )
    assert food.quantity == 1.0
    assert CONTENT_VISIBILITY_THRESHOLD == 0.5
    payload = _payload(observed)
    assert payload["season"] == "summer"
    assert payload["temperature_band"] == "hot"
    assert payload["hazard_kinds"] == ["heat"]
    for name in _FORBIDDEN:
        assert name not in payload
    assert any(
        "environment_observed season=summer band=hot hazard_count=1"
        in record.getMessage()
        for record in caplog.records
    )
    assert not any("tick=" in record.getMessage() for record in caplog.records)


def test_constructed_observation_has_no_calendar() -> None:
    observation = Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(1),
        season=Season.WINTER,
        temperature_band=TemperatureBand.COLD,
        hazard_kinds=(HazardKind.COLD_SNAP,),
    )
    payload = _payload(observation)
    for name in _FORBIDDEN:
        assert name not in payload


def test_engine_observe_follows_the_spec() -> None:
    locations = (make_location("loc-1"),)
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(alive_body(),),
        weather=weather_for_locations(locations),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
    )
    off = WorldEngine(config=SimulationRunConfig(seed=1), bootstrap=bootstrap)
    on = WorldEngine(
        config=SimulationRunConfig(seed=1),
        bootstrap=bootstrap,
        environmental_dynamics=example_environmental_dynamics(),
    )
    plain = off.observe().observations[0]
    present = on.observe().observations[0]
    assert plain.season is None
    assert present.season is Season.SPRING
    assert present.temperature_band is TemperatureBand.MILD
    assert present.hazard_kinds == ()
    assert decode_domain(encode_domain(plain)) == plain
