"""Private validated world operations.

Operation constructors are internal to this module. Python privacy and
import-linter/AST checks prevent accidental bypass of validation; they do
not stop hostile reflection.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world._state import WorldState, rebuild_world_state
from world.actions import (
    ActionRequest,
    Ask,
    Attack,
    Drink,
    Drop,
    Eat,
    Flee,
    Give,
    Help,
    Move,
    Search,
    Sleep,
    Take,
    Talk,
    Tell,
    Wait,
    require_agent_command,
)
from world.events import (
    EventDetails,
    WorldEvent,
    make_replayable_event,
    normalize_ordered_events,
)
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
    require_exact_nonneg_int,
    require_stable_id,
)
from world.models import AgentBody, Item, LifeStatus, Location, Resource

__all__: list[str] = [
    "BatchItemOutcome",
    "BatchItemStatus",
    "OperationAccepted",
    "OperationRejected",
    "PreparedBatch",
    "RejectionCode",
    "ValidatedWorldOperation",
    "prepare_action_batch",
    "validate_action_request",
]


class RejectionCode(StrEnum):
    WRONG_TRUST_STAGE = "wrong_trust_stage"
    WRONG_WORLD = "wrong_world"
    STALE_REVISION = "stale_revision"
    INVALID_ACTOR_BINDING = "invalid_actor_binding"
    MISSING_ACTOR_BODY = "missing_actor_body"
    DEAD_ACTOR = "dead_actor"
    MISSING_TARGET = "missing_target"
    WRONG_TARGET_CATEGORY = "wrong_target_category"
    MALFORMED_ENVELOPE = "malformed_envelope"
    DISTINCT_ID_VIOLATION = "distinct_id_violation"


@dataclass(frozen=True, slots=True)
class _MoveOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    destination_id: EntityId


@dataclass(frozen=True, slots=True)
class _SearchOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    target_id: EntityId | None


@dataclass(frozen=True, slots=True)
class _TakeOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    item_id: EntityId


@dataclass(frozen=True, slots=True)
class _DropOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    item_id: EntityId


@dataclass(frozen=True, slots=True)
class _GiveOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    recipient_id: EntityId
    item_id: EntityId


@dataclass(frozen=True, slots=True)
class _EatOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    item_id: EntityId


@dataclass(frozen=True, slots=True)
class _DrinkOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    source_id: EntityId


@dataclass(frozen=True, slots=True)
class _SleepOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision


@dataclass(frozen=True, slots=True)
class _TalkOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    recipient_id: EntityId
    text: str


@dataclass(frozen=True, slots=True)
class _AskOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    recipient_id: EntityId
    text: str


@dataclass(frozen=True, slots=True)
class _TellOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    recipient_id: EntityId
    text: str


@dataclass(frozen=True, slots=True)
class _HelpOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    target_id: EntityId


@dataclass(frozen=True, slots=True)
class _AttackOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    target_id: EntityId


@dataclass(frozen=True, slots=True)
class _FleeOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    threat_id: EntityId | None


@dataclass(frozen=True, slots=True)
class _WaitOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision


ValidatedWorldOperation = (
    _MoveOp
    | _SearchOp
    | _TakeOp
    | _DropOp
    | _GiveOp
    | _EatOp
    | _DrinkOp
    | _SleepOp
    | _TalkOp
    | _AskOp
    | _TellOp
    | _HelpOp
    | _AttackOp
    | _FleeOp
    | _WaitOp
)

_OPERATION_TYPES: Final[frozenset[type]] = frozenset(
    {
        _MoveOp,
        _SearchOp,
        _TakeOp,
        _DropOp,
        _GiveOp,
        _EatOp,
        _DrinkOp,
        _SleepOp,
        _TalkOp,
        _AskOp,
        _TellOp,
        _HelpOp,
        _AttackOp,
        _FleeOp,
        _WaitOp,
    }
)


@dataclass(frozen=True, slots=True)
class OperationAccepted:
    operation: ValidatedWorldOperation

    def __post_init__(self) -> None:
        if type(self.operation) not in _OPERATION_TYPES:
            raise TypeError("OperationAccepted requires a private operation type")


@dataclass(frozen=True, slots=True)
class OperationRejected:
    code: RejectionCode
    request_id: RequestId | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not RejectionCode:
            raise TypeError("OperationRejected.code must be RejectionCode")
        if self.request_id is not None and type(self.request_id) is not RequestId:
            raise TypeError("OperationRejected.request_id must be RequestId or None")


def validate_action_request(
    *,
    world_id: WorldId,
    state: WorldState,
    request: object,
) -> OperationAccepted | OperationRejected:
    """Promote a bound request to a private operation, or reject it."""
    if type(request) is not ActionRequest:
        return OperationRejected(code=RejectionCode.WRONG_TRUST_STAGE)
    assert isinstance(request, ActionRequest)
    request_id = request.request_id
    try:
        command = require_agent_command(request.command)
    except TypeError:
        return OperationRejected(
            code=RejectionCode.MALFORMED_ENVELOPE, request_id=request_id
        )
    if type(request.world_id) is not WorldId or type(request.actor_id) is not EntityId:
        return OperationRejected(
            code=RejectionCode.MALFORMED_ENVELOPE, request_id=request_id
        )
    if type(request.revision) is not WorldRevision:
        return OperationRejected(
            code=RejectionCode.MALFORMED_ENVELOPE, request_id=request_id
        )
    if request.world_id != world_id:
        return OperationRejected(
            code=RejectionCode.WRONG_WORLD, request_id=request_id
        )
    if request.revision != state.revision:
        return OperationRejected(
            code=RejectionCode.STALE_REVISION, request_id=request_id
        )
    body = state.bodies.get(request.actor_id)
    if body is None:
        return OperationRejected(
            code=RejectionCode.MISSING_ACTOR_BODY, request_id=request_id
        )
    if type(body) is not AgentBody:
        return OperationRejected(
            code=RejectionCode.INVALID_ACTOR_BINDING, request_id=request_id
        )
    if body.life_status is LifeStatus.DEAD:
        return OperationRejected(
            code=RejectionCode.DEAD_ACTOR, request_id=request_id
        )

    base = (
        request.request_id,
        request.actor_id,
        request.world_id,
        request.revision,
    )
    match command:
        case Move(destination_id=destination_id):
            rejected = _require_location(state, destination_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(
                _MoveOp(*base, destination_id=destination_id)
            )
        case Search(target_id=target_id):
            if target_id is not None:
                rejected = _require_any_entity(state, target_id, request_id)
                if rejected is not None:
                    return rejected
            return OperationAccepted(_SearchOp(*base, target_id=target_id))
        case Take(item_id=item_id):
            rejected = _require_item(state, item_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(_TakeOp(*base, item_id=item_id))
        case Drop(item_id=item_id):
            rejected = _require_item(state, item_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(_DropOp(*base, item_id=item_id))
        case Give(recipient_id=recipient_id, item_id=item_id):
            if recipient_id == request.actor_id:
                return OperationRejected(
                    code=RejectionCode.DISTINCT_ID_VIOLATION, request_id=request_id
                )
            rejected = _require_body(state, recipient_id, request_id)
            if rejected is not None:
                return rejected
            rejected = _require_item(state, item_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(
                _GiveOp(*base, recipient_id=recipient_id, item_id=item_id)
            )
        case Eat(item_id=item_id):
            rejected = _require_item(state, item_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(_EatOp(*base, item_id=item_id))
        case Drink(source_id=source_id):
            rejected = _require_resource(state, source_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(_DrinkOp(*base, source_id=source_id))
        case Sleep():
            return OperationAccepted(_SleepOp(*base))
        case Talk(recipient_id=recipient_id, text=text):
            if recipient_id == request.actor_id:
                return OperationRejected(
                    code=RejectionCode.DISTINCT_ID_VIOLATION, request_id=request_id
                )
            rejected = _require_body(state, recipient_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(
                _TalkOp(*base, recipient_id=recipient_id, text=text)
            )
        case Ask(recipient_id=recipient_id, text=text):
            if recipient_id == request.actor_id:
                return OperationRejected(
                    code=RejectionCode.DISTINCT_ID_VIOLATION, request_id=request_id
                )
            rejected = _require_body(state, recipient_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(
                _AskOp(*base, recipient_id=recipient_id, text=text)
            )
        case Tell(recipient_id=recipient_id, text=text):
            if recipient_id == request.actor_id:
                return OperationRejected(
                    code=RejectionCode.DISTINCT_ID_VIOLATION, request_id=request_id
                )
            rejected = _require_body(state, recipient_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(
                _TellOp(*base, recipient_id=recipient_id, text=text)
            )
        case Help(target_id=target_id):
            if target_id == request.actor_id:
                return OperationRejected(
                    code=RejectionCode.DISTINCT_ID_VIOLATION, request_id=request_id
                )
            rejected = _require_body(state, target_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(_HelpOp(*base, target_id=target_id))
        case Attack(target_id=target_id):
            if target_id == request.actor_id:
                return OperationRejected(
                    code=RejectionCode.DISTINCT_ID_VIOLATION, request_id=request_id
                )
            rejected = _require_body(state, target_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(_AttackOp(*base, target_id=target_id))
        case Flee(threat_id=threat_id):
            if threat_id is not None:
                if threat_id == request.actor_id:
                    return OperationRejected(
                        code=RejectionCode.DISTINCT_ID_VIOLATION,
                        request_id=request_id,
                    )
                rejected = _require_body(state, threat_id, request_id)
                if rejected is not None:
                    return rejected
            return OperationAccepted(_FleeOp(*base, threat_id=threat_id))
        case Wait():
            return OperationAccepted(_WaitOp(*base))
        case _:
            return OperationRejected(
                code=RejectionCode.MALFORMED_ENVELOPE, request_id=request_id
            )


def _require_location(
    state: WorldState, entity_id: EntityId, request_id: RequestId
) -> OperationRejected | None:
    if entity_id in state.locations and type(state.locations[entity_id]) is Location:
        return None
    if _exists_elsewhere(state, entity_id):
        return OperationRejected(
            code=RejectionCode.WRONG_TARGET_CATEGORY, request_id=request_id
        )
    return OperationRejected(code=RejectionCode.MISSING_TARGET, request_id=request_id)


def _require_item(
    state: WorldState, entity_id: EntityId, request_id: RequestId
) -> OperationRejected | None:
    if entity_id in state.items and type(state.items[entity_id]) is Item:
        return None
    if _exists_elsewhere(state, entity_id):
        return OperationRejected(
            code=RejectionCode.WRONG_TARGET_CATEGORY, request_id=request_id
        )
    return OperationRejected(code=RejectionCode.MISSING_TARGET, request_id=request_id)


def _require_resource(
    state: WorldState, entity_id: EntityId, request_id: RequestId
) -> OperationRejected | None:
    if entity_id in state.resources and type(state.resources[entity_id]) is Resource:
        return None
    if _exists_elsewhere(state, entity_id):
        return OperationRejected(
            code=RejectionCode.WRONG_TARGET_CATEGORY, request_id=request_id
        )
    return OperationRejected(code=RejectionCode.MISSING_TARGET, request_id=request_id)


def _require_body(
    state: WorldState, entity_id: EntityId, request_id: RequestId
) -> OperationRejected | None:
    if entity_id in state.bodies and type(state.bodies[entity_id]) is AgentBody:
        return None
    if _exists_elsewhere(state, entity_id):
        return OperationRejected(
            code=RejectionCode.WRONG_TARGET_CATEGORY, request_id=request_id
        )
    return OperationRejected(code=RejectionCode.MISSING_TARGET, request_id=request_id)


def _require_any_entity(
    state: WorldState, entity_id: EntityId, request_id: RequestId
) -> OperationRejected | None:
    if _exists_elsewhere(state, entity_id):
        return None
    return OperationRejected(code=RejectionCode.MISSING_TARGET, request_id=request_id)


def _exists_elsewhere(state: WorldState, entity_id: EntityId) -> bool:
    return (
        entity_id in state.locations
        or entity_id in state.items
        or entity_id in state.resources
        or entity_id in state.bodies
    )


class BatchItemStatus(StrEnum):
    APPLIED = "applied"
    REJECTED = "rejected"
    CONFLICTED = "conflicted"
    DEFERRED_POLICY = "deferred_policy"


@dataclass(frozen=True, slots=True)
class BatchItemOutcome:
    ordinal: int
    request_id: RequestId
    status: BatchItemStatus
    reason: str
    action_kind: str

    def __post_init__(self) -> None:
        if (
            type(self.ordinal) is not int
            or isinstance(self.ordinal, bool)
            or self.ordinal < 0
        ):
            raise ValueError("BatchItemOutcome.ordinal must be a non-negative int")
        if type(self.request_id) is not RequestId:
            raise TypeError("BatchItemOutcome.request_id must be RequestId")
        if type(self.status) is not BatchItemStatus:
            raise TypeError("BatchItemOutcome.status must be BatchItemStatus")
        if type(self.reason) is not str or not self.reason:
            raise TypeError("BatchItemOutcome.reason must be a non-empty str")
        if type(self.action_kind) is not str or not self.action_kind:
            raise TypeError("BatchItemOutcome.action_kind must be a non-empty str")


@dataclass(frozen=True, slots=True)
class PreparedBatch:
    """Immutable batch candidate. Does not install world authority."""

    candidate_state: WorldState
    semantic_mutation: bool
    outcomes: tuple[BatchItemOutcome, ...]
    events: tuple[WorldEvent, ...]

    def __post_init__(self) -> None:
        if type(self.candidate_state) is not WorldState:
            raise TypeError("PreparedBatch.candidate_state must be WorldState")
        if type(self.semantic_mutation) is not bool:
            raise TypeError("PreparedBatch.semantic_mutation must be bool")
        object.__setattr__(self, "events", normalize_ordered_events(self.events))


class BatchPreparationError(ValueError):
    """Invariant failure while preparing a batch candidate."""


def prepare_action_batch(
    *,
    world_id: WorldId,
    starting_state: WorldState,
    requests: Sequence[ActionRequest],
    event_ids: Sequence[EventId],
    run_id: str,
    tick: int,
) -> PreparedBatch:
    """Prepare a candidate snapshot from ordered admitted requests.

    Working mutations keep the starting revision until the end. Revision advances
    once when any semantic mutation occurs; all emitted events use that final
    revision. Conflict is recorded only when a request was initially applicable
    and a prior effect invalidated it. Intra-tick ``sequence`` is assigned in
    emission order starting at 0.
    """
    from world._rules import RuleDisposition, apply_operation, evaluate_operation

    if type(world_id) is not WorldId:
        raise TypeError("prepare_action_batch requires WorldId")
    if type(starting_state) is not WorldState:
        raise TypeError("prepare_action_batch requires WorldState")
    run_id_value = require_stable_id("run_id", run_id)
    tick_value = require_exact_nonneg_int("tick", tick)
    if isinstance(requests, (set, frozenset)) or not isinstance(requests, Sequence):
        raise TypeError("requests must be an ordered sequence")
    if isinstance(event_ids, (set, frozenset)) or not isinstance(event_ids, Sequence):
        raise TypeError("event_ids must be an ordered sequence")
    request_tuple = tuple(requests)
    event_id_tuple = tuple(event_ids)
    if len(request_tuple) != len(event_id_tuple):
        raise ValueError("event_ids length must match requests length")
    seen_event_ids: set[EventId] = set()
    for event_id in event_id_tuple:
        if type(event_id) is not EventId:
            raise TypeError("event_ids entries must be EventId")
        if event_id in seen_event_ids:
            raise BatchPreparationError("duplicate event_id in batch inputs")
        seen_event_ids.add(event_id)

    working = starting_state
    semantic_mutation = False
    outcomes: list[BatchItemOutcome] = []
    pending_events: list[tuple[ActionRequest, EventDetails, EventId]] = []

    for ordinal, request in enumerate(request_tuple):
        if type(request) is not ActionRequest:
            raise TypeError("requests entries must be ActionRequest")
        if request.world_id != world_id:
            raise BatchPreparationError("request world_id mismatch")
        if request.revision != starting_state.revision:
            raise BatchPreparationError("request revision must match starting state")
        kind = getattr(request.command, "kind", type(request.command).__name__)

        start_validation = validate_action_request(
            world_id=world_id, state=starting_state, request=request
        )
        if type(start_validation) is OperationRejected:
            outcomes.append(
                BatchItemOutcome(
                    ordinal=ordinal,
                    request_id=request.request_id,
                    status=BatchItemStatus.REJECTED,
                    reason=start_validation.code.value,
                    action_kind=str(kind),
                )
            )
            continue

        assert type(start_validation) is OperationAccepted
        start_rule = evaluate_operation(starting_state, start_validation.operation)
        if start_rule.disposition is RuleDisposition.REJECT:
            outcomes.append(
                BatchItemOutcome(
                    ordinal=ordinal,
                    request_id=request.request_id,
                    status=BatchItemStatus.REJECTED,
                    reason=start_rule.reason.value,
                    action_kind=start_rule.action_kind,
                )
            )
            continue
        if start_rule.disposition is RuleDisposition.DEFERRED:
            outcomes.append(
                BatchItemOutcome(
                    ordinal=ordinal,
                    request_id=request.request_id,
                    status=BatchItemStatus.DEFERRED_POLICY,
                    reason=start_rule.reason.value,
                    action_kind=start_rule.action_kind,
                )
            )
            continue

        work_validation = validate_action_request(
            world_id=world_id, state=working, request=request
        )
        if type(work_validation) is OperationRejected:
            outcomes.append(
                BatchItemOutcome(
                    ordinal=ordinal,
                    request_id=request.request_id,
                    status=BatchItemStatus.CONFLICTED,
                    reason="conflict_with_prior",
                    action_kind=start_rule.action_kind,
                )
            )
            continue

        assert type(work_validation) is OperationAccepted
        application = apply_operation(working, work_validation.operation)
        if application.result.disposition is RuleDisposition.REJECT:
            outcomes.append(
                BatchItemOutcome(
                    ordinal=ordinal,
                    request_id=request.request_id,
                    status=BatchItemStatus.CONFLICTED,
                    reason="conflict_with_prior",
                    action_kind=application.result.action_kind,
                )
            )
            continue
        if application.result.disposition is RuleDisposition.DEFERRED:
            outcomes.append(
                BatchItemOutcome(
                    ordinal=ordinal,
                    request_id=request.request_id,
                    status=BatchItemStatus.DEFERRED_POLICY,
                    reason=application.result.reason.value,
                    action_kind=application.result.action_kind,
                )
            )
            continue

        working = application.next_state
        if application.result.mutates_state:
            semantic_mutation = True
        if application.result.emits_event:
            assert application.event_details is not None
            pending_events.append(
                (request, application.event_details, event_id_tuple[ordinal])
            )
        outcomes.append(
            BatchItemOutcome(
                ordinal=ordinal,
                request_id=request.request_id,
                status=BatchItemStatus.APPLIED,
                reason=application.result.reason.value,
                action_kind=application.result.action_kind,
            )
        )

    if semantic_mutation:
        resulting_revision = WorldRevision(starting_state.revision.value + 1)
        candidate = rebuild_world_state(working, revision=resulting_revision)
    else:
        resulting_revision = starting_state.revision
        candidate = working

    events: list[WorldEvent] = []
    for sequence, (request, details, event_id) in enumerate(pending_events):
        events.append(
            make_replayable_event(
                event_id=event_id,
                run_id=run_id_value,
                world_id=world_id,
                tick=tick_value,
                sequence=sequence,
                request_id=request.request_id,
                resulting_revision=resulting_revision,
                details=details,
                actor_id=request.actor_id,
            )
        )
    normalized = normalize_ordered_events(events)
    for event in normalized:
        if event.world_id != world_id:
            raise BatchPreparationError("event world_id mismatch")
        if event.resulting_revision != resulting_revision:
            raise BatchPreparationError("event revision mismatch")
        if event.run_id != run_id_value or event.tick != tick_value:
            raise BatchPreparationError("event run/tick mismatch")

    return PreparedBatch(
        candidate_state=candidate,
        semantic_mutation=semantic_mutation,
        outcomes=tuple(outcomes),
        events=normalized,
    )
