"""Authority-facing transition capabilities. Not part of the public facade."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from world._state import WorldState, rebuild_world_state
from world.actions import (
    ActionOutcome,
    ActionRequest,
    TransitionOutcome,
    accept_action_request,
)
from world.events import WorldEvent, normalize_events
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
    resulting_state: WorldState

    def __post_init__(self) -> None:
        if type(self.base_revision) is not WorldRevision:
            raise TypeError("TransitionResult.base_revision must be WorldRevision")
        if type(self.resulting_revision) is not WorldRevision:
            raise TypeError("TransitionResult.resulting_revision must be WorldRevision")
        if type(self.outcome) is not TransitionOutcome:
            raise TypeError("TransitionResult.outcome must be TransitionOutcome")
        if type(self.resulting_state) is not WorldState:
            raise TypeError("TransitionResult.resulting_state must be WorldState")
        events = normalize_events(self.events)
        object.__setattr__(self, "events", events)
        if self.resulting_state.revision != self.resulting_revision:
            raise ValueError("resulting_state.revision must match resulting_revision")


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
    """Apply a private validated operation using pure V1 rule handlers.

    Deferred and rule-rejected outcomes emit no events and do not mutate.
    Semantic mutations rebuild an immutable snapshot and advance revision by one.
    """
    from world import _operations as operations
    from world._rules import RuleDisposition, apply_operation

    if type(operation) not in operations._OPERATION_TYPES:
        raise TypeError("apply_validated_operation requires a private operation")
    application = apply_operation(state, operation)  # type: ignore[arg-type]
    base_revision = operation.base_revision  # type: ignore[attr-defined]
    if application.result.disposition in {
        RuleDisposition.REJECT,
        RuleDisposition.DEFERRED,
    }:
        return TransitionResult(
            base_revision=base_revision,
            resulting_revision=state.revision,
            outcome=TransitionOutcome.NOT_APPLIED,
            events=(),
            resulting_state=state,
        )
    event_id_tuple = tuple(event_ids)
    if len(event_id_tuple) != 1:
        raise ValueError("applied transitions emit exactly one occurrence event")
    if application.result.mutates_state:
        resulting_revision = WorldRevision(state.revision.value + 1)
        resulting_state = rebuild_world_state(
            application.next_state, revision=resulting_revision
        )
    else:
        resulting_revision = state.revision
        resulting_state = state
    assert application.event_details is not None
    event = WorldEvent(
        event_id=event_id_tuple[0],
        request_id=operation.request_id,  # type: ignore[attr-defined]
        world_id=operation.world_id,  # type: ignore[attr-defined]
        revision=resulting_revision,
        details=application.event_details,
    )
    return TransitionResult(
        base_revision=base_revision,
        resulting_revision=resulting_revision,
        outcome=TransitionOutcome.APPLIED,
        events=(event,),
        resulting_state=resulting_state,
    )


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
