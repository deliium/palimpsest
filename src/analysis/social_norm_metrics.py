"""Repeated behavior and private norm belief, counted apart.

Analysis-only. This module does not import agent cognition or runtimes.
Callers supply detached rows. The result never re-enters a ledger.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from itertools import pairwise
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
    "EMERGENT_SOCIAL_NORMS_METRIC_VERSION",
    "compute_emergent_social_norms",
    "compute_norm_persistence",
]

EMERGENT_SOCIAL_NORMS_METRIC_VERSION: Final[str] = "emergent_social_norms@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.social_norm_metrics")
_RETURN_WINDOW: Final[int] = 8
_SCARCITY: Final[float] = 1.0
_ACTIVE_RATE: Final[float] = 0.50
_BELIEF_FLOOR: Final[float] = 0.40
_ABSENT: Final[str] = MetricAvailability.ABSENT.value


def compute_emergent_social_norms(
    rows: object | None,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Build repeated-behavior and norm-belief readings from caller rows."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    behavior = _behavior_rows(rows)
    beliefs = _belief_rows(rows)
    if not behavior and not beliefs:
        _LOG.warning("social_norms_metric_empty tick=%s reason=no_rows", tick)
        return _document(
            run_id=run_id,
            input_revision=input_revision,
            availability=MetricAvailability.ABSENT,
            values={},
            notes_code="empty_rows",
        )
    rates = {
        "return_transfer": _return_rate(behavior),
        "share_under_scarcity": _share_rate(behavior),
        "spare_after_sleep": _spare_rate(behavior),
        "reciprocal_exchange": _reciprocal_rate(behavior),
    }
    active = [
        row
        for row in beliefs
        if _text(row, "status") == "active"
    ]
    values: dict[str, object] = {
        "return_transfer_rate": _rate_value(rates["return_transfer"]),
        "share_under_scarcity_rate": _rate_value(rates["share_under_scarcity"]),
        "spare_after_sleep_rate": _rate_value(rates["spare_after_sleep"]),
        "reciprocal_exchange_rate": _rate_value(rates["reciprocal_exchange"]),
        "active_belief_count": len(active),
        "mean_confidence": _mean_confidence(active),
        "repetition_without_belief": _repetition_without_belief(rates, active),
        "belief_without_repetition": _belief_without_repetition(rates, active),
    }
    pattern_count = sum(
        1 for rate in rates.values() if rate is not None and rate >= _ACTIVE_RATE
    )
    _LOG.debug(
        "social_norms_metric_computed tick=%s pattern_count=%s active_belief_count=%s",
        tick,
        pattern_count,
        len(active),
    )
    return _document(
        run_id=run_id,
        input_revision=input_revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        notes_code="caller_rows",
        observed=len(behavior) + len(beliefs),
        expected=len(behavior) + len(beliefs),
    )


def compute_norm_persistence(
    history: object,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Fraction of adjacent readings that stay regular or stay believed."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    documents = _history(history)
    if len(documents) < 2:
        _LOG.warning("social_norms_metric_empty tick=%s reason=no_history", tick)
        return _document(
            run_id=run_id,
            input_revision=input_revision,
            availability=MetricAvailability.ABSENT,
            values={
                "behavior_persistence": _ABSENT,
                "belief_persistence": _ABSENT,
            },
            notes_code="empty_history",
        )
    behavior_hits = 0
    belief_hits = 0
    pairs = 0
    for left, right in pairwise(documents):
        pairs += 1
        if _behavior_stays(left, right):
            behavior_hits += 1
        if _belief_stays(left, right):
            belief_hits += 1
    values = {
        "behavior_persistence": quantize_float(behavior_hits / pairs),
        "belief_persistence": quantize_float(belief_hits / pairs),
    }
    _LOG.debug(
        "norm_persistence_built tick=%s pair_count=%s",
        tick,
        pairs,
    )
    return _document(
        run_id=run_id,
        input_revision=input_revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        notes_code="adjacent_ticks",
        observed=pairs,
        expected=pairs,
    )


def _behavior_rows(rows: object | None) -> tuple[object, ...]:
    if rows is None:
        return ()
    if isinstance(rows, Mapping):
        return _as_rows(rows.get("behavior_rows", rows.get("objective_rows", ())))
    return _as_rows(rows)


def _belief_rows(rows: object | None) -> tuple[object, ...]:
    if isinstance(rows, Mapping):
        return _as_rows(rows.get("belief_rows", ()))
    return ()


def _history(history: object) -> tuple[object, ...]:
    if history is None:
        return ()
    if isinstance(history, (str, bytes)) or not isinstance(history, Sequence):
        return ()
    return tuple(history)


def _as_rows(value: object) -> tuple[object, ...]:
    if value is None or isinstance(value, (str, bytes)):
        return ()
    if not isinstance(value, Sequence):
        return ()
    return tuple(value)


def _cell(row: object, name: str) -> object:
    if isinstance(row, Mapping):
        value = row.get(name)
    else:
        value = getattr(row, name, None)
    nested = getattr(value, "value", None)
    if isinstance(nested, str) and type(value) is not str:
        return nested
    return value


def _text(row: object, name: str) -> str | None:
    value = _cell(row, name)
    if isinstance(value, str) and value:
        return value
    return None


def _number(row: object, name: str) -> float | None:
    value = _cell(row, name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _return_rate(rows: Sequence[object]) -> float | None:
    gives = [row for row in rows if _text(row, "kind") == "give"]
    opened = 0
    returned = 0
    pending: dict[tuple[str, str], int] = {}
    ordered = sorted(gives, key=lambda row: int(_number(row, "tick") or 0))
    last_tick = 0
    for row in ordered:
        tick = int(_number(row, "tick") or 0)
        last_tick = max(last_tick, tick)
        if _cell(row, "success") is False:
            continue
        actor = _text(row, "actor_id")
        other = _text(row, "other_id")
        if actor is None or other is None:
            continue
        opposite = (other, actor)
        window = pending.get(opposite)
        if window is not None and tick <= window:
            returned += 1
            opened += 1
            del pending[opposite]
            continue
        pending[(actor, other)] = tick + _RETURN_WINDOW
    for until in pending.values():
        if last_tick >= until:
            opened += 1
    if opened == 0:
        return None
    return returned / opened


def _share_rate(rows: Sequence[object]) -> float | None:
    scarce_ticks: set[int] = set()
    give_ticks: set[int] = set()
    for row in rows:
        quantity = _number(row, "food_quantity")
        tick = _number(row, "tick")
        if quantity is None or tick is None or quantity > _SCARCITY:
            continue
        scarce_ticks.add(int(tick))
        if _text(row, "kind") == "give" and _cell(row, "success") is not False:
            give_ticks.add(int(tick))
    if not scarce_ticks:
        return None
    return len(give_ticks & scarce_ticks) / len(scarce_ticks)


def _spare_rate(rows: Sequence[object]) -> float | None:
    sleeps = [row for row in rows if _text(row, "kind") == "sleep"]
    if not sleeps:
        return None
    spared = 0
    for sleep in sleeps:
        tick = _number(sleep, "tick")
        actor = _text(sleep, "actor_id")
        attacked = False
        for row in rows:
            if _text(row, "kind") != "attack" or _number(row, "tick") != tick:
                continue
            if _text(row, "other_id") == actor:
                attacked = True
                break
        if not attacked:
            spared += 1
    return spared / len(sleeps)


def _reciprocal_rate(rows: Sequence[object]) -> float | None:
    gives = [
        row
        for row in rows
        if _text(row, "kind") == "give" and _cell(row, "success") is not False
    ]
    ordered = sorted(gives, key=lambda row: int(_number(row, "tick") or 0))
    seen: dict[tuple[str, str], set[str]] = {}
    later = 0
    opportunities = 0
    for row in ordered:
        actor = _text(row, "actor_id")
        other = _text(row, "other_id")
        if actor is None or other is None or actor == other:
            continue
        key = tuple(sorted((actor, other)))
        directions = seen.setdefault(key, set())
        if actor in directions and other in directions:
            later += 1
            opportunities += 1
        directions.add(actor)
    if opportunities == 0:
        return None
    return later / opportunities


def _rate_value(rate: float | None) -> object:
    if rate is None:
        return _ABSENT
    return quantize_float(rate)


def _mean_confidence(active: Sequence[object]) -> object:
    scores = [
        score
        for row in active
        if (score := _number(row, "confidence")) is not None
    ]
    if not scores:
        return _ABSENT
    return quantize_float(sum(scores) / len(scores))


def _repetition_without_belief(
    rates: Mapping[str, float | None], active: Sequence[object]
) -> str:
    held = {_text(row, "pattern") for row in active}
    names = [
        pattern
        for pattern, rate in rates.items()
        if rate is not None and rate >= _ACTIVE_RATE and pattern not in held
    ]
    return ",".join(sorted(names))


def _belief_without_repetition(
    rates: Mapping[str, float | None], active: Sequence[object]
) -> str:
    names: set[str] = set()
    for row in active:
        pattern = _text(row, "pattern")
        if pattern is None:
            continue
        rate = rates.get(pattern)
        if rate is None or rate < _ACTIVE_RATE:
            names.add(pattern)
    return ",".join(sorted(names))


def _behavior_stays(left: object, right: object) -> bool:
    shared = set(_rates(left)) & set(_rates(right))
    for pattern in shared:
        first = _rates(left)[pattern]
        second = _rates(right)[pattern]
        if (
            isinstance(first, (int, float))
            and isinstance(second, (int, float))
            and float(first) >= _ACTIVE_RATE
            and float(second) >= _ACTIVE_RATE
        ):
            return True
    return False


def _belief_stays(left: object, right: object) -> bool:
    return bool(_active_keys(left) & _active_keys(right))


def _rates(document: object) -> dict[str, object]:
    if isinstance(document, Mapping):
        raw = document.get("rates", {})
    else:
        raw = getattr(document, "rates", {})
    if not isinstance(raw, Mapping):
        return {}
    return dict(raw)


def _active_keys(document: object) -> set[tuple[str, str]]:
    if isinstance(document, Mapping):
        raw = document.get("beliefs", ())
    else:
        raw = getattr(document, "beliefs", ())
    keys: set[tuple[str, str]] = set()
    for row in _as_rows(raw):
        if _text(row, "status") != "active":
            continue
        confidence = _number(row, "confidence")
        owner = _text(row, "owner_id")
        pattern = _text(row, "pattern")
        if (
            confidence is None
            or confidence < _BELIEF_FLOOR
            or owner is None
            or pattern is None
        ):
            continue
        keys.add((owner, pattern))
    return keys


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
    spec = metric_specification(MetricFamilyId.EMERGENT_SOCIAL_NORMS)
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
            source_kind="emergent_social_norms",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )
