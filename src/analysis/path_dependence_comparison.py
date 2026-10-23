"""Detached paired/seed-block comparison for historical-contingency outcomes."""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.seed_block_statistics import student_t_interval

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.path_dependence_comparison"
)
MULTIPLICITY_POLICY: Final[str] = "pointwise_exploratory_no_familywise_claim"


class PathDependenceComparisonError(ValueError):
    """Detached comparison failure with a stable reason code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PathDependenceOutcomeCell:
    cell_id: str
    parent_id: str
    fork_tick: int
    numeric_seed: int
    seed_ordinal: int
    replicate: int
    arm_id: str
    contrast_id: str
    outcome_key: str
    window_id: str
    source_digest: str
    channel_alignment: str = "unknown"
    value: float | None = None
    availability: str = "present"

    def __post_init__(self) -> None:
        for name in (
            "cell_id",
            "parent_id",
            "arm_id",
            "contrast_id",
            "outcome_key",
            "window_id",
            "source_digest",
            "channel_alignment",
            "availability",
        ):
            if type(getattr(self, name)) is not str or not getattr(self, name):
                raise PathDependenceComparisonError("comparison_basis_mismatch")
        for name in (
            "fork_tick",
            "numeric_seed",
            "seed_ordinal",
            "replicate",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise PathDependenceComparisonError("comparison_basis_mismatch")
        if self.value is not None and type(self.value) not in (int, float):
            raise PathDependenceComparisonError("comparison_basis_mismatch")
        if self.value is not None:
            object.__setattr__(self, "value", float(self.value))


@dataclass(frozen=True, slots=True)
class ComparisonContrast:
    contrast_id: str
    control_arm_id: str
    treatment_arm_id: str

    def __post_init__(self) -> None:
        if self.control_arm_id == self.treatment_arm_id:
            raise PathDependenceComparisonError("comparison_basis_mismatch")


@dataclass(frozen=True, slots=True)
class PathDependenceComparisonRequest:
    cells: tuple[PathDependenceOutcomeCell, ...]
    contrasts: tuple[ComparisonContrast, ...]
    confidence: float = 0.95

    def __post_init__(self) -> None:
        if isinstance(self.cells, (set, frozenset, Mapping)) or not isinstance(
            self.cells, Sequence
        ):
            raise PathDependenceComparisonError("comparison_basis_mismatch")
        if not isinstance(self.contrasts, Sequence) or not self.contrasts:
            raise PathDependenceComparisonError("comparison_basis_mismatch")
        cells = tuple(self.cells)
        for cell in cells:
            if type(cell) is not PathDependenceOutcomeCell:
                raise PathDependenceComparisonError("comparison_basis_mismatch")
        object.__setattr__(self, "cells", cells)
        object.__setattr__(self, "contrasts", tuple(self.contrasts))


@dataclass(frozen=True, slots=True)
class SeedBlockSummary:
    numeric_seed: int
    paired_count: int
    mean: float
    membership: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PairedContrastComparison:
    contrast_id: str
    outcome_key: str
    window_id: str
    fork_tick: int
    block_count: int
    paired_slot_count: int
    missing_slot_count: int
    mean: float | None
    sample_sd: float | None
    standard_error: float | None
    df: int | None
    ci_low: float | None
    ci_high: float | None
    status: str
    blocks: tuple[SeedBlockSummary, ...]
    channel_alignment: str
    causal_claim: bool = False
    single_run_is_illustrative: bool = True
    multiplicity_policy: str = MULTIPLICITY_POLICY


def _pair_key(cell: PathDependenceOutcomeCell) -> tuple[object, ...]:
    return (
        cell.parent_id,
        cell.fork_tick,
        cell.numeric_seed,
        cell.seed_ordinal,
        cell.replicate,
        cell.contrast_id,
        cell.outcome_key,
        cell.window_id,
    )


def _channel_summary(values: Sequence[str]) -> str:
    unique = set(values)
    if "unknown" in unique:
        return "unknown"
    if unique == {"shared"}:
        return "shared"
    if unique == {"distinct"}:
        return "distinct"
    return "mixed"


def build_path_dependence_comparison(
    request: PathDependenceComparisonRequest,
) -> tuple[PairedContrastComparison, ...]:
    """Compare treatment minus control within matched slots and seed blocks."""
    if type(request) is not PathDependenceComparisonRequest:
        raise TypeError("request must be PathDependenceComparisonRequest")
    contrast_map = {
        contrast.contrast_id: contrast for contrast in request.contrasts
    }
    by_key: dict[tuple[object, ...], list[PathDependenceOutcomeCell]] = (
        defaultdict(list)
    )
    for cell in request.cells:
        if cell.contrast_id not in contrast_map:
            raise PathDependenceComparisonError("comparison_basis_mismatch")
        by_key[_pair_key(cell)].append(cell)
    results: list[PairedContrastComparison] = []
    grouped: dict[tuple[str, str, str, int], list[tuple[object, ...]]] = (
        defaultdict(list)
    )
    for key in by_key:
        contrast_id = str(key[5])
        outcome_key = str(key[6])
        window_id = str(key[7])
        fork_tick_value = key[1]
        if not isinstance(fork_tick_value, int):
            raise PathDependenceComparisonError("comparison_basis_mismatch")
        fork_tick = fork_tick_value
        grouped[(contrast_id, outcome_key, window_id, fork_tick)].append(key)
    for (contrast_id, outcome_key, window_id, fork_tick), keys in sorted(
        grouped.items()
    ):
        contrast = contrast_map[contrast_id]
        block_values: dict[int, list[float]] = defaultdict(list)
        block_members: dict[int, list[str]] = defaultdict(list)
        channel_values: list[str] = []
        paired = 0
        missing = 0
        for key in sorted(keys, key=repr):
            entries = by_key[key]
            by_arm: dict[str, list[PathDependenceOutcomeCell]] = defaultdict(list)
            for entry in entries:
                by_arm[entry.arm_id].append(entry)
            if any(len(items) > 1 for items in by_arm.values()):
                raise PathDependenceComparisonError("comparison_duplicate_branch")
            control = by_arm.get(contrast.control_arm_id, [])
            treatment = by_arm.get(contrast.treatment_arm_id, [])
            if not control or not treatment:
                missing += 1
                continue
            control_cell = control[0]
            treatment_cell = treatment[0]
            if control_cell.source_digest != treatment_cell.source_digest:
                raise PathDependenceComparisonError(
                    "comparison_lineage_mismatch"
                )
            if control_cell.value is None or treatment_cell.value is None:
                missing += 1
                continue
            delta = treatment_cell.value - control_cell.value
            numeric_seed = control_cell.numeric_seed
            block_values[numeric_seed].append(delta)
            block_members[numeric_seed].extend(
                (control_cell.cell_id, treatment_cell.cell_id)
            )
            channel_values.extend(
                (
                    control_cell.channel_alignment,
                    treatment_cell.channel_alignment,
                )
            )
            paired += 1
        block_means = [
            statistics.fmean(values)
            for _seed, values in sorted(block_values.items())
        ]
        interval = student_t_interval(
            block_means, confidence=request.confidence
        )
        blocks = tuple(
            SeedBlockSummary(
                numeric_seed=numeric_seed,
                paired_count=len(values),
                mean=statistics.fmean(values),
                membership=tuple(sorted(block_members[numeric_seed])),
            )
            for numeric_seed, values in sorted(block_values.items())
        )
        results.append(
            PairedContrastComparison(
                contrast_id=contrast_id,
                outcome_key=outcome_key,
                window_id=window_id,
                fork_tick=fork_tick,
                block_count=len(block_means),
                paired_slot_count=paired,
                missing_slot_count=missing,
                mean=interval.mean,
                sample_sd=interval.sample_sd,
                standard_error=interval.standard_error,
                df=interval.df,
                ci_low=interval.low,
                ci_high=interval.high,
                status=interval.status,
                blocks=blocks,
                channel_alignment=_channel_summary(channel_values),
            )
        )
    _LOG.info(
        "path_dependence_comparison_built contrast_count=%s cell_count=%s",
        len(results),
        len(request.cells),
    )
    return tuple(results)


__all__ = [
    "ComparisonContrast",
    "PairedContrastComparison",
    "PathDependenceComparisonError",
    "PathDependenceComparisonRequest",
    "PathDependenceOutcomeCell",
    "SeedBlockSummary",
    "build_path_dependence_comparison",
]
