# mypy: ignore-errors
"""Bounded share and episode invariants for cascade detection."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.economic_cascades_contract import (
    CascadeCoverage,
    CascadeDisruptionKind,
)
from analysis.economic_cascades_detection import detect_economic_cascade_episodes
from analysis.economic_cascades_policy import policy_with
from analysis.economic_cascades_rows import CascadeDisruptionRow, CascadeStageRow


def _stage(demand: int, completions: int, window: int) -> CascadeStageRow:
    return CascadeStageRow(
        window_index=window,
        window_tick=window * 32,
        recipe_id="mill_grain",
        action="craft",
        output_name="flour",
        output_kind="material",
        location_token="loc-1",
        demand_count=demand,
        attempt_count=demand,
        completion_count=completions,
        tool_dependent=False,
        has_infrastructure=False,
        coverage=CascadeCoverage.COMPLETE,
    )


@settings(max_examples=50, deadline=None)
@given(
    st.integers(min_value=1, max_value=64),
    st.integers(min_value=0, max_value=64),
)
def test_shortfall_share_is_bounded(demand: int, completions: int) -> None:
    capped = min(completions, demand)
    result = detect_economic_cascade_episodes(
        disruptions=[], stages=[_stage(demand, capped, 0)]
    )
    share = result.stage_rows[0].shortfall_share_milli
    assert 0 <= share <= 1_000


@settings(max_examples=50, deadline=None)
@given(st.lists(st.integers(min_value=0, max_value=5), min_size=1, max_size=10))
def test_episode_counts_reconcile_with_source_rows(windows: list[int]) -> None:
    disruptions = [
        CascadeDisruptionRow(
            window_index=window,
            window_tick=window * 32,
            sequence=index,
            kind=CascadeDisruptionKind.RESOURCE_LOSS,
            subject_token=f"harvest-{index}",
            magnitude_count=1,
            evidence_event_token=f"evt-{index}",
            coverage=CascadeCoverage.COMPLETE,
        )
        for index, window in enumerate(windows)
    ]
    result = detect_economic_cascade_episodes(
        disruptions=disruptions,
        stages=[],
        policy=policy_with(max_disruptions=100),
    )
    assert sum(item.disruption_count for item in result.episodes) == len(disruptions)
    assert result.episodes == tuple(
        sorted(
            result.episodes,
            key=lambda item: (item.window_index, item.kind.value),
        )
    )
