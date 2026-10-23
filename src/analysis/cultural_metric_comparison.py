"""Repeated-seed means, Student-t intervals and explicit paired contrasts.

The inferential unit is an independent numeric-seed block, never an agent,
tick, acquisition edge, or trait row. Within-run frequencies are censuses over
observed inventories and receive no binomial interval here.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from scipy import stats

from analysis.cultural_evolution_evidence import CulturalMeasurement
from analysis.cultural_evolution_transmission import (
    CULTURAL_EVOLUTION_TRANSMISSION_ALGORITHM_VERSION,
)
from analysis.cultural_narrative_survival import (
    CULTURAL_NARRATIVE_SURVIVAL_ALGORITHM_VERSION,
)
from analysis.cultural_population_structure import (
    CULTURAL_POPULATION_STRUCTURE_ALGORITHM_VERSION,
)
from analysis.cultural_technology_continuity import (
    CULTURAL_TECHNOLOGY_CONTINUITY_ALGORITHM_VERSION,
)
from analysis.cultural_trait_dynamics import CULTURAL_TRAIT_DYNAMICS_ALGORITHM_VERSION
from analysis.cultural_vocabulary_differentiation import (
    CULTURAL_VOCABULARY_DIFFERENTIATION_ALGORITHM_VERSION,
)
from analysis.models import MetricAvailability, MetricDocument
from analysis.numerical import quantize_float
from world.identifiers import require_stable_id

CULTURAL_METRIC_COMPARISON_SCHEMA_VERSION: Final[str] = "cultural-metric-comparison-v1"
STUDENT_T_METHOD: Final[str] = "student_t_seed_block_mean"
PAIRED_STUDENT_T_METHOD: Final[str] = "student_t_seed_block_paired_difference"
PAIRING_BASIS: Final[str] = "seed_ordinal_replicate"
ALLOWED_PROVIDER_BASES: Final[frozenset[str]] = frozenset(
    {"deterministic_fake", "immutable_replay", "live", "record", "cache", "unknown"}
)
INFERENTIAL_PROVIDER_BASES: Final[frozenset[str]] = frozenset(
    {"deterministic_fake", "immutable_replay"}
)
_ROW_ALGORITHM_VERSIONS: Final[Mapping[str, str]] = {
    "cultural_trait_dynamics": CULTURAL_TRAIT_DYNAMICS_ALGORITHM_VERSION,
    "cultural_evolution_transmission": (
        CULTURAL_EVOLUTION_TRANSMISSION_ALGORITHM_VERSION
    ),
    "cultural_population_structure": CULTURAL_POPULATION_STRUCTURE_ALGORITHM_VERSION,
    "cultural_narrative_survival": CULTURAL_NARRATIVE_SURVIVAL_ALGORITHM_VERSION,
    "cultural_vocabulary_differentiation": (
        CULTURAL_VOCABULARY_DIFFERENTIATION_ALGORITHM_VERSION
    ),
    "cultural_technology_continuity": CULTURAL_TECHNOLOGY_CONTINUITY_ALGORITHM_VERSION,
}

_ASSUMPTIONS: Final[tuple[str, ...]] = (
    "independent_numeric_seed_blocks",
    "approximately_well_behaved_seed_block_means",
    "within_run_census_not_resampled",
)

MAX_ROWS_JSON_BYTES: Final[int] = 16 * 1024 * 1024
MAX_ROWS_JSON_DEPTH: Final[int] = 32


def _duplicate_aware_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CulturalComparisonError("comparison_incompatible")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> object:
    raise CulturalComparisonError("comparison_incompatible")


def _rows_depth_ok(data: bytes) -> bool:
    depth = 0
    quoted = False
    escaped = False
    for byte in data:
        char = chr(byte)
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char in "{[":
            depth += 1
            if depth > MAX_ROWS_JSON_DEPTH:
                return False
        elif char in "}]":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _decode_rows_json(raw: str) -> list[object]:
    try:
        data = raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CulturalComparisonError("comparison_incompatible") from exc
    if len(data) > MAX_ROWS_JSON_BYTES or not _rows_depth_ok(data):
        raise CulturalComparisonError("comparison_incompatible")
    try:
        rows = json.loads(
            raw,
            object_pairs_hook=_duplicate_aware_pairs,
            parse_constant=_reject_nonfinite,
        )
    except CulturalComparisonError:
        raise
    except (TypeError, ValueError) as exc:
        raise CulturalComparisonError("comparison_incompatible") from exc
    if not isinstance(rows, list):
        raise CulturalComparisonError("comparison_incompatible")
    return rows


__all__ = [
    "CULTURAL_METRIC_COMPARISON_SCHEMA_VERSION",
    "CulturalComparisonCell",
    "CulturalComparisonError",
    "CulturalComparisonRequest",
    "CulturalConditionComparison",
    "CulturalContrastSummary",
    "CulturalMeasurementComparison",
    "CulturalMetricComparison",
    "build_cultural_metric_comparison",
]


class CulturalComparisonError(ValueError):
    """Stable, payload-free comparison failure code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CulturalComparisonCell:
    """One completed cell with verified documents and stream identity."""

    cell_id: str
    condition_id: str
    seed: int
    seed_ordinal: int
    replicate_index: int
    stochastic_identity: str
    channel_lineage: tuple[tuple[str, str], ...]
    provider_basis: str
    factor_levels: tuple[tuple[str, str], ...]
    config_fingerprint: str
    expected_config_fingerprint: str
    cell_fingerprint: str
    code_revision: str
    library_versions: Mapping[str, str]
    documents: tuple[MetricDocument, ...]
    evidence_digest: str
    group_selector_basis: str | None = None

    def __post_init__(self) -> None:
        require_stable_id("cell_id", self.cell_id)
        require_stable_id("condition_id", self.condition_id)
        for name in ("seed", "seed_ordinal", "replicate_index"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name}: must_be_nonnegative_integer")
        if self.provider_basis not in ALLOWED_PROVIDER_BASES:
            raise ValueError("provider_basis: unknown_value")
        if type(self.documents) is not tuple:
            raise TypeError("documents must be a tuple")


@dataclass(frozen=True, slots=True)
class CulturalComparisonRequest:
    """Explicit control/treatment condition selection."""

    contrast_id: str
    control_condition_id: str
    treatment_condition_id: str

    def __post_init__(self) -> None:
        for name in ("contrast_id", "control_condition_id", "treatment_condition_id"):
            require_stable_id(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class CulturalSeedBlock:
    seed: int
    value: float
    cell_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CulturalMeasurementComparison:
    measurement: Mapping[str, object]
    method: str
    confidence: float
    assumptions: tuple[str, ...]
    n: int
    raw_cell_count: int
    duplicate_cell_count: int
    mean: float | None
    std_sample: float | None
    ci_low: float | None
    ci_high: float | None
    df: int | None
    inference_status: str
    seed_blocks: tuple[CulturalSeedBlock, ...]
    excluded_cells: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CulturalConditionComparison:
    condition_id: str
    raw_cell_count: int
    seed_block_count: int
    duplicate_seed_cell_count: int
    measurements: tuple[CulturalMeasurementComparison, ...]
    excluded_cells: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CulturalContrastSummary:
    contrast_id: str
    control_condition_id: str
    treatment_condition_id: str
    measurement: Mapping[str, object]
    method: str
    confidence: float
    assumptions: tuple[str, ...]
    n: int
    mean_difference: float | None
    std_sample: float | None
    ci_low: float | None
    ci_high: float | None
    df: int | None
    inference_status: str
    pairing_basis: str
    shared_stream_status: str
    channel_alignment: tuple[tuple[str, str], ...]
    pair_ids: tuple[str, ...]
    unmatched_cells: tuple[str, ...]
    excluded_pairs: int
    seed_blocks: tuple[CulturalSeedBlock, ...]


@dataclass(frozen=True, slots=True)
class CulturalMetricComparison:
    schema_version: str
    matrix_fingerprint: str
    confidence: float
    method: str
    conditions: tuple[CulturalConditionComparison, ...]
    contrasts: tuple[CulturalContrastSummary, ...]
    excluded_cells: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "matrix_fingerprint": self.matrix_fingerprint,
            "confidence": quantize_float(self.confidence),
            "method": self.method,
            "conditions": [
                _condition_payload(condition) for condition in self.conditions
            ],
            "contrasts": [_contrast_payload(item) for item in self.contrasts],
            "excluded_cells": list(self.excluded_cells),
            "reasons": list(self.reasons),
        }


def _measurement_payload(
    row: CulturalMeasurement, cell: CulturalComparisonCell
) -> dict[str, object]:
    return {
        "family": row.family,
        "algorithm_version": row.algorithm_version,
        "policy_version": row.policy_version,
        "measurement_id": row.measurement_id,
        "dimension": row.dimension,
        "representation": row.representation,
        "scope": row.scope,
        "partition_id": row.partition_id,
        "group_ids": list(row.group_ids),
        "population_basis": row.population_basis,
        "denominator_code": row.denominator_code,
        "baseline_tick": row.baseline_tick,
        "end_tick": row.end_tick,
        "units": row.units,
        "code_revision": cell.code_revision,
        "library_versions": dict(cell.library_versions),
    }


def _quantized(payload: Mapping[str, object]) -> dict[str, object]:
    return dict(payload)


def _measurement_key(
    row: CulturalMeasurement,
    cell: CulturalComparisonCell,
) -> tuple[object, ...]:
    return (
        row.family,
        row.algorithm_version,
        row.policy_version,
        row.measurement_id,
        row.dimension,
        row.representation,
        row.scope,
        row.partition_id,
        row.group_ids,
        row.population_basis,
        row.denominator_code,
        row.baseline_tick,
        row.end_tick,
        row.units,
        cell.code_revision,
        tuple(sorted(cell.library_versions.items())),
        tuple(
            sorted(
                (document.metric_family, document.algorithm_version)
                for document in cell.documents
            )
        ),
    )


def _is_comparable_row(
    row: CulturalMeasurement,
    cell: CulturalComparisonCell,
) -> bool:
    if row.trait_id is not None or row.lineage_id is not None:
        return False
    if row.subject_id is not None:
        return False
    if row.availability is not MetricAvailability.PRESENT:
        return False
    if row.value is None or not math.isfinite(row.value):
        return False
    if row.scope in {"group", "group_pair"} and cell.group_selector_basis is None:
        return False
    return True


def _measurement_index(
    cell: CulturalComparisonCell,
) -> dict[tuple[object, ...], CulturalMeasurement]:
    index: dict[tuple[object, ...], CulturalMeasurement] = {}
    for document in cell.documents:
        raw = document.values.get("rows_json")
        if not isinstance(raw, str):
            continue
        rows = _decode_rows_json(raw)
        for item in rows:
            if not isinstance(item, Mapping):
                raise CulturalComparisonError("comparison_incompatible")
            try:
                row = CulturalMeasurement.from_payload(
                    item,
                    family=document.metric_family,
                    algorithm_version=_ROW_ALGORITHM_VERSIONS.get(
                        document.metric_family, document.algorithm_version
                    ),
                    policy_version=str(document.values.get("policy_version", "")),
                )
            except ValueError as exc:
                raise CulturalComparisonError("comparison_incompatible") from exc
            if not _is_comparable_row(row, cell):
                continue
            index[_measurement_key(row, cell)] = row
    return index


def _t_interval(
    values: Sequence[float],
    confidence: float,
) -> tuple[float | None, float | None, float | None, float | None, str]:
    n = len(values)
    if n == 0:
        return None, None, None, None, "insufficient_independent_seeds"
    mean = statistics.fmean(values)
    if n == 1:
        return mean, None, None, None, "insufficient_independent_seeds"
    sd = statistics.stdev(values)
    df = n - 1
    if sd == 0.0:
        return mean, sd, mean, mean, "present"
    margin = float(stats.t.ppf((1.0 + confidence) / 2.0, df)) * sd / math.sqrt(n)
    return mean, sd, mean - margin, mean + margin, "present"


def _seed_block_values(
    cells: Sequence[CulturalComparisonCell],
    keys: set[tuple[object, ...]],
) -> tuple[
    dict[tuple[object, ...], dict[int, list[float]]],
    dict[tuple[object, ...], dict[int, list[str]]],
    tuple[str, ...],
]:
    values: dict[tuple[object, ...], dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    membership: dict[tuple[object, ...], dict[int, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    excluded: list[str] = []
    for cell in cells:
        index = _measurement_index(cell)
        for key in keys:
            row = index.get(key)
            if row is None or row.value is None:
                excluded.append(cell.cell_id)
                continue
            values[key][cell.seed].append(float(row.value))
            membership[key][cell.seed].append(cell.cell_id)
    return dict(values), dict(membership), tuple(sorted(set(excluded)))


def _condition_comparisons(
    cells: tuple[CulturalComparisonCell, ...],
    confidence: float,
) -> tuple[CulturalConditionComparison, ...]:
    grouped: dict[str, list[CulturalComparisonCell]] = defaultdict(list)
    for cell in cells:
        grouped[cell.condition_id].append(cell)
    summaries: list[CulturalConditionComparison] = []
    for condition_id in sorted(grouped):
        condition_cells = tuple(grouped[condition_id])
        keys: set[tuple[object, ...]] = set()
        for cell in condition_cells:
            keys.update(_measurement_index(cell))
        values, membership, excluded = _seed_block_values(condition_cells, keys)
        measurements: list[CulturalMeasurementComparison] = []
        for key in sorted(keys, key=repr):
            blocks = values.get(key, {})
            block_values = [
                statistics.fmean(block_values)
                for _seed, block_values in sorted(blocks.items())
            ]
            mean, sd, low, high, status = _t_interval(block_values, confidence)
            inferential = all(
                cell.provider_basis in INFERENTIAL_PROVIDER_BASES
                for cell in condition_cells
                if _measurement_index(cell).get(key) is not None
            )
            if not inferential:
                low, high, status = None, None, "uncontrolled_provider_variation"
            seed_blocks = tuple(
                CulturalSeedBlock(
                    seed=seed,
                    value=statistics.fmean(block_values),
                    cell_ids=tuple(sorted(membership[key][seed])),
                )
                for seed, block_values in sorted(blocks.items())
            )
            representative = _representative_row(condition_cells, key)
            measurements.append(
                CulturalMeasurementComparison(
                    measurement=_measurement_payload(
                        representative[0], representative[1]
                    ),
                    method=STUDENT_T_METHOD,
                    confidence=confidence,
                    assumptions=_ASSUMPTIONS,
                    n=len(block_values),
                    raw_cell_count=sum(len(items) for items in blocks.values()),
                    duplicate_cell_count=sum(
                        len(items) - 1 for items in blocks.values()
                    ),
                    mean=mean,
                    std_sample=sd,
                    ci_low=low,
                    ci_high=high,
                    df=len(block_values) - 1 if block_values else None,
                    inference_status=status,
                    seed_blocks=seed_blocks,
                    excluded_cells=excluded,
                )
            )
        summaries.append(
            CulturalConditionComparison(
                condition_id=condition_id,
                raw_cell_count=len(condition_cells),
                seed_block_count=len({cell.seed for cell in condition_cells}),
                duplicate_seed_cell_count=(
                    len(condition_cells) - len({cell.seed for cell in condition_cells})
                ),
                measurements=tuple(measurements),
                excluded_cells=excluded,
            )
        )
    return tuple(summaries)


def _representative_row(
    cells: Sequence[CulturalComparisonCell],
    key: tuple[object, ...],
) -> tuple[CulturalMeasurement, CulturalComparisonCell]:
    for cell in cells:
        row = _measurement_index(cell).get(key)
        if row is not None:
            return row, cell
    raise CulturalComparisonError("comparison_incompatible")


def _factor_difference(
    control: CulturalComparisonCell,
    treatment: CulturalComparisonCell,
) -> tuple[tuple[str, str], tuple[str, str]] | None:
    control_levels = dict(control.factor_levels)
    treatment_levels = dict(treatment.factor_levels)
    if set(control_levels) != set(treatment_levels):
        return None
    differing = [
        (factor, control_levels[factor])
        for factor in sorted(control_levels)
        if control_levels[factor] != treatment_levels[factor]
    ]
    if len(differing) != 1:
        return None
    factor, _control_level = differing[0]
    return differing[0], (factor, treatment_levels[factor])


def _stream_status(
    control: CulturalComparisonCell,
    treatment: CulturalComparisonCell,
) -> tuple[str, tuple[tuple[str, str], ...]]:
    control_channels = dict(control.channel_lineage)
    treatment_channels = dict(treatment.channel_lineage)
    channels = sorted(set(control_channels) | set(treatment_channels))
    alignment: list[tuple[str, str]] = []
    comparable = 0
    mixed = False
    for channel in channels:
        left = control_channels.get(channel)
        right = treatment_channels.get(channel)
        if left is None or right is None:
            alignment.append((channel, "absent"))
            continue
        comparable += 1
        if left == right:
            alignment.append((channel, "shared"))
        else:
            mixed = True
            alignment.append((channel, "different"))
    if mixed:
        return "mixed", tuple(alignment)
    if comparable:
        return "shared", tuple(alignment)
    return "unknown", tuple(alignment)


def _insufficient_contrast(
    request: CulturalComparisonRequest,
    control_cells: Sequence[CulturalComparisonCell],
    treatment_cells: Sequence[CulturalComparisonCell],
) -> CulturalContrastSummary:
    return CulturalContrastSummary(
        contrast_id=request.contrast_id,
        control_condition_id=request.control_condition_id,
        treatment_condition_id=request.treatment_condition_id,
        measurement={},
        method=PAIRED_STUDENT_T_METHOD,
        confidence=0.95,
        assumptions=_ASSUMPTIONS,
        n=0,
        mean_difference=None,
        std_sample=None,
        ci_low=None,
        ci_high=None,
        df=None,
        inference_status="insufficient_evidence",
        pairing_basis=PAIRING_BASIS,
        shared_stream_status="unknown",
        channel_alignment=(),
        pair_ids=(),
        unmatched_cells=tuple(
            sorted(
                [cell.cell_id for cell in control_cells]
                + [cell.cell_id for cell in treatment_cells]
            )
        ),
        excluded_pairs=0,
        seed_blocks=(),
    )


def _contrast_summaries(
    cells: tuple[CulturalComparisonCell, ...],
    requests: Sequence[CulturalComparisonRequest],
    confidence: float,
) -> tuple[CulturalContrastSummary, ...]:
    by_condition: dict[str, list[CulturalComparisonCell]] = defaultdict(list)
    for cell in cells:
        by_condition[cell.condition_id].append(cell)
    summaries: list[CulturalContrastSummary] = []
    for request in requests:
        control_cells = by_condition.get(request.control_condition_id, [])
        treatment_cells = by_condition.get(request.treatment_condition_id, [])
        if not control_cells or not treatment_cells:
            summaries.append(
                _insufficient_contrast(request, control_cells, treatment_cells)
            )
            continue
        control = control_cells[0]
        treatment = treatment_cells[0]
        difference = _factor_difference(control, treatment)
        if difference is None:
            raise CulturalComparisonError("comparison_factor_mismatch")
        for cell in control_cells + treatment_cells:
            if cell.config_fingerprint != cell.expected_config_fingerprint:
                raise CulturalComparisonError("comparison_factor_mismatch")
        control_by_slot = {
            (cell.seed_ordinal, cell.replicate_index): cell for cell in control_cells
        }
        treatment_by_slot = {
            (cell.seed_ordinal, cell.replicate_index): cell for cell in treatment_cells
        }
        if len(control_by_slot) != len(control_cells) or len(treatment_by_slot) != len(
            treatment_cells
        ):
            raise CulturalComparisonError("duplicate_comparison_cell")
        slots = sorted(set(control_by_slot) & set(treatment_by_slot))
        unmatched = tuple(
            sorted(
                [
                    control_by_slot[slot].cell_id
                    for slot in set(control_by_slot) - set(treatment_by_slot)
                ]
                + [
                    treatment_by_slot[slot].cell_id
                    for slot in set(treatment_by_slot) - set(control_by_slot)
                ]
            )
        )
        keys: set[tuple[object, ...]] = set()
        for slot in slots:
            left = control_by_slot[slot]
            right = treatment_by_slot[slot]
            if left.seed != right.seed:
                continue
            if left.provider_basis != right.provider_basis:
                continue
            keys.update(set(_measurement_index(left)) & set(_measurement_index(right)))
        if not keys:
            raise CulturalComparisonError("comparison_incompatible")
        summaries.extend(
            _build_contrast(
                request=request,
                control_cells=control_cells,
                treatment_cells=treatment_cells,
                slots=slots,
                keys=keys,
                unmatched=unmatched,
                confidence=confidence,
            )
        )
    return tuple(summaries)


def _build_contrast(
    *,
    request: CulturalComparisonRequest,
    control_cells: Sequence[CulturalComparisonCell],
    treatment_cells: Sequence[CulturalComparisonCell],
    slots: Sequence[tuple[int, int]],
    keys: set[tuple[object, ...]],
    unmatched: tuple[str, ...],
    confidence: float,
) -> tuple[CulturalContrastSummary, ...]:
    control_by_slot = {
        (cell.seed_ordinal, cell.replicate_index): cell for cell in control_cells
    }
    treatment_by_slot = {
        (cell.seed_ordinal, cell.replicate_index): cell for cell in treatment_cells
    }
    summaries: list[CulturalContrastSummary] = []
    for key in sorted(keys, key=repr):
        block_values: dict[int, list[float]] = defaultdict(list)
        block_pairs: dict[int, list[str]] = defaultdict(list)
        excluded_pairs = 0
        for slot in slots:
            left = control_by_slot[slot]
            right = treatment_by_slot[slot]
            if left.seed != right.seed:
                excluded_pairs += 1
                continue
            if left.provider_basis != right.provider_basis:
                excluded_pairs += 1
                continue
            left_row = _measurement_index(left).get(key)
            right_row = _measurement_index(right).get(key)
            if (
                left_row is None
                or right_row is None
                or left_row.value is None
                or right_row.value is None
            ):
                excluded_pairs += 1
                continue
            block_values[left.seed].append(float(right_row.value - left_row.value))
            block_pairs[left.seed].append(f"{left.cell_id}+{right.cell_id}")
        means = [
            statistics.fmean(values) for _seed, values in sorted(block_values.items())
        ]
        mean, sd, low, high, status = _t_interval(means, confidence)
        representative = _representative_row(control_cells, key)
        status_pair = _stream_status(
            control_by_slot[slots[0]], treatment_by_slot[slots[0]]
        )
        if any(
            control_by_slot[slot].provider_basis not in INFERENTIAL_PROVIDER_BASES
            or treatment_by_slot[slot].provider_basis not in INFERENTIAL_PROVIDER_BASES
            for slot in slots
        ):
            low, high, status = None, None, "uncontrolled_provider_variation"
        summaries.append(
            CulturalContrastSummary(
                contrast_id=request.contrast_id,
                control_condition_id=request.control_condition_id,
                treatment_condition_id=request.treatment_condition_id,
                measurement=_measurement_payload(representative[0], representative[1]),
                method=PAIRED_STUDENT_T_METHOD,
                confidence=confidence,
                assumptions=_ASSUMPTIONS,
                n=len(means),
                mean_difference=mean,
                std_sample=sd,
                ci_low=low,
                ci_high=high,
                df=len(means) - 1 if means else None,
                inference_status=status,
                pairing_basis=PAIRING_BASIS,
                shared_stream_status=status_pair[0],
                channel_alignment=status_pair[1],
                pair_ids=tuple(
                    sorted(pair for pairs in block_pairs.values() for pair in pairs)
                ),
                unmatched_cells=unmatched,
                excluded_pairs=excluded_pairs,
                seed_blocks=tuple(
                    CulturalSeedBlock(
                        seed=seed,
                        value=statistics.fmean(values),
                        cell_ids=tuple(sorted(block_pairs.get(seed, ()))),
                    )
                    for seed, values in sorted(block_values.items())
                ),
            )
        )
    return tuple(summaries)


def build_cultural_metric_comparison(
    cells: Sequence[CulturalComparisonCell],
    *,
    matrix_fingerprint: str,
    comparisons: Sequence[CulturalComparisonRequest] = (),
    confidence: float = 0.95,
) -> CulturalMetricComparison:
    """Build condition summaries and explicit paired seed-block contrasts."""
    if type(confidence) is not float or not math.isfinite(confidence):
        raise CulturalComparisonError("invalid_confidence")
    if not 0.0 < confidence < 1.0:
        raise CulturalComparisonError("invalid_confidence")
    if type(comparisons) is not tuple and not isinstance(comparisons, Sequence):
        raise CulturalComparisonError("comparison_incompatible")
    matrix_fp = require_stable_id("matrix_fingerprint", matrix_fingerprint)
    seen: set[str] = set()
    normalized: list[CulturalComparisonCell] = []
    for cell in cells:
        if type(cell) is not CulturalComparisonCell:
            raise CulturalComparisonError("comparison_incompatible")
        if cell.cell_id in seen:
            raise CulturalComparisonError("duplicate_comparison_cell")
        seen.add(cell.cell_id)
        normalized.append(cell)
    conditions = _condition_comparisons(tuple(normalized), confidence)
    contrasts = _contrast_summaries(
        tuple(normalized),
        tuple(comparisons),
        confidence,
    )
    return CulturalMetricComparison(
        schema_version=CULTURAL_METRIC_COMPARISON_SCHEMA_VERSION,
        matrix_fingerprint=matrix_fp,
        confidence=confidence,
        method=STUDENT_T_METHOD,
        conditions=conditions,
        contrasts=contrasts,
    )


def _condition_payload(condition: CulturalConditionComparison) -> dict[str, object]:
    return {
        "condition_id": condition.condition_id,
        "raw_cell_count": condition.raw_cell_count,
        "seed_block_count": condition.seed_block_count,
        "duplicate_seed_cell_count": condition.duplicate_seed_cell_count,
        "excluded_cells": list(condition.excluded_cells),
        "measurements": [
            _measurement_comparison_payload(item) for item in condition.measurements
        ],
    }


def _measurement_comparison_payload(
    item: CulturalMeasurementComparison,
) -> dict[str, object]:
    return {
        "measurement": _quantized(item.measurement),
        "method": item.method,
        "confidence": quantize_float(item.confidence),
        "assumptions": list(item.assumptions),
        "n": item.n,
        "raw_cell_count": item.raw_cell_count,
        "duplicate_cell_count": item.duplicate_cell_count,
        "mean": None if item.mean is None else quantize_float(item.mean),
        "std_sample": None
        if item.std_sample is None
        else quantize_float(item.std_sample),
        "ci_low": None if item.ci_low is None else quantize_float(item.ci_low),
        "ci_high": None if item.ci_high is None else quantize_float(item.ci_high),
        "df": item.df,
        "inference_status": item.inference_status,
        "seed_blocks": [
            {
                "seed": block.seed,
                "value": quantize_float(block.value),
                "cell_ids": list(block.cell_ids),
            }
            for block in item.seed_blocks
        ],
        "excluded_cells": list(item.excluded_cells),
    }


def _contrast_payload(item: CulturalContrastSummary) -> dict[str, object]:
    return {
        "contrast_id": item.contrast_id,
        "control_condition_id": item.control_condition_id,
        "treatment_condition_id": item.treatment_condition_id,
        "measurement": _quantized(item.measurement),
        "method": item.method,
        "confidence": quantize_float(item.confidence),
        "assumptions": list(item.assumptions),
        "n": item.n,
        "mean_difference": (
            None
            if item.mean_difference is None
            else quantize_float(item.mean_difference)
        ),
        "std_sample": None
        if item.std_sample is None
        else quantize_float(item.std_sample),
        "ci_low": None if item.ci_low is None else quantize_float(item.ci_low),
        "ci_high": None if item.ci_high is None else quantize_float(item.ci_high),
        "df": item.df,
        "inference_status": item.inference_status,
        "pairing_basis": item.pairing_basis,
        "shared_stream_status": item.shared_stream_status,
        "channel_alignment": [
            [channel, status] for channel, status in item.channel_alignment
        ],
        "pair_ids": list(item.pair_ids),
        "unmatched_cells": list(item.unmatched_cells),
        "excluded_pairs": item.excluded_pairs,
        "seed_blocks": [
            {
                "seed": block.seed,
                "value": quantize_float(block.value),
                "cell_ids": list(block.cell_ids),
            }
            for block in item.seed_blocks
        ],
    }
