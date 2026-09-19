"""Private deterministic perception projector.

Visibility policy:
- Always expose self, hour/day-phase, visibility modifier, current weather,
  current location, and adjacent exits.
- Ground items, resource nodes, and other bodies appear only when effective
  visibility is at least ``0.5``.
- Held inventory remains visible below ``0.5``.
- Dead registered observers still receive self/time/environment observations.
- Physical target validation is not visibility-gated (handled elsewhere).
"""

from __future__ import annotations

from collections.abc import Sequence

from world._state import WorldState
from world.identifiers import EntityId, WorldId
from world.models import (
    Item,
    Location,
    Resource,
    Weather,
    copy_body,
    copy_item,
    copy_location,
    copy_resource,
    copy_weather,
)
from world.observations import (
    Observation,
    ObservationContext,
    VisibleBody,
    VisibleExit,
    coarse_health_for,
)
from world.values import WeatherCondition

__all__: list[str] = ["project_observations"]

_VISIBILITY_CONTENT_THRESHOLD = 0.5


def project_observations(
    *,
    world_id: WorldId,
    state: WorldState,
    observer_ids: Sequence[EntityId],
    context: ObservationContext | None = None,
) -> tuple[Observation, ...]:
    """Project detached observations for ordered observer body ids.

    Raises ``TypeError``/``ValueError`` before returning when inputs are invalid
    or an observer body is missing. Successful results are idempotent for the
    same ``(world_id, state, observer_ids, context)`` inputs.
    """
    if type(world_id) is not WorldId:
        raise TypeError("project_observations requires WorldId")
    if type(state) is not WorldState:
        raise TypeError("project_observations requires WorldState")
    if context is not None and type(context) is not ObservationContext:
        raise TypeError("context must be ObservationContext or None")
    resolved = context if context is not None else ObservationContext(tick=0)
    observers = _copy_observer_ids(observer_ids)
    for observer_id in observers:
        if observer_id not in state.bodies:
            raise ValueError(
                f"observer body {observer_id.value!r} is missing from world state"
            )
    return tuple(
        _project_one(
            world_id=world_id,
            state=state,
            observer_id=observer_id,
            context=resolved,
        )
        for observer_id in observers
    )


def _project_one(
    *,
    world_id: WorldId,
    state: WorldState,
    observer_id: EntityId,
    context: ObservationContext,
) -> Observation:
    body = state.bodies[observer_id]
    location_id = body.location_id
    location = state.locations.get(location_id)
    weather = state.weather.get(location_id)
    condition = (
        weather.condition if weather is not None else WeatherCondition.CLEAR
    )
    visibility = 1.0
    if location is not None:
        visibility = context.physical_rules.effective_visibility(
            location_visibility=location.visibility_factor.value,
            phase=context.day_phase,
            condition=condition,
        )
    content_visible = visibility >= _VISIBILITY_CONTENT_THRESHOLD
    return Observation(
        world_id=world_id,
        observer_id=observer_id,
        revision=state.revision,
        self_body=copy_body(body),
        locations=_sorted_locations(state, location_id),
        items=_sorted_items(
            state,
            observer_id=observer_id,
            location_id=location_id,
            include_ground=content_visible,
        ),
        resources=(
            _sorted_resources(state, location_id) if content_visible else ()
        ),
        weather=_sorted_weather(state, location_id),
        exits=_sorted_exits(state, location_id),
        visible_bodies=(
            _sorted_visible_bodies(state, location_id, observer_id)
            if content_visible
            else ()
        ),
        hour=context.hour,
        day_phase=context.day_phase,
        visibility=visibility,
        weather_condition=condition,
    )


def _copy_observer_ids(values: Sequence[EntityId]) -> tuple[EntityId, ...]:
    if isinstance(values, (set, frozenset)):
        raise TypeError("observer_ids must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(
        values, Sequence
    ):
        raise TypeError("observer_ids must be an ordered sequence")
    copied = tuple(values)
    seen: set[EntityId] = set()
    for value in copied:
        if type(value) is not EntityId:
            raise TypeError("observer_ids entries must be EntityId")
        if value in seen:
            raise ValueError("observer_ids must not contain duplicates")
        seen.add(value)
    return copied


def _sorted_locations(
    state: WorldState, location_id: EntityId
) -> tuple[Location, ...]:
    location = state.locations.get(location_id)
    if location is None:
        return ()
    return (copy_location(location),)


def _sorted_exits(
    state: WorldState, location_id: EntityId
) -> tuple[VisibleExit, ...]:
    location = state.locations.get(location_id)
    if location is None:
        return ()
    exits: list[VisibleExit] = []
    for destination_id in location.adjacent:
        destination = state.locations.get(destination_id)
        if destination is None:
            continue
        exits.append(
            VisibleExit(destination_id=destination_id, name=destination.name)
        )
    exits.sort(key=lambda value: value.destination_id.value)
    return tuple(exits)


def _sorted_items(
    state: WorldState,
    *,
    observer_id: EntityId,
    location_id: EntityId,
    include_ground: bool,
) -> tuple[Item, ...]:
    selected: list[Item] = []
    for item_id in sorted(state.items, key=lambda entity: entity.value):
        item = state.items[item_id]
        held_by_self = item.holder_id == observer_id
        at_location = include_ground and item.location_id == location_id
        if held_by_self or at_location:
            selected.append(copy_item(item))
    return tuple(selected)


def _sorted_resources(
    state: WorldState, location_id: EntityId
) -> tuple[Resource, ...]:
    selected: list[Resource] = []
    for resource_id in sorted(state.resources, key=lambda entity: entity.value):
        resource = state.resources[resource_id]
        if resource.location_id == location_id:
            selected.append(copy_resource(resource))
    return tuple(selected)


def _sorted_weather(
    state: WorldState, location_id: EntityId
) -> tuple[Weather, ...]:
    weather = state.weather.get(location_id)
    if weather is None:
        return ()
    return (copy_weather(weather),)


def _sorted_visible_bodies(
    state: WorldState,
    location_id: EntityId,
    observer_id: EntityId,
) -> tuple[VisibleBody, ...]:
    selected: list[VisibleBody] = []
    for body_id in sorted(state.bodies, key=lambda entity: entity.value):
        if body_id == observer_id:
            continue
        body = state.bodies[body_id]
        if body.location_id != location_id:
            continue
        selected.append(
            VisibleBody(
                entity_id=body_id,
                life_status=body.life_status,
                coarse_health=coarse_health_for(body),
            )
        )
    return tuple(selected)
