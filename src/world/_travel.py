"""Deterministic completion of pending discrete journeys."""

from __future__ import annotations

import logging

from world._state import WorldState, rebuild_world_state
from world.events import JourneyArrived, JourneyEnded
from world.models import LifeStatus, copy_body

_LOG = logging.getLogger("world.travel")

__all__ = ["advance_due_journeys", "cancel_dead_journeys"]


def advance_due_journeys(
    state: WorldState, *, tick: int
) -> tuple[WorldState, tuple[JourneyArrived | JourneyEnded, ...]]:
    """Advance due journeys by deterministic whole-group arrival attempts."""
    if type(state) is not WorldState:
        raise TypeError("advance_due_journeys requires WorldState")
    if type(tick) is not int or tick < 0:
        raise ValueError("tick must be non-negative (code=invalid_tick)")
    if state.regions_migration is None or state.journeys is None:
        return state, ()

    journeys = dict(state.journeys)
    bodies = dict(state.bodies)
    transitions: list[JourneyArrived | JourneyEnded] = []
    for journey in sorted(
        state.journeys.values(), key=lambda row: (row.due_tick, row.journey_id)
    ):
        participants = tuple(bodies[item] for item in journey.participant_body_ids)
        if any(body.life_status is LifeStatus.DEAD for body in participants):
            transitions.append(
                JourneyEnded(
                    journey_id=journey.journey_id,
                    participant_body_ids=journey.participant_body_ids,
                    origin_location_id=journey.origin_location_id,
                    destination_location_id=journey.destination_location_id,
                    reason="participant_dead",
                )
            )
            journeys.pop(journey.journey_id)
            continue
        if tick < journey.due_tick:
            continue
        destination = state.locations[journey.destination_location_id]
        occupied = sum(
            1
            for body in bodies.values()
            if body.location_id == journey.destination_location_id
        )
        if (
            occupied + len(journey.participant_body_ids)
            <= destination.body_capacity.value
        ):
            for participant_id in journey.participant_body_ids:
                bodies[participant_id] = copy_body(
                    bodies[participant_id],
                    location_id=journey.destination_location_id,
                )
            journeys.pop(journey.journey_id)
            transitions.append(
                JourneyArrived(
                    journey_id=journey.journey_id,
                    participant_body_ids=journey.participant_body_ids,
                    origin_location_id=journey.origin_location_id,
                    destination_location_id=journey.destination_location_id,
                )
            )
            _LOG.debug(
                "journey_arrival_prepared journey_id=%s tick=%s participant_count=%s",
                journey.journey_id,
                tick,
                len(journey.participant_body_ids),
            )
        elif tick >= journey.arrival_wait_deadline_tick:
            journeys.pop(journey.journey_id)
            transitions.append(
                JourneyEnded(
                    journey_id=journey.journey_id,
                    participant_body_ids=journey.participant_body_ids,
                    origin_location_id=journey.origin_location_id,
                    destination_location_id=journey.destination_location_id,
                    reason="arrival_timeout",
                )
            )
            _LOG.debug(
                "journey_timeout_prepared journey_id=%s tick=%s",
                journey.journey_id,
                tick,
            )
        else:
            _LOG.debug(
                "journey_capacity_wait journey_id=%s tick=%s occupied=%s group_size=%s",
                journey.journey_id,
                tick,
                occupied,
                len(journey.participant_body_ids),
            )

    if not transitions:
        return state, ()
    next_state = rebuild_world_state(
        state,
        bodies=bodies,
        journeys=tuple(journeys.values()),
    )
    return next_state, tuple(transitions)


def cancel_dead_journeys(
    state: WorldState,
) -> tuple[WorldState, tuple[JourneyEnded, ...]]:
    """End journeys affected by deaths that occurred during physical/lifecycle work."""
    if type(state) is not WorldState:
        raise TypeError("cancel_dead_journeys requires WorldState")
    if state.journeys is None:
        return state, ()
    journeys = dict(state.journeys)
    endings: list[JourneyEnded] = []
    for journey in sorted(
        state.journeys.values(), key=lambda row: (row.due_tick, row.journey_id)
    ):
        if not any(
            state.bodies[item].life_status is LifeStatus.DEAD
            for item in journey.participant_body_ids
        ):
            continue
        journeys.pop(journey.journey_id)
        endings.append(
            JourneyEnded(
                journey_id=journey.journey_id,
                participant_body_ids=journey.participant_body_ids,
                origin_location_id=journey.origin_location_id,
                destination_location_id=journey.destination_location_id,
                reason="participant_dead",
            )
        )
    if not endings:
        return state, ()
    return (
        rebuild_world_state(state, journeys=tuple(journeys.values())),
        tuple(endings),
    )
