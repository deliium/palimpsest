"""Join objective and subjective skill audits after a run.

Analysis-only. This module does not fold skill growth or update beliefs, and
those updaters do not import analysis.
"""

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
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_stable_id

__all__ = [
    "SKILL_LEARNING_METRIC_VERSION",
    "SkillGapRow",
    "SkillLearningMetricResult",
    "compute_skill_learning",
]

SKILL_LEARNING_METRIC_VERSION: Final[str] = "skill_learning@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.skill_learning_metrics")


def _quantize(value: float) -> float:
    return round(value / 1e-6) * 1e-6


@dataclass(frozen=True, slots=True)
class SkillGapRow:
    """One agent-domain join of harvested skill rows."""

    agent_id: str
    domain: str
    empirical_status: str
    objective_level: float | None = None
    believed_level: float | None = None
    gap: float | None = None


@dataclass(frozen=True, slots=True)
class SkillLearningMetricResult:
    """Aggregate document plus per-domain gaps."""

    document: MetricDocument
    rows: tuple[SkillGapRow, ...]


def compute_skill_learning(
    audits: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> SkillLearningMetricResult:
    """Join both sides on agent id and domain. A missing side is unmatched."""
    if isinstance(audits, (set, frozenset, Mapping, str)) or not isinstance(
        audits, Sequence
    ):
        raise TypeError("audits: not_ordered")
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    grouped: dict[tuple[str, str], dict[str, float]] = {}
    order: list[tuple[str, str]] = []
    for audit in audits:
        if type(audit).__name__ != "SkillAudit":
            raise TypeError("audits: invalid_type")
        agent = getattr(audit.agent_id, "value", None)
        side = getattr(audit.side, "value", None)
        domain = audit.domain
        if type(agent) is not str or type(side) is not str or type(domain) is not str:
            raise TypeError("audits: invalid_type")
        key = (agent, domain)
        if key not in grouped:
            grouped[key] = {}
            order.append(key)
        grouped[key][side] = float(audit.level)
    rows: list[SkillGapRow] = []
    for agent, domain in order:
        sides = grouped[(agent, domain)]
        objective = sides.get("objective")
        believed = sides.get("subjective")
        if objective is None or believed is None:
            row = SkillGapRow(
                agent_id=agent,
                domain=domain,
                empirical_status="unmatched",
                objective_level=objective,
                believed_level=believed,
            )
        else:
            gap = _quantize(abs(objective - believed))
            row = SkillGapRow(
                agent_id=agent,
                domain=domain,
                empirical_status="matched",
                objective_level=objective,
                believed_level=believed,
                gap=gap,
            )
            _LOG.debug(
                "skill_gap agent_id=%s domain=%s gap=%s",
                agent,
                domain,
                gap,
            )
        rows.append(row)
    spec = metric_specification(MetricFamilyId.SKILL_LEARNING)
    matched = sum(1 for item in rows if item.empirical_status == "matched")
    if not rows:
        document = _document(
            spec_family=spec.family_id.value,
            algorithm=spec.algorithm_version,
            run_id=document_run,
            revision=revision,
            evidence=frozenset(spec.evidence_inputs),
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.ABSENT,
            values={},
            notes="no_rows",
            coverage=None,
        )
        return SkillLearningMetricResult(document=document, rows=())
    gaps = [item.gap for item in rows if item.gap is not None]
    maximum = max(gaps) if gaps else 0.0
    document = _document(
        spec_family=spec.family_id.value,
        algorithm=spec.algorithm_version,
        run_id=document_run,
        revision=revision,
        evidence=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        availability=MetricAvailability.PRESENT,
        values={
            "matched_count": quantize_float(float(matched)),
            "unmatched_count": quantize_float(float(len(rows) - matched)),
            "max_gap": quantize_float(maximum),
        },
        notes="ok",
        coverage=MetricCoverage(observed=matched, expected=len(rows)),
    )
    return SkillLearningMetricResult(document=document, rows=tuple(rows))


def _document(
    *,
    spec_family: str,
    algorithm: str,
    run_id: str,
    revision: str,
    evidence: frozenset[object],
    population: str,
    denominator: str,
    availability: MetricAvailability,
    values: dict[str, float],
    notes: str,
    coverage: MetricCoverage | None,
) -> MetricDocument:
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec_family,
        algorithm_version=algorithm,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=revision,
        evidence_stages=evidence,
        population=population,
        denominator=denominator,
        coverage=coverage,
        availability=availability,
        values=values,
        provenance=MetricProvenance(
            source_kind="skill_learning",
            source_ids=(run_id,) if notes == "ok" else (),
            notes_code=notes,
        ),
    )
