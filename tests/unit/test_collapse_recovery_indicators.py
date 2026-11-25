# mypy: ignore-errors
"""Collapse-recovery indicator threshold and coverage tests."""

from __future__ import annotations

import pytest

from analysis.collapse_recovery_evidence import (
    CollapseBatch,
    CollapseBodyRow,
    CollapseEvidence,
    CollapseFrame,
    CollapseSourceCoverage,
    OwnerLaneState,
)
from analysis.collapse_recovery_indicators import (
    COLLAPSE_WINDOW_TICKS,
    AxisComparison,
    AxisId,
    CoverageClass,
    reduce_collapse_windows,
    signed_milli,
)
from simulation.resilience_evidence import (
    ResilienceInfrastructureRow,
    ResilienceOwnerKeys,
)

pytestmark = pytest.mark.unit


def _body(
    body_id: str, *, living: bool = True, region: str | None = None
) -> CollapseBodyRow:
    return CollapseBodyRow(
        body_id=body_id,
        agent_id=f"agent-{body_id}",
        living=living,
        region_id=region,
    )


def _frame(
    tick: int,
    bodies: tuple[CollapseBodyRow, ...],
    *,
    infra: tuple[ResilienceInfrastructureRow, ...] = (),
    owners: tuple[ResilienceOwnerKeys, ...] = (),
    infra_channel: OwnerLaneState = OwnerLaneState.OFF,
) -> CollapseFrame:
    return CollapseFrame(
        run_id="run-ind",
        config_fingerprint="cfg",
        tick=tick,
        revision=tick,
        body_projection_hash=None if tick == 0 else f"hash-{tick}",
        history_length=tick,
        infrastructure_channel=infra_channel,
        bodies=bodies,
        infrastructure=infra,
        owners=owners,
    )


def _evidence(
    *,
    ticks: int,
    bodies_by_tick: dict[int, tuple[CollapseBodyRow, ...]],
    batches: tuple[CollapseBatch, ...] = (),
    regions: tuple[str, ...] = (),
    location_regions: dict[str, str] | None = None,
    coverage: CollapseSourceCoverage | None = None,
    infra_by_tick: dict[int, tuple[ResilienceInfrastructureRow, ...]] | None = None,
    owners_by_tick: dict[int, tuple[ResilienceOwnerKeys, ...]] | None = None,
    infra_channel: OwnerLaneState = OwnerLaneState.OFF,
) -> CollapseEvidence:
    frames = tuple(
        _frame(
            tick,
            bodies_by_tick[tick],
            infra=() if infra_by_tick is None else infra_by_tick.get(tick, ()),
            owners=() if owners_by_tick is None else owners_by_tick.get(tick, ()),
            infra_channel=infra_channel,
        )
        for tick in range(ticks + 1)
    )
    if not batches:
        batches = tuple(
            CollapseBatch(
                tick=tick,
                resulting_revision=tick + 1,
                raw_event_count=0,
                receipts=(),
            )
            for tick in range(ticks)
        )
    return CollapseEvidence(
        run_id="run-ind",
        config_fingerprint="cfg",
        captured_through=ticks,
        committed_through=ticks,
        seal_reason=None,
        region_ids=regions,
        location_regions={} if location_regions is None else location_regions,
        source_coverage=coverage
        or CollapseSourceCoverage(
            regions_migration=False,
            resource_exchange=False,
            production=False,
            infrastructure=infra_channel,
        ),
        frames=frames,
        batches=batches,
    )


def test_signed_milli_floors_absolute_then_signs() -> None:
    assert signed_milli(1, 3) == 333
    assert signed_milli(-1, 3) == -333
    assert signed_milli(0, 0) is None


def test_population_stress_threshold_exact() -> None:
    # Baseline 10 living → stress at ≤7.
    bodies0 = tuple(_body(f"b{i}") for i in range(10))
    bodies32 = tuple(_body(f"b{i}", living=i < 7) for i in range(10))
    bodies64_edge = tuple(_body(f"b{i}", living=i < 7) for i in range(10))
    bodies96_clear = tuple(_body(f"b{i}", living=i < 8) for i in range(10))
    by_tick = {0: bodies0}
    for tick in range(1, 33):
        by_tick[tick] = bodies0
    for tick in range(33, 65):
        by_tick[tick] = bodies32 if tick < 64 else bodies64_edge
    for tick in range(65, 97):
        by_tick[tick] = bodies96_clear
    # Need frames through 96 for three windows; rebuild properly.
    by_tick = {}
    for tick in range(0, 33):
        by_tick[tick] = bodies0
    for tick in range(33, 65):
        by_tick[tick] = bodies32
    for tick in range(65, 97):
        by_tick[tick] = bodies96_clear
    evidence = _evidence(ticks=96, bodies_by_tick=by_tick)
    windows = reduce_collapse_windows(evidence)
    run_windows = [window for window in windows if window.scope == "run"]
    assert len(run_windows) == 3
    pop1 = next(
        axis for axis in run_windows[1].axes if axis.axis is AxisId.POPULATION_DECLINE
    )
    assert pop1.value == 7
    assert pop1.comparison is AxisComparison.STRESSED
    # Neighbor: 8/10 is not stressed.
    pop2 = next(
        axis for axis in run_windows[2].axes if axis.axis is AxisId.POPULATION_DECLINE
    )
    assert pop2.value == 8
    assert pop2.comparison is AxisComparison.NOT_STRESSED


def test_population_alone_never_enough_for_episode_context() -> None:
    bodies0 = tuple(_body(f"b{i}") for i in range(10))
    bodies_low = tuple(_body(f"b{i}", living=i < 5) for i in range(10))
    by_tick = {tick: bodies0 for tick in range(0, 33)}
    by_tick.update({tick: bodies_low for tick in range(33, 97)})
    evidence = _evidence(ticks=96, bodies_by_tick=by_tick)
    windows = [
        window for window in reduce_collapse_windows(evidence) if window.scope == "run"
    ]
    # Only population can stress; other axes unavailable/not comparable.
    for window in windows[1:]:
        stressed = [
            axis for axis in window.axes if axis.comparison is AxisComparison.STRESSED
        ]
        assert all(axis.axis is AxisId.POPULATION_DECLINE for axis in stressed)


def test_trade_channel_off_vs_enabled_empty() -> None:
    bodies = tuple(_body(f"b{i}") for i in range(5))
    by_tick = {tick: bodies for tick in range(0, 33)}
    off = _evidence(
        ticks=32,
        bodies_by_tick=by_tick,
        coverage=CollapseSourceCoverage(
            regions_migration=False,
            resource_exchange=False,
            production=False,
            infrastructure=OwnerLaneState.OFF,
        ),
    )
    on = _evidence(
        ticks=32,
        bodies_by_tick=by_tick,
        coverage=CollapseSourceCoverage(
            regions_migration=False,
            resource_exchange=True,
            production=False,
            infrastructure=OwnerLaneState.OFF,
        ),
    )
    off_trade = next(
        axis
        for axis in reduce_collapse_windows(off)[0].axes
        if axis.axis is AxisId.TRADE_DISRUPTION
    )
    on_trade = next(
        axis
        for axis in reduce_collapse_windows(on)[0].axes
        if axis.axis is AxisId.TRADE_DISRUPTION
    )
    assert off_trade.coverage is CoverageClass.UNAVAILABLE
    assert on_trade.coverage is CoverageClass.COMPLETE
    assert on_trade.value == 0


def test_infrastructure_replacement_does_not_count_as_continuity() -> None:
    bodies = tuple(_body(f"b{i}") for i in range(4))
    a1 = ResilienceInfrastructureRow(
        asset_id="asset-1",
        kind="road",
        location_id="loc-a",
        endpoint_location_id=None,
        status="operational",
    )
    a2 = ResilienceInfrastructureRow(
        asset_id="asset-2",
        kind="road",
        location_id="loc-a",
        endpoint_location_id=None,
        status="operational",
    )
    a3 = ResilienceInfrastructureRow(
        asset_id="asset-3",
        kind="road",
        location_id="loc-a",
        endpoint_location_id=None,
        status="operational",
    )
    infra0 = (a1, a2)
    infra_later = (a3, a2)  # asset-1 replaced by asset-3
    by_tick = {tick: bodies for tick in range(0, 65)}
    infra_by_tick = {tick: infra0 for tick in range(0, 33)}
    infra_by_tick.update({tick: infra_later for tick in range(33, 65)})
    evidence = _evidence(
        ticks=64,
        bodies_by_tick=by_tick,
        infra_by_tick=infra_by_tick,
        infra_channel=OwnerLaneState.COMPLETE,
        coverage=CollapseSourceCoverage(
            regions_migration=False,
            resource_exchange=False,
            production=False,
            infrastructure=OwnerLaneState.COMPLETE,
        ),
    )
    second = [
        window for window in reduce_collapse_windows(evidence) if window.scope == "run"
    ][1]
    infra = next(
        axis for axis in second.axes if axis.axis is AxisId.INFRASTRUCTURE_DECAY
    )
    assert infra.denominator == 2
    assert infra.value == 1
    assert infra.comparison is AxisComparison.STRESSED


def test_window_size_constant() -> None:
    assert COLLAPSE_WINDOW_TICKS == 32
