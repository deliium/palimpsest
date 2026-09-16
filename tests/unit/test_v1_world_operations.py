"""Private validated world operations and atomic promotion."""

from __future__ import annotations

from world._operations import (
    OperationRejected,
    RejectionCode,
    validate_action_request,
)
from world._state import World, WorldState
from world._transitions import TransitionResult
from world.actions import ActionProposal, ActionRequest, Move, TransitionOutcome, Wait
from world.events import Waited
from world.identifiers import (
    EntityId,
    EventId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import AgentBody, Item, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst


def _body(entity_id: str, location_id: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(50),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
    )


def _world() -> World:
    state = WorldState(
        WorldRevision(1),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
        bodies=(_body("body-1", "loc-1"), _body("body-2", "loc-1")),
        items=(
            Item(
                entity_id=EntityId("item-1"),
                name="Rock",
                location_id=EntityId("loc-1"),
            ),
        ),
    )
    return World(WorldId("world-1"), state)


def _request(*, command: object, revision: int = 1) -> ActionRequest:
    return ActionRequest(
        request_id=RequestId("r-1"),
        proposal_id=ProposalId("p-1"),
        world_id=WorldId("world-1"),
        actor_id=EntityId("body-1"),
        revision=WorldRevision(revision),
        command=command,  # type: ignore[arg-type]
    )


def test_wait_request_emits_closed_transition_result() -> None:
    world = _world()
    outcome = world.apply_admitted_request(
        _request(command=Wait()),
        event_ids=(EventId("evt-1"),),
        run_id="run-1",
        tick=0,
    )
    assert isinstance(outcome, TransitionResult)
    assert outcome.outcome is TransitionOutcome.APPLIED
    assert outcome.events[0].details == Waited()
    assert outcome.events[0].request_id == RequestId("r-1")


def test_proposals_and_stale_revisions_are_rejected() -> None:
    world = _world()
    proposal = ActionProposal(proposal_id=ProposalId("p-1"), command=Wait())
    rejected = world.apply_admitted_request(
        proposal,
        event_ids=(EventId("evt-1"),),
        run_id="run-1",
        tick=0,
    )
    assert isinstance(rejected, OperationRejected)
    assert rejected.code is RejectionCode.WRONG_TRUST_STAGE

    stale = world.apply_admitted_request(
        _request(command=Wait(), revision=0),
        event_ids=(EventId("evt-1"),),
        run_id="run-1",
        tick=0,
    )
    assert isinstance(stale, OperationRejected)
    assert stale.code is RejectionCode.STALE_REVISION


def test_missing_and_wrong_category_targets_are_rejected() -> None:
    world = _world()
    missing = validate_action_request(
        world_id=WorldId("world-1"),
        state=world.state,
        request=_request(command=Move(EntityId("missing"))),
    )
    assert isinstance(missing, OperationRejected)
    assert missing.code is RejectionCode.MISSING_TARGET

    wrong = validate_action_request(
        world_id=WorldId("world-1"),
        state=world.state,
        request=_request(command=Move(EntityId("item-1"))),
    )
    assert isinstance(wrong, OperationRejected)
    assert wrong.code is RejectionCode.WRONG_TARGET_CATEGORY


def test_cross_world_request_is_rejected() -> None:
    world = _world()
    request = ActionRequest(
        request_id=RequestId("r-1"),
        proposal_id=ProposalId("p-1"),
        world_id=WorldId("other-world"),
        actor_id=EntityId("body-1"),
        revision=WorldRevision(1),
        command=Wait(),
    )
    rejected = world.apply_admitted_request(
        request,
        event_ids=(EventId("evt-1"),),
        run_id="run-1",
        tick=0,
    )
    assert isinstance(rejected, OperationRejected)
    assert rejected.code is RejectionCode.WRONG_WORLD
