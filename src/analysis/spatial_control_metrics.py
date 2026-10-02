"""Repeated spatial-control readings over committed action rows.

Analysis-only. This module does not import agent cognition, the observer,
or the world engine. Callers supply detached rows. The document is not a
cognition input and is not a frame field.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
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
    "SPATIAL_CONTROL_METRIC_VERSION",
    "SpatialActionRow",
    "SpatialClaimRow",
    "SpatialControlError",
    "compute_spatial_control",
]

SPATIAL_CONTROL_METRIC_VERSION: Final[str] = "spatial_control@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.spatial_control")
_WINDOW_KINDS: Final[frozenset[str]] = frozenset(
    {
        "move",
        "sleep",
        "take",
        "search",
        "resource_harvested",
        "structure_built",
        "structure_repaired",
        "item_stored",
    }
)
_INTERRUPT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "take",
        "resource_harvested",
        "item_stored",
        "eat",
        "drink",
    }
)
_LOCATION_TARGET_KINDS: Final[frozenset[str]] = frozenset(
    {"location", "frequent_area"}
)
_TARGET_KINDS: Final[frozenset[str]] = frozenset(
    {"location", "shelter", "stored_resource", "frequent_area"}
)
_WINDOW_LENGTH: Final[int] = 2
_CLAIM_CONTEST_STRENGTH: Final[float] = 0.40
_LAYER: Final[str] = "research_analytics"
_OBJECTIVE_SOURCE: Final[str] = "objective_control"
_SUBJECTIVE_SOURCE: Final[str] = "subjective_claims"


class SpatialControlError(ValueError):
    """Fail-closed spatial-control error. The message is a reason code."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        _LOG.error("spatial_control_invalid reason_code=%s", reason_code)
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class SpatialActionRow:
    """One successful committed action at a location. Not a world event."""

    tick: int
    ordinal: int
    agent_id: str
    action_kind: str
    location_id: str
    success: bool = True


@dataclass(frozen=True, slots=True)
class SpatialClaimRow:
    """One detached head. The metric does not read a live ledger."""

    owner_id: str
    target_kind: str
    target_entity_id: str
    strength: float


@dataclass(frozen=True, slots=True)
class _Window:
    location_id: str
    agent_id: str
    start_tick: int
    end_tick: int
    action_count: int


def compute_spatial_control(
    action_rows: Sequence[object],
    claim_rows: Sequence[object] | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Read exclusive windows and optional claim contests from detached rows.

    An empty action sequence is ``MetricAvailability.ABSENT``. Omitted or
    empty claim rows leave ``claim_contest`` absent while objective windows
    can still be present.
    """
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    ordered = _action_rows(action_rows)
    claims = _claim_rows(claim_rows)
    windows = _exclusive_windows(ordered)
    claim_reading = _claim_contests(claims)
    location_count = len({row.location_id for row in ordered})
    _LOG.debug(
        "spatial_control locations=%s windows=%s claim_rows=%s",
        location_count,
        len(windows),
        0 if claim_rows is None else len(claims),
    )
    spec = metric_specification(MetricFamilyId.SPATIAL_CONTROL)
    if spec.version_identifier != SPATIAL_CONTROL_METRIC_VERSION:
        raise SpatialControlError("unsupported_metric_version")
    if not ordered:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {
                "layer": _LAYER,
                "claim_contest": MetricAvailability.ABSENT.value,
                "contest_source": MetricAvailability.ABSENT.value,
            },
            notes_code="no_action_rows",
        )
    repeated = _repeated_locations(windows)
    contested = _control_contests(windows)
    intervals = _interval_text(windows)
    contest_source = _OBJECTIVE_SOURCE
    if claim_reading:
        contest_source = _SUBJECTIVE_SOURCE
    elif not contested:
        contest_source = MetricAvailability.ABSENT.value
    values: dict[str, object] = {
        "layer": _LAYER,
        "repeated_control": bool(repeated),
        "control_contest": bool(contested),
        "claim_contest": (
            True if claim_reading else MetricAvailability.ABSENT.value
        ),
        "contest_source": contest_source,
        "window_count": len(windows),
        "intervals": intervals,
    }
    if contested:
        values["control_contest_source"] = _OBJECTIVE_SOURCE
    if claim_reading:
        values["claim_contest_source"] = _SUBJECTIVE_SOURCE
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(windows),
        expected=max(len(windows), 1),
    )


def _action_rows(rows: Sequence[object]) -> tuple[SpatialActionRow, ...]:
    if isinstance(rows, (str, bytes, set, frozenset, Mapping)) or not isinstance(
        rows, Sequence
    ):
        raise SpatialControlError("invalid_action_rows")
    parsed: list[SpatialActionRow] = []
    for index, row in enumerate(rows):
        parsed_row = _parse_action(index, row)
        if parsed_row is not None:
            parsed.append(parsed_row)
    parsed.sort(key=lambda item: (item.tick, item.ordinal, item.agent_id))
    return tuple(parsed)


def _parse_action(index: int, row: object) -> SpatialActionRow | None:
    if type(row) is SpatialActionRow:
        if row.success is False:
            return None
        return row
    success = getattr(row, "success", True)
    if success is False:
        return None
    try:
        tick = require_exact_nonneg_int(
            f"action_rows[{index}].tick", getattr(row, "tick", None)
        )
        ordinal = require_exact_nonneg_int(
            f"action_rows[{index}].ordinal", getattr(row, "ordinal", None)
        )
        agent_id = require_stable_id(
            f"action_rows[{index}].agent_id", _text(getattr(row, "agent_id", None))
        )
        action_kind = require_stable_id(
            f"action_rows[{index}].action_kind",
            _text(getattr(row, "action_kind", None)),
        )
        location_raw = getattr(row, "location_id", None)
    except (TypeError, ValueError) as exc:
        raise SpatialControlError("invalid_action_rows") from exc
    if location_raw is None:
        return None
    try:
        location_id = require_stable_id(
            f"action_rows[{index}].location_id", _text(location_raw)
        )
    except (TypeError, ValueError) as exc:
        raise SpatialControlError("invalid_action_rows") from exc
    return SpatialActionRow(
        tick=tick,
        ordinal=ordinal,
        agent_id=agent_id,
        action_kind=action_kind,
        location_id=location_id,
        success=True,
    )


def _claim_rows(rows: Sequence[object] | None) -> tuple[SpatialClaimRow, ...]:
    if rows is None:
        return ()
    if isinstance(rows, (str, bytes, set, frozenset, Mapping)) or not isinstance(
        rows, Sequence
    ):
        raise SpatialControlError("invalid_claim_rows")
    parsed: list[SpatialClaimRow] = []
    for index, row in enumerate(rows):
        parsed.append(_parse_claim(index, row))
    return tuple(parsed)


def _parse_claim(index: int, row: object) -> SpatialClaimRow:
    if type(row) is SpatialClaimRow:
        _require_known_kind(row.target_kind)
        _require_finite_strength(row.strength)
        return row
    try:
        owner_id = require_stable_id(
            f"claim_rows[{index}].owner_id", _text(getattr(row, "owner_id", None))
        )
        target_kind = require_stable_id(
            f"claim_rows[{index}].target_kind",
            _text(getattr(row, "target_kind", None)),
        )
        target_entity_id = require_stable_id(
            f"claim_rows[{index}].target_entity_id",
            _text(getattr(row, "target_entity_id", None)),
        )
    except (TypeError, ValueError) as exc:
        raise SpatialControlError("invalid_claim_rows") from exc
    _require_known_kind(target_kind)
    strength = _require_finite_strength(getattr(row, "strength", None))
    return SpatialClaimRow(
        owner_id=owner_id,
        target_kind=target_kind,
        target_entity_id=target_entity_id,
        strength=quantize_float(strength),
    )


def _require_known_kind(target_kind: str) -> None:
    if target_kind not in _TARGET_KINDS:
        raise SpatialControlError("unknown_target_kind")


def _require_finite_strength(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpatialControlError("not_finite")
    try:
        number = require_finite(float(value))
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise SpatialControlError("not_finite") from exc
    if not math.isfinite(number):
        raise SpatialControlError("not_finite")
    return number


def _text(value: object) -> str:
    raw = getattr(value, "value", value)
    if not isinstance(raw, str):
        raise TypeError("expected str")
    return raw


def _exclusive_windows(rows: Sequence[SpatialActionRow]) -> tuple[_Window, ...]:
    grouped: dict[str, list[SpatialActionRow]] = defaultdict(list)
    for row in rows:
        if row.action_kind in _WINDOW_KINDS or row.action_kind in _INTERRUPT_KINDS:
            grouped[row.location_id].append(row)
    windows: list[_Window] = []
    for location_id in sorted(grouped):
        ordered = sorted(
            grouped[location_id], key=lambda item: (item.tick, item.ordinal)
        )
        windows.extend(_location_windows(location_id, ordered))
    return tuple(windows)


def _location_windows(
    location_id: str, ordered: Sequence[SpatialActionRow]
) -> tuple[_Window, ...]:
    windows: list[_Window] = []
    buffer: list[SpatialActionRow] = []

    def close() -> None:
        nonlocal buffer
        if len(buffer) >= _WINDOW_LENGTH:
            windows.append(
                _Window(
                    location_id=location_id,
                    agent_id=buffer[0].agent_id,
                    start_tick=buffer[0].tick,
                    end_tick=buffer[-1].tick,
                    action_count=len(buffer),
                )
            )
        buffer = []

    for row in ordered:
        same_agent = not buffer or buffer[0].agent_id == row.agent_id
        if row.action_kind in _WINDOW_KINDS and same_agent:
            buffer.append(row)
            continue
        close()
        if row.action_kind in _WINDOW_KINDS:
            buffer = [row]
    close()
    return tuple(windows)


def _repeated_locations(windows: Sequence[_Window]) -> tuple[str, ...]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for window in windows:
        counts[(window.location_id, window.agent_id)] += 1
    locations = {
        location_id
        for (location_id, _agent_id), count in counts.items()
        if count >= _WINDOW_LENGTH
    }
    return tuple(sorted(locations))


def _control_contests(windows: Sequence[_Window]) -> tuple[str, ...]:
    agents: dict[str, set[str]] = defaultdict(set)
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for window in windows:
        counts[(window.location_id, window.agent_id)] += 1
    for (location_id, agent_id), count in counts.items():
        if count >= _WINDOW_LENGTH:
            agents[location_id].add(agent_id)
    return tuple(
        sorted(
            location_id
            for location_id, owners in agents.items()
            if len(owners) >= 2
        )
    )


def _claim_contests(rows: Sequence[SpatialClaimRow]) -> tuple[str, ...]:
    owners: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row.target_kind not in _LOCATION_TARGET_KINDS:
            continue
        strength = quantize_float(row.strength)
        if strength >= _CLAIM_CONTEST_STRENGTH:
            owners[row.target_entity_id].add(row.owner_id)
    return tuple(
        sorted(location_id for location_id, group in owners.items() if len(group) >= 2)
    )


def _interval_text(windows: Sequence[_Window]) -> str:
    parts = [
        (
            f"{window.location_id}:{window.agent_id}:"
            f"{window.start_tick}:{window.end_tick}:{window.action_count}"
        )
        for window in sorted(
            windows,
            key=lambda item: (
                item.location_id,
                item.agent_id,
                item.start_tick,
                item.end_tick,
            ),
        )
    ]
    return ";".join(parts)


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
    family = spec.family_id
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=max(expected, observed))
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family.value,
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
            source_kind="spatial_control",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )
