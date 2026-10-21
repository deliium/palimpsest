"""Scalar-plus-JSON metric assemblers for institutional decay research output."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Sequence
from typing import Final

from analysis.institution_lineage import (
    InstitutionLineageEdgeKind,
    InstitutionLineageResult,
    compute_institution_lineage,
)
from analysis.institutional_decay import (
    INSTITUTION_LIFECYCLE_POLICY_VERSION,
    InstitutionContextEvidenceRow,
    InstitutionLifecycleResult,
    InstitutionLifecycleState,
    InstitutionTemporalRow,
    InstitutionWindowRow,
    compute_institutional_decay,
)
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions
from analysis.specifications import MetricFamilyId, metric_specification

__all__ = [
    "INSTITUTION_DIMENSION_TRAJECTORIES_SCHEMA",
    "INSTITUTION_LIFECYCLE_EPISODES_SCHEMA",
    "INSTITUTION_LINEAGE_GRAPH_SCHEMA",
    "INSTITUTION_MECHANISM_EVIDENCE_SCHEMA",
    "compute_institution_lifecycle_metric",
    "compute_institution_lineage_metric",
    "compute_institutional_decay_metric",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.institutional_decay_metrics")

INSTITUTION_DIMENSION_TRAJECTORIES_SCHEMA: Final[str] = (
    "institution-dimension-trajectories-v1"
)
INSTITUTION_MECHANISM_EVIDENCE_SCHEMA: Final[str] = "institution-mechanism-evidence-v1"
INSTITUTION_LIFECYCLE_EPISODES_SCHEMA: Final[str] = "institution-lifecycle-episodes-v1"
INSTITUTION_LINEAGE_GRAPH_SCHEMA: Final[str] = "institution-lineage-graph-v1"


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _coverage(observed: int, expected: int) -> MetricCoverage | None:
    if expected == 0:
        return None
    return MetricCoverage(observed=observed, expected=expected)


def _doc(
    *,
    family: MetricFamilyId,
    run_id: str,
    input_revision: str,
    values: dict[str, object],
    availability: MetricAvailability,
    observed: int,
    expected: int,
) -> MetricDocument:
    spec = metric_specification(family)
    if set(values) != set(spec.value_keys):
        raise ValueError("institutional_decay_metric:value_keys")
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
        coverage=_coverage(observed, expected),
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind="institutional_decay_exports",
            source_ids=(),
            notes_code="ok"
            if availability is not MetricAvailability.ABSENT
            else "empty",
        ),
    )


def _dimension_payload(
    rows: Sequence[InstitutionTemporalRow],
    lifecycle: InstitutionLifecycleResult,
) -> str:
    windows = [
        {
            "owner": window.owner_id,
            "pattern": window.local_pattern_id,
            "start_tick": window.start_tick,
            "end_tick": window.end_tick,
            "complete": window.complete,
            "covered_updates": window.covered_updates,
            "cohort_size": len(window.cohort),
            "support": {
                "numerator": window.support_numerator,
                "denominator": len(window.cohort),
                "ratio": window.support_ratio,
                "availability": window.support_availability.value,
            },
            "participation": {
                "numerator": window.participation_numerator,
                "denominator": len(window.cohort),
                "ratio": window.participation_ratio,
                "availability": window.participation_availability.value,
            },
            "procedure": {
                "numerator": window.procedure_numerator,
                "denominator": 4,
                "ratio": window.procedure_ratio,
                "availability": window.procedure_availability.value,
            },
            "succession": {
                "numerator": window.succession_completed,
                "denominator": window.succession_eligible,
                "ratio": window.succession_ratio,
                "availability": window.succession_availability.value,
            },
            "knowledge": {
                "numerator": window.knowledge_retained,
                "denominator": window.knowledge_before,
                "ratio": window.knowledge_ratio,
                "availability": window.knowledge_availability.value,
            },
            "legitimacy_strength": window.legitimacy_strength,
            "pruned": window.pruned,
        }
        for window in lifecycle.windows
    ]
    return _canonical(
        {
            "schema_version": INSTITUTION_DIMENSION_TRAJECTORIES_SCHEMA,
            "as_of_tick": lifecycle.as_of_tick,
            "policy_version": INSTITUTION_LIFECYCLE_POLICY_VERSION,
            "input_revision": f"rows:{len(rows)}",
            "windows": windows,
        }
    )


def _mechanism_payload(lifecycle: InstitutionLifecycleResult) -> str:
    tags = [
        {
            "pattern": pattern,
            "kind": kind,
            "native_ref": native_ref,
        }
        for pattern, kind, native_ref in lifecycle.mechanism_tags
    ]
    return _canonical(
        {
            "schema_version": INSTITUTION_MECHANISM_EVIDENCE_SCHEMA,
            "as_of_tick": lifecycle.as_of_tick,
            "associations": tags,
            "excluded_rows": lifecycle.excluded_rows,
            "pruned_rows": lifecycle.pruned_rows,
        }
    )


def _latest_window(
    lifecycle: InstitutionLifecycleResult,
) -> InstitutionWindowRow | None:
    complete = [window for window in lifecycle.windows if window.complete]
    return complete[-1] if complete else None


def compute_institutional_decay_metric(
    rows: object,
    *,
    run_id: str,
    input_revision: str,
    as_of_tick: int,
    context_rows: Iterable[InstitutionContextEvidenceRow] = (),
) -> MetricDocument:
    checked: tuple[InstitutionTemporalRow, ...] = tuple(rows)  # type: ignore[arg-type]
    lifecycle = compute_institutional_decay(
        checked, as_of_tick=as_of_tick, context_rows=context_rows
    )
    latest = _latest_window(lifecycle)
    values: dict[str, object] = {
        "window_count": len(lifecycle.windows),
        "support_ratio": None,
        "participation_ratio": None,
        "procedure_ratio": None,
        "succession_ratio": None,
        "knowledge_ratio": None,
        "as_of_tick": as_of_tick,
        "input_revision": input_revision,
        "dimension_trajectories_json": _dimension_payload(checked, lifecycle),
        "mechanism_evidence_json": _mechanism_payload(lifecycle),
    }
    if latest is not None:
        values.update(
            {
                "support_ratio": latest.support_ratio,
                "participation_ratio": latest.participation_ratio,
                "procedure_ratio": latest.procedure_ratio,
                "succession_ratio": latest.succession_ratio,
                "knowledge_ratio": latest.knowledge_ratio,
            }
        )
    if not checked:
        availability = MetricAvailability.ABSENT
    elif any(row.pruned for row in checked) or any(
        not window.complete for window in lifecycle.windows
    ):
        availability = MetricAvailability.PARTIAL
    else:
        availability = MetricAvailability.PRESENT
    return _doc(
        family=MetricFamilyId.INSTITUTIONAL_DECAY,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        availability=availability,
        observed=len(lifecycle.windows),
        expected=max(len(lifecycle.windows), 1),
    )


def _episodes_payload(lifecycle: InstitutionLifecycleResult) -> str:
    return _canonical(
        {
            "schema_version": INSTITUTION_LIFECYCLE_EPISODES_SCHEMA,
            "as_of_tick": lifecycle.as_of_tick,
            "policy_version": lifecycle.policy_version,
            "thresholds": {
                "strong": 0.50,
                "low": 0.10,
                "renewal": 0.30,
                "weakening_delta": 0.10,
            },
            "states": [
                {"owner": key[0], "pattern": key[1], "state": state}
                for key, state in lifecycle.states
            ],
        }
    )


def compute_institution_lifecycle_metric(
    rows: object,
    *,
    run_id: str,
    input_revision: str,
    as_of_tick: int,
    context_rows: Iterable[InstitutionContextEvidenceRow] = (),
) -> MetricDocument:
    checked: tuple[InstitutionTemporalRow, ...] = tuple(rows)  # type: ignore[arg-type]
    lifecycle = compute_institutional_decay(
        checked, as_of_tick=as_of_tick, context_rows=context_rows
    )
    counts = {state.value: 0 for state in InstitutionLifecycleState}
    for _key, state in lifecycle.states:
        counts[state] += 1
    values: dict[str, object] = {
        "episode_count": len(lifecycle.states),
        "emerging_count": counts["emerging"],
        "stable_count": counts["stable"],
        "weakening_count": counts["weakening"],
        "collapsed_count": counts["collapsed"],
        "right_censored_count": counts["right_censored"] + counts["unknown"],
        "as_of_tick": as_of_tick,
        "input_revision": input_revision,
        "episodes_json": _episodes_payload(lifecycle),
    }
    if not checked:
        availability = MetricAvailability.ABSENT
    elif any(not window.complete for window in lifecycle.windows):
        availability = MetricAvailability.PARTIAL
    else:
        availability = MetricAvailability.PRESENT
    return _doc(
        family=MetricFamilyId.INSTITUTION_LIFECYCLE,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        availability=availability,
        observed=len(lifecycle.states),
        expected=max(len(lifecycle.states), 1),
    )


def _lineage_payload(lineage: InstitutionLineageResult) -> str:
    return _canonical(
        {
            "schema_version": INSTITUTION_LINEAGE_GRAPH_SCHEMA,
            "as_of_tick": lineage.as_of_tick,
            "policy_version": lineage.policy_version,
            "episodes": [
                {
                    "episode_id": episode.episode_id,
                    "owner": episode.owner_id,
                    "pattern": episode.local_pattern_id,
                    "first_tick": episode.first_tick,
                    "last_tick": episode.last_tick,
                    "components": list(episode.components),
                    "state": episode.state,
                    "pruned": episode.pruned,
                }
                for episode in lineage.episodes
            ],
            "stubs": [
                {
                    "episode_id": stub.episode_id,
                    "reason": stub.reason,
                }
                for stub in lineage.stubs
            ],
            "edges": [
                {
                    "kind": edge.kind.value,
                    "parent_id": edge.parent_id,
                    "child_id": edge.child_id,
                    "parent_tick": edge.parent_tick,
                    "child_tick": edge.child_tick,
                    "confidence": edge.confidence.value,
                    "shared_components": edge.shared_components,
                    "jaccard": edge.jaccard,
                }
                for edge in lineage.edges
            ],
            "ambiguous": [
                {"child": child, "candidate_parent": parent}
                for child, parent in lineage.ambiguous
            ],
        }
    )


def compute_institution_lineage_metric(
    rows: object,
    *,
    run_id: str,
    input_revision: str,
    as_of_tick: int,
    lifecycle: InstitutionLifecycleResult | None = None,
) -> MetricDocument:
    checked: tuple[InstitutionTemporalRow, ...] = tuple(rows)  # type: ignore[arg-type]
    lineage = compute_institution_lineage(
        checked,
        as_of_tick=as_of_tick,
        lifecycle=lifecycle,
    )
    counts = {
        kind: sum(1 for edge in lineage.edges if edge.kind is kind)
        for kind in InstitutionLineageEdgeKind
    }
    values: dict[str, object] = {
        "episode_count": len(lineage.episodes),
        "stub_count": len(lineage.stubs),
        "transformed_count": counts[InstitutionLineageEdgeKind.TRANSFORMED],
        "split_count": counts[InstitutionLineageEdgeKind.SPLIT],
        "reappeared_count": counts[InstitutionLineageEdgeKind.REAPPEARED],
        "continued_count": counts[InstitutionLineageEdgeKind.CONTINUED],
        "ambiguous_count": len(lineage.ambiguous),
        "as_of_tick": as_of_tick,
        "input_revision": input_revision,
        "lineage_graph_json": _lineage_payload(lineage),
    }
    if not checked:
        availability = MetricAvailability.ABSENT
    elif any(episode.pruned for episode in lineage.episodes) or lineage.ambiguous:
        availability = MetricAvailability.PARTIAL
    else:
        availability = MetricAvailability.PRESENT
    return _doc(
        family=MetricFamilyId.INSTITUTION_LINEAGE,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        availability=availability,
        observed=len(lineage.episodes),
        expected=max(len(lineage.episodes), 1),
    )
