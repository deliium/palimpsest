"""One-hop market attendance planning over an already-selected command.

An otherwise idle owner may replace ``Wait`` with one ordinary ``Move`` to an
observed adjacent exit whose destination is an expected or persistent venue.
There is no pathfinding, multi-hop travel, lookahead, or global venue catalog.
"""

from __future__ import annotations

import logging
from typing import Final, cast

from agents.cognition.market_institutions import (
    MarketInstitutionLedger,
    MarketInstitutionPolicy,
    MarketVenueStatus,
    default_market_institution_policy,
    market_schedule_is_active,
)
from agents.models import AgentId
from world.actions import AgentCommand, Move, Wait
from world.identifiers import EntityId

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.market_institutions_actions"
)

_ATTENDABLE_STATUSES: Final[frozenset[MarketVenueStatus]] = frozenset(
    {MarketVenueStatus.EXPECTED, MarketVenueStatus.PERSISTENT}
)


def market_attendance_command(
    command: object,
    *,
    owner_id: AgentId,
    tick: int,
    observation: object,
    ledger: object | None,
    policy: MarketInstitutionPolicy | None = None,
) -> AgentCommand:
    """Return one existing ``Move`` for an expected venue, else ``command``."""

    if type(command) is not Wait:
        return _as_command(command)
    if type(ledger) is not MarketInstitutionLedger:
        return _as_command(command)
    if type(owner_id) is not AgentId or ledger.owner_id != owner_id:
        return _as_command(command)
    if type(tick) is not int or tick < 0:
        return _as_command(command)
    active_policy = (
        default_market_institution_policy() if policy is None else policy
    )
    if type(active_policy) is not MarketInstitutionPolicy:
        return _as_command(command)
    body = getattr(observation, "self_body", None)
    current_location = getattr(body, "location_id", None)
    if type(current_location) is not EntityId:
        return _as_command(command)
    exits: dict[str, EntityId] = {}
    for exit_row in getattr(observation, "exits", ()):
        destination = getattr(exit_row, "destination_id", None)
        if type(destination) is EntityId:
            exits.setdefault(destination.value, destination)
    if not exits:
        return _as_command(command)
    candidates = [
        venue
        for venue in ledger.venues
        if venue.status in _ATTENDABLE_STATUSES
        and venue.location_id != current_location
        and any(
            market_schedule_is_active(schedule, tick)
            for schedule in venue.schedules
        )
    ]
    candidates.sort(key=lambda venue: venue.venue_id)
    for venue in candidates:
        destination = exits.get(venue.location_id.value)
        if destination is not None:
            _LOG.debug("market_attendance_selected candidates=%s", len(candidates))
            return Move(destination_id=destination)
    return _as_command(command)


def _as_command(command: object) -> AgentCommand:
    """Narrow an already validated command without constructing a new value."""

    return cast(AgentCommand, command)


__all__ = ["market_attendance_command"]
