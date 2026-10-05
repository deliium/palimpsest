"""Observer frames carry current environment tokens and no calendar."""

from __future__ import annotations

import ast
from pathlib import Path

from agents.models import AgentId
from api.observer_service import _frame_out
from observer.adapt import adapt_event, adapt_events
from observer.layout import catalog_from_mapping
from observer.project import project_frame
from observer.version import OBSERVER_PROTOCOL_VERSION, SEMANTIC_EVENT_TYPES
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.observer_facts import ObjectiveFacts, environment_view, scene_from_facts
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_resource,
    make_weather,
    weather_for_locations,
)
from tests.unit.test_environmental_dynamics_events import (
    _environment_details,
    _event,
    _system,
)
from world._replay import project_event_prefix
from world._state import WorldState
from world.actions import Wait
from world.effects import SystemEffectFamily
from world.environment import (
    ActiveHazard,
    HazardKind,
    example_environmental_dynamics,
    scarcity_scenario_dynamics,
)
from world.events import (
    EVENT_SCHEMA_REPLAY_V7,
    EnvironmentalHazardEnded,
    EnvironmentalHazardStarted,
    ResourceNodeDepleted,
    ResourceNodeRecovered,
    SeasonChanged,
    TemperatureBandChanged,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.values import ResourceKind

_LAYOUT = catalog_from_mapping(
    {
        "schema_version": "observer-layout-v1",
        "layout_id": "environment-empty",
        "locations": [],
    }
)
_FORBIDDEN = frozenset(
    {
        "animation",
        "color",
        "dx",
        "dy",
        "pixels",
        "screen_x",
        "screen_y",
        "sprite",
    }
)


def test_semantic_catalog_gains_six_environment_types() -> None:
    assert OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"
    assert len(SEMANTIC_EVENT_TYPES) == 41
    assert SEMANTIC_EVENT_TYPES[26:32] == (
        "SEASON_CHANGED",
        "TEMPERATURE_BAND_CHANGED",
        "RESOURCE_NODE_DEPLETED",
        "RESOURCE_NODE_RECOVERED",
        "ENVIRONMENTAL_HAZARD_STARTED",
        "ENVIRONMENTAL_HAZARD_ENDED",
    )


def test_adapted_events_publish_tokens_only_when_set() -> None:
    cause = _system(SystemEffectFamily.SEASON, "loc-a")
    for details in _environment_details():
        adapted = adapt_event(
            _event(details, schema_version=EVENT_SCHEMA_REPLAY_V7, cause=cause)
        )
        mapping = adapted.public_mapping()
        assert adapted.type in SEMANTIC_EVENT_TYPES
        assert "pixels" not in mapping
        assert "color" not in mapping
        if adapted.type == "SEASON_CHANGED":
            assert mapping["season"] == "summer"
        else:
            assert "season" not in mapping


def test_absent_spec_omits_environment_tokens() -> None:
    season, bands, hazards = environment_view(
        spec=None,
        tick=6,
        locations=(make_location(),),
        weather=(make_weather(),),
        active_hazards=(),
        rules=default_physical_rules(),
    )
    assert season is None
    assert bands == ()
    assert hazards == ()


def test_present_spec_derives_the_current_band_and_hazard() -> None:
    spec = example_environmental_dynamics()
    hazard = ActiveHazard(
        location_id=make_location().entity_id,
        kind=HazardKind.HEAT,
        start_tick=54,
        duration_ticks=6,
    )
    season, bands, hazards = environment_view(
        spec=spec,
        tick=54,
        locations=(make_location(),),
        weather=(make_weather(),),
        active_hazards=(hazard,),
        rules=default_physical_rules(),
    )
    assert season == "summer"
    assert bands == (("loc-1", "hot"),)
    assert hazards == (("loc-1", "heat", 6),)


def test_observer_package_does_not_import_the_spec() -> None:
    root = Path("src/observer")
    for path in root.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("world.environment")
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith("world.environment")
                    for alias in node.names
                )


def test_prefix_frame_matches_the_live_scene() -> None:
    spec = scarcity_scenario_dynamics()
    engine = _observer_engine(spec)
    for tick in (1, 4, 9):
        while engine.tick.value <= tick:
            before = engine._snapshot.world.state
            token = engine.observe().token
            result = engine.resolve_tick(
                (ActionSubmission(token, AgentId("agent-1"), Wait()),)
            )
        live = engine.detached_objective_facts()
        folded = project_event_prefix(
            before,
            tuple(record.event for record in result.events),
            expected_run_id=engine.run_id.value,
            expected_world_id=engine.world_id,
            includes_last_event=True,
            environmental_dynamics=spec,
        )
        replay = project_frame(
            scene_from_facts(_facts_from_state(engine, folded, live.tick)),
            _LAYOUT,
            mode="replay",
            events=adapt_events(tuple(record.event for record in result.events)),
        )
        shown = project_frame(
            scene_from_facts(live),
            _LAYOUT,
            mode="live",
            events=adapt_events(tuple(record.event for record in result.events)),
        )
        assert replay.world.season == shown.world.season
        assert replay.world.temperature_bands == shown.world.temperature_bands
        assert tuple(item.hazard_kind for item in replay.world.hazards) == tuple(
            item.hazard_kind for item in shown.world.hazards
        )
        assert tuple(item.condition for item in replay.world.weather) == tuple(
            item.condition for item in shown.world.weather
        )
        assert tuple(item.quantity for item in replay.world.resources) == tuple(
            item.quantity for item in shown.world.resources
        )


def test_dynamics_off_frame_omits_environment_keys() -> None:
    engine = _observer_engine(None)
    token = engine.observe().token
    engine.resolve_tick((ActionSubmission(token, AgentId("agent-1"), Wait()),))
    frame = project_frame(
        scene_from_facts(engine.detached_objective_facts()),
        _LAYOUT,
        mode="live",
        events=(),
    )
    assert frame.protocol_version == "observer-protocol-v1"
    assert frame.world.season is None
    payload = _frame_out(frame).model_dump(mode="json")
    assert payload["protocol_version"] == "observer-protocol-v1"
    assert "season" not in payload["world"]
    assert "temperature_bands" not in payload["world"]
    assert "hazards" not in payload["world"]


def test_world_and_events_carry_no_drawing_fields() -> None:
    names = set(WorldState.__slots__)
    for detail in (
        SeasonChanged,
        TemperatureBandChanged,
        ResourceNodeDepleted,
        ResourceNodeRecovered,
        EnvironmentalHazardStarted,
        EnvironmentalHazardEnded,
    ):
        names.update(detail.__slots__)
    assert names.isdisjoint(_FORBIDDEN)


def _observer_engine(spec: object | None) -> WorldEngine:
    locations = (make_location("loc-1"),)
    return WorldEngine(
        config=SimulationRunConfig(seed=4),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            locations=locations,
            bodies=(alive_body(),),
            resources=(
                make_resource(
                    kind=ResourceKind.FOOD,
                    quantity=1.0,
                    maximum_quantity=1.0,
                    regeneration_per_tick=1.0,
                ),
            ),
            weather=weather_for_locations(locations),
            registrations=(
                AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            ),
        ),
        environmental_dynamics=spec,
    )


def _facts_from_state(
    engine: WorldEngine, state: WorldState, tick: int
) -> ObjectiveFacts:
    rules = engine._config.physical_rules
    if rules is None:
        rules = default_physical_rules()
    locations = tuple(
        sorted(state.locations.values(), key=lambda item: item.entity_id.value)
    )
    weather = tuple(
        sorted(state.weather.values(), key=lambda item: item.location_id.value)
    )
    season, bands, hazards = environment_view(
        spec=engine._environmental_dynamics,
        tick=tick,
        locations=locations,
        weather=weather,
        active_hazards=state.active_hazards,
        rules=rules,
    )
    return ObjectiveFacts(
        run_id=engine.run_id.value,
        world_id=engine.world_id.value,
        tick=tick,
        revision=state.revision.value,
        locations=locations,
        bodies=tuple(state.bodies.values()),
        items=tuple(state.items.values()),
        resources=tuple(state.resources.values()),
        weather=weather,
        registrations=tuple(engine._registrations),
        season=season,
        temperature_bands=bands,
        hazards=hazards,
    )
