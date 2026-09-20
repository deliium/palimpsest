"""Private batch preparation, conflict provenance, and revision correlation."""

from __future__ import annotations

from tests.simulation_helpers import make_item, make_location, weather_for_locations
from world._operations import (
    BatchItemStatus,
    PendingBatch,
    PreparedBatch,
    finalize_pending_batch,
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
from world.models import AgentBody, LifeStatus
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


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


def _state() -> WorldState:
    locations = (make_location("loc-1", name="Camp"),)
    return WorldState(
        WorldRevision(4),
        locations=locations,
        items=(make_item("item-1", name="Rock", location_id="loc-1"),),
        bodies=(_alive("body-1", "loc-1"), _alive("body-2", "loc-1")),
        weather=weather_for_locations(locations),
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


def _finalize(
    pending: PendingBatch, *, event_ids: tuple[EventId, ...]
) -> PreparedBatch:
    return finalize_pending_batch(
        pending,
        world_id=WorldId("world-1"),
        starting_revision=WorldRevision(4),
        event_ids=event_ids,
        run_id="run-1",
        tick=0,
    )


def test_event_only_batch_retains_revision_and_stamps_events() -> None:
    state = _state()
    pending = prepare_action_batch(
        world_id=WorldId("world-1"),
        starting_state=state,
        requests=(_request(request_id="r1", actor="body-1", command=Wait()),),
    )
    assert pending.semantic_mutation is False
    assert pending.working_state.revision == WorldRevision(4)
    assert len(pending.pending_events) == 1
    batch = _finalize(pending, event_ids=(EventId("evt-1"),))
    assert batch.semantic_mutation is False
    assert batch.candidate_state.revision == WorldRevision(4)
    assert batch.outcomes[0].status is BatchItemStatus.APPLIED
    assert batch.events[0].details == Waited()
    assert batch.events[0].revision == WorldRevision(4)


def test_mutating_batch_increments_revision_once_for_all_events() -> None:
    state = _state()
    pending = prepare_action_batch(
        world_id=WorldId("world-1"),
        starting_state=state,
        requests=(
            _request(request_id="r1", actor="body-1", command=Take(EntityId("item-1"))),
            _request(request_id="r2", actor="body-2", command=Wait()),
        ),
    )
    assert pending.semantic_mutation is True
    assert pending.working_state.revision == WorldRevision(4)
    assert len(pending.pending_events) == 2
    batch = _finalize(pending, event_ids=(EventId("evt-1"), EventId("evt-2")))
    assert batch.semantic_mutation is True
    assert batch.candidate_state.revision == WorldRevision(5)
    assert all(event.revision == WorldRevision(5) for event in batch.events)
    assert batch.events[0].details == Taken(
        EntityId("item-1"), resulting_holder_id=EntityId("body-1")
    )
    assert (
        EntityId("item-1") in batch.candidate_state.bodies[EntityId("body-1")].inventory
    )


def test_same_item_second_take_is_conflict_not_rejection() -> None:
    state = _state()
    pending = prepare_action_batch(
        world_id=WorldId("world-1"),
        starting_state=state,
        requests=(
            _request(request_id="r1", actor="body-1", command=Take(EntityId("item-1"))),
            _request(request_id="r2", actor="body-2", command=Take(EntityId("item-1"))),
        ),
    )
    batch = _finalize(pending, event_ids=(EventId("evt-1"),))
    assert batch.outcomes[0].status is BatchItemStatus.APPLIED
    assert batch.outcomes[1].status is BatchItemStatus.CONFLICTED
    assert batch.outcomes[1].reason == "conflict_with_prior"
    assert len(batch.events) == 1


def test_initially_invalid_drop_is_rejected_not_conflicted() -> None:
    state = _state()
    pending = prepare_action_batch(
        world_id=WorldId("world-1"),
        starting_state=state,
        requests=(
            _request(
                request_id="r1",
                actor="body-1",
                command=Drop(EntityId("item-1")),
            ),
        ),
    )
    batch = _finalize(pending, event_ids=())
    assert batch.outcomes[0].status is BatchItemStatus.REJECTED
    assert batch.outcomes[0].reason == "not_held"
    assert batch.semantic_mutation is False
    assert batch.events == ()


def test_attack_death_emits_two_pending_events_under_same_cause() -> None:
    from tests.simulation_helpers import connected_locations, weather_for_locations
    from world.actions import Attack
    from world.effects import (
        ActionCause,
        DeathCause,
        ResolvedActionEffects,
        ResolvedAttackEffect,
    )
    from world.events import Attacked, Died

    locations = connected_locations(("loc-1", "Camp"), ("loc-2", "Forest"))
    state = WorldState(
        WorldRevision(4),
        locations=locations,
        bodies=(
            _alive("body-1", "loc-1"),
            _alive("body-2", "loc-1"),
        ),
        weather=weather_for_locations(locations),
    )
    pending = prepare_action_batch(
        world_id=WorldId("world-1"),
        starting_state=state,
        requests=(
            _request(
                request_id="r-atk",
                actor="body-1",
                command=Attack(EntityId("body-2")),
            ),
        ),
        resolved_effects=ResolvedActionEffects(
            {
                RequestId("r-atk"): ResolvedAttackEffect(
                    request_id=RequestId("r-atk"),
                    hit=True,
                    damage=50,
                )
            }
        ),
    )
    assert pending.semantic_mutation is True
    assert len(pending.pending_events) == 2
    cause = ActionCause(RequestId("r-atk"), EntityId("body-1"))
    assert pending.pending_events[0].cause == cause
    assert pending.pending_events[1].cause == cause
    assert pending.pending_events[0].details == Attacked(
        EntityId("body-2"),
        hit=True,
        damage=50,
        resulting_target_health=0.0,
    )
    assert pending.pending_events[1].details == Died(
        EntityId("body-2"), DeathCause.ATTACK
    )
    batch = _finalize(pending, event_ids=(EventId("evt-a"), EventId("evt-d")))
    assert [event.sequence for event in batch.events] == [0, 1]
    dead = batch.candidate_state.bodies[EntityId("body-2")]
    assert dead.life_status is LifeStatus.DEAD


def test_finalize_assigns_contiguous_sequences_for_one_to_many() -> None:
    from world._operations import PendingBatch, PendingEvent
    from world.effects import ActionCause
    from world.events import OccurrenceContext

    state = _state()
    occurrence = OccurrenceContext(origin_location_id=EntityId("loc-1"))
    pending = PendingBatch(
        working_state=state,
        semantic_mutation=False,
        outcomes=(),
        pending_events=(
            PendingEvent(
                cause=ActionCause(RequestId("r1"), EntityId("body-1")),
                details=Waited(),
                occurrence=occurrence,
            ),
            PendingEvent(
                cause=ActionCause(RequestId("r1"), EntityId("body-1")),
                details=Waited(),
                occurrence=occurrence,
            ),
        ),
    )
    batch = _finalize(pending, event_ids=(EventId("evt-a"), EventId("evt-b")))
    assert [event.sequence for event in batch.events] == [0, 1]
    assert all(event.request_id == RequestId("r1") for event in batch.events)
    assert all(event.occurrence == occurrence for event in batch.events)
