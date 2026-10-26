"""Structural validation for stored cultural research artifacts.

This module deliberately duplicates the published wire key sets instead of
importing ``analysis`` or ``experiments``. Validation here proves read safety
and identity binding; it is not a scientific re-analysis of the artifact.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Final

CULTURAL_COMPARISON_SCHEMA_VERSION: Final[str] = "cultural-metric-comparison-v1"
CULTURAL_CELL_METRICS_SCHEMA_VERSION: Final[str] = "cultural-cell-metrics-v1"
MAX_OUTER_ARTIFACT_BYTES: Final[int] = 64 * 1024 * 1024
MAX_OUTER_ARTIFACT_DEPTH: Final[int] = 32
MAX_ROWS_JSON_BYTES: Final[int] = 16 * 1024 * 1024
MAX_ROWS_JSON_DEPTH: Final[int] = 32

_COMPARISON_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "matrix_fingerprint",
        "confidence",
        "method",
        "conditions",
        "contrasts",
        "excluded_cells",
        "reasons",
    }
)
_CELL_METRICS_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "cell_id",
        "matrix_fingerprint",
        "cell_fingerprint",
        "config_fingerprint",
        "run_id",
        "capture_policy",
        "analysis_window",
        "evidence_digest",
        "documents",
        "digest",
    }
)
_WINDOW_KEYS: Final[frozenset[str]] = frozenset({"baseline_boundary", "end_boundary"})
_CAPTURE_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {"enabled", "max_frames", "max_rows"}
)


class CulturalArtifactSchemaError(ValueError):
    """Safe structural failure code without artifact fragments."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def duplicate_aware_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CulturalArtifactSchemaError("duplicate_key")
        result[key] = value
    return result


def reject_nonfinite(value: str) -> object:
    raise CulturalArtifactSchemaError("nonfinite_number")


def depth_ok(data: bytes, *, maximum: int = MAX_OUTER_ARTIFACT_DEPTH) -> bool:
    depth = 0
    quoted = False
    escaped = False
    for byte in data:
        char = chr(byte)
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char in "{[":
            depth += 1
            if depth > maximum:
                return False
        elif char in "}]":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _require_mapping(value: object, code: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CulturalArtifactSchemaError(code)
    if any(not isinstance(key, str) for key in value):
        raise CulturalArtifactSchemaError(code)
    return value


def _require_list(value: object, code: str) -> Sequence[object]:
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(
        value, Sequence
    ):
        raise CulturalArtifactSchemaError(code)
    return value


def _require_str(value: object, code: str, *, hex64: bool = False) -> str:
    if not isinstance(value, str) or value == "":
        raise CulturalArtifactSchemaError(code)
    if hex64 and (len(value) != 64 or any(c not in "0123456789abcdef" for c in value)):
        raise CulturalArtifactSchemaError(code)
    return value


def _require_nonneg_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CulturalArtifactSchemaError(code)
    return value


def validate_comparison(payload: object) -> str:
    """Validate the comparison envelope and return its matrix fingerprint."""
    body = _require_mapping(payload, "invalid_comparison")
    if body.get("schema_version") != CULTURAL_COMPARISON_SCHEMA_VERSION:
        raise CulturalArtifactSchemaError("unsupported_schema")
    if set(body) != _COMPARISON_KEYS:
        raise CulturalArtifactSchemaError("key_set_mismatch")
    fingerprint = _require_str(
        body["matrix_fingerprint"], "invalid_matrix_fingerprint", hex64=True
    )
    confidence = body["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise CulturalArtifactSchemaError("invalid_comparison")
    _require_str(body["method"], "invalid_comparison")
    _require_list(body["conditions"], "invalid_comparison")
    _require_list(body["contrasts"], "invalid_comparison")
    _require_list(body["excluded_cells"], "invalid_comparison")
    _require_list(body["reasons"], "invalid_comparison")
    return fingerprint


def _validate_scalar_row(row: object) -> None:
    mapping = _require_mapping(row, "invalid_rows_json")
    for value in mapping.values():
        if value is None or isinstance(value, (bool, int, float, str)):
            continue
        if isinstance(value, list):
            for item in value:
                if item is not None and not isinstance(item, (bool, int, float, str)):
                    raise CulturalArtifactSchemaError("invalid_rows_json")
            continue
        raise CulturalArtifactSchemaError("invalid_rows_json")


def validate_rows_json(raw: object) -> None:
    if not isinstance(raw, str):
        raise CulturalArtifactSchemaError("invalid_rows_json")
    try:
        data = raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CulturalArtifactSchemaError("invalid_rows_json") from exc
    if len(data) > MAX_ROWS_JSON_BYTES:
        raise CulturalArtifactSchemaError("rows_json_too_large")
    if not depth_ok(data, maximum=MAX_ROWS_JSON_DEPTH):
        raise CulturalArtifactSchemaError("excessive_depth")
    try:
        rows = json.loads(
            raw,
            object_pairs_hook=duplicate_aware_pairs,
            parse_constant=reject_nonfinite,
        )
    except CulturalArtifactSchemaError:
        raise
    except (TypeError, ValueError) as exc:
        raise CulturalArtifactSchemaError("invalid_rows_json") from exc
    if not isinstance(rows, list):
        raise CulturalArtifactSchemaError("invalid_rows_json")
    for row in rows:
        _validate_scalar_row(row)


def validate_cell_metrics(payload: object) -> dict[str, str]:
    """Validate a cell-metrics envelope and return its bound identities."""
    body = _require_mapping(payload, "invalid_cell_metrics")
    if body.get("schema_version") != CULTURAL_CELL_METRICS_SCHEMA_VERSION:
        raise CulturalArtifactSchemaError("unsupported_schema")
    if set(body) != _CELL_METRICS_KEYS:
        raise CulturalArtifactSchemaError("key_set_mismatch")
    digest = _require_str(body["digest"], "invalid_digest", hex64=True)
    without_digest = {key: value for key, value in body.items() if key != "digest"}
    if hashlib.sha256(canonical_bytes(without_digest)).hexdigest() != digest:
        raise CulturalArtifactSchemaError("digest_mismatch")
    window = _require_mapping(body["analysis_window"], "invalid_window")
    if set(window) != _WINDOW_KEYS:
        raise CulturalArtifactSchemaError("invalid_window")
    _require_nonneg_int(window["baseline_boundary"], "invalid_window")
    if window["end_boundary"] is not None:
        _require_nonneg_int(window["end_boundary"], "invalid_window")
    policy = _require_mapping(body["capture_policy"], "invalid_capture_policy")
    if set(policy) != _CAPTURE_POLICY_KEYS:
        raise CulturalArtifactSchemaError("invalid_capture_policy")
    documents = _require_list(body["documents"], "invalid_documents")
    for document in documents:
        item = _require_mapping(document, "invalid_documents")
        values = item.get("values")
        if values is None:
            continue
        value_map = _require_mapping(values, "invalid_documents")
        if "rows_json" in value_map:
            validate_rows_json(value_map["rows_json"])
    return {
        "cell_id": _require_str(body["cell_id"], "invalid_cell_id"),
        "matrix_fingerprint": _require_str(
            body["matrix_fingerprint"], "invalid_matrix_fingerprint", hex64=True
        ),
        "cell_fingerprint": _require_str(
            body["cell_fingerprint"], "invalid_cell_fingerprint", hex64=True
        ),
        "config_fingerprint": _require_str(
            body["config_fingerprint"], "invalid_config_fingerprint", hex64=True
        ),
        "run_id": _require_str(body["run_id"], "invalid_run_id"),
        "evidence_digest": _require_str(
            body["evidence_digest"], "invalid_evidence_digest", hex64=True
        ),
        "digest": digest,
    }


CULTURAL_EVIDENCE_SCHEMA_VERSION: Final[str] = "cultural-evolution-evidence-v1"
MAX_EVIDENCE_ROWS: Final[int] = 1_000_000

_EVIDENCE_ENVELOPE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "run_id",
        "config_fingerprint",
        "source_revision",
        "policy_version",
        "capture_options",
        "analysis_window",
        "boundaries",
        "trait_rows",
        "transmission_edges",
        "group_memberships",
        "archive_states",
        "evidence_pointers",
        "gaps",
        "capture_status",
        "digest",
    }
)
_EVIDENCE_BOUNDARY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "boundary_tick",
        "living_owner_ids",
        "generation_by_owner",
        "owner_dimension_coverage",
    }
)
_EVIDENCE_TRAIT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "boundary_tick",
        "owner_id",
        "local_entry_id",
        "dimension",
        "content_digest",
        "lineage_key",
        "acquisition_tick",
        "parent_refs",
        "source_refs",
        "status",
    }
)
_EVIDENCE_EDGE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "edge_id",
        "source_owner_id",
        "receiver_owner_id",
        "source_local_id",
        "receiver_local_id",
        "acquisition_boundary",
        "modality",
        "attribution_status",
        "generation_class",
        "kin_vertical",
        "source_digest",
        "target_digest",
        "mutated",
        "recombined",
        "evidence_ids",
    }
)
_EVIDENCE_GROUP_KEYS: Final[frozenset[str]] = frozenset(
    {
        "boundary_tick",
        "owner_id",
        "group_id",
        "basis_id",
        "basis_version",
        "evidence_ids",
    }
)
_EVIDENCE_ARCHIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "boundary_tick",
        "subject_id",
        "content_digest",
        "record_present",
        "holder_owner_ids",
        "provenance_source_ids",
        "evidence_ids",
    }
)
_EVIDENCE_POINTER_KEYS: Final[frozenset[str]] = frozenset(
    {
        "run_id",
        "owner_id",
        "boundary_tick",
        "source_kind",
        "local_id",
        "source_revision_digest",
        "original_refs",
    }
)
_EVIDENCE_STATUS_KEYS: Final[frozenset[str]] = frozenset(
    {
        "active",
        "failed",
        "failure_boundary",
        "failure_code",
        "missing_prefix_through",
    }
)


def _exact_row(row: object, keys: frozenset[str], code: str) -> Mapping[str, object]:
    mapping = _require_mapping(row, code)
    if set(mapping) != keys:
        raise CulturalArtifactSchemaError(code)
    return mapping


def validate_cultural_evidence(payload: object) -> dict[str, object]:
    """Validate the evidence envelope and return bound identity plus payload."""
    body = _require_mapping(payload, "invalid_evidence")
    if body.get("schema_version") != CULTURAL_EVIDENCE_SCHEMA_VERSION:
        raise CulturalArtifactSchemaError("unsupported_schema")
    if set(body) != _EVIDENCE_ENVELOPE_KEYS:
        raise CulturalArtifactSchemaError("key_set_mismatch")
    digest = _require_str(body["digest"], "invalid_digest", hex64=True)
    without_digest = {key: value for key, value in body.items() if key != "digest"}
    if hashlib.sha256(canonical_bytes(without_digest)).hexdigest() != digest:
        raise CulturalArtifactSchemaError("digest_mismatch")
    for key in ("run_id", "config_fingerprint", "source_revision", "policy_version"):
        _require_str(body[key], "invalid_evidence")
    window = _require_mapping(body["analysis_window"], "invalid_window")
    if set(window) != _WINDOW_KEYS:
        raise CulturalArtifactSchemaError("invalid_window")
    _require_nonneg_int(window["baseline_boundary"], "invalid_window")
    if window["end_boundary"] is not None:
        _require_nonneg_int(window["end_boundary"], "invalid_window")
    _require_mapping(body["capture_options"], "invalid_capture_policy")
    _require_mapping(body["capture_status"], "invalid_capture_status")
    if set(_require_mapping(body["capture_status"], "invalid_capture_status")) != (
        _EVIDENCE_STATUS_KEYS
    ):
        raise CulturalArtifactSchemaError("invalid_capture_status")
    boundaries = _require_list(body["boundaries"], "invalid_boundaries")
    traits = _require_list(body["trait_rows"], "invalid_trait_rows")
    edges = _require_list(body["transmission_edges"], "invalid_edges")
    groups = _require_list(body["group_memberships"], "invalid_groups")
    archives = _require_list(body["archive_states"], "invalid_archives")
    pointers = _require_list(body["evidence_pointers"], "invalid_pointers")
    if len(boundaries) + len(traits) > MAX_EVIDENCE_ROWS:
        raise CulturalArtifactSchemaError("row_limit")
    for row in boundaries:
        _exact_row(row, _EVIDENCE_BOUNDARY_KEYS, "invalid_boundary")
    for row in traits:
        _exact_row(row, _EVIDENCE_TRAIT_KEYS, "invalid_trait_row")
    for row in edges:
        _exact_row(row, _EVIDENCE_EDGE_KEYS, "invalid_edge")
    for row in groups:
        _exact_row(row, _EVIDENCE_GROUP_KEYS, "invalid_group")
    for row in archives:
        _exact_row(row, _EVIDENCE_ARCHIVE_KEYS, "invalid_archive")
    for row in pointers:
        _exact_row(row, _EVIDENCE_POINTER_KEYS, "invalid_pointer")
    _require_list(body["gaps"], "invalid_gaps")
    return {
        "digest": digest,
        "run_id": body["run_id"],
        "config_fingerprint": body["config_fingerprint"],
        "source_revision": body["source_revision"],
        "analysis_window": window,
        "capture_options": body["capture_options"],
        "capture_status": body["capture_status"],
        "gaps": body["gaps"],
    }
