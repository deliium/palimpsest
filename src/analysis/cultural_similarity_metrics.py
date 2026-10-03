"""Per-channel cultural similarity from detached naming/norm/convention/narrative rows.

Analysis-only. Missing channels stay absent without zeroing others. No blended
culture-emergence score.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
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
    "CULTURAL_SIMILARITY_METRIC_VERSION",
    "compute_cultural_similarity",
]

CULTURAL_SIMILARITY_METRIC_VERSION: Final[str] = "cultural_similarity@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.cultural_similarity_metrics")
_CHANNELS: Final[tuple[tuple[str, str], ...]] = (
    ("naming", "naming_mean_pairwise_similarity"),
    ("norms", "norms_mean_pairwise_similarity"),
    ("conventions", "conventions_mean_pairwise_similarity"),
    ("narratives", "narratives_mean_pairwise_similarity"),
)
_TOKEN_ATTRS: Final[tuple[str, ...]] = (
    "token",
    "label",
    "norm_head",
    "habit_token",
    "variant_fingerprint",
    "fingerprint",
)


def compute_cultural_similarity(
    *,
    naming_rows: Sequence[object] | None = None,
    norms_rows: Sequence[object] | None = None,
    conventions_rows: Sequence[object] | None = None,
    narratives_rows: Sequence[object] | None = None,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Mean pairwise Jaccard similarity per cultural channel."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.CULTURAL_SIMILARITY)
    channel_rows: dict[str, Sequence[object] | None] = {
        "naming": naming_rows,
        "norms": norms_rows,
        "conventions": conventions_rows,
        "narratives": narratives_rows,
    }
    values: dict[str, object] = {}
    contributed: list[str] = []
    for channel, key in _CHANNELS:
        rows = channel_rows[channel]
        if rows is None or (
            isinstance(rows, Sequence)
            and not isinstance(rows, (str, bytes))
            and len(rows) == 0
        ):
            continue
        similarity = _channel_similarity(rows, field=f"{channel}_rows")
        if similarity is None:
            continue
        values[key] = similarity
        contributed.append(channel)
    values["channels_present"] = len(contributed)
    _LOG.debug(
        "cultural_similarity_compute",
        extra={
            "operation": "compute_cultural_similarity",
            "family_id": spec.family_id.value,
            "run_id": document_run,
            "channels_contributed": contributed,
            "channels_present": len(contributed),
        },
    )
    if not contributed:
        _LOG.warning(
            "cultural_similarity_empty",
            extra={
                "operation": "compute_cultural_similarity",
                "family_id": spec.family_id.value,
                "reason": "all_channels_empty",
            },
        )
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {},
            notes_code="all_channels_empty",
        )
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(contributed),
        expected=len(_CHANNELS),
    )


def _channel_similarity(rows: Sequence[object], *, field: str) -> float | None:
    if isinstance(rows, (str, bytes, set, frozenset, Mapping)) or not isinstance(
        rows, Sequence
    ):
        raise TypeError(f"{field}: not_ordered")
    owner_tokens: dict[str, set[str]] = defaultdict(set)
    for index, row in enumerate(rows):
        owner = getattr(row, "owner_id", None)
        if hasattr(owner, "value"):
            owner = getattr(owner, "value")
        if not isinstance(owner, str) or not owner:
            raise TypeError(f"{field}[{index}]: invalid_owner_id")
        token = _extract_token(row)
        if token is None:
            continue
        owner_tokens[owner].add(token)
    owners = sorted(owner_tokens)
    if len(owners) < 2:
        return None
    scores: list[float] = []
    for index, left in enumerate(owners):
        for right in owners[index + 1 :]:
            a = owner_tokens[left]
            b = owner_tokens[right]
            union = a | b
            if not union:
                scores.append(1.0)
                continue
            scores.append(float(len(a & b)) / float(len(union)))
    if not scores:
        return None
    scores.sort()
    return quantize_float(require_finite(float(sum(scores) / len(scores))))


def _extract_token(row: object) -> str | None:
    for attr in _TOKEN_ATTRS:
        value = getattr(row, attr, None)
        if isinstance(value, str) and value:
            return value
    return None


def _document(
    spec: object,
    run_id: str,
    revision: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    *,
    notes_code: str,
    observed: int = 0,
    expected: int = 0,
) -> MetricDocument:
    family = getattr(spec, "family_id")
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=expected)
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family.value,
        algorithm_version=getattr(spec, "algorithm_version"),
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=revision,
        evidence_stages=frozenset(getattr(spec, "evidence_inputs")),
        population=getattr(spec, "population"),
        denominator=getattr(spec, "denominator"),
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="cultural_similarity",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )
