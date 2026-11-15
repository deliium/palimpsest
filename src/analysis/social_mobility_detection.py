"""Quantized mobility and persistence statistics over paired outcomes."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from analysis.social_mobility_contract import (
    SocialMobilityAvailability,
    SocialMobilityCoverage,
    SocialMobilityDomain,
    SocialMobilityError,
    SocialMobilityPersistence,
    social_mobility_measures_for,
)
from analysis.social_mobility_genealogy import SocialMobilityGenealogyHarvest
from analysis.social_mobility_outcomes import SocialMobilityOutcomeHarvest
from analysis.social_mobility_policy import (
    SocialMobilityAnalysisPolicy,
    default_social_mobility_analysis_policy,
)
from analysis.social_mobility_rows import (
    SocialMobilityDomainRow,
    SocialMobilityPairRow,
)

__all__ = [
    "SocialMobilityDetectionResult",
    "detect_social_mobility_rows",
    "spearman_rank_correlation_milli",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.social_mobility.detection")


@dataclass(frozen=True, slots=True)
class SocialMobilityDetectionResult:
    """Detected pair and domain rows plus explicit coverage."""

    pair_rows: tuple[SocialMobilityPairRow, ...] = ()
    domain_rows: tuple[SocialMobilityDomainRow, ...] = ()
    notices: tuple[str, ...] = ()
    coverage: SocialMobilityCoverage = SocialMobilityCoverage.MISSING
    window_count: int = 0
    resolved_pair_count: int = 0

    def __post_init__(self) -> None:
        for name in ("pair_rows", "domain_rows", "notices"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise SocialMobilityError("social_mobility_detection_invalid")
        if type(self.coverage) is not SocialMobilityCoverage:
            raise SocialMobilityError("social_mobility_detection_invalid")
        for name in ("window_count", "resolved_pair_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise SocialMobilityError("social_mobility_detection_invalid")


def _average_ranks(values: Sequence[int]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while (
            end + 1 < len(order) and values[order[end + 1]] == values[order[position]]
        ):
            end += 1
        average = (position + end) / 2.0
        for index in range(position, end + 1):
            ranks[order[index]] = average
        position = end + 1
    return ranks


def spearman_rank_correlation_milli(
    ancestor: Sequence[int], descendant: Sequence[int]
) -> int:
    """Return a quantized integer-milli Spearman rank correlation."""

    if (
        isinstance(ancestor, (str, bytes))
        or isinstance(descendant, (str, bytes))
        or not isinstance(ancestor, Sequence)
        or not isinstance(descendant, Sequence)
        or len(ancestor) != len(descendant)
    ):
        raise SocialMobilityError("social_mobility_invalid_input")
    for value in (*ancestor, *descendant):
        if isinstance(value, bool) or type(value) is not int:
            raise SocialMobilityError("social_mobility_invalid_input")
    if not ancestor:
        return 0
    left = _average_ranks(list(ancestor))
    right = _average_ranks(list(descendant))
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    covariance = sum(
        (x - mean_left) * (y - mean_right) for x, y in zip(left, right, strict=True)
    )
    variance_left = sum((x - mean_left) ** 2 for x in left)
    variance_right = sum((y - mean_right) ** 2 for y in right)
    if variance_left == 0.0 or variance_right == 0.0:
        return 0
    correlation = covariance / (variance_left * variance_right) ** 0.5
    rounded = int(
        Decimal(str(correlation * 1_000.0)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    if rounded == 0:
        return 0
    return max(-1_000, min(1_000, rounded))


def _assign_bins(
    rows: Sequence[SocialMobilityPairRow],
    *,
    rank_bins: int,
    side: str,
) -> dict[tuple[str, str], int]:
    attribute = "ancestor_quantity" if side == "ancestor" else "descendant_quantity"
    ordered = sorted(
        rows,
        key=lambda row: (
            getattr(row, attribute),
            row.ancestor_token,
            row.descendant_token,
        ),
    )
    total = len(ordered)
    return {
        (row.ancestor_token, row.descendant_token): min(
            rank_bins - 1, (position * rank_bins) // total
        )
        for position, row in enumerate(ordered)
    }


def _detect_group(
    *,
    window_index: int,
    window_tick: int,
    domain: SocialMobilityDomain,
    rows: list[SocialMobilityPairRow],
    policy: SocialMobilityAnalysisPolicy,
) -> SocialMobilityDomainRow:
    resolved = [row for row in rows if row.resolved]
    pair_count = len(rows)
    resolved_count = len(resolved)
    measure = social_mobility_measures_for(domain)[0]
    truncated_partial = any(not row.resolved for row in rows)
    if resolved_count < policy.min_mobility_pairs:
        return SocialMobilityDomainRow(
            window_index=window_index,
            window_tick=window_tick,
            domain=domain,
            measure=measure,
            pair_count=pair_count,
            resolved_pair_count=resolved_count,
            rank_correlation_milli=0,
            same_bin_share_milli=0,
            upward_share_milli=0,
            downward_share_milli=0,
            mean_absolute_rank_change_milli=0,
            persistence_direction=SocialMobilityPersistence.INSUFFICIENT_SAMPLES,
            coverage=(
                SocialMobilityCoverage.PARTIAL
                if truncated_partial
                else SocialMobilityCoverage.COMPLETE
            ),
            availability=SocialMobilityAvailability.INSUFFICIENT_SAMPLES,
        )

    ancestor_bins = _assign_bins(resolved, rank_bins=policy.rank_bins, side="ancestor")
    descendant_bins = _assign_bins(
        resolved, rank_bins=policy.rank_bins, side="descendant"
    )
    if (
        len({row.ancestor_quantity for row in resolved}) == 1
        and len({row.descendant_quantity for row in resolved}) == 1
    ):
        for row in resolved:
            key = (row.ancestor_token, row.descendant_token)
            ancestor_bins[key] = 0
            descendant_bins[key] = 0
    same = upward = downward = 0
    total_change = 0
    for row in resolved:
        key = (row.ancestor_token, row.descendant_token)
        ancestor_bin = ancestor_bins[key]
        descendant_bin = descendant_bins[key]
        total_change += abs(descendant_bin - ancestor_bin)
        if descendant_bin == ancestor_bin:
            same += 1
        elif descendant_bin > ancestor_bin:
            upward += 1
        else:
            downward += 1
    same_share = round(1_000 * same / resolved_count)
    upward_share = round(1_000 * upward / resolved_count)
    downward_share = round(1_000 * downward / resolved_count)
    mean_change = round(
        1_000 * (total_change / resolved_count) / max(1, policy.rank_bins - 1)
    )
    mean_change = max(0, min(1_000, mean_change))
    correlation = spearman_rank_correlation_milli(
        [row.ancestor_quantity for row in resolved],
        [row.descendant_quantity for row in resolved],
    )
    persistence = (
        SocialMobilityPersistence.PERSISTENT
        if same_share >= policy.persistence_share_milli
        else SocialMobilityPersistence.MOBILE
    )
    coverage = (
        SocialMobilityCoverage.PARTIAL
        if truncated_partial
        else SocialMobilityCoverage.COMPLETE
    )
    _LOG.debug(
        "social_mobility_detection_group window=%d domain=%s pairs=%d resolved=%d",
        window_index,
        domain.value,
        pair_count,
        resolved_count,
    )
    return SocialMobilityDomainRow(
        window_index=window_index,
        window_tick=window_tick,
        domain=domain,
        measure=measure,
        pair_count=pair_count,
        resolved_pair_count=resolved_count,
        rank_correlation_milli=correlation,
        same_bin_share_milli=same_share,
        upward_share_milli=upward_share,
        downward_share_milli=downward_share,
        mean_absolute_rank_change_milli=mean_change,
        persistence_direction=persistence,
        coverage=coverage,
        availability=SocialMobilityAvailability.AVAILABLE,
    )


def _latest(
    index: Mapping[int, tuple[int, int]], window: int
) -> tuple[int, int] | None:
    candidates = [key for key in index if key <= window]
    if not candidates:
        return None
    return index[max(candidates)]


def detect_social_mobility_rows(
    *,
    genealogy: SocialMobilityGenealogyHarvest,
    outcomes: SocialMobilityOutcomeHarvest,
    policy: SocialMobilityAnalysisPolicy | None = None,
) -> SocialMobilityDetectionResult:
    """Pair ancestor and descendant outcomes and compute quantized statistics."""

    active = default_social_mobility_analysis_policy() if policy is None else policy
    if not genealogy.lineages or not outcomes.rows:
        return SocialMobilityDetectionResult(coverage=SocialMobilityCoverage.MISSING)

    index: dict[SocialMobilityDomain, dict[str, dict[int, tuple[int, int]]]] = {
        domain: {} for domain in SocialMobilityDomain
    }
    windows: set[int] = set()
    for row in outcomes.rows:
        if row.window_index >= active.max_windows:
            continue
        index[row.domain].setdefault(row.owner_token, {})[row.window_index] = (
            row.tick,
            row.quantity,
        )
        windows.add(row.window_index)
    for edge in genealogy.edges:
        if edge.window_index < active.max_windows:
            windows.add(edge.window_index)

    ordered_windows = sorted(windows)
    ordered_windows = [
        window for window in ordered_windows if window < active.max_windows
    ]
    if len(ordered_windows) > active.max_windows:
        ordered_windows = ordered_windows[-active.max_windows :]
    notices: list[str] = []
    truncated = False

    groups: dict[tuple[int, SocialMobilityDomain], list[SocialMobilityPairRow]] = {}
    for window in ordered_windows:
        for domain in SocialMobilityDomain:
            domain_index = index[domain]
            for lineage in genealogy.lineages:
                ancestor = _latest(domain_index.get(lineage.ancestor_token, {}), window)
                descendant = _latest(
                    domain_index.get(lineage.descendant_token, {}), window
                )
                resolved = ancestor is not None and descendant is not None
                if not resolved:
                    pair = SocialMobilityPairRow(
                        window_index=window,
                        ancestor_token=lineage.ancestor_token,
                        descendant_token=lineage.descendant_token,
                        generation_lag=lineage.generation_lag,
                        domain=domain,
                        ancestor_quantity=0,
                        descendant_quantity=0,
                        ancestor_bin=-1,
                        descendant_bin=-1,
                        ancestor_window_index=window,
                        descendant_window_index=window,
                        resolved=False,
                    )
                else:
                    assert ancestor is not None and descendant is not None
                    pair = SocialMobilityPairRow(
                        window_index=window,
                        ancestor_token=lineage.ancestor_token,
                        descendant_token=lineage.descendant_token,
                        generation_lag=lineage.generation_lag,
                        domain=domain,
                        ancestor_quantity=ancestor[1],
                        descendant_quantity=descendant[1],
                        ancestor_bin=0,
                        descendant_bin=0,
                        ancestor_window_index=max(
                            key
                            for key in domain_index[lineage.ancestor_token]
                            if key <= window
                        ),
                        descendant_window_index=max(
                            key
                            for key in domain_index[lineage.descendant_token]
                            if key <= window
                        ),
                        resolved=True,
                    )
                groups.setdefault((window, domain), []).append(pair)

    pair_rows: list[SocialMobilityPairRow] = []
    domain_rows: list[SocialMobilityDomainRow] = []
    for (window, domain), rows in sorted(
        groups.items(), key=lambda item: (item[0][0], item[0][1].value)
    ):
        if not rows:
            continue
        rows.sort(key=lambda row: (row.ancestor_token, row.descendant_token))
        if len(rows) > active.max_pairs:
            rows = rows[: active.max_pairs]
            truncated = True
            if "social_mobility_pairs_truncated" not in notices:
                notices.append("social_mobility_pairs_truncated")
        rows = [
            replace(row, ancestor_bin=0, descendant_bin=0) if row.resolved else row
            for row in rows
        ]
        resolved_rows = [row for row in rows if row.resolved]
        if len(resolved_rows) >= active.min_mobility_pairs:
            ancestor_bins = _assign_bins(
                resolved_rows, rank_bins=active.rank_bins, side="ancestor"
            )
            descendant_bins = _assign_bins(
                resolved_rows, rank_bins=active.rank_bins, side="descendant"
            )
            if (
                len({row.ancestor_quantity for row in resolved_rows}) == 1
                and len({row.descendant_quantity for row in resolved_rows}) == 1
            ):
                for pair_row in resolved_rows:
                    key = (pair_row.ancestor_token, pair_row.descendant_token)
                    ancestor_bins[key] = 0
                    descendant_bins[key] = 0
            rows = [
                replace(
                    row,
                    ancestor_bin=ancestor_bins[
                        (row.ancestor_token, row.descendant_token)
                    ],
                    descendant_bin=descendant_bins[
                        (row.ancestor_token, row.descendant_token)
                    ],
                )
                if row.resolved
                else row
                for row in rows
            ]
        pair_rows.extend(rows)
        domain_rows.append(
            _detect_group(
                window_index=window,
                window_tick=window * active.window_ticks + active.window_ticks - 1,
                domain=domain,
                rows=rows,
                policy=active,
            )
        )

    resolved_total = sum(1 for row in pair_rows if row.resolved)
    if pair_rows and resolved_total < len(pair_rows):
        if "social_mobility_unresolved_pairs" not in notices:
            notices.append("social_mobility_unresolved_pairs")
        _LOG.warning(
            "social_mobility_unresolved_pairs count=%d",
            len(pair_rows) - resolved_total,
        )
    if not pair_rows:
        coverage = SocialMobilityCoverage.MISSING
    elif truncated or resolved_total < len(pair_rows):
        coverage = SocialMobilityCoverage.PARTIAL
    else:
        coverage = SocialMobilityCoverage.COMPLETE
    _LOG.info(
        "social_mobility_detection_complete windows=%d rows=%d",
        len(ordered_windows),
        len(domain_rows),
    )
    ordered_domain_rows = sorted(
        domain_rows, key=lambda row: (row.window_index, row.domain.value)
    )
    if len(ordered_domain_rows) > active.max_domain_rows:
        ordered_domain_rows = ordered_domain_rows[: active.max_domain_rows]
        if "social_mobility_domains_truncated" not in notices:
            notices.append("social_mobility_domains_truncated")
    return SocialMobilityDetectionResult(
        pair_rows=tuple(pair_rows),
        domain_rows=tuple(ordered_domain_rows),
        notices=tuple(notices[: active.max_notices]),
        coverage=coverage,
        window_count=len(ordered_windows),
        resolved_pair_count=resolved_total,
    )
