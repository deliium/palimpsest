"""Three descriptive scientific-institution metric families. Counts only."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.scientific_institutions_contract import (
    PracticeStatus,
    ScientificInstitutionContextEvidence,
)
from analysis.scientific_institutions_detection import (
    PracticeWindowState,
    ScientificPracticeAssessment,
)
from analysis.scientific_institutions_lineage import (
    PracticeLineageKind,
    ScientificPracticeLineage,
)
from analysis.specifications import MetricFamilyId, metric_specification

__all__ = [
    "ScientificInstitutionsMetricInputs",
    "compute_scientific_institution_lineage",
    "compute_scientific_institution_practice",
    "compute_scientific_institution_roles_and_carriers",
]

_ABSENT: Final[MetricCoverage] = MetricCoverage(observed=0, expected=0, ratio=None)


@dataclass(frozen=True, slots=True)
class ScientificInstitutionsMetricInputs:
    """Explicit detached inputs; absent input emits no family."""

    assessment: ScientificPracticeAssessment
    lineage: ScientificPracticeLineage
    context: ScientificInstitutionContextEvidence


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _document(
    family: MetricFamilyId,
    *,
    run_id: str,
    input_revision: str,
    observed: int,
    expected: int,
    values: Mapping[str, object],
    notes_code: str,
) -> MetricDocument:
    spec = metric_specification(family)
    availability = (
        MetricAvailability.PRESENT
        if observed > 0 and expected > 0
        else MetricAvailability.PARTIAL
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
        coverage=(
            MetricCoverage(
                observed=observed,
                expected=expected,
                ratio=_ratio(observed, expected),
            )
            if expected
            else _ABSENT
        ),
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="scientific_institutions_analysis",
            source_ids=(
                run_id,
                input_revision,
                "scientific-institutions.v1",
                "scientific-institutions",
                notes_code,
            ),
        ),
    )


def _require_inputs(value: object) -> ScientificInstitutionsMetricInputs:
    if type(value) is not ScientificInstitutionsMetricInputs:
        raise ValueError("scientific_institutions_analysis_invalid_type")
    return value


def compute_scientific_institution_practice(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require_inputs(analysis)
    assessment = data.assessment
    statuses = [row.status for row in assessment.rows]
    states = [window.state for window in assessment.windows]
    complete_windows = sum(
        1
        for window in assessment.windows
        if window.state
        in {PracticeWindowState.COMPLETE, PracticeWindowState.COMPLETE_EMPTY}
    )
    observed = sum(
        1
        for window in assessment.windows
        if window.execution_coverage.value == "complete"
    )
    return _document(
        MetricFamilyId.SCIENTIFIC_INSTITUTION_PRACTICE,
        run_id=run_id,
        input_revision=input_revision,
        observed=observed,
        expected=len(assessment.windows),
        values={
            "complete_window_count": complete_windows,
            "complete_empty_window_count": states.count(
                PracticeWindowState.COMPLETE_EMPTY
            ),
            "partial_window_count": states.count(PracticeWindowState.PARTIAL),
            "unavailable_window_count": states.count(
                PracticeWindowState.UNAVAILABLE
            ),
            "supported_row_count": statuses.count(PracticeStatus.SUPPORTED),
            "stable_row_count": statuses.count(PracticeStatus.STABLE),
            "observed_only_row_count": statuses.count(
                PracticeStatus.OBSERVED_ONLY
            ),
            "not_observed_row_count": statuses.count(
                PracticeStatus.NOT_OBSERVED
            ),
            "unavailable_row_count": statuses.count(
                PracticeStatus.UNAVAILABLE
            ),
            "eligible_row_count": len(assessment.rows),
            "unassigned_count": assessment.unassigned,
            "ambiguous_count": assessment.ambiguous,
        },
        notes_code="practice",
    )


def compute_scientific_institution_roles_and_carriers(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require_inputs(analysis)
    signals = [
        row.signal.value
        for window in data.context.windows
        for row in window.supplements
    ]
    actors = {
        token
        for window in data.context.windows
        for row in window.supplements
        for token in row.actor_tokens
    }
    carriers = {
        pair
        for window in data.context.windows
        for row in window.supplements
        for pair in row.carrier_tokens
    }
    org_windows = sum(
        1 for window in data.context.windows if window.organizations
    )
    return _document(
        MetricFamilyId.SCIENTIFIC_INSTITUTION_ROLES_AND_CARRIERS,
        run_id=run_id,
        input_revision=input_revision,
        observed=org_windows,
        expected=len(data.context.windows),
        values={
            "experimenter_signal_count": signals.count("experimenter"),
            "record_keeper_signal_count": signals.count("record_keeper"),
            "teacher_signal_count": signals.count("teacher"),
            "replication_expectation_signal_count": signals.count(
                "replication_expectation"
            ),
            "archive_signal_count": signals.count("archive"),
            "shared_instrument_signal_count": signals.count(
                "shared_instrument"
            ),
            "procedure_signal_count": signals.count("procedure"),
            "institutional_memory_signal_count": signals.count(
                "institutional_memory"
            ),
            "office_signal_count": signals.count("office"),
            "distinct_linked_actor_count": len(actors),
            "distinct_carrier_count": len(carriers),
        },
        notes_code="roles_and_carriers",
    )


def compute_scientific_institution_lineage(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require_inputs(analysis)
    lineage = data.lineage
    kinds = [item.kind.value for item in lineage.transitions]
    lengths = [len(episode.windows) for episode in lineage.episodes]
    stable_windows = sum(
        1
        for row in data.assessment.rows
        if row.status is PracticeStatus.STABLE
    )
    complete_windows = sum(
        1
        for window in data.assessment.windows
        if window.state
        in {PracticeWindowState.COMPLETE, PracticeWindowState.COMPLETE_EMPTY}
    )
    return _document(
        MetricFamilyId.SCIENTIFIC_INSTITUTION_LINEAGE,
        run_id=run_id,
        input_revision=input_revision,
        observed=stable_windows,
        expected=complete_windows,
        values={
            "episode_count": len(lineage.episodes),
            "node_count": len(lineage.nodes),
            "continued_count": kinds.count(PracticeLineageKind.CONTINUED.value),
            "emerged_count": kinds.count(PracticeLineageKind.EMERGED.value),
            "handoff_count": kinds.count(PracticeLineageKind.HANDOFF.value),
            "split_count": kinds.count(PracticeLineageKind.SPLIT.value),
            "merged_count": kinds.count(PracticeLineageKind.MERGED.value),
            "split_merged_count": kinds.count(
                PracticeLineageKind.SPLIT_MERGED.value
            ),
            "lapsed_count": kinds.count(PracticeLineageKind.LAPSED.value),
            "continuity_unknown_count": kinds.count(
                PracticeLineageKind.CONTINUITY_UNKNOWN.value
            ),
            "reobserved_after_gap_count": kinds.count(
                PracticeLineageKind.REOBSERVED_AFTER_GAP.value
            ),
            "max_observed_length_windows": max(lengths, default=0),
            "mean_observed_length_milli": (
                0
                if not lengths
                else round(sum(lengths) * 1000 / len(lengths))
            ),
        },
        notes_code="lineage",
    )
