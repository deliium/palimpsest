"""Shared builders for market-like institution unit tests."""

from __future__ import annotations

from types import SimpleNamespace

from agents.cognition.market_institutions import (
    MarketCadence,
    MarketExpectation,
    MarketInstitutionLedger,
    MarketMeetingExpectation,
    MarketRecordKind,
    MarketRecordRef,
    MarketRoleBasis,
    MarketRoleClaim,
    MarketRoleKind,
    MarketScheduleBelief,
    MarketScheduleSource,
    MarketVenueBelief,
    MarketVenueObservation,
    MarketVenueStatus,
    market_observation_digest,
    market_venue_belief_id,
)
from agents.models import AgentId
from world.identifiers import EntityId

OWNER = AgentId("agent-1")
PEER = AgentId("agent-2")
OWNER_ENTITY = EntityId("body-1")
PEER_ENTITY = EntityId("body-2")
PEER3_ENTITY = EntityId("body-3")
A = EntityId("loc-a")
B = EntityId("loc-b")


def observation(
    *,
    tick: int = 3,
    location: EntityId = A,
    observer: EntityId = OWNER_ENTITY,
    occurrences: tuple[object, ...] = (),
    communications: tuple[object, ...] = (),
    exits: tuple[EntityId, ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        tick=tick,
        observer_id=observer,
        self_body=SimpleNamespace(location_id=location, entity_id=observer),
        occurrences=tuple(occurrences),
        communications=tuple(communications),
        exits=tuple(
            SimpleNamespace(destination_id=destination) for destination in exits
        ),
    )


def occurrence(
    *,
    kind: str = "exchange_completed",
    source_tick: int = 2,
    actor: EntityId = OWNER_ENTITY,
    other: EntityId = PEER_ENTITY,
) -> SimpleNamespace:
    return SimpleNamespace(
        kind=kind,
        public_facts={"kind": kind},
        actor_id=actor,
        other_entity_id=other,
        provenance=SimpleNamespace(source_tick=source_tick),
    )


def schedule(
    *,
    cadence: MarketCadence = MarketCadence.RECURRING_INTERVAL,
    interval_ticks: int | None = 5,
    phase_tick: int | None = 1,
    window_index: int | None = None,
    confidence_milli: int = 500,
    source: MarketScheduleSource = MarketScheduleSource.SELF_AUTHORED,
    tick: int = 1,
) -> MarketScheduleBelief:
    return MarketScheduleBelief(
        cadence=cadence,
        interval_ticks=interval_ticks,
        phase_tick=phase_tick,
        window_index=window_index,
        confidence_milli=confidence_milli,
        source=source,
        first_tick=tick,
        last_tick=tick,
    )


def venue(
    *,
    owner: AgentId = OWNER,
    location: EntityId = A,
    creation_tick: int = 1,
    status: MarketVenueStatus = MarketVenueStatus.EXPECTED,
    expectation: MarketExpectation = MarketExpectation.EXPECTED,
    observations: tuple[MarketVenueObservation, ...] = (),
    schedules: tuple[MarketScheduleBelief, ...] = (),
    roles: tuple[MarketRoleClaim, ...] = (),
    records: tuple[MarketRecordRef, ...] = (),
    notices: tuple[str, ...] = (),
) -> MarketVenueBelief:
    venue_id = market_venue_belief_id(
        owner_id=owner, location_id=location, creation_tick=creation_tick
    )
    first = min((item.source_tick for item in observations), default=creation_tick)
    last = max((item.source_tick for item in observations), default=creation_tick)
    return MarketVenueBelief(
        venue_id=venue_id,
        owner_id=owner,
        location_id=location,
        label_token=f"venue-{venue_id[5:13]}",
        status=status,
        first_tick=first,
        last_tick=last,
        observations=observations,
        expectation=MarketMeetingExpectation(
            level=expectation,
            evidence_count=len(observations),
            first_tick=first,
            last_tick=last,
        ),
        schedules=schedules,
        roles=roles,
        records=records,
        notices=notices,
    )


def observed(
    *,
    venue_id: str,
    source_tick: int,
    tick: int | None = None,
    parties: tuple[EntityId, ...] = (PEER_ENTITY,),
    exchange_count: int = 2,
    proposal_count: int = 0,
    withdrawn_count: int = 0,
) -> MarketVenueObservation:
    return MarketVenueObservation(
        tick=source_tick if tick is None else tick,
        source_tick=source_tick,
        counterparty_ids=parties,
        exchange_count=exchange_count,
        proposal_count=proposal_count,
        withdrawn_count=withdrawn_count,
        digest=market_observation_digest(
            venue_id=venue_id,
            source_tick=source_tick,
            counterparty_ids=parties,
            exchange_count=exchange_count,
            proposal_count=proposal_count,
            withdrawn_count=withdrawn_count,
        ),
    )


def ledger(
    *,
    owner: AgentId = OWNER,
    venues: tuple[MarketVenueBelief, ...] = (),
    notices: tuple[str, ...] = (),
) -> MarketInstitutionLedger:
    return MarketInstitutionLedger(owner_id=owner, venues=venues, notices=notices)


def role(
    *,
    kind: MarketRoleKind = MarketRoleKind.BROKER,
    basis: MarketRoleBasis = MarketRoleBasis.CLAIMED,
    actor: EntityId = PEER_ENTITY,
    office_ref: str | None = None,
    organization_ref: str | None = None,
    recognized: bool = False,
    tick: int = 1,
) -> MarketRoleClaim:
    return MarketRoleClaim(
        role_kind=kind,
        basis=basis,
        actor_id=actor,
        office_ref=office_ref,
        organization_ref=organization_ref,
        recognized=recognized,
        first_tick=tick,
        last_tick=tick,
    )


def record(*, tick: int = 1, anchor: str = "record-1") -> MarketRecordRef:
    return MarketRecordRef(
        record_kind=MarketRecordKind.EXCHANGE_RECORD,
        anchor=anchor,
        first_tick=tick,
        last_tick=tick,
    )
