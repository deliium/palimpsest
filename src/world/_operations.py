"""Private validated world operations.

Operation constructors are internal to this module. Python privacy and
import-linter/AST checks prevent accidental bypass of validation; they do
not stop hostile reflection.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal

from world._state import WorldState, rebuild_world_state
from world.actions import (
    ActionRequest,
    Amend,
    AnnotateRecord,
    Ask,
    Attack,
    Build,
    CopyRecord,
    Craft,
    DamageRecord,
    DepositRecord,
    Drink,
    Drop,
    Eat,
    Erase,
    EstablishRepository,
    Feed,
    Flee,
    Give,
    Harvest,
    Help,
    IndexRepository,
    Inscribe,
    MaintainRepository,
    Move,
    Repair,
    RetrieveRecord,
    Search,
    Sleep,
    Store,
    Take,
    Talk,
    Tell,
    TransferArtifact,
    Transport,
    Wait,
    require_agent_command,
)
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
)
from world.communications import StructuredUtterance
from world.effects import ActionCause, EventCause, require_event_cause
from world.events import (
    CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION,
    EventDetails,
    OccurrenceContext,
    WorldEvent,
    build_occurrence_context,
    make_physical_replayable_event,
    normalize_ordered_events,
)
from world.identifiers import (
    EntityId,
    EventId,
    RecipeId,
    RequestId,
    WorldId,
    WorldRevision,
    require_exact_nonneg_int,
    require_stable_id,
)
from world.models import AgentBody, Item, LifeStatus, Location, Resource

_LOG: Final[logging.Logger] = logging.getLogger("world._operations")

__all__: list[str] = [
    "BatchItemOutcome",
    "BatchItemStatus",
    "OperationAccepted",
    "OperationRejected",
    "PendingBatch",
    "PendingEvent",
    "PreparedBatch",
    "RejectionCode",
    "ValidatedWorldOperation",
    "finalize_pending_batch",
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
    NOT_AN_ITEM = "not_an_item"


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
    utterance: StructuredUtterance


@dataclass(frozen=True, slots=True)
class _AskOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    recipient_id: EntityId
    utterance: StructuredUtterance


@dataclass(frozen=True, slots=True)
class _TellOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    recipient_id: EntityId
    utterance: StructuredUtterance


@dataclass(frozen=True, slots=True)
class _HelpOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    target_id: EntityId


@dataclass(frozen=True, slots=True)
class _FeedOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    target_id: EntityId
    item_id: EntityId


@dataclass(frozen=True, slots=True)
class _TransportOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    target_id: EntityId
    destination_id: EntityId


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


@dataclass(frozen=True, slots=True)
class _HarvestOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    recipe_id: RecipeId
    resource_id: EntityId


@dataclass(frozen=True, slots=True)
class _CraftOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    recipe_id: RecipeId


@dataclass(frozen=True, slots=True)
class _BuildOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    recipe_id: RecipeId


@dataclass(frozen=True, slots=True)
class _RepairOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    recipe_id: RecipeId
    structure_id: EntityId


@dataclass(frozen=True, slots=True)
class _StoreOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    recipe_id: RecipeId
    item_id: EntityId


@dataclass(frozen=True, slots=True)
class _InscribeOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    artifact_kind: ArtifactKind
    content: ArtifactContent
    hold: bool
    record_genre: DurableRecordGenre | None = None


@dataclass(frozen=True, slots=True)
class _AmendOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    artifact_id: EntityId
    content: ArtifactContent


@dataclass(frozen=True, slots=True)
class _EraseOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    artifact_id: EntityId


@dataclass(frozen=True, slots=True)
class _TransferArtifactOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    artifact_id: EntityId
    mode: Literal["deposit", "claim", "give"]
    recipient_id: EntityId | None


@dataclass(frozen=True, slots=True)
class _CopyRecordOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    artifact_id: EntityId
    hold: bool
    fidelity_override: str | None


@dataclass(frozen=True, slots=True)
class _AnnotateRecordOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    artifact_id: EntityId
    content: ArtifactContent


@dataclass(frozen=True, slots=True)
class _DamageRecordOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    artifact_id: EntityId
    mode: Literal["damage", "partial_loss", "destroy"]


@dataclass(frozen=True, slots=True)
class _EstablishRepositoryOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    location_id: EntityId
    access_mode: str | None
    structure_id: EntityId | None


@dataclass(frozen=True, slots=True)
class _DepositRecordOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    repository_id: EntityId
    artifact_id: EntityId


@dataclass(frozen=True, slots=True)
class _RetrieveRecordOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    repository_id: EntityId
    artifact_id: EntityId
    hold: bool


@dataclass(frozen=True, slots=True)
class _MaintainRepositoryOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    repository_id: EntityId
    mode: Literal["maintain", "destroy"]


@dataclass(frozen=True, slots=True)
class _IndexRepositoryOp:
    request_id: RequestId
    actor_id: EntityId
    world_id: WorldId
    base_revision: WorldRevision
    repository_id: EntityId
    entries: tuple[Mapping[str, object], ...]


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
    | _FeedOp
    | _TransportOp
    | _AttackOp
    | _FleeOp
    | _WaitOp
    | _HarvestOp
    | _CraftOp
    | _BuildOp
    | _RepairOp
    | _StoreOp
    | _InscribeOp
    | _AmendOp
    | _EraseOp
    | _TransferArtifactOp
    | _CopyRecordOp
    | _AnnotateRecordOp
    | _DamageRecordOp
    | _EstablishRepositoryOp
    | _DepositRecordOp
    | _RetrieveRecordOp
    | _MaintainRepositoryOp
    | _IndexRepositoryOp
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
        _FeedOp,
        _TransportOp,
        _AttackOp,
        _FleeOp,
        _WaitOp,
        _HarvestOp,
        _CraftOp,
        _BuildOp,
        _RepairOp,
        _StoreOp,
        _InscribeOp,
        _AmendOp,
        _EraseOp,
        _TransferArtifactOp,
        _CopyRecordOp,
        _AnnotateRecordOp,
        _DamageRecordOp,
        _EstablishRepositoryOp,
        _DepositRecordOp,
        _RetrieveRecordOp,
        _MaintainRepositoryOp,
        _IndexRepositoryOp,
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
        return OperationRejected(code=RejectionCode.WRONG_WORLD, request_id=request_id)
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
        return OperationRejected(code=RejectionCode.DEAD_ACTOR, request_id=request_id)

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
            return OperationAccepted(_MoveOp(*base, destination_id=destination_id))
        case Search(target_id=target_id):
            if target_id is not None:
                rejected = _require_any_entity(state, target_id, request_id)
                if rejected is not None:
                    return rejected
            return OperationAccepted(_SearchOp(*base, target_id=target_id))
        case Take(item_id=item_id):
            if item_id in state.artifacts:
                _LOG.warning(
                    "artifact_rejected actor_id=%s artifact_id=%s reason_code=%s",
                    request.actor_id.value,
                    item_id.value,
                    RejectionCode.NOT_AN_ITEM.value,
                )
                return OperationRejected(
                    code=RejectionCode.NOT_AN_ITEM, request_id=request_id
                )
            rejected = _require_item(state, item_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(_TakeOp(*base, item_id=item_id))
        case Drop(item_id=item_id):
            if item_id in state.artifacts:
                _LOG.warning(
                    "artifact_rejected actor_id=%s artifact_id=%s reason_code=%s",
                    request.actor_id.value,
                    item_id.value,
                    RejectionCode.NOT_AN_ITEM.value,
                )
                return OperationRejected(
                    code=RejectionCode.NOT_AN_ITEM, request_id=request_id
                )
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
            if item_id in state.artifacts:
                _LOG.warning(
                    "artifact_rejected actor_id=%s artifact_id=%s reason_code=%s",
                    request.actor_id.value,
                    item_id.value,
                    RejectionCode.NOT_AN_ITEM.value,
                )
                return OperationRejected(
                    code=RejectionCode.NOT_AN_ITEM, request_id=request_id
                )
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
            rejected = _require_item_or_resource(state, source_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(_DrinkOp(*base, source_id=source_id))
        case Sleep():
            return OperationAccepted(_SleepOp(*base))
        case Talk(recipient_id=recipient_id, utterance=utterance):
            if recipient_id == request.actor_id:
                return OperationRejected(
                    code=RejectionCode.DISTINCT_ID_VIOLATION, request_id=request_id
                )
            rejected = _require_body(state, recipient_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(
                _TalkOp(*base, recipient_id=recipient_id, utterance=utterance)
            )
        case Ask(recipient_id=recipient_id, utterance=utterance):
            if recipient_id == request.actor_id:
                return OperationRejected(
                    code=RejectionCode.DISTINCT_ID_VIOLATION, request_id=request_id
                )
            rejected = _require_body(state, recipient_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(
                _AskOp(*base, recipient_id=recipient_id, utterance=utterance)
            )
        case Tell(recipient_id=recipient_id, utterance=utterance):
            if recipient_id == request.actor_id:
                return OperationRejected(
                    code=RejectionCode.DISTINCT_ID_VIOLATION, request_id=request_id
                )
            rejected = _require_body(state, recipient_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(
                _TellOp(*base, recipient_id=recipient_id, utterance=utterance)
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
        case Feed(target_id=target_id, item_id=item_id):
            if target_id == request.actor_id:
                return OperationRejected(
                    code=RejectionCode.DISTINCT_ID_VIOLATION, request_id=request_id
                )
            rejected = _require_body(state, target_id, request_id)
            if rejected is not None:
                return rejected
            rejected = _require_item(state, item_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(
                _FeedOp(*base, target_id=target_id, item_id=item_id)
            )
        case Transport(target_id=target_id, destination_id=destination_id):
            if target_id == request.actor_id:
                return OperationRejected(
                    code=RejectionCode.DISTINCT_ID_VIOLATION, request_id=request_id
                )
            rejected = _require_body(state, target_id, request_id)
            if rejected is not None:
                return rejected
            rejected = _require_location(state, destination_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(
                _TransportOp(
                    *base, target_id=target_id, destination_id=destination_id
                )
            )
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
        case Harvest(recipe_id=recipe_id, resource_id=resource_id):
            rejected = _require_resource(state, resource_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(
                _HarvestOp(*base, recipe_id=recipe_id, resource_id=resource_id)
            )
        case Craft(recipe_id=recipe_id):
            return OperationAccepted(_CraftOp(*base, recipe_id=recipe_id))
        case Build(recipe_id=recipe_id):
            return OperationAccepted(_BuildOp(*base, recipe_id=recipe_id))
        case Repair(recipe_id=recipe_id, structure_id=structure_id):
            rejected = _require_structure(state, structure_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(
                _RepairOp(*base, recipe_id=recipe_id, structure_id=structure_id)
            )
        case Store(recipe_id=recipe_id, item_id=item_id):
            rejected = _require_item(state, item_id, request_id)
            if rejected is not None:
                return rejected
            return OperationAccepted(
                _StoreOp(*base, recipe_id=recipe_id, item_id=item_id)
            )
        case Inscribe(
            kind=artifact_kind,
            content=content,
            hold=hold,
            record_genre=record_genre,
        ):
            return OperationAccepted(
                _InscribeOp(
                    *base,
                    artifact_kind=artifact_kind,
                    content=content,
                    hold=hold,
                    record_genre=record_genre,
                )
            )
        case Amend(artifact_id=artifact_id, content=content):
            return OperationAccepted(
                _AmendOp(*base, artifact_id=artifact_id, content=content)
            )
        case Erase(artifact_id=artifact_id):
            return OperationAccepted(_EraseOp(*base, artifact_id=artifact_id))
        case TransferArtifact(
            artifact_id=artifact_id, mode=mode, recipient_id=recipient_id
        ):
            return OperationAccepted(
                _TransferArtifactOp(
                    *base,
                    artifact_id=artifact_id,
                    mode=mode,
                    recipient_id=recipient_id,
                )
            )
        case CopyRecord(
            artifact_id=artifact_id,
            hold=hold,
            fidelity_override=fidelity_override,
        ):
            return OperationAccepted(
                _CopyRecordOp(
                    *base,
                    artifact_id=artifact_id,
                    hold=hold,
                    fidelity_override=fidelity_override,
                )
            )
        case AnnotateRecord(artifact_id=artifact_id, content=content):
            return OperationAccepted(
                _AnnotateRecordOp(*base, artifact_id=artifact_id, content=content)
            )
        case DamageRecord(artifact_id=artifact_id, mode=mode):
            return OperationAccepted(
                _DamageRecordOp(*base, artifact_id=artifact_id, mode=mode)
            )
        case EstablishRepository(
            location_id=location_id,
            access_mode=access_mode,
            structure_id=structure_id,
        ):
            rejected = _require_location(state, location_id, request_id)
            if rejected is not None:
                return rejected
            if structure_id is not None:
                rejected = _require_structure(state, structure_id, request_id)
                if rejected is not None:
                    return rejected
            return OperationAccepted(
                _EstablishRepositoryOp(
                    *base,
                    location_id=location_id,
                    access_mode=access_mode,
                    structure_id=structure_id,
                )
            )
        case DepositRecord(repository_id=repository_id, artifact_id=artifact_id):
            return OperationAccepted(
                _DepositRecordOp(
                    *base,
                    repository_id=repository_id,
                    artifact_id=artifact_id,
                )
            )
        case RetrieveRecord(
            repository_id=repository_id, artifact_id=artifact_id, hold=hold
        ):
            return OperationAccepted(
                _RetrieveRecordOp(
                    *base,
                    repository_id=repository_id,
                    artifact_id=artifact_id,
                    hold=hold,
                )
            )
        case MaintainRepository(repository_id=repository_id, mode=mode):
            return OperationAccepted(
                _MaintainRepositoryOp(
                    *base, repository_id=repository_id, mode=mode
                )
            )
        case IndexRepository(repository_id=repository_id, entries=entries):
            return OperationAccepted(
                _IndexRepositoryOp(
                    *base, repository_id=repository_id, entries=entries
                )
            )
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


def _require_item_or_resource(
    state: WorldState, entity_id: EntityId, request_id: RequestId
) -> OperationRejected | None:
    if entity_id in state.items and type(state.items[entity_id]) is Item:
        return None
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
        or entity_id in state.structures
        or entity_id in state.artifacts
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
class PendingEvent:
    """Unfrozen objective detail pending final revision/event-id allocation."""

    cause: EventCause
    details: EventDetails
    occurrence: OccurrenceContext

    def __post_init__(self) -> None:
        object.__setattr__(self, "cause", require_event_cause(self.cause))
        from world.events import require_event_details

        object.__setattr__(self, "details", require_event_details(self.details))
        if type(self.occurrence) is not OccurrenceContext:
            raise TypeError("PendingEvent.occurrence must be OccurrenceContext")


@dataclass(frozen=True, slots=True)
class PendingBatch:
    """Action-stage candidate before revision/event finalization."""

    working_state: WorldState
    semantic_mutation: bool
    outcomes: tuple[BatchItemOutcome, ...]
    pending_events: tuple[PendingEvent, ...]

    def __post_init__(self) -> None:
        if type(self.working_state) is not WorldState:
            raise TypeError("PendingBatch.working_state must be WorldState")
        if type(self.semantic_mutation) is not bool:
            raise TypeError("PendingBatch.semantic_mutation must be bool")
        if isinstance(self.outcomes, (str, bytes)) or not isinstance(
            self.outcomes, tuple
        ):
            raise TypeError("PendingBatch.outcomes must be a tuple")
        for outcome in self.outcomes:
            if type(outcome) is not BatchItemOutcome:
                raise TypeError(
                    "PendingBatch.outcomes entries must be BatchItemOutcome"
                )
        if isinstance(self.pending_events, (str, bytes)) or not isinstance(
            self.pending_events, tuple
        ):
            raise TypeError("PendingBatch.pending_events must be a tuple")
        for pending in self.pending_events:
            if type(pending) is not PendingEvent:
                raise TypeError(
                    "PendingBatch.pending_events entries must be PendingEvent"
                )


@dataclass(frozen=True, slots=True)
class PreparedBatch:
    """Immutable finalized batch candidate. Does not install world authority."""

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
    resolved_effects: object | None = None,
    rules: object | None = None,
    tick: int | None = None,
    skill_efficiency: object | None = None,
    witness_resource_nodes: bool = False,
    effective_carry_capacity: Mapping[EntityId, int] | None = None,
    denied_command_kinds_by_entity: Mapping[EntityId, frozenset[str]] | None = None,
    dependency_care_context: object | None = None,
    durable_records_context: object | None = None,
    knowledge_repositories_context: object | None = None,
) -> PendingBatch:
    """Resolve ordered requests into pending effects against one evolving state.

    Working mutations keep the starting revision. Conflict is recorded only when
    a request was initially applicable and a prior effect invalidated it.
    Revision, sequences, and event IDs are allocated by
    :func:`finalize_pending_batch`.
    """
    from world._rules import RuleDisposition, apply_operation, evaluate_operation
    from world.effects import ResolvedActionEffects
    from world.models import PhysicalRules, default_physical_rules

    if type(world_id) is not WorldId:
        raise TypeError("prepare_action_batch requires WorldId")
    if type(starting_state) is not WorldState:
        raise TypeError("prepare_action_batch requires WorldState")
    if isinstance(requests, (set, frozenset)) or not isinstance(requests, Sequence):
        raise TypeError("requests must be an ordered sequence")
    if (
        resolved_effects is not None
        and type(resolved_effects) is not ResolvedActionEffects
    ):
        raise TypeError(
            "prepare_action_batch resolved_effects must be ResolvedActionEffects"
        )
    if rules is None:
        physical_rules = default_physical_rules()
    elif type(rules) is PhysicalRules:
        physical_rules = rules
    else:
        raise TypeError("prepare_action_batch rules must be PhysicalRules")
    efficiency_map = None
    if skill_efficiency is not None:
        from world._skills import SkillEfficiencyOverride

        if not isinstance(skill_efficiency, Mapping):
            raise TypeError("skill_efficiency must be a mapping")
        efficiency_map = {}
        for entity_id, override in skill_efficiency.items():
            if type(entity_id) is not EntityId:
                raise TypeError("skill_efficiency keys must be EntityId")
            if type(override) is not SkillEfficiencyOverride:
                raise TypeError(
                    "skill_efficiency values must be SkillEfficiencyOverride"
                )
            efficiency_map[entity_id] = override
    capacity_map = None
    if effective_carry_capacity is not None:
        if not isinstance(effective_carry_capacity, Mapping):
            raise TypeError("effective_carry_capacity must be a mapping")
        capacity_map = effective_carry_capacity
    deny_map = None
    if denied_command_kinds_by_entity is not None:
        if not isinstance(denied_command_kinds_by_entity, Mapping):
            raise TypeError("denied_command_kinds_by_entity must be a mapping")
        deny_map = denied_command_kinds_by_entity
    care_context = dependency_care_context
    if care_context is not None:
        from world.dependency_care import DependencyCareRuleContext

        if type(care_context) is not DependencyCareRuleContext:
            raise TypeError(
                "dependency_care_context must be DependencyCareRuleContext or None"
            )
    durable_context = durable_records_context
    if durable_context is not None:
        from world.artifacts import DurableRecordsRuleContext

        if type(durable_context) is not DurableRecordsRuleContext:
            raise TypeError(
                "durable_records_context must be DurableRecordsRuleContext or None"
            )
    repository_context = knowledge_repositories_context
    if repository_context is not None:
        from world.repositories import KnowledgeRepositoriesRuleContext

        if type(repository_context) is not KnowledgeRepositoriesRuleContext:
            raise TypeError(
                "knowledge_repositories_context must be "
                "KnowledgeRepositoriesRuleContext or None"
            )
    request_tuple = tuple(requests)
    resolved = resolved_effects

    working = starting_state
    semantic_mutation = False
    outcomes: list[BatchItemOutcome] = []
    pending_events: list[PendingEvent] = []

    for ordinal, request in enumerate(request_tuple):
        if type(request) is not ActionRequest:
            raise TypeError("requests entries must be ActionRequest")
        if request.world_id != world_id:
            raise BatchPreparationError("request world_id mismatch")
        if request.revision != starting_state.revision:
            raise BatchPreparationError("request revision must match starting state")
        kind = getattr(request.command, "kind", type(request.command).__name__)
        if deny_map is not None:
            denied = deny_map.get(request.actor_id)
            reject_reason: str | None = None
            if isinstance(denied, Mapping):
                raw_reason = denied.get(str(kind))
                if type(raw_reason) is str:
                    reject_reason = raw_reason
            elif denied is not None and str(kind) in denied:
                reject_reason = "lifecycle_stage_action_denied"
            if reject_reason is not None:
                _LOG.warning(
                    "command_kind_denied actor_id=%s kind=%s "
                    "reason_code=%s",
                    request.actor_id.value,
                    kind,
                    reject_reason,
                )
                if reject_reason == "dependency_care_self_satisfy_denied":
                    _LOG.debug(
                        "dependency_care_self_satisfy_denied actor_id=%s "
                        "command_kind=%s code=dependency_care_self_satisfy_denied",
                        request.actor_id.value,
                        kind,
                    )
                outcomes.append(
                    BatchItemOutcome(
                        ordinal=ordinal,
                        request_id=request.request_id,
                        status=BatchItemStatus.REJECTED,
                        reason=reject_reason,
                        action_kind=str(kind),
                    )
                )
                continue

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
        start_rule = evaluate_operation(
            starting_state,
            start_validation.operation,
            rules=physical_rules,
            resolved=resolved,
            tick=tick,
            effective_carry_capacity=capacity_map,
            dependency_care_context=care_context,
            durable_records_context=durable_context,
            knowledge_repositories_context=repository_context,
        )
        if start_rule.disposition is RuleDisposition.REJECT:
            if start_rule.action_kind in {"feed", "transport"}:
                _LOG.warning(
                    "dependency_care_reject actor_id=%s kind=%s reason_code=%s",
                    request.actor_id.value,
                    start_rule.action_kind,
                    start_rule.reason.value,
                )
            if start_rule.action_kind in {
                "copy_record",
                "annotate_record",
                "damage_record",
            }:
                _LOG.warning(
                    "durable_record_reject actor_id=%s kind=%s reason_code=%s",
                    request.actor_id.value,
                    start_rule.action_kind,
                    start_rule.reason.value,
                )
            if start_rule.action_kind in {
                "establish_repository",
                "deposit_record",
                "retrieve_record",
                "maintain_repository",
                "index_repository",
            }:
                _LOG.warning(
                    "knowledge_repository_reject actor_id=%s kind=%s reason_code=%s",
                    request.actor_id.value,
                    start_rule.action_kind,
                    start_rule.reason.value,
                )
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
        state_before = working
        actor_efficiency = None
        if efficiency_map is not None:
            actor_efficiency = efficiency_map.get(request.actor_id)
        application = apply_operation(
            working,
            work_validation.operation,
            rules=physical_rules,
            resolved=resolved,
            tick=tick,
            skill_efficiency=actor_efficiency,
            witness_resource_nodes=witness_resource_nodes,
            effective_carry_capacity=capacity_map,
            dependency_care_context=care_context,
            durable_records_context=durable_context,
            knowledge_repositories_context=repository_context,
        )
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
            cause = ActionCause(request.request_id, request.actor_id)
            actor_body = state_before.bodies.get(request.actor_id)
            origin_location_id = None if actor_body is None else actor_body.location_id
            for details in application.all_event_details():
                pending_events.append(
                    PendingEvent(
                        cause=cause,
                        details=details,
                        occurrence=build_occurrence_context(
                            details,
                            origin_location_id=origin_location_id,
                        ),
                    )
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
        if application.result.action_kind in {"feed", "transport"}:
            target_id = getattr(work_validation.operation, "target_id", None)
            _LOG.info(
                "dependency_care_mutate actor_id=%s target_id=%s assist_kind=%s tick=%s",
                request.actor_id.value,
                getattr(target_id, "value", target_id),
                application.result.action_kind,
                tick,
            )

    return PendingBatch(
        working_state=working,
        semantic_mutation=semantic_mutation,
        outcomes=tuple(outcomes),
        pending_events=tuple(pending_events),
    )


def _require_structure(
    state: WorldState, entity_id: EntityId, request_id: RequestId
) -> OperationRejected | None:
    from world.production import Structure

    if entity_id in state.structures and type(state.structures[entity_id]) is Structure:
        return None
    if _exists_elsewhere(state, entity_id):
        return OperationRejected(
            code=RejectionCode.WRONG_TARGET_CATEGORY, request_id=request_id
        )
    return OperationRejected(code=RejectionCode.MISSING_TARGET, request_id=request_id)


def finalize_pending_batch(
    pending: PendingBatch,
    *,
    world_id: WorldId,
    starting_revision: WorldRevision,
    event_ids: Sequence[EventId],
    run_id: str,
    tick: int,
    schema_version: int = CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION,
) -> PreparedBatch:
    """Advance revision at most once and freeze pending events with final facts."""
    if type(pending) is not PendingBatch:
        raise TypeError("finalize_pending_batch requires PendingBatch")
    if type(world_id) is not WorldId:
        raise TypeError("finalize_pending_batch requires WorldId")
    if type(starting_revision) is not WorldRevision:
        raise TypeError("finalize_pending_batch requires WorldRevision")
    run_id_value = require_stable_id("run_id", run_id)
    tick_value = require_exact_nonneg_int("tick", tick)
    if isinstance(event_ids, (set, frozenset)) or not isinstance(event_ids, Sequence):
        raise TypeError("event_ids must be an ordered sequence")
    event_id_tuple = tuple(event_ids)
    if len(event_id_tuple) != len(pending.pending_events):
        raise ValueError("event_ids length must match pending_events length")
    seen_event_ids: set[EventId] = set()
    for event_id in event_id_tuple:
        if type(event_id) is not EventId:
            raise TypeError("event_ids entries must be EventId")
        if event_id in seen_event_ids:
            raise BatchPreparationError("duplicate event_id in batch inputs")
        seen_event_ids.add(event_id)

    if pending.semantic_mutation:
        resulting_revision = WorldRevision(starting_revision.value + 1)
        candidate = rebuild_world_state(
            pending.working_state, revision=resulting_revision
        )
    else:
        if pending.working_state.revision != starting_revision:
            raise BatchPreparationError("non-mutating working revision mismatch")
        resulting_revision = starting_revision
        candidate = pending.working_state

    events: list[WorldEvent] = []
    for sequence, (pending_event, event_id) in enumerate(
        zip(pending.pending_events, event_id_tuple, strict=True)
    ):
        events.append(
            make_physical_replayable_event(
                event_id=event_id,
                run_id=run_id_value,
                world_id=world_id,
                tick=tick_value,
                sequence=sequence,
                cause=pending_event.cause,
                resulting_revision=resulting_revision,
                details=pending_event.details,
                occurrence=pending_event.occurrence,
                schema_version=schema_version,
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
        semantic_mutation=pending.semantic_mutation,
        outcomes=pending.outcomes,
        events=normalized,
    )
