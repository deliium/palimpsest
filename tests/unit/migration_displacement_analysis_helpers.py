# mypy: ignore-errors
"""Shared builders for detached migration-displacement analysis tests."""

from __future__ import annotations

from types import SimpleNamespace

from analysis.migration_displacement_events import (
    MigrationIntegrationEvidenceRow,
    MigrationMovementRow,
    migration_agent_token,
    migration_location_token,
)
from analysis.migration_displacement_policy import (
    default_migration_displacement_analysis_policy,
)
from analysis.migration_displacement_rows import MigrationCauseRow
from world.effects import DeathCause
from world.events import (
    Died,
    Fled,
    JourneyArrived,
    JourneyEnded,
    JourneyStarted,
    Moved,
    Transported,
)
from world.identifiers import EntityId, EventId
from world.regions import Journey

POLICY = default_migration_displacement_analysis_policy()
RUN = "run-1"
REV = "rev-1"

_COUNTER = {"n": 0}


def event(details, *, tick=0, actor=None, target=None, origin=None):
    _COUNTER["n"] += 1
    return SimpleNamespace(
        event_id=EventId(f"event-{_COUNTER['n']}"),
        tick=tick,
        sequence=_COUNTER["n"],
        actor_id=None if actor is None else EntityId(actor),
        target_id=None if target is None else EntityId(target),
        details=details,
        occurrence=SimpleNamespace(
            origin_location_id=None if origin is None else EntityId(origin),
            destination_location_id=None,
        ),
    )


def move(tick, actor, origin, destination):
    return event(
        Moved(destination_id=EntityId(destination)),
        tick=tick,
        actor=actor,
        origin=origin,
    )


def transport(tick, actor, target, origin, destination):
    return event(
        Transported(
            target_id=EntityId(target),
            destination_id=EntityId(destination),
            origin_location_id=EntityId(origin),
        ),
        tick=tick,
        actor=actor,
        target=target,
    )


def flee(tick, actor, origin, destination, *, success=True):
    return event(
        Fled(
            success=success,
            destination_id=EntityId(destination) if success else None,
        ),
        tick=tick,
        actor=actor,
        origin=origin,
    )


def journey_started(tick, journey_id, bodies, origin, destination):
    journey = Journey(
        journey_id=journey_id,
        participant_body_ids=tuple(EntityId(item) for item in bodies),
        actor_body_id=EntityId(bodies[0]),
        origin_location_id=EntityId(origin),
        destination_location_id=EntityId(destination),
        origin_region_id=None,
        destination_region_id=None,
        start_tick=tick,
        due_tick=tick + 2,
        charged_fatigue_cost=0.0,
        arrival_wait_deadline_tick=tick + 6,
    )
    return event(
        JourneyStarted(
            journey=journey,
            command_kind="move",
            fatigue_delta=0.0,
            resulting_actor_fatigue=0.0,
        ),
        tick=tick,
        actor=bodies[0],
    )


def journey_arrived(tick, journey_id, bodies, origin, destination):
    return event(
        JourneyArrived(
            journey_id=journey_id,
            participant_body_ids=tuple(EntityId(item) for item in bodies),
            origin_location_id=EntityId(origin),
            destination_location_id=EntityId(destination),
        ),
        tick=tick,
    )


def journey_ended(tick, journey_id, bodies, origin, destination, reason):
    return event(
        JourneyEnded(
            journey_id=journey_id,
            participant_body_ids=tuple(EntityId(item) for item in bodies),
            origin_location_id=EntityId(origin),
            destination_location_id=EntityId(destination),
            reason=reason,
        ),
        tick=tick,
    )


def died(tick, body):
    return event(
        Died(body_id=EntityId(body), death_cause=DeathCause.LIFESPAN),
        tick=tick,
    )


def p(name):
    return migration_agent_token(name)


def loc(name):
    return migration_location_token(name)


def movement(
    participant,
    origin,
    destination,
    start,
    *,
    end=None,
    route=None,
    status="arrived",
    coverage="complete",
    kind="journey",
    group=1,
):
    origin_token = loc(origin)
    destination_token = loc(destination)
    return MigrationMovementRow(
        participant_token=p(participant),
        origin_token=origin_token,
        destination_token=destination_token,
        route_tokens=(
            route if route is not None else (origin_token, destination_token)
        ),
        start_tick=start,
        end_tick=start if end is None else end,
        relocation_kind=kind,
        group_size=group,
        arrival_status=status,
        coverage=coverage,
    )


def evidence(
    participant, destination, domain, count=1, first=1, last=1, cov="complete"
):
    return MigrationIntegrationEvidenceRow(
        participant_token=p(participant),
        destination_token=loc(destination),
        domain=domain,
        evidence_count=count,
        first_tick=first,
        last_tick=last,
        coverage=cov,
    )


def cause(
    owner,
    kind,
    *,
    anchor="",
    lineage=(),
    tick=1,
    status="active",
    source="direct_observation",
    token=None,
    coverage="resolved",
):
    owner_token = p(owner)
    return MigrationCauseRow(
        owner_token=owner_token,
        cause_token=token or f"mdc-{owner}-{kind.replace('_', '-')}-{tick}"[:63],
        cause_kind=kind,
        source_kind=source,
        anchor_token=anchor,
        lineage_refs=tuple(sorted(lineage)),
        confidence=0.5,
        tick=tick,
        status=status,
        coverage=coverage,
    )
