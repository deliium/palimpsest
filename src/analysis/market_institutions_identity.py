"""Content-addressed market identity and forward-only lineage."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import replace
from itertools import pairwise
from typing import Final, cast

from analysis.market_institutions_contract import (
    MarketCoverage,
    MarketInstitutionsError,
    MarketLineageStatus,
    market_candidate_token,
)
from analysis.market_institutions_policy import (
    MarketInstitutionsAnalysisPolicy,
    default_market_institutions_analysis_policy,
)
from analysis.market_institutions_rows import (
    MarketCandidateRow,
    MarketLineageRow,
)

__all__ = [
    "group_markets_by_window",
    "link_market_lineage",
    "link_market_series",
    "mint_market_token",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.market_institutions.identity"
)


def mint_market_token(venue_tokens: Sequence[str]) -> str:
    """Mint one ``mktc-`` token from sorted unique venue ids."""

    return market_candidate_token(venue_tokens)


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
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise MarketInstitutionsError("market_institutions_invalid_identity")
    rows = tuple(values)
    for row in rows:
        if type(row) is not row_type:
            raise MarketInstitutionsError("market_institutions_invalid_identity")
    return cast(tuple[T, ...], rows)


def group_markets_by_window(
    candidates: Sequence[MarketCandidateRow],
    *,
    first_window: int,
    last_window: int,
) -> tuple[tuple[MarketCandidateRow, ...], ...]:
    """Group candidates per window, materializing empty windows."""

    if (
        type(first_window) is not int
        or type(last_window) is not int
        or first_window < 0
        or last_window < first_window
    ):
        raise MarketInstitutionsError("market_institutions_invalid_identity")
    rows = _rows(candidates, MarketCandidateRow)
    grouped: list[list[MarketCandidateRow]] = [
        [] for _ in range(last_window - first_window + 1)
    ]
    seen: set[tuple[int, str]] = set()
    for row in rows:
        if row.window_index < first_window or row.window_index > last_window:
            raise MarketInstitutionsError("market_institutions_invalid_identity")
        key = (row.window_index, row.market_token)
        if key in seen:
            raise MarketInstitutionsError("market_institutions_invalid_identity")
        seen.add(key)
        grouped[row.window_index - first_window].append(row)
    return tuple(
        tuple(sorted(values, key=lambda item: item.market_token))
        for values in grouped
    )


def _overlap_milli(left: set[str], right: set[str]) -> int:
    if not left and not right:
        return 1_000
    if not left or not right:
        return 0
    return len(left & right) * 1_000 // min(len(left), len(right))


def link_market_lineage(
    previous: Sequence[MarketCandidateRow],
    current: Sequence[MarketCandidateRow],
    *,
    policy: MarketInstitutionsAnalysisPolicy | None = None,
    previous_window_index: int,
    current_window_index: int,
) -> tuple[MarketLineageRow, ...]:
    """Link two consecutive windows with forward-only market lineage."""

    active = _policy(policy)
    if current_window_index != previous_window_index + 1:
        raise MarketInstitutionsError("market_institutions_invalid_identity")
    previous_rows = _rows(previous, MarketCandidateRow)
    current_rows = _rows(current, MarketCandidateRow)
    for previous_row in previous_rows:
        if previous_row.window_index != previous_window_index:
            raise MarketInstitutionsError("market_institutions_invalid_identity")
    for current_row in current_rows:
        if current_row.window_index != current_window_index:
            raise MarketInstitutionsError("market_institutions_invalid_identity")
    if len({row.market_token for row in previous_rows}) != len(previous_rows):
        raise MarketInstitutionsError("market_institutions_invalid_identity")
    if len({row.market_token for row in current_rows}) != len(current_rows):
        raise MarketInstitutionsError("market_institutions_invalid_identity")

    previous_sets = {
        row.market_token: set(row.venue_ids) for row in previous_rows
    }
    current_sets = {
        row.market_token: set(row.venue_ids) for row in current_rows
    }
    links: list[tuple[str, str, int]] = []
    for previous_token, previous_venues in previous_sets.items():
        for current_token, current_venues in current_sets.items():
            overlap = _overlap_milli(previous_venues, current_venues)
            if overlap >= active.lineage_overlap_milli:
                links.append((previous_token, current_token, overlap))
    predecessors: dict[str, list[str]] = {}
    successors: dict[str, list[str]] = {}
    for previous_token, current_token, _ in links:
        predecessors.setdefault(current_token, []).append(previous_token)
        successors.setdefault(previous_token, []).append(current_token)

    rows: list[MarketLineageRow] = []
    for current_row in sorted(current_rows, key=lambda item: item.market_token):
        preds = sorted(predecessors.get(current_row.market_token, []))
        if not preds:
            status = MarketLineageStatus.EMERGED
        elif any(len(successors.get(token, [])) >= 2 for token in preds):
            status = MarketLineageStatus.SPLIT
        elif len(preds) >= 2:
            status = MarketLineageStatus.MERGE
        else:
            previous_token = preds[0]
            if previous_sets[previous_token] == current_sets[current_row.market_token]:
                status = MarketLineageStatus.CONTINUED
            else:
                status = MarketLineageStatus.TRANSFORMED
        rows.append(
            MarketLineageRow(
                window_index=current_window_index,
                market_token=current_row.market_token,
                venue_ids=current_row.venue_ids,
                party_count=current_row.distinct_party_count,
                status=status,
                previous_market_tokens=tuple(preds),
                next_market_tokens=(),
                rerouted=status is MarketLineageStatus.TRANSFORMED,
                sustained=status
                in {MarketLineageStatus.CONTINUED, MarketLineageStatus.TRANSFORMED},
                coverage=current_row.coverage,
            )
        )
    for previous_row in sorted(previous_rows, key=lambda item: item.market_token):
        if previous_row.market_token in successors:
            continue
        rows.append(
            MarketLineageRow(
                window_index=current_window_index,
                market_token=previous_row.market_token,
                venue_ids=previous_row.venue_ids,
                party_count=0,
                status=MarketLineageStatus.DISSOLVED,
                previous_market_tokens=(previous_row.market_token,),
                next_market_tokens=(),
                rerouted=False,
                sustained=False,
                coverage=MarketCoverage.PARTIAL,
            )
        )
    rows.sort(key=lambda row: (row.window_index, row.market_token))
    return tuple(rows)


def link_market_series(
    grouped: Sequence[Sequence[MarketCandidateRow]],
    *,
    policy: MarketInstitutionsAnalysisPolicy | None = None,
    start_window: int = 0,
) -> tuple[MarketLineageRow, ...]:
    """Link every consecutive window in a grouped market series."""

    active = _policy(policy)
    if isinstance(grouped, (str, bytes)) or not isinstance(grouped, Sequence):
        raise MarketInstitutionsError("market_institutions_invalid_identity")
    windows = tuple(grouped)
    if type(start_window) is not int or start_window < 0:
        raise MarketInstitutionsError("market_institutions_invalid_identity")
    rows: list[MarketLineageRow] = []
    for offset, (previous, current) in enumerate(pairwise(windows)):
        rows.extend(
            link_market_lineage(
                previous,
                current,
                policy=active,
                previous_window_index=start_window + offset,
                current_window_index=start_window + offset + 1,
            )
        )
    if len(rows) > active.max_lineage_edges:
        rows = rows[: active.max_lineage_edges]
        rows = [replace(row, coverage=MarketCoverage.PARTIAL) for row in rows]
        _LOG.warning(
            "market_lineage_truncated edges=%s cap=%s",
            len(rows),
            active.max_lineage_edges,
        )
    _LOG.debug(
        "market_lineage_linked windows=%s edges=%s",
        len(windows),
        len(rows),
    )
    return tuple(rows)
