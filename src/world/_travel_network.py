"""Private objective travel-network helpers. Not part of the public facade."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from world._state import WorldState, rebuild_world_state
from world.environment import Season
from world.events import RouteConditionChanged
from world.identifiers import EntityId

if TYPE_CHECKING:
    from world._rules import RuleReason

from world.travel_network import (
    MAX_ROUTE_CONDITIONS,
    RouteCondition,
    RouteStatus,
    SeasonalAvailability,
    derive_route_condition,
)

_LOG: Final[logging.Logger] = logging.getLogger("world.travel_network")

__all__ = [
    "advance_route_conditions",
    "condition_for_command",
    "route_rejection_reason",
]


def _changed(previous: RouteCondition | None, current: RouteCondition) -> bool:
    if previous is None:
        return True
    return (
        previous.status is not current.status
        or previous.seasonal_availability is not current.seasonal_availability
        or previous.duration_ticks != current.duration_ticks
        or previous.fatigue_cost != current.fatigue_cost
        or previous.capacity != current.capacity
        or previous.risk != current.risk
        or previous.infrastructure_quality != current.infrastructure_quality
        or previous.blockage_cause is not current.blockage_cause
        or previous.reason_codes != current.reason_codes
    )


def _transition_detail(
    previous: RouteCondition | None,
    current: RouteCondition,
    *,
    season: Season | None,
) -> RouteConditionChanged:
    return RouteConditionChanged(
        origin_location_id=current.origin_id,
        destination_location_id=current.destination_id,
        previous_status=(
            RouteStatus.OPEN.value if previous is None else previous.status.value
        ),
        current_status=current.status.value,
        previous_seasonal_availability=(
            SeasonalAvailability.OPEN.value
            if previous is None
            else previous.seasonal_availability.value
        ),
        current_seasonal_availability=current.seasonal_availability.value,
        duration_ticks=current.duration_ticks,
        fatigue_cost=current.fatigue_cost,
        capacity=current.capacity,
        risk=current.risk,
        infrastructure_quality=current.infrastructure_quality,
        blockage_cause=current.blockage_cause.value,
        reason_codes=current.reason_codes,
        season=None if season is None else season.value,
        as_of_tick=current.as_of_tick,
        previous_duration_ticks=(
            None if previous is None else previous.duration_ticks
        ),
        previous_fatigue_cost=(
            None if previous is None else previous.fatigue_cost
        ),
        previous_capacity=None if previous is None else previous.capacity,
        previous_risk=None if previous is None else previous.risk,
        previous_infrastructure_quality=(
            None if previous is None else previous.infrastructure_quality
        ),
        previous_blockage_cause=(
            None if previous is None else previous.blockage_cause.value
        ),
        previous_reason_codes=(
            None if previous is None else previous.reason_codes
        ),
    )


def advance_route_conditions(
    state: WorldState, *, season: Season | None, tick: int
) -> tuple[WorldState, tuple[RouteConditionChanged, ...]]:
    """Recompute all adjacent edges and emit one event per changed edge."""
    if type(state) is not WorldState:
        raise TypeError("advance_route_conditions requires WorldState")
    if season is not None and type(season) is not Season:
        raise TypeError("season must be Season or None")
    rows: list[RouteCondition] = []
    transitions: list[RouteConditionChanged] = []
    for origin_id in sorted(state.locations, key=lambda item: item.value):
        origin = state.locations[origin_id]
        for destination_id in sorted(origin.adjacent, key=lambda item: item.value):
            if origin_id.value >= destination_id.value:
                continue
            current = derive_route_condition(
                state,
                origin_id,
                destination_id,
                season=season,
                tick=tick,
            )
            previous = state.route_condition(origin_id, destination_id)
            if previous is not None and _changed(previous, current):
                rows.append(current)
                transitions.append(_transition_detail(previous, current, season=season))
            else:
                rows.append(current if previous is None else previous)
            if len(rows) > MAX_ROUTE_CONDITIONS:
                _LOG.warning(
                    "travel_network_transition_count tick=%s count=%s",
                    tick,
                    len(rows),
                )
                raise ValueError("travel_network_route_cap_exceeded")
    next_state = rebuild_world_state(state, travel_network=tuple(rows))
    if transitions:
        _LOG.debug(
            "travel_network_transition tick=%s changed=%s",
            tick,
            len(transitions),
        )
    return next_state, tuple(transitions)


def condition_for_command(
    state: WorldState,
    origin_id: EntityId,
    destination_id: EntityId,
    *,
    season: Season | None,
    active: bool,
) -> RouteCondition | None:
    """Return the authoritative condition or ``None`` when the channel is off."""
    if not active:
        return None
    if state.regions_migration is None:
        return None
    return state.route_condition(origin_id, destination_id)


def route_rejection_reason(
    condition: RouteCondition,
    participant_count: int,
) -> RuleReason | None:
    """Map a condition/capacity overflow to the rules' closed reason enum."""
    from world._rules import RuleReason

    if condition.status is RouteStatus.CLOSED:
        if condition.blockage_cause.value != "none":
            return RuleReason.ROUTE_BLOCKED
        return RuleReason.ROUTE_CLOSED
    if participant_count > condition.capacity:
        return RuleReason.ROUTE_CAPACITY_EXCEEDED
    return None
