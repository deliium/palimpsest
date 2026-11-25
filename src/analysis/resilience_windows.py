"""Closed societal-resilience shock clocks and window coverage.

Pure detached policy: applied receipts anchor episodes; schedules and
non-applied receipts never start or censor an episode. No logging.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

__all__ = [
    "RESILIENCE_ERROR_CODES",
    "RESILIENCE_POLICY_ID",
    "RESILIENCE_POST_WINDOW_COUNT",
    "RESILIENCE_WINDOW_TICKS",
    "ImmediateStatePoint",
    "ResilienceError",
    "ScheduleDisposition",
    "ScheduleDispositionRow",
    "ScheduleEntry",
    "ShockEpisode",
    "ShockReceipt",
    "ShockWindowBuild",
    "WindowCoverage",
    "WindowReason",
    "WindowSpec",
    "build_shock_windows",
]

RESILIENCE_POLICY_ID: Final[str] = "societal-resilience.v1"
RESILIENCE_WINDOW_TICKS: Final[int] = 8
RESILIENCE_POST_WINDOW_COUNT: Final[int] = 8

RESILIENCE_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "resilience_duplicate_event_id",
        "resilience_duplicate_cursor",
        "resilience_non_canonical_order",
        "resilience_receipt_beyond_prefix",
        "resilience_invalid_integer",
        "resilience_invalid_token",
        "resilience_schedule_mismatch",
        "resilience_invalid_input",
    }
)

_APPLIED: Final[str] = "applied"
_SCHEDULED: Final[str] = "scheduled"
_OUTCOME_ORDER: Final[tuple[str, ...]] = (
    "no_effect",
    "weather_ineligible",
    "no_live_asset",
    "asset_ambiguous",
)


class ResilienceError(ValueError):
    """Fail-closed resilience policy error; ``args[0]`` is a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "resilience_invalid_input"
        return str(self.args[0])


class WindowCoverage(StrEnum):
    """Closed structural coverage for one aligned window cell."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    CENSORED = "censored"


class WindowReason(StrEnum):
    """Closed window reason; precedence is overlap, pre-run, run end, capture gap."""

    OVERLAPPING_BASELINE = "overlapping_baseline"
    LATER_SHOCK = "later_shock"
    PRE_RUN = "pre_run"
    RUN_END = "run_end"
    CAPTURE_GAP = "capture_gap"
    CHANNEL_OFF = "channel_off"
    PROJECTION_GAP = "projection_gap"


class ScheduleDisposition(StrEnum):
    """Independent schedule-entry disposition; never episode status."""

    APPLIED = "applied"
    NOT_APPLIED = "not_applied"
    NOT_REACHED = "not_reached"
    UNVERIFIED = "unverified"
    RECEIPT_MISSING = "receipt_missing"


@dataclass(frozen=True, slots=True)
class ShockReceipt:
    """Safe applied/non-applied receipt identity for episode clocks."""

    tick: int
    sequence: int
    event_id: str
    kind: str
    origin: str
    outcome: str
    rule_id: str

    def __post_init__(self) -> None:
        _require_nonneg_int("tick", self.tick)
        _require_nonneg_int("sequence", self.sequence)
        _require_token("event_id", self.event_id)
        _require_token("kind", self.kind)
        _require_token("origin", self.origin)
        _require_token("outcome", self.outcome)
        _require_token("rule_id", self.rule_id)


@dataclass(frozen=True, slots=True)
class ScheduleEntry:
    """Configured schedule key ``(tick, rule_id)``."""

    tick: int
    rule_id: str

    def __post_init__(self) -> None:
        _require_nonneg_int("tick", self.tick)
        _require_token("rule_id", self.rule_id)


@dataclass(frozen=True, slots=True)
class ScheduleDispositionRow:
    """One schedule key joined to committed scheduled receipts."""

    tick: int
    rule_id: str
    disposition: ScheduleDisposition


@dataclass(frozen=True, slots=True)
class WindowSpec:
    """One of nine aligned cells: baseline index ``-1``, then post ``0..7``."""

    index: int
    start_tick: int
    end_tick: int
    coverage: WindowCoverage
    reason: WindowReason | None
    expected_ticks: int
    observed_ticks: int
    baseline_relative_allowed: bool

    def __post_init__(self) -> None:
        if type(self.index) is not int or isinstance(self.index, bool):
            raise ResilienceError("resilience_invalid_integer")
        if self.index < -1 or self.index >= RESILIENCE_POST_WINDOW_COUNT:
            raise ResilienceError("resilience_invalid_integer")
        if type(self.start_tick) is not int or isinstance(self.start_tick, bool):
            raise ResilienceError("resilience_invalid_integer")
        if type(self.end_tick) is not int or isinstance(self.end_tick, bool):
            raise ResilienceError("resilience_invalid_integer")
        if self.end_tick != self.start_tick + RESILIENCE_WINDOW_TICKS:
            raise ResilienceError("resilience_invalid_integer")
        _require_nonneg_int("expected_ticks", self.expected_ticks)
        _require_nonneg_int("observed_ticks", self.observed_ticks)
        if self.expected_ticks != RESILIENCE_WINDOW_TICKS:
            raise ResilienceError("resilience_invalid_integer")
        if self.observed_ticks > RESILIENCE_WINDOW_TICKS:
            raise ResilienceError("resilience_invalid_integer")
        if type(self.coverage) is not WindowCoverage:
            raise ResilienceError("resilience_invalid_input")
        if self.reason is not None and type(self.reason) is not WindowReason:
            raise ResilienceError("resilience_invalid_input")
        if type(self.baseline_relative_allowed) is not bool:
            raise ResilienceError("resilience_invalid_input")


@dataclass(frozen=True, slots=True)
class ImmediateStatePoint:
    """State after the shock tick; separate from the nine window cells."""

    boundary: int
    preceding_boundary: int
    coverage: WindowCoverage
    reason: WindowReason | None
    deltas_allowed: bool

    def __post_init__(self) -> None:
        _require_nonneg_int("boundary", self.boundary)
        _require_nonneg_int("preceding_boundary", self.preceding_boundary)
        if self.boundary != self.preceding_boundary + 1:
            raise ResilienceError("resilience_invalid_integer")
        if type(self.coverage) is not WindowCoverage:
            raise ResilienceError("resilience_invalid_input")
        if self.reason is not None and type(self.reason) is not WindowReason:
            raise ResilienceError("resilience_invalid_input")
        if type(self.deltas_allowed) is not bool:
            raise ResilienceError("resilience_invalid_input")


@dataclass(frozen=True, slots=True)
class ShockEpisode:
    """One applied-shock tick with shared co-tick receipts and aligned windows."""

    run_id: str
    shock_tick: int
    applied_receipts: tuple[ShockReceipt, ...]
    windows: tuple[WindowSpec, ...]
    immediate: ImmediateStatePoint

    def __post_init__(self) -> None:
        _require_token("run_id", self.run_id)
        _require_nonneg_int("shock_tick", self.shock_tick)
        if type(self.applied_receipts) is not tuple or not self.applied_receipts:
            raise ResilienceError("resilience_invalid_input")
        for receipt in self.applied_receipts:
            if type(receipt) is not ShockReceipt:
                raise ResilienceError("resilience_invalid_input")
            if receipt.tick != self.shock_tick:
                raise ResilienceError("resilience_invalid_input")
            if receipt.outcome != _APPLIED:
                raise ResilienceError("resilience_invalid_input")
        if len(self.windows) != 1 + RESILIENCE_POST_WINDOW_COUNT:
            raise ResilienceError("resilience_invalid_input")
        expected_indexes = (-1, *range(RESILIENCE_POST_WINDOW_COUNT))
        for index, window in zip(expected_indexes, self.windows, strict=True):
            if type(window) is not WindowSpec or window.index != index:
                raise ResilienceError("resilience_invalid_input")
        if type(self.immediate) is not ImmediateStatePoint:
            raise ResilienceError("resilience_invalid_input")
        if self.immediate.preceding_boundary != self.shock_tick:
            raise ResilienceError("resilience_invalid_input")


@dataclass(frozen=True, slots=True)
class ShockWindowBuild:
    """Deterministic episode/window axis for one sealed capture prefix."""

    policy_id: str
    run_id: str
    finalized_through: int
    capture_through: int
    episodes: tuple[ShockEpisode, ...]
    schedule_dispositions: tuple[ScheduleDispositionRow, ...]
    non_applied_counts: Mapping[str, int]
    no_shock: bool

    def __post_init__(self) -> None:
        if self.policy_id != RESILIENCE_POLICY_ID:
            raise ResilienceError("resilience_invalid_token")
        _require_token("run_id", self.run_id)
        _require_nonneg_int("finalized_through", self.finalized_through)
        _require_nonneg_int("capture_through", self.capture_through)
        if self.capture_through > self.finalized_through:
            raise ResilienceError("resilience_invalid_integer")
        if type(self.no_shock) is not bool:
            raise ResilienceError("resilience_invalid_input")


def build_shock_windows(
    receipts: Sequence[ShockReceipt],
    *,
    run_id: str,
    finalized_through: int,
    capture_through: int,
    schedule: Sequence[ScheduleEntry] = (),
) -> ShockWindowBuild:
    """Build aligned shock episodes and window coverage for one run prefix."""

    _require_token("run_id", run_id)
    _require_nonneg_int("finalized_through", finalized_through)
    _require_nonneg_int("capture_through", capture_through)
    if capture_through > finalized_through:
        raise ResilienceError("resilience_invalid_integer")
    if type(receipts) is not tuple and not isinstance(receipts, list):
        raise ResilienceError("resilience_invalid_input")
    if type(schedule) is not tuple and not isinstance(schedule, list):
        raise ResilienceError("resilience_invalid_input")

    validated = tuple(_validate_receipt(item) for item in receipts)
    _assert_canonical_receipts(validated, capture_through=capture_through)
    schedule_rows = tuple(_validate_schedule_entry(item) for item in schedule)
    _assert_unique_schedule(schedule_rows)

    applied_by_tick = _group_applied(validated)
    non_applied_counts = _count_non_applied(validated)
    dispositions = _schedule_dispositions(
        schedule_rows,
        receipts=validated,
        finalized_through=finalized_through,
        capture_through=capture_through,
    )
    applied_ticks = tuple(sorted(applied_by_tick))
    episodes = tuple(
        _build_episode(
            run_id=run_id,
            shock_tick=shock_tick,
            applied_receipts=applied_by_tick[shock_tick],
            applied_ticks=applied_ticks,
            finalized_through=finalized_through,
            capture_through=capture_through,
        )
        for shock_tick in applied_ticks
    )
    missing_schedule = any(
        row.disposition is ScheduleDisposition.RECEIPT_MISSING for row in dispositions
    )
    capture_complete = capture_through == finalized_through
    no_shock = (
        capture_complete
        and not episodes
        and not missing_schedule
        and capture_through >= 0
    )
    return ShockWindowBuild(
        policy_id=RESILIENCE_POLICY_ID,
        run_id=run_id,
        finalized_through=finalized_through,
        capture_through=capture_through,
        episodes=episodes,
        schedule_dispositions=dispositions,
        non_applied_counts=non_applied_counts,
        no_shock=no_shock,
    )


def _validate_receipt(value: object) -> ShockReceipt:
    if type(value) is not ShockReceipt:
        raise ResilienceError("resilience_invalid_input")
    return value


def _validate_schedule_entry(value: object) -> ScheduleEntry:
    if type(value) is not ScheduleEntry:
        raise ResilienceError("resilience_invalid_input")
    return value


def _assert_unique_schedule(entries: Sequence[ScheduleEntry]) -> None:
    seen: set[tuple[int, str]] = set()
    for entry in entries:
        key = (entry.tick, entry.rule_id)
        if key in seen:
            raise ResilienceError("resilience_schedule_mismatch")
        seen.add(key)


def _assert_canonical_receipts(
    receipts: Sequence[ShockReceipt],
    *,
    capture_through: int,
) -> None:
    seen_ids: set[str] = set()
    seen_cursors: set[tuple[int, int]] = set()
    previous: tuple[int, int, str] | None = None
    for receipt in receipts:
        # Event tick t is sealed only when boundary t+1 exists: t < capture_through.
        if receipt.tick >= capture_through:
            raise ResilienceError("resilience_receipt_beyond_prefix")
        if receipt.event_id in seen_ids:
            raise ResilienceError("resilience_duplicate_event_id")
        seen_ids.add(receipt.event_id)
        cursor = (receipt.tick, receipt.sequence)
        if cursor in seen_cursors:
            raise ResilienceError("resilience_duplicate_cursor")
        seen_cursors.add(cursor)
        current = (receipt.tick, receipt.sequence, receipt.event_id)
        if previous is not None and current < previous:
            raise ResilienceError("resilience_non_canonical_order")
        previous = current


def _group_applied(
    receipts: Sequence[ShockReceipt],
) -> dict[int, tuple[ShockReceipt, ...]]:
    buckets: dict[int, list[ShockReceipt]] = {}
    for receipt in receipts:
        if receipt.outcome != _APPLIED:
            continue
        buckets.setdefault(receipt.tick, []).append(receipt)
    return {
        tick: tuple(
            sorted(group, key=lambda item: (item.sequence, item.event_id))
        )
        for tick, group in buckets.items()
    }


def _count_non_applied(receipts: Sequence[ShockReceipt]) -> Mapping[str, int]:
    counts = {outcome: 0 for outcome in _OUTCOME_ORDER}
    for receipt in receipts:
        if receipt.outcome == _APPLIED:
            continue
        if receipt.outcome not in counts:
            counts[receipt.outcome] = 0
        counts[receipt.outcome] += 1
    return MappingProxyType(dict(sorted(counts.items())))


def _schedule_dispositions(
    schedule: Sequence[ScheduleEntry],
    *,
    receipts: Sequence[ShockReceipt],
    finalized_through: int,
    capture_through: int,
) -> tuple[ScheduleDispositionRow, ...]:
    scheduled_receipts: dict[tuple[int, str], list[ShockReceipt]] = {}
    for receipt in receipts:
        if receipt.origin != _SCHEDULED:
            continue
        key = (receipt.tick, receipt.rule_id)
        scheduled_receipts.setdefault(key, []).append(receipt)

    rows: list[ScheduleDispositionRow] = []
    for entry in sorted(schedule, key=lambda item: (item.tick, item.rule_id)):
        key = (entry.tick, entry.rule_id)
        matches = scheduled_receipts.pop(key, [])
        if len(matches) > 1:
            raise ResilienceError("resilience_schedule_mismatch")
        if entry.tick >= finalized_through:
            if matches:
                raise ResilienceError("resilience_schedule_mismatch")
            disposition = ScheduleDisposition.NOT_REACHED
        elif entry.tick >= capture_through:
            if matches:
                raise ResilienceError("resilience_schedule_mismatch")
            disposition = ScheduleDisposition.UNVERIFIED
        elif not matches:
            disposition = ScheduleDisposition.RECEIPT_MISSING
        elif matches[0].outcome == _APPLIED:
            disposition = ScheduleDisposition.APPLIED
        else:
            disposition = ScheduleDisposition.NOT_APPLIED
        rows.append(
            ScheduleDispositionRow(
                tick=entry.tick,
                rule_id=entry.rule_id,
                disposition=disposition,
            )
        )
    if scheduled_receipts:
        # Unmatched scheduled receipts against the configured schedule.
        raise ResilienceError("resilience_schedule_mismatch")
    return tuple(rows)


def _build_episode(
    *,
    run_id: str,
    shock_tick: int,
    applied_receipts: tuple[ShockReceipt, ...],
    applied_ticks: Sequence[int],
    finalized_through: int,
    capture_through: int,
) -> ShockEpisode:
    prior_in_baseline = any(
        max(0, shock_tick - RESILIENCE_WINDOW_TICKS) <= other < shock_tick
        for other in applied_ticks
    )
    later_ticks = tuple(tick for tick in applied_ticks if tick > shock_tick)
    windows: list[WindowSpec] = []
    baseline = _window_interval(shock_tick, index=-1)
    windows.append(
        _classify_window(
            index=-1,
            start_tick=baseline[0],
            end_tick=baseline[1],
            finalized_through=finalized_through,
            capture_through=capture_through,
            overlap_reason=(
                WindowReason.OVERLAPPING_BASELINE if prior_in_baseline else None
            ),
            baseline_complete_for_relative=False,
        )
    )
    baseline_relative_ok = windows[0].coverage is WindowCoverage.COMPLETE
    censored_from: int | None = None
    for index in range(RESILIENCE_POST_WINDOW_COUNT):
        start_tick, end_tick = _window_interval(shock_tick, index=index)
        overlap_reason: WindowReason | None = None
        if censored_from is not None and index >= censored_from:
            overlap_reason = WindowReason.LATER_SHOCK
        else:
            for later in later_ticks:
                # Later shock exactly at exclusive end does not invalidate.
                if start_tick <= later < end_tick:
                    overlap_reason = WindowReason.LATER_SHOCK
                    censored_from = index
                    break
        windows.append(
            _classify_window(
                index=index,
                start_tick=start_tick,
                end_tick=end_tick,
                finalized_through=finalized_through,
                capture_through=capture_through,
                overlap_reason=overlap_reason,
                baseline_complete_for_relative=baseline_relative_ok,
            )
        )
    immediate = _immediate_point(
        shock_tick=shock_tick,
        capture_through=capture_through,
        prior_in_baseline=prior_in_baseline,
    )
    return ShockEpisode(
        run_id=run_id,
        shock_tick=shock_tick,
        applied_receipts=applied_receipts,
        windows=tuple(windows),
        immediate=immediate,
    )


def _window_interval(shock_tick: int, *, index: int) -> tuple[int, int]:
    if index == -1:
        start = shock_tick - RESILIENCE_WINDOW_TICKS
        return start, shock_tick
    start = shock_tick + RESILIENCE_WINDOW_TICKS * index
    return start, start + RESILIENCE_WINDOW_TICKS


def _classify_window(
    *,
    index: int,
    start_tick: int,
    end_tick: int,
    finalized_through: int,
    capture_through: int,
    overlap_reason: WindowReason | None,
    baseline_complete_for_relative: bool,
) -> WindowSpec:
    observed = _observed_ticks(
        start_tick=start_tick,
        end_tick=end_tick,
        capture_through=capture_through,
    )
    if overlap_reason is not None:
        coverage = WindowCoverage.CENSORED
        reason: WindowReason | None = overlap_reason
    else:
        reason = _structural_reason(
            start_tick=start_tick,
            end_tick=end_tick,
            finalized_through=finalized_through,
            capture_through=capture_through,
        )
        if reason is None and observed == RESILIENCE_WINDOW_TICKS:
            coverage = WindowCoverage.COMPLETE
            reason = None
        elif observed == 0:
            coverage = WindowCoverage.UNAVAILABLE
            if reason is None:
                reason = WindowReason.CAPTURE_GAP
        else:
            coverage = WindowCoverage.PARTIAL
            if reason is None:
                reason = WindowReason.CAPTURE_GAP
    if coverage is WindowCoverage.COMPLETE:
        if index == -1:
            baseline_relative_allowed = True
        else:
            # Raw post measures remain allowed when baseline is censored; relative off.
            baseline_relative_allowed = baseline_complete_for_relative
    else:
        baseline_relative_allowed = False
    return WindowSpec(
        index=index,
        start_tick=start_tick,
        end_tick=end_tick,
        coverage=coverage,
        reason=reason,
        expected_ticks=RESILIENCE_WINDOW_TICKS,
        observed_ticks=observed,
        baseline_relative_allowed=baseline_relative_allowed,
    )


def _structural_reason(
    *,
    start_tick: int,
    end_tick: int,
    finalized_through: int,
    capture_through: int,
) -> WindowReason | None:
    # Precedence: pre-run, run end, capture gap.
    if start_tick < 0:
        return WindowReason.PRE_RUN
    if end_tick > finalized_through:
        return WindowReason.RUN_END
    # Endpoint boundaries sealed when boundary <= capture_through.
    if start_tick > capture_through or end_tick > capture_through:
        return WindowReason.CAPTURE_GAP
    return None


def _observed_ticks(
    *,
    start_tick: int,
    end_tick: int,
    capture_through: int,
) -> int:
    lo = max(0, start_tick)
    hi = min(end_tick, capture_through)
    if hi <= lo:
        return 0
    return hi - lo


def _immediate_point(
    *,
    shock_tick: int,
    capture_through: int,
    prior_in_baseline: bool,
) -> ImmediateStatePoint:
    boundary = shock_tick + 1
    if boundary > capture_through:
        return ImmediateStatePoint(
            boundary=boundary,
            preceding_boundary=shock_tick,
            coverage=WindowCoverage.UNAVAILABLE,
            reason=WindowReason.CAPTURE_GAP,
            deltas_allowed=False,
        )
    # Point uses only verified boundary s+1; preceding s for deltas.
    deltas_allowed = (not prior_in_baseline) and shock_tick <= capture_through
    return ImmediateStatePoint(
        boundary=boundary,
        preceding_boundary=shock_tick,
        coverage=WindowCoverage.COMPLETE,
        reason=None,
        deltas_allowed=deltas_allowed,
    )


def _require_nonneg_int(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise ResilienceError("resilience_invalid_integer")
    return value


def _require_token(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ResilienceError("resilience_invalid_token")
    if len(value) > 128 or any(ord(char) < 32 for char in value):
        raise ResilienceError("resilience_invalid_token")
    return value
