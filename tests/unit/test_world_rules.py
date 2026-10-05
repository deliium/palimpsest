"""V1 rule interfaces and complete command outcome matrix."""

from __future__ import annotations

from world.communications import origin_utterance

import pytest

from tests.simulation_helpers import (
    connected_locations,
    make_item,
    make_resource,
    weather_for_locations,
)
from world._operations import (
    OperationAccepted,
    RejectionCode,
    ValidatedWorldOperation,
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
from world.models import AgentBody, LifeStatus
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    TemperatureCelsius,
    Thirst,
)

_ALL_COMMAND_CASES = [
    ("move", Move(EntityId("loc-2")), RuleDisposition.MUTATE),
    ("search", Search(), RuleDisposition.MUTATE),
    ("take", Take(EntityId("item-ground")), RuleDisposition.MUTATE),
    ("drop", Drop(EntityId("item-held")), RuleDisposition.MUTATE),
    ("give", Give(EntityId("body-2"), EntityId("item-held")), RuleDisposition.MUTATE),
    ("eat", Eat(EntityId("item-food")), RuleDisposition.MUTATE),
    ("drink", Drink(EntityId("res-1")), RuleDisposition.MUTATE),
    ("sleep", Sleep(), RuleDisposition.MUTATE),
    (
        "talk",
        Talk(
            EntityId("body-2"),
            origin_utterance(text="hi", speaker_id=EntityId("body-1")),
        ),
        RuleDisposition.EVENT_ONLY,
    ),
    (
        "ask",
        Ask(
            EntityId("body-2"),
            origin_utterance(text="why", speaker_id=EntityId("body-1")),
        ),
        RuleDisposition.EVENT_ONLY,
    ),
    (
        "tell",
        Tell(
            EntityId("body-2"),
            origin_utterance(text="news", speaker_id=EntityId("body-1")),
        ),
        RuleDisposition.EVENT_ONLY,
    ),
    ("help", Help(EntityId("body-2")), RuleDisposition.MUTATE),
    ("attack", Attack(EntityId("body-2")), RuleDisposition.MUTATE),
    ("flee", Flee(), RuleDisposition.MUTATE),
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
        carry_capacity=CarryCapacity(10),
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
        carry_capacity=CarryCapacity(10),
    )


def _state(*, include_held: bool = True) -> WorldState:
    held = (
        make_item("item-held", name="Cup", location_id=None, holder_id="body-1"),
        make_item(
            "item-food",
            name="Bread",
            kind=ItemKind.FOOD,
            location_id=None,
            holder_id="body-1",
        ),
        make_item(
            "item-water",
            name="Flask",
            kind=ItemKind.WATER,
            location_id=None,
            holder_id="body-1",
        ),
    )
    inventory = (
        (EntityId("item-held"), EntityId("item-food"), EntityId("item-water"))
        if include_held
        else ()
    )
    items = (
        make_item("item-ground", name="Rock", location_id="loc-1"),
        *(held if include_held else ()),
    )
    return WorldState(
        WorldRevision(1),
        locations=connected_locations(("loc-1", "Camp"), ("loc-2", "Forest")),
        items=items,
        resources=(
            make_resource(
                "res-1",
                name="Water",
                location_id="loc-1",
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
        weather=weather_for_locations(
            connected_locations(("loc-1", "Camp"), ("loc-2", "Forest"))
        ),
    )


def _accept(command: object, *, actor: str = "body-1") -> ValidatedWorldOperation:
    from world.actions import ActionRequest, require_agent_command

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
            command=require_agent_command(command),
        ),
    )
    assert isinstance(outcome, OperationAccepted)
    operation: ValidatedWorldOperation = outcome.operation
    return operation


def test_matrix_covers_all_twenty_four_operation_types() -> None:
    assert len(COMMAND_RULE_MATRIX) == 26
    kinds = {policy.disposition for policy in COMMAND_RULE_MATRIX.values()}
    assert RuleDisposition.MUTATE in kinds
    assert RuleDisposition.EVENT_ONLY in kinds
    assert RuleDisposition.DEFERRED not in kinds


@pytest.mark.parametrize(("kind", "command", "expected"), _ALL_COMMAND_CASES)
def test_living_actor_matrix_dispositions(
    kind: str, command: object, expected: RuleDisposition
) -> None:
    from world.effects import (
        ResolvedActionEffects,
        ResolvedAttackEffect,
        ResolvedFleeEffect,
        ResolvedSearchEffect,
    )

    state = _state()
    operation = _accept(command)
    resolved = None
    if kind == "search":
        resolved = ResolvedActionEffects(
            {
                RequestId("r-1"): ResolvedSearchEffect(
                    request_id=RequestId("r-1"),
                    success=True,
                    resource_id=EntityId("res-1"),
                    created_item_id=EntityId("item-foraged"),
                )
            }
        )
    elif kind == "attack":
        resolved = ResolvedActionEffects(
            {
                RequestId("r-1"): ResolvedAttackEffect(
                    request_id=RequestId("r-1"),
                    hit=True,
                    damage=10,
                )
            }
        )
    elif kind == "flee":
        resolved = ResolvedActionEffects(
            {
                RequestId("r-1"): ResolvedFleeEffect(
                    request_id=RequestId("r-1"),
                    success=True,
                    destination_index=0,
                )
            }
        )
    result = evaluate_operation(state, operation, resolved=resolved)
    assert result.action_kind == kind
    assert result.disposition is expected
    policy = COMMAND_RULE_MATRIX[type(operation)]
    if expected is RuleDisposition.EVENT_ONLY:
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
    from world.actions import ActionRequest, require_agent_command

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
            command=require_agent_command(command),
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


def test_event_only_actions_never_claim_mutation() -> None:
    state = _state()
    wait = evaluate_operation(state, _accept(Wait()))
    assert wait.emits_event is True
    assert wait.mutates_state is False
    sleep = evaluate_operation(state, _accept(Sleep()))
    assert sleep.disposition is RuleDisposition.MUTATE
    assert sleep.emits_event is True
    assert sleep.mutates_state is True
    move = evaluate_operation(state, _accept(Move(EntityId("loc-2"))))
    assert move.disposition is RuleDisposition.MUTATE
    assert move.emits_event is True
    assert move.mutates_state is True


def test_apply_take_drop_give_mutate_inventories_deterministically() -> None:
    from world._rules import apply_operation
    from world.actions import ActionRequest
    from world.events import Dropped, Given, Taken

    state = _state()
    taken = apply_operation(state, _accept(Take(EntityId("item-ground"))))
    assert taken.result.disposition is RuleDisposition.MUTATE
    assert taken.event_details == Taken(
        EntityId("item-ground"), resulting_holder_id=EntityId("body-1")
    )
    assert (
        EntityId("item-ground") in taken.next_state.bodies[EntityId("body-1")].inventory
    )
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
    assert dropped.event_details == Dropped(
        EntityId("item-held"), resulting_location_id=EntityId("loc-1")
    )
    assert (
        EntityId("item-held")
        not in dropped.next_state.bodies[EntityId("body-1")].inventory
    )
    assert dropped.next_state.items[EntityId("item-held")].location_id == EntityId(
        "loc-1"
    )

    given = apply_operation(
        _state(), _accept(Give(EntityId("body-2"), EntityId("item-held")))
    )
    assert given.event_details == Given(
        EntityId("body-2"),
        EntityId("item-held"),
        resulting_holder_id=EntityId("body-2"),
    )
    assert (
        EntityId("item-held")
        not in given.next_state.bodies[EntityId("body-1")].inventory
    )
    assert given.next_state.bodies[EntityId("body-2")].inventory == (
        EntityId("item-held"),
    )
    assert given.next_state.items[EntityId("item-held")].holder_id == EntityId("body-2")


def test_sleep_help_attack_flee_and_terminal_death() -> None:
    from world._rules import apply_operation
    from world.effects import (
        DeathCause,
        ResolvedActionEffects,
        ResolvedAttackEffect,
        ResolvedFleeEffect,
    )
    from world.events import Attacked, Died, Fled, Helped, Slept

    fatigued = _state()
    bodies = dict(fatigued.bodies)
    actor = bodies[EntityId("body-1")]
    bodies[EntityId("body-1")] = AgentBody(
        entity_id=actor.entity_id,
        location_id=actor.location_id,
        health=actor.health,
        hunger=actor.hunger,
        thirst=actor.thirst,
        fatigue=Fatigue(40),
        temperature=actor.temperature,
        inventory=actor.inventory,
        life_status=actor.life_status,
        carry_capacity=actor.carry_capacity,
    )
    state = WorldState(
        WorldRevision(1),
        locations=tuple(fatigued.locations.values()),
        items=tuple(fatigued.items.values()),
        resources=tuple(fatigued.resources.values()),
        bodies=tuple(bodies.values()),
        weather=tuple(fatigued.weather.values()),
    )
    slept = apply_operation(state, _accept(Sleep()))
    assert slept.result.disposition is RuleDisposition.MUTATE
    assert slept.event_details == Slept(fatigue_delta=-30.0, resulting_fatigue=10.0)
    assert slept.next_state.bodies[EntityId("body-1")].fatigue.value == 10.0

    zero = apply_operation(_state(), _accept(Sleep()))
    assert zero.event_details == Slept(fatigue_delta=0.0, resulting_fatigue=0.0)

    helped = apply_operation(_state(), _accept(Help(EntityId("body-2"))))
    assert helped.result.disposition is RuleDisposition.MUTATE
    assert isinstance(helped.event_details, Helped)
    assert helped.next_state.bodies[EntityId("body-2")].health.value == 60.0
    assert helped.next_state.bodies[EntityId("body-1")].fatigue.value == 5.0

    dead_help = apply_operation(_state(), _accept(Help(EntityId("body-dead"))))
    assert dead_help.result.disposition is RuleDisposition.REJECT
    assert dead_help.result.reason is RuleReason.DEAD_TARGET

    miss = apply_operation(
        _state(),
        _accept(Attack(EntityId("body-2"))),
        resolved=ResolvedActionEffects(
            {
                RequestId("r-1"): ResolvedAttackEffect(
                    request_id=RequestId("r-1"), hit=False
                )
            }
        ),
    )
    assert miss.result.disposition is RuleDisposition.EVENT_ONLY
    assert miss.event_details == Attacked(EntityId("body-2"), hit=False)
    assert miss.extra_event_details == ()

    lethal = apply_operation(
        _state(),
        _accept(Attack(EntityId("body-2"))),
        resolved=ResolvedActionEffects(
            {
                RequestId("r-1"): ResolvedAttackEffect(
                    request_id=RequestId("r-1"), hit=True, damage=50
                )
            }
        ),
    )
    assert lethal.result.disposition is RuleDisposition.MUTATE
    assert lethal.event_details == Attacked(
        EntityId("body-2"),
        hit=True,
        damage=50,
        resulting_target_health=0.0,
    )
    assert lethal.extra_event_details == (Died(EntityId("body-2"), DeathCause.ATTACK),)
    assert lethal.all_event_details() == (
        lethal.event_details,
        *lethal.extra_event_details,
    )
    dead_body = lethal.next_state.bodies[EntityId("body-2")]
    assert dead_body.life_status is LifeStatus.DEAD
    assert dead_body.health.value == 0.0

    from world.actions import ActionRequest, require_agent_command

    help_dead = validate_action_request(
        world_id=WorldId("world-1"),
        state=lethal.next_state,
        request=ActionRequest(
            request_id=RequestId("r-help-dead"),
            proposal_id=ProposalId("p-help-dead"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-1"),
            revision=lethal.next_state.revision,
            command=require_agent_command(Help(EntityId("body-2"))),
        ),
    )
    assert isinstance(help_dead, OperationAccepted)
    revive = apply_operation(lethal.next_state, help_dead.operation)
    assert revive.result.reason is RuleReason.DEAD_TARGET

    attack_dead = validate_action_request(
        world_id=WorldId("world-1"),
        state=lethal.next_state,
        request=ActionRequest(
            request_id=RequestId("r-attack-dead"),
            proposal_id=ProposalId("p-attack-dead"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-1"),
            revision=lethal.next_state.revision,
            command=require_agent_command(Attack(EntityId("body-2"))),
        ),
    )
    assert isinstance(attack_dead, OperationAccepted)
    reattack = apply_operation(
        lethal.next_state,
        attack_dead.operation,
        resolved=ResolvedActionEffects(
            {
                RequestId("r-attack-dead"): ResolvedAttackEffect(
                    request_id=RequestId("r-attack-dead"),
                    hit=True,
                    damage=10,
                )
            }
        ),
    )
    assert reattack.result.reason is RuleReason.DEAD_TARGET

    fled_fail = apply_operation(
        _state(),
        _accept(Flee(EntityId("body-2"))),
        resolved=ResolvedActionEffects(
            {
                RequestId("r-1"): ResolvedFleeEffect(
                    request_id=RequestId("r-1"), success=False
                )
            }
        ),
    )
    assert fled_fail.result.disposition is RuleDisposition.EVENT_ONLY
    assert fled_fail.event_details == Fled(threat_id=EntityId("body-2"), success=False)

    fled_ok = apply_operation(
        _state(),
        _accept(Flee()),
        resolved=ResolvedActionEffects(
            {
                RequestId("r-1"): ResolvedFleeEffect(
                    request_id=RequestId("r-1"),
                    success=True,
                    destination_index=0,
                )
            }
        ),
    )
    assert fled_ok.result.disposition is RuleDisposition.MUTATE
    assert isinstance(fled_ok.event_details, Fled)
    assert fled_ok.event_details.success is True
    assert fled_ok.event_details.destination_id == EntityId("loc-2")
    assert fled_ok.next_state.bodies[EntityId("body-1")].location_id == EntityId(
        "loc-2"
    )
    assert fled_ok.next_state.bodies[EntityId("body-1")].fatigue.value == 10.0


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
        run_id="run-1",
        tick=0,
    )
    from world._transitions import TransitionResult
    from world.actions import TransitionOutcome

    assert isinstance(result, TransitionResult)
    assert result.outcome is TransitionOutcome.APPLIED
    assert result.events[0].details == Taken(
        EntityId("item-ground"), resulting_holder_id=EntityId("body-1")
    )
    assert result.resulting_revision == WorldRevision(2)
    assert world.state.revision == WorldRevision(2)
    assert EntityId("item-ground") in world.state.bodies[EntityId("body-1")].inventory


def test_world_apply_move_emits_and_mutates() -> None:
    from world._state import World
    from world._transitions import TransitionResult
    from world.actions import ActionRequest, TransitionOutcome
    from world.events import Moved
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
        run_id="run-1",
        tick=0,
    )
    assert isinstance(result, TransitionResult)
    assert result.outcome is TransitionOutcome.APPLIED
    assert isinstance(result.events[0].details, Moved)
    assert result.events[0].details.resulting_location_id == EntityId("loc-2")
    assert world.state.bodies[EntityId("body-1")].location_id == EntityId("loc-2")
    assert world.state.bodies[EntityId("body-1")].fatigue.value == 5.0


def test_move_rejects_non_adjacent_and_full_capacity() -> None:
    from world._rules import apply_operation
    from world.values import BodyCapacity

    state = _state()
    same = evaluate_operation(state, _accept(Move(EntityId("loc-1"))))
    assert same.reason is RuleReason.ALREADY_AT_DESTINATION

    locations = connected_locations(("loc-1", "Camp"), ("loc-2", "Forest"))
    tight = tuple(
        type(loc)(
            entity_id=loc.entity_id,
            name=loc.name,
            adjacent=loc.adjacent,
            body_capacity=(
                BodyCapacity(1) if loc.entity_id.value == "loc-2" else loc.body_capacity
            ),
            item_capacity=loc.item_capacity,
            base_temperature=loc.base_temperature,
            shelter_factor=loc.shelter_factor,
            visibility_factor=loc.visibility_factor,
        )
        for loc in locations
    )
    # loc-2 already has body-far; capacity 1 → move into loc-2 from loc-1 fails.
    crowded = WorldState(
        WorldRevision(1),
        locations=tight,
        items=tuple(state.items.values()),
        resources=tuple(state.resources.values()),
        bodies=tuple(state.bodies.values()),
        weather=tuple(state.weather.values()),
    )
    full = evaluate_operation(crowded, _accept(Move(EntityId("loc-2"))))
    assert full.reason is RuleReason.NO_BODY_CAPACITY
    applied = apply_operation(state, _accept(Move(EntityId("loc-2"))))
    assert applied.result.disposition is RuleDisposition.MUTATE
    assert applied.next_state.bodies[EntityId("body-1")].location_id == EntityId(
        "loc-2"
    )


def test_take_rejects_over_carry_capacity() -> None:
    from world.actions import ActionRequest, require_agent_command
    from world.values import CarryCapacity as CC

    heavy = make_item("item-heavy", name="Boulder", location_id="loc-1", load=20)
    actor = AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(50),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CC(1),
    )
    base = _state()
    crowded = WorldState(
        WorldRevision(1),
        locations=tuple(base.locations.values()),
        items=(heavy,),
        resources=tuple(base.resources.values()),
        bodies=(
            actor,
            _alive("body-2", "loc-1"),
            _alive("body-far", "loc-2"),
            _dead("body-dead", "loc-1"),
        ),
        weather=tuple(base.weather.values()),
    )
    outcome = validate_action_request(
        world_id=WorldId("world-1"),
        state=crowded,
        request=ActionRequest(
            request_id=RequestId("r-heavy"),
            proposal_id=ProposalId("p-heavy"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-1"),
            revision=WorldRevision(1),
            command=require_agent_command(Take(EntityId("item-heavy"))),
        ),
    )
    assert isinstance(outcome, OperationAccepted)
    result = evaluate_operation(crowded, outcome.operation)
    assert result.reason is RuleReason.NO_CARRY_CAPACITY


def test_search_miss_and_success() -> None:
    from world._rules import apply_operation
    from world.effects import ResolvedActionEffects, ResolvedSearchEffect
    from world.events import Searched

    state = _state()
    miss_resolved = ResolvedActionEffects(
        {
            RequestId("r-1"): ResolvedSearchEffect(
                request_id=RequestId("r-1"),
                success=False,
                resource_id=EntityId("res-1"),
            )
        }
    )
    miss = apply_operation(state, _accept(Search()), resolved=miss_resolved)
    assert miss.result.disposition is RuleDisposition.EVENT_ONLY
    assert miss.event_details == Searched(target_id=EntityId("res-1"), success=False)
    assert miss.next_state is state

    success_resolved = ResolvedActionEffects(
        {
            RequestId("r-1"): ResolvedSearchEffect(
                request_id=RequestId("r-1"),
                success=True,
                resource_id=EntityId("res-1"),
                created_item_id=EntityId("item-foraged"),
            )
        }
    )
    success = apply_operation(state, _accept(Search()), resolved=success_resolved)
    assert success.result.disposition is RuleDisposition.MUTATE
    assert isinstance(success.event_details, Searched)
    assert success.event_details.success is True
    assert success.event_details.created_item_id == EntityId("item-foraged")
    assert EntityId("item-foraged") in success.next_state.items
    assert success.next_state.resources[EntityId("res-1")].quantity == 0.0


def test_eat_and_drink_consume_and_relieve_needs() -> None:
    from world._rules import apply_operation
    from world.events import Drunk, Eaten

    hungry = _state()
    bodies = dict(hungry.bodies)
    actor = bodies[EntityId("body-1")]
    bodies[EntityId("body-1")] = AgentBody(
        entity_id=actor.entity_id,
        location_id=actor.location_id,
        health=actor.health,
        hunger=Hunger(50),
        thirst=Thirst(50),
        fatigue=actor.fatigue,
        temperature=actor.temperature,
        inventory=actor.inventory,
        life_status=actor.life_status,
        carry_capacity=actor.carry_capacity,
    )
    state = WorldState(
        WorldRevision(1),
        locations=tuple(hungry.locations.values()),
        items=tuple(hungry.items.values()),
        resources=tuple(hungry.resources.values()),
        bodies=tuple(bodies.values()),
        weather=tuple(hungry.weather.values()),
    )
    eaten = apply_operation(state, _accept(Eat(EntityId("item-food"))))
    assert eaten.result.disposition is RuleDisposition.MUTATE
    assert isinstance(eaten.event_details, Eaten)
    assert eaten.next_state.bodies[EntityId("body-1")].hunger.value == 20.0
    assert EntityId("item-food") not in eaten.next_state.items

    drunk_item = apply_operation(state, _accept(Drink(EntityId("item-water"))))
    assert drunk_item.result.disposition is RuleDisposition.MUTATE
    assert isinstance(drunk_item.event_details, Drunk)
    assert drunk_item.event_details.consumed_item is True
    assert drunk_item.next_state.bodies[EntityId("body-1")].thirst.value == 10.0

    drunk_res = apply_operation(state, _accept(Drink(EntityId("res-1"))))
    assert drunk_res.result.disposition is RuleDisposition.MUTATE
    assert isinstance(drunk_res.event_details, Drunk)
    assert drunk_res.event_details.consumed_item is False
    assert drunk_res.next_state.resources[EntityId("res-1")].quantity == 0.0
    assert drunk_res.next_state.bodies[EntityId("body-1")].thirst.value == 10.0
