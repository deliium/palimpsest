# mypy: ignore-errors
"""Physical/network resilience reducer arithmetic and censoring."""

from __future__ import annotations

from analysis.resilience_physical import PhysicalReduceInputs, reduce_physical
from analysis.resilience_windows import (
    ShockReceipt,
    WindowCoverage,
    WindowReason,
    build_shock_windows,
)
from simulation.resilience_evidence import (
    OwnerLaneState,
    ResilienceBatchEvents,
    ResilienceBodyRow,
    ResilienceBoundaryFacts,
    ResilienceDeathRow,
    ResilienceExchangeRow,
    ResilienceInfrastructureRow,
    ResilienceJourneyArrivalRow,
    ResilienceStockRow,
)

pytestmark = __import__("pytest").mark.unit


def _frame(
    boundary: int,
    *,
    bodies: tuple[ResilienceBodyRow, ...] = (),
    stocks: tuple[ResilienceStockRow, ...] = (),
    infrastructure: tuple[ResilienceInfrastructureRow, ...] = (),
    ecology: OwnerLaneState = OwnerLaneState.COMPLETE,
    infra: OwnerLaneState = OwnerLaneState.OFF,
) -> ResilienceBoundaryFacts:
    return ResilienceBoundaryFacts(
        run_id="run-a",
        config_fingerprint="fp",
        boundary_tick=boundary,
        revision=boundary,
        body_projection_hash=None if boundary == 0 else "a" * 64,
        history_length=0,
        infrastructure_channel=infra,
        ecology_channel=ecology,
        bodies=bodies,
        stocks=stocks,
        infrastructure=infrastructure,
        owners=(),
    )


def _body(body_id: str, *, living: bool = True, held: int = 0) -> ResilienceBodyRow:
    return ResilienceBodyRow(
        body_id=body_id,
        agent_id=f"agent-{body_id}",
        living=living,
        held_item_count=held,
        region_id=None,
    )


def _windows_for(shock_tick: int, *, through: int) -> tuple:
    built = build_shock_windows(
        (
            ShockReceipt(
                tick=shock_tick,
                sequence=0,
                event_id="shock",
                kind="drought",
                origin="spontaneous",
                outcome="applied",
                rule_id="r1",
            ),
        ),
        run_id="run-a",
        finalized_through=through,
        capture_through=through,
        schedule=(),
    )
    return built.episodes[0], built.episodes[0].windows


def test_population_entries_deaths_and_baseline_ratio() -> None:
    episode, windows = _windows_for(8, through=80)
    frames = {
        0: _frame(0, bodies=(_body("a"), _body("b"))),
        8: _frame(8, bodies=(_body("a"), _body("b"))),
        16: _frame(16, bodies=(_body("a"), _body("c"))),
    }
    batches = (
        ResilienceBatchEvents(
            tick=10,
            resulting_revision=11,
            deaths=(
                ResilienceDeathRow(
                    event_id="d1", tick=10, sequence=0, body_id="b"
                ),
            ),
            journey_arrivals=(),
            helps=(),
            feeds=(),
            contributions=(),
            exchanges=(),
            shock_receipts=(),
            event_count=1,
        ),
    )
    inputs = PhysicalReduceInputs(
        frames_by_boundary=frames,
        batches=batches,
        regions_migration_enabled=False,
        subjective_valuation_enabled=False,
        location_regions={},
    )
    panels = reduce_physical(inputs, episode, windows)
    pop = panels[0]
    post0 = pop.windows[1]
    assert post0.status is WindowCoverage.COMPLETE
    by_metric = {m.metric: m for m in post0.measures if m.scope is None}
    assert by_metric["living"].value == 2
    assert by_metric["deaths"].value == 1
    assert by_metric["entries"].value == 1  # c new vs boundary 8
    assert by_metric["living_vs_baseline_milli"].value == 1000


def test_migration_disabled_and_direction_counts() -> None:
    episode, windows = _windows_for(8, through=80)
    frames = {b: _frame(b, bodies=(_body("a"),)) for b in range(0, 81, 8)}
    off = PhysicalReduceInputs(
        frames_by_boundary=frames,
        batches=(),
        regions_migration_enabled=False,
        subjective_valuation_enabled=False,
        location_regions={},
    )
    mig_off = reduce_physical(off, episode, windows)[1].windows[1]
    assert mig_off.status is WindowCoverage.UNAVAILABLE

    batches = (
        ResilienceBatchEvents(
            tick=9,
            resulting_revision=10,
            deaths=(),
            journey_arrivals=(
                ResilienceJourneyArrivalRow(
                    event_id="j1",
                    tick=9,
                    sequence=0,
                    journey_id="jour-1",
                    body_id="a",
                    origin_region_id="north",
                    destination_region_id="south",
                ),
                # Duplicate (journey, body) must not double-count.
                ResilienceJourneyArrivalRow(
                    event_id="j1",
                    tick=9,
                    sequence=0,
                    journey_id="jour-1",
                    body_id="a",
                    origin_region_id="north",
                    destination_region_id="south",
                ),
                ResilienceJourneyArrivalRow(
                    event_id="j2",
                    tick=9,
                    sequence=1,
                    journey_id="jour-2",
                    body_id="a",
                    origin_region_id="north",
                    destination_region_id="south",
                ),
            ),
            helps=(),
            feeds=(),
            contributions=(),
            exchanges=(),
            shock_receipts=(),
            event_count=1,
        ),
    )
    on = PhysicalReduceInputs(
        frames_by_boundary=frames,
        batches=batches,
        regions_migration_enabled=True,
        subjective_valuation_enabled=False,
        location_regions={},
    )
    mig = reduce_physical(on, episode, windows)[1].windows[1]
    totals = {m.metric: m for m in mig.measures if m.scope is None}
    assert totals["cross_region_arrivals"].value == 2
    assert totals["unique_arrivals"].value == 1


def test_resource_groups_and_immediate_dip() -> None:
    episode, windows = _windows_for(8, through=80)
    def stock(qty, cap, kind="water", unit="units", sid="s1"):
        return ResilienceStockRow(
            stock_id=sid,
            resource_kind=kind,
            unit=unit,
            quantity_tenths=qty,
            effective_capacity_tenths=cap,
        )
    frames = {
        8: _frame(8, stocks=(stock(40, 40),)),
        9: _frame(9, stocks=(stock(20, 40),)),
        16: _frame(16, stocks=(stock(40, 40),)),
    }
    for b in range(0, 81):
        frames.setdefault(b, _frame(b, stocks=(stock(40, 40),)))
    frames[9] = _frame(9, stocks=(stock(20, 40),))
    frames[16] = _frame(16, stocks=(stock(40, 40),))
    inputs = PhysicalReduceInputs(
        frames_by_boundary=frames,
        batches=(),
        regions_migration_enabled=False,
        subjective_valuation_enabled=False,
        location_regions={},
    )
    panels = reduce_physical(inputs, episode, windows)
    res = panels[2]
    assert res.immediate is not None
    qty = next(m for m in res.immediate.measures if m.metric == "quantity_tenths")
    assert qty.value == 20
    assert qty.delta_from_baseline == -20
    post0_qty = next(
        m for m in res.windows[1].measures if m.metric == "quantity_tenths"
    )
    assert post0_qty.value == 40
    assert post0_qty.delta_from_baseline == 0


def test_trade_first_seen_and_missing_venue_partial() -> None:
    episode, windows = _windows_for(8, through=80)
    frames = {b: _frame(b) for b in range(0, 81, 8)}
    batches = (
        ResilienceBatchEvents(
            tick=9,
            resulting_revision=10,
            deaths=(),
            journey_arrivals=(),
            helps=(),
            feeds=(),
            contributions=(),
            exchanges=(
                ResilienceExchangeRow(
                    event_id="e1",
                    tick=9,
                    sequence=0,
                    venue_location_id="loc-a",
                    item_ids=("item-1",),
                ),
            ),
            shock_receipts=(),
            event_count=1,
        ),
        ResilienceBatchEvents(
            tick=15,
            resulting_revision=16,
            deaths=(),
            journey_arrivals=(),
            helps=(),
            feeds=(),
            contributions=(),
            exchanges=(
                ResilienceExchangeRow(
                    event_id="e2",
                    tick=15,
                    sequence=0,
                    venue_location_id=None,
                    item_ids=("item-1",),
                ),
            ),
            shock_receipts=(),
            event_count=1,
        ),
    )
    inputs = PhysicalReduceInputs(
        frames_by_boundary=frames,
        batches=batches,
        regions_migration_enabled=False,
        subjective_valuation_enabled=True,
        location_regions={},
    )
    trade = reduce_physical(inputs, episode, windows)[3]
    assert trade.windows[1].status is WindowCoverage.PARTIAL
    assert trade.windows[1].reason is WindowReason.PROJECTION_GAP


def test_infrastructure_destroyed_vs_replacement() -> None:
    episode, windows = _windows_for(8, through=80)
    base_asset = ResilienceInfrastructureRow(
        asset_id="infra-1",
        kind="well",
        location_id="loc-a",
        endpoint_location_id=None,
        status="operational",
    )
    destroyed = ResilienceInfrastructureRow(
        asset_id="infra-1",
        kind="well",
        location_id="loc-a",
        endpoint_location_id=None,
        status="destroyed",
    )
    replacement = ResilienceInfrastructureRow(
        asset_id="infra-2",
        kind="well",
        location_id="loc-a",
        endpoint_location_id=None,
        status="operational",
    )
    frames = {
        8: _frame(8, infrastructure=(base_asset,), infra=OwnerLaneState.COMPLETE),
        16: _frame(
            16,
            infrastructure=(destroyed, replacement),
            infra=OwnerLaneState.COMPLETE,
        ),
    }
    for b in range(0, 81, 8):
        frames.setdefault(
            b, _frame(b, infrastructure=(base_asset,), infra=OwnerLaneState.COMPLETE)
        )
    frames[16] = _frame(
        16, infrastructure=(destroyed, replacement), infra=OwnerLaneState.COMPLETE
    )
    inputs = PhysicalReduceInputs(
        frames_by_boundary=frames,
        batches=(),
        regions_migration_enabled=False,
        subjective_valuation_enabled=False,
        location_regions={},
    )
    infra = reduce_physical(inputs, episode, windows)[4].windows[1]
    by_metric = {m.metric: m for m in infra.measures}
    assert by_metric["operational_assets"].value == 1
    assert by_metric["baseline_assets"].value == 1
    assert by_metric["baseline_assets_operational"].value == 0
    assert by_metric["new_operational_assets"].value == 1
    assert by_metric["baseline_slots_reoccupied_by_new_assets"].value == 1
