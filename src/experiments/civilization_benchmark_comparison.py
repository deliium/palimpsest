"""Thin comparison composer for V3 civilization benchmark outcomes.

This module does not introduce a universal culture, institution, or civilization
score. It composes the existing repeated-seed Student-t policy over the scalar
outcomes a completed benchmark attempt actually retained, keeps descriptive and
inferential summaries separate, and delegates grouped historical-fork scalar
contrasts to the existing path-dependence estimator.

The inferential unit is one independent numeric-seed block. A benchmark cell is
eligible only when its execution completed the declared horizon and its retained
evidence is complete. Early nonfailure stops, partial evidence, unavailable
measurements and missing pairs are recorded with their original denominators;
they are never counted as passing blocks.
"""

from __future__ import annotations

import logging
import math
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.numerical import quantize_float
from analysis.path_dependence_comparison import (
    ComparisonContrast,
    PairedContrastComparison,
    PathDependenceComparisonError,
    PathDependenceComparisonRequest,
    PathDependenceOutcomeCell,
    build_path_dependence_comparison,
)
from analysis.seed_block_statistics import student_t_interval
from experiments.civilization_benchmark_models import (
    V3_BENCHMARK_SUITE_ID,
    V3BenchmarkContrastKind,
    V3BenchmarkTreatmentScope,
)
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_comparison"
)

BENCHMARK_COMPARISON_SCHEMA_ID: Final[str] = "civilization-benchmark-comparison-v1"
DESCRIPTIVE_METHOD: Final[str] = "descriptive_seed_block_mean"
PAIRED_METHOD: Final[str] = "student_t_seed_block_paired_difference"
PAIRING_BASIS: Final[str] = "numeric_seed"
MULTIPLICITY_POLICY: Final[str] = "pointwise_exploratory_no_familywise_claim"
INFERENTIAL_PROVIDER_BASES: Final[frozenset[str]] = frozenset(
    {"deterministic_fake", "immutable_replay"}
)
POPULATION_SCOPES: Final[frozenset[str]] = frozenset(
    {"founder_roster", "whole_population"}
)
OBSERVATION_AVAILABILITIES: Final[frozenset[str]] = frozenset(
    {"present", "unavailable", "partial", "unknown"}
)
_EXECUTION_COMPLETED: Final[str] = "completed"
_EVIDENCE_COMPLETE: Final[str] = "complete"

_ASSUMPTIONS: Final[tuple[str, ...]] = (
    "independent_numeric_seed_blocks",
    "approximately_well_behaved_seed_block_means",
    "within_run_census_not_resampled",
)


class BenchmarkComparisonError(ValueError):
    """Fail-closed comparison error with a stable, payload-free code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
        _LOG.error("v3_benchmark_comparison_invalid reason_code=%s", code)


@dataclass(frozen=True, slots=True)
class BenchmarkModeEntry:
    """One agent's materialized mode vector inside one benchmark arm."""

    agent_id: str
    founder: bool
    modes: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "agent_id", require_stable_id("agent_id", self.agent_id)
        )
        if type(self.founder) is not bool:
            raise BenchmarkComparisonError("comparison_basis_mismatch")
        if isinstance(self.modes, (str, bytes)) or not isinstance(
            self.modes, Sequence
        ):
            raise BenchmarkComparisonError("comparison_basis_mismatch")
        normalized: list[tuple[str, str]] = []
        seen: set[str] = set()
        for entry in self.modes:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise BenchmarkComparisonError("comparison_basis_mismatch")
            mode_id, value = entry
            if type(mode_id) is not str or type(value) is not str:
                raise BenchmarkComparisonError("comparison_basis_mismatch")
            require_stable_id("mode_id", mode_id)
            if not value.strip():
                raise BenchmarkComparisonError("comparison_basis_mismatch")
            if mode_id in seen:
                raise BenchmarkComparisonError("comparison_basis_mismatch")
            seen.add(mode_id)
            normalized.append((mode_id, value))
        object.__setattr__(self, "modes", tuple(normalized))

    def mode_map(self) -> dict[str, str]:
        return dict(self.modes)


@dataclass(frozen=True, slots=True)
class BenchmarkTreatmentDesign:
    """Declared contrast with the materialized scope actually observed."""

    contrast_id: str
    control_arm_id: str
    treatment_arm_id: str
    treatment_scope: V3BenchmarkTreatmentScope
    contrast_kind: V3BenchmarkContrastKind
    founder_ids: tuple[str, ...] = ()
    control_initializer_profile_id: str = ""
    treatment_initializer_profile_id: str = ""
    declared_changed_modes: tuple[str, ...] = ()
    control_modes: tuple[BenchmarkModeEntry, ...] = ()
    treatment_modes: tuple[BenchmarkModeEntry, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "contrast_id",
            "control_arm_id",
            "treatment_arm_id",
        ):
            object.__setattr__(
                self, name, require_stable_id(name, getattr(self, name))
            )
        if self.control_arm_id == self.treatment_arm_id:
            raise BenchmarkComparisonError("comparison_basis_mismatch")
        if type(self.treatment_scope) is not V3BenchmarkTreatmentScope:
            raise BenchmarkComparisonError("invalid_treatment_scope")
        if type(self.contrast_kind) is not V3BenchmarkContrastKind:
            raise BenchmarkComparisonError("invalid_contrast_kind")
        if isinstance(self.founder_ids, (set, frozenset)) or not isinstance(
            self.founder_ids, Sequence
        ):
            raise BenchmarkComparisonError("comparison_basis_mismatch")
        founders = tuple(
            require_stable_id("founder_id", item) for item in self.founder_ids
        )
        if len(set(founders)) != len(founders):
            raise BenchmarkComparisonError("comparison_basis_mismatch")
        object.__setattr__(self, "founder_ids", founders)
        for name in (
            "control_initializer_profile_id",
            "treatment_initializer_profile_id",
        ):
            value = getattr(self, name)
            if value:
                object.__setattr__(
                    self, name, require_stable_id(name, value)
                )
        declared = tuple(
            require_stable_id("changed_mode", item)
            for item in self.declared_changed_modes
        )
        if len(set(declared)) != len(declared):
            raise BenchmarkComparisonError("comparison_basis_mismatch")
        object.__setattr__(self, "declared_changed_modes", declared)
        object.__setattr__(
            self, "control_modes", _mode_entries(self.control_modes)
        )
        object.__setattr__(
            self, "treatment_modes", _mode_entries(self.treatment_modes)
        )
        validate_treatment_design(self)

    @property
    def founder_only(self) -> bool:
        return self.treatment_scope is V3BenchmarkTreatmentScope.FOUNDER_ROSTER


def _mode_entries(value: object) -> tuple[BenchmarkModeEntry, ...]:
    if isinstance(value, (str, bytes, set, frozenset, Mapping)) or not isinstance(
        value, Sequence
    ):
        raise BenchmarkComparisonError("comparison_basis_mismatch")
    entries = tuple(value)
    for entry in entries:
        if type(entry) is not BenchmarkModeEntry:
            raise BenchmarkComparisonError("comparison_basis_mismatch")
    agent_ids = [entry.agent_id for entry in entries]
    if len(set(agent_ids)) != len(agent_ids):
        raise BenchmarkComparisonError("comparison_basis_mismatch")
    return entries


@dataclass(frozen=True, slots=True)
class TreatmentDesignValidation:
    """Actually materialized differences, never inferred from labels."""

    changed_modes: tuple[str, ...]
    changed_agent_ids: tuple[str, ...]
    founder_changed_agent_ids: tuple[str, ...]
    entrant_changed_agent_ids: tuple[str, ...]
    entrant_modes_unchanged: bool


def validate_treatment_design(
    design: BenchmarkTreatmentDesign,
) -> TreatmentDesignValidation:
    """Verify the declared contrast against the materialized mode vectors."""
    if type(design) is not BenchmarkTreatmentDesign:
        raise BenchmarkComparisonError("comparison_basis_mismatch")
    scope = design.treatment_scope
    kind = design.contrast_kind
    if scope is V3BenchmarkTreatmentScope.NONE:
        if kind is not V3BenchmarkContrastKind.NONE:
            raise BenchmarkComparisonError("treatment_scope_mismatch")
        if design.declared_changed_modes:
            raise BenchmarkComparisonError("untreated_mode_change")
    elif scope is V3BenchmarkTreatmentScope.INITIALIZER_PROFILE:
        if kind is not V3BenchmarkContrastKind.COMPOSITE_PROFILE:
            raise BenchmarkComparisonError("composite_profile_required")
        if (
            not design.control_initializer_profile_id
            or not design.treatment_initializer_profile_id
        ):
            raise BenchmarkComparisonError("composite_profile_required")
        if (
            design.control_initializer_profile_id
            == design.treatment_initializer_profile_id
        ):
            raise BenchmarkComparisonError(
                "composite_profile_requires_distinct_initializers"
            )
        if not design.declared_changed_modes:
            raise BenchmarkComparisonError("composite_modes_undeclared")
    else:
        if kind is not V3BenchmarkContrastKind.SINGLE_FACTOR:
            raise BenchmarkComparisonError("treatment_scope_mismatch")
    validation = _materialized_difference(design)
    if scope is V3BenchmarkTreatmentScope.INITIALIZER_PROFILE:
        declared = set(design.declared_changed_modes)
        actual = set(validation.changed_modes)
        if actual != declared:
            if actual - declared:
                raise BenchmarkComparisonError("composite_modes_undeclared")
            raise BenchmarkComparisonError("composite_declaration_mismatch")
    elif scope is V3BenchmarkTreatmentScope.FOUNDER_ROSTER:
        if not design.founder_ids:
            raise BenchmarkComparisonError("founder_roster_required")
        declared_agents = set(design.founder_ids)
        listed = {
            entry.agent_id
            for entry in design.control_modes
            if entry.founder
        } | {entry.agent_id for entry in design.treatment_modes if entry.founder}
        if listed != declared_agents:
            raise BenchmarkComparisonError("founder_roster_mismatch")
        if validation.entrant_changed_agent_ids:
            raise BenchmarkComparisonError("entrant_mode_treatment")
        if not validation.founder_changed_agent_ids:
            raise BenchmarkComparisonError("founder_treatment_missing")
    elif scope is V3BenchmarkTreatmentScope.RUN_OPPORTUNITY:
        if validation.changed_agent_ids:
            raise BenchmarkComparisonError("run_opportunity_requires_shared_modes")
        if (
            design.control_initializer_profile_id
            and design.treatment_initializer_profile_id
            and design.control_initializer_profile_id
            != design.treatment_initializer_profile_id
        ):
            raise BenchmarkComparisonError(
                "run_opportunity_requires_same_initializer"
            )
    elif validation.changed_agent_ids:
        raise BenchmarkComparisonError("untreated_mode_change")
    return validation


def _materialized_difference(
    design: BenchmarkTreatmentDesign,
) -> TreatmentDesignValidation:
    control = {entry.agent_id: entry for entry in design.control_modes}
    treatment = {entry.agent_id: entry for entry in design.treatment_modes}
    if set(control) != set(treatment):
        raise BenchmarkComparisonError("comparison_basis_mismatch")
    changed_modes: set[str] = set()
    changed_agents: list[str] = []
    founder_changed: list[str] = []
    entrant_changed: list[str] = []
    for agent_id in sorted(control):
        left = control[agent_id]
        right = treatment[agent_id]
        if left.founder != right.founder:
            raise BenchmarkComparisonError("comparison_basis_mismatch")
        left_modes = left.mode_map()
        right_modes = right.mode_map()
        if set(left_modes) != set(right_modes):
            raise BenchmarkComparisonError("comparison_basis_mismatch")
        differing = {
            mode_id
            for mode_id in left_modes
            if left_modes[mode_id] != right_modes[mode_id]
        }
        if not differing:
            continue
        changed_modes.update(differing)
        changed_agents.append(agent_id)
        if left.founder:
            founder_changed.append(agent_id)
        else:
            entrant_changed.append(agent_id)
    return TreatmentDesignValidation(
        changed_modes=tuple(sorted(changed_modes)),
        changed_agent_ids=tuple(changed_agents),
        founder_changed_agent_ids=tuple(founder_changed),
        entrant_changed_agent_ids=tuple(entrant_changed),
        entrant_modes_unchanged=not entrant_changed,
    )


@dataclass(frozen=True, slots=True)
class BenchmarkComparisonObservation:
    """One retained scalar outcome from one benchmark attempt."""

    cell_id: str
    scenario_id: str
    contrast_id: str
    arm_id: str
    numeric_seed: int
    seed_ordinal: int
    replicate: int
    outcome_key: str
    window_id: str
    value: float | None
    execution_status: str
    declared_horizon: int
    ticks_committed: int
    evidence: str
    population_scope: str
    availability: str = "present"
    source_digest: str = ""
    provider_basis: str = "deterministic_fake"

    def __post_init__(self) -> None:
        for name in (
            "cell_id",
            "scenario_id",
            "contrast_id",
            "arm_id",
            "outcome_key",
            "window_id",
            "execution_status",
            "evidence",
            "population_scope",
            "availability",
        ):
            value = getattr(self, name)
            if type(value) is not str or not value.strip():
                raise BenchmarkComparisonError("comparison_basis_mismatch")
            require_stable_id(name, value)
        if self.population_scope not in POPULATION_SCOPES:
            raise BenchmarkComparisonError("comparison_basis_mismatch")
        if self.availability not in OBSERVATION_AVAILABILITIES:
            raise BenchmarkComparisonError("comparison_basis_mismatch")
        for name in (
            "numeric_seed",
            "seed_ordinal",
            "replicate",
            "declared_horizon",
            "ticks_committed",
        ):
            value = getattr(self, name)
            if type(value) is not int or isinstance(value, bool) or value < 0:
                raise BenchmarkComparisonError("comparison_basis_mismatch")
        if self.declared_horizon < 1:
            raise BenchmarkComparisonError("comparison_basis_mismatch")
        if self.ticks_committed > self.declared_horizon:
            raise BenchmarkComparisonError("comparison_basis_mismatch")
        if self.value is None:
            if self.availability == "present":
                raise BenchmarkComparisonError("comparison_basis_mismatch")
        else:
            if type(self.value) not in (int, float) or isinstance(self.value, bool):
                raise BenchmarkComparisonError("comparison_basis_mismatch")
            number = float(self.value)
            if not math.isfinite(number):
                raise BenchmarkComparisonError("comparison_incompatible")
            object.__setattr__(self, "value", number)
            if self.availability != "present":
                raise BenchmarkComparisonError("comparison_basis_mismatch")
        if self.source_digest:
            require_stable_id("source_digest", self.source_digest)
        if type(self.provider_basis) is not str or not self.provider_basis.strip():
            raise BenchmarkComparisonError("comparison_basis_mismatch")


def _eligibility_reasons(
    observation: BenchmarkComparisonObservation,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if observation.execution_status != _EXECUTION_COMPLETED:
        reasons.append("execution_not_completed")
    if observation.ticks_committed != observation.declared_horizon:
        reasons.append("horizon_incomplete")
    if observation.evidence != _EVIDENCE_COMPLETE:
        reasons.append("evidence_not_complete")
    if observation.availability != "present" or observation.value is None:
        reasons.append("measurement_unavailable")
    return tuple(reasons)


@dataclass(frozen=True, slots=True)
class BenchmarkSeedBlock:
    numeric_seed: int
    value: float
    cell_ids: tuple[str, ...]

    @property
    def replicate_count(self) -> int:
        return len(self.cell_ids)


@dataclass(frozen=True, slots=True)
class BenchmarkDescriptiveSummary:
    arm_id: str
    outcome_key: str
    window_id: str
    method: str
    confidence: float
    assumptions: tuple[str, ...]
    block_count: int
    raw_observation_count: int
    duplicate_seed_observation_count: int
    mean: float | None
    std_sample: float | None
    ci_low: float | None
    ci_high: float | None
    df: int | None
    inference_status: str
    seed_blocks: tuple[BenchmarkSeedBlock, ...]
    excluded_cell_ids: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkContrastSummary:
    contrast_id: str
    control_arm_id: str
    treatment_arm_id: str
    outcome_key: str
    window_id: str
    treatment_scope: V3BenchmarkTreatmentScope
    contrast_kind: V3BenchmarkContrastKind
    founder_only: bool
    method: str
    confidence: float
    assumptions: tuple[str, ...]
    pairing_basis: str
    multiplicity_policy: str
    paired_block_count: int
    missing_pair_count: int
    descriptive_only_observation_count: int
    excluded_pair_count: int
    mean_difference: float | None
    std_sample: float | None
    ci_low: float | None
    ci_high: float | None
    df: int | None
    inference_status: str
    seed_blocks: tuple[BenchmarkSeedBlock, ...]
    excluded_cell_ids: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class V3BenchmarkComparison:
    schema_version: str
    suite_id: str
    confidence: float
    method: str
    descriptive: tuple[BenchmarkDescriptiveSummary, ...]
    contrasts: tuple[BenchmarkContrastSummary, ...]
    excluded_cells: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "suite_id": self.suite_id,
            "confidence": quantize_float(self.confidence),
            "method": self.method,
            "descriptive": [
                _descriptive_payload(item) for item in self.descriptive
            ],
            "contrasts": [_contrast_payload(item) for item in self.contrasts],
            "excluded_cells": list(self.excluded_cells),
            "reasons": list(self.reasons),
        }


def _block_payload(block: BenchmarkSeedBlock) -> dict[str, object]:
    return {
        "numeric_seed": block.numeric_seed,
        "value": quantize_float(block.value),
        "cell_ids": list(block.cell_ids),
        "replicate_count": block.replicate_count,
    }


def _quantized_optional(value: float | None) -> float | None:
    return None if value is None else quantize_float(value)


def _descriptive_payload(item: BenchmarkDescriptiveSummary) -> dict[str, object]:
    return {
        "arm_id": item.arm_id,
        "outcome_key": item.outcome_key,
        "window_id": item.window_id,
        "method": item.method,
        "confidence": quantize_float(item.confidence),
        "assumptions": list(item.assumptions),
        "block_count": item.block_count,
        "raw_observation_count": item.raw_observation_count,
        "duplicate_seed_observation_count": (
            item.duplicate_seed_observation_count
        ),
        "mean": _quantized_optional(item.mean),
        "std_sample": _quantized_optional(item.std_sample),
        "ci_low": _quantized_optional(item.ci_low),
        "ci_high": _quantized_optional(item.ci_high),
        "df": item.df,
        "inference_status": item.inference_status,
        "seed_blocks": [_block_payload(block) for block in item.seed_blocks],
        "excluded_cell_ids": list(item.excluded_cell_ids),
        "reasons": list(item.reasons),
    }


def _contrast_payload(item: BenchmarkContrastSummary) -> dict[str, object]:
    return {
        "contrast_id": item.contrast_id,
        "control_arm_id": item.control_arm_id,
        "treatment_arm_id": item.treatment_arm_id,
        "outcome_key": item.outcome_key,
        "window_id": item.window_id,
        "treatment_scope": item.treatment_scope.value,
        "contrast_kind": item.contrast_kind.value,
        "founder_only": item.founder_only,
        "method": item.method,
        "confidence": quantize_float(item.confidence),
        "assumptions": list(item.assumptions),
        "pairing_basis": item.pairing_basis,
        "multiplicity_policy": item.multiplicity_policy,
        "paired_block_count": item.paired_block_count,
        "missing_pair_count": item.missing_pair_count,
        "descriptive_only_observation_count": item.descriptive_only_observation_count,
        "excluded_pair_count": item.excluded_pair_count,
        "mean_difference": _quantized_optional(item.mean_difference),
        "std_sample": _quantized_optional(item.std_sample),
        "ci_low": _quantized_optional(item.ci_low),
        "ci_high": _quantized_optional(item.ci_high),
        "df": item.df,
        "inference_status": item.inference_status,
        "seed_blocks": [_block_payload(block) for block in item.seed_blocks],
        "excluded_cell_ids": list(item.excluded_cell_ids),
        "reasons": list(item.reasons),
    }


def _seed_blocks(
    observations: Sequence[BenchmarkComparisonObservation],
) -> tuple[tuple[BenchmarkSeedBlock, ...], int]:
    grouped: dict[int, list[BenchmarkComparisonObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.numeric_seed].append(observation)
    blocks = tuple(
        BenchmarkSeedBlock(
            numeric_seed=seed,
            value=statistics.fmean(
                float(item.value) for item in items if item.value is not None
            ),
            cell_ids=tuple(sorted(item.cell_id for item in items)),
        )
        for seed, items in sorted(grouped.items())
    )
    raw = sum(len(items) for items in grouped.values())
    return blocks, raw - len(grouped)


def _descriptive_summaries(
    observations: Sequence[BenchmarkComparisonObservation],
    *,
    confidence: float,
) -> tuple[BenchmarkDescriptiveSummary, ...]:
    grouped: dict[tuple[str, str, str], list[BenchmarkComparisonObservation]] = (
        defaultdict(list)
    )
    for observation in observations:
        grouped[
            (observation.arm_id, observation.outcome_key, observation.window_id)
        ].append(observation)
    summaries: list[BenchmarkDescriptiveSummary] = []
    for (arm_id, outcome_key, window_id), items in sorted(grouped.items()):
        eligible: list[BenchmarkComparisonObservation] = []
        excluded: list[str] = []
        reasons: set[str] = set()
        for item in items:
            item_reasons = _eligibility_reasons(item)
            if not item_reasons:
                eligible.append(item)
            else:
                excluded.append(item.cell_id)
                reasons.update(item_reasons)
        blocks, duplicates = _seed_blocks(eligible)
        means = [block.value for block in blocks]
        interval = student_t_interval(means, confidence=confidence)
        status = interval.status
        low, high = interval.low, interval.high
        if any(
            item.provider_basis not in INFERENTIAL_PROVIDER_BASES
            for item in eligible
        ):
            low, high, status = None, None, "uncontrolled_provider_variation"
        summaries.append(
            BenchmarkDescriptiveSummary(
                arm_id=arm_id,
                outcome_key=outcome_key,
                window_id=window_id,
                method=DESCRIPTIVE_METHOD,
                confidence=confidence,
                assumptions=_ASSUMPTIONS,
                block_count=len(blocks),
                raw_observation_count=len(items),
                duplicate_seed_observation_count=duplicates,
                mean=interval.mean,
                std_sample=interval.sample_sd,
                ci_low=low,
                ci_high=high,
                df=interval.df,
                inference_status=status,
                seed_blocks=blocks,
                excluded_cell_ids=tuple(sorted(excluded)),
                reasons=tuple(sorted(reasons)),
            )
        )
    return tuple(summaries)


def _contrast_summaries(
    observations: Sequence[BenchmarkComparisonObservation],
    designs: Sequence[BenchmarkTreatmentDesign],
    *,
    confidence: float,
) -> tuple[BenchmarkContrastSummary, ...]:
    by_key: dict[
        tuple[str, str, str], list[BenchmarkComparisonObservation]
    ] = defaultdict(list)
    for observation in observations:
        by_key[
            (
                observation.contrast_id,
                observation.outcome_key,
                observation.window_id,
            )
        ].append(observation)
    summaries: list[BenchmarkContrastSummary] = []
    for design in designs:
        keys = sorted(
            {
                (outcome_key, window_id)
                for contrast_id, outcome_key, window_id in by_key
                if contrast_id == design.contrast_id
            }
        )
        for outcome_key, window_id in keys:
            items = by_key[(design.contrast_id, outcome_key, window_id)]
            control: list[BenchmarkComparisonObservation] = []
            treatment: list[BenchmarkComparisonObservation] = []
            excluded: list[str] = []
            reasons: set[str] = set()
            descriptive_only = 0
            for item in items:
                if item.arm_id not in {
                    design.control_arm_id,
                    design.treatment_arm_id,
                }:
                    raise BenchmarkComparisonError("unknown_arm")
                item_reasons = _eligibility_reasons(item)
                if item_reasons:
                    excluded.append(item.cell_id)
                    reasons.update(item_reasons)
                    continue
                if design.founder_only and item.population_scope != "founder_roster":
                    excluded.append(item.cell_id)
                    reasons.add("founder_scope_overreach")
                    descriptive_only += 1
                    continue
                if item.arm_id == design.control_arm_id:
                    control.append(item)
                else:
                    treatment.append(item)
            control_blocks, _ = _seed_blocks(control)
            treatment_blocks, _ = _seed_blocks(treatment)
            control_by_seed = {
                block.numeric_seed: block for block in control_blocks
            }
            treatment_by_seed = {
                block.numeric_seed: block for block in treatment_blocks
            }
            seeds = sorted(set(control_by_seed) & set(treatment_by_seed))
            missing = len(set(control_by_seed) ^ set(treatment_by_seed))
            if missing:
                reasons.add("missing_paired_block")
            deltas = tuple(
                BenchmarkSeedBlock(
                    numeric_seed=seed,
                    value=(
                        treatment_by_seed[seed].value
                        - control_by_seed[seed].value
                    ),
                    cell_ids=(
                        *control_by_seed[seed].cell_ids,
                        *treatment_by_seed[seed].cell_ids,
                    ),
                )
                for seed in seeds
            )
            interval = student_t_interval(
                [block.value for block in deltas], confidence=confidence
            )
            status = interval.status
            low, high = interval.low, interval.high
            if any(
                item.provider_basis not in INFERENTIAL_PROVIDER_BASES
                for item in control + treatment
            ):
                low, high, status = None, None, "uncontrolled_provider_variation"
            if descriptive_only:
                reasons.add("founder_scope_overreach")
            mean_difference = interval.mean
            if len(deltas) == 1:
                status = "descriptive_single_seed_block"
            summaries.append(
                BenchmarkContrastSummary(
                    contrast_id=design.contrast_id,
                    control_arm_id=design.control_arm_id,
                    treatment_arm_id=design.treatment_arm_id,
                    outcome_key=outcome_key,
                    window_id=window_id,
                    treatment_scope=design.treatment_scope,
                    contrast_kind=design.contrast_kind,
                    founder_only=design.founder_only,
                    method=PAIRED_METHOD,
                    confidence=confidence,
                    assumptions=_ASSUMPTIONS,
                    pairing_basis=PAIRING_BASIS,
                    multiplicity_policy=MULTIPLICITY_POLICY,
                    paired_block_count=len(deltas),
                    missing_pair_count=missing,
                    descriptive_only_observation_count=descriptive_only,
                    excluded_pair_count=len(excluded),
                    mean_difference=mean_difference,
                    std_sample=interval.sample_sd,
                    ci_low=low,
                    ci_high=high,
                    df=interval.df,
                    inference_status=status,
                    seed_blocks=deltas,
                    excluded_cell_ids=tuple(sorted(excluded)),
                    reasons=tuple(sorted(reasons)),
                )
            )
    return tuple(summaries)


def build_v3_benchmark_comparison(
    observations: Sequence[BenchmarkComparisonObservation],
    designs: Sequence[BenchmarkTreatmentDesign] = (),
    *,
    confidence: float = 0.95,
    suite_id: str = V3_BENCHMARK_SUITE_ID,
) -> V3BenchmarkComparison:
    """Build descriptive and predeclared paired summaries over seed blocks."""
    if type(confidence) not in (int, float) or isinstance(confidence, bool):
        raise BenchmarkComparisonError("invalid_confidence")
    value = float(confidence)
    if not math.isfinite(value) or not 0.0 < value < 1.0:
        raise BenchmarkComparisonError("invalid_confidence")
    suite = require_stable_id("suite_id", suite_id)
    observation_shape_invalid = isinstance(
        observations, (str, bytes, set, frozenset, Mapping)
    ) or not isinstance(observations, Sequence)
    if observation_shape_invalid:
        raise BenchmarkComparisonError("comparison_basis_mismatch")
    if isinstance(designs, (str, bytes, set, frozenset, Mapping)) or not isinstance(
        designs, Sequence
    ):
        raise BenchmarkComparisonError("comparison_basis_mismatch")
    normalized: list[BenchmarkComparisonObservation] = []
    seen_cells: set[str] = set()
    for observation in observations:
        if type(observation) is not BenchmarkComparisonObservation:
            raise BenchmarkComparisonError("comparison_basis_mismatch")
        if observation.cell_id in seen_cells:
            raise BenchmarkComparisonError("duplicate_comparison_cell")
        seen_cells.add(observation.cell_id)
        normalized.append(observation)
    normalized_designs: list[BenchmarkTreatmentDesign] = []
    seen_contrasts: set[str] = set()
    for design in designs:
        if type(design) is not BenchmarkTreatmentDesign:
            raise BenchmarkComparisonError("comparison_basis_mismatch")
        if design.contrast_id in seen_contrasts:
            raise BenchmarkComparisonError("duplicate_contrast")
        seen_contrasts.add(design.contrast_id)
        normalized_designs.append(design)
    known_contrasts = {design.contrast_id for design in normalized_designs}
    for observation in normalized:
        if observation.contrast_id == "none":
            continue
        if observation.contrast_id not in known_contrasts:
            if normalized_designs:
                raise BenchmarkComparisonError("unknown_contrast")
    descriptive = _descriptive_summaries(normalized, confidence=value)
    contrasts = _contrast_summaries(
        normalized, tuple(normalized_designs), confidence=value
    )
    excluded_ids: set[str] = set()
    reason_codes: set[str] = set()
    for summary in descriptive:
        excluded_ids.update(summary.excluded_cell_ids)
        reason_codes.update(summary.reasons)
    for contrast in contrasts:
        excluded_ids.update(contrast.excluded_cell_ids)
        reason_codes.update(contrast.reasons)
    comparison = V3BenchmarkComparison(
        schema_version=BENCHMARK_COMPARISON_SCHEMA_ID,
        suite_id=suite,
        confidence=value,
        method=PAIRED_METHOD,
        descriptive=descriptive,
        contrasts=contrasts,
        excluded_cells=tuple(sorted(excluded_ids)),
        reasons=tuple(sorted(reason_codes)),
    )
    _LOG.info(
        "v3_benchmark_comparison_built observation_count=%s descriptive_count=%s "
        "contrast_count=%s excluded_count=%s",
        len(normalized),
        len(descriptive),
        len(contrasts),
        len(excluded_ids),
    )
    return comparison


def compare_grouped_benchmark_outcomes(
    cells: Sequence[PathDependenceOutcomeCell],
    contrasts: Sequence[ComparisonContrast],
    *,
    confidence: float = 0.95,
) -> tuple[PairedContrastComparison, ...]:
    """Delegate grouped scalar contrasts to the existing seed-block estimator."""
    try:
        request = PathDependenceComparisonRequest(
            cells=tuple(cells),
            contrasts=tuple(contrasts),
            confidence=confidence,
        )
        return build_path_dependence_comparison(request)
    except PathDependenceComparisonError as exc:
        raise BenchmarkComparisonError(exc.code) from exc


__all__ = [
    "BENCHMARK_COMPARISON_SCHEMA_ID",
    "DESCRIPTIVE_METHOD",
    "MULTIPLICITY_POLICY",
    "PAIRED_METHOD",
    "PAIRING_BASIS",
    "BenchmarkComparisonError",
    "BenchmarkComparisonObservation",
    "BenchmarkContrastSummary",
    "BenchmarkDescriptiveSummary",
    "BenchmarkModeEntry",
    "BenchmarkSeedBlock",
    "BenchmarkTreatmentDesign",
    "TreatmentDesignValidation",
    "V3BenchmarkComparison",
    "build_v3_benchmark_comparison",
    "compare_grouped_benchmark_outcomes",
    "validate_treatment_design",
]
