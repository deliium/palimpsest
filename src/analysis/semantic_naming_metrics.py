"""Vocabulary convergence and semantic drift from detached naming rows.

Analysis-only. This module does not import agent cognition or runtimes.
Callers supply detached rows. The result never re-enters a ledger.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from itertools import combinations, pairwise
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
    "EMERGENT_SEMANTIC_NAMING_METRIC_VERSION",
    "compute_emergent_semantic_naming",
    "compute_naming_persistence",
]

EMERGENT_SEMANTIC_NAMING_METRIC_VERSION: Final[str] = "emergent_semantic_naming@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.semantic_naming_metrics")
_ABSENT: Final[str] = MetricAvailability.ABSENT.value
_ACTIVE_STRENGTH: Final[float] = 0.40


def compute_emergent_semantic_naming(
    rows: object | None,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Build vocabulary convergence and semantic drift from caller rows."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    bindings = _binding_rows(rows)
    if not bindings:
        _LOG.warning("semantic_naming_metric_empty reason=%s", "no_rows")
        return _document(
            run_id=run_id,
            input_revision=input_revision,
            availability=MetricAvailability.ABSENT,
            values={},
            notes_code="empty_rows",
        )
    active = [row for row in bindings if _text(row, "status") == "active"]
    values: dict[str, object] = {
        **_vocabulary_convergence(bindings, active),
        **_semantic_drift(bindings, active),
    }
    entities = {
        candidate
        for row in active
        if (candidate := _text(row, "top_candidate_id")) is not None
    }
    _LOG.debug(
        "semantic_naming_metric_computed entity_count=%s active_binding_count=%s",
        len(entities),
        len(active),
    )
    return _document(
        run_id=run_id,
        input_revision=input_revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        notes_code="caller_rows",
        observed=len(bindings),
        expected=len(bindings),
    )


def compute_naming_persistence(
    history: object,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Persistence of preferred labels and sense revisions across documents."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    documents = _history(history)
    if len(documents) < 2:
        _LOG.warning("semantic_naming_metric_empty reason=%s", "no_history")
        return _document(
            run_id=run_id,
            input_revision=input_revision,
            availability=MetricAvailability.ABSENT,
            values={
                "label_persistence": _ABSENT,
                "sense_stability": _ABSENT,
            },
            notes_code="empty_history",
        )
    label_hits = 0
    sense_hits = 0
    pairs = 0
    for left, right in pairwise(documents):
        pairs += 1
        left_keys = _persistent_keys(left)
        right_keys = _persistent_keys(right)
        if left_keys & right_keys:
            label_hits += 1
        if _sense_stable(left, right):
            sense_hits += 1
    values = {
        "label_persistence": quantize_float(label_hits / pairs),
        "sense_stability": quantize_float(sense_hits / pairs),
    }
    return _document(
        run_id=run_id,
        input_revision=input_revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        notes_code="adjacent_ticks",
        observed=pairs,
        expected=pairs,
    )


def _vocabulary_convergence(
    bindings: Sequence[object], active: Sequence[object]
) -> dict[str, object]:
    by_entity: dict[str, list[object]] = defaultdict(list)
    by_label: dict[str, set[str]] = defaultdict(set)
    owners: set[str] = set()
    active_owners: set[str] = set()
    for row in bindings:
        owner = _text(row, "owner_id")
        if owner is not None:
            owners.add(owner)
    for row in active:
        owner = _text(row, "owner_id")
        token = _text(row, "label_token")
        candidate = _text(row, "top_candidate_id")
        if owner is not None:
            active_owners.add(owner)
        if candidate is None or token is None:
            continue
        by_entity[candidate].append(row)
        if owner is not None:
            by_label[token].add(owner)
    shared = 0
    label_counts: list[int] = []
    for _entity, rows in by_entity.items():
        tokens_by_owner: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            owner = _text(row, "owner_id")
            token = _text(row, "label_token")
            if owner is None or token is None:
                continue
            tokens_by_owner[owner].add(token)
        distinct_tokens = {
            token for tokens in tokens_by_owner.values() for token in tokens
        }
        label_counts.append(len(distinct_tokens))
        token_owners: dict[str, set[str]] = defaultdict(set)
        for owner, tokens in tokens_by_owner.items():
            for token in tokens:
                token_owners[token].add(owner)
        if any(len(owners_for_token) >= 2 for owners_for_token in token_owners.values()):
            shared += 1
    preferred = _preferred_by_entity(active)
    agreement_hits = 0
    agreement_pairs = 0
    for _entity, owner_labels in preferred.items():
        owners_list = sorted(owner_labels)
        for left, right in combinations(owners_list, 2):
            agreement_pairs += 1
            if owner_labels[left] == owner_labels[right]:
                agreement_hits += 1
    owner_count = len(owners)
    empty_lexicon = (
        _ABSENT
        if owner_count == 0
        else quantize_float((owner_count - len(active_owners)) / owner_count)
    )
    return {
        "shared_label_rate": (
            _ABSENT if not by_entity else quantize_float(shared / len(by_entity))
        ),
        "mean_labels_per_entity": (
            _ABSENT
            if not label_counts
            else quantize_float(sum(label_counts) / len(label_counts))
        ),
        "mean_owners_per_label": (
            _ABSENT
            if not by_label
            else quantize_float(
                sum(len(owners_for) for owners_for in by_label.values()) / len(by_label)
            )
        ),
        "preferred_label_agreement": (
            _ABSENT
            if agreement_pairs == 0
            else quantize_float(agreement_hits / agreement_pairs)
        ),
        "empty_lexicon_owner_rate": empty_lexicon,
    }


def _semantic_drift(
    bindings: Sequence[object], active: Sequence[object]
) -> dict[str, object]:
    revisions = [_number(row, "sense_revision") for row in active]
    revisions = [value for value in revisions if value is not None]
    retired = [row for row in bindings if _text(row, "status") == "retired"]
    merged = [
        row
        for row in retired
        if _text(row, "merged_into") is not None
    ]
    competing = [
        row
        for row in active
        if _sequence(row, "competing_label_ids")
    ]
    shifted = [
        row
        for row in active
        if (_number(row, "sense_revision") or 0.0) >= 1.0
    ]
    ticks = sorted(
        {
            int(tick)
            for row in bindings
            if (tick := _number(row, "tick")) is not None
        }
    )
    turnover = _label_turnover_rate(bindings, ticks)
    extinction = _extinction_rate(bindings, ticks)
    pool = len(active) + len(retired)
    return {
        "mean_sense_revision": (
            _ABSENT
            if not revisions
            else quantize_float(sum(revisions) / len(revisions))
        ),
        "label_turnover_rate": turnover,
        "meaning_shift_rate": (
            _ABSENT if not active else quantize_float(len(shifted) / len(active))
        ),
        "merge_rate": (
            _ABSENT if pool == 0 else quantize_float(len(merged) / pool)
        ),
        "competition_rate": (
            _ABSENT if not active else quantize_float(len(competing) / len(active))
        ),
        "extinction_rate": extinction,
    }


def _preferred_by_entity(
    active: Sequence[object],
) -> dict[str, dict[str, str]]:
    preferred: dict[str, dict[str, tuple[float, str]]] = defaultdict(dict)
    for row in active:
        owner = _text(row, "owner_id")
        token = _text(row, "label_token")
        candidate = _text(row, "top_candidate_id")
        strength = _number(row, "strength")
        if owner is None or token is None or candidate is None or strength is None:
            continue
        current = preferred[candidate].get(owner)
        if current is None or strength > current[0]:
            preferred[candidate][owner] = (strength, token)
    return {
        entity: {owner: token for owner, (_strength, token) in owners.items()}
        for entity, owners in preferred.items()
    }


def _label_turnover_rate(
    bindings: Sequence[object], ticks: Sequence[int]
) -> object:
    if len(ticks) < 2:
        return _ABSENT
    by_tick: dict[int, list[object]] = defaultdict(list)
    for row in bindings:
        tick = _number(row, "tick")
        if tick is None:
            continue
        by_tick[int(tick)].append(row)
    changes = 0
    windows = 0
    for left_tick, right_tick in pairwise(ticks):
        left_pref = _preferred_by_entity(
            [row for row in by_tick[left_tick] if _text(row, "status") == "active"]
        )
        right_pref = _preferred_by_entity(
            [row for row in by_tick[right_tick] if _text(row, "status") == "active"]
        )
        entities = set(left_pref) | set(right_pref)
        for entity in entities:
            left_owners = left_pref.get(entity, {})
            right_owners = right_pref.get(entity, {})
            for owner in set(left_owners) | set(right_owners):
                windows += 1
                if left_owners.get(owner) != right_owners.get(owner):
                    changes += 1
    if windows == 0:
        return _ABSENT
    return quantize_float(changes / windows)


def _extinction_rate(bindings: Sequence[object], ticks: Sequence[int]) -> object:
    if len(ticks) < 2:
        return _ABSENT
    start = ticks[0]
    end = ticks[-1]
    start_active = {
        _identity(row)
        for row in bindings
        if _number(row, "tick") == float(start) and _text(row, "status") == "active"
        and _identity(row) is not None
    }
    end_retired = {
        _identity(row)
        for row in bindings
        if _number(row, "tick") == float(end) and _text(row, "status") == "retired"
        and _identity(row) is not None
    }
    if not start_active:
        return _ABSENT
    extinct = len(start_active & end_retired)
    return quantize_float(extinct / len(start_active))


def _persistent_keys(document: object) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for row in _document_bindings(document):
        if _text(row, "status") != "active":
            continue
        strength = _number(row, "strength")
        owner = _text(row, "owner_id")
        token = _text(row, "label_token")
        candidate = _text(row, "top_candidate_id")
        if (
            strength is None
            or strength < _ACTIVE_STRENGTH
            or owner is None
            or token is None
            or candidate is None
        ):
            continue
        keys.add((owner, token, candidate))
    return keys


def _sense_stable(left: object, right: object) -> bool:
    left_map = {
        _identity(row): _number(row, "sense_revision")
        for row in _document_bindings(left)
        if _text(row, "status") == "active" and _identity(row) is not None
    }
    right_map = {
        _identity(row): _number(row, "sense_revision")
        for row in _document_bindings(right)
        if _text(row, "status") == "active" and _identity(row) is not None
    }
    shared = set(left_map) & set(right_map)
    if not shared:
        return False
    return all(left_map[key] == right_map[key] for key in shared)


def _identity(row: object) -> tuple[str, str, str] | None:
    owner = _text(row, "owner_id")
    token = _text(row, "label_token")
    candidate = _text(row, "top_candidate_id")
    if owner is None or token is None or candidate is None:
        return None
    return (owner, token, candidate)


def _binding_rows(rows: object | None) -> tuple[object, ...]:
    if rows is None:
        return ()
    if isinstance(rows, Mapping):
        return _as_rows(rows.get("binding_rows", rows.get("rows", ())))
    return _as_rows(rows)


def _document_bindings(document: object) -> tuple[object, ...]:
    if isinstance(document, Mapping):
        return _as_rows(
            document.get("bindings", document.get("binding_rows", document.get("rows", ())))
        )
    return _as_rows(getattr(document, "bindings", ()))


def _history(history: object | None) -> tuple[object, ...]:
    if history is None:
        return ()
    if isinstance(history, (str, bytes)) or not isinstance(history, Sequence):
        return ()
    return tuple(history)


def _as_rows(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return ()
    return tuple(value)


def _text(row: object, name: str) -> str | None:
    raw = row.get(name) if isinstance(row, Mapping) else getattr(row, name, None)
    value = getattr(raw, "value", raw)
    if type(value) is not str or not value:
        return None
    return value


def _number(row: object, name: str) -> float | None:
    raw = row.get(name) if isinstance(row, Mapping) else getattr(row, name, None)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    number = float(raw)
    if not math.isfinite(number):
        return None
    return number


def _sequence(row: object, name: str) -> tuple[object, ...]:
    raw = row.get(name) if isinstance(row, Mapping) else getattr(row, name, None)
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        return ()
    return tuple(raw)


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
    spec = metric_specification(MetricFamilyId.EMERGENT_SEMANTIC_NAMING)
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
            source_kind="emergent_semantic_naming",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )
