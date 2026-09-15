"""Private validated world operations.

Operation constructors are internal to this module. Python privacy and
import-linter/AST checks prevent accidental bypass of validation; they do
not stop hostile reflection.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world._state import WorldState
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
from world.identifiers import EntityId, RequestId, WorldId, WorldRevision
from world.models import AgentBody, Item, Location, Resource

__all__: list[str] = [
    "OperationAccepted",
    "OperationRejected",
    "RejectionCode",
    "ValidatedWorldOperation",
    "validate_action_request",
]


class RejectionCode(StrEnum):
    WRONG_TRUST_STAGE = "wrong_trust_stage"
    WRONG_WORLD = "wrong_world"
    STALE_REVISION = "stale_revision"
    INVALID_ACTOR_BINDING = "invalid_actor_binding"
    MISSING_ACTOR_BODY = "missing_actor_body"
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
