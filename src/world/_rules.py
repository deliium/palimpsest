"""Pure V1 action rule interfaces and outcome matrix.

Rules evaluate immutable snapshots and validated operations only. They do not
import simulation, logging, wall clocks, UUID factories, or randomness.
Behavioral mutation handlers are applied by later rule/transition stages;
this module owns dispositions, reason codes, and precedence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world._operations import (
    ValidatedWorldOperation,
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
from world._state import WorldState, rebuild_world_state
from world.events import (
    Asked,
    Dropped,
    EventDetails,
    Given,
    Searched,
    Taken,
    Talked,
    Told,
    Waited,
)
from world.identifiers import EntityId
from world.models import AgentBody, Item, LifeStatus

__all__: list[str] = [
    "COMMAND_RULE_MATRIX",
    "CommandRulePolicy",
    "RuleApplication",
    "RuleDisposition",
    "RuleReason",
    "RuleResult",
    "apply_operation",
    "evaluate_operation",
]


class RuleDisposition(StrEnum):
    """Closed rule outcome category for one validated operation."""

    MUTATE = "mutate"
    EVENT_ONLY = "event_only"
    DEFERRED = "deferred"
    REJECT = "reject"


class RuleReason(StrEnum):
    """Stable reason codes for engine DEBUG correlation (no free-form text)."""

    OCCURRENCE = "occurrence"
    DEAD_ACTOR = "dead_actor"
    DEAD_TARGET = "dead_target"
    NOT_HELD = "not_held"
    NOT_AT_LOCATION = "not_at_location"
    NOT_COLOCATED = "not_colocated"
    ALREADY_AT_DESTINATION = "already_at_destination"
    DEFERRED_POLICY = "deferred_policy"
    STRUCTURAL_OK = "structural_ok"


@dataclass(frozen=True, slots=True)
class CommandRulePolicy:
    """Documented V1 policy row for one command family."""

    disposition: RuleDisposition
    emits_event_when_applied: bool
    mutates_state_when_applied: bool
    requires_living_actor: bool
    notes: str


@dataclass(frozen=True, slots=True)
class RuleResult:
    """Pure evaluation result. Contains no snapshots or communication text."""

    disposition: RuleDisposition
    reason: RuleReason
    emits_event: bool
    mutates_state: bool
    action_kind: str

    def __post_init__(self) -> None:
        if type(self.disposition) is not RuleDisposition:
            raise TypeError("RuleResult.disposition must be RuleDisposition")
        if type(self.reason) is not RuleReason:
            raise TypeError("RuleResult.reason must be RuleReason")
        if type(self.emits_event) is not bool:
            raise TypeError("RuleResult.emits_event must be bool")
        if type(self.mutates_state) is not bool:
            raise TypeError("RuleResult.mutates_state must be bool")
        if type(self.action_kind) is not str or not self.action_kind:
            raise TypeError("RuleResult.action_kind must be a non-empty str")
        if self.disposition is RuleDisposition.REJECT:
            if self.emits_event or self.mutates_state:
                raise ValueError("rejected rules never emit events or mutate")
        if self.disposition is RuleDisposition.DEFERRED:
            if self.emits_event or self.mutates_state:
                raise ValueError("deferred rules never emit events or mutate")
        if self.disposition is RuleDisposition.EVENT_ONLY and self.mutates_state:
            raise ValueError("event-only rules must not mutate state")
        if self.disposition is RuleDisposition.MUTATE and not self.mutates_state:
            raise ValueError("mutate disposition requires mutates_state")


# Complete V1 outcome matrix (interfaces + precedence documentation).
COMMAND_RULE_MATRIX: Final[dict[type, CommandRulePolicy]] = {
    _TakeOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="item at actor location, not held; inventory/holder agreement",
    ),
    _DropOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="item held by actor; place at actor location",
    ),
    _GiveOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="item held; living colocated recipient; reject dead recipient",
    ),
    _SearchOp: CommandRulePolicy(
        disposition=RuleDisposition.EVENT_ONLY,
        emits_event_when_applied=True,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes="validated occurrence only; no hidden-object discovery",
    ),
    _TalkOp: CommandRulePolicy(
        disposition=RuleDisposition.EVENT_ONLY,
        emits_event_when_applied=True,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes="recipient body must exist; dead recipient still allowed as occurrence",
    ),
    _AskOp: CommandRulePolicy(
        disposition=RuleDisposition.EVENT_ONLY,
        emits_event_when_applied=True,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes="recipient body must exist; dead recipient still allowed as occurrence",
    ),
    _TellOp: CommandRulePolicy(
        disposition=RuleDisposition.EVENT_ONLY,
        emits_event_when_applied=True,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes="recipient body must exist; dead recipient still allowed as occurrence",
    ),
    _WaitOp: CommandRulePolicy(
        disposition=RuleDisposition.EVENT_ONLY,
        emits_event_when_applied=True,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes="validated occurrence only",
    ),
    _MoveOp: CommandRulePolicy(
        disposition=RuleDisposition.DEFERRED,
        emits_event_when_applied=False,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes="topology undefined; includes same-location no-op cases",
    ),
    _EatOp: CommandRulePolicy(
        disposition=RuleDisposition.DEFERRED,
        emits_event_when_applied=False,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes="nutrition policy undefined",
    ),
    _DrinkOp: CommandRulePolicy(
        disposition=RuleDisposition.DEFERRED,
        emits_event_when_applied=False,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes="consumption policy undefined",
    ),
    _SleepOp: CommandRulePolicy(
        disposition=RuleDisposition.DEFERRED,
        emits_event_when_applied=False,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes="recovery/duration policy undefined",
    ),
    _HelpOp: CommandRulePolicy(
        disposition=RuleDisposition.DEFERRED,
        emits_event_when_applied=False,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes="social/assist policy undefined; dead target rejected later if needed",
    ),
    _AttackOp: CommandRulePolicy(
        disposition=RuleDisposition.DEFERRED,
        emits_event_when_applied=False,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes="combat policy undefined",
    ),
    _FleeOp: CommandRulePolicy(
        disposition=RuleDisposition.DEFERRED,
        emits_event_when_applied=False,
        mutates_state_when_applied=False,
        requires_living_actor=True,
        notes="escape/topology policy undefined",
    ),
}

_OPERATION_KIND: Final[dict[type, str]] = {
    _MoveOp: "move",
    _SearchOp: "search",
    _TakeOp: "take",
    _DropOp: "drop",
    _GiveOp: "give",
    _EatOp: "eat",
    _DrinkOp: "drink",
    _SleepOp: "sleep",
    _TalkOp: "talk",
    _AskOp: "ask",
    _TellOp: "tell",
    _HelpOp: "help",
    _AttackOp: "attack",
    _FleeOp: "flee",
    _WaitOp: "wait",
}


def evaluate_operation(
    state: WorldState, operation: ValidatedWorldOperation
) -> RuleResult:
    """Evaluate a validated operation against an immutable snapshot.

    Precedence:
    1. dead actor (all commands)
    2. deferred-policy family
    3. command-specific placement/ownership/co-location/dead-target checks
    4. mutate or event-only success

    One-action slot consumption is enforced by the engine, not by rules.
    Conflict classification across a batch is handled by batch preparation.
    """
    if type(state) is not WorldState:
        raise TypeError("evaluate_operation requires WorldState")
    op_type = type(operation)
    policy = COMMAND_RULE_MATRIX.get(op_type)
    if policy is None:
        raise TypeError(f"unsupported operation type {op_type.__name__}")
    kind = _OPERATION_KIND[op_type]
    actor = state.bodies.get(operation.actor_id)
    if actor is None:
        # Structural validation should have caught this; fail closed.
        return RuleResult(
            disposition=RuleDisposition.REJECT,
            reason=RuleReason.DEAD_ACTOR,
            emits_event=False,
            mutates_state=False,
            action_kind=kind,
        )
    if actor.life_status is LifeStatus.DEAD:
        return RuleResult(
            disposition=RuleDisposition.REJECT,
            reason=RuleReason.DEAD_ACTOR,
            emits_event=False,
            mutates_state=False,
            action_kind=kind,
        )
    if policy.disposition is RuleDisposition.DEFERRED:
        return RuleResult(
            disposition=RuleDisposition.DEFERRED,
            reason=RuleReason.DEFERRED_POLICY,
            emits_event=False,
            mutates_state=False,
            action_kind=kind,
        )
    match operation:
        case _TakeOp(item_id=item_id):
            return _evaluate_take(state, operation.actor_id, item_id, kind)
        case _DropOp(item_id=item_id):
            return _evaluate_drop(state, operation.actor_id, item_id, kind)
        case _GiveOp(recipient_id=recipient_id, item_id=item_id):
            return _evaluate_give(
                state, operation.actor_id, recipient_id, item_id, kind
            )
        case _SearchOp() | _TalkOp() | _AskOp() | _TellOp() | _WaitOp():
            return RuleResult(
                disposition=RuleDisposition.EVENT_ONLY,
                reason=RuleReason.OCCURRENCE,
                emits_event=True,
                mutates_state=False,
                action_kind=kind,
            )
        case _:
            raise TypeError(f"unhandled operation type {op_type.__name__}")


def _evaluate_take(
    state: WorldState, actor_id: EntityId, item_id: EntityId, kind: str
) -> RuleResult:
    actor = state.bodies[actor_id]
    item = state.items[item_id]
    if item.location_id is None or item.holder_id is not None:
        return _reject(kind, RuleReason.NOT_AT_LOCATION)
    if item.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_AT_LOCATION)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_drop(
    state: WorldState, actor_id: EntityId, item_id: EntityId, kind: str
) -> RuleResult:
    actor = state.bodies[actor_id]
    item = state.items[item_id]
    if item.holder_id != actor_id or item_id not in actor.inventory:
        return _reject(kind, RuleReason.NOT_HELD)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_give(
    state: WorldState,
    actor_id: EntityId,
    recipient_id: EntityId,
    item_id: EntityId,
    kind: str,
) -> RuleResult:
    actor = state.bodies[actor_id]
    recipient = state.bodies[recipient_id]
    item = state.items[item_id]
    if recipient.life_status is LifeStatus.DEAD:
        return _reject(kind, RuleReason.DEAD_TARGET)
    if item.holder_id != actor_id or item_id not in actor.inventory:
        return _reject(kind, RuleReason.NOT_HELD)
    if recipient.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_COLOCATED)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _reject(kind: str, reason: RuleReason) -> RuleResult:
    return RuleResult(
        disposition=RuleDisposition.REJECT,
        reason=reason,
        emits_event=False,
        mutates_state=False,
        action_kind=kind,
    )


@dataclass(frozen=True, slots=True)
class RuleApplication:
    """Pure apply result: disposition metadata plus optional next state/details."""

    result: RuleResult
    next_state: WorldState
    event_details: EventDetails | None

    def __post_init__(self) -> None:
        if type(self.result) is not RuleResult:
            raise TypeError("RuleApplication.result must be RuleResult")
        if type(self.next_state) is not WorldState:
            raise TypeError("RuleApplication.next_state must be WorldState")
        if self.event_details is not None and not self.result.emits_event:
            raise ValueError("event_details require emits_event")
        if self.event_details is None and self.result.emits_event:
            raise ValueError("emits_event requires event_details")
        if self.result.mutates_state and self.next_state is None:
            raise ValueError("mutate requires next_state")


def apply_operation(
    state: WorldState, operation: ValidatedWorldOperation
) -> RuleApplication:
    """Evaluate then apply immutable physical or event-only effects.

    Deferred and rejected outcomes never mutate state and never produce events.
    Revision bumping is owned by batch preparation, not by this helper.
    """
    result = evaluate_operation(state, operation)
    if result.disposition in {
        RuleDisposition.REJECT,
        RuleDisposition.DEFERRED,
    }:
        return RuleApplication(
            result=result, next_state=state, event_details=None
        )
    details = _event_details_for(operation)
    if result.disposition is RuleDisposition.EVENT_ONLY:
        return RuleApplication(
            result=result, next_state=state, event_details=details
        )
    assert result.disposition is RuleDisposition.MUTATE
    next_state = _apply_mutation(state, operation)
    return RuleApplication(
        result=result, next_state=next_state, event_details=details
    )


def _event_details_for(operation: ValidatedWorldOperation) -> EventDetails:
    match operation:
        case _TakeOp(item_id=item_id):
            return Taken(item_id)
        case _DropOp(item_id=item_id):
            return Dropped(item_id)
        case _GiveOp(recipient_id=recipient_id, item_id=item_id):
            return Given(recipient_id, item_id)
        case _SearchOp(target_id=target_id):
            return Searched(target_id)
        case _TalkOp(recipient_id=recipient_id, text=text):
            return Talked(recipient_id, text)
        case _AskOp(recipient_id=recipient_id, text=text):
            return Asked(recipient_id, text)
        case _TellOp(recipient_id=recipient_id, text=text):
            return Told(recipient_id, text)
        case _WaitOp():
            return Waited()
        case _:
            raise TypeError(
                f"no event details for {type(operation).__name__}"
            )


def _apply_mutation(
    state: WorldState, operation: ValidatedWorldOperation
) -> WorldState:
    match operation:
        case _TakeOp(actor_id=actor_id, item_id=item_id):
            return _mutate_take(state, actor_id, item_id)
        case _DropOp(actor_id=actor_id, item_id=item_id):
            return _mutate_drop(state, actor_id, item_id)
        case _GiveOp(actor_id=actor_id, recipient_id=recipient_id, item_id=item_id):
            return _mutate_give(state, actor_id, recipient_id, item_id)
        case _:
            raise TypeError(
                f"mutation unsupported for {type(operation).__name__}"
            )


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


def _mutate_take(
    state: WorldState, actor_id: EntityId, item_id: EntityId
) -> WorldState:
    actor = state.bodies[actor_id]
    item = state.items[item_id]
    items = dict(state.items)
    bodies = dict(state.bodies)
    items[item_id] = Item(
        entity_id=item.entity_id,
        name=item.name,
        holder_id=actor_id,
    )
    bodies[actor_id] = _copy_body(
        actor, inventory=(*actor.inventory, item_id)
    )
    return rebuild_world_state(state, items=items, bodies=bodies)


def _mutate_drop(
    state: WorldState, actor_id: EntityId, item_id: EntityId
) -> WorldState:
    actor = state.bodies[actor_id]
    item = state.items[item_id]
    items = dict(state.items)
    bodies = dict(state.bodies)
    items[item_id] = Item(
        entity_id=item.entity_id,
        name=item.name,
        location_id=actor.location_id,
    )
    bodies[actor_id] = _copy_body(
        actor,
        inventory=tuple(owned for owned in actor.inventory if owned != item_id),
    )
    return rebuild_world_state(state, items=items, bodies=bodies)


def _mutate_give(
    state: WorldState,
    actor_id: EntityId,
    recipient_id: EntityId,
    item_id: EntityId,
) -> WorldState:
    actor = state.bodies[actor_id]
    recipient = state.bodies[recipient_id]
    item = state.items[item_id]
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
    return rebuild_world_state(state, items=items, bodies=bodies)

