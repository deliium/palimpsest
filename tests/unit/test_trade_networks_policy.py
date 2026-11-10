# mypy: ignore-errors
"""Locked trade-network analysis policy values and window helpers."""

from __future__ import annotations

from dataclasses import replace

import pytest

from analysis.trade_networks_policy import (
    DEFAULT_TRADE_WINDOW_TICKS,
    TradeNetworksAnalysisPolicy,
    default_trade_networks_analysis_policy,
    window_bounds,
    window_index_for_tick,
)


def test_default_policy_values() -> None:
    policy = default_trade_networks_analysis_policy()
    assert policy.window_ticks == 32
    assert DEFAULT_TRADE_WINDOW_TICKS == 32
    assert policy.max_windows == 512
    assert policy.max_transfer_rows == 200_000
    assert policy.max_corridors == 4_096
    assert policy.max_networks == 1_024
    assert policy.max_locations == 4_096
    assert policy.max_cross_society_pairs == 2_048
    assert policy.max_lineage_edges == 16_384
    assert policy.media_min_transfers == 2
    assert policy.media_min_distinct_parties == 2
    assert policy.major_min_corridors == 2
    assert policy.major_min_transfers == 3
    assert policy.lineage_overlap_milli == 500
    assert policy.high_dependence_milli == 500


def test_policy_rejects_bool_and_out_of_range() -> None:
    with pytest.raises(ValueError, match="window_ticks"):
        TradeNetworksAnalysisPolicy(window_ticks=True)
    with pytest.raises(ValueError, match="window_ticks"):
        TradeNetworksAnalysisPolicy(window_ticks=3)
    with pytest.raises(ValueError, match="window_ticks"):
        TradeNetworksAnalysisPolicy(window_ticks=257)
    with pytest.raises(ValueError, match="max_corridors"):
        TradeNetworksAnalysisPolicy(max_corridors=0)
    with pytest.raises(ValueError, match="lineage_overlap_milli"):
        TradeNetworksAnalysisPolicy(lineage_overlap_milli=1_001)
    policy = default_trade_networks_analysis_policy()
    assert replace(policy, max_corridors=1).max_corridors == 1


def test_window_helpers_match_locked_32_tick_window() -> None:
    policy = default_trade_networks_analysis_policy()
    for tick in (0, 1, 31, 32, 33, 1_024):
        start, end = window_bounds(window_index_for_tick(tick), policy)
        assert end - start == 32
        assert start <= tick < end
    with pytest.raises(ValueError):
        window_index_for_tick(-5)
