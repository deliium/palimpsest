"""Sibling metric families for analysis-only technique lifecycle."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import (
    MetricFamilyId,
    MetricSpecification,
    metric_specification,
)
from analysis.technique_lifecycle import (
    TechniqueLifecycleSnapshot,
    TechniqueLifecycleState,
    TechniqueLossCause,
    classify_technique_lifecycle,
)
from simulation.runner_models import TechniqueLifecycleSpec
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.technique_lifecycle_metrics")
_LAYER: Final[str] = "research_inference"

TECHNIQUE_LIFECYCLE_STATE_METRIC_VERSION: Final[str] = "technique_lifecycle_state@1"
TECHNIQUE_LIFECYCLE_LOSS_METRIC_VERSION: Final[str] = "technique_lifecycle_loss@1"
TECHNIQUE_LIFECYCLE_DIFFUSION_METRIC_VERSION: Final[str] = (
    "technique_lifecycle_diffusion@1"
)


class TechniqueLifecycleMetricError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        _LOG.error("technique_lifecycle_metric_invalid reason_code=%s", reason_code)
        super().__init__(reason_code)


def _document(
    spec: MetricSpecification,
    run_id: str,
    revision: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    *,
    notes_code: str,
    observed: int = 0,
) -> MetricDocument:
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=max(observed, 1))
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="technique_lifecycle",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )


def _absent(spec: MetricSpecification, run_id: str, revision: str) -> MetricDocument:
    return _document(
        spec,
        run_id,
        revision,
        MetricAvailability.ABSENT,
        {"layer": _LAYER},
        notes_code="no_technique_lifecycle",
    )


def assemble_technique_lifecycle_metrics(
    audits: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
    spec: TechniqueLifecycleSpec,
    as_of_tick: int = 0,
    death_ticks: Mapping[str, int] | None = None,
    artifact_rows: Sequence[object] = (),
    applied_actions: Sequence[object] = (),
    mentorship_audits: Sequence[object] = (),
    catalog: object | None = None,
    node_rows: Sequence[object] = (),
    item_rows: Sequence[object] = (),
) -> tuple[MetricDocument, MetricDocument, MetricDocument]:
    """Three sibling families. Caller omits the call when the spec is absent."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = classify_technique_lifecycle(
        audits,
        as_of_tick=as_of_tick,
        spec=spec,
        death_ticks=death_ticks,
        artifact_rows=artifact_rows,
        applied_actions=applied_actions,  # type: ignore[arg-type]
        mentorship_audits=mentorship_audits,
        catalog=catalog,
        node_rows=node_rows,
        item_rows=item_rows,
    )
    documents = (
        compute_technique_lifecycle_state(
            rows, run_id=document_run, input_revision=revision
        ),
        compute_technique_lifecycle_loss(
            rows, run_id=document_run, input_revision=revision
        ),
        compute_technique_lifecycle_diffusion(
            rows, run_id=document_run, input_revision=revision
        ),
    )
    _LOG.debug(
        "technique_lifecycle_metrics_assembled family_ids=%s row_counts=%s",
        [doc.metric_family for doc in documents],
        [len(rows), len(rows), len(rows)],
    )
    return documents


def compute_technique_lifecycle_state(
    rows: Sequence[TechniqueLifecycleSnapshot],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.TECHNIQUE_LIFECYCLE_STATE)
    if spec.version_identifier != TECHNIQUE_LIFECYCLE_STATE_METRIC_VERSION:
        raise TechniqueLifecycleMetricError("unsupported_metric_version")
    if not rows:
        return _absent(spec, run_id, input_revision)
    values: dict[str, object] = {
        "layer": _LAYER,
        "row_count": len(rows),
        "performable_false_count": sum(row.performable is False for row in rows),
        "known_by_n_mean": quantize_float(
            sum(row.known_by_n for row in rows) / len(rows)
        ),
        "known_by_n_histogram": _known_by_histogram(rows),
    }
    _LOG.debug(
        "[FIX] technique_lifecycle_state known_by_n_histogram=%s row_count=%s",
        values["known_by_n_histogram"],
        len(rows),
    )
    for state in TechniqueLifecycleState:
        values[f"{state.value}_count"] = sum(row.state is state for row in rows)
    return _document(
        spec, run_id, input_revision, MetricAvailability.PRESENT, values,
        notes_code="ok", observed=len(rows),
    )


def compute_technique_lifecycle_loss(
    rows: Sequence[TechniqueLifecycleSnapshot],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.TECHNIQUE_LIFECYCLE_LOSS)
    if spec.version_identifier != TECHNIQUE_LIFECYCLE_LOSS_METRIC_VERSION:
        raise TechniqueLifecycleMetricError("unsupported_metric_version")
    if not rows:
        return _absent(spec, run_id, input_revision)
    global_rows = [row for row in rows if row.scope == "global"]
    lost = sum(
        row.state is TechniqueLifecycleState.GLOBALLY_LOST for row in global_rows
    )
    values = {
        "layer": _LAYER,
        "holders_died_count": _cause_count(rows, TechniqueLossCause.HOLDERS_DIED),
        "records_destroyed_count": _cause_count(
            rows, TechniqueLossCause.RECORDS_DESTROYED
        ),
        "materials_absent_count": _cause_count(
            rows, TechniqueLossCause.MATERIALS_ABSENT
        ),
        "teaching_chain_failed_count": _cause_count(
            rows, TechniqueLossCause.TEACHING_CHAIN_FAILED
        ),
        "globally_lost_share": quantize_float(
            lost / len(global_rows) if global_rows else 0.0
        ),
    }
    return _document(
        spec, run_id, input_revision, MetricAvailability.PRESENT, values,
        notes_code="ok", observed=len(rows),
    )


def compute_technique_lifecycle_diffusion(
    rows: Sequence[TechniqueLifecycleSnapshot],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.TECHNIQUE_LIFECYCLE_DIFFUSION)
    if spec.version_identifier != TECHNIQUE_LIFECYCLE_DIFFUSION_METRIC_VERSION:
        raise TechniqueLifecycleMetricError("unsupported_metric_version")
    global_rows = [row for row in rows if row.scope == "global"]
    if not global_rows:
        return _absent(spec, run_id, input_revision)
    rediscovered = [
        row
        for row in global_rows
        if row.state is TechniqueLifecycleState.REDISCOVERED
    ]
    new_roots = sum(row.new_lineage_root_id is not None for row in rediscovered)
    hop_count = sum(row.living_hop_count for row in global_rows)
    hop_sum = sum(row.living_hop_sum for row in global_rows)
    values = {
        "layer": _LAYER,
        "mean_location_spread": quantize_float(
            sum(row.location_count for row in global_rows) / len(global_rows)
        ),
        "mean_hop": quantize_float(hop_sum / hop_count if hop_count else 0.0),
        "rediscovery_count": len(rediscovered),
        "rediscovery_new_root_share": quantize_float(
            new_roots / len(rediscovered) if rediscovered else 0.0
        ),
    }
    _LOG.debug(
        "[FIX] technique_lifecycle_diffusion mean_location_spread=%s mean_hop=%s",
        values["mean_location_spread"],
        values["mean_hop"],
    )
    return _document(
        spec, run_id, input_revision, MetricAvailability.PRESENT, values,
        notes_code="ok", observed=len(global_rows),
    )


def _known_by_histogram(rows: Sequence[TechniqueLifecycleSnapshot]) -> str:
    counts = Counter(row.known_by_n for row in rows)
    return ",".join(f"{known_by}:{counts[known_by]}" for known_by in sorted(counts))


def _cause_count(
    rows: Sequence[TechniqueLifecycleSnapshot], cause: TechniqueLossCause
) -> int:
    return sum(cause in row.causes for row in rows)
