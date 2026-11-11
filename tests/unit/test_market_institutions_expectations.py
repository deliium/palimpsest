"""Detached owner expectation, role, record joins and alignment."""

from __future__ import annotations

import pytest

from analysis.market_institutions_contract import (
    MarketAlignment,
    MarketCoverage,
    MarketInstitutionsError,
    MarketVenueStatus,
    market_venue_token,
)
from analysis.market_institutions_expectations import (
    join_expectations,
    join_market_owner_rows,
    join_records,
    join_roles,
)
from analysis.market_institutions_policy import (
    MarketInstitutionsAnalysisPolicy,
)
from analysis.market_institutions_rows import (
    MarketOwnerExpectationInput,
    MarketOwnerRecordInput,
    MarketOwnerRoleInput,
    MarketParticipationRow,
    MarketVenueRow,
)

pytestmark = pytest.mark.unit

VENUE = market_venue_token("loc-a")


def _venue(
    window: int,
    *,
    status: MarketVenueStatus = MarketVenueStatus.SINGLE_GATHERING,
) -> MarketVenueRow:
    return MarketVenueRow(
        venue_id=VENUE,
        window_index=window,
        location_token="loc-a",
        exchange_count=2,
        proposal_count=0,
        withdrawn_count=0,
        distinct_party_count=2,
        distinct_actor_count=1,
        active_window_count=1,
        recurrence_milli=1_000,
        status=status,
        market_like=False,
        coverage=MarketCoverage.COMPLETE,
        participant_tokens=("body-a", "body-b"),
    )


def _expectation(
    *,
    window: int = 0,
    cadence: str = "recurring_interval",
    interval: int | None = 32,
    phase: int | None = 0,
    schedule_window: int | None = None,
    expectation: str = "strong",
) -> MarketOwnerExpectationInput:
    return MarketOwnerExpectationInput(
        owner_token="owner-1",
        venue_token=VENUE,
        expectation=expectation,
        cadence=cadence,
        interval_ticks=interval,
        phase_tick=phase,
        schedule_window_index=schedule_window,
        confidence_milli=750,
        evidence_count=2,
        first_tick=0,
        last_tick=50,
    )


def test_no_owner_rows_means_missing_coverage() -> None:
    joined = join_market_owner_rows(
        venues=(_venue(0),),
        participation=(),
        window_end=0,
    )
    assert joined.expectations == ()
    assert joined.roles == ()
    assert joined.records == ()
    assert joined.expectation_coverage is MarketCoverage.MISSING
    assert joined.role_coverage is MarketCoverage.MISSING
    assert joined.record_coverage is MarketCoverage.MISSING


def test_interval_alignment_three_of_four_is_consistent() -> None:
    venues = (_venue(0), _venue(1), _venue(2))
    rows = join_expectations(
        (_expectation(cadence="recurring_interval", interval=1, phase=0),),
        venues=venues,
        window_end=3,
    )
    assert rows
    assert rows[0].alignment is MarketAlignment.CONSISTENT
    assert rows[0].coverage is MarketCoverage.COMPLETE


def test_interval_prediction_boundaries() -> None:
    venues = (_venue(0), _venue(1), _venue(2))
    interval_32 = join_expectations(
        (_expectation(interval=32, phase=0),),
        venues=venues,
        window_end=2,
    )
    assert interval_32[0].alignment is MarketAlignment.CONSISTENT
    sparse = join_expectations(
        (_expectation(interval=65, phase=0),),
        venues=(_venue(0),),
        window_end=2,
    )
    assert sparse[0].alignment is MarketAlignment.UNRESOLVED


def test_periodic_window_and_not_applicable() -> None:
    venues = (_venue(0), _venue(1))
    periodic = join_expectations(
        (
            _expectation(
                cadence="periodic_window",
                interval=None,
                phase=None,
                schedule_window=1,
            ),
        ),
        venues=venues,
        window_end=1,
    )
    assert periodic[0].cadence == "periodic_window"
    not_applicable = join_expectations(
        (_expectation(cadence="unknown", interval=None, phase=None),),
        venues=venues,
        window_end=1,
    )
    assert not_applicable[0].alignment is MarketAlignment.NOT_APPLICABLE


def test_recognized_role_requires_office_or_organization() -> None:
    participation = (
        MarketParticipationRow(
            venue_id=VENUE,
            window_index=0,
            actor_token="body-a",
            exchange_count=3,
            counterparty_count=2,
            active_window_count=2,
            broker_like=True,
            coverage=MarketCoverage.COMPLETE,
        ),
    )
    rows = join_roles(
        (
            MarketOwnerRoleInput(
                owner_token="owner-1",
                venue_token=VENUE,
                role_kind="broker",
                role_basis="office",
                recognized=True,
                actor_token="body-a",
                first_tick=0,
                last_tick=1,
            ),
            MarketOwnerRoleInput(
                owner_token="owner-1",
                venue_token=VENUE,
                role_kind="host",
                role_basis="claimed",
                recognized=True,
                actor_token="body-b",
                first_tick=0,
                last_tick=1,
            ),
        ),
        venues=(_venue(0),),
        participation=participation,
    )
    assert rows[0].recognized is True
    assert rows[1].recognized is False


def test_broker_role_requires_broker_like_participation() -> None:
    rows = join_roles(
        (
            MarketOwnerRoleInput(
                owner_token="owner-1",
                venue_token=VENUE,
                role_kind="broker",
                role_basis="claimed",
                recognized=False,
                actor_token="body-a",
                first_tick=0,
                last_tick=1,
            ),
        ),
        venues=(_venue(0),),
        participation=(),
    )
    assert rows == ()


def test_record_anchors_are_copied_not_dereferenced() -> None:
    rows = join_records(
        (
            MarketOwnerRecordInput(
                owner_token="owner-1",
                venue_token=VENUE,
                record_kind="exchange_record",
                anchor_token="record-1",
                first_tick=0,
                last_tick=1,
            ),
        ),
        venues=(_venue(0),),
    )
    assert rows[0].anchor_token == "record-1"
    assert rows[0].owner_row_count == 1


def test_unknown_venue_is_not_fabricated() -> None:
    joined = join_market_owner_rows(
        expectation_inputs=(_expectation(),),
        venues=(),
        participation=(),
        window_end=0,
    )
    assert joined.expectations == ()
    assert joined.expectation_coverage is MarketCoverage.PARTIAL


def test_expectation_cap_sets_partial() -> None:
    policy = MarketInstitutionsAnalysisPolicy(max_expectation_rows=1)
    rows = join_expectations(
        (_expectation(interval=1),),
        venues=(_venue(0), _venue(1), _venue(2)),
        window_end=2,
        policy=policy,
    )
    assert len(rows) == 1
    assert rows[0].coverage is MarketCoverage.PARTIAL


def test_foreign_input_row_is_rejected() -> None:
    with pytest.raises(MarketInstitutionsError):
        join_expectations((object(),), venues=(), window_end=0)  # type: ignore[arg-type]
    with pytest.raises(MarketInstitutionsError):
        join_roles((object(),), venues=(), participation=())  # type: ignore[arg-type]
    with pytest.raises(MarketInstitutionsError):
        join_records((object(),), venues=())  # type: ignore[arg-type]
