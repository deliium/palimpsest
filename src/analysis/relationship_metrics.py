"""Directed relationship stability metrics (Task 14).

Tick-/revision-weighted stability with missing-dimension, activation/retirement,
sign-change, variance, delta, and duration policy. Missing dimensions are
excluded — never coerced to 0.0.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from typing import Final

import numpy as np
import pandas as pd

from analysis.evidence import EvidenceStage
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
    RelationshipEdgeRow,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = ["compute_relationship_stability"]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.relationship_metrics")

_DIMENSIONS: Final[tuple[str, ...]] = (
    "trust",
    "fear",
    "affection",
    "debt",
    "respect",
    "resentment",
    "familiarity",
    "dependency",
)


def _document(
    *,
    family: str,
    algorithm_version: str,
    run_id: str,
    input_revision: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    coverage: MetricCoverage | None,
    notes_code: str,
    population: str,
    denominator: str,
) -> MetricDocument:
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family,
        algorithm_version=algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset({EvidenceStage.RELATIONSHIP_REVISION}),
        population=population,
        denominator=denominator,
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="relationship_metrics",
            source_ids=(),
            notes_code=notes_code,
        ),
    )


def compute_relationship_stability(
    rows: Sequence[RelationshipEdgeRow],
    *,
    run_id: str,
    input_revision: str,
    window_end: int,
    death_ticks: Mapping[str, int] | None = None,
) -> MetricDocument:
    """Revision-weighted directed relationship stability over a run window."""
    started = time.perf_counter()
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    window_end = require_exact_nonneg_int("window_end", window_end)
    deaths = dict(death_ticks or {})
    spec = metric_specification(MetricFamilyId.RELATIONSHIP_STABILITY)

    if not rows:
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            availability=MetricAvailability.ABSENT,
            values={},
            coverage=None,
            notes_code="no_relationships",
            population=spec.population,
            denominator=spec.denominator,
        )

    ordered = sorted(
        rows,
        key=lambda row: (
            row.source_id,
            row.target_id,
            row.logical_tick,
            row.ordinal,
        ),
    )
    records: list[dict[str, object]] = []
    for row in ordered:
        payload: dict[str, object] = {
            "source_id": row.source_id,
            "target_id": row.target_id,
            "logical_tick": row.logical_tick,
            "ordinal": row.ordinal,
            "activation_state": row.activation_state,
            "trust_confidence": row.trust_confidence,
        }
        for dim in _DIMENSIONS:
            payload[dim] = getattr(row, dim)
        records.append(payload)
    frame = pd.DataFrame.from_records(records).sort_values(
        by=["source_id", "target_id", "logical_tick", "ordinal"],
        kind="mergesort",
    )

    abs_deltas: list[float] = []
    sign_changes = 0
    sign_intervals = 0
    duration_values: list[tuple[float, float]] = []  # (value, weight)
    active_pairs: set[tuple[str, str]] = set()
    retired_pairs: set[tuple[str, str]] = set()

    grouped = frame.groupby(["source_id", "target_id"], sort=True)
    for (source_id, target_id), group in grouped:
        pair = (str(source_id), str(target_id))
        revisions = group.to_dict(orient="records")
        for index, current in enumerate(revisions):
            state = str(current["activation_state"])
            if state == "active":
                active_pairs.add(pair)
            elif state == "retired":
                retired_pairs.add(pair)
            next_tick = (
                int(revisions[index + 1]["logical_tick"])
                if index + 1 < len(revisions)
                else window_end + 1
            )
            death_cap = window_end + 1
            for endpoint in (pair[0], pair[1]):
                death = deaths.get(endpoint)
                if death is not None:
                    death_cap = min(death_cap, death + 1)
            end_tick = min(next_tick, death_cap)
            start_tick = int(current["logical_tick"])
            duration = max(0, end_tick - start_tick)
            if duration <= 0:
                continue
            for dim in _DIMENSIONS:
                value = current.get(dim)
                if value is None or (isinstance(value, float) and value != value):
                    continue
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    duration_values.append((float(value), float(duration)))
            if index == 0:
                continue
            previous = revisions[index - 1]
            for dim in _DIMENSIONS:
                before = previous.get(dim)
                after = current.get(dim)
                if before is None or after is None:
                    continue
                if isinstance(before, float) and before != before:
                    continue
                if isinstance(after, float) and after != after:
                    continue
                try:
                    before_f = float(before)
                    after_f = float(after)
                except (TypeError, ValueError):
                    continue
                abs_deltas.append(abs(after_f - before_f))
                if dim == "trust":
                    if before_f == 0.0 or after_f == 0.0:
                        continue
                    sign_intervals += 1
                    if (before_f > 0.0) != (after_f > 0.0):
                        sign_changes += 1

    if not abs_deltas and not duration_values:
        availability = MetricAvailability.PARTIAL
        values: dict[str, object] = {
            "mean_abs_delta": None,
            "sign_change_rate": None,
            "active_edge_count": len(active_pairs),
            "retired_edge_count": len(retired_pairs - active_pairs),
        }
        notes = "insufficient_intervals"
    else:
        mean_abs = (
            quantize_float(
                require_finite(float(np.mean(np.asarray(abs_deltas, dtype=np.float64))))
            )
            if abs_deltas
            else None
        )
        sign_rate = (
            quantize_float(
                require_finite(float(sign_changes) / float(sign_intervals))
            )
            if sign_intervals > 0
            else None
        )
        variance = None
        if duration_values:
            vals = np.asarray([v for v, _ in duration_values], dtype=np.float64)
            weights = np.asarray([w for _, w in duration_values], dtype=np.float64)
            weight_sum = float(np.sum(weights))
            if weight_sum > 0.0:
                mean = float(np.sum(vals * weights) / weight_sum)
                variance = quantize_float(
                    require_finite(
                        float(np.sum(weights * (vals - mean) ** 2) / weight_sum)
                    )
                )
        availability = MetricAvailability.PRESENT
        values = {
            "mean_abs_delta": mean_abs,
            "sign_change_rate": sign_rate,
            "active_edge_count": len(active_pairs),
            "retired_edge_count": len(retired_pairs - active_pairs),
        }
        if variance is not None:
            values["duration_weighted_variance"] = variance
        notes = "ok"

    duration_ms = int((time.perf_counter() - started) * 1000)
    _LOG.debug(
        "relationship_stability_complete",
        extra={
            "operation": "compute_relationship_stability",
            "run_id": run_id,
            "row_count": len(ordered),
            "active_edge_count": values.get("active_edge_count"),
            "availability": availability.value,
            "duration_ms": duration_ms,
        },
    )
    return _document(
        family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        availability=availability,
        values=values,
        coverage=MetricCoverage(
            observed=len(active_pairs) + len(retired_pairs),
            expected=len(active_pairs) + len(retired_pairs),
            ratio=1.0,
        ),
        notes_code=notes,
        population=spec.population,
        denominator=spec.denominator,
    )
