"""Private batch preparation, conflict provenance, and revision correlation."""

from __future__ import annotations

from world._operations import (
    BatchItemStatus,
    prepare_action_batch,
)
from world._state import WorldState
from world.actions import ActionRequest, Drop, Take, Wait
from world.events import Taken, Waited
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


def _state() -> WorldState:
    return WorldState(
        WorldRevision(4),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
        items=(
            Item(
                entity_id=EntityId("item-1"),
                name="Rock",
                location_id=EntityId("loc-1"),
            ),
        ),
        bodies=(_alive("body-1", "loc-1"), _alive("body-2", "loc-1")),
    )


def _request(
    *,
    request_id: str,
    actor: str,
    command: object,
    revision: int = 4,
) -> ActionRequest:
    return ActionRequest(
        request_id=RequestId(request_id),
        proposal_id=ProposalId(f"p-{request_id}"),
        world_id=WorldId("world-1"),
        actor_id=EntityId(actor),
        revision=WorldRevision(revision),
        command=command,  # type: ignore[arg-type]
    )


def test_event_only_batch_retains_revision_and_stamps_events() -> None:
    state = _state()
    batch = prepare_action_batch(
        world_id=WorldId("world-1"),
        starting_state=state,
        requests=(_request(request_id="r1", actor="body-1", command=Wait()),),
        event_ids=(EventId("evt-1"),),
        run_id="run-1",
        tick=0,
    )
    assert batch.semantic_mutation is False
    assert batch.candidate_state.revision == WorldRevision(4)
    assert batch.outcomes[0].status is BatchItemStatus.APPLIED
    assert batch.events[0].details == Waited()
    assert batch.events[0].revision == WorldRevision(4)


def test_mutating_batch_increments_revision_once_for_all_events() -> None:
    state = _state()
    batch = prepare_action_batch(
        world_id=WorldId("world-1"),
        starting_state=state,
        requests=(
            _request(request_id="r1", actor="body-1", command=Take(EntityId("item-1"))),
            _request(request_id="r2", actor="body-2", command=Wait()),
        ),
        event_ids=(EventId("evt-1"), EventId("evt-2")),
        run_id="run-1",
        tick=0,
    )
    assert batch.semantic_mutation is True
    assert batch.candidate_state.revision == WorldRevision(5)
    assert all(event.revision == WorldRevision(5) for event in batch.events)
    assert batch.events[0].details == Taken(
        EntityId("item-1"), resulting_holder_id=EntityId("body-1")
    )
    assert EntityId("item-1") in batch.candidate_state.bodies[
        EntityId("body-1")
    ].inventory


def test_same_item_second_take_is_conflict_not_rejection() -> None:
    state = _state()
    batch = prepare_action_batch(
        world_id=WorldId("world-1"),
        starting_state=state,
        requests=(
            _request(request_id="r1", actor="body-1", command=Take(EntityId("item-1"))),
            _request(request_id="r2", actor="body-2", command=Take(EntityId("item-1"))),
        ),
        event_ids=(EventId("evt-1"), EventId("evt-2")),
        run_id="run-1",
        tick=0,
    )
    assert batch.outcomes[0].status is BatchItemStatus.APPLIED
    assert batch.outcomes[1].status is BatchItemStatus.CONFLICTED
    assert batch.outcomes[1].reason == "conflict_with_prior"
    assert len(batch.events) == 1


def test_initially_invalid_drop_is_rejected_not_conflicted() -> None:
    state = _state()
    batch = prepare_action_batch(
        world_id=WorldId("world-1"),
        starting_state=state,
        requests=(
            _request(
                request_id="r1",
                actor="body-1",
                command=Drop(EntityId("item-1")),
            ),
        ),
        event_ids=(EventId("evt-1"),),
        run_id="run-1",
        tick=0,
    )
    assert batch.outcomes[0].status is BatchItemStatus.REJECTED
    assert batch.outcomes[0].reason == "not_held"
    assert batch.semantic_mutation is False
    assert batch.events == ()
