"""Locked V4-20 analysis contract: enums, policy, tokens, and windows."""

from __future__ import annotations

from enum import Enum

import pytest

from agents.cognition.market_institutions import (
    MARKET_INSTITUTIONS_POLICY_VERSION,
)
from analysis.market_institutions_contract import (
    MARKET_FORBIDDEN_KEYS,
    MARKET_INSTITUTIONS_ANALYSIS_POLICY_VERSION,
    MARKET_LAYER_FORBIDDEN_PREFIXES,
    MarketAlignment,
    MarketAttemptKind,
    MarketCoverage,
    MarketGatheringStatus,
    MarketInstitutionsError,
    MarketLayer,
    MarketLineageStatus,
    MarketVenueStatus,
    market_candidate_token,
    market_venue_token,
    require_market_candidate_token,
    require_market_venue_token,
)
from analysis.market_institutions_policy import (
    MarketInstitutionsAnalysisPolicy,
    default_market_institutions_analysis_policy,
    window_bounds,
    window_index_for_tick,
)

pytestmark = pytest.mark.unit


def test_policy_token_matches_cognition_contract() -> None:
    assert (
        MARKET_INSTITUTIONS_ANALYSIS_POLICY_VERSION
        == MARKET_INSTITUTIONS_POLICY_VERSION
        == "market-institutions.v1"
    )


@pytest.mark.parametrize(
    ("enum_type", "expected"),
    (
        (MarketCoverage, ("complete", "partial", "missing")),
        (
            MarketLayer,
            (
                "objective_exchange",
                "owner_expectation",
                "analytical_market",
                "comparison_view",
            ),
        ),
        (
            MarketVenueStatus,
            (
                "single_gathering",
                "recurring_gathering",
                "market_like_persistent",
                "dormant",
            ),
        ),
        (MarketGatheringStatus, ("gathering", "below_threshold")),
        (
            MarketLineageStatus,
            (
                "emerged",
                "continued",
                "transformed",
                "split",
                "merge",
                "dissolved",
            ),
        ),
        (
            MarketAlignment,
            ("consistent", "unresolved", "inconsistent", "not_applicable"),
        ),
        (MarketAttemptKind, ("offer", "counteroffer", "withdraw")),
    ),
)
def test_enum_closure(enum_type: type[Enum], expected: tuple[str, ...]) -> None:
    assert tuple(member.value for member in enum_type) == expected


def test_policy_defaults_are_locked() -> None:
    policy = default_market_institutions_analysis_policy()
    assert type(policy) is MarketInstitutionsAnalysisPolicy
    assert policy.window_ticks == 32
    assert policy.max_windows == 512
    assert policy.max_exchange_events == 200_000
    assert policy.max_attempt_rows == 200_000
    assert policy.max_venue_rows == 8_192
    assert policy.max_gathering_rows == 8_192
    assert policy.max_participation_rows == 8_192
    assert policy.max_expectation_rows == 4_096
    assert policy.max_role_rows == 4_096
    assert policy.max_record_rows == 4_096
    assert policy.max_markets == 1_024
    assert policy.max_locations == 4_096
    assert policy.max_lineage_edges == 16_384
    assert policy.max_dormant_windows_per_venue == 1
    assert policy.min_gathering_exchanges == 2
    assert policy.min_gathering_participants == 2
    assert policy.min_persistent_windows == 3
    assert policy.persistent_recurrence_milli == 500
    assert policy.broker_min_exchanges == 3
    assert policy.broker_min_counterparties == 2
    assert policy.broker_min_windows == 2
    assert policy.alignment_high_milli == 750
    assert policy.alignment_low_milli == 250
    assert policy.lineage_overlap_milli == 500


def test_policy_rejects_bool_and_out_of_range() -> None:
    with pytest.raises(MarketInstitutionsError):
        MarketInstitutionsAnalysisPolicy(window_ticks=True)
    with pytest.raises(MarketInstitutionsError):
        MarketInstitutionsAnalysisPolicy(window_ticks=0)
    with pytest.raises(MarketInstitutionsError):
        MarketInstitutionsAnalysisPolicy(alignment_low_milli=800)


def test_venue_and_market_tokens_are_stable_and_ordered() -> None:
    first = market_venue_token("loc-a")
    assert first == market_venue_token("loc-a")
    assert first.startswith("mkt-ven-")
    assert require_market_venue_token(first) == first
    left = market_venue_token("loc-a")
    right = market_venue_token("loc-b")
    assert market_candidate_token((left, right)) == market_candidate_token(
        (right, left)
    )
    token = market_candidate_token((left, right))
    assert require_market_candidate_token(token) == token
    with pytest.raises(MarketInstitutionsError):
        require_market_venue_token("mkt-ven-XYZ")
    with pytest.raises(MarketInstitutionsError):
        market_candidate_token(())


def test_window_helpers_are_bounded() -> None:
    policy = default_market_institutions_analysis_policy()
    assert window_index_for_tick(0, policy) == 0
    assert window_index_for_tick(63, policy) == 1
    assert window_bounds(1, policy) == (32, 64)
    with pytest.raises(MarketInstitutionsError):
        window_index_for_tick(-1, policy)
    with pytest.raises(MarketInstitutionsError):
        window_index_for_tick(policy.max_windows * policy.window_ticks, policy)
    with pytest.raises(MarketInstitutionsError):
        window_bounds(policy.max_windows, policy)


def test_forbidden_vocabulary_and_layer_prefixes() -> None:
    for key in ("price", "money", "credit_limit", "score", "volume", "liquidity"):
        assert key in MARKET_FORBIDDEN_KEYS
    assert MARKET_LAYER_FORBIDDEN_PREFIXES[MarketLayer.OBJECTIVE_EXCHANGE]
    assert (
        "event_token" in MARKET_LAYER_FORBIDDEN_PREFIXES[MarketLayer.ANALYTICAL_MARKET]
    )
