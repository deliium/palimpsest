"""Analysis-only dependency-care metrics (never feed cognition).

Families:
- ``dependency_survival@1``
- ``caregiver_diversity@1``
- ``caregiving_burden@1``
- ``intergenerational_cooperation@1``
"""

from __future__ import annotations

import logging
import math
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
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import (
    MetricFamilyId,
    MetricSpecification,
    metric_specification,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "CAREGIVER_DIVERSITY_METRIC_VERSION",
    "CAREGIVING_BURDEN_METRIC_VERSION",
    "DEPENDENT_SURVIVAL_METRIC_VERSION",
    "INTERGENERATIONAL_COOPERATION_METRIC_VERSION",
    "CareActRow",
    "DependencyAgentRow",
    "compute_caregiver_diversity",
    "compute_caregiving_burden",
    "compute_dependency_survival",
    "compute_intergenerational_cooperation",
]

DEPENDENT_SURVIVAL_METRIC_VERSION: Final[str] = "dependency_survival@1"
CAREGIVER_DIVERSITY_METRIC_VERSION: Final[str] = "caregiver_diversity@1"
CAREGIVING_BURDEN_METRIC_VERSION: Final[str] = "caregiving_burden@1"
INTERGENERATIONAL_COOPERATION_METRIC_VERSION: Final[str] = (
    "intergenerational_cooperation@1"
)

_LOG: Final[logging.Logger] = logging.getLogger("analysis.dependency_care")
_LAYER: Final[str] = "research_analytics"
_CARE_KINDS: Final[frozenset[str]] = frozenset(
    {"help", "give", "feed", "transport", "teach"}
)


class DependencyCareMetricError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        _LOG.error("dependency_care_metric_invalid reason_code=%s", reason_code)
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class DependencyAgentRow:
    """Detached lifecycle/survival row for a dependency-care metric."""

    agent_id: str
    dependency_status: str
    survived: bool
    lifespan_ticks: int
    generation_index: int = 0


@dataclass(frozen=True, slots=True)
class CareActRow:
    """One detached care/help act (analysis-only)."""

    caregiver_agent_id: str
    dependent_agent_id: str
    kind: str
    tick: int
    fatigue_delta: float = 0.0
    caregiver_generation_index: int = 0
    dependent_generation_index: int = 0


def compute_dependency_survival(
    agent_rows: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Survival outcomes while DEPENDENT vs INDEPENDENT cohort contrast."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = _agent_rows(agent_rows)
    _LOG.debug("dependency_survival agent_count=%s", len(rows))
    spec = metric_specification(MetricFamilyId.DEPENDENCY_SURVIVAL)
    if spec.version_identifier != DEPENDENT_SURVIVAL_METRIC_VERSION:
        raise DependencyCareMetricError("unsupported_metric_version")
    if not rows:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_dependency_agent_rows",
        )
    dependent = [row for row in rows if row.dependency_status == "dependent"]
    independent = [row for row in rows if row.dependency_status == "independent"]
    dep_rate = _survival_rate(dependent)
    ind_rate = _survival_rate(independent)
    mean_life = (
        0.0
        if not dependent
        else require_finite(
            sum(row.lifespan_ticks for row in dependent) / len(dependent)
        )
    )
    values: dict[str, object] = {
        "layer": _LAYER,
        "dependent_count": len(dependent),
        "independent_count": len(independent),
        "dependent_survival_rate": quantize_float(dep_rate),
        "independent_survival_rate": quantize_float(ind_rate),
        "mean_dependent_lifespan_ticks": quantize_float(mean_life),
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


def compute_caregiver_diversity(
    care_rows: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Unique caregivers per dependent and care-act concentration."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = _care_rows(care_rows)
    _LOG.debug("caregiver_diversity act_count=%s", len(rows))
    spec = metric_specification(MetricFamilyId.CAREGIVER_DIVERSITY)
    if spec.version_identifier != CAREGIVER_DIVERSITY_METRIC_VERSION:
        raise DependencyCareMetricError("unsupported_metric_version")
    if not rows:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_care_act_rows",
        )
    by_dependent: dict[str, set[str]] = defaultdict(set)
    caregiver_counts: Counter[str] = Counter()
    for row in rows:
        by_dependent[row.dependent_agent_id].add(row.caregiver_agent_id)
        caregiver_counts[row.caregiver_agent_id] += 1
    diversity = tuple(
        sorted((len(caregivers) for caregivers in by_dependent.values()), reverse=True)
    )
    mean_unique = (
        0.0
        if not diversity
        else require_finite(sum(diversity) / len(diversity))
    )
    entropy = _normalized_entropy(tuple(caregiver_counts.values()))
    values = {
        "layer": _LAYER,
        "care_act_count": len(rows),
        "dependent_count": len(by_dependent),
        "mean_unique_caregivers": quantize_float(mean_unique),
        "caregiver_entropy": quantize_float(entropy),
        "unique_caregiver_counts": ",".join(str(item) for item in diversity),
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


def compute_caregiving_burden(
    care_rows: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Care acts, fatigue deltas, and care-time share per caregiver."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = _care_rows(care_rows)
    _LOG.debug("caregiving_burden act_count=%s", len(rows))
    spec = metric_specification(MetricFamilyId.CAREGIVING_BURDEN)
    if spec.version_identifier != CAREGIVING_BURDEN_METRIC_VERSION:
        raise DependencyCareMetricError("unsupported_metric_version")
    if not rows:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_care_act_rows",
        )
    acts: Counter[str] = Counter()
    fatigue: dict[str, float] = defaultdict(float)
    for row in rows:
        acts[row.caregiver_agent_id] += 1
        fatigue[row.caregiver_agent_id] += row.fatigue_delta
    total_acts = len(rows)
    shares = tuple(
        sorted(
            (count / total_acts for count in acts.values()),
            reverse=True,
        )
    )
    mean_fatigue = require_finite(sum(fatigue.values()) / max(len(fatigue), 1))
    values = {
        "layer": _LAYER,
        "care_act_count": total_acts,
        "caregiver_count": len(acts),
        "mean_fatigue_delta": quantize_float(mean_fatigue),
        "max_care_time_share": quantize_float(shares[0] if shares else 0.0),
    }
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=total_acts,
        expected=total_acts,
    )


def compute_intergenerational_cooperation(
    care_rows: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Care acts whose actor/target generation_index differ."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = _care_rows(care_rows)
    _LOG.debug("intergenerational_cooperation act_count=%s", len(rows))
    spec = metric_specification(MetricFamilyId.INTERGENERATIONAL_COOPERATION)
    if spec.version_identifier != INTERGENERATIONAL_COOPERATION_METRIC_VERSION:
        raise DependencyCareMetricError("unsupported_metric_version")
    if not rows:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {"layer": _LAYER},
            notes_code="no_care_act_rows",
        )
    cross = [
        row
        for row in rows
        if row.caregiver_generation_index != row.dependent_generation_index
    ]
    rate = 0.0 if not rows else require_finite(len(cross) / len(rows))
    values = {
        "layer": _LAYER,
        "care_act_count": len(rows),
        "cross_generation_act_count": len(cross),
        "cross_generation_rate": quantize_float(rate),
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


def _survival_rate(rows: Sequence[DependencyAgentRow]) -> float:
    if not rows:
        return 0.0
    survived = sum(1 for row in rows if row.survived)
    return require_finite(survived / len(rows))


def _normalized_entropy(counts: Sequence[int]) -> float:
    total = sum(counts)
    if total <= 0 or len(counts) <= 1:
        return 0.0
    entropy = 0.0
    for count in counts:
        if count <= 0:
            continue
        p = count / total
        entropy -= p * math.log(p)
    return require_finite(entropy / math.log(len(counts)))


def _agent_rows(rows: Sequence[object]) -> tuple[DependencyAgentRow, ...]:
    if isinstance(rows, (str, bytes, set, frozenset, Mapping)) or not isinstance(
        rows, Sequence
    ):
        raise DependencyCareMetricError("invalid_agent_rows")
    parsed: list[DependencyAgentRow] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        item = _parse_agent(index, row)
        if item.agent_id in seen:
            raise DependencyCareMetricError("duplicate_agent")
        seen.add(item.agent_id)
        parsed.append(item)
    parsed.sort(key=lambda item: item.agent_id)
    return tuple(parsed)


def _parse_agent(index: int, row: object) -> DependencyAgentRow:
    if type(row) is DependencyAgentRow:
        return row
    try:
        agent_id = require_stable_id(
            f"agent[{index}].agent_id",
            getattr(row, "agent_id", None)
            if not isinstance(row, Mapping)
            else row.get("agent_id"),
        )
        status_raw = (
            getattr(row, "dependency_status", None)
            if not isinstance(row, Mapping)
            else row.get("dependency_status")
        )
        if type(status_raw) is not str:
            raise TypeError("dependency_status")
        status = status_raw.lower()
        if status not in {"dependent", "independent"}:
            raise ValueError("dependency_status")
        survived_raw = (
            getattr(row, "survived", None)
            if not isinstance(row, Mapping)
            else row.get("survived")
        )
        if type(survived_raw) is not bool:
            raise TypeError("survived")
        life = require_exact_nonneg_int(
            f"agent[{index}].lifespan_ticks",
            getattr(row, "lifespan_ticks", None)
            if not isinstance(row, Mapping)
            else row.get("lifespan_ticks"),
        )
        gen = require_exact_nonneg_int(
            f"agent[{index}].generation_index",
            getattr(row, "generation_index", 0)
            if not isinstance(row, Mapping)
            else row.get("generation_index", 0),
        )
    except (TypeError, ValueError) as exc:
        raise DependencyCareMetricError("invalid_agent_row") from exc
    return DependencyAgentRow(
        agent_id=agent_id,
        dependency_status=status,
        survived=survived_raw,
        lifespan_ticks=life,
        generation_index=gen,
    )


def _care_rows(rows: Sequence[object]) -> tuple[CareActRow, ...]:
    if isinstance(rows, (str, bytes, set, frozenset, Mapping)) or not isinstance(
        rows, Sequence
    ):
        raise DependencyCareMetricError("invalid_care_rows")
    parsed: list[CareActRow] = []
    for index, row in enumerate(rows):
        parsed.append(_parse_care(index, row))
    parsed.sort(
        key=lambda item: (
            item.tick,
            item.caregiver_agent_id,
            item.dependent_agent_id,
            item.kind,
        )
    )
    return tuple(parsed)


def _parse_care(index: int, row: object) -> CareActRow:
    if type(row) is CareActRow:
        if row.kind not in _CARE_KINDS:
            raise DependencyCareMetricError("invalid_care_kind")
        return row
    try:
        caregiver = require_stable_id(
            f"care[{index}].caregiver_agent_id",
            getattr(row, "caregiver_agent_id", None)
            if not isinstance(row, Mapping)
            else row.get("caregiver_agent_id"),
        )
        dependent = require_stable_id(
            f"care[{index}].dependent_agent_id",
            getattr(row, "dependent_agent_id", None)
            if not isinstance(row, Mapping)
            else row.get("dependent_agent_id"),
        )
        kind_raw = (
            getattr(row, "kind", None)
            if not isinstance(row, Mapping)
            else row.get("kind")
        )
        if type(kind_raw) is not str or kind_raw not in _CARE_KINDS:
            raise ValueError("kind")
        tick = require_exact_nonneg_int(
            f"care[{index}].tick",
            getattr(row, "tick", None)
            if not isinstance(row, Mapping)
            else row.get("tick"),
        )
        fatigue_raw = (
            getattr(row, "fatigue_delta", 0.0)
            if not isinstance(row, Mapping)
            else row.get("fatigue_delta", 0.0)
        )
        if isinstance(fatigue_raw, bool) or not isinstance(fatigue_raw, (int, float)):
            raise TypeError("fatigue_delta")
        fatigue = require_finite(float(fatigue_raw))
        care_gen = require_exact_nonneg_int(
            f"care[{index}].caregiver_generation_index",
            getattr(row, "caregiver_generation_index", 0)
            if not isinstance(row, Mapping)
            else row.get("caregiver_generation_index", 0),
        )
        dep_gen = require_exact_nonneg_int(
            f"care[{index}].dependent_generation_index",
            getattr(row, "dependent_generation_index", 0)
            if not isinstance(row, Mapping)
            else row.get("dependent_generation_index", 0),
        )
    except (TypeError, ValueError) as exc:
        raise DependencyCareMetricError("invalid_care_row") from exc
    return CareActRow(
        caregiver_agent_id=caregiver,
        dependent_agent_id=dependent,
        kind=kind_raw,
        tick=tick,
        fatigue_delta=fatigue,
        caregiver_generation_index=care_gen,
        dependent_generation_index=dep_gen,
    )


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
            source_kind="dependency_care",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )
