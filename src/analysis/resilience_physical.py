"""Pure physical/network resilience reducers."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.resilience_series import (
    Measure,
    MeasureScope,
    ResilienceDimension,
    SeriesCell,
    SeriesPanel,
    cell_from_window,
    floor_milli,
    measure_delta,
    sort_measures,
)
from analysis.resilience_windows import (
    ResilienceError,
    ShockEpisode,
    WindowCoverage,
    WindowReason,
    WindowSpec,
)
from simulation.resilience_evidence import (
    OwnerLaneState,
    ResilienceBatchEvents,
    ResilienceBoundaryFacts,
    ResilienceExchangeRow,
    ResilienceInfrastructureRow,
    ResilienceJourneyArrivalRow,
    ResilienceStockRow,
)

__all__ = [
    "PhysicalReduceInputs",
    "reduce_physical",
]

_OPERATIONAL: Final[str] = "operational"


@dataclass(frozen=True, slots=True)
class PhysicalReduceInputs:
    """Trusted sealed prefix facts for physical/network lanes."""

    frames_by_boundary: Mapping[int, ResilienceBoundaryFacts]
    batches: tuple[ResilienceBatchEvents, ...]
    regions_migration_enabled: bool
    subjective_valuation_enabled: bool
    location_regions: Mapping[str, str]

    def __post_init__(self) -> None:
        if type(self.regions_migration_enabled) is not bool:
            raise ResilienceError("resilience_invalid_input")
        if type(self.subjective_valuation_enabled) is not bool:
            raise ResilienceError("resilience_invalid_input")
        if type(self.batches) is not tuple:
            raise ResilienceError("resilience_invalid_input")


def reduce_physical(
    inputs: PhysicalReduceInputs,
    episode: ShockEpisode,
    windows: Sequence[WindowSpec],
) -> tuple[SeriesPanel, ...]:
    """Reduce the five physical/network dimensions for one episode."""

    if type(inputs) is not PhysicalReduceInputs:
        raise ResilienceError("resilience_invalid_input")
    if type(episode) is not ShockEpisode:
        raise ResilienceError("resilience_invalid_input")
    if len(windows) != 9:
        raise ResilienceError("resilience_invalid_input")

    population = _reduce_population(inputs, episode, windows)
    migration = _reduce_migration(inputs, episode, windows)
    resources = _reduce_resources(inputs, episode, windows)
    trade = _reduce_trade(inputs, episode, windows)
    infrastructure = _reduce_infrastructure(inputs, episode, windows)
    return (population, migration, resources, trade, infrastructure)


def _frame(
    inputs: PhysicalReduceInputs, boundary: int
) -> ResilienceBoundaryFacts | None:
    return inputs.frames_by_boundary.get(boundary)


def _batches_in(
    inputs: PhysicalReduceInputs, start: int, end: int
) -> tuple[ResilienceBatchEvents, ...]:
    return tuple(
        batch for batch in inputs.batches if start <= batch.tick < end
    )


def _unavailable_panel(
    dimension: ResilienceDimension,
    windows: Sequence[WindowSpec],
    *,
    reason: WindowReason,
) -> SeriesPanel:
    # Preserve structural censor/partial; only override complete→unavailable.
    rebuilt: list[SeriesCell] = []
    for window in windows:
        if window.coverage is WindowCoverage.COMPLETE:
            rebuilt.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.UNAVAILABLE,
                    reason=reason,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
        else:
            rebuilt.append(cell_from_window(window, measures=()))
    return SeriesPanel(dimension=dimension, windows=tuple(rebuilt), immediate=None)


def _reduce_population(
    inputs: PhysicalReduceInputs,
    episode: ShockEpisode,
    windows: Sequence[WindowSpec],
) -> SeriesPanel:
    baseline_window = windows[0]
    baseline_living: int | None = None
    if baseline_window.coverage is WindowCoverage.COMPLETE:
        frame = _frame(inputs, baseline_window.end_tick)
        if frame is not None:
            baseline_living = sum(1 for body in frame.bodies if body.living)

    cells: list[SeriesCell] = []
    for window in windows:
        if window.coverage is not WindowCoverage.COMPLETE:
            cells.append(cell_from_window(window, measures=()))
            continue
        end_frame = _frame(inputs, window.end_tick)
        if end_frame is None:
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.PARTIAL,
                    reason=WindowReason.PROJECTION_GAP,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
            continue
        living = sum(1 for body in end_frame.bodies if body.living)
        deaths = _count_deaths(inputs, window.start_tick, window.end_tick)
        entries = _count_entries(inputs, window.start_tick, window.end_tick)
        vs_baseline = None
        if window.baseline_relative_allowed and baseline_living is not None:
            vs_baseline = floor_milli(living, baseline_living)
        delta_living = measure_delta(
            living,
            baseline_living,
            allowed=window.baseline_relative_allowed,
        )
        measures = sort_measures(
            (
                Measure(
                    metric="living",
                    unit="count",
                    value=living,
                    delta_from_baseline=delta_living,
                ),
                Measure(metric="entries", unit="count", value=entries),
                Measure(metric="deaths", unit="count", value=deaths),
                Measure(
                    metric="living_vs_baseline_milli",
                    unit="milli",
                    value=vs_baseline,
                    numerator=living if baseline_living is not None else None,
                    denominator=baseline_living,
                    reason=(
                        None
                        if vs_baseline is not None
                        else "baseline_zero_or_invalid"
                    ),
                ),
            )
        )
        cells.append(cell_from_window(window, measures=measures))

    immediate = _immediate_population(inputs, episode)
    return SeriesPanel(
        dimension=ResilienceDimension.POPULATION_RECOVERY,
        windows=tuple(cells),
        immediate=immediate,
    )


def _count_deaths(inputs: PhysicalReduceInputs, start: int, end: int) -> int:
    seen: set[str] = set()
    for batch in _batches_in(inputs, start, end):
        for row in batch.deaths:
            seen.add(row.body_id)
    return len(seen)


def _count_entries(inputs: PhysicalReduceInputs, start: int, end: int) -> int:
    """First appearance of a registered body in (start, end] relative to start frame."""

    if start < 0:
        start_ids: set[str] = set()
    else:
        start_frame = _frame(inputs, max(0, start))
        start_ids = (
            set()
            if start_frame is None
            else {b.body_id for b in start_frame.bodies}
        )
    end_frame = _frame(inputs, end)
    if end_frame is None:
        return 0
    return sum(1 for body in end_frame.bodies if body.body_id not in start_ids)


def _immediate_population(
    inputs: PhysicalReduceInputs, episode: ShockEpisode
) -> SeriesCell:
    point = episode.immediate
    if point.coverage is not WindowCoverage.COMPLETE:
        return SeriesCell(
            window_index=None,
            status=point.coverage,
            reason=point.reason,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    current = _frame(inputs, point.boundary)
    prior = _frame(inputs, point.preceding_boundary)
    if current is None:
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.PARTIAL,
            reason=WindowReason.PROJECTION_GAP,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    living = sum(1 for body in current.bodies if body.living)
    prior_living = (
        None
        if prior is None
        else sum(1 for body in prior.bodies if body.living)
    )
    return SeriesCell(
        window_index=None,
        status=WindowCoverage.COMPLETE,
        reason=None,
        expected_ticks=0,
        observed_ticks=0,
        measures=sort_measures(
            (
                Measure(
                    metric="living",
                    unit="count",
                    value=living,
                    delta_from_baseline=measure_delta(
                        living, prior_living, allowed=point.deltas_allowed
                    ),
                ),
            )
        ),
    )


def _reduce_migration(
    inputs: PhysicalReduceInputs,
    episode: ShockEpisode,
    windows: Sequence[WindowSpec],
) -> SeriesPanel:
    del episode
    if not inputs.regions_migration_enabled:
        return _unavailable_panel(
            ResilienceDimension.MIGRATION,
            windows,
            reason=WindowReason.CHANNEL_OFF,
        )
    baseline_complete = windows[0].coverage is WindowCoverage.COMPLETE
    baseline_dirs = (
        _migration_counts(inputs, windows[0].start_tick, windows[0].end_tick)
        if baseline_complete
        else {}
    )
    cells: list[SeriesCell] = []
    for window in windows:
        if window.coverage is not WindowCoverage.COMPLETE:
            cells.append(cell_from_window(window, measures=()))
            continue
        counts, gap = _migration_counts_with_gap(
            inputs, window.start_tick, window.end_tick
        )
        if gap:
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.PARTIAL,
                    reason=WindowReason.PROJECTION_GAP,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
            continue
        measures = _migration_measures(
            counts,
            baseline_dirs if window.baseline_relative_allowed else None,
        )
        cells.append(cell_from_window(window, measures=measures))
    return SeriesPanel(
        dimension=ResilienceDimension.MIGRATION,
        windows=tuple(cells),
        immediate=None,
    )


def _migration_counts(
    inputs: PhysicalReduceInputs, start: int, end: int
) -> dict[tuple[str, str], tuple[int, set[str]]]:
    counts, _gap = _migration_counts_with_gap(inputs, start, end)
    return counts


def _migration_counts_with_gap(
    inputs: PhysicalReduceInputs, start: int, end: int
) -> tuple[dict[tuple[str, str], tuple[int, set[str]]], bool]:
    buckets: dict[tuple[str, str], tuple[int, set[str]]] = {}
    seen_pairs: set[tuple[str, str]] = set()
    gap = False
    for batch in _batches_in(inputs, start, end):
        for row in batch.journey_arrivals:
            origin, dest, row_gap = _regions_for_arrival(row)
            if row_gap:
                gap = True
                continue
            if origin is None or dest is None or origin == dest:
                continue
            pair = (row.journey_id, row.body_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            key = (origin, dest)
            count, bodies = buckets.get(key, (0, set()))
            bodies = set(bodies)
            bodies.add(row.body_id)
            buckets[key] = (count + 1, bodies)
    return buckets, gap


def _regions_for_arrival(
    row: ResilienceJourneyArrivalRow,
) -> tuple[str | None, str | None, bool]:
    if row.origin_region_id is not None and row.destination_region_id is not None:
        return row.origin_region_id, row.destination_region_id, False
    # Unmappable endpoint is a projection gap, not same-region movement.
    return None, None, True


def _migration_measures(
    counts: dict[tuple[str, str], tuple[int, set[str]]],
    baseline: dict[tuple[str, str], tuple[int, set[str]]] | None,
) -> tuple[Measure, ...]:
    measures: list[Measure] = []
    total_arrivals = sum(count for count, _ in counts.values())
    unique = {body for _, bodies in counts.values() for body in bodies}
    measures.append(
        Measure(metric="cross_region_arrivals", unit="count", value=total_arrivals)
    )
    measures.append(
        Measure(metric="unique_arrivals", unit="count", value=len(unique))
    )
    keys = sorted(set(counts) | (set(baseline) if baseline is not None else set()))
    for origin, dest in keys:
        scope = MeasureScope(kind="region_direction", key=f"{origin}>{dest}")
        cur_count, cur_bodies = counts.get((origin, dest), (0, set()))
        base_count = (
            None
            if baseline is None
            else baseline.get((origin, dest), (0, set()))[0]
        )
        measures.append(
            Measure(
                metric="cross_region_arrivals",
                unit="count",
                value=cur_count,
                scope=scope,
                delta_from_baseline=measure_delta(
                    cur_count, base_count, allowed=baseline is not None
                ),
            )
        )
        measures.append(
            Measure(
                metric="unique_arrivals",
                unit="count",
                value=len(cur_bodies),
                scope=scope,
            )
        )
    return sort_measures(tuple(measures))


def _reduce_resources(
    inputs: PhysicalReduceInputs,
    episode: ShockEpisode,
    windows: Sequence[WindowSpec],
) -> SeriesPanel:
    sample = next(iter(inputs.frames_by_boundary.values()), None)
    if sample is None or sample.ecology_channel is OwnerLaneState.OFF:
        return _unavailable_panel(
            ResilienceDimension.RESOURCE_RECOVERY,
            windows,
            reason=WindowReason.CHANNEL_OFF,
        )
    baseline_groups = None
    if windows[0].coverage is WindowCoverage.COMPLETE:
        baseline_frame = _frame(inputs, windows[0].end_tick)
        if baseline_frame is not None:
            baseline_groups = _stock_groups(baseline_frame.stocks)

    cells: list[SeriesCell] = []
    for window in windows:
        if window.coverage is not WindowCoverage.COMPLETE:
            cells.append(cell_from_window(window, measures=()))
            continue
        frame = _frame(inputs, window.end_tick)
        if frame is None or frame.ecology_channel is not OwnerLaneState.COMPLETE:
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.PARTIAL,
                    reason=WindowReason.PROJECTION_GAP,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
            continue
        current = _stock_groups(frame.stocks)
        partial = False
        if baseline_groups is not None and window.baseline_relative_allowed:
            for key, base_row in baseline_groups.items():
                cur = current.get(key)
                if cur is None or cur[3] != base_row[3]:
                    # missing/retyped baseline ID or unit mismatch
                    partial = True
                    break
        if partial:
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.PARTIAL,
                    reason=WindowReason.PROJECTION_GAP,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
            continue
        measures = _resource_measures(
            current,
            baseline_groups if window.baseline_relative_allowed else None,
        )
        cells.append(cell_from_window(window, measures=measures))

    immediate = _immediate_resources(inputs, episode)
    return SeriesPanel(
        dimension=ResilienceDimension.RESOURCE_RECOVERY,
        windows=tuple(cells),
        immediate=immediate,
    )


def _stock_groups(
    stocks: Sequence[ResilienceStockRow],
) -> dict[tuple[str, str], tuple[int, int, int, frozenset[str]]]:
    """Map (kind, unit) -> (nodes, quantity, capacity, stock_ids)."""

    groups: dict[tuple[str, str], tuple[int, int, int, frozenset[str]]] = {}
    for row in stocks:
        key = (row.resource_kind, row.unit)
        nodes, qty, cap, ids = groups.get(key, (0, 0, 0, frozenset()))
        groups[key] = (
            nodes + 1,
            qty + row.quantity_tenths,
            cap + row.effective_capacity_tenths,
            ids | frozenset({row.stock_id}),
        )
    return groups


def _resource_measures(
    current: dict[tuple[str, str], tuple[int, int, int, frozenset[str]]],
    baseline: dict[tuple[str, str], tuple[int, int, int, frozenset[str]]] | None,
) -> tuple[Measure, ...]:
    measures: list[Measure] = []
    keys = sorted(set(current) | (set(baseline) if baseline else set()))
    for kind, unit in keys:
        scope = MeasureScope(kind="stock_group", key=f"{kind}|{unit}")
        nodes, qty, cap, _ids = current.get((kind, unit), (0, 0, 0, frozenset()))
        base = None if baseline is None else baseline.get((kind, unit))
        measures.extend(
            (
                Measure(
                    metric="managed_nodes",
                    unit="count",
                    value=nodes,
                    scope=scope,
                    delta_from_baseline=measure_delta(
                        nodes,
                        None if base is None else base[0],
                        allowed=base is not None,
                    ),
                ),
                Measure(
                    metric="quantity_tenths",
                    unit="tenths",
                    value=qty,
                    scope=scope,
                    delta_from_baseline=measure_delta(
                        qty, None if base is None else base[1], allowed=base is not None
                    ),
                ),
                Measure(
                    metric="effective_capacity_tenths",
                    unit="tenths",
                    value=cap,
                    scope=scope,
                    delta_from_baseline=measure_delta(
                        cap, None if base is None else base[2], allowed=base is not None
                    ),
                ),
            )
        )
    return sort_measures(tuple(measures))


def _immediate_resources(
    inputs: PhysicalReduceInputs, episode: ShockEpisode
) -> SeriesCell:
    point = episode.immediate
    if point.coverage is not WindowCoverage.COMPLETE:
        return SeriesCell(
            window_index=None,
            status=point.coverage,
            reason=point.reason,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    current = _frame(inputs, point.boundary)
    prior = _frame(inputs, point.preceding_boundary)
    if current is None or current.ecology_channel is OwnerLaneState.OFF:
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.UNAVAILABLE,
            reason=WindowReason.CHANNEL_OFF,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    if current.ecology_channel is not OwnerLaneState.COMPLETE:
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.PARTIAL,
            reason=WindowReason.PROJECTION_GAP,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    cur_groups = _stock_groups(current.stocks)
    prior_groups = (
        None
        if prior is None or not point.deltas_allowed
        else _stock_groups(prior.stocks)
    )
    return SeriesCell(
        window_index=None,
        status=WindowCoverage.COMPLETE,
        reason=None,
        expected_ticks=0,
        observed_ticks=0,
        measures=_resource_measures(cur_groups, prior_groups),
    )


def _reduce_trade(
    inputs: PhysicalReduceInputs,
    episode: ShockEpisode,
    windows: Sequence[WindowSpec],
) -> SeriesPanel:
    del episode
    if not inputs.subjective_valuation_enabled:
        return _unavailable_panel(
            ResilienceDimension.TRADE_NETWORK_RECOVERY,
            windows,
            reason=WindowReason.CHANNEL_OFF,
        )
    # Build visit history once over verified prefix.
    history = _trade_history(inputs)
    baseline_edges: frozenset[tuple[str, str]] | None = None
    if windows[0].coverage is WindowCoverage.COMPLETE:
        summary = _trade_window_summary(
            history, windows[0].start_tick, windows[0].end_tick
        )
        if summary is not None and summary.complete:
            baseline_edges = frozenset(summary.edges)

    cells: list[SeriesCell] = []
    for window in windows:
        if window.coverage is not WindowCoverage.COMPLETE:
            cells.append(cell_from_window(window, measures=()))
            continue
        summary = _trade_window_summary(history, window.start_tick, window.end_tick)
        if summary is None or not summary.complete:
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.PARTIAL,
                    reason=WindowReason.PROJECTION_GAP,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
            continue
        base = baseline_edges if window.baseline_relative_allowed else None
        active_baseline = (
            0 if base is None else sum(1 for edge in base if edge in summary.edges)
        )
        share = None if base is None else floor_milli(active_baseline, len(base))
        measures = sort_measures(
            (
                Measure(
                    metric="completed_exchanges",
                    unit="count",
                    value=summary.exchanges,
                ),
                Measure(
                    metric="resolved_corridor_item_visits",
                    unit="count",
                    value=summary.resolved_visits,
                ),
                Measure(
                    metric="first_seen_item_visits",
                    unit="count",
                    value=summary.first_seen,
                ),
                Measure(
                    metric="active_corridors",
                    unit="count",
                    value=len(summary.edges),
                ),
                Measure(
                    metric="baseline_corridors",
                    unit="count",
                    value=None if base is None else len(base),
                ),
                Measure(
                    metric="baseline_corridors_active",
                    unit="count",
                    value=None if base is None else active_baseline,
                ),
                Measure(
                    metric="baseline_corridor_share_milli",
                    unit="milli",
                    value=share,
                    numerator=None if base is None else active_baseline,
                    denominator=None if base is None else len(base),
                ),
            )
        )
        cells.append(cell_from_window(window, measures=measures))
    return SeriesPanel(
        dimension=ResilienceDimension.TRADE_NETWORK_RECOVERY,
        windows=tuple(cells),
        immediate=None,
    )


@dataclass(frozen=True, slots=True)
class _TradeSummary:
    exchanges: int
    resolved_visits: int
    first_seen: int
    edges: frozenset[tuple[str, str]]
    complete: bool


@dataclass
class _TradeCursor:
    # item_id -> ("unseen",) | ("known", venue) | ("unknown_venue",)
    state: dict[str, tuple[str, str | None]]
    tainted_unknown: set[str]


def _trade_history(
    inputs: PhysicalReduceInputs,
) -> tuple[tuple[int, ResilienceExchangeRow], ...]:
    rows: list[tuple[int, ResilienceExchangeRow]] = []
    for batch in sorted(inputs.batches, key=lambda item: (item.tick,)):
        for exchange in batch.exchanges:
            rows.append((batch.tick, exchange))
    return tuple(rows)


def _trade_window_summary(
    history: tuple[tuple[int, ResilienceExchangeRow], ...],
    start: int,
    end: int,
) -> _TradeSummary | None:
    cursor = _TradeCursor(state={}, tainted_unknown=set())
    # Replay from beginning to start (no look-ahead into window).
    for tick, exchange in history:
        if tick >= start:
            break
        _apply_exchange(cursor, exchange, accumulate=None)
    exchanges = 0
    resolved = 0
    first_seen = 0
    edges: set[tuple[str, str]] = set()
    complete = True

    def accumulate(kind: str, *, edge: tuple[str, str] | None = None) -> None:
        nonlocal resolved, first_seen
        if kind == "resolved":
            resolved += 1
        elif kind == "first":
            first_seen += 1
        elif kind == "edge" and edge is not None:
            edges.add(edge)

    for tick, exchange in history:
        if tick < start:
            continue
        if tick >= end:
            break
        exchanges += 1
        before_partial = bool(cursor.tainted_unknown)
        ok = _apply_exchange(cursor, exchange, accumulate=accumulate)
        if not ok or (
            cursor.tainted_unknown
            and not before_partial
            and exchange.venue_location_id is None
        ):
            complete = False
        if exchange.venue_location_id is None:
            complete = False
    return _TradeSummary(
        exchanges=exchanges,
        resolved_visits=resolved,
        first_seen=first_seen,
        edges=frozenset(edges),
        complete=complete,
    )


def _apply_exchange(
    cursor: _TradeCursor,
    exchange: ResilienceExchangeRow,
    *,
    accumulate: (
        Callable[..., None] | None
    ),
) -> bool:
    venue = exchange.venue_location_id
    ok = True
    for item_id in exchange.item_ids:
        prior = cursor.state.get(item_id, ("unseen", None))
        if venue is None:
            cursor.state[item_id] = ("unknown_venue", None)
            cursor.tainted_unknown.add(item_id)
            ok = False
            continue
        if item_id in cursor.tainted_unknown and prior[0] == "unknown_venue":
            # Next known visit after missing venue: mark partial, no first/edge,
            # reset predecessor to known.
            cursor.state[item_id] = ("known", venue)
            cursor.tainted_unknown.discard(item_id)
            ok = False
            continue
        if prior[0] == "unseen":
            cursor.state[item_id] = ("known", venue)
            if accumulate is not None:
                accumulate("first")
            continue
        if prior[0] == "known" and prior[1] is not None and prior[1] != venue:
            cursor.state[item_id] = ("known", venue)
            if accumulate is not None:
                accumulate("resolved")
                accumulate("edge", edge=(prior[1], venue))
            continue
        cursor.state[item_id] = ("known", venue)
    return ok


def _reduce_infrastructure(
    inputs: PhysicalReduceInputs,
    episode: ShockEpisode,
    windows: Sequence[WindowSpec],
) -> SeriesPanel:
    sample = next(iter(inputs.frames_by_boundary.values()), None)
    if sample is None or sample.infrastructure_channel is OwnerLaneState.OFF:
        return _unavailable_panel(
            ResilienceDimension.INFRASTRUCTURE_RECOVERY,
            windows,
            reason=WindowReason.CHANNEL_OFF,
        )
    baseline_ops: frozenset[str] | None = None
    baseline_slots: dict[tuple[str, str, str | None], str] = {}
    if windows[0].coverage is WindowCoverage.COMPLETE:
        base_frame = _frame(inputs, windows[0].end_tick)
        if (
            base_frame is not None
            and base_frame.infrastructure_channel is OwnerLaneState.COMPLETE
        ):
            baseline_ops = frozenset(
                row.asset_id
                for row in base_frame.infrastructure
                if row.status == _OPERATIONAL
            )
            for row in base_frame.infrastructure:
                if row.status == _OPERATIONAL:
                    baseline_slots[_slot(row)] = row.asset_id

    cells: list[SeriesCell] = []
    for window in windows:
        if window.coverage is not WindowCoverage.COMPLETE:
            cells.append(cell_from_window(window, measures=()))
            continue
        frame = _frame(inputs, window.end_tick)
        if frame is None or frame.infrastructure_channel is not OwnerLaneState.COMPLETE:
            cells.append(
                SeriesCell(
                    window_index=window.index,
                    status=WindowCoverage.PARTIAL,
                    reason=WindowReason.PROJECTION_GAP,
                    expected_ticks=window.expected_ticks,
                    observed_ticks=window.observed_ticks,
                    measures=(),
                )
            )
            continue
        measures = _infra_measures(
            frame.infrastructure,
            baseline_ops if window.baseline_relative_allowed else None,
            baseline_slots if window.baseline_relative_allowed else None,
        )
        cells.append(cell_from_window(window, measures=measures))

    immediate = _immediate_infra(inputs, episode)
    return SeriesPanel(
        dimension=ResilienceDimension.INFRASTRUCTURE_RECOVERY,
        windows=tuple(cells),
        immediate=immediate,
    )


def _slot(row: ResilienceInfrastructureRow) -> tuple[str, str, str | None]:
    loc = row.location_id
    end = row.endpoint_location_id
    if end is not None and end < loc:
        loc, end = end, loc
    return (row.kind, loc, end)


def _infra_measures(
    rows: Sequence[ResilienceInfrastructureRow],
    baseline_ops: frozenset[str] | None,
    baseline_slots: dict[tuple[str, str, str | None], str] | None,
) -> tuple[Measure, ...]:
    operational = {row.asset_id for row in rows if row.status == _OPERATIONAL}
    new_ops = (
        None
        if baseline_ops is None
        else len(operational - baseline_ops)
    )
    baseline_active = (
        None
        if baseline_ops is None
        else len(baseline_ops & operational)
    )
    share = (
        None
        if baseline_ops is None
        else floor_milli(baseline_active or 0, len(baseline_ops))
    )
    reoccupied = 0
    if baseline_slots is not None and baseline_ops is not None:
        current_by_slot = {
            _slot(row): row.asset_id
            for row in rows
            if row.status == _OPERATIONAL
        }
        for slot, original_id in baseline_slots.items():
            current_id = current_by_slot.get(slot)
            if (
                current_id is not None
                and current_id != original_id
                and original_id not in operational
            ):
                reoccupied += 1
    return sort_measures(
        (
            Measure(
                metric="operational_assets",
                unit="count",
                value=len(operational),
            ),
            Measure(
                metric="baseline_assets",
                unit="count",
                value=None if baseline_ops is None else len(baseline_ops),
            ),
            Measure(
                metric="baseline_assets_operational",
                unit="count",
                value=baseline_active,
            ),
            Measure(
                metric="baseline_asset_share_milli",
                unit="milli",
                value=share,
                numerator=baseline_active,
                denominator=None if baseline_ops is None else len(baseline_ops),
            ),
            Measure(
                metric="new_operational_assets",
                unit="count",
                value=new_ops,
            ),
            Measure(
                metric="baseline_slots_reoccupied_by_new_assets",
                unit="count",
                value=None if baseline_slots is None else reoccupied,
            ),
        )
    )


def _immediate_infra(
    inputs: PhysicalReduceInputs, episode: ShockEpisode
) -> SeriesCell:
    point = episode.immediate
    if point.coverage is not WindowCoverage.COMPLETE:
        return SeriesCell(
            window_index=None,
            status=point.coverage,
            reason=point.reason,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    current = _frame(inputs, point.boundary)
    prior = _frame(inputs, point.preceding_boundary)
    if current is None or current.infrastructure_channel is OwnerLaneState.OFF:
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.UNAVAILABLE,
            reason=WindowReason.CHANNEL_OFF,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    if current.infrastructure_channel is not OwnerLaneState.COMPLETE:
        return SeriesCell(
            window_index=None,
            status=WindowCoverage.PARTIAL,
            reason=WindowReason.PROJECTION_GAP,
            expected_ticks=0,
            observed_ticks=0,
            measures=(),
        )
    cur_ops = sum(1 for row in current.infrastructure if row.status == _OPERATIONAL)
    prior_ops = None
    if prior is not None and point.deltas_allowed:
        prior_ops = sum(
            1 for row in prior.infrastructure if row.status == _OPERATIONAL
        )
    return SeriesCell(
        window_index=None,
        status=WindowCoverage.COMPLETE,
        reason=None,
        expected_ticks=0,
        observed_ticks=0,
        measures=sort_measures(
            (
                Measure(
                    metric="operational_assets",
                    unit="count",
                    value=cur_ops,
                    delta_from_baseline=measure_delta(
                        cur_ops, prior_ops, allowed=point.deltas_allowed
                    ),
                ),
            )
        ),
    )
