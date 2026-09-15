"""Deterministic test-only projections of private WorldState."""

from __future__ import annotations

from world._state import WorldState
from world.models import AgentBody, Item, Location, Resource, Weather


def project_world_state(state: WorldState) -> tuple[object, ...]:
    """Canonical, order-stable projection for replay equality checks."""
    if type(state) is not WorldState:
        raise TypeError("project_world_state requires WorldState")
    return (
        state.revision.value,
        tuple(_project_location(value) for value in _sorted_locations(state)),
        tuple(_project_item(value) for value in _sorted_items(state)),
        tuple(_project_resource(value) for value in _sorted_resources(state)),
        tuple(_project_body(value) for value in _sorted_bodies(state)),
        tuple(_project_weather(value) for value in _sorted_weather(state)),
    )


def _sorted_locations(state: WorldState) -> tuple[Location, ...]:
    return tuple(
        sorted(state.locations.values(), key=lambda value: value.entity_id.value)
    )


def _sorted_items(state: WorldState) -> tuple[Item, ...]:
    return tuple(sorted(state.items.values(), key=lambda value: value.entity_id.value))


def _sorted_resources(state: WorldState) -> tuple[Resource, ...]:
    return tuple(
        sorted(state.resources.values(), key=lambda value: value.entity_id.value)
    )


def _sorted_bodies(state: WorldState) -> tuple[AgentBody, ...]:
    return tuple(sorted(state.bodies.values(), key=lambda value: value.entity_id.value))


def _sorted_weather(state: WorldState) -> tuple[Weather, ...]:
    return tuple(
        sorted(state.weather.values(), key=lambda value: value.location_id.value)
    )


def _project_location(location: Location) -> tuple[str, str]:
    return (location.entity_id.value, location.name)


def _project_item(
    item: Item,
) -> tuple[str, str, str | None, str | None]:
    return (
        item.entity_id.value,
        item.name,
        None if item.location_id is None else item.location_id.value,
        None if item.holder_id is None else item.holder_id.value,
    )


def _project_resource(
    resource: Resource,
) -> tuple[str, str, str, float, str]:
    return (
        resource.entity_id.value,
        resource.name,
        resource.location_id.value,
        resource.quantity,
        resource.unit,
    )


def _project_body(
    body: AgentBody,
) -> tuple[object, ...]:
    return (
        body.entity_id.value,
        body.location_id.value,
        body.health.value,
        body.hunger.value,
        body.thirst.value,
        body.fatigue.value,
        body.temperature.value,
        tuple(item.value for item in body.inventory),
        body.life_status.value,
    )


def _project_weather(weather: Weather) -> tuple[str, str, float]:
    return (
        weather.location_id.value,
        weather.condition,
        weather.temperature.value,
    )
