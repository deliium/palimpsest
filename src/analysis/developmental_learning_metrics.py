"""Analysis-only developmental learning metrics (never feed cognition).

Families:
- ``developmental_acquisition@1``
- ``developmental_source_mix@1``
- ``developmental_divergence@1``
"""

from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict
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
from world.identifiers import require_stable_id

__all__ = [
    "DEVELOPMENTAL_ACQUISITION_METRIC_VERSION",
    "DEVELOPMENTAL_DIVERGENCE_METRIC_VERSION",
    "DEVELOPMENTAL_SOURCE_MIX_METRIC_VERSION",
    "compute_developmental_acquisition",
    "compute_developmental_divergence",
    "compute_developmental_source_mix",
]

DEVELOPMENTAL_ACQUISITION_METRIC_VERSION: Final[str] = "developmental_acquisition@1"
DEVELOPMENTAL_SOURCE_MIX_METRIC_VERSION: Final[str] = "developmental_source_mix@1"
DEVELOPMENTAL_DIVERGENCE_METRIC_VERSION: Final[str] = "developmental_divergence@1"

_LOG: Final[logging.Logger] = logging.getLogger("analysis.developmental_learning")
_LAYER: Final[str] = "research_analytics"


class DevelopmentalLearningMetricError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        _LOG.error(
            "developmental_learning_metric_invalid reason_code=%s", reason_code
        )
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
            source_kind="developmental_learning",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )


def _audit_rows(audits: Sequence[object]) -> tuple[object, ...]:
    if isinstance(audits, (set, frozenset, Mapping, str)) or not isinstance(
        audits, Sequence
    ):
        raise DevelopmentalLearningMetricError("audits_not_ordered")
    rows: list[object] = []
    for audit in audits:
        if type(audit).__name__ != "DevelopmentalAcquisitionAudit":
            raise DevelopmentalLearningMetricError("invalid_audit_type")
        rows.append(audit)
    return tuple(rows)


def compute_developmental_acquisition(
    audits: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Per-agent domain coverage, mean confidence band mass, time-to-first."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = _audit_rows(audits)
    _LOG.info(
        "developmental_metric_compute run_id=%s family_id=%s agent_count=%s",
        document_run,
        MetricFamilyId.DEVELOPMENTAL_ACQUISITION.value,
        len({getattr(r.owner_id, "value", None) for r in rows}),
    )
    spec = metric_specification(MetricFamilyId.DEVELOPMENTAL_ACQUISITION)
    if spec.version_identifier != DEVELOPMENTAL_ACQUISITION_METRIC_VERSION:
        raise DevelopmentalLearningMetricError("unsupported_metric_version")
    if not rows:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_developmental_audits",
        )
    acquired = [r for r in rows if bool(getattr(r, "acquired", False))]
    agents: dict[str, set[str]] = defaultdict(set)
    first_tick: dict[str, int] = {}
    band_mass = 0.0
    band_weight = {"none": 0.0, "low": 0.25, "mid": 0.5, "high": 0.85}
    for row in acquired:
        owner = getattr(row.owner_id, "value", None)
        domain = getattr(getattr(row, "domain_id", None), "value", None)
        if type(owner) is not str or type(domain) is not str:
            continue
        agents[owner].add(domain)
        tick = int(getattr(row, "tick", 0))
        if owner not in first_tick or tick < first_tick[owner]:
            first_tick[owner] = tick
        band = str(getattr(row, "confidence_band", "none"))
        band_mass += band_weight.get(band, 0.0)
    coverage = (
        0.0
        if not agents
        else sum(len(domains) for domains in agents.values()) / len(agents)
    )
    mean_conf = 0.0 if not acquired else band_mass / len(acquired)
    mean_ttf = (
        0.0
        if not first_tick
        else sum(first_tick.values()) / len(first_tick)
    )
    exposure_samples = [
        int(row.exposures_to_acquisition)
        for row in acquired
        if getattr(row, "exposures_to_acquisition", None) is not None
    ]
    mean_exposures = (
        0.0
        if not exposure_samples
        else sum(exposure_samples) / len(exposure_samples)
    )
    values: dict[str, object] = {
        "layer": _LAYER,
        "agent_count": len(agents),
        "acquired_count": len(acquired),
        "mean_domain_coverage": quantize_float(coverage),
        "mean_confidence_mass": quantize_float(mean_conf),
        "mean_time_to_first_entry": quantize_float(mean_ttf),
        "mean_exposures_to_acquisition": quantize_float(mean_exposures),
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


def compute_developmental_source_mix(
    audits: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Share of acquired entries by source_id; teacher entropy when present."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = _audit_rows(audits)
    _LOG.info(
        "developmental_metric_compute run_id=%s family_id=%s agent_count=%s",
        document_run,
        MetricFamilyId.DEVELOPMENTAL_SOURCE_MIX.value,
        len({getattr(r.owner_id, "value", None) for r in rows}),
    )
    spec = metric_specification(MetricFamilyId.DEVELOPMENTAL_SOURCE_MIX)
    if spec.version_identifier != DEVELOPMENTAL_SOURCE_MIX_METRIC_VERSION:
        raise DevelopmentalLearningMetricError("unsupported_metric_version")
    acquired = [r for r in rows if bool(getattr(r, "acquired", False))]
    if not acquired:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_acquired_audits",
        )
    source_counts: Counter[str] = Counter()
    teacher_counts: Counter[str] = Counter()
    for row in acquired:
        source = getattr(getattr(row, "source_id", None), "value", None)
        if type(source) is str:
            source_counts[source] += 1
        if bool(getattr(row, "teacher_present", False)):
            teacher = getattr(row, "teacher_agent_id", None)
            token = getattr(teacher, "value", None) if teacher is not None else None
            if type(token) is str:
                teacher_counts[token] += 1
    total = sum(source_counts.values()) or 1
    teacher_total = sum(teacher_counts.values())
    if teacher_total <= 0:
        entropy = 0.0
    else:
        entropy = 0.0
        for count in teacher_counts.values():
            p = count / teacher_total
            entropy -= p * math.log(p, 2)
        max_h = math.log(len(teacher_counts), 2) if len(teacher_counts) > 1 else 1.0
        entropy = entropy / max_h if max_h > 0 else 0.0
    values: dict[str, object] = {
        "layer": _LAYER,
        "acquired_count": len(acquired),
        "teacher_present_count": teacher_total,
        "teacher_entropy": quantize_float(entropy),
        "dominant_source_share": quantize_float(
            max(source_counts.values()) / total if source_counts else 0.0
        ),
        "source_kind_count": len(source_counts),
    }
    for source, count in sorted(source_counts.items()):
        values[f"share_{source}"] = quantize_float(count / total)
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(acquired),
        expected=len(acquired),
    )


def compute_developmental_divergence(
    ledgers: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Pairwise concept-set Jaccard distance between owner ledgers."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    if isinstance(ledgers, (set, frozenset, Mapping, str)) or not isinstance(
        ledgers, Sequence
    ):
        raise DevelopmentalLearningMetricError("ledgers_not_ordered")
    _LOG.info(
        "developmental_metric_compute run_id=%s family_id=%s agent_count=%s",
        document_run,
        MetricFamilyId.DEVELOPMENTAL_DIVERGENCE.value,
        len(ledgers),
    )
    spec = metric_specification(MetricFamilyId.DEVELOPMENTAL_DIVERGENCE)
    if spec.version_identifier != DEVELOPMENTAL_DIVERGENCE_METRIC_VERSION:
        raise DevelopmentalLearningMetricError("unsupported_metric_version")
    sets: list[tuple[str, frozenset[str]]] = []
    for ledger in ledgers:
        if type(ledger).__name__ != "DevelopmentalKnowledgeLedger":
            raise DevelopmentalLearningMetricError("invalid_ledger_type")
        owner = getattr(getattr(ledger, "owner_id", None), "value", None)
        if type(owner) is not str:
            raise DevelopmentalLearningMetricError("invalid_ledger_owner")
        keys = frozenset(
            f"{getattr(e.domain_id, 'value', '')}:{e.concept_key}"
            for e in getattr(ledger, "entries", ())
        )
        sets.append((owner, keys))
    if len(sets) < 2:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="insufficient_agents",
        )
    distances: list[float] = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            a = sets[i][1]
            b = sets[j][1]
            union = a | b
            if not union:
                dist = 0.0
            else:
                dist = 1.0 - (len(a & b) / len(union))
            distances.append(dist)
    mean_dist = sum(distances) / len(distances)
    values = {
        "layer": _LAYER,
        "pair_count": len(distances),
        "mean_pairwise_distance": quantize_float(mean_dist),
        "max_pairwise_distance": quantize_float(max(distances)),
    }
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(sets),
        expected=len(sets),
    )
