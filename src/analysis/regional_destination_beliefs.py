"""Coverage summaries for owner-scoped destination evidence after a run."""

from __future__ import annotations

import logging
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
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "REGIONAL_DESTINATION_BELIEFS_METRIC_VERSION",
    "RegionalDestinationEvidenceRow",
    "compute_regional_destination_beliefs",
]

REGIONAL_DESTINATION_BELIEFS_METRIC_VERSION: Final[str] = (
    "regional_destination_beliefs@1"
)
_LOG: Final[logging.Logger] = logging.getLogger("analysis.regional_destination_beliefs")
_ALLOWED_SOURCES: Final[frozenset[str]] = frozenset(
    {"direct_observation", "communicated"}
)


class RegionalDestinationBeliefsError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        _LOG.error("regional_destination_beliefs_invalid reason_code=%s", reason_code)
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class RegionalDestinationEvidenceRow:
    owner_id: str
    destination_id: str
    region_id: str | None
    source_kind: str
    source_tick: int
    confidence: float

    def __post_init__(self) -> None:
        for name in ("owner_id", "destination_id", "source_kind"):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        if self.region_id is not None:
            object.__setattr__(
                self, "region_id", require_stable_id("region_id", self.region_id)
            )
        object.__setattr__(
            self,
            "source_tick",
            require_exact_nonneg_int("source_tick", self.source_tick),
        )
        if isinstance(self.confidence, bool) or not isinstance(
            self.confidence, (int, float)
        ):
            raise TypeError("confidence must be numeric")
        confidence = require_finite(float(self.confidence))
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence_out_of_range")
        object.__setattr__(self, "confidence", quantize_float(confidence))
        if self.source_kind not in _ALLOWED_SOURCES:
            raise ValueError("unknown_destination_evidence_source")


def compute_regional_destination_beliefs(
    rows: Sequence[object] | None,
    *,
    run_id: str,
    input_revision: str,
    as_of_tick: int,
    expected_owner_count: int | None = None,
) -> MetricDocument:
    """Summarize evidence availability without exposing propositions or truth."""
    run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("as_of_tick", as_of_tick)
    expected = (
        None
        if expected_owner_count is None
        else require_exact_nonneg_int("expected_owner_count", expected_owner_count)
    )
    evidence_available = rows is not None
    if rows is not None and (
        isinstance(rows, (str, bytes, Mapping)) or not isinstance(rows, Sequence)
    ):
        raise TypeError("destination evidence rows must be ordered")
    evidence: list[RegionalDestinationEvidenceRow] = []
    for row in rows or ():
        if type(row) is not RegionalDestinationEvidenceRow:
            raise TypeError(
                "destination evidence entries must be RegionalDestinationEvidenceRow"
            )
        if row.source_tick > tick:
            raise RegionalDestinationBeliefsError("source_tick_after_as_of")
        evidence.append(row)
    spec = metric_specification(MetricFamilyId.REGIONAL_DESTINATION_BELIEFS)
    if spec.version_identifier != REGIONAL_DESTINATION_BELIEFS_METRIC_VERSION:
        raise RegionalDestinationBeliefsError("unsupported_metric_version")
    owners = {row.owner_id for row in evidence}
    destinations = {row.destination_id for row in evidence}
    direct = sum(row.source_kind == "direct_observation" for row in evidence)
    communicated = sum(row.source_kind == "communicated" for row in evidence)
    assigned = sum(row.region_id is not None for row in evidence)
    expected_count = len(owners) if expected is None else max(expected, len(owners))
    values: dict[str, object] = {
        "communicated_count": communicated if evidence_available else None,
        "destination_count": len(destinations) if evidence_available else None,
        "direct_observation_count": direct if evidence_available else None,
        "evidence_trace_count": len(evidence) if evidence_available else None,
        "expected_owner_count": expected_count,
        "owner_count": len(owners) if evidence_available else None,
        "owner_coverage_ratio": (
            None
            if not evidence_available or expected_count == 0
            else quantize_float(len(owners) / max(expected_count, len(owners)))
        ),
        "region_assigned_evidence_count": assigned if evidence_available else None,
        "unassigned_region_evidence_count": (
            len(evidence) - assigned if evidence_available else None
        ),
    }
    if evidence:
        values["mean_confidence"] = quantize_float(
            require_finite(sum(row.confidence for row in evidence) / len(evidence))
        )
        values["mean_source_age_ticks"] = quantize_float(
            require_finite(
                sum(tick - row.source_tick for row in evidence) / len(evidence)
            )
        )
    else:
        values["mean_confidence"] = None
        values["mean_source_age_ticks"] = None
    if not evidence_available:
        availability = MetricAvailability.UNKNOWN
        coverage = None
        notes_code = "evidence_unavailable"
    elif not evidence:
        availability = MetricAvailability.ABSENT
        coverage = MetricCoverage(observed=0, expected=expected_count)
        notes_code = "no_destination_evidence"
    else:
        availability = (
            MetricAvailability.PRESENT
            if expected_count <= len(owners)
            else MetricAvailability.PARTIAL
        )
        coverage = MetricCoverage(
            observed=len(owners),
            expected=max(expected_count, len(owners)),
            ratio=(
                1.0
                if expected_count == 0
                else len(owners) / max(expected_count, len(owners))
            ),
        )
        notes_code = (
            "ok"
            if availability is MetricAvailability.PRESENT
            else "owner_coverage_partial"
        )
    _LOG.debug(
        "regional_destination_beliefs_coverage run_id=%s evidence_count=%s "
        "owner_count=%s expected_owner_count=%s availability=%s",
        run,
        None if not evidence_available else len(evidence),
        len(owners),
        expected_count,
        availability.value,
    )
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run,
        input_revision=revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind="regional_destination_evidence",
            source_ids=(run,) if evidence else (),
            notes_code=notes_code,
        ),
    )
