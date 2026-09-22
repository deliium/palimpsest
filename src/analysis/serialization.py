"""Strict canonical JSON codecs for analysis metric documents.

Codecs are log-free. Errors expose only stable ``code`` and ``path`` metadata.
Never log evidence, claims, graph labels, seeds, or metric document payloads.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Final

from analysis.evidence import EvidenceStage, require_evidence_stage
from analysis.models import (
    ACTION_RESOLUTION_RATES_FAMILY,
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import (
    NumericalPolicyError,
    quantize_float,
    require_finite,
)
from world.identifiers import require_stable_id

__all__ = [
    "ACTION_RESOLUTION_RATES_FAMILY",
    "MetricSerializationError",
    "decode_metric_document",
    "encode_metric_document",
    "is_supported_metric_family",
    "metric_document_fingerprint",
]


def is_supported_metric_family(metric_family: str) -> bool:
    """True for catalog families or the shared action-resolution rates family."""
    if metric_family == ACTION_RESOLUTION_RATES_FAMILY:
        return True
    try:
        from analysis.specifications import MetricFamilyId

        MetricFamilyId(metric_family)
    except ValueError:
        return False
    return True

_REQUIRED_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "metric_family",
        "algorithm_version",
        "library_versions",
        "run_id",
        "input_revision",
        "evidence_stages",
        "population",
        "denominator",
        "coverage",
        "availability",
        "values",
        "provenance",
    }
)


class MetricSerializationError(ValueError):
    """Fail-closed metric codec error with stable metadata only."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}:{path}")


def _canonical_dumps(value: object) -> bytes:
    text = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return text.encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MetricSerializationError("duplicate_key", "$")
        result[key] = value
    return result


def _require_keys(
    data: Mapping[str, Any], required: frozenset[str], *, path: str
) -> None:
    keys = frozenset(data)
    if required - keys:
        raise MetricSerializationError("missing_field", path)
    if keys - required:
        raise MetricSerializationError("unknown_field", path)


def _str_field(data: Mapping[str, Any], key: str, *, path: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise MetricSerializationError("invalid_string", f"{path}.{key}")
    return value


def _encode_coverage(coverage: MetricCoverage | None) -> dict[str, Any] | None:
    if coverage is None:
        return None
    payload: dict[str, Any] = {
        "observed": coverage.observed,
        "expected": coverage.expected,
    }
    if coverage.ratio is not None:
        payload["ratio"] = coverage.ratio
    return payload


def _decode_coverage(raw: object, *, path: str) -> MetricCoverage | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise MetricSerializationError("invalid_object", path)
    allowed = frozenset({"observed", "expected", "ratio"})
    keys = frozenset(raw)
    if "observed" not in keys or "expected" not in keys:
        raise MetricSerializationError("missing_field", path)
    if keys - allowed:
        raise MetricSerializationError("unknown_field", path)
    observed = raw["observed"]
    expected = raw["expected"]
    if isinstance(observed, bool) or not isinstance(observed, int) or observed < 0:
        raise MetricSerializationError("invalid_int", f"{path}.observed")
    if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
        raise MetricSerializationError("invalid_int", f"{path}.expected")
    ratio: float | None = None
    if "ratio" in raw and raw["ratio"] is not None:
        value = raw["ratio"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MetricSerializationError("invalid_number", f"{path}.ratio")
        try:
            ratio = quantize_float(require_finite(float(value)))
        except NumericalPolicyError as exc:
            raise MetricSerializationError(exc.code, f"{path}.ratio") from exc
    try:
        return MetricCoverage(observed=observed, expected=expected, ratio=ratio)
    except (TypeError, ValueError) as exc:
        raise MetricSerializationError("invalid_model", path) from exc


def _encode_provenance(provenance: MetricProvenance) -> dict[str, Any]:
    return {
        "source_kind": provenance.source_kind,
        "source_ids": list(provenance.source_ids),
        "notes_code": provenance.notes_code,
    }


def _decode_provenance(raw: object, *, path: str) -> MetricProvenance:
    if not isinstance(raw, dict):
        raise MetricSerializationError("invalid_object", path)
    _require_keys(
        raw, frozenset({"source_kind", "source_ids", "notes_code"}), path=path
    )
    source_ids_raw = raw["source_ids"]
    if not isinstance(source_ids_raw, list):
        raise MetricSerializationError("invalid_array", f"{path}.source_ids")
    source_ids: list[str] = []
    for index, item in enumerate(source_ids_raw):
        if not isinstance(item, str):
            raise MetricSerializationError(
                "invalid_string", f"{path}.source_ids[{index}]"
            )
        source_ids.append(item)
    notes = raw["notes_code"]
    if notes is not None and not isinstance(notes, str):
        raise MetricSerializationError("invalid_string", f"{path}.notes_code")
    try:
        return MetricProvenance(
            source_kind=_str_field(raw, "source_kind", path=path),
            source_ids=tuple(source_ids),
            notes_code=notes,
        )
    except (TypeError, ValueError) as exc:
        raise MetricSerializationError("invalid_model", path) from exc


def _encode_values(values: Mapping[str, object]) -> dict[str, object]:
    encoded: dict[str, object] = {}
    for key in sorted(values):
        value = values[key]
        if value is None or isinstance(value, (str, bool, int)):
            if type(value) is bool or value is None or isinstance(value, str):
                encoded[key] = value
            elif type(value) is int:
                encoded[key] = value
            else:
                raise MetricSerializationError("invalid_value", f"$.values.{key}")
        elif type(value) is float:
            try:
                encoded[key] = quantize_float(require_finite(value))
            except NumericalPolicyError as exc:
                raise MetricSerializationError(exc.code, f"$.values.{key}") from exc
        else:
            raise MetricSerializationError("invalid_value", f"$.values.{key}")
    return encoded


def _decode_values(raw: object, *, path: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise MetricSerializationError("invalid_object", path)
    decoded: dict[str, object] = {}
    for key in sorted(raw):
        if not isinstance(key, str):
            raise MetricSerializationError("invalid_string", path)
        value = raw[key]
        if value is None or type(value) is bool or isinstance(value, str):
            decoded[key] = value
        elif type(value) is int:
            decoded[key] = value
        elif isinstance(value, float):
            try:
                decoded[key] = quantize_float(require_finite(float(value)))
            except NumericalPolicyError as exc:
                raise MetricSerializationError(exc.code, f"{path}.{key}") from exc
        else:
            raise MetricSerializationError("invalid_value", f"{path}.{key}")
    return decoded


def encode_metric_document(document: MetricDocument) -> bytes:
    """Encode a metric document as canonical UTF-8 JSON bytes."""
    if type(document) is not MetricDocument:
        raise MetricSerializationError("invalid_model", "$")
    payload = {
        "schema_version": document.schema_version,
        "metric_family": document.metric_family,
        "algorithm_version": document.algorithm_version,
        "library_versions": dict(
            sorted(
                (key, document.library_versions[key])
                for key in document.library_versions
            )
        ),
        "run_id": document.run_id,
        "input_revision": document.input_revision,
        "evidence_stages": sorted(stage.value for stage in document.evidence_stages),
        "population": document.population,
        "denominator": document.denominator,
        "coverage": _encode_coverage(document.coverage),
        "availability": document.availability.value,
        "values": _encode_values(document.values),
        "provenance": _encode_provenance(document.provenance),
    }
    try:
        return _canonical_dumps(payload)
    except (TypeError, ValueError) as exc:
        raise MetricSerializationError("canonical_encode_failed", "$") from exc


def decode_metric_document(payload: bytes | str | Mapping[str, Any]) -> MetricDocument:
    """Decode a metric document; reject unknown fields and non-finite values."""
    if isinstance(payload, Mapping):
        data = dict(payload)
    else:
        if isinstance(payload, bytes):
            try:
                text = payload.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise MetricSerializationError("invalid_encoding", "$") from exc
        elif isinstance(payload, str):
            text = payload
        else:
            raise MetricSerializationError("invalid_payload", "$")
        try:
            decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_keys)
            raw = decoder.decode(text)
        except MetricSerializationError:
            raise
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise MetricSerializationError("invalid_json", "$") from exc
        if not isinstance(raw, dict):
            raise MetricSerializationError("invalid_object", "$")
        data = raw

    _require_keys(data, _REQUIRED_FIELDS, path="$")
    schema_version = _str_field(data, "schema_version", path="$")
    if schema_version != METRIC_DOCUMENT_SCHEMA_VERSION:
        raise MetricSerializationError("unsupported_version", "$.schema_version")

    library_raw = data["library_versions"]
    if not isinstance(library_raw, dict):
        raise MetricSerializationError("invalid_object", "$.library_versions")
    library_versions: dict[str, str] = {}
    for key in sorted(library_raw):
        if not isinstance(key, str) or not isinstance(library_raw[key], str):
            raise MetricSerializationError("invalid_string", "$.library_versions")
        library_versions[key] = library_raw[key]

    stages_raw = data["evidence_stages"]
    if not isinstance(stages_raw, list):
        raise MetricSerializationError("invalid_array", "$.evidence_stages")
    stages: list[EvidenceStage] = []
    for index, item in enumerate(stages_raw):
        try:
            stages.append(
                require_evidence_stage(f"$.evidence_stages[{index}]", item)
            )
        except (TypeError, ValueError) as exc:
            raise MetricSerializationError(
                "invalid_enum", f"$.evidence_stages[{index}]"
            ) from exc

    try:
        availability = MetricAvailability(_str_field(data, "availability", path="$"))
    except ValueError as exc:
        raise MetricSerializationError("invalid_enum", "$.availability") from exc

    try:
        run_id = require_stable_id("run_id", _str_field(data, "run_id", path="$"))
    except (TypeError, ValueError) as exc:
        raise MetricSerializationError("invalid_id", "$.run_id") from exc

    try:
        return MetricDocument(
            schema_version=schema_version,
            metric_family=_str_field(data, "metric_family", path="$"),
            algorithm_version=_str_field(data, "algorithm_version", path="$"),
            library_versions=library_versions,
            run_id=run_id,
            input_revision=_str_field(data, "input_revision", path="$"),
            evidence_stages=frozenset(stages),
            population=_str_field(data, "population", path="$"),
            denominator=_str_field(data, "denominator", path="$"),
            coverage=_decode_coverage(data["coverage"], path="$.coverage"),
            availability=availability,
            values=_decode_values(data["values"], path="$.values"),
            provenance=_decode_provenance(data["provenance"], path="$.provenance"),
        )
    except MetricSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise MetricSerializationError("invalid_model", "$") from exc


def metric_document_fingerprint(document: MetricDocument) -> str:
    """SHA-256 hex digest of the canonical metric document encoding."""
    import hashlib

    return hashlib.sha256(encode_metric_document(document)).hexdigest()
