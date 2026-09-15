"""Private deterministic perception projector.

V1 policy (minimal, documented):
- One observation per observer body id, in caller-provided registration order.
- Each observation includes the observer's detached ``self_body`` when present.
- Location/item/resource/weather projections are limited to the observer's
  current location (items held by the observer are also included).
- Collections are sorted by ``EntityId.value`` for determinism.
- No other full ``AgentBody`` is ever exposed.
- Missing observer bodies fail closed before any observation batch is returned.
- Dead bodies still receive observations; action eligibility is enforced later.
"""

from __future__ import annotations

from collections.abc import Sequence

from world._state import WorldState
from world.identifiers import EntityId, WorldId
from world.models import AgentBody, Item, Location, Resource, Weather
from world.observations import Observation

__all__: list[str] = ["project_observations"]


def project_observations(
    *,
    world_id: WorldId,
    state: WorldState,
    observer_ids: Sequence[EntityId],
) -> tuple[Observation, ...]:
    """Project detached observations for ordered observer body ids.

    Raises ``TypeError``/``ValueError`` before returning when inputs are invalid
    or an observer body is missing. Successful results are idempotent for the
    same ``(world_id, state, observer_ids)`` inputs.
    """
    if type(world_id) is not WorldId:
        raise TypeError("project_observations requires WorldId")
    if type(state) is not WorldState:
        raise TypeError("project_observations requires WorldState")
    observers = _copy_observer_ids(observer_ids)
    for observer_id in observers:
        if observer_id not in state.bodies:
            raise ValueError(
                f"observer body {observer_id.value!r} is missing from world state"
            )
    return tuple(
        _project_one(world_id=world_id, state=state, observer_id=observer_id)
        for observer_id in observers
    )


def _project_one(
    *,
    world_id: WorldId,
    state: WorldState,
    observer_id: EntityId,
) -> Observation:
    body = state.bodies[observer_id]
    location_id = body.location_id
    locations = _sorted_locations(state, location_id)
    items = _sorted_items(state, observer_id=observer_id, location_id=location_id)
    resources = _sorted_resources(state, location_id)
    weather = _sorted_weather(state, location_id)
    return Observation(
        world_id=world_id,
        observer_id=observer_id,
        revision=state.revision,
        self_body=_detach_body(body),
        locations=locations,
        items=items,
        resources=resources,
        weather=weather,
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


def _detach_body(body: AgentBody) -> AgentBody:
    return AgentBody(
        entity_id=body.entity_id,
        location_id=body.location_id,
        health=body.health,
        hunger=body.hunger,
        thirst=body.thirst,
        fatigue=body.fatigue,
        temperature=body.temperature,
        inventory=tuple(body.inventory),
        life_status=body.life_status,
    )


def _sorted_locations(
    state: WorldState, location_id: EntityId
) -> tuple[Location, ...]:
    location = state.locations.get(location_id)
    if location is None:
        return ()
    return (Location(entity_id=location.entity_id, name=location.name),)


def _sorted_items(
    state: WorldState,
    *,
    observer_id: EntityId,
    location_id: EntityId,
) -> tuple[Item, ...]:
    selected: list[Item] = []
    for item_id in sorted(state.items, key=lambda entity: entity.value):
        item = state.items[item_id]
        at_location = item.location_id == location_id
        held_by_self = item.holder_id == observer_id
        if at_location or held_by_self:
            selected.append(
                Item(
                    entity_id=item.entity_id,
                    name=item.name,
                    location_id=item.location_id,
                    holder_id=item.holder_id,
                )
            )
    return tuple(selected)


def _sorted_resources(
    state: WorldState, location_id: EntityId
) -> tuple[Resource, ...]:
    selected: list[Resource] = []
    for resource_id in sorted(state.resources, key=lambda entity: entity.value):
        resource = state.resources[resource_id]
        if resource.location_id == location_id:
            selected.append(
                Resource(
                    entity_id=resource.entity_id,
                    name=resource.name,
                    location_id=resource.location_id,
                    quantity=resource.quantity,
                    unit=resource.unit,
                )
            )
    return tuple(selected)


def _sorted_weather(
    state: WorldState, location_id: EntityId
) -> tuple[Weather, ...]:
    weather = state.weather.get(location_id)
    if weather is None:
        return ()
    return (
        Weather(
            location_id=weather.location_id,
            condition=weather.condition,
            temperature=weather.temperature,
        ),
    )
