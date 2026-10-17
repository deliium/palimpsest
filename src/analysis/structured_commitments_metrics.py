"""Sibling metric families for commitment speech. Statuses are not world facts."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions
from analysis.specifications import (
    MetricFamilyId,
    MetricSpecification,
    metric_specification,
)
from analysis.structured_commitments import (
    CommitmentLedgerSnapshot,
    CommitmentSpeechView,
    classify_commitment_speech,
)
from world.events import WorldEvent
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.structured_commitments_metrics"
)
_LAYER: Final[str] = "research_inference"
_CHANNELS: Final[tuple[str, ...]] = (
    "relationship",
    "reputation",
    "norm",
    "sanction",
)

COMMITMENT_TERM_DIVERGENCE_METRIC_VERSION: Final[str] = "commitment_term_divergence@1"
COMMITMENT_FULFILLMENT_STATUS_METRIC_VERSION: Final[str] = (
    "commitment_fulfillment_status@1"
)
COMMITMENT_SOCIAL_CONSEQUENCES_METRIC_VERSION: Final[str] = (
    "commitment_social_consequences@1"
)


def assemble_structured_commitment_metrics(
    events: Sequence[WorldEvent],
    *,
    run_id: str,
    input_revision: str,
    spec: object | None,
    as_of_tick: int,
    ledgers: Sequence[CommitmentLedgerSnapshot] = (),
    owner_ids: Sequence[str] = (),
    consequence_counts: Mapping[str, int] | None = None,
) -> tuple[MetricDocument, ...]:
    """Three families. An absent spec yields an empty harvest."""
    if spec is None:
        return ()
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("as_of_tick", as_of_tick)
    views = classify_commitment_speech(
        events,
        as_of_tick=tick,
        ledgers=ledgers,
        owner_ids=owner_ids,
    )
    counts = _counts(consequence_counts)
    documents = (
        _divergence(views, document_run, revision),
        _fulfillment(views, document_run, revision),
        _consequences(views, counts, document_run, revision),
    )
    _LOG.debug(
        "structured_commitments_metrics_assembled family_ids=%s row_counts=%s",
        [document.metric_family for document in documents],
        [len(views), len(views), sum(counts.values())],
    )
    return documents


def _counts(raw: Mapping[str, int] | None) -> dict[str, int]:
    counts = {channel: 0 for channel in _CHANNELS}
    if raw is None:
        return counts
    for channel in _CHANNELS:
        value = raw.get(channel, 0)
        if type(value) is not int or isinstance(value, bool) or value < 0:
            raise ValueError("consequence_counts")
        counts[channel] = value
    return counts


def _document(
    spec: MetricSpecification,
    run_id: str,
    revision: str,
    values: Mapping[str, object],
    *,
    observed: int,
) -> MetricDocument:
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
        coverage=MetricCoverage(observed=observed, expected=max(observed, 1)),
        availability=MetricAvailability.PRESENT,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="structured_commitments",
            source_ids=(run_id,),
            notes_code="ok",
        ),
    )


def _divergence(
    views: Sequence[CommitmentSpeechView], run_id: str, revision: str
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.COMMITMENT_TERM_DIVERGENCE)
    if spec.version_identifier != COMMITMENT_TERM_DIVERGENCE_METRIC_VERSION:
        raise ValueError("unsupported_metric_version")
    unformed = sum(
        1 for view in views for row in view.interpretations if row.status == "unformed"
    )
    return _document(
        spec,
        run_id,
        revision,
        {
            "layer": _LAYER,
            "speech_count": len(views),
            "divergent_count": sum(view.divergent for view in views),
            "unformed_count": unformed,
        },
        observed=len(views),
    )


def _fulfillment(
    views: Sequence[CommitmentSpeechView], run_id: str, revision: str
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.COMMITMENT_FULFILLMENT_STATUS)
    if spec.version_identifier != COMMITMENT_FULFILLMENT_STATUS_METRIC_VERSION:
        raise ValueError("unsupported_metric_version")
    statuses: Counter[str] = Counter()
    partial = 0
    for view in views:
        for row in view.interpretations:
            if row.status == "unformed":
                continue
            statuses[row.status] += 1
            if row.status == "partial":
                partial += 1
    histogram = ",".join(
        f"{status}:{count}" for status, count in sorted(statuses.items())
    )
    return _document(
        spec,
        run_id,
        revision,
        {
            "layer": _LAYER,
            "status_histogram": histogram,
            "partial_count": partial,
            "forgotten_split_count": sum(view.forgotten_split for view in views),
        },
        observed=len(views),
    )


def _consequences(
    views: Sequence[CommitmentSpeechView],
    counts: Mapping[str, int],
    run_id: str,
    revision: str,
) -> MetricDocument:
    spec = metric_specification(MetricFamilyId.COMMITMENT_SOCIAL_CONSEQUENCES)
    if spec.version_identifier != COMMITMENT_SOCIAL_CONSEQUENCES_METRIC_VERSION:
        raise ValueError("unsupported_metric_version")
    return _document(
        spec,
        run_id,
        revision,
        {
            "layer": _LAYER,
            "relationship_request_count": counts["relationship"],
            "reputation_request_count": counts["reputation"],
            "norm_request_count": counts["norm"],
            "sanction_request_count": counts["sanction"],
        },
        observed=len(views),
    )
