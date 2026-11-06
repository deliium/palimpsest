# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from dataclasses import dataclass, field

from agents.cognition.organized_conflict import (
    ConflictLedger,
    ConflictOperation,
    ConflictPlan,
    ConflictPlanStatus,
    ConflictProvenance,
    ConflictRole,
    ConflictTargetKind,
    conflict_plan_id,
    conflict_target_token,
    default_organized_conflict_policy,
)
from agents.cognition.organized_conflict_actions import (
    organized_conflict_wait_replacement,
)
from agents.models import AgentId
from world import EntityId
from world.actions import (
    Attack,
    Feed,
    Flee,
    Give,
    Help,
    Move,
    OpposePublicGood,
    Take,
    Tell,
    Wait,
)

OWNER = AgentId("agent-owner")
OWNER_REF = conflict_target_token(OWNER.value)
TARGET_REF = conflict_target_token("body-enemy")


@dataclass
class _Body:
    entity_id: EntityId
    coarse_health: str = "stable"
    dependency_needs: object | None = None


@dataclass
class _Item:
    entity_id: EntityId
    placement: str


@dataclass
class _Project:
    project_id: EntityId
    status: str
    public_acts: tuple[object, ...] = ()
    kind: str = "public_good"


@dataclass
class _Occurrence:
    kind: str
    actor_id: EntityId | None
    other_entity_id: EntityId | None


@dataclass
class _Exit:
    destination_id: EntityId
    name: str = "east"


@dataclass
class _Observation:
    tick: int
    observer_id: EntityId = field(default_factory=lambda: EntityId("body-owner"))
    visible_bodies: tuple[_Body, ...] = ()
    items: tuple[_Item, ...] = ()
    structures: tuple[object, ...] = ()
    collective_projects: tuple[_Project, ...] = ()
    exits: tuple[_Exit, ...] = ()
    occurrences: tuple[_Occurrence, ...] = ()
    locations: tuple[object, ...] = ()
    resources: tuple[object, ...] = ()
    communications: tuple[object, ...] = ()
    self_body: object | None = None


def _plan(
    operation: ConflictOperation,
    *,
    target_kind: ConflictTargetKind = ConflictTargetKind.AGENT,
    target_ref: str = TARGET_REF,
    role: ConflictRole = ConflictRole.ATTACKER,
    status: ConflictPlanStatus = ConflictPlanStatus.ACTIVE,
    provenance: ConflictProvenance = ConflictProvenance.SELF_DECLARED,
    start_tick: int = 1,
    last_tick: int = 1,
    participants: tuple[str, ...] = (OWNER_REF,),
) -> ConflictPlan:
    return ConflictPlan(
        plan_id=conflict_plan_id(
            OWNER, operation, target_kind, target_ref, start_tick, participants
        ),
        operation=operation,
        target_kind=target_kind,
        target_ref=target_ref,
        role=role,
        side_ref=OWNER_REF,
        participant_refs=participants,
        start_tick=start_tick,
        status=status,
        provenance=provenance,
        last_tick=last_tick,
    )


def _ledger(*plans: ConflictPlan) -> ConflictLedger:
    return ConflictLedger(
        owner_id=OWNER,
        tick=2,
        plans=tuple(sorted(plans, key=lambda row: row.plan_id)),
    )


def _replace(command: object, ledger: object, observation: object):
    return organized_conflict_wait_replacement(
        command,  # type: ignore[arg-type]
        owner_id=OWNER,
        tick=10,
        observation=observation,
        identity=None,
        ledger=ledger,
        policy=default_organized_conflict_policy(),
    )


def test_non_wait_command_is_never_replaced() -> None:
    attack = Attack(target_id=EntityId("body-enemy"))
    replacement, audits = _replace(
        attack,
        _ledger(_plan(ConflictOperation.COORDINATED_ATTACK)),
        _Observation(tick=10),
    )
    assert replacement is attack
    assert audits is None


def test_coordinated_attack_returns_attack() -> None:
    observation = _Observation(
        tick=10, visible_bodies=(_Body(entity_id=EntityId("body-enemy")),)
    )
    replacement, audits = _replace(
        Wait(), _ledger(_plan(ConflictOperation.COORDINATED_ATTACK)), observation
    )
    assert isinstance(replacement, Attack)
    assert replacement.target_id == EntityId("body-enemy")
    assert audits is not None and len(audits) == 1


def test_defense_prefers_help_then_attack_then_move() -> None:
    plan = _plan(ConflictOperation.DEFENSE)
    hurt = _Observation(
        tick=10,
        visible_bodies=(_Body(EntityId("body-ally"), coarse_health="injured"),),
    )
    replacement, _ = _replace(Wait(), _ledger(plan), hurt)
    assert isinstance(replacement, Help)

    threatened = _Observation(
        tick=10,
        visible_bodies=(_Body(EntityId("body-enemy")),),
        occurrences=(
            _Occurrence("attack", EntityId("body-enemy"), EntityId("body-owner")),
        ),
    )
    replacement, _ = _replace(Wait(), _ledger(plan), threatened)
    assert isinstance(replacement, Attack)

    move = _Observation(tick=10, exits=(_Exit(EntityId("place-east")),))
    replacement, _ = _replace(
        Wait(),
        _ledger(
            _plan(
                ConflictOperation.DEFENSE,
                target_ref=conflict_target_token("place-east"),
            )
        ),
        move,
    )
    assert isinstance(replacement, Move)


def test_movement_group_and_route_blocking_return_move() -> None:
    destination = EntityId("place-east")
    observation = _Observation(tick=10, exits=(_Exit(destination),))
    replacement, _ = _replace(
        Wait(),
        _ledger(
            _plan(
                ConflictOperation.MOVEMENT_GROUP,
                target_kind=ConflictTargetKind.LOCATION,
                target_ref=conflict_target_token(destination.value),
            )
        ),
        observation,
    )
    assert isinstance(replacement, Move) and replacement.destination_id == destination
    replacement, _ = _replace(
        Wait(), _ledger(_plan(ConflictOperation.ROUTE_BLOCKING)), observation
    )
    assert isinstance(replacement, Move) and replacement.destination_id == destination


def test_route_blocking_flees_when_the_owner_is_in_danger() -> None:
    observation = _Observation(
        tick=10,
        self_body=_Body(EntityId("body-owner"), coarse_health="critical"),
        occurrences=(
            _Occurrence("attack", EntityId("body-enemy"), EntityId("body-owner")),
        ),
    )
    replacement, _ = _replace(
        Wait(), _ledger(_plan(ConflictOperation.ROUTE_BLOCKING)), observation
    )
    assert isinstance(replacement, Flee)


def test_resource_capture_never_seizes_from_living_holder() -> None:
    plan = _plan(
        ConflictOperation.RESOURCE_CAPTURE,
        target_kind=ConflictTargetKind.RESOURCE,
        target_ref=conflict_target_token("food"),
    )
    ground = _Observation(tick=10, items=(_Item(EntityId("food"), "ground_here"),))
    replacement, _ = _replace(Wait(), _ledger(plan), ground)
    assert isinstance(replacement, Take)

    held = _Observation(
        tick=10,
        items=(_Item(EntityId("food"), "held_by_self"),),
        visible_bodies=(_Body(EntityId("body-ally")),),
    )
    replacement, _ = _replace(Wait(), _ledger(plan), held)
    assert isinstance(replacement, Give)
    assert replacement.item_id == EntityId("food")


def test_structure_attack_requires_completed_public_good() -> None:
    plan = _plan(
        ConflictOperation.STRUCTURE_ATTACK,
        target_kind=ConflictTargetKind.STRUCTURE,
        target_ref=conflict_target_token("store"),
    )
    open_project = _Observation(
        tick=10,
        collective_projects=(_Project(EntityId("store"), "open"),),
    )
    replacement, _ = _replace(Wait(), _ledger(plan), open_project)
    assert replacement.__class__ is Wait

    completed = _Observation(
        tick=10,
        collective_projects=(
            _Project(EntityId("store"), "completed", public_acts=(object(),)),
        ),
    )
    replacement, _ = _replace(Wait(), _ledger(plan), completed)
    assert isinstance(replacement, OpposePublicGood)


def test_retreat_returns_flee_and_assistance_returns_help() -> None:
    threat = _Observation(
        tick=10,
        visible_bodies=(_Body(EntityId("body-enemy")),),
        occurrences=(_Occurrence("attack", EntityId("body-enemy"), None),),
    )
    replacement, _ = _replace(Wait(), _ledger(_plan(ConflictOperation.RETREAT)), threat)
    assert isinstance(replacement, Flee)
    assert replacement.threat_id == EntityId("body-enemy")

    ally = _Observation(tick=10, visible_bodies=(_Body(EntityId("body-ally")),))
    replacement, _ = _replace(
        Wait(),
        _ledger(
            _plan(
                ConflictOperation.ASSISTANCE,
                role=ConflictRole.ASSISTANT,
                target_ref=conflict_target_token("body-ally"),
            )
        ),
        ally,
    )
    assert isinstance(replacement, Help)


def test_assistance_can_feed_dependent() -> None:
    dependent = _Body(EntityId("body-child"), dependency_needs=object())
    observation = _Observation(
        tick=10,
        visible_bodies=(dependent,),
        items=(_Item(EntityId("food"), "held_by_self"),),
    )
    replacement, _ = _replace(
        Wait(),
        _ledger(
            _plan(
                ConflictOperation.ASSISTANCE,
                role=ConflictRole.ASSISTANT,
                target_ref=conflict_target_token("body-child"),
            )
        ),
        observation,
    )
    assert isinstance(replacement, Feed)


def test_plan_coordination_uses_tell_with_ocf_v1() -> None:
    participant = conflict_target_token("body-ally")
    observation = _Observation(tick=10, visible_bodies=(_Body(EntityId("body-ally")),))
    plan = _plan(
        ConflictOperation.COORDINATED_ATTACK,
        status=ConflictPlanStatus.PROPOSED,
        provenance=ConflictProvenance.COMMUNICATED,
        start_tick=10,
        last_tick=10,
        participants=(OWNER_REF, participant),
    )
    replacement, audits = _replace(Wait(), _ledger(plan), observation)
    assert isinstance(replacement, Tell)
    assert any(
        relation.subject == "ocf_v1"
        for relation in replacement.utterance.content.relations
    )
    assert audits is not None


def test_plan_order_is_deterministic_and_one_audit() -> None:
    observation = _Observation(tick=10, visible_bodies=(_Body(EntityId("body-enemy")),))
    first = _plan(ConflictOperation.COORDINATED_ATTACK, start_tick=1)
    second = _plan(
        ConflictOperation.RETREAT,
        start_tick=2,
        target_ref=conflict_target_token("body-other"),
    )
    _replacement, audits = _replace(Wait(), _ledger(second, first), observation)
    assert audits is not None and len(audits) == 1
    assert audits[0].plan_id == min(first.plan_id, second.plan_id) or audits[
        0
    ].operation in {ConflictOperation.COORDINATED_ATTACK, ConflictOperation.RETREAT}
