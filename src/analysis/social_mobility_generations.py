"""Per-generation and per-lag mobility summaries for many-generation studies."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.social_mobility_contract import (
    SocialMobilityAvailability,
    SocialMobilityCoverage,
    SocialMobilityError,
)
from analysis.social_mobility_genealogy import SocialMobilityGenealogyHarvest
from analysis.social_mobility_outcomes import SocialMobilityOutcomeHarvest
from analysis.social_mobility_policy import (
    SocialMobilityAnalysisPolicy,
    default_social_mobility_analysis_policy,
)
from analysis.social_mobility_rows import (
    SocialMobilityGenerationRow,
    SocialMobilityLagRow,
    SocialMobilityPairRow,
)

__all__ = [
    "SocialMobilityGenerationResult",
    "compare_social_mobility_generations",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.social_mobility.generations")


@dataclass(frozen=True, slots=True)
class SocialMobilityGenerationResult:
    """Generation and lag strata plus explicit comparability."""

    generation_rows: tuple[SocialMobilityGenerationRow, ...] = ()
    lag_rows: tuple[SocialMobilityLagRow, ...] = ()
    notices: tuple[str, ...] = ()
    coverage: SocialMobilityCoverage = SocialMobilityCoverage.MISSING
    comparable_generation_count: int = 0
    comparable_lag_count: int = 0

    def __post_init__(self) -> None:
        for name in ("generation_rows", "lag_rows", "notices"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise SocialMobilityError("social_mobility_generation_invalid")
        if type(self.coverage) is not SocialMobilityCoverage:
            raise SocialMobilityError("social_mobility_generation_invalid")
        for name in ("comparable_generation_count", "comparable_lag_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise SocialMobilityError("social_mobility_generation_invalid")


def _shares(
    rows: Sequence[SocialMobilityPairRow], *, rank_bins: int
) -> tuple[int, int, int]:
    if not rows:
        return 0, 0, 0
    if (
        len({row.ancestor_quantity for row in rows}) == 1
        and len({row.descendant_quantity for row in rows}) == 1
    ):
        return 1_000, 0, 0
    ancestor_order = sorted(
        rows,
        key=lambda row: (
            row.ancestor_quantity,
            row.ancestor_token,
            row.descendant_token,
        ),
    )
    descendant_order = sorted(
        rows,
        key=lambda row: (
            row.descendant_quantity,
            row.ancestor_token,
            row.descendant_token,
        ),
    )
    total = len(rows)
    ancestor_bins = {
        (row.ancestor_token, row.descendant_token): min(
            rank_bins - 1, (position * rank_bins) // total
        )
        for position, row in enumerate(ancestor_order)
    }
    descendant_bins = {
        (row.ancestor_token, row.descendant_token): min(
            rank_bins - 1, (position * rank_bins) // total
        )
        for position, row in enumerate(descendant_order)
    }
    same = upward = downward = 0
    for row in rows:
        key = (row.ancestor_token, row.descendant_token)
        ancestor_bin = ancestor_bins[key]
        descendant_bin = descendant_bins[key]
        if descendant_bin == ancestor_bin:
            same += 1
        elif descendant_bin > ancestor_bin:
            upward += 1
        else:
            downward += 1
    return (
        round(1_000 * same / total),
        round(1_000 * upward / total),
        round(1_000 * downward / total),
    )


def compare_social_mobility_generations(
    *,
    genealogy: SocialMobilityGenealogyHarvest,
    outcomes: SocialMobilityOutcomeHarvest,
    pair_rows: Sequence[SocialMobilityPairRow],
    policy: SocialMobilityAnalysisPolicy | None = None,
) -> SocialMobilityGenerationResult:
    """Compose generation and generation-lag strata without ranking them."""

    active = default_social_mobility_analysis_policy() if policy is None else policy
    if isinstance(pair_rows, (str, bytes)) or not isinstance(pair_rows, Sequence):
        raise SocialMobilityError("social_mobility_invalid_input")
    rows = tuple(pair_rows)
    if not rows:
        return SocialMobilityGenerationResult(coverage=SocialMobilityCoverage.MISSING)

    notices: list[str] = []
    generation_of = dict(genealogy.generations)
    owners_by_window_generation: dict[tuple[int, int], set[str]] = {}
    for outcome_row in outcomes.rows:
        owners_by_window_generation.setdefault(
            (outcome_row.window_index, outcome_row.generation_index), set()
        ).add(outcome_row.owner_token)

    resolved = [row for row in rows if row.resolved]
    generation_groups: dict[tuple[int, int], list[SocialMobilityPairRow]] = {}
    lag_groups: dict[tuple[int, int], list[SocialMobilityPairRow]] = {}
    for pair_row in resolved:
        generation = generation_of.get(pair_row.descendant_token)
        if generation is None or generation > active.max_generation_index:
            if "social_mobility_generation_out_of_range" not in notices:
                notices.append("social_mobility_generation_out_of_range")
            continue
        generation_groups.setdefault(
            (pair_row.window_index, generation), []
        ).append(pair_row)
        if 1 <= pair_row.generation_lag <= active.max_generation_lag:
            lag_groups.setdefault(
                (pair_row.window_index, pair_row.generation_lag), []
            ).append(pair_row)

    generation_rows: list[SocialMobilityGenerationRow] = []
    for (window, generation), group in sorted(generation_groups.items()):
        same, upward, downward = _shares(group, rank_bins=active.rank_bins)
        comparable = len(group) >= active.min_mobility_pairs
        generation_rows.append(
            SocialMobilityGenerationRow(
                window_index=window,
                window_tick=window * active.window_ticks + active.window_ticks - 1,
                generation_index=generation,
                owner_count=len(
                    owners_by_window_generation.get((window, generation), set())
                ),
                pair_count=len(group),
                comparable=comparable,
                same_bin_share_milli=same,
                upward_share_milli=upward,
                downward_share_milli=downward,
                coverage=SocialMobilityCoverage.COMPLETE,
                availability=(
                    SocialMobilityAvailability.AVAILABLE
                    if comparable
                    else SocialMobilityAvailability.INSUFFICIENT_SAMPLES
                ),
            )
        )
    if len(generation_rows) > active.max_generation_rows:
        generation_rows = generation_rows[: active.max_generation_rows]
        notices.append("social_mobility_generations_truncated")

    lag_rows: list[SocialMobilityLagRow] = []
    for (window, lag), group in sorted(lag_groups.items()):
        same, upward, downward = _shares(group, rank_bins=active.rank_bins)
        comparable = len(group) >= active.min_mobility_pairs
        lag_rows.append(
            SocialMobilityLagRow(
                window_index=window,
                window_tick=window * active.window_ticks + active.window_ticks - 1,
                generation_lag=lag,
                pair_count=len(group),
                comparable=comparable,
                same_bin_share_milli=same,
                upward_share_milli=upward,
                downward_share_milli=downward,
                coverage=SocialMobilityCoverage.COMPLETE,
                availability=(
                    SocialMobilityAvailability.AVAILABLE
                    if comparable
                    else SocialMobilityAvailability.INSUFFICIENT_SAMPLES
                ),
            )
        )
    if len(lag_rows) > active.max_lag_rows:
        lag_rows = lag_rows[: active.max_lag_rows]
        notices.append("social_mobility_lags_truncated")

    comparable_generations = sum(1 for row in generation_rows if row.comparable)
    comparable_lags = sum(1 for row in lag_rows if row.comparable)
    if not comparable_generations:
        _LOG.warning("social_mobility_insufficient_generations")
        notices.append("social_mobility_insufficient_generations")
    coverage = (
        SocialMobilityCoverage.PARTIAL
        if notices
        else (
            SocialMobilityCoverage.COMPLETE
            if generation_rows or lag_rows
            else SocialMobilityCoverage.MISSING
        )
    )
    _LOG.info(
        "social_mobility_generations_complete generations=%d lags=%d",
        len(generation_rows),
        len(lag_rows),
    )
    return SocialMobilityGenerationResult(
        generation_rows=tuple(generation_rows),
        lag_rows=tuple(lag_rows),
        notices=tuple(notices[: active.max_notices]),
        coverage=coverage,
        comparable_generation_count=comparable_generations,
        comparable_lag_count=comparable_lags,
    )
