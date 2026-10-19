"""Detached persistence metrics for analytical institution candidates.

Temporary coordination is a first-class reported result. Classification
thresholds live in this analysis module (and the metric specification), never
in world rules. No institution type is created or inferred.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.institution_emergence import (
    InstitutionAnalysisError,
    InstitutionCandidateRow,
    InstitutionEmergenceResult,
    InstitutionLane,
)
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.institutional_persistence")

_PERSISTENCE_SPAN: Final[int] = 4
_PERSISTENCE_GENERATION_SPAN: Final[int] = 1
_MAX_CURVE_POINTS: Final[int] = 64


class InstitutionPersistenceClassification(StrEnum):
    """Closed reported classification. Never an institution type."""

    TEMPORARY_COORDINATION = "temporary_coordination"
    PERSISTENT_INSTITUTION_LIKE = "persistent_institution_like"


@dataclass(frozen=True, slots=True)
class InstitutionPersistenceRow:
    """One candidate's reported temporal persistence."""

    candidate_id: str
    lifetime_ticks: int
    generation_span: int
    succession_continues: bool
    classification: InstitutionPersistenceClassification
    lane_coverage_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or len(self.candidate_id) != 64:
            raise InstitutionAnalysisError("invalid_candidate_id")
        for name in ("lifetime_ticks", "generation_span", "lane_coverage_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise InstitutionAnalysisError(f"invalid_int:{name}")
        if type(self.succession_continues) is not bool:
            raise InstitutionAnalysisError("invalid_succession")
        if type(self.classification) is not InstitutionPersistenceClassification:
            raise InstitutionAnalysisError("invalid_classification")


@dataclass(frozen=True, slots=True)
class InstitutionalPersistenceResult:
    """Reported survival, continuity, and classification rows."""

    rows: tuple[InstitutionPersistenceRow, ...]
    survival_curve: tuple[tuple[int, str], ...]
    coverage: MetricCoverage

    def __post_init__(self) -> None:
        for row in self.rows:
            if type(row) is not InstitutionPersistenceRow:
                raise InstitutionAnalysisError("invalid_persistence_row")
        for item in self.survival_curve:
            if not isinstance(item, tuple) or len(item) != 2:
                raise InstitutionAnalysisError("invalid_survival_curve")
            tick, share = item
            if isinstance(tick, bool) or type(tick) is not int or tick < 0:
                raise InstitutionAnalysisError("invalid_curve_tick")
            float(share)
        if type(self.coverage) is not MetricCoverage:
            raise InstitutionAnalysisError("invalid_coverage")


def _candidate_succession(row: InstitutionCandidateRow) -> bool:
    return any(
        lane_row.lane is InstitutionLane.SUCCESSION
        and lane_row.tick_end > lane_row.tick_start
        for lane_row in row.lane_rows
    )


def _classify(row: InstitutionCandidateRow) -> InstitutionPersistenceClassification:
    lifetime = row.tick_end - row.tick_start
    multi_generation = (
        InstitutionLane.CONTINUITY.value in row.lane_coverage
        and row.generation_span >= _PERSISTENCE_GENERATION_SPAN
    )
    persistent = lifetime >= _PERSISTENCE_SPAN and (
        multi_generation or _candidate_succession(row)
    )
    return (
        InstitutionPersistenceClassification.PERSISTENT_INSTITUTION_LIKE
        if persistent
        else InstitutionPersistenceClassification.TEMPORARY_COORDINATION
    )


def _survival_curve(
    candidates: Sequence[InstitutionCandidateRow],
) -> tuple[tuple[int, str], ...]:
    if not candidates:
        return ()
    spans = {
        candidate.candidate_id: (
            candidate.tick_start,
            candidate.tick_end,
        )
        for candidate in candidates
    }
    ticks = sorted({tick for span in spans.values() for tick in span})
    if len(ticks) > _MAX_CURVE_POINTS:
        stride = max(1, len(ticks) // _MAX_CURVE_POINTS)
        ticks = ticks[::stride]
    curve: list[tuple[int, str]] = []
    total = len(candidates)
    for tick in ticks:
        alive = sum(1 for start, end in spans.values() if start <= tick <= end)
        curve.append((tick, str(quantize_float(require_finite(alive / total)))))
    return tuple(curve)


def compute_institutional_persistence(
    result: InstitutionEmergenceResult,
) -> InstitutionalPersistenceResult:
    """Compute deterministic persistence rows over candidates and bundles."""
    if type(result) is not InstitutionEmergenceResult:
        raise InstitutionAnalysisError("invalid_result")
    all_rows = (*result.candidates, *result.sub_threshold)
    persistence_rows: list[InstitutionPersistenceRow] = []
    for candidate in sorted(all_rows, key=lambda row: row.candidate_id):
        persistence_rows.append(
            InstitutionPersistenceRow(
                candidate_id=candidate.candidate_id,
                lifetime_ticks=candidate.tick_end - candidate.tick_start,
                generation_span=candidate.generation_span,
                succession_continues=_candidate_succession(candidate),
                classification=_classify(candidate),
                lane_coverage_count=len(candidate.lane_coverage),
            )
        )
    _LOG.debug(
        "institutional_persistence_computed candidate_count=%s "
        "persistent_count=%s temporary_count=%s",
        len(persistence_rows),
        sum(
            1
            for row in persistence_rows
            if row.classification
            is InstitutionPersistenceClassification.PERSISTENT_INSTITUTION_LIKE
        ),
        sum(
            1
            for row in persistence_rows
            if row.classification
            is InstitutionPersistenceClassification.TEMPORARY_COORDINATION
        ),
    )
    return InstitutionalPersistenceResult(
        rows=tuple(persistence_rows),
        survival_curve=_survival_curve(all_rows),
        coverage=result.coverage,
    )


def compute_institutional_persistence_metric(
    result: InstitutionalPersistenceResult,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Pin one institutional-persistence document for a run revision."""
    if type(result) is not InstitutionalPersistenceResult:
        raise InstitutionAnalysisError("invalid_result")
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.INSTITUTIONAL_PERSISTENCE)
    persistent = sum(
        1
        for row in result.rows
        if row.classification
        is InstitutionPersistenceClassification.PERSISTENT_INSTITUTION_LIKE
    )
    temporary = sum(
        1
        for row in result.rows
        if row.classification
        is InstitutionPersistenceClassification.TEMPORARY_COORDINATION
    )
    succession_total = len(result.rows)
    succession_continues = sum(1 for row in result.rows if row.succession_continues)
    generation_total = len(result.rows)
    generation_multi = sum(1 for row in result.rows if row.generation_span > 0)
    lifetime = [row.lifetime_ticks for row in result.rows]
    if not result.rows:
        availability = MetricAvailability.ABSENT
    elif persistent == 0:
        availability = MetricAvailability.PARTIAL
    else:
        availability = MetricAvailability.PRESENT
    mean_lifetime = (
        quantize_float(require_finite(sum(lifetime) / len(lifetime)))
        if lifetime
        else 0.0
    )
    succession_ratio = (
        quantize_float(require_finite(succession_continues / succession_total))
        if succession_total
        else 0.0
    )
    generation_ratio = (
        quantize_float(require_finite(generation_multi / generation_total))
        if generation_total
        else 0.0
    )
    _LOG.info(
        "institutional_persistence_document persistent_count=%s temporary_count=%s",
        persistent,
        temporary,
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
        values={
            "candidate_count": len(result.rows),
            "persistent_institution_like_count": persistent,
            "temporary_coordination_count": temporary,
            "survival_curve": ";".join(
                f"{tick}:{share}" for tick, share in result.survival_curve
            ),
            "mean_lifetime_ticks": mean_lifetime,
            "succession_survival_ratio": succession_ratio,
            "cross_generational_ratio": generation_ratio,
        },
        provenance=MetricProvenance(
            source_kind="institutional_persistence",
            source_ids=(),
            notes_code="ok"
            if availability is not MetricAvailability.ABSENT
            else "empty",
        ),
    )
