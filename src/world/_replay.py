"""Pure objective-event projector for authoritative replay.

Applies recorded effect facts onto immutable ``WorldState`` without invoking
current command validation or behavioral rules. Log-free: callers map
``ProjectionError.code`` into orchestration ERROR diagnostics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world._state import WorldState, rebuild_world_state
from world.events import (
    Dropped,
    Given,
    Taken,
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
from world.models import AgentBody, Item

__all__: list[str] = [
    "ProjectionError",
    "ProjectionErrorCode",
    "project_events",
]

_MUTATING_KINDS: Final[frozenset[str]] = frozenset({"take", "drop", "give"})


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
        if event.details.kind in _MUTATING_KINDS:
            working = _apply_mutating_effect(working, event)
            mutated = True
        else:
            _validate_event_only_refs(working, event)

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


def _apply_mutating_effect(state: WorldState, event: WorldEvent) -> WorldState:
    match event.details:
        case Taken(item_id=item_id, resulting_holder_id=holder_id):
            return _project_take(state, event, item_id=item_id, holder_id=holder_id)
        case Dropped(item_id=item_id, resulting_location_id=location_id):
            return _project_drop(
                state, event, item_id=item_id, location_id=location_id
            )
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
    items[item_id] = Item(
        entity_id=item.entity_id,
        name=item.name,
        holder_id=actor_id,
    )
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
    items[item_id] = Item(
        entity_id=item.entity_id,
        name=item.name,
        location_id=location_id,
    )
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
    items[item_id] = Item(
        entity_id=item.entity_id,
        name=item.name,
        holder_id=recipient_id,
    )
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


def _copy_body(body: AgentBody, *, inventory: tuple[EntityId, ...]) -> AgentBody:
    return AgentBody(
        entity_id=body.entity_id,
        location_id=body.location_id,
        health=body.health,
        hunger=body.hunger,
        thirst=body.thirst,
        fatigue=body.fatigue,
        temperature=body.temperature,
        inventory=inventory,
        life_status=body.life_status,
    )
