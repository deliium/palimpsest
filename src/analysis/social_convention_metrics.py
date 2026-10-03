"""Objective repetition and private habit belief, counted apart.

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
    "PERSISTENT_SOCIAL_CONVENTIONS_METRIC_VERSION",
    "compute_convention_persistence",
    "compute_persistent_social_conventions",
]

PERSISTENT_SOCIAL_CONVENTIONS_METRIC_VERSION: Final[str] = (
    "persistent_social_conventions@1"
)
_LOG: Final[logging.Logger] = logging.getLogger("analysis.social_convention_metrics")
_EXCHANGE_WINDOW: Final[int] = 8
_ACTIVE_RATE: Final[float] = 0.50
_HABIT_FLOOR: Final[float] = 0.40
_RITUAL_DURATION: Final[int] = 8
_ABSENT: Final[str] = MetricAvailability.ABSENT.value
_MEETING_KINDS: Final[frozenset[str]] = frozenset({"wait", "talk"})
_SITUATIONS: Final[tuple[str, ...]] = (
    "colocated_meeting",
    "timed_gathering",
    "greeting_exchange",
    "habitual_exchange",
    "collective_action",
)


def compute_persistent_social_conventions(
    rows: object | None,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
    history: object | None = None,
) -> MetricDocument:
    """Build objective, habit, and divergence readings from caller rows."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    objective = _objective_rows(rows)
    habits = _habit_rows(rows)
    if not objective and not habits:
        _LOG.warning("social_conventions_metric_empty tick=%s reason=no_rows", tick)
        return _document(
            run_id=run_id,
            input_revision=input_revision,
            availability=MetricAvailability.ABSENT,
            values={},
            notes_code="empty_rows",
        )
    rates = {
        "colocated_meeting": _recurrent_meeting_rate(objective),
        "timed_gathering": _timed_gathering_rate(objective),
        "habitual_exchange": _habitual_exchange_rate(objective),
        "collective_action": _collective_action_rate(objective),
        "greeting_exchange": None,
    }
    active = [row for row in habits if _text(row, "status") == "active"]
    values: dict[str, object] = {
        "recurrent_meeting_rate": _rate_value(rates["colocated_meeting"]),
        "timed_gathering_rate": _rate_value(rates["timed_gathering"]),
        "habitual_exchange_rate": _rate_value(rates["habitual_exchange"]),
        "collective_action_rate": _rate_value(rates["collective_action"]),
        "active_habit_count": len(active),
        "mean_habit_strength": _mean_number(active, "strength"),
        "mean_duration_ticks": _mean_number(active, "duration_ticks"),
        "mean_participant_count": _mean_number(active, "participant_count"),
        "transmission_adoption_rate": _active_fraction(
            active,
            lambda row: _text(row, "transmission") in {"communicated", "both"},
        ),
        "forgotten_reason_rate": _active_fraction(
            active, lambda row: _text(row, "explanation") == "forgotten"
        ),
        "competing_variant_share": _active_fraction(
            active,
            lambda row: (_number(row, "variant_count") or 0.0) >= 1.0,
        ),
        "named_custom_rate": _active_fraction(
            active, lambda row: _text(row, "conceptualization") == "named_custom"
        ),
        "repetition_without_habit": _repetition_without_habit(rates, active),
        "habit_without_repetition": _habit_without_repetition(rates, active),
        "reason_loss_persistence": _reason_loss_persistence(history, active),
        "ritual_like_persistence": _ritual_like_persistence(history, active),
    }
    _LOG.debug(
        "social_conventions_metric_computed tick=%s situation_count=%s "
        "active_habit_count=%s",
        tick,
        sum(1 for rate in rates.values() if rate is not None and rate >= _ACTIVE_RATE),
        len(active),
    )
    return _document(
        run_id=run_id,
        input_revision=input_revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        notes_code="caller_rows",
        observed=len(objective) + len(habits),
        expected=len(objective) + len(habits),
    )


def compute_convention_persistence(
    history: object,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Fraction of adjacent readings that stay regular or stay habitual."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    documents = _history(history)
    if len(documents) < 2:
        _LOG.warning("social_conventions_metric_empty tick=%s reason=no_history", tick)
        return _document(
            run_id=run_id,
            input_revision=input_revision,
            availability=MetricAvailability.ABSENT,
            values={
                "behavior_persistence": _ABSENT,
                "habit_persistence": _ABSENT,
            },
            notes_code="empty_history",
        )
    behavior_hits = 0
    habit_hits = 0
    pairs = 0
    for left, right in pairwise(documents):
        pairs += 1
        if _behavior_stays(left, right):
            behavior_hits += 1
        if _habit_stays(left, right):
            habit_hits += 1
    values = {
        "behavior_persistence": quantize_float(behavior_hits / pairs),
        "habit_persistence": quantize_float(habit_hits / pairs),
    }
    _LOG.debug(
        "convention_persistence_built tick=%s pair_count=%s",
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


def _objective_rows(rows: object | None) -> tuple[object, ...]:
    if rows is None:
        return ()
    if isinstance(rows, Mapping):
        return _as_rows(rows.get("objective_rows", rows.get("behavior_rows", ())))
    return _as_rows(rows)


def _habit_rows(rows: object | None) -> tuple[object, ...]:
    if isinstance(rows, Mapping):
        return _as_rows(rows.get("habit_rows", rows.get("belief_rows", ())))
    return ()


def _history(history: object | None) -> tuple[object, ...]:
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


def _rate_value(rate: float | None) -> object:
    if rate is None:
        return _ABSENT
    return quantize_float(rate)


def _mean_number(active: Sequence[object], name: str) -> object:
    scores = [
        score for row in active if (score := _number(row, name)) is not None
    ]
    if not scores:
        return _ABSENT
    return quantize_float(sum(scores) / len(scores))


def _active_fraction(active: Sequence[object], predicate: object) -> object:
    if not active:
        return _ABSENT
    hits = sum(1 for row in active if predicate(row))  # type: ignore[operator]
    return quantize_float(hits / len(active))


def _groups_by_tick_location(
    rows: Sequence[object],
) -> dict[tuple[int, str], list[object]]:
    groups: dict[tuple[int, str], list[object]] = {}
    for row in rows:
        tick = _number(row, "tick")
        location = _text(row, "location_id")
        actor = _text(row, "actor_id")
        if tick is None or location is None or actor is None:
            continue
        groups.setdefault((int(tick), location), []).append(row)
    return groups


def _multi_agent_colocated(
    groups: Mapping[tuple[int, str], list[object]],
) -> list[tuple[tuple[int, str], list[object]]]:
    return [
        (key, members)
        for key, members in groups.items()
        if len({_text(row, "actor_id") for row in members}) >= 2
    ]


def _recurrent_meeting_rate(rows: Sequence[object]) -> float | None:
    groups = _groups_by_tick_location(rows)
    colocated = _multi_agent_colocated(groups)
    if not colocated:
        return None
    meetings = 0
    for _key, members in colocated:
        if any(_text(row, "kind") in _MEETING_KINDS for row in members):
            meetings += 1
    return meetings / len(colocated)


def _timed_gathering_rate(rows: Sequence[object]) -> float | None:
    groups = _groups_by_tick_location(rows)
    colocated = _multi_agent_colocated(groups)
    if not colocated:
        return None
    phase_ticks: dict[str, set[int]] = {}
    meeting_ticks = 0
    for (tick, _location), members in colocated:
        phases = {
            _text(row, "day_phase")
            for row in members
            if _text(row, "day_phase") is not None
        }
        if len(phases) != 1:
            continue
        phase = next(iter(phases))
        if phase is None:
            continue
        if any(_text(row, "kind") in _MEETING_KINDS for row in members):
            meeting_ticks += 1
            phase_ticks.setdefault(phase, set()).add(tick)
    if not any(len(ticks) >= 3 for ticks in phase_ticks.values()):
        return None
    return meeting_ticks / len(colocated)


def _habitual_exchange_rate(rows: Sequence[object]) -> float | None:
    gives = [row for row in rows if _text(row, "kind") == "give"]
    opened = 0
    repeated = 0
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
        key = tuple(sorted((actor, other)))
        until = pending.get(key)  # type: ignore[arg-type]
        if until is not None and tick <= until:
            repeated += 1
            opened += 1
            del pending[key]  # type: ignore[arg-type]
            continue
        pending[key] = tick + _EXCHANGE_WINDOW  # type: ignore[index]
    for until in pending.values():
        if last_tick >= until:
            opened += 1
    if opened == 0:
        return None
    return repeated / opened


def _collective_action_rate(rows: Sequence[object]) -> float | None:
    groups = _groups_by_tick_location(rows)
    colocated = _multi_agent_colocated(groups)
    if not colocated:
        return None
    collective = 0
    for _key, members in colocated:
        by_kind: dict[str, set[str]] = {}
        for row in members:
            kind = _text(row, "kind")
            actor = _text(row, "actor_id")
            if kind is None or actor is None:
                continue
            by_kind.setdefault(kind, set()).add(actor)
        if any(len(actors) >= 2 for actors in by_kind.values()):
            collective += 1
    return collective / len(colocated)


def _repetition_without_habit(
    rates: Mapping[str, float | None], active: Sequence[object]
) -> str:
    held = {_text(row, "situation") for row in active}
    names = [
        situation
        for situation, rate in rates.items()
        if rate is not None and rate >= _ACTIVE_RATE and situation not in held
    ]
    return ",".join(sorted(names))


def _habit_without_repetition(
    rates: Mapping[str, float | None], active: Sequence[object]
) -> str:
    names: set[str] = set()
    for row in active:
        situation = _text(row, "situation")
        if situation is None:
            continue
        rate = rates.get(situation)
        if rate is None or rate < _ACTIVE_RATE:
            names.add(situation)
    return ",".join(sorted(names))


def _reason_loss_persistence(
    history: object | None, active: Sequence[object]
) -> object:
    documents = _history(history)
    if len(documents) >= 2:
        hits = 0
        pairs = 0
        for left, right in pairwise(documents):
            pairs += 1
            if _forgotten_active(left) and _forgotten_active(right):
                hits += 1
        if pairs == 0:
            return _ABSENT
        return quantize_float(hits / pairs)
    if not active:
        return _ABSENT
    hits = sum(
        1
        for row in active
        if _text(row, "explanation") == "forgotten"
        and (_number(row, "strength") or 0.0) >= _HABIT_FLOOR
    )
    return quantize_float(hits / len(active))


def _ritual_like_persistence(
    history: object | None, active: Sequence[object]
) -> object:
    documents = _history(history)
    if len(documents) >= 1:
        hits = 0
        for document in documents:
            if _ritual_rows(document):
                hits += 1
        return quantize_float(hits / len(documents))
    if not active:
        return _ABSENT
    hits = sum(1 for row in active if _is_ritual_row(row))
    return quantize_float(hits / len(active))


def _forgotten_active(document: object) -> bool:
    for row in _document_habits(document):
        if (
            _text(row, "status") == "active"
            and _text(row, "explanation") == "forgotten"
            and (_number(row, "strength") or 0.0) >= _HABIT_FLOOR
        ):
            return True
    return False


def _ritual_rows(document: object) -> bool:
    return any(_is_ritual_row(row) for row in _document_habits(document))


def _is_ritual_row(row: object) -> bool:
    if _text(row, "status") != "active":
        return False
    explanation = _text(row, "explanation")
    if explanation not in {"forgotten", "unknown"}:
        return False
    duration = _number(row, "duration_ticks")
    participants = _number(row, "participant_count")
    strength = _number(row, "strength")
    return (
        duration is not None
        and duration >= _RITUAL_DURATION
        and participants is not None
        and participants >= 2
        and strength is not None
        and strength >= _HABIT_FLOOR
    )


def _document_habits(document: object) -> tuple[object, ...]:
    if isinstance(document, Mapping):
        return _as_rows(document.get("habits", document.get("habit_rows", ())))
    return _as_rows(getattr(document, "habits", ()))


def _behavior_stays(left: object, right: object) -> bool:
    shared = set(_rates(left)) & set(_rates(right))
    for situation in shared:
        first = _rates(left)[situation]
        second = _rates(right)[situation]
        if (
            isinstance(first, (int, float))
            and isinstance(second, (int, float))
            and float(first) >= _ACTIVE_RATE
            and float(second) >= _ACTIVE_RATE
        ):
            return True
    return False


def _habit_stays(left: object, right: object) -> bool:
    return bool(_active_keys(left) & _active_keys(right))


def _rates(document: object) -> dict[str, object]:
    if isinstance(document, Mapping):
        raw = document.get("rates", {})
    else:
        raw = getattr(document, "rates", {})
    if not isinstance(raw, Mapping):
        return {}
    return dict(raw)


def _active_keys(document: object) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for row in _document_habits(document):
        if _text(row, "status") != "active":
            continue
        strength = _number(row, "strength")
        owner = _text(row, "owner_id")
        situation = _text(row, "situation")
        action = _text(row, "usual_action")
        if (
            strength is None
            or strength < _HABIT_FLOOR
            or owner is None
            or situation is None
            or action is None
        ):
            continue
        keys.add((owner, situation, action))
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
    spec = metric_specification(MetricFamilyId.PERSISTENT_SOCIAL_CONVENTIONS)
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
            source_kind="persistent_social_conventions",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )


_ = _SITUATIONS
