"""Cultural narrative lineage detectors from detached variant history rows.

Analysis-only. This module does not import agent cognition or runtimes.
Callers supply detached rows. The result never re-enters a ledger.
"""

from __future__ import annotations

import logging
import math
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
    "CULTURAL_NARRATIVE_LINEAGE_METRIC_VERSION",
    "compute_cultural_narrative_lineage",
]

CULTURAL_NARRATIVE_LINEAGE_METRIC_VERSION: Final[str] = "cultural_narrative_lineage@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.cultural_narrative_metrics")
_ABSENT: Final[str] = MetricAvailability.ABSENT.value


def compute_cultural_narrative_lineage(
    rows: object | None,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Build persistence/mutation/distortion/source-loss/convergence/spread blocks."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    history = _variant_rows(rows)
    if not history:
        _LOG.warning("cultural_narrative_metric_empty reason=%s", "no_rows")
        return _document(
            run_id=run_id,
            input_revision=input_revision,
            availability=MetricAvailability.ABSENT,
            values={},
            notes_code="empty_rows",
        )
    final_tick = max(_int(row, "tick") or 0 for row in history)
    final_rows = [row for row in history if (_int(row, "tick") or 0) == final_tick]
    active = [row for row in final_rows if _text(row, "status") == "active"]
    values: dict[str, object] = {}
    values.update(_narrative_persistence(history, final_rows, active))
    values.update(_mutation_rate(history, active))
    values.update(_distortion(active))
    values.update(_source_loss(history, active))
    values.update(_convergence(history, active))
    values.update(_geographic_social_spread(active))
    _LOG.debug(
        "cultural_narrative_metric_computed active_variant_count=%s "
        "block_availability=%s",
        len(active),
        "present" if values else "absent",
    )
    return _document(
        run_id=run_id,
        input_revision=input_revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        notes_code="caller_rows",
        observed=len(history),
        expected=len(history),
    )


def _narrative_persistence(
    history: Sequence[Mapping[str, object]],
    final_rows: Sequence[Mapping[str, object]],
    active: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    active_count = len(active)
    strengths = [_float(row, "strength") for row in active]
    strengths = [value for value in strengths if value is not None]
    durations: list[float] = []
    for row in final_rows:
        if _text(row, "status") not in {"active", "merged"}:
            continue
        first = _int(row, "first_tick")
        last = _int(row, "last_tick")
        if first is None or last is None:
            continue
        durations.append(float(last - first))
    founding = {
        _text(row, "fingerprint")
        for row in history
        if (_int(row, "mutation_generation") or 0) == 0
        and _text(row, "fingerprint") is not None
    }
    live_founding = set()
    for row in active:
        fingerprint = _text(row, "fingerprint")
        if fingerprint is None:
            continue
        if (_int(row, "mutation_generation") or 0) == 0:
            live_founding.add(fingerprint)
        else:
            # Child still represents founding lineage when active.
            live_founding.add(fingerprint)
    # Prefer explicit founding fingerprint presence via active/merged lineage.
    represented = 0
    for fingerprint in founding:
        if any(
            _text(row, "fingerprint") == fingerprint
            or (
                _text(row, "status") in {"active", "merged"}
                and (_int(row, "mutation_generation") or 0) >= 0
                and fingerprint is not None
            )
            for row in final_rows
            if _text(row, "status") in {"active", "merged"}
        ):
            represented += 1
    persistence_rate: object = _ABSENT
    if founding:
        persistence_rate = quantize_float(represented / len(founding))
    return {
        "active_variant_count": active_count,
        "mean_active_strength": (
            _ABSENT
            if not strengths
            else quantize_float(sum(strengths) / len(strengths))
        ),
        "mean_duration_ticks": (
            _ABSENT
            if not durations
            else quantize_float(sum(durations) / len(durations))
        ),
        "persistence_rate": persistence_rate,
    }


def _mutation_rate(
    history: Sequence[Mapping[str, object]],
    active: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    founding = [
        row
        for row in history
        if (_int(row, "mutation_generation") or 0) == 0
    ]
    children = [
        row
        for row in history
        if (_int(row, "mutation_generation") or 0) >= 1
    ]
    branch_rate: object = _ABSENT
    if founding:
        branch_rate = quantize_float(len(children) / len(founding))
    generations = [
        float(_int(row, "mutation_generation") or 0) for row in active
    ]
    # fingerprint churn: distinct fingerprints per transmission root
    by_root: dict[str, set[str]] = {}
    for row in history:
        root = _text(row, "transmission_root_id")
        fingerprint = _text(row, "fingerprint")
        if root is None or fingerprint is None:
            continue
        by_root.setdefault(root, set()).add(fingerprint)
    churn_values = [float(len(items)) for items in by_root.values()]
    return {
        "branch_rate": branch_rate,
        "mean_mutation_generation": (
            _ABSENT
            if not generations
            else quantize_float(sum(generations) / len(generations))
        ),
        "fingerprint_churn": (
            _ABSENT
            if not churn_values
            else quantize_float(sum(churn_values) / len(churn_values))
        ),
    }


def _distortion(active: Sequence[Mapping[str, object]]) -> dict[str, object]:
    add_rates: list[float] = []
    loss_rates: list[float] = []
    inaccurate = 0
    coverage_rows = 0
    for row in active:
        if (_int(row, "mutation_generation") or 0) < 1:
            continue
        add = _float(row, "token_add_rate")
        loss = _float(row, "token_loss_rate")
        if add is not None:
            add_rates.append(add)
        if loss is not None:
            loss_rates.append(loss)
        covers = row.get("covers_source")
        if covers is None:
            continue
        coverage_rows += 1
        if covers is False:
            inaccurate += 1
    return {
        "token_add_rate": (
            _ABSENT
            if not add_rates
            else quantize_float(sum(add_rates) / len(add_rates))
        ),
        "token_loss_rate": (
            _ABSENT
            if not loss_rates
            else quantize_float(sum(loss_rates) / len(loss_rates))
        ),
        "inaccuracy_vs_objective": (
            _ABSENT
            if coverage_rows == 0
            else quantize_float(inaccurate / coverage_rows)
        ),
    }


def _source_loss(
    history: Sequence[Mapping[str, object]],
    active: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    drop = 0
    lineage_count = 0
    origin_shift = 0
    child_count = 0
    orphan = 0
    for row in active:
        lineage_count += 1
        has_source = bool(row.get("has_source_event"))
        # earliest ancestor had source but live does not
        founding_had = bool(row.get("founding_had_source_event", has_source))
        if founding_had and not has_source:
            drop += 1
        if (_int(row, "mutation_generation") or 0) >= 1:
            child_count += 1
            if _text(row, "origin") != _text(row, "founding_origin"):
                origin_shift += 1
        if (
            _text(row, "origin") == "retold_story"
            and not row.get("has_source_event")
            and not row.get("has_source_memory")
        ):
            orphan += 1
    return {
        "source_event_drop_rate": (
            _ABSENT if lineage_count == 0 else quantize_float(drop / lineage_count)
        ),
        "origin_shift_rate": (
            _ABSENT if child_count == 0 else quantize_float(origin_shift / child_count)
        ),
        "orphan_retell_rate": (
            _ABSENT if lineage_count == 0 else quantize_float(orphan / lineage_count)
        ),
    }


def _convergence(
    history: Sequence[Mapping[str, object]],
    active: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    merged_parents = [
        row for row in history if _text(row, "status") == "merged"
    ]
    ever_active = {
        _text(row, "variant_id")
        for row in history
        if _text(row, "status") in {"active", "merged"}
        and _text(row, "variant_id") is not None
    }
    merge_rate: object = _ABSENT
    if ever_active:
        merge_rate = quantize_float(len(merged_parents) / len(ever_active))
    parent_arities = [
        float(_int(row, "parent_count") or 0)
        for row in history
        if (_int(row, "parent_count") or 0) >= 2
        and _text(row, "status") == "active"
    ]
    competing = [
        row
        for row in active
        if (_int(row, "competing_count") or 0) >= 1
    ]
    return {
        "merge_rate": merge_rate,
        "mean_parents_per_merge": (
            _ABSENT
            if not parent_arities
            else quantize_float(sum(parent_arities) / len(parent_arities))
        ),
        "competing_variant_share": (
            _ABSENT if not active else quantize_float(len(competing) / len(active))
        ),
    }


def _geographic_social_spread(
    active: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    locations = [_float(row, "location_count") for row in active]
    locations = [value for value in locations if value is not None]
    carriers = [_float(row, "carrier_count") for row in active]
    carriers = [value for value in carriers if value is not None]
    multi = sum(1 for row in active if (_int(row, "location_count") or 0) >= 2)
    social = sum(1 for row in active if (_int(row, "carrier_count") or 0) >= 3)
    return {
        "mean_location_span": (
            _ABSENT
            if not locations
            else quantize_float(sum(locations) / len(locations))
        ),
        "mean_carrier_span": (
            _ABSENT if not carriers else quantize_float(sum(carriers) / len(carriers))
        ),
        "multi_location_rate": (
            _ABSENT if not active else quantize_float(multi / len(active))
        ),
        "social_reach_rate": (
            _ABSENT if not active else quantize_float(social / len(active))
        ),
    }


def _variant_rows(rows: object | None) -> list[Mapping[str, object]]:
    if rows is None:
        return []
    if isinstance(rows, Mapping):
        return [rows]
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        return []
    out: list[Mapping[str, object]] = []
    for item in rows:
        if isinstance(item, Mapping):
            out.append(item)
            continue
        # duck-type
        keys = (
            "tick",
            "owner_id",
            "variant_id",
            "fingerprint",
            "status",
            "strength",
            "origin",
            "repetition_count",
            "mutation_generation",
            "has_source_event",
            "location_count",
            "carrier_count",
        )
        mapped = {key: getattr(item, key, None) for key in keys}
        out.append(mapped)
    return out


def _text(row: Mapping[str, object], key: str) -> str | None:
    value = row.get(key)
    return value if isinstance(value, str) and value else None


def _int(row: Mapping[str, object], key: str) -> int | None:
    value = row.get(key)
    if isinstance(value, bool) or type(value) is not int:
        return None
    return value


def _float(row: Mapping[str, object], key: str) -> float | None:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


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
    spec = metric_specification(MetricFamilyId.CULTURAL_NARRATIVE_LINEAGE)
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
            source_kind="cultural_narrative_lineage",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )
