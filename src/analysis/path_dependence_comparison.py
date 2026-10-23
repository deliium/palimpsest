"""Detached paired/seed-block comparison for historical-contingency outcomes."""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.numerical import quantize_float
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
    config_digest: str = ""
    provider_basis: str = "deterministic_fake"
    channel_manifest: tuple[str, ...] = ()
    root_id: str | None = None
    planned_child_run_id: str | None = None
    child_run_id: str | None = None

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
        for name in (
            "config_digest",
            "provider_basis",
            "root_id",
            "planned_child_run_id",
            "child_run_id",
        ):
            value = getattr(self, name)
            if name == "config_digest" and value == "":
                continue
            if value is not None and (type(value) is not str or not value):
                raise PathDependenceComparisonError("comparison_basis_mismatch")
        if isinstance(self.channel_manifest, (str, bytes)) or not isinstance(
            self.channel_manifest, Sequence
        ):
            raise PathDependenceComparisonError("comparison_basis_mismatch")
        manifest = tuple(self.channel_manifest)
        if any(type(item) is not str or not item for item in manifest):
            raise PathDependenceComparisonError("comparison_basis_mismatch")
        object.__setattr__(self, "channel_manifest", manifest)


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
    root_id: str | None = None


@dataclass(frozen=True, slots=True)
class PairedContrastComparison:
    contrast_id: str
    outcome_key: str
    window_id: str
    fork_tick: int
    block_count: int
    branch_count: int
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
    arm_counts: tuple[tuple[str, int], ...] = ()
    excluded_slot_count: int = 0
    provider_basis: str = "deterministic_fake"
    interval_method: str = "pointwise_two_sided_student_t_0.95"
    arm_assignment_policy: str = "treatment_blind_slots"
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
    arm_counts_by_group: dict[tuple[str, str, str, int], dict[str, int]] = (
        defaultdict(lambda: defaultdict(int))
    )
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
        group_key = (contrast_id, outcome_key, window_id, fork_tick)
        grouped[group_key].append(key)
        for cell in by_key[key]:
            arm_counts_by_group[group_key][cell.arm_id] += 1
    for (contrast_id, outcome_key, window_id, fork_tick), keys in sorted(
        grouped.items()
    ):
        contrast = contrast_map[contrast_id]
        block_values: dict[str, list[float]] = defaultdict(list)
        block_members: dict[str, list[str]] = defaultdict(list)
        block_seed: dict[str, int] = {}
        block_root: dict[str, str | None] = {}
        channel_values: list[str] = []
        provider_values: set[str] = set()
        paired = 0
        missing = 0
        excluded = 0
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
                excluded += 1
                continue
            control_cell = control[0]
            treatment_cell = treatment[0]
            if control_cell.source_digest != treatment_cell.source_digest:
                raise PathDependenceComparisonError(
                    "comparison_lineage_mismatch"
                )
            if (
                control_cell.config_digest
                and treatment_cell.config_digest
                and control_cell.config_digest != treatment_cell.config_digest
            ):
                raise PathDependenceComparisonError(
                    "comparison_basis_mismatch"
                )
            if control_cell.provider_basis != treatment_cell.provider_basis:
                raise PathDependenceComparisonError(
                    "comparison_basis_mismatch"
                )
            if (
                control_cell.channel_manifest
                and treatment_cell.channel_manifest
                and control_cell.channel_manifest
                != treatment_cell.channel_manifest
            ):
                raise PathDependenceComparisonError(
                    "comparison_basis_mismatch"
                )
            if (
                control_cell.root_id is not None
                and treatment_cell.root_id is not None
                and control_cell.root_id != treatment_cell.root_id
            ):
                raise PathDependenceComparisonError(
                    "comparison_lineage_mismatch"
                )
            for cell in (control_cell, treatment_cell):
                if (
                    cell.planned_child_run_id is not None
                    and cell.child_run_id is not None
                    and cell.planned_child_run_id != cell.child_run_id
                ):
                    raise PathDependenceComparisonError(
                        "comparison_lineage_mismatch"
                    )
            if control_cell.value is None or treatment_cell.value is None:
                missing += 1
                excluded += 1
                continue
            delta = treatment_cell.value - control_cell.value
            root_id = control_cell.root_id or treatment_cell.root_id
            block_key = root_id if root_id is not None else (
                f"seed:{control_cell.numeric_seed}"
            )
            block_values[block_key].append(delta)
            block_seed.setdefault(block_key, control_cell.numeric_seed)
            block_root.setdefault(block_key, root_id)
            block_members[block_key].extend(
                (control_cell.cell_id, treatment_cell.cell_id)
            )
            channel_values.extend(
                (
                    control_cell.channel_alignment,
                    treatment_cell.channel_alignment,
                )
            )
            provider_values.add(control_cell.provider_basis)
            paired += 1
        block_keys = sorted(block_values)
        block_means = [
            statistics.fmean(block_values[key]) for key in block_keys
        ]
        interval = student_t_interval(
            block_means, confidence=request.confidence
        )
        blocks = tuple(
            SeedBlockSummary(
                numeric_seed=block_seed[key],
                paired_count=len(block_values[key]),
                mean=quantize_float(statistics.fmean(block_values[key])),
                membership=tuple(sorted(block_members[key])),
                root_id=block_root[key],
            )
            for key in block_keys
        )
        results.append(
            PairedContrastComparison(
                contrast_id=contrast_id,
                outcome_key=outcome_key,
                window_id=window_id,
                fork_tick=fork_tick,
                block_count=len(block_means),
                branch_count=len(request.cells),
                paired_slot_count=paired,
                missing_slot_count=missing,
                excluded_slot_count=excluded,
                mean=(
                    None
                    if interval.mean is None
                    else quantize_float(interval.mean)
                ),
                sample_sd=(
                    None
                    if interval.sample_sd is None
                    else quantize_float(interval.sample_sd)
                ),
                standard_error=(
                    None
                    if interval.standard_error is None
                    else quantize_float(interval.standard_error)
                ),
                df=interval.df,
                ci_low=(
                    None if interval.low is None else quantize_float(interval.low)
                ),
                ci_high=(
                    None
                    if interval.high is None
                    else quantize_float(interval.high)
                ),
                status=interval.status,
                blocks=blocks,
                channel_alignment=_channel_summary(channel_values),
                arm_counts=tuple(
                    sorted(arm_counts_by_group[group_key].items())
                ),
                provider_basis=(
                    next(iter(provider_values))
                    if len(provider_values) == 1
                    else "mixed"
                ),
                interval_method=(
                    "pointwise_two_sided_student_t_"
                    f"{request.confidence:.2f}"
                ),
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
