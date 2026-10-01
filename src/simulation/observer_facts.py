"""Detached objective facts for read-only observers. No observer imports."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from simulation.bootstrap import AgentRegistration
from simulation.persistence import WorldSnapshot
from world.events import WorldEvent
from world.models import AgentBody, Item, Location, Resource, Weather
from world.production import Structure

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
