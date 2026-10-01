"""Detached objective facts for read-only observers. No observer imports."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from simulation.bootstrap import AgentRegistration
from simulation.persistence import WorldSnapshot
from world.environment import (
    ActiveHazard,
    EnvironmentalDynamicsSpec,
    temperature_band,
)
from world.events import WorldEvent
from world.models import AgentBody, Item, Location, PhysicalRules, Resource, Weather
from world.production import Structure
from world.values import round_physical

_LOGGER = logging.getLogger("simulation.observer_facts")


class ObjectiveFactsError(ValueError):
    """Closed failure while assembling an objective scene."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


def _reject(reason_code: str) -> None:
    _LOGGER.error("objective_scene_rejected reason_code=%s", reason_code)
    raise ObjectiveFactsError(reason_code)


@dataclass(frozen=True, slots=True)
class ObjectiveFacts:
    """Copied public facts. Contains no seed and no live world."""

    run_id: str
    world_id: str
    tick: int
    revision: int
    locations: tuple[Location, ...]
    bodies: tuple[AgentBody, ...]
    items: tuple[Item, ...]
    resources: tuple[Resource, ...]
    weather: tuple[Weather, ...]
    registrations: tuple[AgentRegistration, ...]
    structures: tuple[Structure, ...] = ()
    season: str | None = None
    temperature_bands: tuple[tuple[str, str], ...] = ()
    hazards: tuple[tuple[str, str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class ObjectiveScene:
    """Validated detached scene built from objective facts."""

    run_id: str
    world_id: str
    tick: int
    revision: int
    locations: tuple[Location, ...]
    bodies: tuple[AgentBody, ...]
    items: tuple[Item, ...]
    resources: tuple[Resource, ...]
    weather: tuple[Weather, ...]
    registrations: tuple[AgentRegistration, ...]
    structures: tuple[Structure, ...] = ()
    season: str | None = None
    temperature_bands: tuple[tuple[str, str], ...] = ()
    hazards: tuple[tuple[str, str, int], ...] = ()


def _freeze_facts(facts: ObjectiveFacts) -> ObjectiveScene:
    if type(facts) is not ObjectiveFacts:
        _reject("invalid_facts")
    if type(facts.world_id) is not str or not facts.world_id:
        _reject("empty_world_id")
    if type(facts.run_id) is not str or not facts.run_id:
        _reject("empty_world_id")
    locations = tuple(facts.locations)
    weather = tuple(facts.weather)
    location_ids = tuple(item.entity_id for item in locations)
    weather_ids = tuple(item.location_id for item in weather)
    if set(location_ids) != set(weather_ids) or len(location_ids) != len(
        set(location_ids)
    ):
        _reject("weather_incomplete")
    scene = ObjectiveScene(
        run_id=facts.run_id,
        world_id=facts.world_id,
        tick=facts.tick,
        revision=facts.revision,
        locations=locations,
        bodies=tuple(facts.bodies),
        items=tuple(facts.items),
        resources=tuple(facts.resources),
        weather=weather,
        registrations=tuple(facts.registrations),
        structures=tuple(facts.structures),
        season=facts.season,
        temperature_bands=tuple(facts.temperature_bands),
        hazards=tuple(facts.hazards),
    )
    _LOGGER.debug(
        "objective_scene_built run_id=%s tick=%s location_count=%s "
        "body_count=%s item_count=%s",
        scene.run_id,
        scene.tick,
        len(scene.locations),
        len(scene.bodies),
        len(scene.items),
    )
    return scene


def environment_view(
    *,
    spec: object | None,
    tick: int,
    locations: Sequence[Location],
    weather: Sequence[Weather],
    active_hazards: Sequence[object],
    rules: PhysicalRules,
) -> tuple[str | None, tuple[tuple[str, str], ...], tuple[tuple[str, str, int], ...]]:
    """Current season, local bands, and hazard tokens. Absent spec omits them."""
    if spec is None:
        return None, (), ()
    if type(spec) is not EnvironmentalDynamicsSpec:
        raise TypeError(
            "environmental_dynamics must be EnvironmentalDynamicsSpec or None"
        )
    if type(rules) is not PhysicalRules:
        raise TypeError("rules must be PhysicalRules")
    by_location = {item.location_id: item for item in weather}
    phase = rules.day_phase_for_tick(tick)
    phase_offsets = rules.phase_temperature_offset
    weather_offsets = rules.weather_temperature_offset
    assert phase_offsets is not None and weather_offsets is not None
    season_offset = spec.offset_for(spec.season_at(tick))
    bands: list[tuple[str, str]] = []
    for location in sorted(locations, key=lambda item: item.entity_id.value):
        local = by_location[location.entity_id]
        ambient = round_physical(
            location.base_temperature.value
            + weather_offsets[local.condition]
            + phase_offsets[phase]
            + season_offset
        )
        bands.append((location.entity_id.value, temperature_band(ambient).value))
    hazards: list[tuple[str, str, int]] = []
    for hazard in active_hazards:
        if type(hazard) is not ActiveHazard or not hazard.contains(tick):
            continue
        hazards.append(
            (
                hazard.location_id.value,
                hazard.kind.value,
                hazard.remaining_ticks(tick),
            )
        )
    hazards.sort(key=lambda item: (item[0], item[1]))
    return spec.season_at(tick).value, tuple(bands), tuple(hazards)


def scene_from_facts(facts: ObjectiveFacts) -> ObjectiveScene:
    return _freeze_facts(facts)


def scene_from_snapshot(
    snapshot: WorldSnapshot,
    *,
    events: Sequence[WorldEvent] = (),
    requested_tick: int | None = None,
) -> ObjectiveScene:
    """Build a scene only when the snapshot cursor is already the request."""
    if type(snapshot) is not WorldSnapshot:
        _reject("invalid_snapshot")
    if isinstance(events, (set, frozenset)) or not isinstance(events, Sequence):
        _reject("invalid_events")
    if len(events) != 0:
        _reject("later_events_require_fold")
    cursor = snapshot.next_tick.value
    if requested_tick is not None and requested_tick != cursor:
        _reject("snapshot_cursor_mismatch")
    facts = ObjectiveFacts(
        run_id=snapshot.run_id.value,
        world_id=snapshot.world_id.value,
        tick=cursor,
        revision=snapshot.revision.value,
        locations=tuple(snapshot.locations),
        bodies=tuple(snapshot.bodies),
        items=tuple(snapshot.items),
        resources=tuple(snapshot.resources),
        weather=tuple(snapshot.weather),
        registrations=tuple(snapshot.registrations),
        structures=tuple(snapshot.structures),
    )
    return scene_from_facts(facts)


__all__ = [
    "ObjectiveFacts",
    "ObjectiveFactsError",
    "ObjectiveScene",
    "scene_from_facts",
    "scene_from_snapshot",
]
