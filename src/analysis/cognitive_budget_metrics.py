"""Cognitive budget consumption detectors from detached audit rows.

Analysis-only. This module does not import agent cognition or runtimes.
Callers supply detached audit rows (and optional committed events). The
result never re-enters cognition.
"""

from __future__ import annotations

import logging
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
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "COGNITIVE_BUDGET_METRIC_VERSION",
    "compute_cognitive_budget_metrics",
]

COGNITIVE_BUDGET_METRIC_VERSION: Final[str] = "cognitive_budget@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.cognitive_budget_metrics")
_ABSENT: Final[str] = MetricAvailability.ABSENT.value


def compute_cognitive_budget_metrics(
    rows: object | None,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
    low_cost_rows: object | None = None,
    high_cost_rows: object | None = None,
) -> MetricDocument:
    """Build consumption / degradation / low-vs-high comparison blocks."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    audits = _audit_rows(rows)
    if not audits and low_cost_rows is None and high_cost_rows is None:
        _LOG.warning("cognitive_budget_metric_empty reason=%s", "no_rows")
        return _document(
            run_id=run_id,
            input_revision=input_revision,
            availability=MetricAvailability.ABSENT,
            values={},
            notes_code="empty_rows",
        )
    values: dict[str, object] = {}
    if audits:
        values.update(_consumption(audits))
        values.update(_degradation(audits))
    low_rows = _audit_rows(low_cost_rows)
    high_rows = _audit_rows(high_cost_rows)
    if low_rows or high_rows:
        values.update(_low_vs_high(low_rows, high_rows))
    _LOG.debug(
        "cognitive_budget_metric_computed run_id=%s audit_count=%s "
        "value_count=%s",
        run_id,
        len(audits),
        len(values),
    )
    return _document(
        run_id=run_id,
        input_revision=input_revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        notes_code="caller_rows",
        observed=len(audits) + len(low_rows) + len(high_rows),
        expected=len(audits) + len(low_rows) + len(high_rows),
    )


def _consumption(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    llm = [_int(row, "llm_calls_used") for row in rows]
    llm = [value for value in llm if value is not None]
    tokens = [_int(row, "tokens_used") for row in rows]
    tokens = [value for value in tokens if value is not None]
    branches = [_int(row, "imagination_branches_used") for row in rows]
    branches = [value for value in branches if value is not None]
    memories = [_int(row, "memories_recalled") for row in rows]
    memories = [value for value in memories if value is not None]
    tom = [_int(row, "tom_targets_used") for row in rows]
    tom = [value for value in tom if value is not None]
    return {
        "total_llm_calls": sum(llm) if llm else _ABSENT,
        "total_tokens": sum(tokens) if tokens else _ABSENT,
        "total_imagination_branches": sum(branches) if branches else _ABSENT,
        "total_memories_recalled": sum(memories) if memories else _ABSENT,
        "total_tom_targets": sum(tom) if tom else _ABSENT,
        "mean_llm_calls_per_tick": (
            quantize_float(sum(llm) / len(llm)) if llm else _ABSENT
        ),
        "mean_branches_per_tick": (
            quantize_float(sum(branches) / len(branches)) if branches else _ABSENT
        ),
    }


def _degradation(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    degraded = 0
    exhausted_total = 0
    for row in rows:
        if _bool(row, "degraded"):
            degraded += 1
        reasons = row.get("exhausted_reasons")
        if isinstance(reasons, (list, tuple)):
            exhausted_total += len(reasons)
    return {
        "degraded_tick_count": degraded,
        "degraded_tick_rate": (
            quantize_float(degraded / len(rows)) if rows else _ABSENT
        ),
        "exhausted_reason_count": exhausted_total,
    }


def _low_vs_high(
    low_rows: Sequence[Mapping[str, object]],
    high_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    low_llm = sum(_int(row, "llm_calls_used") or 0 for row in low_rows)
    high_llm = sum(_int(row, "llm_calls_used") or 0 for row in high_rows)
    low_branches = sum(
        _int(row, "imagination_branches_used") or 0 for row in low_rows
    )
    high_branches = sum(
        _int(row, "imagination_branches_used") or 0 for row in high_rows
    )
    if not low_rows and not high_rows:
        return {
            "low_vs_high_llm_calls_strictly_fewer": _ABSENT,
            "low_vs_high_branches_strictly_fewer": _ABSENT,
        }
    return {
        "low_cost_total_llm_calls": low_llm,
        "high_cost_total_llm_calls": high_llm,
        "low_cost_total_branches": low_branches,
        "high_cost_total_branches": high_branches,
        "low_vs_high_llm_calls_strictly_fewer": low_llm < high_llm,
        "low_vs_high_branches_strictly_fewer": low_branches < high_branches,
    }


def _audit_rows(rows: object | None) -> list[Mapping[str, object]]:
    if rows is None:
        return []
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise ValueError("cognitive_budget_rows: invalid_type")
    out: list[Mapping[str, object]] = []
    for item in rows:
        if isinstance(item, Mapping):
            out.append(item)
            continue
        # Duck-type frozen audits / SimpleNamespace
        payload = {
            "owner_id": getattr(item, "owner_id", None),
            "tick": getattr(item, "tick", None),
            "llm_calls_used": getattr(item, "llm_calls_used", None),
            "tokens_used": getattr(item, "tokens_used", None),
            "imagination_branches_used": getattr(
                item, "imagination_branches_used", None
            ),
            "memories_recalled": getattr(item, "memories_recalled", None),
            "tom_targets_used": getattr(item, "tom_targets_used", None),
            "degraded": getattr(item, "degraded", None),
            "exhausted_reasons": getattr(item, "exhausted_reasons", ()),
        }
        out.append(payload)
    return out


def _int(row: Mapping[str, object], key: str) -> int | None:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _bool(row: Mapping[str, object], key: str) -> bool:
    value = row.get(key)
    return value is True


def _document(
    *,
    run_id: str,
    input_revision: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    notes_code: str,
    observed: int = 0,
    expected: int = 0,
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.COGNITIVE_BUDGET)
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=max(expected, observed))
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
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="cognitive_budget",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )
