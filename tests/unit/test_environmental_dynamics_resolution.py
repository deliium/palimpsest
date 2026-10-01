"""Opt-in seasons, yields, shortages, and hazards stay off the default step."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_resource,
    make_weather,
    weather_for_locations,
)
from world._operations import _DrinkOp, _SearchOp
from world._physical import apply_autonomous_physical_step
from world._production import _apply_harvest
from world._rules import apply_operation
from world._state import ActiveHazard, WorldState, rebuild_world_state
from world.actions import Harvest, Wait
from world.effects import (
    DeathCause,
    ResolvedActionEffects,
    ResolvedProductionEffect,
    ResolvedSearchEffect,
)
from world.environment import (
    EnvironmentalDynamicsSpec,
    HazardKind,
    Season,
    SeasonalYield,
    ShortageWindow,
    TemperatureBand,
    example_environmental_dynamics,
    scarcity_scenario_dynamics,
)
from world.events import (
    EnvironmentalHazardEnded,
    EnvironmentalHazardStarted,
    ExposureApplied,
    ResourceNodeDepleted,
    ResourceNodeRecovered,
    ResourceRegenerated,
    SeasonChanged,
    TemperatureBandChanged,
)
from world.identifiers import EntityId, RecipeId, RequestId, WorldId, WorldRevision
from world.models import PhysicalRules, non_lethal_physical_rules
from world.production import example_production_catalog
from world.values import DayPhase, ResourceKind, WeatherCondition


def _state(
    *,
    resources: tuple[object, ...] = (),
    bodies: tuple[object, ...] = (),
    weather: object | None = None,
    tick_weather: WeatherCondition = WeatherCondition.CLEAR,
) -> WorldState:
    locations = (make_location("loc-1"),)
    chosen = (
        (make_weather("loc-1", condition=tick_weather),)
        if weather is None
        else weather
    )
    return WorldState(
        WorldRevision(1),
        locations=locations,
        resources=resources,  # type: ignore[arg-type]
        bodies=bodies,  # type: ignore[arg-type]
        weather=chosen,  # type: ignore[arg-type]
    )


def _step(
    state: WorldState,
    *,
    tick: int,
    hour: int,
    phase: DayPhase,
    spec: EnvironmentalDynamicsSpec | None = None,
    weather: WeatherCondition | None = None,
    rules: PhysicalRules | None = None,
) -> object:
    resolved = None
    if weather is not None:
        from world.effects import ResolvedSystemEffects, ResolvedWeatherEffect

        resolved = ResolvedSystemEffects(
            weather_by_location={
                EntityId("loc-1"): ResolvedWeatherEffect(EntityId("loc-1"), weather)
            }
        )
    return apply_autonomous_physical_step(
        state=state,
        rules=rules if rules is not None else PhysicalRules(),
        tick=tick,
        hour=hour,
        day_phase=phase,
        resolved=resolved,
        environmental_dynamics=spec,
    )


def _all_ones() -> EnvironmentalDynamicsSpec:
    example = example_environmental_dynamics()
    yields = tuple(
        SeasonalYield(item.resource_kind, item.season, 1.0) for item in example.yields
    )
    return EnvironmentalDynamicsSpec(
        season_length_ticks=example.season_length_ticks,
        season_offsets=dict(example.season_offsets),
        yields=yields,
        shortage_windows=(),
        hazard_rules=(),
    )


def _kinds(step: object) -> list[str]:
    return [detail.details.kind for detail in step.pending_details]  # type: ignore[attr-defined]


def test_spec_off_matches_all_ones_and_skips_environment_events() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=1.0,
        maximum_quantity=3.0,
        regeneration_per_tick=1.0,
    )
    state = _state(resources=(food,), bodies=())
    plain = _step(state, tick=1, hour=0, phase=DayPhase.NIGHT)
    ones = _step(state, tick=1, hour=0, phase=DayPhase.NIGHT, spec=_all_ones())
    assert plain.working_state.resources[EntityId("res-food")].quantity == (  # type: ignore[attr-defined]
        ones.working_state.resources[EntityId("res-food")].quantity  # type: ignore[attr-defined]
    )
    assert "season_changed" not in _kinds(plain)
    assert plain.working_state.active_hazards == ()  # type: ignore[attr-defined]
    assert ones.working_state.active_hazards == ()  # type: ignore[attr-defined]
    assert list(DeathCause) == [
        DeathCause.ATTACK,
        DeathCause.COMBINED_NEEDS,
        DeathCause.EXPOSURE,
    ]


def test_winter_yield_and_shortage_suppress_regeneration_without_zeroing() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    water = make_resource(
        "res-water",
        name="Water",
        kind=ResourceKind.WATER,
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    state = _state(resources=(food, water), bodies=())
    winter = _step(
        state,
        tick=12,
        hour=0,
        phase=DayPhase.NIGHT,
        spec=scarcity_scenario_dynamics(),
    )
    assert winter.working_state.resources[EntityId("res-food")].quantity == 2.0  # type: ignore[attr-defined]
    assert winter.working_state.resources[EntityId("res-water")].quantity == 3.0  # type: ignore[attr-defined]
    assert "resource_regenerated" not in [
        detail.details.kind
        for detail in winter.pending_details  # type: ignore[attr-defined]
        if detail.entity_id == EntityId("res-food")
    ]
    window = ShortageWindow(ResourceKind.WATER, 1, 2)
    spec = EnvironmentalDynamicsSpec(
        season_length_ticks=48,
        season_offsets=dict(example_environmental_dynamics().season_offsets),
        yields=_all_ones().yields,
        shortage_windows=(window,),
        hazard_rules=(),
    )
    held = _step(state, tick=1, hour=6, phase=DayPhase.DAY, spec=spec)
    assert held.working_state.resources[EntityId("res-water")].quantity == 2.0  # type: ignore[attr-defined]
    assert held.working_state.resources[EntityId("res-food")].quantity == 3.0  # type: ignore[attr-defined]


def test_season_boundaries_bands_and_hazard_span() -> None:
    state = _state(bodies=(alive_body(),))
    spring = _step(
        state,
        tick=0,
        hour=6,
        phase=DayPhase.DAY,
        spec=example_environmental_dynamics(),
    )
    assert "season_changed" not in _kinds(spring)
    exposure = next(
        detail.details
        for detail in spring.pending_details  # type: ignore[attr-defined]
        if type(detail.details) is ExposureApplied
    )
    assert exposure.ambient_celsius == 22.0
    summer = _step(
        state,
        tick=54,
        hour=6,
        phase=DayPhase.DAY,
        spec=example_environmental_dynamics(),
    )
    summer_exposure = next(
        detail.details
        for detail in summer.pending_details  # type: ignore[attr-defined]
        if type(detail.details) is ExposureApplied
    )
    assert summer_exposure.ambient_celsius == 34.0
    winter = _step(
        _state(bodies=(alive_body(),)),
        tick=144,
        hour=0,
        phase=DayPhase.NIGHT,
        spec=example_environmental_dynamics(),
    )
    assert any(
        type(detail.details) is SeasonChanged
        for detail in winter.pending_details  # type: ignore[attr-defined]
    )
    season = next(
        detail
        for detail in winter.pending_details  # type: ignore[attr-defined]
        if type(detail.details) is SeasonChanged
    )
    assert season.entity_id == EntityId("loc-1")
    assert season.details.season is Season.WINTER
    winter_exposure = next(
        detail.details
        for detail in winter.pending_details  # type: ignore[attr-defined]
        if type(detail.details) is ExposureApplied
    )
    assert winter_exposure.ambient_celsius == 4.0
    assert any(
        type(detail.details) is TemperatureBandChanged
        and detail.details.band is TemperatureBand.COLD
        for detail in winter.pending_details  # type: ignore[attr-defined]
    )

    storm = _state(weather=(make_weather("loc-1", condition=WeatherCondition.STORM),))
    spec = scarcity_scenario_dynamics()
    current = storm
    started = None
    for tick in range(12, 18):
        phase = DayPhase.NIGHT
        hour = 0
        scheduled = (tick + 1) % 6 == 0
        stepped = _step(
            current,
            tick=tick,
            hour=hour,
            phase=phase,
            spec=spec,
            weather=WeatherCondition.STORM if scheduled else None,
        )
        if tick == 12:
            started = next(
                detail.details
                for detail in stepped.pending_details  # type: ignore[attr-defined]
                if type(detail.details) is EnvironmentalHazardStarted
            )
            assert started.duration_ticks == 6
            assert started.remaining_ticks == 6
            assert started.hazard_kind is HazardKind.COLD_SNAP
        current = stepped.working_state  # type: ignore[attr-defined]
        if tick < 17:
            assert current.active_hazards
            assert "environmental_hazard_ended" not in _kinds(stepped)
    assert current.active_hazards == ()
    ended = next(
        detail.details
        for detail in stepped.pending_details  # type: ignore[attr-defined]
        if type(detail.details) is EnvironmentalHazardEnded
    )
    assert ended.remaining_ticks == 0
    record = ActiveHazard(EntityId("loc-1"), HazardKind.COLD_SNAP, 12, 6)
    assert record.remaining_ticks(12) == 6
    assert record.remaining_ticks(16) == 2
    copied = rebuild_world_state(current, active_hazards=(record,))
    again = rebuild_world_state(copied)
    assert again.active_hazards == (record,)


def test_hazard_extra_is_suppressed_when_exposure_damage_is_zero() -> None:
    storm = _state(
        bodies=(alive_body(),),
        weather=(make_weather("loc-1", condition=WeatherCondition.STORM),),
    )
    lethal = _step(
        storm,
        tick=12,
        hour=0,
        phase=DayPhase.NIGHT,
        spec=example_environmental_dynamics(),
    )
    exposure = next(
        detail.details
        for detail in lethal.pending_details  # type: ignore[attr-defined]
        if type(detail.details) is ExposureApplied
    )
    assert exposure.health_delta == -5.0
    safe = _step(
        storm,
        tick=12,
        hour=0,
        phase=DayPhase.NIGHT,
        spec=example_environmental_dynamics(),
        rules=non_lethal_physical_rules(),
    )
    safe_exposure = next(
        detail.details
        for detail in safe.pending_details  # type: ignore[attr-defined]
        if type(detail.details) is ExposureApplied
    )
    assert safe_exposure.health_delta == 0.0


def test_node_witnesses_follow_zero_crossings() -> None:
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=0.0,
        maximum_quantity=2.0,
        regeneration_per_tick=1.0,
    )
    recovered = _step(
        _state(resources=(food,), bodies=()),
        tick=1,
        hour=6,
        phase=DayPhase.DAY,
        spec=_all_ones(),
    )
    assert any(
        type(detail.details) is ResourceRegenerated
        for detail in recovered.pending_details  # type: ignore[attr-defined]
    )
    assert any(
        type(detail.details) is ResourceNodeRecovered
        and detail.details.resulting_quantity == 1.0
        for detail in recovered.pending_details  # type: ignore[attr-defined]
    )
    request = RequestId("req-1")
    revision = WorldRevision(1)
    world = WorldId("world-1")
    depleted_state = _state(
        resources=(
            make_resource(
                "res-food",
                name="Food",
                kind=ResourceKind.FOOD,
                quantity=1.0,
                maximum_quantity=2.0,
                regeneration_per_tick=0.0,
            ),
        ),
        bodies=(alive_body(),),
    )
    searched = apply_operation(
        depleted_state,
        _SearchOp(request, EntityId("body-1"), world, revision, EntityId("res-food")),
        rules=PhysicalRules(),
        resolved=ResolvedActionEffects(
            by_request={
                request: ResolvedSearchEffect(
                    request,
                    True,
                    EntityId("res-food"),
                    created_item_id=EntityId("item-found"),
                )
            }
        ),
        witness_resource_nodes=True,
    )
    assert any(
        type(detail) is ResourceNodeDepleted and detail.resulting_quantity == 0.0
        for detail in searched.all_event_details()
    )
    searched_plain = apply_operation(
        depleted_state,
        _SearchOp(request, EntityId("body-1"), world, revision, EntityId("res-food")),
        rules=PhysicalRules(),
        resolved=ResolvedActionEffects(
            by_request={
                request: ResolvedSearchEffect(
                    request,
                    True,
                    EntityId("res-food"),
                    created_item_id=EntityId("item-found"),
                )
            }
        ),
    )
    assert not any(
        type(detail) is ResourceNodeDepleted
        for detail in searched_plain.all_event_details()
    )
    water = _state(
        resources=(
            make_resource(
                "res-water",
                name="Water",
                kind=ResourceKind.WATER,
                quantity=1.0,
                maximum_quantity=2.0,
                regeneration_per_tick=0.0,
            ),
        ),
        bodies=(alive_body(),),
    )
    drunk = apply_operation(
        water,
        _DrinkOp(request, EntityId("body-1"), world, revision, EntityId("res-water")),
        rules=PhysicalRules(),
        witness_resource_nodes=True,
    )
    assert any(
        type(detail) is ResourceNodeDepleted
        and detail.resource_id == EntityId("res-water")
        for detail in drunk.all_event_details()
    )


def test_same_seed_keeps_weather_and_seeds_do_not_move_seasons(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="simulation.engine")

    def trace(
        seed: int, spec: object | None
    ) -> tuple[tuple[str, ...], tuple[int, ...]]:
        locations = (make_location("loc-1"),)
        body = alive_body()
        body = type(body)(
            entity_id=body.entity_id,
            location_id=body.location_id,
            health=body.health,
            hunger=body.hunger,
            thirst=body.thirst,
            fatigue=body.fatigue,
            temperature=body.temperature,
            inventory=body.inventory,
            life_status=body.life_status,
            carry_capacity=body.carry_capacity,
        )
        engine = WorldEngine(
            config=SimulationRunConfig(seed=seed),
            bootstrap=WorldBootstrap(
                world_id=WorldId("world-1"),
                revision=WorldRevision(0),
                locations=locations,
                bodies=(body,),
                weather=weather_for_locations(locations),
                registrations=(
                    AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
                ),
            ),
            environmental_dynamics=spec,
        )
        seasons: list[int] = []
        conditions: list[str] = []
        for _tick in range(36):
            token = engine.observe().token
            result = engine.resolve_tick(
                (ActionSubmission(token, AgentId("agent-1"), Wait()),)
            )
            seasons.extend(
                event.event.tick
                for event in result.events
                if event.event.details.kind == "season_changed"
            )
            weather = engine._snapshot.world.state.weather[EntityId("loc-1")]
            condition = weather.condition
            conditions.append(condition.value)
        return tuple(conditions), tuple(seasons)

    left = trace(3, None)
    right = trace(3, scarcity_scenario_dynamics())
    other = trace(9, scarcity_scenario_dynamics())
    assert left[0] == right[0]
    assert right[1] == other[1]
    assert right[1]
    assert left[0] != other[0]
    assert any(
        "family_season=" in record.getMessage() for record in caplog.records
    )
    assert any(
        "environment_event_committed" in record.getMessage()
        and record.levelno == logging.INFO
        for record in caplog.records
    )


def test_yield_undefined_warning(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    caplog.set_level(logging.WARNING, logger="simulation.engine")

    def _missing(self: object, kind: object, season: object) -> float:
        del self, kind, season
        raise ValueError("yield_undefined")

    monkeypatch.setattr(EnvironmentalDynamicsSpec, "multiplier_for", _missing)
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        quantity=1.0,
        regeneration_per_tick=1.0,
    )
    with pytest.raises(ValueError, match="yield_undefined"):
        _step(
            _state(resources=(food,), bodies=()),
            tick=1,
            hour=6,
            phase=DayPhase.DAY,
            spec=_all_ones(),
        )
    # The engine logs the warning when the step raises inside a tick.
    locations = (make_location("loc-1"),)
    engine = WorldEngine(
        config=SimulationRunConfig(seed=1),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            locations=locations,
            bodies=(alive_body(),),
            resources=(
                make_resource(
                    "res-food",
                    name="Food",
                    kind=ResourceKind.FOOD,
                    quantity=1.0,
                    regeneration_per_tick=1.0,
                ),
            ),
            weather=weather_for_locations(locations),
            registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
        ),
        environmental_dynamics=_all_ones(),
    )
    token = engine.observe().token
    with pytest.raises(ValueError, match="yield_undefined"):
        engine.resolve_tick((ActionSubmission(token, AgentId("agent-1"), Wait()),))
    assert any(
        record.levelno == logging.WARNING
        and "yield_undefined reason_code=yield_undefined" in record.getMessage()
        for record in caplog.records
    )
    assert not any("seed" in record.getMessage() for record in caplog.records)


def test_harvest_witness_does_not_scale_extraction() -> None:
    catalog = example_production_catalog()
    recipe = catalog.recipe(RecipeId("harvest_wood"))
    assert recipe is not None
    state = _state(
        resources=(
            make_resource(
                "res-wood",
                name="wood",
                kind=ResourceKind.MATERIAL,
                quantity=1.0,
                regeneration_per_tick=0.0,
            ),
        ),
        bodies=(alive_body(),),
    )
    effect = ResolvedProductionEffect(
        RequestId("req-h"),
        RecipeId("harvest_wood"),
        True,
        1,
        EntityId("item-wood"),
        recipe=recipe,
    )
    _next, details, _code, witness = _apply_harvest(
        state,
        EntityId("body-1"),
        Harvest(RecipeId("harvest_wood"), EntityId("res-wood")),
        effect,
        recipe,
        1,
        witness_resource_nodes=True,
    )
    assert details.resulting_resource_quantity == 0.0
    assert type(witness) is ResourceNodeDepleted
