"""Authority-facing transition capabilities. Not part of the public facade."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from world._state import WorldState
from world.actions import (
    ActionOutcome,
    ActionRequest,
    TransitionOutcome,
    accept_action_request,
)
from world.events import (
    Asked,
    Attacked,
    Dropped,
    Drunk,
    Eaten,
    EventDetails,
    Fled,
    Given,
    Helped,
    Moved,
    Searched,
    Slept,
    Taken,
    Talked,
    Told,
    Waited,
    WorldEvent,
    normalize_events,
)
from world.identifiers import EventId, RequestId, WorldId, WorldRevision

__all__: list[str] = [
    "TransitionResult",
    "WorldTransition",
    "apply_trusted",
    "apply_validated_operation",
]


@dataclass(frozen=True, slots=True)
class TransitionResult:
    """Private result of applying a validated operation."""

    base_revision: WorldRevision
    resulting_revision: WorldRevision
    outcome: TransitionOutcome
    events: tuple[WorldEvent, ...]

    def __post_init__(self) -> None:
        if type(self.base_revision) is not WorldRevision:
            raise TypeError("TransitionResult.base_revision must be WorldRevision")
        if type(self.resulting_revision) is not WorldRevision:
            raise TypeError("TransitionResult.resulting_revision must be WorldRevision")
        if type(self.outcome) is not TransitionOutcome:
            raise TypeError("TransitionResult.outcome must be TransitionOutcome")
        events = normalize_events(self.events)
        object.__setattr__(self, "events", events)


class WorldTransition(Protocol):
    """Applies a trusted request to authoritative state. Simulation-only."""

    def apply(self, state: WorldState, request: ActionRequest) -> ActionOutcome:
        """Advance ``state`` using ``request`` after gateway validation."""
        ...


def apply_trusted(
    transition: WorldTransition, state: WorldState, request: object
) -> ActionOutcome:
    """Validate ``request`` then apply it. Proposals and mappings are rejected."""
    trusted = accept_action_request(request)
    return transition.apply(state, trusted)


def apply_validated_operation(
    state: WorldState,
    operation: object,
    *,
    event_ids: Sequence[EventId],
) -> TransitionResult:
    """Apply a private validated operation and emit closed occurrence events.

    Behavioral world mutation is deferred. Events record occurrence-only facts
    correlated to the request, world, and resulting revision.
    """
    from world import _operations as operations

    if type(operation) not in operations._OPERATION_TYPES:
        raise TypeError("apply_validated_operation requires a private operation")
    details = _details_for(operation)
    resulting_revision = state.revision
    event_id_tuple = tuple(event_ids)
    if len(event_id_tuple) != 1:
        raise ValueError("deferred transitions emit exactly one occurrence event")
    event = WorldEvent(
        event_id=event_id_tuple[0],
        request_id=operation.request_id,  # type: ignore[attr-defined]
        world_id=operation.world_id,  # type: ignore[attr-defined]
        revision=resulting_revision,
        details=details,
    )
    return TransitionResult(
        base_revision=operation.base_revision,  # type: ignore[attr-defined]
        resulting_revision=resulting_revision,
        outcome=TransitionOutcome.APPLIED,
        events=(event,),
    )


def _details_for(operation: object) -> EventDetails:
    from world._operations import (
        _AskOp,
        _AttackOp,
        _DrinkOp,
        _DropOp,
        _EatOp,
        _FleeOp,
        _GiveOp,
        _HelpOp,
        _MoveOp,
        _SearchOp,
        _SleepOp,
        _TakeOp,
        _TalkOp,
        _TellOp,
        _WaitOp,
    )

    match operation:
        case _MoveOp(destination_id=destination_id):
            return Moved(destination_id)
        case _SearchOp(target_id=target_id):
            return Searched(target_id)
        case _TakeOp(item_id=item_id):
            return Taken(item_id)
        case _DropOp(item_id=item_id):
            return Dropped(item_id)
        case _GiveOp(recipient_id=recipient_id, item_id=item_id):
            return Given(recipient_id, item_id)
        case _EatOp(item_id=item_id):
            return Eaten(item_id)
        case _DrinkOp(source_id=source_id):
            return Drunk(source_id)
        case _SleepOp():
            return Slept()
        case _TalkOp(recipient_id=recipient_id, text=text):
            return Talked(recipient_id, text)
        case _AskOp(recipient_id=recipient_id, text=text):
            return Asked(recipient_id, text)
        case _TellOp(recipient_id=recipient_id, text=text):
            return Told(recipient_id, text)
        case _HelpOp(target_id=target_id):
            return Helped(target_id)
        case _AttackOp(target_id=target_id):
            return Attacked(target_id)
        case _FleeOp(threat_id=threat_id):
            return Fled(threat_id)
        case _WaitOp():
            return Waited()
        case _:
            raise TypeError(f"unsupported operation type {type(operation).__name__}")


def require_transition_events(
    *,
    world_id: WorldId,
    request_id: RequestId,
    resulting_revision: WorldRevision,
    events: Sequence[WorldEvent],
) -> tuple[WorldEvent, ...]:
    """Normalize and correlate transition events."""
    normalized = normalize_events(events)
    for event in normalized:
        if event.world_id != world_id:
            raise ValueError("transition event world_id mismatch")
        if event.request_id != request_id:
            raise ValueError("transition event request_id mismatch")
        if event.revision != resulting_revision:
            raise ValueError("transition event revision mismatch")
    return normalized
