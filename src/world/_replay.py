"""Pure objective-event projector for authoritative replay.

Applies recorded effect facts onto immutable ``WorldState`` without invoking
current command validation or behavioral rules. Log-free: callers map
``ProjectionError.code`` into orchestration ERROR diagnostics.

Compatibility:
- Replay schema v2: legacy take/drop/give mutations only.
- Replay schema v3/v4: effect-complete physical projector for all mutating kinds.
  Schema v4 additionally carries occurrence context (ignored by state projection).
Runs never mix replay schema versions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world._state import WorldState, rebuild_world_state
from world.events import (
    EVENT_SCHEMA_REPLAY_V2,
    EVENT_SCHEMA_REPLAY_V3,
    EVENT_SCHEMA_REPLAY_V4,
    Asked,
    Attacked,
    Died,
    Dropped,
    Drunk,
    Eaten,
    ExposureApplied,
    Fled,
    Given,
    Helped,
    Moved,
    NeedsApplied,
    ResourceRegenerated,
    Searched,
    Slept,
    Taken,
    Talked,
    Told,
    Waited,
    WeatherChanged,
    WorldEvent,
    event_is_replayable,
    normalize_events,
    require_replayable_event,
)
from world.identifiers import (
    EntityId,
    EventId,
    WorldId,
    WorldRevision,
    require_stable_id,
)
from world.models import (
    AgentBody,
    Item,
    LifeStatus,
    copy_body,
    copy_item,
    copy_resource,
    copy_weather,
)
from world.values import (
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ItemLoad,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
)

__all__: list[str] = [
    "ProjectionError",
    "ProjectionErrorCode",
    "project_events",
]

_ITEM_KIND_FOR_RESOURCE: Final[dict[ResourceKind, ItemKind]] = {
    ResourceKind.FOOD: ItemKind.FOOD,
    ResourceKind.WATER: ItemKind.WATER,
    ResourceKind.MATERIAL: ItemKind.MATERIAL,
}


class ProjectionErrorCode(StrEnum):
    """Stable corruption/mismatch codes for restore orchestration logs."""

    NON_REPLAYABLE = "non_replayable_event"
    RUN_ID_MISMATCH = "run_id_mismatch"
    WORLD_ID_MISMATCH = "world_id_mismatch"
    DUPLICATE_EVENT = "duplicate_event_id"
    INVALID_ORDERING = "invalid_event_ordering"
    REVISION_MISMATCH = "revision_mismatch"
    ACTOR_MISSING = "actor_missing"
    TARGET_MISSING = "target_missing"
    PRECONDITION_FAILED = "precondition_failed"
    INVARIANT_FAILED = "invariant_failed"
    INVALID_SEQUENCE = "invalid_sequence"
    MIXED_SCHEMA = "mixed_replay_schema_version"
    UNSUPPORTED_SCHEMA = "unsupported_event_schema_version"


class ProjectionError(ValueError):
    """Fail-closed projection failure with a stable code and no payloads."""

    def __init__(self, code: ProjectionErrorCode | str) -> None:
        self.code = code.value if isinstance(code, ProjectionErrorCode) else code
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class _TickGroup:
    tick: int
    events: tuple[WorldEvent, ...]


def project_events(
    state: WorldState,
    events: Sequence[WorldEvent],
    *,
    expected_run_id: str,
    expected_world_id: WorldId,
) -> WorldState:
    """Fold ordered replay-capable events onto ``state``.

    Enforces run/world identity, contiguous per-tick sequences, revision
    transitions (0 or +1 per tick), duplicate rejection, and graph invariants.
    Does not call ``evaluate_operation`` / ``apply_operation``.
    """
    if type(state) is not WorldState:
        raise TypeError("project_events requires WorldState")
    if type(expected_world_id) is not WorldId:
        raise TypeError("expected_world_id must be WorldId")
    run_id = require_stable_id("expected_run_id", expected_run_id)
    if isinstance(events, (set, frozenset, Mapping)):
        raise ProjectionError(ProjectionErrorCode.INVALID_SEQUENCE)
    if isinstance(events, (str, bytes, bytearray)) or not isinstance(events, Sequence):
        raise ProjectionError(ProjectionErrorCode.INVALID_SEQUENCE)

    try:
        normalized = normalize_events(events)
    except (TypeError, ValueError) as exc:
        message = str(exc)
        if "duplicate" in message:
            raise ProjectionError(ProjectionErrorCode.DUPLICATE_EVENT) from exc
        raise ProjectionError(ProjectionErrorCode.INVALID_SEQUENCE) from exc

    if not normalized:
        return state

    schema_version = normalized[0].schema_version
    for event in normalized:
        if event.schema_version != schema_version:
            raise ProjectionError(ProjectionErrorCode.MIXED_SCHEMA)
        if event.schema_version not in {
            EVENT_SCHEMA_REPLAY_V2,
            EVENT_SCHEMA_REPLAY_V3,
            EVENT_SCHEMA_REPLAY_V4,
        }:
            raise ProjectionError(ProjectionErrorCode.UNSUPPORTED_SCHEMA)

    working = state
    base_revision = state.revision
    seen_ids: set[EventId] = set()
    previous_tick: int | None = None

    for group in _group_by_tick(normalized):
        if previous_tick is not None and group.tick <= previous_tick:
            raise ProjectionError(ProjectionErrorCode.INVALID_ORDERING)
        previous_tick = group.tick
        working, base_revision = _project_tick_group(
            working,
            group,
            expected_run_id=run_id,
            expected_world_id=expected_world_id,
            base_revision=base_revision,
            seen_ids=seen_ids,
            schema_version=schema_version,
        )
    return working


def _group_by_tick(events: tuple[WorldEvent, ...]) -> tuple[_TickGroup, ...]:
    groups: list[_TickGroup] = []
    index = 0
    while index < len(events):
        tick = events[index].tick
        start = index
        while index < len(events) and events[index].tick == tick:
            index += 1
        batch = events[start:index]
        for sequence, event in enumerate(batch):
            if event.sequence != sequence:
                raise ProjectionError(ProjectionErrorCode.INVALID_ORDERING)
        groups.append(_TickGroup(tick=tick, events=batch))
    return tuple(groups)


def _project_tick_group(
    state: WorldState,
    group: _TickGroup,
    *,
    expected_run_id: str,
    expected_world_id: WorldId,
    base_revision: WorldRevision,
    seen_ids: set[EventId],
    schema_version: int,
) -> tuple[WorldState, WorldRevision]:
    resulting_revision = group.events[0].resulting_revision
    for event in group.events:
        _validate_event_identity(
            event,
            expected_run_id=expected_run_id,
            expected_world_id=expected_world_id,
            seen_ids=seen_ids,
        )
        if event.resulting_revision != resulting_revision:
            raise ProjectionError(ProjectionErrorCode.REVISION_MISMATCH)
        if event.tick != group.tick:
            raise ProjectionError(ProjectionErrorCode.INVALID_ORDERING)

    working = state
    mutated = False
    for event in group.events:
        next_state, changed = _apply_event_effect(
            working, event, schema_version=schema_version
        )
        working = next_state
        mutated = mutated or changed

    if mutated:
        expected = WorldRevision(base_revision.value + 1)
        if resulting_revision != expected:
            raise ProjectionError(ProjectionErrorCode.REVISION_MISMATCH)
        working = rebuild_world_state(working, revision=resulting_revision)
    else:
        if resulting_revision != base_revision:
            raise ProjectionError(ProjectionErrorCode.REVISION_MISMATCH)
        if working.revision != base_revision:
            raise ProjectionError(ProjectionErrorCode.REVISION_MISMATCH)

    if working.revision != resulting_revision:
        raise ProjectionError(ProjectionErrorCode.REVISION_MISMATCH)
    return working, resulting_revision


def _validate_event_identity(
    event: WorldEvent,
    *,
    expected_run_id: str,
    expected_world_id: WorldId,
    seen_ids: set[EventId],
) -> None:
    try:
        require_replayable_event(event)
    except (TypeError, ValueError) as exc:
        raise ProjectionError(ProjectionErrorCode.NON_REPLAYABLE) from exc
    if not event_is_replayable(event):
        raise ProjectionError(ProjectionErrorCode.NON_REPLAYABLE)
    if event.run_id != expected_run_id:
        raise ProjectionError(ProjectionErrorCode.RUN_ID_MISMATCH)
    if event.world_id != expected_world_id:
        raise ProjectionError(ProjectionErrorCode.WORLD_ID_MISMATCH)
    if event.event_id in seen_ids:
        raise ProjectionError(ProjectionErrorCode.DUPLICATE_EVENT)
    seen_ids.add(event.event_id)


def _validate_event_only_refs(state: WorldState, event: WorldEvent) -> None:
    if event.actor_id is not None and event.actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if event.target_id is not None and not _entity_known(state, event.target_id):
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)


def _entity_known(state: WorldState, entity_id: EntityId) -> bool:
    return (
        entity_id in state.bodies
        or entity_id in state.items
        or entity_id in state.locations
        or entity_id in state.resources
    )


def _apply_event_effect(
    state: WorldState, event: WorldEvent, *, schema_version: int
) -> tuple[WorldState, bool]:
    if schema_version == EVENT_SCHEMA_REPLAY_V2:
        match event.details:
            case Taken() | Dropped() | Given():
                return _apply_legacy_transfer(state, event), True
            case _:
                _validate_event_only_refs(state, event)
                return state, False

    match event.details:
        case Searched(success=False) | Attacked(hit=False) | Fled(success=False):
            _validate_event_only_refs(state, event)
            return state, False
        case Talked() | Asked() | Told() | Waited():
            _validate_event_only_refs(state, event)
            return state, False
        case Taken() | Dropped() | Given():
            return _apply_legacy_transfer(state, event), True
        case Moved() as moved:
            return _project_move(state, event, moved), True
        case Searched() as searched if searched.success is True:
            return _project_search_success(state, event, searched), True
        case Eaten() as eaten:
            return _project_eat(state, event, eaten), True
        case Drunk() as drunk:
            return _project_drink(state, event, drunk), True
        case Slept() as slept:
            return _project_sleep(state, event, slept), True
        case Helped() as helped:
            return _project_help(state, event, helped), True
        case Attacked() as attacked if attacked.hit is True:
            return _project_attack_hit(state, event, attacked), True
        case Fled() as fled if fled.success is True:
            return _project_flee_success(state, event, fled), True
        case WeatherChanged() as weather:
            return _project_weather(state, weather), True
        case ResourceRegenerated() as regenerated:
            return _project_regeneration(state, regenerated), True
        case NeedsApplied() as needs:
            return _project_needs(state, needs), True
        case ExposureApplied() as exposure:
            return _project_exposure(state, exposure), True
        case Died() as died:
            return _project_died(state, died), True
        case _:
            raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)


def _apply_legacy_transfer(state: WorldState, event: WorldEvent) -> WorldState:
    match event.details:
        case Taken(item_id=item_id, resulting_holder_id=holder_id):
            return _project_take(state, event, item_id=item_id, holder_id=holder_id)
        case Dropped(item_id=item_id, resulting_location_id=location_id):
            return _project_drop(state, event, item_id=item_id, location_id=location_id)
        case Given(
            recipient_id=recipient_id,
            item_id=item_id,
            resulting_holder_id=holder_id,
        ):
            return _project_give(
                state,
                event,
                recipient_id=recipient_id,
                item_id=item_id,
                holder_id=holder_id,
            )
        case _:
            raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)


def _project_take(
    state: WorldState,
    event: WorldEvent,
    *,
    item_id: EntityId,
    holder_id: EntityId | None,
) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if holder_id is None or holder_id != actor_id:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if item_id not in state.items:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    item = state.items[item_id]
    if item.location_id is None or item.holder_id is not None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    actor = state.bodies[actor_id]
    if item_id in actor.inventory:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    items = dict(state.items)
    bodies = dict(state.bodies)
    items[item_id] = copy_item(item, location_id=None, holder_id=actor_id)
    bodies[actor_id] = _copy_body(actor, inventory=(*actor.inventory, item_id))
    try:
        return rebuild_world_state(state, items=items, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_drop(
    state: WorldState,
    event: WorldEvent,
    *,
    item_id: EntityId,
    location_id: EntityId | None,
) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if location_id is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if location_id not in state.locations:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if item_id not in state.items:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    actor = state.bodies[actor_id]
    if location_id != actor.location_id:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    item = state.items[item_id]
    if item.holder_id != actor_id or item_id not in actor.inventory:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    items = dict(state.items)
    bodies = dict(state.bodies)
    items[item_id] = copy_item(item, location_id=location_id, holder_id=None)
    bodies[actor_id] = _copy_body(
        actor,
        inventory=tuple(owned for owned in actor.inventory if owned != item_id),
    )
    try:
        return rebuild_world_state(state, items=items, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_give(
    state: WorldState,
    event: WorldEvent,
    *,
    recipient_id: EntityId,
    item_id: EntityId,
    holder_id: EntityId | None,
) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if holder_id is None or holder_id != recipient_id:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if recipient_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if item_id not in state.items:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    actor = state.bodies[actor_id]
    recipient = state.bodies[recipient_id]
    item = state.items[item_id]
    if item.holder_id != actor_id or item_id not in actor.inventory:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if actor_id == recipient_id:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    items = dict(state.items)
    bodies = dict(state.bodies)
    items[item_id] = copy_item(item, location_id=None, holder_id=recipient_id)
    bodies[actor_id] = _copy_body(
        actor,
        inventory=tuple(owned for owned in actor.inventory if owned != item_id),
    )
    bodies[recipient_id] = _copy_body(
        recipient, inventory=(*recipient.inventory, item_id)
    )
    try:
        return rebuild_world_state(state, items=items, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_move(state: WorldState, event: WorldEvent, details: Moved) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.resulting_location_id is None or details.resulting_fatigue is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if details.resulting_location_id != details.destination_id:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if details.destination_id not in state.locations:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    actor = state.bodies[actor_id]
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(
        actor,
        location_id=details.resulting_location_id,
        fatigue=Fatigue(details.resulting_fatigue),
    )
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_search_success(
    state: WorldState, event: WorldEvent, details: Searched
) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if (
        details.target_id is None
        or details.created_item_id is None
        or details.resulting_resource_quantity is None
    ):
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if details.target_id not in state.resources:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if details.created_item_id in state.items:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    actor = state.bodies[actor_id]
    resource = state.resources[details.target_id]
    item_kind = _ITEM_KIND_FOR_RESOURCE.get(resource.kind)
    if item_kind is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    created = Item(
        entity_id=details.created_item_id,
        name=f"foraged-{resource.kind.value}",
        kind=item_kind,
        load=ItemLoad(1),
        location_id=actor.location_id,
        holder_id=None,
    )
    resources = dict(state.resources)
    items = dict(state.items)
    resources[details.target_id] = copy_resource(
        resource, quantity=details.resulting_resource_quantity
    )
    items[details.created_item_id] = created
    try:
        return rebuild_world_state(state, items=items, resources=resources)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_eat(state: WorldState, event: WorldEvent, details: Eaten) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.resulting_hunger is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if details.item_id not in state.items:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    actor = state.bodies[actor_id]
    if details.item_id not in actor.inventory:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    items = dict(state.items)
    bodies = dict(state.bodies)
    del items[details.item_id]
    bodies[actor_id] = copy_body(
        actor,
        inventory=tuple(owned for owned in actor.inventory if owned != details.item_id),
        hunger=Hunger(details.resulting_hunger),
    )
    try:
        return rebuild_world_state(state, items=items, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_drink(state: WorldState, event: WorldEvent, details: Drunk) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.consumed_item is None or details.resulting_thirst is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    actor = state.bodies[actor_id]
    bodies = dict(state.bodies)
    items = dict(state.items)
    resources = dict(state.resources)
    if details.consumed_item:
        if details.source_id not in state.items:
            raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
        if details.source_id not in actor.inventory:
            raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
        del items[details.source_id]
        bodies[actor_id] = copy_body(
            actor,
            inventory=tuple(
                owned for owned in actor.inventory if owned != details.source_id
            ),
            thirst=Thirst(details.resulting_thirst),
        )
    else:
        if details.source_id not in state.resources:
            raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
        if details.resulting_resource_quantity is None:
            raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
        resource = state.resources[details.source_id]
        resources[details.source_id] = copy_resource(
            resource, quantity=details.resulting_resource_quantity
        )
        bodies[actor_id] = copy_body(actor, thirst=Thirst(details.resulting_thirst))
    try:
        return rebuild_world_state(
            state, items=items, bodies=bodies, resources=resources
        )
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_sleep(state: WorldState, event: WorldEvent, details: Slept) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.resulting_fatigue is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    actor = state.bodies[actor_id]
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(actor, fatigue=Fatigue(details.resulting_fatigue))
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_help(state: WorldState, event: WorldEvent, details: Helped) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.target_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if (
        details.resulting_target_health is None
        or details.resulting_helper_fatigue is None
    ):
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    helper = state.bodies[actor_id]
    target = state.bodies[details.target_id]
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(
        helper, fatigue=Fatigue(details.resulting_helper_fatigue)
    )
    bodies[details.target_id] = copy_body(
        target, health=Health(details.resulting_target_health)
    )
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_attack_hit(
    state: WorldState, event: WorldEvent, details: Attacked
) -> WorldState:
    if event.actor_id is None or event.actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.target_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    if details.resulting_target_health is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    target = state.bodies[details.target_id]
    bodies = dict(state.bodies)
    resulting = details.resulting_target_health
    if resulting <= 0.0:
        # Match live attack application: lethal hits flip life status atomically
        # before the separate Died event is projected.
        bodies[details.target_id] = copy_body(
            target,
            health=Health(0.0),
            life_status=LifeStatus.DEAD,
        )
    else:
        bodies[details.target_id] = copy_body(target, health=Health(resulting))
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_flee_success(
    state: WorldState, event: WorldEvent, details: Fled
) -> WorldState:
    actor_id = event.actor_id
    if actor_id is None or actor_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.ACTOR_MISSING)
    if details.destination_id is None or details.resulting_fatigue is None:
        raise ProjectionError(ProjectionErrorCode.PRECONDITION_FAILED)
    if details.destination_id not in state.locations:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    actor = state.bodies[actor_id]
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(
        actor,
        location_id=details.destination_id,
        fatigue=Fatigue(details.resulting_fatigue),
    )
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_weather(state: WorldState, details: WeatherChanged) -> WorldState:
    if details.location_id not in state.weather:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    weather = dict(state.weather)
    current = state.weather[details.location_id]
    weather[details.location_id] = copy_weather(current, condition=details.condition)
    try:
        return rebuild_world_state(state, weather=weather)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_regeneration(
    state: WorldState, details: ResourceRegenerated
) -> WorldState:
    if details.resource_id not in state.resources:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    resource = state.resources[details.resource_id]
    resources = dict(state.resources)
    resources[details.resource_id] = copy_resource(
        resource, quantity=details.resulting_quantity
    )
    try:
        return rebuild_world_state(state, resources=resources)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_needs(state: WorldState, details: NeedsApplied) -> WorldState:
    if details.body_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    body = state.bodies[details.body_id]
    bodies = dict(state.bodies)
    bodies[details.body_id] = copy_body(
        body,
        hunger=Hunger(details.resulting_hunger),
        thirst=Thirst(details.resulting_thirst),
        fatigue=Fatigue(details.resulting_fatigue),
        health=Health(details.resulting_health),
    )
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_exposure(state: WorldState, details: ExposureApplied) -> WorldState:
    if details.body_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    body = state.bodies[details.body_id]
    bodies = dict(state.bodies)
    bodies[details.body_id] = copy_body(
        body,
        temperature=TemperatureCelsius(details.resulting_temperature),
        health=Health(details.resulting_health),
    )
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _project_died(state: WorldState, details: Died) -> WorldState:
    if details.body_id not in state.bodies:
        raise ProjectionError(ProjectionErrorCode.TARGET_MISSING)
    body = state.bodies[details.body_id]
    bodies = dict(state.bodies)
    bodies[details.body_id] = copy_body(
        body,
        health=Health(0.0),
        life_status=LifeStatus.DEAD,
    )
    try:
        return rebuild_world_state(state, bodies=bodies)
    except ValueError as exc:
        raise ProjectionError(ProjectionErrorCode.INVARIANT_FAILED) from exc


def _copy_body(body: AgentBody, *, inventory: tuple[EntityId, ...]) -> AgentBody:
    return copy_body(body, inventory=inventory)
