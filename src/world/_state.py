"""Authority-facing world state. Not part of the public world facade."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, Item, Location, Resource, Weather

__all__: list[str] = ["World", "WorldState"]


def _index_by_entity_id[T](
    name: str,
    values: Sequence[T],
    *,
    model_type: type[T],
) -> dict[EntityId, T]:
    indexed: dict[EntityId, T] = {}
    for value in values:
        if type(value) is not model_type:
            raise TypeError(f"{name} entries must be {model_type.__name__}")
        entity_id = value.entity_id  # type: ignore[attr-defined]
        if type(entity_id) is not EntityId:
            raise TypeError(f"{name} entity_id must be EntityId")
        if entity_id in indexed:
            raise ValueError(f"duplicate {name} entity_id {entity_id.value!r}")
        indexed[entity_id] = value
    return indexed


class WorldState:
    """Authoritative immutable world snapshot. Not visible to agents."""

    __slots__ = (
        "_bodies",
        "_items",
        "_locations",
        "_resources",
        "_revision",
        "_weather",
    )

    def __init__(
        self,
        revision: WorldRevision,
        *,
        locations: Sequence[Location] = (),
        items: Sequence[Item] = (),
        resources: Sequence[Resource] = (),
        bodies: Sequence[AgentBody] = (),
        weather: Sequence[Weather] = (),
    ) -> None:
        if type(revision) is not WorldRevision:
            raise TypeError("WorldState.revision must be WorldRevision")
        location_index = _index_by_entity_id(
            "locations", locations, model_type=Location
        )
        item_index = _index_by_entity_id("items", items, model_type=Item)
        resource_index = _index_by_entity_id(
            "resources", resources, model_type=Resource
        )
        body_index = _index_by_entity_id("bodies", bodies, model_type=AgentBody)
        _reject_global_id_collisions(
            location_index, item_index, resource_index, body_index
        )
        weather_index = _index_weather(weather, location_index)
        _validate_graph(
            location_index=location_index,
            item_index=item_index,
            resource_index=resource_index,
            body_index=body_index,
        )
        self._revision = revision
        self._locations = MappingProxyType(location_index)
        self._items = MappingProxyType(item_index)
        self._resources = MappingProxyType(resource_index)
        self._bodies = MappingProxyType(body_index)
        self._weather = MappingProxyType(weather_index)

    @property
    def revision(self) -> WorldRevision:
        return self._revision

    @property
    def locations(self) -> Mapping[EntityId, Location]:
        return self._locations

    @property
    def items(self) -> Mapping[EntityId, Item]:
        return self._items

    @property
    def resources(self) -> Mapping[EntityId, Resource]:
        return self._resources

    @property
    def bodies(self) -> Mapping[EntityId, AgentBody]:
        return self._bodies

    @property
    def weather(self) -> Mapping[EntityId, Weather]:
        return self._weather


class World:
    """Private mutable authority holder for a single world identity."""

    __slots__ = ("_state", "_world_id")

    def __init__(self, world_id: WorldId, initial_state: WorldState) -> None:
        if type(world_id) is not WorldId:
            raise TypeError("World.world_id must be WorldId")
        if type(initial_state) is not WorldState:
            raise TypeError("World.initial_state must be WorldState")
        self._world_id = world_id
        self._state = initial_state

    @property
    def world_id(self) -> WorldId:
        return self._world_id

    @property
    def state(self) -> WorldState:
        return self._state

    def replace_state(self, new_state: WorldState) -> WorldState:
        """Replace the current immutable snapshot and return it."""
        if type(new_state) is not WorldState:
            raise TypeError("World.replace_state requires WorldState")
        self._state = new_state
        return self._state


def _reject_global_id_collisions(
    locations: Mapping[EntityId, Location],
    items: Mapping[EntityId, Item],
    resources: Mapping[EntityId, Resource],
    bodies: Mapping[EntityId, AgentBody],
) -> None:
    seen: dict[EntityId, str] = {}
    for label, mapping in (
        ("location", locations),
        ("item", items),
        ("resource", resources),
        ("body", bodies),
    ):
        for entity_id in mapping:
            prior = seen.get(entity_id)
            if prior is not None:
                raise ValueError(
                    f"duplicate physical EntityId {entity_id.value!r} "
                    f"across {prior} and {label}"
                )
            seen[entity_id] = label


def _index_weather(
    weather: Sequence[Weather],
    locations: Mapping[EntityId, Location],
) -> dict[EntityId, Weather]:
    indexed: dict[EntityId, Weather] = {}
    for value in weather:
        if type(value) is not Weather:
            raise TypeError("weather entries must be Weather")
        location_id = value.location_id
        if location_id in indexed:
            raise ValueError(
                f"duplicate weather for location {location_id.value!r}"
            )
        if location_id not in locations:
            raise ValueError(
                f"weather references unknown location {location_id.value!r}"
            )
        indexed[location_id] = value
    return indexed


def _validate_graph(
    *,
    location_index: Mapping[EntityId, Location],
    item_index: Mapping[EntityId, Item],
    resource_index: Mapping[EntityId, Resource],
    body_index: Mapping[EntityId, AgentBody],
) -> None:
    inventory_owners: dict[EntityId, EntityId] = {}
    for body_id, body in body_index.items():
        if body.location_id not in location_index:
            raise ValueError(
                f"body {body_id.value!r} references unknown location "
                f"{body.location_id.value!r}"
            )
        for item_id in body.inventory:
            if item_id in inventory_owners:
                raise ValueError(
                    f"item {item_id.value!r} appears in multiple inventories"
                )
            inventory_owners[item_id] = body_id

    for item_id, item in item_index.items():
        if item.location_id is not None:
            if item.location_id not in location_index:
                raise ValueError(
                    f"item {item_id.value!r} references unknown location "
                    f"{item.location_id.value!r}"
                )
            if item_id in inventory_owners:
                raise ValueError(
                    f"item {item_id.value!r} is location-placed but also held"
                )
            continue
        assert item.holder_id is not None
        holder_id = item.holder_id
        if holder_id not in body_index:
            raise ValueError(
                f"item {item_id.value!r} references unknown holder "
                f"{holder_id.value!r}"
            )
        owner = inventory_owners.get(item_id)
        if owner is None:
            raise ValueError(
                f"item {item_id.value!r} holder_id does not match any inventory"
            )
        if owner != holder_id:
            raise ValueError(
                f"item {item_id.value!r} holder_id disagrees with body inventory"
            )

    for item_id, owner_id in inventory_owners.items():
        owned_item = item_index.get(item_id)
        if owned_item is None:
            raise ValueError(
                f"body {owner_id.value!r} inventory references unknown item "
                f"{item_id.value!r}"
            )
        if owned_item.holder_id != owner_id:
            raise ValueError(
                f"item {item_id.value!r} holder_id disagrees with body inventory"
            )

    for resource_id, resource in resource_index.items():
        if resource.location_id not in location_index:
            raise ValueError(
                f"resource {resource_id.value!r} references unknown location "
                f"{resource.location_id.value!r}"
            )
