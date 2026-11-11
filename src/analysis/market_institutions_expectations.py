"""Detached owner expectation, role, and record joins with alignment.

Owner rows are optional inputs. When absent, each family reports ``missing`` and
no row is fabricated. Alignment is researcher-only and never reaches cognition.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final, cast

from analysis.market_institutions_contract import (
    MarketAlignment,
    MarketCoverage,
    MarketInstitutionsError,
    MarketVenueStatus,
)
from analysis.market_institutions_policy import (
    MarketInstitutionsAnalysisPolicy,
    default_market_institutions_analysis_policy,
)
from analysis.market_institutions_rows import (
    MarketExpectationRow,
    MarketOwnerExpectationInput,
    MarketOwnerRecordInput,
    MarketOwnerRoleInput,
    MarketParticipationRow,
    MarketRecordRow,
    MarketRoleRow,
    MarketVenueRow,
)

__all__ = [
    "MarketOwnerJoin",
    "join_expectations",
    "join_market_owner_rows",
    "join_records",
    "join_roles",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.market_institutions.expectations"
)


@dataclass(frozen=True, slots=True)
class MarketOwnerJoin:
    """Combined detached owner joins and their independent coverage."""

    expectations: tuple[MarketExpectationRow, ...]
    roles: tuple[MarketRoleRow, ...]
    records: tuple[MarketRecordRow, ...]
    expectation_coverage: MarketCoverage
    role_coverage: MarketCoverage
    record_coverage: MarketCoverage
    notices: tuple[str, ...]


def _policy(
    policy: MarketInstitutionsAnalysisPolicy | None,
) -> MarketInstitutionsAnalysisPolicy:
    active = (
        default_market_institutions_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not MarketInstitutionsAnalysisPolicy:
        raise MarketInstitutionsError("market_institutions_invalid_policy")
    return active


def _rows[T](values: object, row_type: type[T]) -> tuple[T, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise MarketInstitutionsError("market_institutions_invalid_input")
    rows = tuple(values)
    for row in rows:
        if type(row) is not row_type:
            raise MarketInstitutionsError("market_institutions_invalid_input")
    return cast(tuple[T, ...], rows)


def _venue_windows(
    venues: Sequence[MarketVenueRow],
) -> dict[str, tuple[int, tuple[int, ...]]]:
    active: dict[str, list[int]] = defaultdict(list)
    for row in venues:
        if row.status is MarketVenueStatus.DORMANT:
            continue
        active[row.venue_id].append(row.window_index)
    return {
        venue_id: (min(windows), tuple(sorted(set(windows))))
        for venue_id, windows in active.items()
    }


def _schedule_predicts(
    *,
    cadence: str,
    interval_ticks: int | None,
    phase_tick: int | None,
    schedule_window_index: int | None,
    window_index: int,
    policy: MarketInstitutionsAnalysisPolicy,
) -> bool:
    if cadence == "periodic_window":
        return schedule_window_index == window_index
    if cadence == "recurring_interval":
        if interval_ticks is None or phase_tick is None or interval_ticks <= 0:
            return False
        start = window_index * policy.window_ticks
        for tick in range(start, start + policy.window_ticks):
            if (tick - phase_tick) % interval_ticks == 0:
                return True
        return False
    return False


def join_expectations(
    expectation_inputs: Sequence[MarketOwnerExpectationInput],
    *,
    venues: Sequence[MarketVenueRow],
    window_end: int,
    policy: MarketInstitutionsAnalysisPolicy | None = None,
) -> tuple[MarketExpectationRow, ...]:
    """Join owner expectation inputs to objective venue windows."""

    active = _policy(policy)
    if (
        isinstance(window_end, bool)
        or type(window_end) is not int
        or window_end < 0
    ):
        raise MarketInstitutionsError("market_institutions_invalid_window")
    inputs = _rows(expectation_inputs, MarketOwnerExpectationInput)
    venue_rows = _rows(venues, MarketVenueRow)
    venue_windows = _venue_windows(venue_rows)

    rows: list[MarketExpectationRow] = []
    unresolved = 0
    for item in inputs:
        venue = venue_windows.get(item.venue_token)
        if venue is None:
            unresolved += 1
            continue
        first_window, active_windows = venue
        active_set = set(active_windows)
        expected_windows = [
            window
            for window in range(first_window, window_end + 1)
            if _schedule_predicts(
                cadence=item.cadence,
                interval_ticks=item.interval_ticks,
                phase_tick=item.phase_tick,
                schedule_window_index=item.schedule_window_index,
                window_index=window,
                policy=active,
            )
        ]
        expected_set = set(expected_windows)
        observed = len(expected_set & active_set)
        alignment_milli = (
            0 if not expected_windows else observed * 1000 // len(expected_windows)
        )
        if item.cadence in {"unknown", "single_occurrence"}:
            alignment = MarketAlignment.NOT_APPLICABLE
        elif alignment_milli >= active.alignment_high_milli:
            alignment = MarketAlignment.CONSISTENT
        elif alignment_milli < active.alignment_low_milli:
            alignment = MarketAlignment.INCONSISTENT
        else:
            alignment = MarketAlignment.UNRESOLVED
        for window in range(first_window, window_end + 1):
            rows.append(
                MarketExpectationRow(
                    venue_id=item.venue_token,
                    window_index=window,
                    owner_token=item.owner_token,
                    expectation=item.expectation,
                    cadence=item.cadence,
                    interval_ticks=item.interval_ticks,
                    phase_tick=item.phase_tick,
                    schedule_window_index=item.schedule_window_index,
                    confidence_milli=item.confidence_milli,
                    evidence_count=item.evidence_count,
                    alignment=alignment,
                    coverage=MarketCoverage.COMPLETE,
                )
            )
    rows.sort(key=lambda row: (row.window_index, row.venue_id, row.owner_token))
    if len(rows) > active.max_expectation_rows:
        rows = rows[: active.max_expectation_rows]
        rows = [replace(row, coverage=MarketCoverage.PARTIAL) for row in rows]
        _LOG.warning(
            "market_expectation_rows_truncated rows=%s cap=%s",
            len(rows),
            active.max_expectation_rows,
        )
    if unresolved:
        rows = [replace(row, coverage=MarketCoverage.PARTIAL) for row in rows]
    return tuple(rows)


def join_roles(
    role_inputs: Sequence[MarketOwnerRoleInput],
    *,
    venues: Sequence[MarketVenueRow],
    participation: Sequence[MarketParticipationRow],
    policy: MarketInstitutionsAnalysisPolicy | None = None,
) -> tuple[MarketRoleRow, ...]:
    """Join owner role claims to objective venue participation counts."""

    active = _policy(policy)
    inputs = _rows(role_inputs, MarketOwnerRoleInput)
    venue_rows = _rows(venues, MarketVenueRow)
    participation_rows = _rows(participation, MarketParticipationRow)
    venue_windows = _venue_windows(venue_rows)
    by_participation = {
        (row.window_index, row.venue_id, row.actor_token): row
        for row in participation_rows
    }

    rows: list[MarketRoleRow] = []
    unresolved = 0
    for item in inputs:
        venue = venue_windows.get(item.venue_token)
        if venue is None:
            unresolved += 1
            continue
        recognized = item.recognized and item.role_basis in {
            "office",
            "organization",
        }
        for window in venue[1]:
            counts = by_participation.get(
                (window, item.venue_token, item.actor_token)
            )
            if item.role_kind == "broker" and (
                counts is None or not counts.broker_like
            ):
                continue
            rows.append(
                MarketRoleRow(
                    venue_id=item.venue_token,
                    window_index=window,
                    actor_token=item.actor_token,
                    role_kind=item.role_kind,
                    role_basis=item.role_basis,
                    recognized=recognized,
                    exchange_count=0 if counts is None else counts.exchange_count,
                    counterparty_count=(
                        0 if counts is None else counts.counterparty_count
                    ),
                    active_window_count=(
                        0 if counts is None else counts.active_window_count
                    ),
                    coverage=MarketCoverage.COMPLETE,
                )
            )
    rows.sort(key=lambda row: (row.window_index, row.venue_id, row.actor_token))
    if len(rows) > active.max_role_rows:
        rows = rows[: active.max_role_rows]
        rows = [replace(row, coverage=MarketCoverage.PARTIAL) for row in rows]
        _LOG.warning(
            "market_role_rows_truncated rows=%s cap=%s",
            len(rows),
            active.max_role_rows,
        )
    if unresolved:
        rows = [replace(row, coverage=MarketCoverage.PARTIAL) for row in rows]
    return tuple(rows)


def join_records(
    record_inputs: Sequence[MarketOwnerRecordInput],
    *,
    venues: Sequence[MarketVenueRow],
    policy: MarketInstitutionsAnalysisPolicy | None = None,
) -> tuple[MarketRecordRow, ...]:
    """Join opaque owner record anchors to objective venue windows."""

    active = _policy(policy)
    inputs = _rows(record_inputs, MarketOwnerRecordInput)
    venue_rows = _rows(venues, MarketVenueRow)
    venue_windows = _venue_windows(venue_rows)

    counts: dict[tuple[str, str], int] = defaultdict(int)
    for item in inputs:
        counts[(item.venue_token, item.anchor_token)] += 1
    rows: list[MarketRecordRow] = []
    unresolved = 0
    for item in inputs:
        venue = venue_windows.get(item.venue_token)
        if venue is None:
            unresolved += 1
            continue
        for window in venue[1]:
            rows.append(
                MarketRecordRow(
                    venue_id=item.venue_token,
                    window_index=window,
                    record_kind=item.record_kind,
                    anchor_token=item.anchor_token,
                    owner_row_count=counts[(item.venue_token, item.anchor_token)],
                    coverage=MarketCoverage.COMPLETE,
                )
            )
    rows.sort(key=lambda row: (row.window_index, row.venue_id, row.anchor_token))
    if len(rows) > active.max_record_rows:
        rows = rows[: active.max_record_rows]
        rows = [replace(row, coverage=MarketCoverage.PARTIAL) for row in rows]
        _LOG.warning(
            "market_record_rows_truncated rows=%s cap=%s",
            len(rows),
            active.max_record_rows,
        )
    if unresolved:
        rows = [replace(row, coverage=MarketCoverage.PARTIAL) for row in rows]
    return tuple(rows)


def _coverage(
    rows: Sequence[object],
    *,
    present: bool,
    notices: Sequence[str],
) -> MarketCoverage:
    if not present:
        return MarketCoverage.MISSING
    if notices or any(
        getattr(row, "coverage", MarketCoverage.COMPLETE)
        is MarketCoverage.PARTIAL
        for row in rows
    ):
        return MarketCoverage.PARTIAL
    return MarketCoverage.COMPLETE


def join_market_owner_rows(
    *,
    expectation_inputs: Sequence[MarketOwnerExpectationInput] = (),
    role_inputs: Sequence[MarketOwnerRoleInput] = (),
    record_inputs: Sequence[MarketOwnerRecordInput] = (),
    venues: Sequence[MarketVenueRow],
    participation: Sequence[MarketParticipationRow],
    window_end: int,
    policy: MarketInstitutionsAnalysisPolicy | None = None,
) -> MarketOwnerJoin:
    """Join every detached owner family in one deterministic call."""

    active = _policy(policy)
    expectations = join_expectations(
        expectation_inputs, venues=venues, window_end=window_end, policy=active
    )
    roles = join_roles(
        role_inputs,
        venues=venues,
        participation=participation,
        policy=active,
    )
    records = join_records(record_inputs, venues=venues, policy=active)
    notices: list[str] = []
    if expectations == () and expectation_inputs:
        notices.append("market_institutions_expectation_truncated")
    if roles == () and role_inputs:
        notices.append("market_institutions_role_truncated")
    if records == () and record_inputs:
        notices.append("market_institutions_record_truncated")
    result = MarketOwnerJoin(
        expectations=expectations,
        roles=roles,
        records=records,
        expectation_coverage=_coverage(
            expectations, present=bool(expectation_inputs), notices=notices
        ),
        role_coverage=_coverage(
            roles, present=bool(role_inputs), notices=notices
        ),
        record_coverage=_coverage(
            records, present=bool(record_inputs), notices=notices
        ),
        notices=tuple(sorted(set(notices))),
    )
    _LOG.debug(
        "market_owner_rows_joined expectations=%s roles=%s records=%s coverage=%s",
        len(expectations),
        len(roles),
        len(records),
        result.expectation_coverage.value,
    )
    return result
