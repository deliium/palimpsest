"""V1 rule interfaces and complete command outcome matrix."""

from __future__ import annotations

import pytest

from world._operations import (
    OperationAccepted,
    RejectionCode,
    validate_action_request,
)
from world._rules import (
    COMMAND_RULE_MATRIX,
    RuleDisposition,
    RuleReason,
    evaluate_operation,
)
from world._state import WorldState
from world.actions import (
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
)
from world.identifiers import (
    EntityId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import AgentBody, Item, LifeStatus, Location, Resource
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

_ALL_COMMAND_CASES = [
    ("move", Move(EntityId("loc-2")), RuleDisposition.DEFERRED),
    ("search", Search(), RuleDisposition.EVENT_ONLY),
    ("take", Take(EntityId("item-ground")), RuleDisposition.MUTATE),
    ("drop", Drop(EntityId("item-held")), RuleDisposition.MUTATE),
    ("give", Give(EntityId("body-2"), EntityId("item-held")), RuleDisposition.MUTATE),
    ("eat", Eat(EntityId("item-ground")), RuleDisposition.DEFERRED),
    ("drink", Drink(EntityId("res-1")), RuleDisposition.DEFERRED),
    ("sleep", Sleep(), RuleDisposition.DEFERRED),
    ("talk", Talk(EntityId("body-2"), "hi"), RuleDisposition.EVENT_ONLY),
    ("ask", Ask(EntityId("body-2"), "why"), RuleDisposition.EVENT_ONLY),
    ("tell", Tell(EntityId("body-2"), "news"), RuleDisposition.EVENT_ONLY),
    ("help", Help(EntityId("body-2")), RuleDisposition.DEFERRED),
    ("attack", Attack(EntityId("body-2")), RuleDisposition.DEFERRED),
    ("flee", Flee(), RuleDisposition.DEFERRED),
    ("wait", Wait(), RuleDisposition.EVENT_ONLY),
]


def _alive(
    entity_id: str,
    location_id: str,
    inventory: tuple[EntityId, ...] = (),
) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(50),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=inventory,
        life_status=LifeStatus.ALIVE,
    )


def _dead(entity_id: str, location_id: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(0),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(20),
        inventory=(),
        life_status=LifeStatus.DEAD,
    )


def _state(*, include_held: bool = True) -> WorldState:
    held = (
        Item(
            entity_id=EntityId("item-held"),
            name="Cup",
            holder_id=EntityId("body-1"),
        ),
    )
    inventory = (EntityId("item-held"),) if include_held else ()
    items = (
        Item(
            entity_id=EntityId("item-ground"),
            name="Rock",
            location_id=EntityId("loc-1"),
        ),
        *held,
    )
    return WorldState(
        WorldRevision(1),
        locations=(
            Location(entity_id=EntityId("loc-1"), name="Camp"),
            Location(entity_id=EntityId("loc-2"), name="Forest"),
        ),
        items=items,
        resources=(
            Resource(
                entity_id=EntityId("res-1"),
                name="Water",
                location_id=EntityId("loc-1"),
                quantity=1.0,
                unit="L",
            ),
        ),
        bodies=(
            _alive("body-1", "loc-1", inventory=inventory),
            _alive("body-2", "loc-1"),
            _alive("body-far", "loc-2"),
            _dead("body-dead", "loc-1"),
        ),
    )


def _accept(command: object, *, actor: str = "body-1") -> object:
    from world.actions import ActionRequest

    state = _state()
    outcome = validate_action_request(
        world_id=WorldId("world-1"),
        state=state,
        request=ActionRequest(
            request_id=RequestId("r-1"),
            proposal_id=ProposalId("p-1"),
            world_id=WorldId("world-1"),
            actor_id=EntityId(actor),
            revision=WorldRevision(1),
            command=command,
        ),
    )
    assert isinstance(outcome, OperationAccepted)
    return outcome.operation


def test_matrix_covers_all_fifteen_operation_types() -> None:
    assert len(COMMAND_RULE_MATRIX) == 15
    kinds = {policy.disposition for policy in COMMAND_RULE_MATRIX.values()}
    assert RuleDisposition.MUTATE in kinds
    assert RuleDisposition.EVENT_ONLY in kinds
    assert RuleDisposition.DEFERRED in kinds


@pytest.mark.parametrize(("kind", "command", "expected"), _ALL_COMMAND_CASES)
def test_living_actor_matrix_dispositions(
    kind: str, command: object, expected: RuleDisposition
) -> None:
    state = _state()
    operation = _accept(command)
    result = evaluate_operation(state, operation)
    assert result.action_kind == kind
    assert result.disposition is expected
    policy = COMMAND_RULE_MATRIX[type(operation)]
    if expected is RuleDisposition.DEFERRED:
        assert result.emits_event is False
        assert result.mutates_state is False
        assert result.reason is RuleReason.DEFERRED_POLICY
    elif expected is RuleDisposition.EVENT_ONLY:
        assert result.emits_event is True
        assert result.mutates_state is False
        assert result.reason is RuleReason.OCCURRENCE
    else:
        assert result.emits_event is policy.emits_event_when_applied
        assert result.mutates_state is policy.mutates_state_when_applied


@pytest.mark.parametrize(("kind", "command", "_expected"), _ALL_COMMAND_CASES)
def test_dead_actor_rejected_before_command_specific_behavior(
    kind: str, command: object, _expected: RuleDisposition
) -> None:
    from world._operations import OperationRejected
    from world.actions import ActionRequest

    del kind, _expected
    state = _state()
    outcome = validate_action_request(
        world_id=WorldId("world-1"),
        state=state,
        request=ActionRequest(
            request_id=RequestId("r-dead"),
            proposal_id=ProposalId("p-dead"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-dead"),
            revision=WorldRevision(1),
            command=command,
        ),
    )
    assert isinstance(outcome, OperationRejected)
    assert outcome.code is RejectionCode.DEAD_ACTOR


def test_take_drop_give_placement_ownership_and_colocation() -> None:
    state = _state()
    take_ok = evaluate_operation(state, _accept(Take(EntityId("item-ground"))))
    assert take_ok.disposition is RuleDisposition.MUTATE

    drop_ok = evaluate_operation(state, _accept(Drop(EntityId("item-held"))))
    assert drop_ok.disposition is RuleDisposition.MUTATE

    give_ok = evaluate_operation(
        state, _accept(Give(EntityId("body-2"), EntityId("item-held")))
    )
    assert give_ok.disposition is RuleDisposition.MUTATE

    not_held = evaluate_operation(state, _accept(Drop(EntityId("item-ground"))))
    assert not_held.disposition is RuleDisposition.REJECT
    assert not_held.reason is RuleReason.NOT_HELD

    far = evaluate_operation(
        state, _accept(Give(EntityId("body-far"), EntityId("item-held")))
    )
    assert far.disposition is RuleDisposition.REJECT
    assert far.reason is RuleReason.NOT_COLOCATED

    dead_target = evaluate_operation(
        state, _accept(Give(EntityId("body-dead"), EntityId("item-held")))
    )
    assert dead_target.disposition is RuleDisposition.REJECT
    assert dead_target.reason is RuleReason.DEAD_TARGET


def test_event_only_and_deferred_never_claim_mutation() -> None:
    state = _state()
    wait = evaluate_operation(state, _accept(Wait()))
    assert wait.emits_event is True
    assert wait.mutates_state is False
    move = evaluate_operation(state, _accept(Move(EntityId("loc-2"))))
    assert move.disposition is RuleDisposition.DEFERRED
    assert move.emits_event is False
    assert move.mutates_state is False


def test_apply_take_drop_give_mutate_inventories_deterministically() -> None:
    from world._rules import apply_operation
    from world.actions import ActionRequest
    from world.events import Dropped, Given, Taken

    state = _state()
    taken = apply_operation(state, _accept(Take(EntityId("item-ground"))))
    assert taken.result.disposition is RuleDisposition.MUTATE
    assert taken.event_details == Taken(EntityId("item-ground"))
    assert EntityId("item-ground") in taken.next_state.bodies[
        EntityId("body-1")
    ].inventory
    assert taken.next_state.items[EntityId("item-ground")].holder_id == EntityId(
        "body-1"
    )
    assert taken.next_state.revision == state.revision

    working = taken.next_state
    drop_outcome = validate_action_request(
        world_id=WorldId("world-1"),
        state=working,
        request=ActionRequest(
            request_id=RequestId("r-drop"),
            proposal_id=ProposalId("p-drop"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-1"),
            revision=working.revision,
            command=Drop(EntityId("item-held")),
        ),
    )
    assert isinstance(drop_outcome, OperationAccepted)
    dropped = apply_operation(working, drop_outcome.operation)
    assert dropped.event_details == Dropped(EntityId("item-held"))
    assert EntityId("item-held") not in dropped.next_state.bodies[
        EntityId("body-1")
    ].inventory
    assert dropped.next_state.items[EntityId("item-held")].location_id == EntityId(
        "loc-1"
    )

    given = apply_operation(
        _state(), _accept(Give(EntityId("body-2"), EntityId("item-held")))
    )
    assert given.event_details == Given(EntityId("body-2"), EntityId("item-held"))
    assert EntityId("item-held") not in given.next_state.bodies[
        EntityId("body-1")
    ].inventory
    assert given.next_state.bodies[EntityId("body-2")].inventory == (
        EntityId("item-held"),
    )
    assert given.next_state.items[EntityId("item-held")].holder_id == EntityId(
        "body-2"
    )


def test_deferred_apply_produces_no_event_or_mutation() -> None:
    from world._rules import apply_operation

    state = _state()
    applied = apply_operation(state, _accept(Move(EntityId("loc-2"))))
    assert applied.result.disposition is RuleDisposition.DEFERRED
    assert applied.event_details is None
    assert applied.next_state is state


def test_world_apply_take_commits_mutated_state_and_bumps_revision() -> None:
    from world._state import World
    from world.actions import ActionRequest, Take
    from world.events import Taken
    from world.identifiers import EventId

    state = _state()
    world = World(WorldId("world-1"), state)
    result = world.apply_admitted_request(
        ActionRequest(
            request_id=RequestId("r-take"),
            proposal_id=ProposalId("p-take"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-1"),
            revision=WorldRevision(1),
            command=Take(EntityId("item-ground")),
        ),
        event_ids=(EventId("evt-take"),),
    )
    from world._transitions import TransitionResult
    from world.actions import TransitionOutcome

    assert isinstance(result, TransitionResult)
    assert result.outcome is TransitionOutcome.APPLIED
    assert result.events[0].details == Taken(EntityId("item-ground"))
    assert result.resulting_revision == WorldRevision(2)
    assert world.state.revision == WorldRevision(2)
    assert EntityId("item-ground") in world.state.bodies[EntityId("body-1")].inventory


def test_world_apply_deferred_move_does_not_emit_or_mutate() -> None:
    from world._state import World
    from world._transitions import TransitionResult
    from world.actions import ActionRequest, TransitionOutcome
    from world.identifiers import EventId

    state = _state()
    world = World(WorldId("world-1"), state)
    result = world.apply_admitted_request(
        ActionRequest(
            request_id=RequestId("r-move"),
            proposal_id=ProposalId("p-move"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-1"),
            revision=WorldRevision(1),
            command=Move(EntityId("loc-2")),
        ),
        event_ids=(EventId("evt-move"),),
    )
    assert isinstance(result, TransitionResult)
    assert result.outcome is TransitionOutcome.NOT_APPLIED
    assert result.events == ()
    assert world.state is state
