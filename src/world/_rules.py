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
from world.effects import (
    DeathCause,
    ResolvedActionEffects,
    ResolvedAttackEffect,
    ResolvedFleeEffect,
    ResolvedSearchEffect,
)
from world.events import (
    Asked,
    Attacked,
    Died,
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
)
from world.identifiers import EntityId
from world.models import (
    AgentBody,
    Item,
    LifeStatus,
    PhysicalRules,
    Resource,
    copy_body,
    copy_item,
    copy_resource,
    default_physical_rules,
)
from world.values import (
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ItemLoad,
    ResourceKind,
    Thirst,
    clamp_need,
    round_physical,
)

__all__: list[str] = [
    "COMMAND_RULE_MATRIX",
    "CommandRulePolicy",
    "RuleApplication",
    "RuleDisposition",
    "RuleReason",
    "RuleResult",
    "apply_operation",
    "evaluate_operation",
    "find_eligible_flee_destinations",
    "find_eligible_search_resource",
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
    NOT_ADJACENT = "not_adjacent"
    NO_BODY_CAPACITY = "no_body_capacity"
    NO_ITEM_CAPACITY = "no_item_capacity"
    NO_CARRY_CAPACITY = "no_carry_capacity"
    RESOURCE_DEPLETED = "resource_depleted"
    WRONG_KIND = "wrong_kind"
    MISSING_RESOLVED_EFFECT = "missing_resolved_effect"
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
        notes="local ground item; carry capacity; inventory/holder agreement",
    ),
    _DropOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="item held by actor; free local ground item capacity",
    ),
    _GiveOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="item held; living colocated recipient; recipient carry capacity",
    ),
    _SearchOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes=(
            "eligible local resource + free ground slot; mutate-or-event via resolved"
        ),
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
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="adjacent destination with free body slot; add move fatigue",
    ),
    _EatOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="held food item; consume and reduce hunger",
    ),
    _DrinkOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="held water item or local water resource qty>=1; reduce thirst",
    ),
    _SleepOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="reduce fatigue by sleep recovery; shelter does not gate",
    ),
    _HelpOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes="living colocated target; heal + helper fatigue; no revival",
    ),
    _AttackOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes=(
            "living colocated target; mutate-or-event via resolved; "
            "lethal hit emits Attacked then Died"
        ),
    ),
    _FleeOp: CommandRulePolicy(
        disposition=RuleDisposition.MUTATE,
        emits_event_when_applied=True,
        mutates_state_when_applied=True,
        requires_living_actor=True,
        notes=(
            "optional living colocated threat; eligible adjacent capacity; "
            "mutate-or-event via resolved"
        ),
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

_SEARCH_RESOURCE_KINDS: Final[frozenset[ResourceKind]] = frozenset(
    {ResourceKind.FOOD, ResourceKind.WATER, ResourceKind.MATERIAL}
)

_ITEM_KIND_FOR_RESOURCE: Final[dict[ResourceKind, ItemKind]] = {
    ResourceKind.FOOD: ItemKind.FOOD,
    ResourceKind.WATER: ItemKind.WATER,
    ResourceKind.MATERIAL: ItemKind.MATERIAL,
}


def evaluate_operation(
    state: WorldState,
    operation: ValidatedWorldOperation,
    *,
    rules: PhysicalRules | None = None,
    resolved: ResolvedActionEffects | None = None,
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
    physical_rules = _require_rules(rules)
    if resolved is not None and type(resolved) is not ResolvedActionEffects:
        raise TypeError("evaluate_operation resolved must be ResolvedActionEffects")
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
        case _MoveOp(destination_id=destination_id):
            return _evaluate_move(state, operation.actor_id, destination_id, kind)
        case _SearchOp(target_id=target_id):
            return _evaluate_search(
                state,
                operation.actor_id,
                target_id,
                kind,
                request_id=operation.request_id,
                resolved=resolved,
            )
        case _TakeOp(item_id=item_id):
            return _evaluate_take(state, operation.actor_id, item_id, kind)
        case _DropOp(item_id=item_id):
            return _evaluate_drop(state, operation.actor_id, item_id, kind)
        case _GiveOp(recipient_id=recipient_id, item_id=item_id):
            return _evaluate_give(
                state, operation.actor_id, recipient_id, item_id, kind
            )
        case _EatOp(item_id=item_id):
            return _evaluate_eat(state, operation.actor_id, item_id, kind)
        case _DrinkOp(source_id=source_id):
            return _evaluate_drink(
                state, operation.actor_id, source_id, kind, rules=physical_rules
            )
        case _SleepOp():
            return RuleResult(
                disposition=RuleDisposition.MUTATE,
                reason=RuleReason.OCCURRENCE,
                emits_event=True,
                mutates_state=True,
                action_kind=kind,
            )
        case _HelpOp(target_id=target_id):
            return _evaluate_help(state, operation.actor_id, target_id, kind)
        case _AttackOp(target_id=target_id):
            return _evaluate_attack(
                state,
                operation.actor_id,
                target_id,
                kind,
                request_id=operation.request_id,
                resolved=resolved,
            )
        case _FleeOp(threat_id=threat_id):
            return _evaluate_flee(
                state,
                operation.actor_id,
                threat_id,
                kind,
                request_id=operation.request_id,
                resolved=resolved,
            )
        case _TalkOp() | _AskOp() | _TellOp() | _WaitOp():
            return RuleResult(
                disposition=RuleDisposition.EVENT_ONLY,
                reason=RuleReason.OCCURRENCE,
                emits_event=True,
                mutates_state=False,
                action_kind=kind,
            )
        case _:
            raise TypeError(f"unhandled operation type {op_type.__name__}")


def find_eligible_search_resource(
    state: WorldState,
    actor_id: EntityId,
    target_id: EntityId | None,
) -> EntityId | None:
    """Return the eligible Search resource id, or None when structurally invalid."""
    if type(state) is not WorldState:
        raise TypeError("find_eligible_search_resource requires WorldState")
    if type(actor_id) is not EntityId:
        raise TypeError("find_eligible_search_resource requires EntityId actor")
    if target_id is not None and type(target_id) is not EntityId:
        raise TypeError("find_eligible_search_resource target must be EntityId")
    actor = state.bodies.get(actor_id)
    if actor is None or actor.life_status is LifeStatus.DEAD:
        return None
    if (
        _ground_item_count(state, actor.location_id)
        >= state.locations[actor.location_id].item_capacity.value
    ):
        return None
    if target_id is not None:
        if not _resource_search_eligible(state, actor, target_id):
            return None
        return target_id
    for resource_id in sorted(state.resources, key=lambda value: value.value):
        if _resource_search_eligible(state, actor, resource_id):
            return resource_id
    return None


def find_eligible_flee_destinations(
    state: WorldState, actor_id: EntityId
) -> tuple[EntityId, ...]:
    """Return canonically sorted adjacent destinations with free body capacity."""
    if type(state) is not WorldState:
        raise TypeError("find_eligible_flee_destinations requires WorldState")
    if type(actor_id) is not EntityId:
        raise TypeError("find_eligible_flee_destinations requires EntityId actor")
    actor = state.bodies.get(actor_id)
    if actor is None or actor.life_status is LifeStatus.DEAD:
        return ()
    location = state.locations[actor.location_id]
    eligible: list[EntityId] = []
    for destination_id in sorted(location.adjacent, key=lambda value: value.value):
        destination = state.locations[destination_id]
        if _body_count(state, destination_id) < destination.body_capacity.value:
            eligible.append(destination_id)
    return tuple(eligible)


def _evaluate_move(
    state: WorldState, actor_id: EntityId, destination_id: EntityId, kind: str
) -> RuleResult:
    actor = state.bodies[actor_id]
    if destination_id == actor.location_id:
        return _reject(kind, RuleReason.ALREADY_AT_DESTINATION)
    location = state.locations[actor.location_id]
    if destination_id not in location.adjacent:
        return _reject(kind, RuleReason.NOT_ADJACENT)
    destination = state.locations[destination_id]
    if _body_count(state, destination_id) >= destination.body_capacity.value:
        return _reject(kind, RuleReason.NO_BODY_CAPACITY)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_search(
    state: WorldState,
    actor_id: EntityId,
    target_id: EntityId | None,
    kind: str,
    *,
    request_id: object,
    resolved: ResolvedActionEffects | None,
) -> RuleResult:
    structural = _search_structural_reject(state, actor_id, target_id, kind)
    if structural is not None:
        return structural
    if resolved is None:
        return _reject(kind, RuleReason.MISSING_RESOLVED_EFFECT)
    from world.identifiers import RequestId

    if type(request_id) is not RequestId:
        raise TypeError("search evaluation requires RequestId")
    effect = resolved.require(request_id, ResolvedSearchEffect)
    assert type(effect) is ResolvedSearchEffect
    if target_id is not None and effect.resource_id != target_id:
        raise ValueError("resolved search resource_id must match Search target")
    actor = state.bodies[actor_id]
    if (
        _ground_item_count(state, actor.location_id)
        >= state.locations[actor.location_id].item_capacity.value
    ):
        return _reject(kind, RuleReason.NO_ITEM_CAPACITY)
    resource_reject = _search_resource_reject(state, actor, effect.resource_id, kind)
    if resource_reject is not None:
        return resource_reject
    if effect.success:
        return RuleResult(
            disposition=RuleDisposition.MUTATE,
            reason=RuleReason.OCCURRENCE,
            emits_event=True,
            mutates_state=True,
            action_kind=kind,
        )
    return RuleResult(
        disposition=RuleDisposition.EVENT_ONLY,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=False,
        action_kind=kind,
    )


def _search_structural_reject(
    state: WorldState,
    actor_id: EntityId,
    target_id: EntityId | None,
    kind: str,
) -> RuleResult | None:
    actor = state.bodies[actor_id]
    location = state.locations[actor.location_id]
    if _ground_item_count(state, actor.location_id) >= location.item_capacity.value:
        return _reject(kind, RuleReason.NO_ITEM_CAPACITY)
    if target_id is None:
        if find_eligible_search_resource(state, actor_id, None) is None:
            return _reject(kind, RuleReason.RESOURCE_DEPLETED)
        return None
    return _search_resource_reject(state, actor, target_id, kind)


def _search_resource_reject(
    state: WorldState, actor: AgentBody, resource_id: EntityId, kind: str
) -> RuleResult | None:
    resource = state.resources.get(resource_id)
    if resource is None or type(resource) is not Resource:
        return _reject(kind, RuleReason.WRONG_KIND)
    if resource.kind not in _SEARCH_RESOURCE_KINDS:
        return _reject(kind, RuleReason.WRONG_KIND)
    if resource.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_AT_LOCATION)
    if resource.quantity < 1.0:
        return _reject(kind, RuleReason.RESOURCE_DEPLETED)
    return None


def _resource_search_eligible(
    state: WorldState, actor: AgentBody, resource_id: EntityId
) -> bool:
    return _search_resource_reject(state, actor, resource_id, "search") is None


def _evaluate_take(
    state: WorldState, actor_id: EntityId, item_id: EntityId, kind: str
) -> RuleResult:
    actor = state.bodies[actor_id]
    item = state.items[item_id]
    if item.location_id is None or item.holder_id is not None:
        return _reject(kind, RuleReason.NOT_AT_LOCATION)
    if item.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_AT_LOCATION)
    if _inventory_load(state, actor) + item.load.value > actor.carry_capacity.value:
        return _reject(kind, RuleReason.NO_CARRY_CAPACITY)
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
    location = state.locations[actor.location_id]
    if _ground_item_count(state, actor.location_id) >= location.item_capacity.value:
        return _reject(kind, RuleReason.NO_ITEM_CAPACITY)
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
    if (
        _inventory_load(state, recipient) + item.load.value
        > recipient.carry_capacity.value
    ):
        return _reject(kind, RuleReason.NO_CARRY_CAPACITY)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_eat(
    state: WorldState, actor_id: EntityId, item_id: EntityId, kind: str
) -> RuleResult:
    actor = state.bodies[actor_id]
    item = state.items[item_id]
    if item.holder_id != actor_id or item_id not in actor.inventory:
        return _reject(kind, RuleReason.NOT_HELD)
    if item.kind is not ItemKind.FOOD:
        return _reject(kind, RuleReason.WRONG_KIND)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_drink(
    state: WorldState,
    actor_id: EntityId,
    source_id: EntityId,
    kind: str,
    *,
    rules: PhysicalRules,
) -> RuleResult:
    del rules  # extraction threshold is fixed at 1.0 per contract
    actor = state.bodies[actor_id]
    item = state.items.get(source_id)
    if item is not None and type(item) is Item:
        if item.holder_id != actor_id or source_id not in actor.inventory:
            return _reject(kind, RuleReason.NOT_HELD)
        if item.kind is not ItemKind.WATER:
            return _reject(kind, RuleReason.WRONG_KIND)
        return RuleResult(
            disposition=RuleDisposition.MUTATE,
            reason=RuleReason.OCCURRENCE,
            emits_event=True,
            mutates_state=True,
            action_kind=kind,
        )
    resource = state.resources.get(source_id)
    if resource is None or type(resource) is not Resource:
        return _reject(kind, RuleReason.WRONG_KIND)
    if resource.kind is not ResourceKind.WATER:
        return _reject(kind, RuleReason.WRONG_KIND)
    if resource.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_AT_LOCATION)
    if resource.quantity < 1.0:
        return _reject(kind, RuleReason.RESOURCE_DEPLETED)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_help(
    state: WorldState, actor_id: EntityId, target_id: EntityId, kind: str
) -> RuleResult:
    actor = state.bodies[actor_id]
    target = state.bodies[target_id]
    if target.life_status is LifeStatus.DEAD:
        return _reject(kind, RuleReason.DEAD_TARGET)
    if target.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_COLOCATED)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _evaluate_attack(
    state: WorldState,
    actor_id: EntityId,
    target_id: EntityId,
    kind: str,
    *,
    request_id: object,
    resolved: ResolvedActionEffects | None,
) -> RuleResult:
    structural = _attack_structural_reject(state, actor_id, target_id, kind)
    if structural is not None:
        return structural
    if resolved is None:
        return _reject(kind, RuleReason.MISSING_RESOLVED_EFFECT)
    from world.identifiers import RequestId

    if type(request_id) is not RequestId:
        raise TypeError("attack evaluation requires RequestId")
    effect = resolved.require(request_id, ResolvedAttackEffect)
    assert type(effect) is ResolvedAttackEffect
    if effect.hit:
        return RuleResult(
            disposition=RuleDisposition.MUTATE,
            reason=RuleReason.OCCURRENCE,
            emits_event=True,
            mutates_state=True,
            action_kind=kind,
        )
    return RuleResult(
        disposition=RuleDisposition.EVENT_ONLY,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=False,
        action_kind=kind,
    )


def _attack_structural_reject(
    state: WorldState, actor_id: EntityId, target_id: EntityId, kind: str
) -> RuleResult | None:
    actor = state.bodies[actor_id]
    target = state.bodies[target_id]
    if target.life_status is LifeStatus.DEAD:
        return _reject(kind, RuleReason.DEAD_TARGET)
    if target.location_id != actor.location_id:
        return _reject(kind, RuleReason.NOT_COLOCATED)
    return None


def _evaluate_flee(
    state: WorldState,
    actor_id: EntityId,
    threat_id: EntityId | None,
    kind: str,
    *,
    request_id: object,
    resolved: ResolvedActionEffects | None,
) -> RuleResult:
    structural = _flee_structural_reject(state, actor_id, threat_id, kind)
    if structural is not None:
        return structural
    if resolved is None:
        return _reject(kind, RuleReason.MISSING_RESOLVED_EFFECT)
    from world.identifiers import RequestId

    if type(request_id) is not RequestId:
        raise TypeError("flee evaluation requires RequestId")
    effect = resolved.require(request_id, ResolvedFleeEffect)
    assert type(effect) is ResolvedFleeEffect
    eligible = find_eligible_flee_destinations(state, actor_id)
    if not eligible:
        return _reject(kind, RuleReason.NO_BODY_CAPACITY)
    if not effect.success:
        return RuleResult(
            disposition=RuleDisposition.EVENT_ONLY,
            reason=RuleReason.OCCURRENCE,
            emits_event=True,
            mutates_state=False,
            action_kind=kind,
        )
    assert effect.destination_index is not None
    if effect.destination_index >= len(eligible):
        return _reject(kind, RuleReason.NO_BODY_CAPACITY)
    return RuleResult(
        disposition=RuleDisposition.MUTATE,
        reason=RuleReason.OCCURRENCE,
        emits_event=True,
        mutates_state=True,
        action_kind=kind,
    )


def _flee_structural_reject(
    state: WorldState,
    actor_id: EntityId,
    threat_id: EntityId | None,
    kind: str,
) -> RuleResult | None:
    actor = state.bodies[actor_id]
    if threat_id is not None:
        threat = state.bodies[threat_id]
        if threat.life_status is LifeStatus.DEAD:
            return _reject(kind, RuleReason.DEAD_TARGET)
        if threat.location_id != actor.location_id:
            return _reject(kind, RuleReason.NOT_COLOCATED)
    location = state.locations[actor.location_id]
    if not location.adjacent:
        return _reject(kind, RuleReason.NOT_ADJACENT)
    if not find_eligible_flee_destinations(state, actor_id):
        return _reject(kind, RuleReason.NO_BODY_CAPACITY)
    return None


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
    extra_event_details: tuple[EventDetails, ...] = ()

    def __post_init__(self) -> None:
        if type(self.result) is not RuleResult:
            raise TypeError("RuleApplication.result must be RuleResult")
        if type(self.next_state) is not WorldState:
            raise TypeError("RuleApplication.next_state must be WorldState")
        if not isinstance(self.extra_event_details, tuple):
            raise TypeError("RuleApplication.extra_event_details must be a tuple")
        for detail in self.extra_event_details:
            from world.events import require_event_details

            require_event_details(detail)
        if self.event_details is not None and not self.result.emits_event:
            raise ValueError("event_details require emits_event")
        if self.event_details is None and self.result.emits_event:
            raise ValueError("emits_event requires event_details")
        if self.extra_event_details and not self.result.emits_event:
            raise ValueError("extra_event_details require emits_event")
        if self.extra_event_details and self.event_details is None:
            raise ValueError("extra_event_details require primary event_details")
        if self.result.mutates_state and self.next_state is None:
            raise ValueError("mutate requires next_state")

    def all_event_details(self) -> tuple[EventDetails, ...]:
        """Ordered primary and secondary details under one action cause."""
        if self.event_details is None:
            return ()
        return (self.event_details, *self.extra_event_details)


def apply_operation(
    state: WorldState,
    operation: ValidatedWorldOperation,
    *,
    rules: PhysicalRules | None = None,
    resolved: ResolvedActionEffects | None = None,
) -> RuleApplication:
    """Evaluate then apply immutable physical or event-only effects.

    Deferred and rejected outcomes never mutate state and never produce events.
    Revision bumping is owned by batch preparation, not by this helper.
    """
    physical_rules = _require_rules(rules)
    if resolved is not None and type(resolved) is not ResolvedActionEffects:
        raise TypeError("apply_operation resolved must be ResolvedActionEffects")
    result = evaluate_operation(
        state, operation, rules=physical_rules, resolved=resolved
    )
    if result.disposition in {
        RuleDisposition.REJECT,
        RuleDisposition.DEFERRED,
    }:
        return RuleApplication(result=result, next_state=state, event_details=None)
    if type(operation) is _SearchOp:
        return _apply_search(
            state, operation, result=result, rules=physical_rules, resolved=resolved
        )
    if type(operation) is _AttackOp:
        return _apply_attack(
            state, operation, result=result, rules=physical_rules, resolved=resolved
        )
    if type(operation) is _FleeOp:
        return _apply_flee(
            state, operation, result=result, rules=physical_rules, resolved=resolved
        )
    details = _event_details_for(state, operation, rules=physical_rules)
    if result.disposition is RuleDisposition.EVENT_ONLY:
        return RuleApplication(result=result, next_state=state, event_details=details)
    assert result.disposition is RuleDisposition.MUTATE
    next_state = _apply_mutation(state, operation, rules=physical_rules)
    # Recompute details from next_state for resulting physiology facts where needed.
    details = _event_details_for(
        state, operation, rules=physical_rules, next_state=next_state
    )
    return RuleApplication(result=result, next_state=next_state, event_details=details)


def _apply_search(
    state: WorldState,
    operation: _SearchOp,
    *,
    result: RuleResult,
    rules: PhysicalRules,
    resolved: ResolvedActionEffects | None,
) -> RuleApplication:
    if resolved is None:
        raise ValueError("search apply requires ResolvedActionEffects")
    effect = resolved.require(operation.request_id, ResolvedSearchEffect)
    assert type(effect) is ResolvedSearchEffect
    if not effect.success:
        return RuleApplication(
            result=result,
            next_state=state,
            event_details=Searched(target_id=effect.resource_id, success=False),
        )
    assert effect.created_item_id is not None
    resource = state.resources[effect.resource_id]
    extract = rules.resource_extraction_amount
    resulting_quantity = round_physical(resource.quantity - extract)
    item_kind = _ITEM_KIND_FOR_RESOURCE[resource.kind]
    actor = state.bodies[operation.actor_id]
    created = Item(
        entity_id=effect.created_item_id,
        name=f"foraged-{resource.kind.value}",
        kind=item_kind,
        load=ItemLoad(1),
        location_id=actor.location_id,
        holder_id=None,
    )
    resources = dict(state.resources)
    resources[effect.resource_id] = copy_resource(resource, quantity=resulting_quantity)
    items = dict(state.items)
    items[effect.created_item_id] = created
    next_state = rebuild_world_state(state, items=items, resources=resources)
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=Searched(
            target_id=effect.resource_id,
            success=True,
            created_item_id=effect.created_item_id,
            extracted_quantity=extract,
            resulting_resource_quantity=resulting_quantity,
        ),
    )


def _apply_attack(
    state: WorldState,
    operation: _AttackOp,
    *,
    result: RuleResult,
    rules: PhysicalRules,
    resolved: ResolvedActionEffects | None,
) -> RuleApplication:
    del rules
    if resolved is None:
        raise ValueError("attack apply requires ResolvedActionEffects")
    effect = resolved.require(operation.request_id, ResolvedAttackEffect)
    assert type(effect) is ResolvedAttackEffect
    if not effect.hit:
        return RuleApplication(
            result=result,
            next_state=state,
            event_details=Attacked(
                target_id=operation.target_id,
                hit=False,
            ),
        )
    assert effect.damage is not None
    target = state.bodies[operation.target_id]
    resulting_health = clamp_need(
        round_physical(target.health.value - float(effect.damage))
    )
    bodies = dict(state.bodies)
    if resulting_health <= 0.0:
        bodies[operation.target_id] = copy_body(
            target,
            health=Health(0.0),
            life_status=LifeStatus.DEAD,
        )
        next_state = rebuild_world_state(state, bodies=bodies)
        return RuleApplication(
            result=result,
            next_state=next_state,
            event_details=Attacked(
                target_id=operation.target_id,
                hit=True,
                damage=effect.damage,
                resulting_target_health=0.0,
            ),
            extra_event_details=(
                Died(
                    body_id=operation.target_id,
                    death_cause=DeathCause.ATTACK,
                ),
            ),
        )
    bodies[operation.target_id] = copy_body(target, health=Health(resulting_health))
    next_state = rebuild_world_state(state, bodies=bodies)
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=Attacked(
            target_id=operation.target_id,
            hit=True,
            damage=effect.damage,
            resulting_target_health=resulting_health,
        ),
    )


def _apply_flee(
    state: WorldState,
    operation: _FleeOp,
    *,
    result: RuleResult,
    rules: PhysicalRules,
    resolved: ResolvedActionEffects | None,
) -> RuleApplication:
    if resolved is None:
        raise ValueError("flee apply requires ResolvedActionEffects")
    effect = resolved.require(operation.request_id, ResolvedFleeEffect)
    assert type(effect) is ResolvedFleeEffect
    if not effect.success:
        return RuleApplication(
            result=result,
            next_state=state,
            event_details=Fled(
                threat_id=operation.threat_id,
                success=False,
            ),
        )
    eligible = find_eligible_flee_destinations(state, operation.actor_id)
    assert effect.destination_index is not None
    if effect.destination_index >= len(eligible):
        raise ValueError("flee destination_index out of range for eligible set")
    destination_id = eligible[effect.destination_index]
    next_state = _mutate_flee(state, operation.actor_id, destination_id, rules=rules)
    prior = state.bodies[operation.actor_id]
    resulting = next_state.bodies[operation.actor_id]
    return RuleApplication(
        result=result,
        next_state=next_state,
        event_details=Fled(
            threat_id=operation.threat_id,
            success=True,
            destination_id=destination_id,
            fatigue_delta=round_physical(resulting.fatigue.value - prior.fatigue.value),
            resulting_fatigue=resulting.fatigue.value,
        ),
    )


def _event_details_for(
    state: WorldState,
    operation: ValidatedWorldOperation,
    *,
    rules: PhysicalRules,
    next_state: WorldState | None = None,
) -> EventDetails:
    match operation:
        case _MoveOp(actor_id=actor_id, destination_id=destination_id):
            resulting = next_state.bodies[actor_id] if next_state is not None else None
            prior = state.bodies[actor_id]
            fatigue_delta = (
                None
                if resulting is None
                else round_physical(resulting.fatigue.value - prior.fatigue.value)
            )
            return Moved(
                destination_id,
                resulting_location_id=(
                    None if resulting is None else resulting.location_id
                ),
                fatigue_delta=fatigue_delta,
                resulting_fatigue=(
                    None if resulting is None else resulting.fatigue.value
                ),
            )
        case _TakeOp(actor_id=actor_id, item_id=item_id):
            return Taken(item_id, resulting_holder_id=actor_id)
        case _DropOp(actor_id=actor_id, item_id=item_id):
            actor = state.bodies[actor_id]
            return Dropped(item_id, resulting_location_id=actor.location_id)
        case _GiveOp(recipient_id=recipient_id, item_id=item_id):
            return Given(recipient_id, item_id, resulting_holder_id=recipient_id)
        case _EatOp(actor_id=actor_id, item_id=item_id):
            prior = state.bodies[actor_id]
            resulting = next_state.bodies[actor_id] if next_state is not None else prior
            return Eaten(
                item_id,
                hunger_delta=round_physical(
                    resulting.hunger.value - prior.hunger.value
                ),
                resulting_hunger=resulting.hunger.value,
            )
        case _DrinkOp(actor_id=actor_id, source_id=source_id):
            prior = state.bodies[actor_id]
            resulting = next_state.bodies[actor_id] if next_state is not None else prior
            consumed_item = source_id in state.items
            quantity_delta = None
            resulting_resource_quantity = None
            if not consumed_item:
                quantity_delta = -rules.resource_extraction_amount
                if next_state is not None:
                    resulting_resource_quantity = next_state.resources[
                        source_id
                    ].quantity
            return Drunk(
                source_id,
                consumed_item=consumed_item,
                quantity_delta=quantity_delta,
                resulting_resource_quantity=resulting_resource_quantity,
                thirst_delta=round_physical(
                    resulting.thirst.value - prior.thirst.value
                ),
                resulting_thirst=resulting.thirst.value,
            )
        case _SleepOp(actor_id=actor_id):
            prior = state.bodies[actor_id]
            resulting = next_state.bodies[actor_id] if next_state is not None else prior
            return Slept(
                fatigue_delta=round_physical(
                    resulting.fatigue.value - prior.fatigue.value
                ),
                resulting_fatigue=resulting.fatigue.value,
            )
        case _HelpOp(actor_id=actor_id, target_id=target_id):
            prior_target = state.bodies[target_id]
            prior_helper = state.bodies[actor_id]
            resulting_target = (
                next_state.bodies[target_id] if next_state is not None else prior_target
            )
            resulting_helper = (
                next_state.bodies[actor_id] if next_state is not None else prior_helper
            )
            return Helped(
                target_id,
                health_delta=round_physical(
                    resulting_target.health.value - prior_target.health.value
                ),
                resulting_target_health=resulting_target.health.value,
                helper_fatigue_delta=round_physical(
                    resulting_helper.fatigue.value - prior_helper.fatigue.value
                ),
                resulting_helper_fatigue=resulting_helper.fatigue.value,
            )
        case _TalkOp(recipient_id=recipient_id, text=text):
            return Talked(recipient_id, text)
        case _AskOp(recipient_id=recipient_id, text=text):
            return Asked(recipient_id, text)
        case _TellOp(recipient_id=recipient_id, text=text):
            return Told(recipient_id, text)
        case _WaitOp():
            return Waited()
        case _:
            raise TypeError(f"no event details for {type(operation).__name__}")


def _apply_mutation(
    state: WorldState,
    operation: ValidatedWorldOperation,
    *,
    rules: PhysicalRules,
) -> WorldState:
    match operation:
        case _MoveOp(actor_id=actor_id, destination_id=destination_id):
            return _mutate_move(state, actor_id, destination_id, rules=rules)
        case _TakeOp(actor_id=actor_id, item_id=item_id):
            return _mutate_take(state, actor_id, item_id)
        case _DropOp(actor_id=actor_id, item_id=item_id):
            return _mutate_drop(state, actor_id, item_id)
        case _GiveOp(actor_id=actor_id, recipient_id=recipient_id, item_id=item_id):
            return _mutate_give(state, actor_id, recipient_id, item_id)
        case _EatOp(actor_id=actor_id, item_id=item_id):
            return _mutate_eat(state, actor_id, item_id, rules=rules)
        case _DrinkOp(actor_id=actor_id, source_id=source_id):
            return _mutate_drink(state, actor_id, source_id, rules=rules)
        case _SleepOp(actor_id=actor_id):
            return _mutate_sleep(state, actor_id, rules=rules)
        case _HelpOp(actor_id=actor_id, target_id=target_id):
            return _mutate_help(state, actor_id, target_id, rules=rules)
        case _:
            raise TypeError(f"mutation unsupported for {type(operation).__name__}")


def _mutate_move(
    state: WorldState,
    actor_id: EntityId,
    destination_id: EntityId,
    *,
    rules: PhysicalRules,
) -> WorldState:
    actor = state.bodies[actor_id]
    fatigue = Fatigue(
        clamp_need(round_physical(actor.fatigue.value + rules.move_fatigue))
    )
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(actor, location_id=destination_id, fatigue=fatigue)
    return rebuild_world_state(state, bodies=bodies)


def _mutate_take(
    state: WorldState, actor_id: EntityId, item_id: EntityId
) -> WorldState:
    actor = state.bodies[actor_id]
    item = state.items[item_id]
    items = dict(state.items)
    bodies = dict(state.bodies)
    items[item_id] = copy_item(item, location_id=None, holder_id=actor_id)
    bodies[actor_id] = copy_body(actor, inventory=(*actor.inventory, item_id))
    return rebuild_world_state(state, items=items, bodies=bodies)


def _mutate_drop(
    state: WorldState, actor_id: EntityId, item_id: EntityId
) -> WorldState:
    actor = state.bodies[actor_id]
    item = state.items[item_id]
    items = dict(state.items)
    bodies = dict(state.bodies)
    items[item_id] = copy_item(item, location_id=actor.location_id, holder_id=None)
    bodies[actor_id] = copy_body(
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
    items[item_id] = copy_item(item, location_id=None, holder_id=recipient_id)
    bodies[actor_id] = copy_body(
        actor,
        inventory=tuple(owned for owned in actor.inventory if owned != item_id),
    )
    bodies[recipient_id] = copy_body(
        recipient, inventory=(*recipient.inventory, item_id)
    )
    return rebuild_world_state(state, items=items, bodies=bodies)


def _mutate_eat(
    state: WorldState,
    actor_id: EntityId,
    item_id: EntityId,
    *,
    rules: PhysicalRules,
) -> WorldState:
    actor = state.bodies[actor_id]
    hunger = Hunger(
        clamp_need(round_physical(actor.hunger.value - rules.eat_hunger_relief))
    )
    items = dict(state.items)
    del items[item_id]
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(
        actor,
        hunger=hunger,
        inventory=tuple(owned for owned in actor.inventory if owned != item_id),
    )
    return rebuild_world_state(state, items=items, bodies=bodies)


def _mutate_drink(
    state: WorldState,
    actor_id: EntityId,
    source_id: EntityId,
    *,
    rules: PhysicalRules,
) -> WorldState:
    actor = state.bodies[actor_id]
    thirst = Thirst(
        clamp_need(round_physical(actor.thirst.value - rules.drink_thirst_relief))
    )
    bodies = dict(state.bodies)
    if source_id in state.items:
        items = dict(state.items)
        del items[source_id]
        bodies[actor_id] = copy_body(
            actor,
            thirst=thirst,
            inventory=tuple(owned for owned in actor.inventory if owned != source_id),
        )
        return rebuild_world_state(state, items=items, bodies=bodies)
    resource = state.resources[source_id]
    resulting_quantity = round_physical(
        resource.quantity - rules.resource_extraction_amount
    )
    resources = dict(state.resources)
    resources[source_id] = copy_resource(resource, quantity=resulting_quantity)
    bodies[actor_id] = copy_body(actor, thirst=thirst)
    return rebuild_world_state(state, bodies=bodies, resources=resources)


def _mutate_sleep(
    state: WorldState,
    actor_id: EntityId,
    *,
    rules: PhysicalRules,
) -> WorldState:
    actor = state.bodies[actor_id]
    fatigue = Fatigue(
        clamp_need(round_physical(actor.fatigue.value - rules.sleep_fatigue_recovery))
    )
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(actor, fatigue=fatigue)
    return rebuild_world_state(state, bodies=bodies)


def _mutate_help(
    state: WorldState,
    actor_id: EntityId,
    target_id: EntityId,
    *,
    rules: PhysicalRules,
) -> WorldState:
    actor = state.bodies[actor_id]
    target = state.bodies[target_id]
    health = Health(
        clamp_need(round_physical(target.health.value + rules.help_health_gain))
    )
    fatigue = Fatigue(
        clamp_need(round_physical(actor.fatigue.value + rules.help_fatigue))
    )
    bodies = dict(state.bodies)
    bodies[target_id] = copy_body(target, health=health)
    bodies[actor_id] = copy_body(actor, fatigue=fatigue)
    return rebuild_world_state(state, bodies=bodies)


def _mutate_flee(
    state: WorldState,
    actor_id: EntityId,
    destination_id: EntityId,
    *,
    rules: PhysicalRules,
) -> WorldState:
    actor = state.bodies[actor_id]
    fatigue = Fatigue(
        clamp_need(round_physical(actor.fatigue.value + rules.flee_fatigue))
    )
    bodies = dict(state.bodies)
    bodies[actor_id] = copy_body(actor, location_id=destination_id, fatigue=fatigue)
    return rebuild_world_state(state, bodies=bodies)


def _require_rules(rules: PhysicalRules | None) -> PhysicalRules:
    if rules is None:
        return default_physical_rules()
    if type(rules) is not PhysicalRules:
        raise TypeError("rules must be PhysicalRules")
    return rules


def _inventory_load(state: WorldState, body: AgentBody) -> int:
    return sum(state.items[item_id].load.value for item_id in body.inventory)


def _ground_item_count(state: WorldState, location_id: EntityId) -> int:
    return sum(1 for item in state.items.values() if item.location_id == location_id)


def _body_count(state: WorldState, location_id: EntityId) -> int:
    return sum(1 for body in state.bodies.values() if body.location_id == location_id)
