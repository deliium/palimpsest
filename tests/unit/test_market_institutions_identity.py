"""Market identity and forward-only lineage including empty windows."""

from __future__ import annotations

import pytest

from analysis.market_institutions_contract import (
    MarketCoverage,
    MarketInstitutionsError,
    MarketLineageStatus,
    market_candidate_token,
    market_venue_token,
)
from analysis.market_institutions_identity import (
    group_markets_by_window,
    link_market_lineage,
    link_market_series,
    mint_market_token,
)
from analysis.market_institutions_policy import (
    MarketInstitutionsAnalysisPolicy,
)
from analysis.market_institutions_rows import MarketCandidateRow

pytestmark = pytest.mark.unit


def _candidate(
    *tokens: str,
    window: int = 0,
    party_count: int = 2,
) -> MarketCandidateRow:
    venue_ids = tuple(market_venue_token(token) for token in sorted(tokens))
    return MarketCandidateRow(
        market_token=market_candidate_token(venue_ids),
        window_index=window,
        venue_ids=venue_ids,
        exchange_count=2,
        distinct_party_count=party_count,
        coverage=MarketCoverage.COMPLETE,
    )


def test_mint_market_token_is_content_addressed() -> None:
    left = market_venue_token("loc-a")
    right = market_venue_token("loc-b")
    assert mint_market_token((left, right)) == market_candidate_token((left, right))
    assert mint_market_token((right, left)) == mint_market_token((left, right))


def test_continued_and_transformed() -> None:
    previous = (_candidate("loc-a", "loc-b", window=0),)
    same = (_candidate("loc-a", "loc-b", window=1),)
    continued = link_market_lineage(
        previous, same, previous_window_index=0, current_window_index=1
    )
    assert continued[0].status is MarketLineageStatus.CONTINUED
    assert continued[0].sustained is True
    assert continued[0].rerouted is False

    changed = (_candidate("loc-a", "loc-c", window=1),)
    transformed = link_market_lineage(
        previous, changed, previous_window_index=0, current_window_index=1
    )
    assert transformed[0].status is MarketLineageStatus.TRANSFORMED
    assert transformed[0].rerouted is True


def test_overlap_boundary_below_threshold_dissolves_and_emerges() -> None:
    policy = MarketInstitutionsAnalysisPolicy(lineage_overlap_milli=501)
    previous = (_candidate("loc-a", "loc-b", window=0),)
    changed = (_candidate("loc-a", "loc-c", window=1),)
    rows = link_market_lineage(
        previous,
        changed,
        policy=policy,
        previous_window_index=0,
        current_window_index=1,
    )
    statuses = {row.market_token: row.status for row in rows}
    assert MarketLineageStatus.DISSOLVED in statuses.values()
    assert MarketLineageStatus.EMERGED in statuses.values()


def test_split_and_merge() -> None:
    previous = (_candidate("loc-a", "loc-b", window=0),)
    current = (
        _candidate("loc-a", window=1),
        _candidate("loc-b", window=1),
    )
    split = link_market_lineage(
        previous, current, previous_window_index=0, current_window_index=1
    )
    assert {row.status for row in split} == {MarketLineageStatus.SPLIT}

    merged = (_candidate("loc-a", "loc-b", window=2),)
    merge = link_market_lineage(
        current,
        merged,
        previous_window_index=1,
        current_window_index=2,
    )
    assert merge[0].status is MarketLineageStatus.MERGE


def test_empty_window_produces_dissolved_then_emerged() -> None:
    grouped = (
        (_candidate("loc-a", "loc-b", window=0),),
        (),
        (_candidate("loc-a", "loc-b", window=2),),
    )
    rows = link_market_series(grouped, start_window=0)
    statuses = [row.status for row in rows]
    assert MarketLineageStatus.DISSOLVED in statuses
    assert MarketLineageStatus.EMERGED in statuses


def test_grouping_materializes_empty_windows() -> None:
    grouped = group_markets_by_window(
        (_candidate("loc-a", window=0), _candidate("loc-b", window=2)),
        first_window=0,
        last_window=2,
    )
    assert len(grouped) == 3
    assert grouped[1] == ()


def test_reversed_windows_and_duplicates_are_rejected() -> None:
    with pytest.raises(MarketInstitutionsError):
        link_market_lineage((), (), previous_window_index=1, current_window_index=0)
    duplicate = _candidate("loc-a", window=0)
    with pytest.raises(MarketInstitutionsError):
        link_market_lineage(
            (duplicate, duplicate),
            (),
            previous_window_index=0,
            current_window_index=1,
        )


def test_lineage_cap_sets_partial() -> None:
    policy = MarketInstitutionsAnalysisPolicy(max_lineage_edges=1)
    grouped = (
        (_candidate("loc-a", window=0),),
        (_candidate("loc-a", window=1),),
        (_candidate("loc-a", window=2),),
    )
    rows = link_market_series(grouped, policy=policy, start_window=0)
    assert len(rows) == 1
    assert rows[0].coverage is MarketCoverage.PARTIAL
