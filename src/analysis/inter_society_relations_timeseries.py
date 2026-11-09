"""Windowed time series and vectorial pair comparison for ISR panels.

Series use fixed ``INTER_SOCIETY_RELATION_WINDOW_TICKS`` aggregates. Comparison
returns per-domain count deltas and availability transitions only — never a
single relationship rank or composite score.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.inter_society_relations_contract import (
    INTER_SOCIETY_DOMAIN_KEYS,
    INTER_SOCIETY_RELATION_WINDOW_TICKS,
    INTER_SOCIETY_RELATIONS_FORBIDDEN_RESULT_FIELDS,
    InterSocietyAvailability,
    InterSocietyDomain,
    InterSocietyRelationsError,
    assert_no_forbidden_fields,
    require_inter_society_pair_id,
)
from analysis.inter_society_relations_evidence import InterSocietyDomainPanel
from analysis.inter_society_relations_layers import (
    InterSocietyComparisonView,
    InterSocietyPairCandidate,
)
from world.identifiers import require_exact_nonneg_int

__all__ = [
    "INTER_SOCIETY_RELATION_WINDOW_TICKS",
    "MAX_INTER_SOCIETY_SERIES_WINDOWS",
    "InterSocietyPairWindowSeries",
    "InterSocietyWindowPoint",
    "build_pair_window_series",
    "compare_inter_society_pairs",
    "compare_inter_society_windows",
    "window_index_for_tick",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.inter_society_relations.timeseries"
)

MAX_INTER_SOCIETY_SERIES_WINDOWS: Final[int] = 512


@dataclass(frozen=True, slots=True)
class InterSocietyWindowPoint:
    """One forward-only window aggregate for one pair."""

    pair_id: str
    window_index: int
    window_start_tick: int
    window_end_tick: int
    panels: tuple[InterSocietyDomainPanel, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "pair_id", require_inter_society_pair_id(self.pair_id))
        object.__setattr__(
            self,
            "window_index",
            require_exact_nonneg_int("window_index", self.window_index),
        )
        object.__setattr__(
            self,
            "window_start_tick",
            require_exact_nonneg_int("window_start_tick", self.window_start_tick),
        )
        object.__setattr__(
            self,
            "window_end_tick",
            require_exact_nonneg_int("window_end_tick", self.window_end_tick),
        )
        if self.window_end_tick < self.window_start_tick:
            raise InterSocietyRelationsError(
                "inter_society_relations_analysis_invalid_input"
            )


@dataclass(frozen=True, slots=True)
class InterSocietyPairWindowSeries:
    """Append-only researcher series for one society pair."""

    society_a: str
    society_b: str
    points: tuple[InterSocietyWindowPoint, ...]

    def __post_init__(self) -> None:
        indexes = [point.window_index for point in self.points]
        if indexes != sorted(indexes) or len(set(indexes)) != len(indexes):
            raise InterSocietyRelationsError(
                "inter_society_relations_analysis_invalid_input"
            )


def window_index_for_tick(tick: int) -> int:
    """Map an absolute tick onto a fixed-size forward window index."""
    value = require_exact_nonneg_int("tick", tick)
    return value // INTER_SOCIETY_RELATION_WINDOW_TICKS


def build_pair_window_series(
    pairs: Sequence[InterSocietyPairCandidate],
) -> tuple[InterSocietyPairWindowSeries, ...]:
    """Group pair candidates into deterministic per-pair window series."""
    buckets: dict[tuple[str, str], list[InterSocietyPairCandidate]] = {}
    for pair in pairs:
        if type(pair) is not InterSocietyPairCandidate:
            raise InterSocietyRelationsError(
                "inter_society_relations_analysis_invalid_input"
            )
        buckets.setdefault((pair.society_a, pair.society_b), []).append(pair)

    series_list: list[InterSocietyPairWindowSeries] = []
    truncated = False
    for (society_a, society_b), group in sorted(buckets.items()):
        points: list[InterSocietyWindowPoint] = []
        # Keep the latest candidate per window index (forward-only).
        by_index: dict[int, InterSocietyPairCandidate] = {}
        for pair in sorted(group, key=lambda item: item.window_tick):
            index = window_index_for_tick(pair.window_tick)
            by_index[index] = pair
        for index in sorted(by_index):
            if len(points) >= MAX_INTER_SOCIETY_SERIES_WINDOWS:
                truncated = True
                break
            pair = by_index[index]
            start = index * INTER_SOCIETY_RELATION_WINDOW_TICKS
            end = start + INTER_SOCIETY_RELATION_WINDOW_TICKS - 1
            points.append(
                InterSocietyWindowPoint(
                    pair_id=pair.pair_id,
                    window_index=index,
                    window_start_tick=start,
                    window_end_tick=end,
                    panels=pair.panels,
                )
            )
        series_list.append(
            InterSocietyPairWindowSeries(
                society_a=society_a,
                society_b=society_b,
                points=tuple(points),
            )
        )
    if truncated:
        _LOG.warning(
            "inter_society_relations_series_truncated cap=%s",
            MAX_INTER_SOCIETY_SERIES_WINDOWS,
        )
    _LOG.debug(
        "inter_society_relations_series pair_series=%s window_points=%s",
        len(series_list),
        sum(len(item.points) for item in series_list),
    )
    return tuple(series_list)


def _panel_map(
    panels: Sequence[InterSocietyDomainPanel],
) -> dict[InterSocietyDomain, InterSocietyDomainPanel]:
    mapping = {panel.domain: panel for panel in panels}
    if set(mapping) != set(InterSocietyDomain):
        # Allow sparse panels by synthesizing absent entries for comparison.
        for domain in InterSocietyDomain:
            mapping.setdefault(
                domain,
                InterSocietyDomainPanel(
                    domain=domain,
                    event_count=0,
                    availability=InterSocietyAvailability.ABSENT,
                    coverage_observed=0,
                    coverage_expected=0,
                    values={"availability": InterSocietyAvailability.ABSENT.value},
                ),
            )
    return mapping


def _domain_deltas(
    left_panels: Sequence[InterSocietyDomainPanel],
    right_panels: Sequence[InterSocietyDomainPanel],
) -> tuple[tuple[str, int, str, str], ...]:
    left = _panel_map(left_panels)
    right = _panel_map(right_panels)
    deltas: list[tuple[str, int, str, str]] = []
    for domain_key in sorted(INTER_SOCIETY_DOMAIN_KEYS):
        domain = InterSocietyDomain(domain_key)
        left_panel = left[domain]
        right_panel = right[domain]
        delta = right_panel.event_count - left_panel.event_count
        row = (
            domain_key,
            delta,
            left_panel.availability.value,
            right_panel.availability.value,
        )
        payload = {
            "domain": domain_key,
            "count_delta": delta,
            "left_availability": left_panel.availability.value,
            "right_availability": right_panel.availability.value,
        }
        assert_no_forbidden_fields(payload, path="comparison")
        for forbidden in INTER_SOCIETY_RELATIONS_FORBIDDEN_RESULT_FIELDS:
            if forbidden in payload:
                raise InterSocietyRelationsError(
                    "inter_society_relations_forbidden_result_field"
                )
        deltas.append(row)
    return tuple(deltas)


def compare_inter_society_pairs(
    left: InterSocietyPairCandidate,
    right: InterSocietyPairCandidate,
) -> InterSocietyComparisonView:
    """Compare two pairs' domain vectors; never ranks into one score."""
    if type(left) is not InterSocietyPairCandidate or type(right) is not (
        InterSocietyPairCandidate
    ):
        raise InterSocietyRelationsError("inter_society_relations_comparison_invalid")
    _LOG.debug("inter_society_relations_compare_pairs operands=2")
    return InterSocietyComparisonView(
        left_pair_id=left.pair_id,
        right_pair_id=right.pair_id,
        left_window_tick=left.window_tick,
        right_window_tick=right.window_tick,
        domain_deltas=_domain_deltas(left.panels, right.panels),
    )


def compare_inter_society_windows(
    left: InterSocietyWindowPoint,
    right: InterSocietyWindowPoint,
) -> InterSocietyComparisonView:
    """Compare the same or different pair across two windows."""
    if type(left) is not InterSocietyWindowPoint or type(right) is not (
        InterSocietyWindowPoint
    ):
        raise InterSocietyRelationsError("inter_society_relations_comparison_invalid")
    _LOG.debug("inter_society_relations_compare_windows operands=2")
    return InterSocietyComparisonView(
        left_pair_id=left.pair_id,
        right_pair_id=right.pair_id,
        left_window_tick=left.window_start_tick,
        right_window_tick=right.window_start_tick,
        domain_deltas=_domain_deltas(left.panels, right.panels),
    )
