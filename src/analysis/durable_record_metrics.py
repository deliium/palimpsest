"""Analysis-only durable-record lineage / fidelity / survival metrics.

Duck-types harvest rows via ``getattr`` / mapping keys. Never imports
cognition, private ``world._*`` authority modules, or feeds agent state.
False-record persistence uses an analysis-only truth spec (seeded expected
marks vs observed marks) — never engine admission.
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
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_stable_id

__all__ = [
    "DURABLE_RECORD_FIDELITY_METRIC_VERSION",
    "DURABLE_RECORD_LINEAGE_METRIC_VERSION",
    "DURABLE_RECORD_SURVIVAL_METRIC_VERSION",
    "CopyFidelitySummary",
    "DurableRecordLineageSummary",
    "RecordSurvivalSummary",
    "compute_durable_record_fidelity",
    "compute_durable_record_lineage",
    "compute_durable_record_survival",
    "summarize_copy_fidelity",
    "summarize_durable_record_lineage",
    "summarize_record_survival",
]

DURABLE_RECORD_LINEAGE_METRIC_VERSION: Final[str] = "durable_record_lineage@1"
DURABLE_RECORD_FIDELITY_METRIC_VERSION: Final[str] = "durable_record_fidelity@1"
DURABLE_RECORD_SURVIVAL_METRIC_VERSION: Final[str] = "durable_record_survival@1"

_LOG: Final[logging.Logger] = logging.getLogger("analysis.durable_record_metrics")
_LAYER: Final[str] = "research_analytics"
_CENSOR: Final[str] = "analysis-only durable records; never cognition"
_ABSENT: Final[str] = MetricAvailability.ABSENT.value
_FIDELITY_MODES: Final[frozenset[str]] = frozenset(
    {"perfect", "deterministic_mutation", "lossy"}
)


@dataclass(frozen=True, slots=True)
class DurableRecordLineageSummary:
    """Counts / histograms for durable copy trees (no mark payloads)."""

    record_count: int
    max_copy_generation: int
    mean_copy_generation: float
    generation_histogram: tuple[tuple[int, int], ...]
    parent_coverage: float
    source_coverage: float
    tombstone_share: float
    tombstone_count: int


@dataclass(frozen=True, slots=True)
class CopyFidelitySummary:
    """Parent→child copy fidelity rates and mean edit distances."""

    copy_event_count: int
    perfect_rate: float
    deterministic_mutation_rate: float
    lossy_rate: float
    mean_mark_edit_distance: float
    mean_relation_edit_distance: float


@dataclass(frozen=True, slots=True)
class RecordSurvivalSummary:
    """Integrity / author-death / false-record persistence counts."""

    record_count: int
    intact_count: int
    damaged_count: int
    partially_lost_count: int
    destroyed_count: int
    intact_after_author_death_count: int
    false_record_persistence_rate: float | str


def summarize_durable_record_lineage(
    rows: Sequence[object],
) -> DurableRecordLineageSummary:
    """Build lineage summary from duck-typed durable harvest rows."""
    generations: list[int] = []
    with_parent = 0
    with_source = 0
    tombstones = 0
    histogram: Counter[int] = Counter()
    for row in rows:
        generation = _int(row, "copy_generation")
        if generation is None:
            generation = 0
        generations.append(generation)
        histogram[generation] += 1
        if _text(row, "parent_artifact_id") is not None:
            with_parent += 1
        if _text(row, "source_artifact_id") is not None:
            with_source += 1
        integrity = _text(row, "integrity")
        if integrity == "destroyed" or _bool(row, "tombstone") is True:
            tombstones += 1
    count = len(rows)
    if count == 0:
        return DurableRecordLineageSummary(
            record_count=0,
            max_copy_generation=0,
            mean_copy_generation=0.0,
            generation_histogram=(),
            parent_coverage=0.0,
            source_coverage=0.0,
            tombstone_share=0.0,
            tombstone_count=0,
        )
    return DurableRecordLineageSummary(
        record_count=count,
        max_copy_generation=max(generations),
        mean_copy_generation=quantize_float(sum(generations) / count),
        generation_histogram=tuple(sorted(histogram.items())),
        parent_coverage=quantize_float(with_parent / count),
        source_coverage=quantize_float(with_source / count),
        tombstone_share=quantize_float(tombstones / count),
        tombstone_count=tombstones,
    )


def summarize_copy_fidelity(
    event_rows: Sequence[object],
    *,
    record_rows: Sequence[object] = (),
) -> CopyFidelitySummary:
    """Summarize copy fidelity from copied events and optional parent/child rows."""
    by_id = {
        artifact_id: row
        for row in record_rows
        if (artifact_id := _text(row, "artifact_id")) is not None
    }
    modes: Counter[str] = Counter()
    mark_distances: list[float] = []
    relation_distances: list[float] = []
    copies = 0
    for row in event_rows:
        kind = _text(row, "kind") or _text(row, "event_kind")
        if kind not in {"artifact_copied", "copied"}:
            continue
        copies += 1
        mode = _text(row, "fidelity_mode") or "perfect"
        if mode not in _FIDELITY_MODES:
            mode = "perfect"
        modes[mode] += 1
        child_id = _text(row, "child_artifact_id") or _text(row, "artifact_id")
        parent_id = _text(row, "parent_artifact_id")
        if child_id is None or parent_id is None:
            continue
        child = by_id.get(child_id)
        parent = by_id.get(parent_id)
        if child is None or parent is None:
            # Fall back to explicit edit distances on the event row.
            mark_edit = _number(row, "mark_edit_distance")
            relation_edit = _number(row, "relation_edit_distance")
            if mark_edit is not None:
                mark_distances.append(mark_edit)
            if relation_edit is not None:
                relation_distances.append(relation_edit)
            continue
        mark_distances.append(
            float(_edit_distance(_marks(parent, "marks"), _marks(child, "marks")))
        )
        relation_distances.append(
            float(
                _edit_distance(
                    _relation_tokens(parent),
                    _relation_tokens(child),
                )
            )
        )
    if copies == 0:
        return CopyFidelitySummary(
            copy_event_count=0,
            perfect_rate=0.0,
            deterministic_mutation_rate=0.0,
            lossy_rate=0.0,
            mean_mark_edit_distance=0.0,
            mean_relation_edit_distance=0.0,
        )
    return CopyFidelitySummary(
        copy_event_count=copies,
        perfect_rate=quantize_float(modes["perfect"] / copies),
        deterministic_mutation_rate=quantize_float(
            modes["deterministic_mutation"] / copies
        ),
        lossy_rate=quantize_float(modes["lossy"] / copies),
        mean_mark_edit_distance=quantize_float(
            sum(mark_distances) / len(mark_distances) if mark_distances else 0.0
        ),
        mean_relation_edit_distance=quantize_float(
            sum(relation_distances) / len(relation_distances)
            if relation_distances
            else 0.0
        ),
    )


def summarize_record_survival(
    rows: Sequence[object],
    *,
    death_ticks_by_body: Mapping[str, int] | None = None,
    false_record_expectations: Sequence[object] | None = None,
) -> RecordSurvivalSummary:
    """Integrity / author-death survival and optional false-record rate."""
    deaths = dict(death_ticks_by_body or {})
    intact = damaged = partial = destroyed = 0
    intact_after_death = 0
    for row in rows:
        integrity = _text(row, "integrity") or "intact"
        if integrity == "intact":
            intact += 1
        elif integrity == "damaged":
            damaged += 1
        elif integrity == "partially_lost":
            partial += 1
        elif integrity == "destroyed":
            destroyed += 1
        author_id = _text(row, "author_id")
        created = _int(row, "created_tick")
        if (
            integrity == "intact"
            and author_id is not None
            and author_id in deaths
            and created is not None
            and deaths[author_id] >= created
        ):
            intact_after_death += 1
    false_rate: float | str = _ABSENT
    expectations = tuple(false_record_expectations or ())
    if expectations:
        matched = 0
        persisted = 0
        by_id = {
            artifact_id: row
            for row in rows
            if (artifact_id := _text(row, "artifact_id")) is not None
        }
        for expect in expectations:
            artifact_id = _text(expect, "artifact_id")
            if artifact_id is None:
                continue
            matched += 1
            observed = by_id.get(artifact_id)
            if observed is None:
                continue
            expected_marks = _marks(expect, "expected_marks") or _marks(expect, "marks")
            observed_marks = _marks(observed, "marks")
            # Analysis truth: seeded false marks still present (mismatch intentional).
            if observed_marks == expected_marks and _text(observed, "integrity") != (
                "destroyed"
            ):
                persisted += 1
        false_rate = (
            quantize_float(persisted / matched) if matched else _ABSENT
        )
    return RecordSurvivalSummary(
        record_count=len(rows),
        intact_count=intact,
        damaged_count=damaged,
        partially_lost_count=partial,
        destroyed_count=destroyed,
        intact_after_author_death_count=intact_after_death,
        false_record_persistence_rate=false_rate,
    )


def compute_durable_record_lineage(
    rows: Sequence[object] | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Assemble ``durable_record_lineage@1`` from harvest rows."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    record_rows = _as_rows(rows)
    summary = summarize_durable_record_lineage(record_rows)
    _LOG.debug(
        "durable_record_lineage_computed record_count=%s max_generation=%s "
        "tombstone_count=%s censoring_policy=%s",
        summary.record_count,
        summary.max_copy_generation,
        summary.tombstone_count,
        _CENSOR,
    )
    if summary.record_count == 0:
        return _document(
            family_id="durable_record_lineage",
            version=DURABLE_RECORD_LINEAGE_METRIC_VERSION,
            run_id=document_run,
            input_revision=revision,
            availability=MetricAvailability.ABSENT,
            values={"layer": _LAYER, "censoring_policy": _CENSOR},
            notes_code="no_durable_record_rows",
            source_kind="durable_record_lineage",
        )
    values: dict[str, object] = {
        "layer": _LAYER,
        "censoring_policy": _CENSOR,
        "record_count": summary.record_count,
        "max_copy_generation": summary.max_copy_generation,
        "mean_copy_generation": summary.mean_copy_generation,
        "parent_coverage": summary.parent_coverage,
        "source_coverage": summary.source_coverage,
        "tombstone_share": summary.tombstone_share,
        "tombstone_count": summary.tombstone_count,
        # Flat histogram keys (MetricDocument values disallow nested maps).
        "generation_histogram_encoded": ",".join(
            f"{generation}:{count}"
            for generation, count in summary.generation_histogram
        ),
    }
    for generation, count in summary.generation_histogram:
        values[f"generation_{generation}_count"] = count
    return _document(
        family_id="durable_record_lineage",
        version=DURABLE_RECORD_LINEAGE_METRIC_VERSION,
        run_id=document_run,
        input_revision=revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        notes_code="ok",
        observed=summary.record_count,
        expected=summary.record_count,
        source_kind="durable_record_lineage",
    )


def compute_durable_record_fidelity(
    event_rows: Sequence[object] | None,
    *,
    run_id: str,
    input_revision: str,
    record_rows: Sequence[object] | None = None,
) -> MetricDocument:
    """Assemble ``durable_record_fidelity@1`` from copy events (+ optional rows)."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    events = _as_rows(event_rows)
    records = _as_rows(record_rows)
    summary = summarize_copy_fidelity(events, record_rows=records)
    _LOG.debug(
        "durable_record_fidelity_computed copy_event_count=%s perfect_rate=%s "
        "censoring_policy=%s",
        summary.copy_event_count,
        summary.perfect_rate,
        _CENSOR,
    )
    if summary.copy_event_count == 0:
        return _document(
            family_id="durable_record_fidelity",
            version=DURABLE_RECORD_FIDELITY_METRIC_VERSION,
            run_id=document_run,
            input_revision=revision,
            availability=MetricAvailability.ABSENT,
            values={"layer": _LAYER, "censoring_policy": _CENSOR},
            notes_code="no_copy_events",
            source_kind="durable_record_fidelity",
        )
    values = {
        "layer": _LAYER,
        "censoring_policy": _CENSOR,
        "copy_event_count": summary.copy_event_count,
        "perfect_rate": summary.perfect_rate,
        "deterministic_mutation_rate": summary.deterministic_mutation_rate,
        "lossy_rate": summary.lossy_rate,
        "mean_mark_edit_distance": summary.mean_mark_edit_distance,
        "mean_relation_edit_distance": summary.mean_relation_edit_distance,
    }
    return _document(
        family_id="durable_record_fidelity",
        version=DURABLE_RECORD_FIDELITY_METRIC_VERSION,
        run_id=document_run,
        input_revision=revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        notes_code="ok",
        observed=summary.copy_event_count,
        expected=summary.copy_event_count,
        source_kind="durable_record_fidelity",
    )


def compute_durable_record_survival(
    rows: Sequence[object] | None,
    *,
    run_id: str,
    input_revision: str,
    death_ticks_by_body: Mapping[str, int] | None = None,
    false_record_expectations: Sequence[object] | None = None,
) -> MetricDocument:
    """Assemble ``durable_record_survival@1`` from harvest + death ticks."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    record_rows = _as_rows(rows)
    summary = summarize_record_survival(
        record_rows,
        death_ticks_by_body=death_ticks_by_body,
        false_record_expectations=false_record_expectations,
    )
    _LOG.debug(
        "durable_record_survival_computed record_count=%s intact_after_death=%s "
        "censoring_policy=%s",
        summary.record_count,
        summary.intact_after_author_death_count,
        _CENSOR,
    )
    if summary.record_count == 0:
        return _document(
            family_id="durable_record_survival",
            version=DURABLE_RECORD_SURVIVAL_METRIC_VERSION,
            run_id=document_run,
            input_revision=revision,
            availability=MetricAvailability.ABSENT,
            values={"layer": _LAYER, "censoring_policy": _CENSOR},
            notes_code="no_durable_record_rows",
            source_kind="durable_record_survival",
        )
    values = {
        "layer": _LAYER,
        "censoring_policy": _CENSOR,
        "record_count": summary.record_count,
        "intact_count": summary.intact_count,
        "damaged_count": summary.damaged_count,
        "partially_lost_count": summary.partially_lost_count,
        "destroyed_count": summary.destroyed_count,
        "intact_after_author_death_count": summary.intact_after_author_death_count,
        "false_record_persistence_rate": summary.false_record_persistence_rate,
    }
    return _document(
        family_id="durable_record_survival",
        version=DURABLE_RECORD_SURVIVAL_METRIC_VERSION,
        run_id=document_run,
        input_revision=revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        notes_code="ok",
        observed=summary.record_count,
        expected=summary.record_count,
        source_kind="durable_record_survival",
    )


def _document(
    *,
    family_id: str,
    version: str,
    run_id: str,
    input_revision: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    notes_code: str,
    source_kind: str,
    observed: int = 0,
    expected: int = 0,
) -> MetricDocument:
    family = MetricFamilyId(family_id)
    spec = metric_specification(family)
    if spec.version_identifier != version:
        raise ValueError("unsupported_metric_version")
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
            source_kind=source_kind,
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )


def _as_rows(value: object | None) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        nested = value.get("rows") or value.get("durable_record_rows") or ()
        if isinstance(nested, Sequence) and not isinstance(nested, (str, bytes)):
            return tuple(nested)
        return ()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(value)
    return ()


def _text(row: object, name: str) -> str | None:
    raw = getattr(row, name, None)
    if raw is None and isinstance(row, Mapping):
        raw = row.get(name)
    token = getattr(raw, "value", raw)
    if isinstance(token, str) and token:
        return token
    return None


def _int(row: object, name: str) -> int | None:
    raw = getattr(row, name, None)
    if raw is None and isinstance(row, Mapping):
        raw = row.get(name)
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return None
    return raw


def _number(row: object, name: str) -> float | None:
    raw = getattr(row, name, None)
    if raw is None and isinstance(row, Mapping):
        raw = row.get(name)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    number = float(raw)
    if number != number or number in (float("inf"), float("-inf")):
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


def _relation_tokens(row: object) -> tuple[str, ...]:
    raw = getattr(row, "relations", None)
    if raw is None and isinstance(row, Mapping):
        raw = row.get("relations")
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        return ()
    tokens: list[str] = []
    for item in raw:
        if isinstance(item, Mapping):
            tokens.append(
                f"{item.get('subject', '')}|{item.get('predicate', '')}|"
                f"{item.get('object', '')}"
            )
            continue
        subject = getattr(item, "subject", "")
        predicate = getattr(item, "predicate", "")
        obj = getattr(item, "object", "")
        tokens.append(f"{subject}|{predicate}|{obj}")
    return tuple(tokens)


def _edit_distance(left: Sequence[str], right: Sequence[str]) -> int:
    """Token multiset L1 distance (drops + inserts); no payload logging."""
    left_counts = Counter(left)
    right_counts = Counter(right)
    keys = set(left_counts) | set(right_counts)
    return sum(abs(left_counts[key] - right_counts[key]) for key in keys)
