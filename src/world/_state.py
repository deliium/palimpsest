"""Authority-facing world state. Not part of the public world facade."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import AgentBody, Item, Location, Resource, Weather
from world.production import ProductionJob, Structure, ToolMark

__all__: list[str] = ["World", "WorldState", "rebuild_world_state"]


def rebuild_world_state(
    state: WorldState,
    *,
    revision: WorldRevision | None = None,
    locations: Mapping[EntityId, Location] | None = None,
    items: Mapping[EntityId, Item] | None = None,
    resources: Mapping[EntityId, Resource] | None = None,
    bodies: Mapping[EntityId, AgentBody] | None = None,
    weather: Mapping[EntityId, Weather] | None = None,
    structures: Mapping[EntityId, Structure] | None = None,
    production_jobs: Mapping[EntityId, ProductionJob] | None = None,
    tool_marks: Mapping[EntityId, ToolMark] | None = None,
) -> WorldState:
    """Build a new immutable snapshot with deterministic EntityId ordering."""
    if type(state) is not WorldState:
        raise TypeError("rebuild_world_state requires WorldState")
    if revision is not None and type(revision) is not WorldRevision:
        raise TypeError("revision must be WorldRevision")
    location_src = state.locations if locations is None else locations
    item_src = state.items if items is None else items
    resource_src = state.resources if resources is None else resources
    body_src = state.bodies if bodies is None else bodies
    weather_src = state.weather if weather is None else weather
    structure_src = state.structures if structures is None else structures
    job_src = state.production_jobs if production_jobs is None else production_jobs
    mark_src = state.tool_marks if tool_marks is None else tool_marks
    return WorldState(
        state.revision if revision is None else revision,
        locations=tuple(
            sorted(location_src.values(), key=lambda value: value.entity_id.value)
        ),
        items=tuple(sorted(item_src.values(), key=lambda value: value.entity_id.value)),
        resources=tuple(
            sorted(resource_src.values(), key=lambda value: value.entity_id.value)
        ),
        bodies=tuple(
            sorted(body_src.values(), key=lambda value: value.entity_id.value)
        ),
        weather=tuple(
            sorted(weather_src.values(), key=lambda value: value.location_id.value)
        ),
        structures=tuple(
            sorted(structure_src.values(), key=lambda value: value.entity_id.value)
        ),
        production_jobs=tuple(
            sorted(job_src.values(), key=lambda value: value.actor_id.value)
        ),
        tool_marks=tuple(
            sorted(mark_src.values(), key=lambda value: value.item_id.value)
        ),
    )


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
        "_production_jobs",
        "_resources",
        "_revision",
        "_structures",
        "_tool_marks",
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
        structures: Sequence[Structure] = (),
        production_jobs: Sequence[ProductionJob] = (),
        tool_marks: Sequence[ToolMark] = (),
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
        structure_index = _index_by_entity_id(
            "structures", structures, model_type=Structure
        )
        _reject_global_id_collisions(
            location_index, item_index, resource_index, body_index, structure_index
        )
        for structure in structure_index.values():
            if structure.location_id not in location_index:
                raise ValueError(
                    "Structure.location_id must reference a known location"
                )
        job_index = _index_jobs(production_jobs)
        mark_index = _index_tool_marks(tool_marks)
        weather_index = _index_weather(weather, location_index)
        _validate_topology(location_index)
        _validate_weather_coverage(location_index, weather_index)
        _validate_graph(
            location_index=location_index,
            item_index=item_index,
            resource_index=resource_index,
            body_index=body_index,
        )
        _validate_capacities(
            location_index=location_index,
            item_index=item_index,
            body_index=body_index,
        )
        self._revision = revision
        self._locations = MappingProxyType(location_index)
        self._items = MappingProxyType(item_index)
        self._resources = MappingProxyType(resource_index)
        self._bodies = MappingProxyType(body_index)
        self._weather = MappingProxyType(weather_index)
        self._structures = MappingProxyType(structure_index)
        self._production_jobs = MappingProxyType(job_index)
        self._tool_marks = MappingProxyType(mark_index)

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

    @property
    def structures(self) -> Mapping[EntityId, Structure]:
        return self._structures

    @property
    def production_jobs(self) -> Mapping[EntityId, ProductionJob]:
        return self._production_jobs

    @property
    def tool_marks(self) -> Mapping[EntityId, ToolMark]:
        return self._tool_marks


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
        """Unsupported mutation hook — never restore or swap state here.

        Checkpoint restoration constructs a new ``World`` via simulation
        bootstrap helpers. Objective evolution must go through
        :class:`simulation.engine.WorldEngine`.
        """
        raise RuntimeError(
            "World.replace_state is not a supported mutation path; use WorldEngine"
        )

    def apply_admitted_request(
        self,
        request: object,
        *,
        event_ids: Sequence[EventId],
        run_id: str,
        tick: int,
        sequence: int = 0,
    ) -> object:
        """Validate then apply a bound request against the current snapshot.

        Rechecks the base revision atomically after validation. Rule handlers
        decide mutation vs event-only vs deferred/rejected outcomes.
        """
        from world._operations import (
            OperationAccepted,
            OperationRejected,
            RejectionCode,
            validate_action_request,
        )
        from world._transitions import TransitionResult, apply_validated_operation
        from world.actions import ActionRequest
        from world.identifiers import EventId as EventIdType

        if type(request) is not ActionRequest:
            return OperationRejected(code=RejectionCode.WRONG_TRUST_STAGE)
        if request.world_id != self._world_id:
            return OperationRejected(
                code=RejectionCode.WRONG_WORLD, request_id=request.request_id
            )
        if request.revision != self._state.revision:
            return OperationRejected(
                code=RejectionCode.STALE_REVISION, request_id=request.request_id
            )
        outcome = validate_action_request(
            world_id=self._world_id, state=self._state, request=request
        )
        if type(outcome) is OperationRejected:
            return outcome
        assert type(outcome) is OperationAccepted
        if request.revision != self._state.revision:
            return OperationRejected(
                code=RejectionCode.STALE_REVISION, request_id=request.request_id
            )
        for event_id in event_ids:
            if type(event_id) is not EventIdType:
                raise TypeError("event_ids entries must be EventId")
        result = apply_validated_operation(
            self._state,
            outcome.operation,
            event_ids=event_ids,
            run_id=run_id,
            tick=tick,
            sequence=sequence,
        )
        assert type(result) is TransitionResult
        self._state = result.resulting_state
        return result


def _index_jobs(jobs: Sequence[ProductionJob]) -> dict[EntityId, ProductionJob]:
    indexed: dict[EntityId, ProductionJob] = {}
    for job in jobs:
        if type(job) is not ProductionJob:
            raise TypeError("production_jobs entries must be ProductionJob")
        if job.actor_id in indexed:
            raise ValueError(f"duplicate production job for {job.actor_id.value!r}")
        indexed[job.actor_id] = job
    return indexed


def _index_tool_marks(marks: Sequence[ToolMark]) -> dict[EntityId, ToolMark]:
    indexed: dict[EntityId, ToolMark] = {}
    for mark in marks:
        if type(mark) is not ToolMark:
            raise TypeError("tool_marks entries must be ToolMark")
        if mark.item_id in indexed:
            raise ValueError(f"duplicate tool mark for {mark.item_id.value!r}")
        indexed[mark.item_id] = mark
    return indexed


def _reject_global_id_collisions(
    locations: Mapping[EntityId, Location],
    items: Mapping[EntityId, Item],
    resources: Mapping[EntityId, Resource],
    bodies: Mapping[EntityId, AgentBody],
    structures: Mapping[EntityId, Structure],
) -> None:
    seen: dict[EntityId, str] = {}
    for label, mapping in (
        ("location", locations),
        ("item", items),
        ("resource", resources),
        ("body", bodies),
        ("structure", structures),
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
            raise ValueError(f"duplicate weather for location {location_id.value!r}")
        if location_id not in locations:
            raise ValueError(
                f"weather references unknown location {location_id.value!r}"
            )
        indexed[location_id] = value
    return indexed


def _validate_topology(location_index: Mapping[EntityId, Location]) -> None:
    if not location_index:
        return
    for location_id, location in location_index.items():
        for neighbor_id in location.adjacent:
            neighbor = location_index.get(neighbor_id)
            if neighbor is None:
                raise ValueError(
                    f"location {location_id.value!r} has dangling edge to "
                    f"{neighbor_id.value!r}"
                )
            if location_id not in neighbor.adjacent:
                raise ValueError(
                    f"asymmetric edge between {location_id.value!r} and "
                    f"{neighbor_id.value!r}"
                )
    start = next(iter(sorted(location_index, key=lambda entity: entity.value)))
    seen: set[EntityId] = {start}
    queue: list[EntityId] = [start]
    while queue:
        current = queue.pop()
        for neighbor_id in location_index[current].adjacent:
            if neighbor_id not in seen:
                seen.add(neighbor_id)
                queue.append(neighbor_id)
    if len(seen) != len(location_index):
        raise ValueError("world graph must be connected")


def _validate_weather_coverage(
    location_index: Mapping[EntityId, Location],
    weather_index: Mapping[EntityId, Weather],
) -> None:
    if not location_index:
        return
    missing = set(location_index) - set(weather_index)
    if missing:
        sample = sorted(entity.value for entity in missing)[0]
        raise ValueError(f"weather coverage incomplete; missing location {sample!r}")


def _validate_capacities(
    *,
    location_index: Mapping[EntityId, Location],
    item_index: Mapping[EntityId, Item],
    body_index: Mapping[EntityId, AgentBody],
) -> None:
    body_counts: dict[EntityId, int] = {}
    for body in body_index.values():
        body_counts[body.location_id] = body_counts.get(body.location_id, 0) + 1
    for location_id, count in body_counts.items():
        capacity = location_index[location_id].body_capacity.value
        if count > capacity:
            raise ValueError(
                f"location {location_id.value!r} body occupancy {count} "
                f"exceeds capacity {capacity}"
            )

    ground_counts: dict[EntityId, int] = {}
    for item in item_index.values():
        if item.location_id is None:
            continue
        ground_counts[item.location_id] = ground_counts.get(item.location_id, 0) + 1
    for location_id, count in ground_counts.items():
        capacity = location_index[location_id].item_capacity.value
        if count > capacity:
            raise ValueError(
                f"location {location_id.value!r} ground-item occupancy {count} "
                f"exceeds capacity {capacity}"
            )

    for body_id, body in body_index.items():
        load = 0
        for item_id in body.inventory:
            load += item_index[item_id].load.value
        if load > body.carry_capacity.value:
            raise ValueError(
                f"body {body_id.value!r} carry load {load} exceeds capacity "
                f"{body.carry_capacity.value}"
            )


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
                f"item {item_id.value!r} references unknown holder {holder_id.value!r}"
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
