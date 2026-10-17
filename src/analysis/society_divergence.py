"""Cross-candidate-community divergence over detached digest distributions.

Divergence is symmetric and pair-scoped. Missing channels stay absent; they are
never coerced to zero. All tokens are opaque digests/labels, never content.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import (
    jensen_shannon_divergence,
    library_versions,
    quantize_float,
    require_finite,
)
from analysis.society_emergence import CandidateCommunityRow
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "SOCIETY_DIMENSIONS",
    "SOCIETY_DIVERGENCE_METRIC_VERSION",
    "SocietyDigestRow",
    "SocietyDivergenceError",
    "SocietyDivergenceResult",
    "SocietyDivergenceRow",
    "compute_society_divergence",
    "compute_society_divergence_metric",
]

SOCIETY_DIVERGENCE_METRIC_VERSION: Final[str] = "society_divergence@1"
SOCIETY_DIMENSIONS: Final[tuple[str, ...]] = (
    "vocabulary",
    "norms",
    "conventions",
    "technology",
    "stories",
    "institutions",
    "trade",
)
_GLOBAL_BASELINE: Final[str] = "global-baseline"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.society_divergence")


class SocietyDivergenceError(ValueError):
    """Fail-closed divergence error with a stable reason code only."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class SocietyDigestRow:
    """One detached digest/label observation for a person and dimension."""

    dimension: str
    person_id: str
    token: str

    def __post_init__(self) -> None:
        dimension = require_stable_id("dimension", self.dimension)
        if dimension not in SOCIETY_DIMENSIONS:
            raise SocietyDivergenceError("unknown_dimension")
        object.__setattr__(self, "dimension", dimension)
        object.__setattr__(
            self, "person_id", require_stable_id("person_id", self.person_id)
        )
        object.__setattr__(self, "token", require_stable_id("token", self.token))


@dataclass(frozen=True, slots=True)
class SocietyDivergenceRow:
    """One symmetric pair/dimension divergence value with coverage counts."""

    community_a: str
    community_b: str
    dimension: str
    divergence: float | None
    observed_a: int
    observed_b: int
    reason_code: str

    def __post_init__(self) -> None:
        for name in ("community_a", "community_b", "dimension", "reason_code"):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        if self.dimension not in SOCIETY_DIMENSIONS:
            raise SocietyDivergenceError("unknown_dimension")
        if self.divergence is not None:
            object.__setattr__(
                self,
                "divergence",
                quantize_float(require_finite(float(self.divergence))),
            )
        object.__setattr__(
            self, "observed_a", require_exact_nonneg_int("observed_a", self.observed_a)
        )
        object.__setattr__(
            self, "observed_b", require_exact_nonneg_int("observed_b", self.observed_b)
        )


@dataclass(frozen=True, slots=True)
class SocietyDivergenceResult:
    """Pair-scoped divergence rows plus explicit coverage."""

    rows: tuple[SocietyDivergenceRow, ...]
    coverage: MetricCoverage
    dimensions_present: tuple[str, ...]
    dimensions_absent: tuple[str, ...]

    def __post_init__(self) -> None:
        rows = tuple(
            sorted(
                self.rows,
                key=lambda row: (row.dimension, row.community_a, row.community_b),
            )
        )
        object.__setattr__(self, "rows", rows)
        if type(self.coverage) is not MetricCoverage:
            raise SocietyDivergenceError("invalid_coverage")
        object.__setattr__(
            self, "dimensions_present", tuple(sorted(self.dimensions_present))
        )
        object.__setattr__(
            self, "dimensions_absent", tuple(sorted(self.dimensions_absent))
        )


def _distribution(
    counts: Mapping[str, int], universe: Sequence[str]
) -> tuple[float, ...]:
    return tuple(float(counts.get(token, 0)) for token in universe)


def compute_society_divergence(
    communities: Sequence[CandidateCommunityRow],
    dimension_rows: Sequence[SocietyDigestRow],
) -> SocietyDivergenceResult:
    """Compute quantized JS divergence for every community pair and baseline."""
    if isinstance(communities, (str, bytes)) or not isinstance(communities, Sequence):
        raise SocietyDivergenceError("invalid_communities")
    community_rows = tuple(communities)
    if any(type(item) is not CandidateCommunityRow for item in community_rows):
        raise SocietyDivergenceError("invalid_communities")
    ordered = tuple(sorted(community_rows, key=lambda item: item.community_id))
    owner_of: dict[str, str] = {}
    for community in ordered:
        for person in community.person_ids:
            if person in owner_of:
                raise SocietyDivergenceError("duplicate_person_across_communities")
            owner_of[person] = community.community_id

    rows_by_key: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    universe_by_dimension: dict[str, set[str]] = defaultdict(set)
    observed_by_key: Counter[tuple[str, str]] = Counter()
    for row in dimension_rows:
        if type(row) is not SocietyDigestRow:
            raise SocietyDivergenceError("invalid_dimension_row")
        community_id = owner_of.get(row.person_id)
        universe_by_dimension[row.dimension].add(row.token)
        if community_id is None:
            continue
        rows_by_key[(row.dimension, community_id)][row.token] += 1
        observed_by_key[(row.dimension, community_id)] += 1

    global_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for (dimension, _community_id), counts in rows_by_key.items():
        global_counts[dimension].update(counts)

    pairs: list[tuple[str, str]] = []
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            pairs.append((left.community_id, right.community_id))
    baseline_pairs = [
        (community.community_id, _GLOBAL_BASELINE) for community in ordered
    ]

    result_rows: list[SocietyDivergenceRow] = []
    present: set[str] = set()
    absent: set[str] = set()
    evaluable = 0
    expected = 0
    for dimension in SOCIETY_DIMENSIONS:
        universe = tuple(sorted(universe_by_dimension.get(dimension, set())))
        dimension_has_value = False
        for community_a, community_b in (*pairs, *baseline_pairs):
            expected += 1
            if community_b == _GLOBAL_BASELINE:
                counts_a = rows_by_key.get((dimension, community_a), Counter())
                counts_b = global_counts.get(dimension, Counter())
                observed_a = observed_by_key.get((dimension, community_a), 0)
                observed_b = sum(counts_b.values())
            else:
                counts_a = rows_by_key.get((dimension, community_a), Counter())
                counts_b = rows_by_key.get((dimension, community_b), Counter())
                observed_a = observed_by_key.get((dimension, community_a), 0)
                observed_b = observed_by_key.get((dimension, community_b), 0)
            if not universe or not counts_a or not counts_b:
                result_rows.append(
                    SocietyDivergenceRow(
                        community_a=community_a,
                        community_b=community_b,
                        dimension=dimension,
                        divergence=None,
                        observed_a=observed_a,
                        observed_b=observed_b,
                        reason_code="absent_channel",
                    )
                )
                continue
            divergence = jensen_shannon_divergence(
                _distribution(counts_a, universe),
                _distribution(counts_b, universe),
            )
            if divergence is None:
                result_rows.append(
                    SocietyDivergenceRow(
                        community_a=community_a,
                        community_b=community_b,
                        dimension=dimension,
                        divergence=None,
                        observed_a=observed_a,
                        observed_b=observed_b,
                        reason_code="empty_distribution",
                    )
                )
                continue
            evaluable += 1
            dimension_has_value = True
            result_rows.append(
                SocietyDivergenceRow(
                    community_a=community_a,
                    community_b=community_b,
                    dimension=dimension,
                    divergence=divergence,
                    observed_a=observed_a,
                    observed_b=observed_b,
                    reason_code="ok",
                )
            )
        if dimension_has_value:
            present.add(dimension)
        else:
            absent.add(dimension)

    ratio = None
    if expected:
        ratio = quantize_float(require_finite(float(evaluable) / float(expected)))
    _LOG.debug(
        "society_divergence_computed community_count=%s pair_count=%s "
        "dimension_count=%s evaluable=%s expected=%s",
        len(ordered),
        len(pairs) + len(baseline_pairs),
        len(SOCIETY_DIMENSIONS),
        evaluable,
        expected,
    )
    return SocietyDivergenceResult(
        rows=tuple(result_rows),
        coverage=MetricCoverage(observed=evaluable, expected=expected, ratio=ratio),
        dimensions_present=tuple(present),
        dimensions_absent=tuple(absent),
    )


def compute_society_divergence_metric(
    result: SocietyDivergenceResult,
    *,
    run_id: str,
    input_revision: str,
    community_count: int,
) -> MetricDocument:
    """Pin one society-divergence document with per-dimension summaries."""
    if type(result) is not SocietyDivergenceResult:
        raise SocietyDivergenceError("invalid_divergence_result")
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    community_count = require_exact_nonneg_int("community_count", community_count)
    spec = metric_specification(MetricFamilyId.SOCIETY_DIVERGENCE)

    values: dict[str, object] = {
        "community_count": community_count,
        "evaluable_pair_dimension_count": result.coverage.observed,
        "pair_dimension_count": result.coverage.expected,
        "dimension_count": len(SOCIETY_DIMENSIONS),
    }
    for dimension in SOCIETY_DIMENSIONS:
        divergences = [
            row.divergence
            for row in result.rows
            if row.dimension == dimension and row.divergence is not None
        ]
        values[f"{dimension}_pair_count"] = len(divergences)
        values[f"{dimension}_availability"] = "present" if divergences else "absent"
        values[f"{dimension}_mean_divergence"] = (
            quantize_float(require_finite(sum(divergences) / len(divergences)))
            if divergences
            else None
        )
    if community_count < 2 or not result.rows:
        availability = MetricAvailability.ABSENT
    elif not result.dimensions_present:
        availability = MetricAvailability.UNKNOWN
    elif result.dimensions_absent:
        availability = MetricAvailability.PARTIAL
    else:
        availability = MetricAvailability.PRESENT
    _LOG.debug(
        "society_divergence_document family_id=%s availability=%s "
        "pair_count=%s dimension_count=%s",
        spec.family_id.value,
        availability.value,
        result.coverage.expected,
        len(result.dimensions_present),
    )
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=result.coverage,
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind="society_divergence",
            source_ids=(),
            notes_code="ok"
            if availability is not MetricAvailability.ABSENT
            else "empty",
        ),
    )
