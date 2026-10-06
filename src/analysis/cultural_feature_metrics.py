"""Analysis-only cultural feature provenance / diffusion / mutation metrics."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.cultural_traits import compute_analytical_cultural_traits
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
from world.identifiers import require_stable_id

__all__ = [
    "CULTURAL_FEATURE_MUTATION_METRIC_VERSION",
    "CULTURAL_FEATURE_PROVENANCE_METRIC_VERSION",
    "CULTURAL_TRAIT_DIFFUSION_METRIC_VERSION",
    "compute_cultural_feature_mutation",
    "compute_cultural_feature_provenance",
    "compute_cultural_trait_diffusion",
]

CULTURAL_FEATURE_PROVENANCE_METRIC_VERSION: Final[str] = (
    "cultural_feature_provenance@1"
)
CULTURAL_TRAIT_DIFFUSION_METRIC_VERSION: Final[str] = "cultural_trait_diffusion@1"
CULTURAL_FEATURE_MUTATION_METRIC_VERSION: Final[str] = "cultural_feature_mutation@1"

_LOG: Final[logging.Logger] = logging.getLogger("analysis.cultural_features")
_LAYER: Final[str] = "research_analytics"


class CulturalFeatureMetricError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        _LOG.error("cultural_feature_metric_invalid reason_code=%s", reason_code)
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
    expected: int = 0,
) -> MetricDocument:
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=max(expected, observed))
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
            source_kind="cultural_features",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )


def _audit_rows(audits: Sequence[object]) -> tuple[object, ...]:
    if isinstance(audits, (set, frozenset, Mapping, str)) or not isinstance(
        audits, Sequence
    ):
        raise CulturalFeatureMetricError("audits_not_ordered")
    rows: list[object] = []
    for audit in audits:
        if type(audit).__name__ != "CulturalFeatureAudit":
            raise CulturalFeatureMetricError("invalid_audit_type")
        rows.append(audit)
    return tuple(rows)


def compute_cultural_feature_provenance(
    audits: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Channel mix, per-kind counts, independent_rediscovery share."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = _audit_rows(audits)
    _LOG.info(
        "cultural_feature_metric_compute run_id=%s family_id=%s audit_count=%s",
        document_run,
        MetricFamilyId.CULTURAL_FEATURE_PROVENANCE.value,
        len(rows),
    )
    spec = metric_specification(MetricFamilyId.CULTURAL_FEATURE_PROVENANCE)
    if spec.version_identifier != CULTURAL_FEATURE_PROVENANCE_METRIC_VERSION:
        raise CulturalFeatureMetricError("unsupported_metric_version")
    if not rows:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_cultural_feature_audits",
        )
    channels: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    independent = 0
    with_evidence = 0
    for row in rows:
        channel = getattr(getattr(row, "channel", None), "value", "unknown")
        kind = getattr(getattr(row, "feature_kind", None), "value", "unknown")
        channels[channel] += 1
        kinds[kind] += 1
        if channel == "independent_rediscovery":
            independent += 1
        if (
            int(getattr(row, "parent_count", 0)) > 0
            or channel != "independent_rediscovery"
        ):
            with_evidence += 1
    values: dict[str, object] = {
        "layer": _LAYER,
        "audit_count": len(rows),
        "channel_count": len(channels),
        "feature_kind_count": len(kinds),
        "independent_rediscovery_share": quantize_float(independent / len(rows)),
        "evidence_coverage_share": quantize_float(with_evidence / len(rows)),
        "dominant_channel": channels.most_common(1)[0][0],
    }
    for channel, count in channels.items():
        values[f"channel_{channel}_count"] = count
    for kind, count in kinds.items():
        values[f"kind_{kind}_count"] = count
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(rows),
        expected=len(rows),
    )


def compute_cultural_trait_diffusion(
    audits: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
    generation_index_by_owner: Mapping[str, int] | None = None,
) -> MetricDocument:
    """Analytical trait carrier counts and mean hop from harvested audits."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = _audit_rows(audits)
    _LOG.info(
        "cultural_feature_metric_compute run_id=%s family_id=%s audit_count=%s",
        document_run,
        MetricFamilyId.CULTURAL_TRAIT_DIFFUSION.value,
        len(rows),
    )
    spec = metric_specification(MetricFamilyId.CULTURAL_TRAIT_DIFFUSION)
    if spec.version_identifier != CULTURAL_TRAIT_DIFFUSION_METRIC_VERSION:
        raise CulturalFeatureMetricError("unsupported_metric_version")
    if not rows:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_cultural_feature_audits",
        )
    traits = compute_analytical_cultural_traits(
        rows, generation_index_by_owner=generation_index_by_owner
    )
    if not traits:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_analytical_traits",
        )
    hop_sum = sum(trait.mean_hop_index for trait in traits)
    carrier_sum = sum(trait.carrier_count for trait in traits)
    gen_spreads = [
        trait.generation_spread
        for trait in traits
        if trait.generation_spread is not None
    ]
    values: dict[str, object] = {
        "layer": _LAYER,
        "trait_count": len(traits),
        "mean_carrier_count": quantize_float(carrier_sum / len(traits)),
        "mean_hop_index": quantize_float(hop_sum / len(traits)),
        "max_carrier_count": max(trait.carrier_count for trait in traits),
    }
    if gen_spreads:
        values["mean_generation_spread"] = quantize_float(
            sum(gen_spreads) / len(gen_spreads)
        )
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(rows),
        expected=len(rows),
    )


def compute_cultural_feature_mutation(
    audits: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Mutation / recombination rates and mean parent arity."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = _audit_rows(audits)
    _LOG.info(
        "cultural_feature_metric_compute run_id=%s family_id=%s audit_count=%s",
        document_run,
        MetricFamilyId.CULTURAL_FEATURE_MUTATION.value,
        len(rows),
    )
    spec = metric_specification(MetricFamilyId.CULTURAL_FEATURE_MUTATION)
    if spec.version_identifier != CULTURAL_FEATURE_MUTATION_METRIC_VERSION:
        raise CulturalFeatureMetricError("unsupported_metric_version")
    if not rows:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_cultural_feature_audits",
        )
    mutated = sum(1 for row in rows if bool(getattr(row, "mutated", False)))
    recombined = sum(1 for row in rows if bool(getattr(row, "recombined", False)))
    parent_sum = sum(int(getattr(row, "parent_count", 0)) for row in rows)
    recombined_rows = [row for row in rows if bool(getattr(row, "recombined", False))]
    mean_recomb_parents = (
        0.0
        if not recombined_rows
        else sum(int(getattr(row, "parent_count", 0)) for row in recombined_rows)
        / len(recombined_rows)
    )
    values = {
        "layer": _LAYER,
        "audit_count": len(rows),
        "mutated_count": mutated,
        "mutation_rate": quantize_float(mutated / len(rows)),
        "recombined_count": recombined,
        "recombination_rate": quantize_float(recombined / len(rows)),
        "mean_parent_count": quantize_float(parent_sum / len(rows)),
        "mean_recombined_parent_count": quantize_float(mean_recomb_parents),
    }
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(rows),
        expected=len(rows),
    )
