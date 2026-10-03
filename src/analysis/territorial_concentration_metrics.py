"""Territorial concentration (HHI / top-share) over detached spatial rows.

Analysis-only. Leaves ``spatial_control@1`` claim-contest logic unchanged.
Missing rows are ``ABSENT``, never coerced to zero.
"""

from __future__ import annotations

import logging
from collections import Counter
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
from world.identifiers import require_stable_id

__all__ = [
    "TERRITORIAL_CONCENTRATION_METRIC_VERSION",
    "TerritorialConcentrationRow",
    "compute_territorial_concentration",
]

TERRITORIAL_CONCENTRATION_METRIC_VERSION: Final[str] = "territorial_concentration@1"
_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.territorial_concentration_metrics"
)


@dataclass(frozen=True, slots=True)
class TerritorialConcentrationRow:
    """One detached presence or control observation at a location."""

    location_id: str
    tick: int = 0
    agent_id: str = ""
    weight: float = 1.0


def compute_territorial_concentration(
    presence_rows: Sequence[object] | None,
    control_rows: Sequence[object] | None = None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """HHI and top-1/top-3 shares over presence ticks and control events."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.TERRITORIAL_CONCENTRATION)
    presence = _parse_rows(presence_rows, field="presence_rows")
    control = _parse_rows(control_rows, field="control_rows")
    presence_stats = _concentration(presence)
    control_stats = _concentration(control)
    location_cardinality = {
        "presence": 0 if presence_stats is None else presence_stats["location_count"],
        "control": 0 if control_stats is None else control_stats["location_count"],
    }
    present_keys = _present_key_flags(presence_stats, control_stats)
    _LOG.debug(
        "territorial_concentration_compute",
        extra={
            "operation": "compute_territorial_concentration",
            "family_id": spec.family_id.value,
            "run_id": document_run,
            "location_cardinality": location_cardinality,
            "share_keys_present": present_keys,
        },
    )
    if presence_stats is None and control_stats is None:
        _LOG.warning(
            "territorial_concentration_empty",
            extra={
                "operation": "compute_territorial_concentration",
                "family_id": spec.family_id.value,
                "reason": "no_spatial_rows",
            },
        )
        return _document(
            spec.family_id.value,
            spec.algorithm_version,
            document_run,
            revision,
            frozenset(spec.evidence_inputs),
            spec.population,
            spec.denominator,
            MetricAvailability.ABSENT,
            {},
            notes_code="no_spatial_rows",
        )

    values: dict[str, object] = {}
    if presence_stats is not None:
        values.update(
            {
                "presence_hhi": presence_stats["hhi"],
                "presence_top1_share": presence_stats["top1_share"],
                "presence_top3_share": presence_stats["top3_share"],
                "presence_location_count": presence_stats["location_count"],
            }
        )
    if control_stats is not None:
        values.update(
            {
                "control_hhi": control_stats["hhi"],
                "control_top1_share": control_stats["top1_share"],
                "control_top3_share": control_stats["top3_share"],
                "control_location_count": control_stats["location_count"],
            }
        )
    observed = (0 if presence_stats is None else 1) + (
        0 if control_stats is None else 1
    )
    return _document(
        spec.family_id.value,
        spec.algorithm_version,
        document_run,
        revision,
        frozenset(spec.evidence_inputs),
        spec.population,
        spec.denominator,
        MetricAvailability.PRESENT if observed == 2 else MetricAvailability.PARTIAL,
        values,
        notes_code="ok",
        observed=observed,
        expected=2,
    )


def _parse_rows(
    rows: Sequence[object] | None, *, field: str
) -> tuple[TerritorialConcentrationRow, ...]:
    if rows is None:
        return ()
    if isinstance(rows, (str, bytes, set, frozenset, Mapping)) or not isinstance(
        rows, Sequence
    ):
        raise TypeError(f"{field}: not_ordered")
    parsed: list[TerritorialConcentrationRow] = []
    for index, row in enumerate(rows):
        if type(row) is TerritorialConcentrationRow:
            parsed.append(row)
            continue
        location_id = getattr(row, "location_id", None)
        if not isinstance(location_id, str) or not location_id:
            raise TypeError(f"{field}[{index}]: invalid_location_id")
        tick = getattr(row, "tick", 0)
        agent_id = getattr(row, "agent_id", "")
        weight = getattr(row, "weight", 1.0)
        if type(tick) is not int or tick < 0:
            raise TypeError(f"{field}[{index}]: invalid_tick")
        if not isinstance(agent_id, str):
            raise TypeError(f"{field}[{index}]: invalid_agent_id")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise TypeError(f"{field}[{index}]: invalid_weight")
        weight_f = require_finite(float(weight))
        if weight_f < 0.0:
            raise ValueError(f"{field}[{index}]: negative_weight")
        parsed.append(
            TerritorialConcentrationRow(
                location_id=require_stable_id(f"{field}.location_id", location_id),
                tick=tick,
                agent_id=agent_id,
                weight=weight_f,
            )
        )
    return tuple(parsed)


def _concentration(
    rows: Sequence[TerritorialConcentrationRow],
) -> dict[str, object] | None:
    if not rows:
        return None
    totals: Counter[str] = Counter()
    for row in rows:
        totals[row.location_id] += float(row.weight)
    mass = float(sum(totals.values()))
    if mass <= 0.0:
        return None
    shares = sorted(
        (float(count) / mass for count in totals.values()),
        reverse=True,
    )
    hhi = quantize_float(require_finite(float(sum(share * share for share in shares))))
    top1 = quantize_float(require_finite(float(shares[0])))
    top3 = quantize_float(require_finite(float(sum(shares[:3]))))
    return {
        "hhi": hhi,
        "top1_share": top1,
        "top3_share": top3,
        "location_count": len(totals),
    }


def _present_key_flags(
    presence: dict[str, object] | None,
    control: dict[str, object] | None,
) -> dict[str, bool]:
    return {
        "presence_hhi": presence is not None,
        "presence_top1_share": presence is not None,
        "presence_top3_share": presence is not None,
        "control_hhi": control is not None,
        "control_top1_share": control is not None,
        "control_top3_share": control is not None,
    }


def _document(
    family: str,
    algorithm_version: str,
    run_id: str,
    revision: str,
    evidence_stages: frozenset,
    population: str,
    denominator: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    *,
    notes_code: str,
    observed: int = 0,
    expected: int = 0,
) -> MetricDocument:
    coverage = None
    if availability in (MetricAvailability.PRESENT, MetricAvailability.PARTIAL):
        coverage = MetricCoverage(observed=observed, expected=max(expected, observed))
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family,
        algorithm_version=algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=revision,
        evidence_stages=evidence_stages,
        population=population,
        denominator=denominator,
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="territorial_concentration",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )
