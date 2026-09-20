"""Physical visibility, redaction, and noninterference proofs."""

from __future__ import annotations

import logging

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from simulation.serialization import encode_domain
from tests.simulation_helpers import (
    connected_locations,
    make_item,
    make_location,
    make_resource,
    make_weather,
)
from world._perception import PerceptionService
from world._state import WorldState, rebuild_world_state
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import (
    AgentBody,
    Item,
    LifeStatus,
    Location,
    Resource,
    copy_body,
    copy_item,
    copy_weather,
)
from world.observations import (
    CONTENT_VISIBILITY_THRESHOLD,
    CoarseHealth,
    Observation,
    ObservationContext,
    ObservedItemPlacement,
    ObservedSelf,
    VisibleBody,
    coarse_health_for,
)
from world.values import (
    CarryCapacity,
    DayPhase,
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ItemLoad,
    TemperatureCelsius,
    Thirst,
    UnitInterval,
    WeatherCondition,
)

_WORLD = WorldId("world-1")
_SERVICE = PerceptionService()
_FORBIDDEN_ATTRS = (
    "body_capacity",
    "item_capacity",
    "shelter_factor",
    "visibility_factor",
    "base_temperature",
    "maximum_quantity",
    "regeneration_per_tick",
    "carry_capacity",  # on VisibleBody / other bodies only
    "hunger",
    "thirst",
    "fatigue",
    "temperature",
    "inventory",
)


def _body(
    entity_id: str,
    location_id: str,
    *,
    inventory: tuple[EntityId, ...] = (),
    health: float = 100.0,
    hunger: float = 0.0,
    thirst: float = 0.0,
    fatigue: float = 0.0,
    dead: bool = False,
) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(0.0 if dead else health),
        hunger=Hunger(hunger),
        thirst=Thirst(thirst),
        fatigue=Fatigue(fatigue),
        temperature=TemperatureCelsius(36.5),
        inventory=inventory,
        life_status=LifeStatus.DEAD if dead else LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _base_state(
    *,
    weather_loc1: WeatherCondition = WeatherCondition.CLEAR,
    weather_loc2: WeatherCondition = WeatherCondition.CLEAR,
    visibility_loc1: float = 1.0,
    body2_health: float = 100.0,
    body2_hunger: float = 0.0,
    body2_inventory: tuple[EntityId, ...] = (),
) -> WorldState:
    locations = (
        make_location(
            "loc-1",
            name="Camp",
            adjacent=(EntityId("loc-2"),),
            visibility_factor=visibility_loc1,
        ),
        make_location(
            "loc-2",
            name="Forest",
            adjacent=(EntityId("loc-1"),),
        ),
    )
    held = make_item("item-held", name="Cup", location_id=None, holder_id="body-1")
    ground = make_item("item-ground", name="Rock", location_id="loc-1")
    remote_item = make_item("item-far", name="OreChunk", location_id="loc-2")
    secret = make_item(
        "item-secret", name="Secret", location_id=None, holder_id="body-2"
    )
    items: tuple[Item, ...] = (held, ground, remote_item, secret)
    inventory_two = body2_inventory or (EntityId("item-secret"),)
    return WorldState(
        WorldRevision(1),
        locations=locations,
        items=items,
        resources=(
            make_resource(
                "res-local",
                name="Spring",
                location_id="loc-1",
                quantity=3.0,
                unit="L",
            ),
            make_resource(
                "res-far",
                name="Berries",
                location_id="loc-2",
                quantity=2.0,
                unit="kg",
            ),
        ),
        bodies=(
            _body("body-1", "loc-1", inventory=(EntityId("item-held"),)),
            _body(
                "body-2",
                "loc-2",
                inventory=inventory_two,
                health=body2_health,
                hunger=body2_hunger,
            ),
            _body("body-local", "loc-1", health=40.0, hunger=55.0),
            _body("body-dead", "loc-1", dead=True),
        ),
        weather=(
            make_weather("loc-1", condition=weather_loc1),
            make_weather("loc-2", condition=weather_loc2),
        ),
    )


def _observe(
    state: WorldState,
    observer: str = "body-1",
    *,
    tick: int = 12,
) -> Observation:
    return _SERVICE.project(
        world_id=_WORLD,
        state=state,
        observer_ids=(EntityId(observer),),
        context=ObservationContext(tick=tick),
    )[0]


def _assert_no_forbidden_fields(observation: Observation) -> None:
    for location in observation.locations:
        for attr in (
            "body_capacity",
            "item_capacity",
            "shelter_factor",
            "visibility_factor",
            "base_temperature",
            "adjacent",
        ):
            assert not hasattr(location, attr)
    for resource in observation.resources:
        for attr in ("maximum_quantity", "regeneration_per_tick", "location_id"):
            assert not hasattr(resource, attr)
    for body in observation.visible_bodies:
        assert type(body) is VisibleBody
        for attr in (
            "inventory",
            "hunger",
            "thirst",
            "fatigue",
            "temperature",
            "carry_capacity",
            "health",
        ):
            assert not hasattr(body, attr)


@pytest.mark.parametrize("condition", list(WeatherCondition))
@pytest.mark.parametrize(
    ("tick", "phase"),
    [
        (5, DayPhase.NIGHT),
        (6, DayPhase.DAY),
        (17, DayPhase.DAY),
        (18, DayPhase.NIGHT),
    ],
)
def test_weather_and_day_night_visibility_matrix(
    condition: WeatherCondition, tick: int, phase: DayPhase
) -> None:
    state = _base_state(weather_loc1=condition)
    obs = _observe(state, tick=tick)
    assert obs.day_phase is phase
    assert obs.weather_condition is condition
    assert obs.hour == tick % 24
    assert obs.visibility is not None
    content_visible = obs.visibility >= CONTENT_VISIBILITY_THRESHOLD
    ground_ids = {
        item.entity_id
        for item in obs.items
        if item.placement is ObservedItemPlacement.GROUND_HERE
    }
    held_ids = {
        item.entity_id
        for item in obs.items
        if item.placement is ObservedItemPlacement.HELD_BY_SELF
    }
    assert EntityId("item-held") in held_ids
    if content_visible:
        assert EntityId("item-ground") in ground_ids
        assert EntityId("res-local") in {r.entity_id for r in obs.resources}
        assert EntityId("body-local") in {b.entity_id for b in obs.visible_bodies}
    else:
        assert EntityId("item-ground") not in ground_ids
        assert obs.resources == ()
        assert all(
            body.entity_id != EntityId("body-local") for body in obs.visible_bodies
        )
    # Exits and self always available.
    assert obs.exits
    assert obs.exits[0].destination_id == EntityId("loc-2")
    assert isinstance(obs.self_body, ObservedSelf)
    # Remote facts never appear.
    assert EntityId("item-far") not in {item.entity_id for item in obs.items}
    assert EntityId("res-far") not in {r.entity_id for r in obs.resources}
    assert EntityId("body-2") not in {b.entity_id for b in obs.visible_bodies}
    _assert_no_forbidden_fields(obs)


@pytest.mark.parametrize(
    ("visibility_factor", "tick", "condition", "expect_content"),
    [
        (1.0, 12, WeatherCondition.CLEAR, True),  # 1.0
        (1.0, 0, WeatherCondition.CLEAR, True),  # 0.5 at threshold
        (1.0, 0, WeatherCondition.CLOUDY, False),  # 0.45
        (1.0, 0, WeatherCondition.STORM, False),  # 0.25
        (0.4, 12, WeatherCondition.CLEAR, False),  # 0.4
        (0.5, 12, WeatherCondition.CLEAR, True),  # 0.5
    ],
)
def test_content_visibility_threshold_boundaries(
    visibility_factor: float,
    tick: int,
    condition: WeatherCondition,
    expect_content: bool,
) -> None:
    state = _base_state(weather_loc1=condition, visibility_loc1=visibility_factor)
    obs = _observe(state, tick=tick)
    assert obs.visibility is not None
    assert (obs.visibility >= CONTENT_VISIBILITY_THRESHOLD) is expect_content
    has_ground = any(item.entity_id == EntityId("item-ground") for item in obs.items)
    assert has_ground is expect_content
    assert (len(obs.resources) > 0) is expect_content


@pytest.mark.parametrize(
    ("health", "expected"),
    [
        (100.0, CoarseHealth.STABLE),
        (76.0, CoarseHealth.STABLE),
        (75.0, CoarseHealth.INJURED),
        (26.0, CoarseHealth.INJURED),
        (25.0, CoarseHealth.CRITICAL),
        (1.0, CoarseHealth.CRITICAL),
        (0.0, CoarseHealth.DEAD),
    ],
)
def test_coarse_health_bands(health: float, expected: CoarseHealth) -> None:
    dead = health <= 0.0
    body = _body("body-x", "loc-1", health=health, dead=dead)
    assert coarse_health_for(body) is expected
    state = _base_state()
    # Put the band subject colocated and visible.
    bodies = dict(state.bodies)
    bodies[EntityId("body-local")] = copy_body(
        bodies[EntityId("body-local")],
        health=Health(0.0 if dead else health),
        life_status=LifeStatus.DEAD if dead else LifeStatus.ALIVE,
        hunger=Hunger(0.0),
    )
    mutated = rebuild_world_state(state, bodies=bodies)
    obs = _observe(mutated, tick=12)
    visible = {body.entity_id: body for body in obs.visible_bodies}
    assert visible[EntityId("body-local")].coarse_health is expected


def test_dead_observer_keeps_self_time_and_environment() -> None:
    obs = _observe(_base_state(), observer="body-dead", tick=12)
    assert obs.self_body is not None
    assert obs.self_body.life_status is LifeStatus.DEAD
    assert obs.hour == 12
    assert obs.day_phase is DayPhase.DAY
    assert obs.weather_condition is WeatherCondition.CLEAR
    assert obs.locations[0].entity_id == EntityId("loc-1")
    assert obs.exits


def test_hidden_remote_state_noninterference() -> None:
    base = _base_state()
    baseline = _observe(base, tick=12)
    baseline_bytes = encode_domain(baseline)

    # Mutate only remote body inventory, physiology, and remote weather/item qty.
    bodies = dict(base.bodies)
    bodies[EntityId("body-2")] = copy_body(
        bodies[EntityId("body-2")],
        health=Health(12.0),
        hunger=Hunger(99.0),
        thirst=Thirst(88.0),
        fatigue=Fatigue(77.0),
        temperature=TemperatureCelsius(34.0),
        inventory=(EntityId("item-secret"),),
    )
    items = dict(base.items)
    items[EntityId("item-secret")] = copy_item(items[EntityId("item-secret")])
    items[EntityId("item-far")] = Item(
        entity_id=EntityId("item-far"),
        name="OreChunk-mutated",
        kind=ItemKind.MATERIAL,
        load=ItemLoad(2),
        location_id=EntityId("loc-2"),
        holder_id=None,
    )
    resources = dict(base.resources)
    far = resources[EntityId("res-far")]
    resources[EntityId("res-far")] = Resource(
        entity_id=far.entity_id,
        name=far.name,
        kind=far.kind,
        location_id=far.location_id,
        quantity=9.0,
        maximum_quantity=99.0,
        regeneration_per_tick=5.0,
        unit=far.unit,
    )
    weather = dict(base.weather)
    weather[EntityId("loc-2")] = copy_weather(
        weather[EntityId("loc-2")], condition=WeatherCondition.STORM
    )
    # Remote location capacity / base temperature changes.
    locations = dict(base.locations)
    remote = locations[EntityId("loc-2")]
    locations[EntityId("loc-2")] = Location(
        entity_id=remote.entity_id,
        name=remote.name,
        adjacent=remote.adjacent,
        body_capacity=remote.body_capacity,
        item_capacity=remote.item_capacity,
        base_temperature=TemperatureCelsius(1.0),
        shelter_factor=UnitInterval(1.0),
        visibility_factor=UnitInterval(0.1),
    )
    mutated = rebuild_world_state(
        base,
        bodies=bodies,
        items=items,
        resources=resources,
        weather=weather,
        locations=locations,
    )
    observed = _observe(mutated, tick=12)
    assert observed == baseline
    assert encode_domain(observed) == baseline_bytes


def test_hidden_nearby_physiology_and_inventory_noninterference() -> None:
    base = _base_state()
    baseline = _observe(base, tick=12)
    baseline_bytes = encode_domain(baseline)
    # Keep health band STABLE while changing exact needs of colocated body.
    bodies = dict(base.bodies)
    local = bodies[EntityId("body-local")]
    assert coarse_health_for(local) is CoarseHealth.INJURED
    bodies[EntityId("body-local")] = copy_body(
        local,
        health=Health(40.0),  # still INJURED
        hunger=Hunger(100.0),
        thirst=Thirst(100.0),
        fatigue=Fatigue(100.0),
        temperature=TemperatureCelsius(33.0),
        inventory=(),
    )
    # Local resource regeneration/max policy change with same quantity.
    resources = dict(base.resources)
    spring = resources[EntityId("res-local")]
    resources[EntityId("res-local")] = Resource(
        entity_id=spring.entity_id,
        name=spring.name,
        kind=spring.kind,
        location_id=spring.location_id,
        quantity=spring.quantity,
        maximum_quantity=50.0,
        regeneration_per_tick=2.5,
        unit=spring.unit,
    )
    # Local location capacity/shelter policy fields.
    locations = dict(base.locations)
    camp = locations[EntityId("loc-1")]
    locations[EntityId("loc-1")] = Location(
        entity_id=camp.entity_id,
        name=camp.name,
        adjacent=camp.adjacent,
        body_capacity=camp.body_capacity.__class__(20),
        item_capacity=camp.item_capacity.__class__(40),
        base_temperature=camp.base_temperature,
        shelter_factor=UnitInterval(1.0),
        visibility_factor=camp.visibility_factor,
    )
    mutated = rebuild_world_state(
        base, bodies=bodies, resources=resources, locations=locations
    )
    observed = _observe(mutated, tick=12)
    assert observed == baseline
    assert encode_domain(observed) == baseline_bytes
    local_view = next(
        body
        for body in observed.visible_bodies
        if body.entity_id == EntityId("body-local")
    )
    assert local_view.coarse_health is CoarseHealth.INJURED
    assert not hasattr(local_view, "inventory")
    assert not hasattr(local_view, "hunger")


def test_local_resource_quantity_change_is_visible() -> None:
    base = _base_state()
    baseline = _observe(base, tick=12)
    resources = dict(base.resources)
    spring = resources[EntityId("res-local")]
    resources[EntityId("res-local")] = Resource(
        entity_id=spring.entity_id,
        name=spring.name,
        kind=spring.kind,
        location_id=spring.location_id,
        quantity=1.0,
        maximum_quantity=spring.maximum_quantity,
        regeneration_per_tick=spring.regeneration_per_tick,
        unit=spring.unit,
    )
    mutated = rebuild_world_state(base, resources=resources)
    observed = _observe(mutated, tick=12)
    assert observed != baseline
    by_id = {resource.entity_id: resource for resource in observed.resources}
    assert by_id[EntityId("res-local")].quantity == 1.0


@given(
    condition=st.sampled_from(list(WeatherCondition)),
    tick=st.integers(min_value=0, max_value=47),
)
@settings(max_examples=40, deadline=None)
def test_hypothesis_visibility_never_exposes_remote_or_policy_fields(
    condition: WeatherCondition, tick: int
) -> None:
    obs = _observe(_base_state(weather_loc1=condition), tick=tick)
    assert obs.self_body is not None
    assert obs.self_body.entity_id == EntityId("body-1")
    assert EntityId("body-2") not in {b.entity_id for b in obs.visible_bodies}
    assert EntityId("item-far") not in {i.entity_id for i in obs.items}
    assert EntityId("item-secret") not in {i.entity_id for i in obs.items}
    assert EntityId("res-far") not in {r.entity_id for r in obs.resources}
    _assert_no_forbidden_fields(obs)
    # Canonical bytes are stable for identical projection.
    assert encode_domain(obs) == encode_domain(
        _observe(_base_state(weather_loc1=condition), tick=tick)
    )


def test_projection_is_log_free(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    with caplog.at_level(logging.DEBUG, logger="world._perception"):
        _observe(_base_state(), tick=12)
    assert caplog.records == []


def test_engine_debug_logs_omit_observation_payloads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.models import AgentId
    from simulation.bootstrap import AgentRegistration, WorldBootstrap
    from simulation.engine import WorldEngine
    from simulation.lifecycle import EngineDiagnosticCode
    from simulation.models import SimulationRunConfig

    locations = connected_locations(("loc-1", "Camp"), ("loc-2", "Forest"))
    bootstrap = WorldBootstrap(
        world_id=_WORLD,
        revision=WorldRevision(0),
        locations=locations,
        bodies=(
            _body("body-1", "loc-1"),
            _body("body-2", "loc-2"),
        ),
        weather=(
            make_weather("loc-1"),
            make_weather("loc-2"),
        ),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )
    engine = WorldEngine(config=SimulationRunConfig(seed=7), bootstrap=bootstrap)
    caplog.set_level(logging.DEBUG, logger="simulation.engine")
    batch = engine.observe()
    _ = engine.observation_for(AgentId("agent-1"))
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert EngineDiagnosticCode.OBSERVATIONS_ISSUED.value in messages
    assert EngineDiagnosticCode.OBSERVATION_ROUTED.value in messages
    assert "Camp" not in messages
    assert "Forest" not in messages
    assert "self_body" not in messages
    assert "Observation(" not in messages
    assert "inventory" not in messages
    assert str(batch.observations[0]) not in messages
