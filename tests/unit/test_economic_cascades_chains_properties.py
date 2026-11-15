# mypy: ignore-errors
"""No back-dating, depth/lag bounds, and prefix stability for chains."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.economic_cascades_chains import link_economic_cascade_chains
from analysis.economic_cascades_contract import (
    CascadeAvailability,
    CascadeCoverage,
    CascadeDependencyKind,
    CascadeDisruptionKind,
)
from analysis.economic_cascades_detection import CascadeStageShortfall
from analysis.economic_cascades_policy import policy_with
from analysis.economic_cascades_rows import (
    CascadeDependencyEdgeRow,
    CascadeDisruptionRow,
    CascadeEpisodeRow,
    CascadeStageRow,
)


def _stage(recipe: str, window: int) -> CascadeStageShortfall:
    row = CascadeStageRow(
        window_index=window,
        window_tick=window * 32,
        recipe_id=recipe,
        action="craft",
        output_name=recipe,
        output_kind="material",
        location_token="loc-1",
        demand_count=2,
        attempt_count=2,
        completion_count=1,
        tool_dependent=False,
        has_infrastructure=False,
        coverage=CascadeCoverage.COMPLETE,
    )
    return CascadeStageShortfall(
        stage=row,
        shortfall_share_milli=500,
        in_shortfall=True,
        availability=CascadeAvailability.AVAILABLE,
    )


@settings(max_examples=50, deadline=None)
@given(
    st.integers(min_value=0, max_value=8),
    st.integers(min_value=0, max_value=8),
)
def test_chain_lag_is_never_negative_and_bounded(
    disruption_window: int, stage_window: int
) -> None:
    episode = CascadeEpisodeRow(
        window_index=disruption_window,
        window_tick=disruption_window * 32,
        kind=CascadeDisruptionKind.RESOURCE_LOSS,
        disruption_count=1,
        magnitude_total=1,
        subject_count=1,
        first_sequence=0,
        last_sequence=0,
        coverage=CascadeCoverage.COMPLETE,
    )
    result = link_economic_cascade_chains(
        episodes=[episode],
        disruptions=[
            CascadeDisruptionRow(
                window_index=disruption_window,
                window_tick=disruption_window * 32,
                sequence=0,
                kind=CascadeDisruptionKind.RESOURCE_LOSS,
                subject_token="harvest_ore",
                magnitude_count=1,
                evidence_event_token="evt-1",
                coverage=CascadeCoverage.COMPLETE,
            )
        ],
        stages=[_stage("smelt_ore", stage_window)],
        edges=[
            CascadeDependencyEdgeRow(
                window_index=stage_window,
                window_tick=stage_window * 32,
                upstream_token="harvest_ore",
                downstream_recipe_id="smelt_ore",
                kind=CascadeDependencyKind.ITEM_INPUT,
                depth=1,
                evidence_count=1,
            )
        ],
        policy=policy_with(max_propagation_lag_windows=2),
    )
    for row in result.chains:
        assert row.lag_windows >= 0
        assert row.lag_windows <= 2
        if row.state.value == "linked":
            assert row.window_index >= disruption_window


@settings(max_examples=50, deadline=None)
@given(st.integers(min_value=1, max_value=4))
def test_chain_prefix_is_stable_under_truncation(cap: int) -> None:
    recipe_ids = ["a", "b", "c", "d"]
    edges = [
        CascadeDependencyEdgeRow(
            window_index=0,
            window_tick=0,
            upstream_token="harvest_ore",
            downstream_recipe_id=recipe_id,
            kind=CascadeDependencyKind.ITEM_INPUT,
            depth=1,
            evidence_count=1,
        )
        for recipe_id in recipe_ids
    ]
    episode = CascadeEpisodeRow(
        window_index=0,
        window_tick=0,
        kind=CascadeDisruptionKind.RESOURCE_LOSS,
        disruption_count=1,
        magnitude_total=1,
        subject_count=1,
        first_sequence=0,
        last_sequence=0,
        coverage=CascadeCoverage.COMPLETE,
    )
    disruption = CascadeDisruptionRow(
        window_index=0,
        window_tick=0,
        sequence=0,
        kind=CascadeDisruptionKind.RESOURCE_LOSS,
        subject_token="harvest_ore",
        magnitude_count=1,
        evidence_event_token="evt-1",
        coverage=CascadeCoverage.COMPLETE,
    )
    full = link_economic_cascade_chains(
        episodes=[episode],
        disruptions=[disruption],
        stages=[_stage(recipe_id, 0) for recipe_id in recipe_ids],
        edges=edges,
        policy=policy_with(max_chains=10),
    )
    truncated = link_economic_cascade_chains(
        episodes=[episode],
        disruptions=[disruption],
        stages=[_stage(recipe_id, 0) for recipe_id in recipe_ids],
        edges=edges,
        policy=policy_with(max_chains=cap),
    )
    assert [row.chain_token for row in truncated.chains] == [
        row.chain_token for row in full.chains[:cap]
    ]
