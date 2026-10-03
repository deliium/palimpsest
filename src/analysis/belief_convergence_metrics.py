"""Belief convergence via pairwise Jaccard on detached claim sets.

Analysis-only. Convergence is not accuracy — no truth specs required.
Overlap identity is ``(claim_id, value_kind, normalized value)``. Never uses
claim text. Does not import cognition or mutate beliefs.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    BeliefClaimRow,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_stable_id

__all__ = [
    "BELIEF_CONVERGENCE_METRIC_VERSION",
    "claim_overlap_token",
    "compute_belief_convergence",
]

BELIEF_CONVERGENCE_METRIC_VERSION: Final[str] = "belief_convergence@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.belief_convergence_metrics")


def claim_overlap_token(row: object) -> tuple[str, str, str] | None:
    """Build overlap identity from claim fields — never claim text."""
    claim_id = getattr(row, "claim_id", None)
    value_kind = getattr(row, "value_kind", None)
    if not isinstance(claim_id, str) or not isinstance(value_kind, str):
        return None
    activation = getattr(row, "activation_state", None)
    if activation != "active":
        return None
    normalized = _normalized_value(row, value_kind)
    if normalized is None:
        return None
    return (claim_id, value_kind, normalized)


def compute_belief_convergence(
    claims: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Pairwise Jaccard trajectories over per-owner active claim sets."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.BELIEF_CONVERGENCE)
    if isinstance(claims, (str, bytes, set, frozenset, Mapping)) or not isinstance(
        claims, Sequence
    ):
        raise TypeError("claims: not_ordered")

    ordered = _ordered_rows(claims)
    by_tick = _sets_by_tick(ordered)
    owner_count = len({row.owner_id for row in ordered})
    universe = {
        token
        for row in ordered
        if (token := claim_overlap_token(row)) is not None
    }
    _LOG.debug(
        "belief_convergence_compute",
        extra={
            "operation": "compute_belief_convergence",
            "family_id": spec.family_id.value,
            "run_id": document_run,
            "owner_count": owner_count,
            "claim_universe_size": len(universe),
            "tick_count": len(by_tick),
        },
    )
    if owner_count < 2 or not by_tick:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {},
            notes_code="unevaluable_claims",
        )

    ticks = sorted(by_tick)
    first_mean = _mean_pairwise_jaccard(by_tick[ticks[0]])
    final_mean = _mean_pairwise_jaccard(by_tick[ticks[-1]])
    if first_mean is None or final_mean is None:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {},
            notes_code="unevaluable_claims",
        )
    delta = quantize_float(require_finite(float(final_mean - first_mean)))
    values: dict[str, object] = {
        "mean_pairwise_jaccard_final": final_mean,
        "mean_pairwise_jaccard_delta": delta,
        "owner_count": owner_count,
        "claim_universe_size": len(universe),
    }
    _LOG.debug(
        "belief_convergence_done",
        extra={
            "operation": "compute_belief_convergence",
            "family_id": spec.family_id.value,
            "run_id": document_run,
            "owner_count": owner_count,
            "claim_universe_size": len(universe),
            "availability": MetricAvailability.PRESENT.value,
        },
    )
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=owner_count,
        expected=owner_count,
    )


def _ordered_rows(claims: Sequence[object]) -> tuple[BeliefClaimRow, ...]:
    parsed: list[BeliefClaimRow] = []
    for index, row in enumerate(claims):
        if type(row) is BeliefClaimRow:
            parsed.append(row)
            continue
        # Duck-typed construction into BeliefClaimRow for validation.
        try:
            parsed.append(
                BeliefClaimRow(
                    owner_id=str(getattr(row, "owner_id")),
                    belief_id=str(getattr(row, "belief_id", "belief")),
                    claim_id=str(getattr(row, "claim_id")),
                    logical_tick=int(getattr(row, "logical_tick")),
                    activation_state=str(getattr(row, "activation_state")),
                    confidence=getattr(row, "confidence", None),
                    value_kind=str(getattr(row, "value_kind")),
                    bool_value=getattr(row, "bool_value", None),
                    categorical_value=getattr(row, "categorical_value", None),
                    numeric_value=getattr(row, "numeric_value", None),
                )
            )
        except (TypeError, ValueError, AttributeError) as exc:
            raise TypeError(f"claims[{index}]: invalid_type") from exc
    return tuple(
        sorted(
            parsed,
            key=lambda item: (
                item.logical_tick,
                item.owner_id,
                item.belief_id,
                item.claim_id,
            ),
        )
    )


def _normalized_value(row: object, value_kind: str) -> str | None:
    if value_kind == "bool":
        value = getattr(row, "bool_value", None)
        if type(value) is not bool:
            return None
        return "true" if value else "false"
    if value_kind == "categorical":
        value = getattr(row, "categorical_value", None)
        if not isinstance(value, str) or not value:
            return None
        return value
    if value_kind == "numeric":
        value = getattr(row, "numeric_value", None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return f"{quantize_float(require_finite(float(value))):.12f}"
    return None


def _sets_by_tick(
    rows: Sequence[BeliefClaimRow],
) -> dict[int, dict[str, frozenset[tuple[str, str, str]]]]:
    """Cumulative per-tick owner claim sets; latest activation wins per claim."""
    snapshots: dict[int, dict[str, frozenset[tuple[str, str, str]]]] = {}
    for tick in sorted({row.logical_tick for row in rows}):
        latest: dict[tuple[str, str], BeliefClaimRow] = {}
        for row in rows:
            if row.logical_tick > tick:
                continue
            key = (row.owner_id, row.claim_id)
            previous = latest.get(key)
            if previous is None or (row.logical_tick, row.belief_id) >= (
                previous.logical_tick,
                previous.belief_id,
            ):
                latest[key] = row
        owner_sets: dict[str, set[tuple[str, str, str]]] = {}
        for (_owner_id, _claim_id), row in sorted(latest.items()):
            token = claim_overlap_token(row)
            if token is None:
                continue
            owner_sets.setdefault(row.owner_id, set()).add(token)
        # Ensure owners with empty active sets still participate.
        for row in rows:
            if row.logical_tick <= tick:
                owner_sets.setdefault(row.owner_id, set())
        snapshots[tick] = {
            owner: frozenset(tokens) for owner, tokens in sorted(owner_sets.items())
        }
    return snapshots


def _mean_pairwise_jaccard(
    owner_sets: Mapping[str, frozenset[tuple[str, str, str]]],
) -> float | None:
    owners = sorted(owner_sets)
    if len(owners) < 2:
        return None
    scores: list[float] = []
    for index, left in enumerate(owners):
        for right in owners[index + 1 :]:
            a = owner_sets[left]
            b = owner_sets[right]
            if not a and not b:
                scores.append(1.0)
                continue
            union = a | b
            if not union:
                scores.append(1.0)
                continue
            scores.append(float(len(a & b)) / float(len(union)))
    if not scores:
        return None
    scores.sort()
    return quantize_float(require_finite(float(sum(scores) / len(scores))))


def _document(
    spec: object,
    run_id: str,
    revision: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    *,
    notes_code: str,
    observed: int = 0,
    expected: int = 0,
) -> MetricDocument:
    family = getattr(spec, "family_id")
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=expected)
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family.value,
        algorithm_version=getattr(spec, "algorithm_version"),
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=revision,
        evidence_stages=frozenset(getattr(spec, "evidence_inputs")),
        population=getattr(spec, "population"),
        denominator=getattr(spec, "denominator"),
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="belief_convergence",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )
