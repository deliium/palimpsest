"""Objective gathering, venue, market-cluster, and participation detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import pytest

from analysis.market_institutions_contract import (
    MarketCoverage,
    MarketGatheringStatus,
    MarketInstitutionsError,
    MarketLayer,
    MarketVenueStatus,
    market_candidate_token,
    market_venue_token,
)
from analysis.market_institutions_detection import (
    assert_market_layer_separation,
    detect_gatherings,
    detect_market_candidates,
    detect_participation,
    detect_venues,
)
from analysis.market_institutions_events import (
    MarketAttemptRow,
    MarketEvidenceHarvest,
    MarketExchangeRow,
)
from analysis.market_institutions_policy import (
    MarketInstitutionsAnalysisPolicy,
)
from analysis.market_institutions_rows import MarketVenueRow

pytestmark = pytest.mark.unit


def _exchange(
    token: str,
    *,
    tick: int,
    window: int,
    location: str = "loc-a",
    actor: str = "body-a",
    other: str = "body-b",
) -> MarketExchangeRow:
    return MarketExchangeRow(
        tick=tick,
        window_index=window,
        location_token=location,
        event_token=token,
        actor_token=actor,
        counterparty_token=other,
        party_tokens=cast(tuple[str, str], tuple(sorted((actor, other)))),
    )


def _harvest(
    exchanges: tuple[MarketExchangeRow, ...] = (),
    attempts: tuple[MarketAttemptRow, ...] = (),
    coverage: MarketCoverage = MarketCoverage.COMPLETE,
) -> MarketEvidenceHarvest:
    return MarketEvidenceHarvest(
        exchanges=exchanges,
        attempts=attempts,
        coverage=coverage,
        notices=(),
        exchange_count=len(exchanges),
        attempt_count=len(attempts),
    )


def test_gathering_thresholds() -> None:
    below = detect_gatherings(_harvest((_exchange("evt-1", tick=0, window=0),)))
    assert below[0].status is MarketGatheringStatus.BELOW_THRESHOLD
    gathered = detect_gatherings(
        _harvest(
            (
                _exchange("evt-1", tick=0, window=0),
                _exchange("evt-2", tick=1, window=0, actor="body-c", other="body-b"),
            )
        )
    )
    assert gathered[0].status is MarketGatheringStatus.GATHERING
    assert gathered[0].distinct_party_count == 3


def test_three_active_windows_are_market_like_persistent() -> None:
    exchanges = tuple(
        _exchange(f"evt-{window}-{index}", tick=window, window=window)
        for window in (0, 1, 2)
        for index in (0, 1)
    )
    venues = detect_venues(
        _harvest(exchanges),
        window_end=2,
    )
    persistent = [
        row for row in venues if row.status is MarketVenueStatus.MARKET_LIKE_PERSISTENT
    ]
    assert persistent
    assert persistent[-1].market_like is True
    assert persistent[-1].recurrence_milli == 1_000


def test_single_gathering_stays_single() -> None:
    venues = detect_venues(
        _harvest(
            (
                _exchange("evt-1", tick=0, window=0),
                _exchange("evt-2", tick=1, window=0),
            )
        ),
        window_end=0,
    )
    assert venues[0].status is MarketVenueStatus.SINGLE_GATHERING
    assert venues[0].market_like is False


def test_exactly_one_dormant_row_after_last_activity() -> None:
    venues = detect_venues(
        _harvest(
            (
                _exchange("evt-1", tick=0, window=0),
                _exchange("evt-2", tick=1, window=0),
            )
        ),
        window_end=4,
    )
    dormant = [row for row in venues if row.status is MarketVenueStatus.DORMANT]
    assert len(dormant) == 1
    assert dormant[0].window_index == 1
    assert dormant[0].coverage is MarketCoverage.PARTIAL


def test_no_gathering_produces_no_venue_row() -> None:
    venues = detect_venues(
        _harvest((_exchange("evt-1", tick=0, window=0),)),
        window_end=3,
    )
    assert venues == ()


def _venue(
    *,
    window: int,
    location: str,
    participants: tuple[str, ...],
    exchange_count: int = 2,
) -> MarketVenueRow:
    return MarketVenueRow(
        venue_id=market_venue_token(location),
        window_index=window,
        location_token=location,
        exchange_count=exchange_count,
        proposal_count=0,
        withdrawn_count=0,
        distinct_party_count=len(participants),
        distinct_actor_count=len(participants),
        active_window_count=1,
        recurrence_milli=1_000,
        status=MarketVenueStatus.SINGLE_GATHERING,
        market_like=False,
        coverage=MarketCoverage.COMPLETE,
        participant_tokens=tuple(sorted(participants)),
    )


def test_market_candidates_connect_shared_participants() -> None:
    rows = (
        _venue(window=0, location="loc-a", participants=("body-1", "body-2")),
        _venue(window=0, location="loc-b", participants=("body-2", "body-3")),
        _venue(window=0, location="loc-c", participants=("body-9", "body-8")),
    )
    candidates = detect_market_candidates(rows)
    keys = {tuple(row.venue_ids) for row in candidates}
    expected = tuple(sorted((market_venue_token("loc-a"), market_venue_token("loc-b"))))
    assert expected in keys
    assert (market_venue_token("loc-c"),) in keys
    assert len(candidates) == 2


def test_cluster_identity_is_sorted_and_stable() -> None:
    rows = (
        _venue(window=0, location="loc-a", participants=("body-1", "body-2")),
        _venue(window=0, location="loc-b", participants=("body-2", "body-3")),
    )
    candidates = detect_market_candidates(rows)
    assert candidates[0].market_token == market_candidate_token(candidates[0].venue_ids)


def test_broker_like_requires_three_exchanges_two_counterparties_two_windows() -> None:
    exchanges = (
        _exchange("evt-1", tick=0, window=0, actor="body-a", other="body-b"),
        _exchange("evt-2", tick=1, window=0, actor="body-a", other="body-c"),
        _exchange("evt-3a", tick=2, window=0, actor="body-a", other="body-b"),
        _exchange("evt-3", tick=32, window=1, actor="body-a", other="body-b"),
    )
    rows = detect_participation(_harvest(exchanges))
    actor_rows = [row for row in rows if row.actor_token == "body-a"]
    assert len(actor_rows) == 2
    assert actor_rows[0].broker_like is True
    assert actor_rows[0].counterparty_count == 2


def test_participation_below_threshold_is_not_broker_like() -> None:
    rows = detect_participation(_harvest((_exchange("evt-1", tick=0, window=0),)))
    assert rows[0].broker_like is False


def test_gathering_cap_sets_partial_coverage() -> None:
    policy = MarketInstitutionsAnalysisPolicy(max_gathering_rows=1)
    exchanges = (
        _exchange("evt-1", tick=0, window=0),
        _exchange("evt-2", tick=1, window=0),
        _exchange("evt-3", tick=32, window=1),
        _exchange("evt-4", tick=33, window=1),
    )
    rows = detect_gatherings(_harvest(exchanges), policy=policy)
    assert len(rows) == 1
    assert rows[0].coverage is MarketCoverage.PARTIAL


def test_input_type_is_rejected() -> None:
    invalid = cast(Any, object())
    with pytest.raises(MarketInstitutionsError):
        detect_gatherings(invalid)
    with pytest.raises(MarketInstitutionsError):
        detect_venues(invalid, window_end=0)
    with pytest.raises(MarketInstitutionsError):
        detect_market_candidates(invalid)
    with pytest.raises(MarketInstitutionsError):
        detect_participation(invalid)


def test_layer_leak_is_detected() -> None:
    with pytest.raises(MarketInstitutionsError):
        assert_market_layer_separation(
            {
                MarketLayer.OBJECTIVE_EXCHANGE: (
                    _venue(window=0, location="loc-a", participants=("a", "b")),
                )
            }
        )

    @dataclass(frozen=True, slots=True)
    class LeakyRow:
        event_token: str = "evt-1"

    with pytest.raises(MarketInstitutionsError):
        assert_market_layer_separation({MarketLayer.ANALYTICAL_MARKET: (LeakyRow(),)})

    assert_market_layer_separation(
        {MarketLayer.OBJECTIVE_EXCHANGE: (_exchange("evt-1", tick=0, window=0),)}
    )
