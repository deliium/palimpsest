"""Analysis-only bounded-experiment trial, discovery, and provenance metrics.

Duck-types detached trial audits and practical-knowledge evidence refs.
Never imports cognition ledgers or private world modules.
"""

from __future__ import annotations

import logging
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
from analysis.specifications import (
    MetricFamilyId,
    MetricSpecification,
    metric_specification,
)
from world.identifiers import require_stable_id

__all__ = [
    "BOUNDED_EXPERIMENT_DISCOVERY_METRIC_VERSION",
    "BOUNDED_EXPERIMENT_PROVENANCE_METRIC_VERSION",
    "BOUNDED_EXPERIMENT_TRIALS_METRIC_VERSION",
    "assemble_bounded_experiment_metrics",
    "compute_bounded_experiment_discovery",
    "compute_bounded_experiment_provenance",
    "compute_bounded_experiment_trials",
    "knowledge_provenance_for_experiment",
]

BOUNDED_EXPERIMENT_TRIALS_METRIC_VERSION: Final[str] = "bounded_experiment_trials@1"
BOUNDED_EXPERIMENT_DISCOVERY_METRIC_VERSION: Final[str] = (
    "bounded_experiment_discovery@1"
)
BOUNDED_EXPERIMENT_PROVENANCE_METRIC_VERSION: Final[str] = (
    "bounded_experiment_provenance@1"
)

_OUTCOMES: Final[tuple[str, ...]] = (
    "failure",
    "harm",
    "partial_success",
    "success",
    "unexpected",
)
_OPERATORS: Final[tuple[str, ...]] = ("apply_tool", "combine", "vary_process")
_MODES: Final[frozenset[str]] = frozenset({"accidental", "deliberate"})
_LOG: Final[logging.Logger] = logging.getLogger("analysis.experimentation")
_LAYER: Final[str] = "research_analytics"
_CENSOR: Final[str] = "analysis-only bounded experimentation; never cognition"


class ExperimentMetricError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        _LOG.error("experiment_metric_invalid reason_code=%s", reason_code)
        super().__init__(reason_code)


def _rows(values: object, reason: str) -> tuple[object, ...]:
    if isinstance(values, (set, frozenset, Mapping, str)) or not isinstance(
        values, Sequence
    ):
        raise ExperimentMetricError(reason)
    return tuple(values)


def _text(row: object, name: str) -> str:
    value = row.get(name) if isinstance(row, Mapping) else getattr(row, name, None)
    if type(value) is not str or not value:
        raise ExperimentMetricError("malformed_trial")
    return value


def _refs(row: object) -> tuple[str, ...]:
    value = (
        row.get("evidence_refs")
        if isinstance(row, Mapping)
        else getattr(row, "evidence_refs", ())
    )
    if isinstance(value, (set, frozenset, Mapping, str)) or not isinstance(
        value, Sequence
    ):
        raise ExperimentMetricError("malformed_evidence_refs")
    refs: list[str] = []
    for item in value:
        if type(item) is not str:
            raise ExperimentMetricError("malformed_evidence_refs")
        refs.append(item)
    return tuple(refs)


def _entry_id(row: object) -> str:
    value = (
        row.get("entry_id")
        if isinstance(row, Mapping)
        else getattr(row, "entry_id", None)
    )
    if type(value) is not str or not value:
        raise ExperimentMetricError("malformed_entry")
    return value


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
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=max(expected, observed))
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
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
            source_kind="bounded_experimentation",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )


def _absent(
    family: MetricFamilyId,
    version: str,
    run_id: str,
    revision: str,
    notes_code: str,
) -> MetricDocument:
    spec = metric_specification(family)
    if spec.version_identifier != version:
        raise ExperimentMetricError("unsupported_metric_version")
    return _document(
        spec,
        run_id,
        revision,
        MetricAvailability.ABSENT,
        {"layer": _LAYER},
        notes_code=notes_code,
    )


def compute_bounded_experiment_trials(
    trials: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
    spec_present: bool,
) -> MetricDocument:
    """Trial counts by closed outcome class and operator."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = () if not spec_present else _rows(trials, "trials_not_ordered")
    if not spec_present or not rows:
        return _absent(
            MetricFamilyId.BOUNDED_EXPERIMENT_TRIALS,
            BOUNDED_EXPERIMENT_TRIALS_METRIC_VERSION,
            document_run,
            revision,
            "channel_off" if not spec_present else "no_experiment_trials",
        )
    outcome_counts = {name: 0 for name in _OUTCOMES}
    operator_counts = {name: 0 for name in _OPERATORS}
    for row in rows:
        outcome = _text(row, "outcome_class")
        operator = _text(row, "operator")
        if outcome not in outcome_counts or operator not in operator_counts:
            raise ExperimentMetricError("unknown_trial_class")
        outcome_counts[outcome] += 1
        operator_counts[operator] += 1
    values: dict[str, object] = {
        "layer": _LAYER,
        "trial_count": len(rows),
        "censoring_policy": _CENSOR,
    }
    for name, count in outcome_counts.items():
        values[f"outcome_{name}_count"] = count
    for name, count in operator_counts.items():
        values[f"operator_{name}_count"] = count
    spec = metric_specification(MetricFamilyId.BOUNDED_EXPERIMENT_TRIALS)
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(rows),
        expected=len(rows),
    )


def compute_bounded_experiment_discovery(
    trials: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
    spec_present: bool,
) -> MetricDocument:
    """Deliberate versus accidental counts and the unexpected share."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    rows = () if not spec_present else _rows(trials, "trials_not_ordered")
    if not spec_present or not rows:
        return _absent(
            MetricFamilyId.BOUNDED_EXPERIMENT_DISCOVERY,
            BOUNDED_EXPERIMENT_DISCOVERY_METRIC_VERSION,
            document_run,
            revision,
            "channel_off" if not spec_present else "no_experiment_trials",
        )
    deliberate = 0
    accidental = 0
    unexpected = 0
    for row in rows:
        mode = _text(row, "discovery_mode")
        outcome = _text(row, "outcome_class")
        if mode not in _MODES or outcome not in _OUTCOMES:
            raise ExperimentMetricError("unknown_trial_class")
        if mode == "deliberate":
            deliberate += 1
        else:
            accidental += 1
        if outcome == "unexpected":
            unexpected += 1
    spec = metric_specification(MetricFamilyId.BOUNDED_EXPERIMENT_DISCOVERY)
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        {
            "layer": _LAYER,
            "trial_count": len(rows),
            "deliberate_count": deliberate,
            "accidental_count": accidental,
            "unexpected_count": unexpected,
            "unexpected_share": quantize_float(unexpected / len(rows)),
            "censoring_policy": _CENSOR,
        },
        notes_code="ok",
        observed=len(rows),
        expected=len(rows),
    )


def compute_bounded_experiment_provenance(
    trials: Sequence[object],
    entries: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
    spec_present: bool,
    genealogy_uptake: bool,
) -> MetricDocument:
    """Share of learned entries that cite a harvested experiment event."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    if not spec_present:
        return _absent(
            MetricFamilyId.BOUNDED_EXPERIMENT_PROVENANCE,
            BOUNDED_EXPERIMENT_PROVENANCE_METRIC_VERSION,
            document_run,
            revision,
            "channel_off",
        )
    learned = _rows(entries, "entries_not_ordered")
    if not learned:
        return _absent(
            MetricFamilyId.BOUNDED_EXPERIMENT_PROVENANCE,
            BOUNDED_EXPERIMENT_PROVENANCE_METRIC_VERSION,
            document_run,
            revision,
            "no_learned_entries",
        )
    event_ids = {
        _text(row, "event_id") for row in _rows(trials, "trials_not_ordered")
    }
    cited = 0
    if genealogy_uptake:
        for entry in learned:
            refs = _refs(entry)
            if any(f"evt:{event_id}" in refs for event_id in event_ids):
                cited += 1
    spec = metric_specification(MetricFamilyId.BOUNDED_EXPERIMENT_PROVENANCE)
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        {
            "layer": _LAYER,
            "learned_entry_count": len(learned),
            "cited_entry_count": cited,
            "provenance_share": quantize_float(
                0.0 if not genealogy_uptake else cited / len(learned)
            ),
            "censoring_policy": _CENSOR,
        },
        notes_code="ok",
        observed=len(learned),
        expected=len(learned),
    )


def assemble_bounded_experiment_metrics(
    trials: Sequence[object],
    entries: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
    spec_present: bool,
    genealogy_uptake: bool,
) -> tuple[MetricDocument, MetricDocument, MetricDocument]:
    """Assemble the three sibling families. Empty when the spec was absent."""
    documents = (
        compute_bounded_experiment_trials(
            trials,
            run_id=run_id,
            input_revision=input_revision,
            spec_present=spec_present,
        ),
        compute_bounded_experiment_discovery(
            trials,
            run_id=run_id,
            input_revision=input_revision,
            spec_present=spec_present,
        ),
        compute_bounded_experiment_provenance(
            trials,
            entries,
            run_id=run_id,
            input_revision=input_revision,
            spec_present=spec_present,
            genealogy_uptake=genealogy_uptake,
        ),
    )
    _LOG.debug(
        "experiment_metrics_assembled family_ids=%s trial_rows=%s learned_rows=%s",
        ",".join(document.metric_family for document in documents),
        0 if not spec_present else len(_rows(trials, "trials_not_ordered")),
        0 if not spec_present else len(_rows(entries, "entries_not_ordered")),
    )
    return documents


def knowledge_provenance_for_experiment(
    event_id: str, entries: Sequence[object]
) -> tuple[str, ...]:
    """Holder entry ids that cite ``evt:{event_id}``. Empty when none do."""
    token = require_stable_id("event_id", event_id)
    needle = f"evt:{token}"
    found: list[str] = []
    for entry in _rows(entries, "entries_not_ordered"):
        if needle in _refs(entry):
            found.append(_entry_id(entry))
    return tuple(found)
