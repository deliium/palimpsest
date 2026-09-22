"""Canonical metric-document serialization is strict and fail-closed."""

from __future__ import annotations

import json

import pytest

from analysis.evidence import EvidenceStage
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.serialization import (
    MetricSerializationError,
    decode_metric_document,
    encode_metric_document,
    metric_document_fingerprint,
)


def _document(**overrides: object) -> MetricDocument:
    base: dict[str, object] = {
        "schema_version": METRIC_DOCUMENT_SCHEMA_VERSION,
        "metric_family": "resource_inequality",
        "algorithm_version": "1",
        "library_versions": MetricDocument.default_library_versions(),
        "run_id": "run-1",
        "input_revision": "rev-1",
        "evidence_stages": frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE}),
        "population": "living_agents",
        "denominator": "inventory_count",
        "coverage": MetricCoverage(observed=1, expected=1, ratio=1.0),
        "availability": MetricAvailability.PRESENT,
        "values": {"gini": 0.25, "count": 2},
        "provenance": MetricProvenance(
            source_kind="objective_events",
            source_ids=("evt-1",),
        ),
    }
    base.update(overrides)
    return MetricDocument(**base)  # type: ignore[arg-type]


def test_metric_document_round_trip() -> None:
    document = _document()
    encoded = encode_metric_document(document)
    decoded = decode_metric_document(encoded)
    assert decoded == document
    assert metric_document_fingerprint(decoded) == metric_document_fingerprint(document)
    payload = json.loads(encoded.decode("utf-8"))
    assert payload["schema_version"] == METRIC_DOCUMENT_SCHEMA_VERSION
    assert "gini" in payload["values"]


def test_metric_document_rejects_unknown_fields() -> None:
    document = _document()
    payload = json.loads(encode_metric_document(document).decode("utf-8"))
    payload["extra"] = "nope"
    with pytest.raises(MetricSerializationError) as exc:
        decode_metric_document(json.dumps(payload, sort_keys=True))
    assert exc.value.code == "unknown_field"


def test_metric_document_rejects_non_finite_values() -> None:
    document = _document()
    payload = json.loads(encode_metric_document(document).decode("utf-8"))
    # allow_nan=False on encode; inject after the fact.
    text = json.dumps(payload, sort_keys=True).replace("0.25", "NaN")
    with pytest.raises(MetricSerializationError) as exc:
        decode_metric_document(text)
    assert exc.value.code in {"invalid_json", "non_finite", "invalid_value"}


def test_encode_rejects_non_finite_document_values() -> None:
    with pytest.raises((ValueError, MetricSerializationError)):
        encode_metric_document(
            _document(values={"gini": float("inf")})  # type: ignore[arg-type]
        )
