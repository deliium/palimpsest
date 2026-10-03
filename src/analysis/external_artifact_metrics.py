"""External records that outlast soft-forgotten episodic cues.

Analysis-only. This module duck-types caller rows with ``getattr`` and must
not import agents, ``apply_artifact_interpretation_update``, or
``AgentRuntime``. Empty denominators yield ``MetricAvailability.ABSENT`` for
that key only.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from itertools import combinations
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
    "EXTERNAL_ARTIFACT_MEMORY_METRIC_VERSION",
    "compute_external_artifact_memory",
]

EXTERNAL_ARTIFACT_MEMORY_METRIC_VERSION: Final[str] = "external_artifact_memory@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.external_artifact_memory")
_ABSENT: Final[str] = MetricAvailability.ABSENT.value


def compute_external_artifact_memory(
    rows: object | None,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Build survival, memory-loss, recovery, and divergence from caller rows."""
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    payload = rows if isinstance(rows, Mapping) else {}
    objective = _as_rows(
        payload.get("objective_rows", ()) if isinstance(rows, Mapping) else rows
    )
    memory = _as_rows(
        payload.get("memory_rows", ()) if isinstance(rows, Mapping) else ()
    )
    interpretations = _as_rows(
        payload.get("interpretation_rows", ())
        if isinstance(rows, Mapping)
        else ()
    )
    if not objective and not memory and not interpretations:
        _LOG.warning(
            "external_artifact_memory_empty tick=%s reason=no_rows",
            tick,
        )
        return _document(
            run_id=run_id,
            input_revision=input_revision,
            availability=MetricAvailability.ABSENT,
            values={},
            notes_code="empty_rows",
        )
    forget_tick = _forget_tick(payload)
    scenario_artifact_id = _text(payload, "scenario_artifact_id")
    owner_a = _text(payload, "owner_a_id") or "ada"
    values: dict[str, object] = {
        "record_present_after_forget": _record_present_after_forget(
            objective,
            forget_tick=forget_tick,
            scenario_artifact_id=scenario_artifact_id,
        ),
        "mean_content_revision": _mean_content_revision(
            objective, forget_tick=forget_tick
        ),
        "memory_loss_rate": _memory_loss_rate(memory, owner_a=owner_a),
        "reading_recovery_rate": _reading_recovery_rate(
            interpretations,
            objective=objective,
            scenario_artifact_id=scenario_artifact_id,
        ),
        "interpretation_divergence": _interpretation_divergence(
            interpretations,
            objective=objective,
            scenario_artifact_id=scenario_artifact_id,
        ),
    }
    _LOG.debug(
        "external_artifact_memory_computed tick=%s "
        "objective_count=%s memory_count=%s interpretation_count=%s "
        "record_present=%s mean_revision_absent=%s memory_absent=%s "
        "recovery_absent=%s divergence_absent=%s",
        tick,
        len(objective),
        len(memory),
        len(interpretations),
        values["record_present_after_forget"] == 1.0,
        values["mean_content_revision"] == _ABSENT,
        values["memory_loss_rate"] == _ABSENT,
        values["reading_recovery_rate"] == _ABSENT,
        values["interpretation_divergence"] == _ABSENT,
    )
    return _document(
        run_id=run_id,
        input_revision=input_revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        notes_code="caller_rows",
        observed=len(objective) + len(memory) + len(interpretations),
        expected=len(objective) + len(memory) + len(interpretations),
    )


def _forget_tick(payload: Mapping[str, object]) -> int:
    raw = payload.get("forget_tick", 0)
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return 0
    return raw


def _record_present_after_forget(
    objective: Sequence[object],
    *,
    forget_tick: int,
    scenario_artifact_id: str | None,
) -> float:
    for row in objective:
        tick = _int(row, "tick")
        if tick is None or tick < forget_tick:
            continue
        kind = _text(row, "kind")
        if kind != "record":
            continue
        artifact_id = _text(row, "artifact_id")
        if scenario_artifact_id is not None and artifact_id != scenario_artifact_id:
            continue
        if _bool(row, "present") is True:
            return 1.0
    return 0.0


def _mean_content_revision(
    objective: Sequence[object],
    *,
    forget_tick: int,
) -> float | str:
    revisions: list[float] = []
    for row in objective:
        tick = _int(row, "tick")
        if tick is None or tick < forget_tick:
            continue
        if _bool(row, "present") is not True:
            continue
        revision = _number(row, "content_revision")
        if revision is None:
            continue
        revisions.append(revision)
    if not revisions:
        return _ABSENT
    return quantize_float(sum(revisions) / len(revisions))


def _memory_loss_rate(memory: Sequence[object], *, owner_a: str) -> float | str:
    cue_rows = [
        row
        for row in memory
        if _text(row, "owner_id") == owner_a and _bool(row, "has_cue_concept") is True
    ]
    if not cue_rows:
        return _ABSENT
    forgotten = sum(1 for row in cue_rows if _bool(row, "forgotten") is True)
    return quantize_float(forgotten / len(cue_rows))


def _reading_recovery_rate(
    interpretations: Sequence[object],
    *,
    objective: Sequence[object],
    scenario_artifact_id: str | None,
) -> float | str:
    marks_by_id = _objective_marks(objective, scenario_artifact_id=scenario_artifact_id)
    readers: list[object] = []
    for row in interpretations:
        artifact_id = _text(row, "artifact_id")
        if scenario_artifact_id is not None and artifact_id != scenario_artifact_id:
            continue
        if artifact_id is None or artifact_id not in marks_by_id:
            continue
        readers.append(row)
    if not readers:
        return _ABSENT
    recovered = 0
    for row in readers:
        artifact_id = _text(row, "artifact_id")
        assert artifact_id is not None
        reading = _marks(row, "reading_marks")
        distorted = _bool(row, "distorted")
        if reading == marks_by_id[artifact_id] and distorted is False:
            recovered += 1
    return quantize_float(recovered / len(readers))


def _interpretation_divergence(
    interpretations: Sequence[object],
    *,
    objective: Sequence[object],
    scenario_artifact_id: str | None,
) -> float | str:
    marks_by_id = _objective_marks(objective, scenario_artifact_id=scenario_artifact_id)
    by_artifact: dict[str, list[tuple[str, ...]]] = {}
    for row in interpretations:
        artifact_id = _text(row, "artifact_id")
        owner_id = _text(row, "owner_id")
        if artifact_id is None or owner_id is None:
            continue
        if scenario_artifact_id is not None and artifact_id != scenario_artifact_id:
            continue
        if artifact_id not in marks_by_id:
            continue
        by_artifact.setdefault(artifact_id, []).append(_marks(row, "reading_marks"))
    pair_count = 0
    diverge_count = 0
    for artifact_id, readings in by_artifact.items():
        if artifact_id not in marks_by_id or len(readings) < 2:
            continue
        for left, right in combinations(readings, 2):
            pair_count += 1
            # Same artifact id ⇒ identical objective content for the pair.
            if left != right:
                diverge_count += 1
    if pair_count == 0:
        return _ABSENT
    return quantize_float(diverge_count / pair_count)


def _objective_marks(
    objective: Sequence[object],
    *,
    scenario_artifact_id: str | None,
) -> dict[str, tuple[str, ...]]:
    marks: dict[str, tuple[str, ...]] = {}
    for row in objective:
        artifact_id = _text(row, "artifact_id")
        if artifact_id is None:
            continue
        if scenario_artifact_id is not None and artifact_id != scenario_artifact_id:
            continue
        if _bool(row, "present") is False:
            continue
        marks[artifact_id] = _marks(row, "marks")
    return marks


def _as_rows(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return ()
    return tuple(value)


def _text(row: object, name: str) -> str | None:
    raw = getattr(row, name, None)
    if raw is None and isinstance(row, Mapping):
        raw = row.get(name)
    raw = getattr(raw, "value", raw)
    if not isinstance(raw, str) or not raw:
        return None
    return raw


def _int(row: object, name: str) -> int | None:
    raw = getattr(row, name, None)
    if raw is None and isinstance(row, Mapping):
        raw = row.get(name)
    if isinstance(raw, bool) or not isinstance(raw, int):
        return None
    return raw


def _number(row: object, name: str) -> float | None:
    raw = getattr(row, name, None)
    if raw is None and isinstance(row, Mapping):
        raw = row.get(name)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    number = float(raw)
    if not math.isfinite(number):
        return None
    return number


def _bool(row: object, name: str) -> bool | None:
    raw = getattr(row, name, None)
    if raw is None and isinstance(row, Mapping):
        raw = row.get(name)
    if type(raw) is not bool:
        return None
    return raw


def _marks(row: object, name: str) -> tuple[str, ...]:
    raw = getattr(row, name, None)
    if raw is None and isinstance(row, Mapping):
        raw = row.get(name)
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        return ()
    out: list[str] = []
    for item in raw:
        token = getattr(item, "value", item)
        if isinstance(token, str) and token:
            out.append(token)
    return tuple(out)


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
    spec = metric_specification(MetricFamilyId.EXTERNAL_ARTIFACT_MEMORY)
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
            source_kind="external_artifact_memory",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )
