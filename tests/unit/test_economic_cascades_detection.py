# mypy: ignore-errors
"""Episode aggregation and quantized stage shortfalls."""

from __future__ import annotations

import pytest

from analysis.economic_cascades_contract import (
    CascadeAvailability,
    CascadeCoverage,
    CascadeDisruptionKind,
)
from analysis.economic_cascades_detection import detect_economic_cascade_episodes
from analysis.economic_cascades_policy import policy_with
from analysis.economic_cascades_rows import CascadeDisruptionRow, CascadeStageRow

pytestmark = pytest.mark.unit


def _disruption(
    *,
    window: int = 0,
    kind: CascadeDisruptionKind = CascadeDisruptionKind.RESOURCE_LOSS,
    subject: str = "harvest_grain",
    sequence: int = 1,
    magnitude: int = 1,
    coverage: CascadeCoverage = CascadeCoverage.COMPLETE,
) -> CascadeDisruptionRow:
    return CascadeDisruptionRow(
        window_index=window,
        window_tick=window * 32,
        sequence=sequence,
        kind=kind,
        subject_token=subject,
        magnitude_count=magnitude,
        evidence_event_token=f"evt-{window}-{sequence}",
        coverage=coverage,
    )


def _stage(
    *,
    window: int = 0,
    recipe: str = "mill_grain",
    demand: int = 2,
    attempts: int = 2,
    completions: int = 1,
    output_kind: str = "material",
) -> CascadeStageRow:
    return CascadeStageRow(
        window_index=window,
        window_tick=window * 32,
        recipe_id=recipe,
        action="craft",
        output_name="flour",
        output_kind=output_kind,
        location_token="loc-1",
        demand_count=demand,
        attempt_count=attempts,
        completion_count=completions,
        tool_dependent=False,
        has_infrastructure=False,
        coverage=CascadeCoverage.COMPLETE,
    )


def test_zero_demand_stage_is_retained_and_unavailable() -> None:
    result = detect_economic_cascade_episodes(
        disruptions=[], stages=[_stage(demand=0, attempts=0, completions=0)]
    )
    row = result.stage_rows[0]
    assert row.shortfall_share_milli == 0
    assert row.availability is CascadeAvailability.UNAVAILABLE
    assert row.in_shortfall is False
    assert result.coverage is CascadeCoverage.COMPLETE


def test_shortfall_threshold_is_inclusive_at_250() -> None:
    result = detect_economic_cascade_episodes(
        disruptions=[],
        stages=[
            _stage(demand=4, attempts=4, completions=3),
            _stage(recipe="harvest_grain", demand=4, attempts=4, completions=4),
        ],
    )
    by_recipe = {row.recipe_id: row for row in result.stage_rows}
    assert by_recipe["mill_grain"].shortfall_share_milli == 250
    assert by_recipe["mill_grain"].in_shortfall is True
    assert by_recipe["harvest_grain"].shortfall_share_milli == 0
    assert by_recipe["harvest_grain"].in_shortfall is False


def test_one_completion_short_of_three_rounds_to_333() -> None:
    result = detect_economic_cascade_episodes(
        disruptions=[], stages=[_stage(demand=3, attempts=3, completions=2)]
    )
    assert result.stage_rows[0].shortfall_share_milli == 333


def test_demand_without_attempts_is_insufficient_samples() -> None:
    result = detect_economic_cascade_episodes(
        disruptions=[], stages=[_stage(demand=2, attempts=0, completions=0)]
    )
    assert result.stage_rows[0].availability is CascadeAvailability.INSUFFICIENT_SAMPLES
    assert "insufficient_stage_samples" in result.notices


def test_episode_grouping_sums_counts_per_window_and_kind() -> None:
    result = detect_economic_cascade_episodes(
        disruptions=[
            _disruption(sequence=1, subject="a", magnitude=2),
            _disruption(sequence=2, subject="b", magnitude=3),
            _disruption(
                kind=CascadeDisruptionKind.POPULATION_LOSS,
                sequence=3,
                subject="body-1",
            ),
            _disruption(window=1, sequence=4, subject="c"),
        ],
        stages=[],
    )
    assert len(result.episodes) == 3
    first = result.episodes[0]
    assert first.kind is CascadeDisruptionKind.POPULATION_LOSS
    assert first.disruption_count == 1
    resource = next(
        item
        for item in result.episodes
        if item.window_index == 0
        and item.kind is CascadeDisruptionKind.RESOURCE_LOSS
    )
    assert resource.disruption_count == 2
    assert resource.magnitude_total == 5
    assert resource.subject_count == 2
    assert resource.first_sequence == 1
    assert resource.last_sequence == 2


def test_tool_shortage_proxy_emits_only_on_decline() -> None:
    result = detect_economic_cascade_episodes(
        disruptions=[],
        stages=[
            _stage(
                window=0,
                recipe="assemble_tool",
                demand=3,
                attempts=3,
                completions=3,
                output_kind="tool",
            ),
            _stage(
                window=1,
                recipe="assemble_tool",
                demand=3,
                attempts=3,
                completions=1,
                output_kind="tool",
            ),
        ],
    )
    proxy = [
        item
        for item in result.episodes
        if item.kind is CascadeDisruptionKind.TOOL_SHORTAGE
    ]
    assert len(proxy) == 1
    assert proxy[0].window_index == 1
    assert proxy[0].magnitude_total == 2
    assert result.tool_shortage_available is True


def test_tool_proxy_is_absent_without_a_tool_stage() -> None:
    result = detect_economic_cascade_episodes(
        disruptions=[], stages=[_stage(output_kind="material")]
    )
    assert result.tool_shortage_available is False
    assert not any(
        item.kind is CascadeDisruptionKind.TOOL_SHORTAGE
        for item in result.episodes
    )


def test_episode_cap_truncates_with_notice() -> None:
    result = detect_economic_cascade_episodes(
        disruptions=[
            _disruption(window=index, subject=f"s-{index}")
            for index in range(4)
        ],
        stages=[],
        policy=policy_with(max_disruptions=2),
    )
    assert len(result.episodes) <= 2
    assert "disruptions_truncated" in result.notices
    assert result.coverage is CascadeCoverage.PARTIAL
