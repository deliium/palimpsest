# mypy: ignore-errors
"""Locked social-mobility policy defaults, ranges, and window arithmetic."""

from __future__ import annotations

import pytest

from analysis.social_mobility_contract import SocialMobilityError
from analysis.social_mobility_policy import (
    SOCIAL_MOBILITY_ANALYSIS_LOCKED_POLICY,
    SocialMobilityAnalysisPolicy,
    default_social_mobility_analysis_policy,
    validate_window_index,
    window_bounds,
    window_index_for_tick,
    with_window_end,
)

pytestmark = pytest.mark.unit


def test_locked_defaults() -> None:
    policy = default_social_mobility_analysis_policy()
    assert policy == SocialMobilityAnalysisPolicy()
    assert policy.window_ticks == 32
    assert policy.max_windows == 512
    assert policy.min_mobility_pairs == 8
    assert policy.rank_bins == 5
    assert policy.max_generation_lag == 4
    assert policy.max_lineage_depth == 8
    assert policy.max_generation_index == 32
    assert policy.persistence_share_milli == 500
    assert SOCIAL_MOBILITY_ANALYSIS_LOCKED_POLICY["window_ticks"] == 32


@pytest.mark.parametrize(
    "field,value",
    [
        ("window_ticks", 0),
        ("max_windows", 0),
        ("min_mobility_pairs", 1),
        ("rank_bins", 1),
        ("max_generation_lag", 5),
        ("max_lineage_depth", 9),
        ("max_generation_index", 33),
        ("persistence_share_milli", 1_001),
    ],
)
def test_out_of_range_values_fail_closed(field: str, value: int) -> None:
    with pytest.raises(SocialMobilityError, match=f"social_mobility_policy_{field}"):
        SocialMobilityAnalysisPolicy(**{field: value})


def test_window_arithmetic_matches_policy() -> None:
    assert window_index_for_tick(0) == 0
    assert window_index_for_tick(31) == 0
    assert window_index_for_tick(32) == 1
    assert validate_window_index(0) == 0
    assert window_bounds(2) == (64, 96)
    with pytest.raises(
        SocialMobilityError, match="social_mobility_window_out_of_range"
    ):
        window_index_for_tick(-1)
    with pytest.raises(
        SocialMobilityError, match="social_mobility_window_out_of_range"
    ):
        validate_window_index(512)


def test_with_window_end_truncates_to_last_window() -> None:
    truncated = with_window_end(95)
    assert truncated.max_windows == 3
    assert window_bounds(2, truncated) == (64, 96)
    with pytest.raises(
        SocialMobilityError, match="social_mobility_window_out_of_range"
    ):
        window_index_for_tick(96, truncated)
    with pytest.raises(
        SocialMobilityError, match="social_mobility_window_out_of_range"
    ):
        with_window_end(-1)
