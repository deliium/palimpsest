"""Versioned cognition-trace-v1 codec (canonical bytes + content_hash).

Persistence adapters must store codec output only — no ad-hoc JSON in ORM.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any, Final

from agents.cognition.models import DecisionMetadata, UncertaintyBand
from agents.cognition.trace import (
    CognitionTraceIdRef,
    CognitionTraceLlmMeta,
    CognitionTraceRefKind,
    CognitionTraceStageKind,
    CognitionTraceStageStatus,
    CognitionTraceStageSummary,
)
from agents.models import AgentId
from simulation.cognition_trace import (
    COGNITION_TRACE_SCHEMA_VERSION,
    CognitionTraceInvocation,
    CognitionTraceStageRecord,
    build_cognition_trace_invocation,
)
from simulation.models import RunId

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.cognition_trace_serialization"
)

__all__ = [
    "ACCEPTED_COGNITION_TRACE_SCHEMA_VERSIONS",
    "COGNITION_TRACE_SCHEMA_VERSION",
    "CognitionTraceSerializationError",
    "cognition_trace_content_hash",
    "decode_cognition_trace_invocation",
    "encode_cognition_trace_invocation",
]

ACCEPTED_COGNITION_TRACE_SCHEMA_VERSIONS: Final[frozenset[str]] = frozenset(
    {COGNITION_TRACE_SCHEMA_VERSION}
)

_INVOCATION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "run_id",
        "agent_id",
        "tick",
        "invocation_id",
        "stages",
        "command_kind",
        "final_confidence",
        "content_hash",
    }
)


class CognitionTraceSerializationError(ValueError):
    """Codec failure with stable ``code`` and JSON ``path``."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"code={code} path={path}")


def encode_cognition_trace_invocation(invocation: CognitionTraceInvocation) -> bytes:
    """Encode an invocation to strict canonical UTF-8 JSON bytes."""
    if type(invocation) is not CognitionTraceInvocation:
        raise TypeError(
            "encode_cognition_trace_invocation requires CognitionTraceInvocation"
        )
    document = _encode_document(invocation)
    # Content hash is over the payload excluding the hash field itself.
    payload_for_hash = {
        key: value for key, value in document.items() if key != "content_hash"
    }
    digest = _sha256_hex(_canonical_dumps(payload_for_hash))
    document["content_hash"] = digest
    encoded = _canonical_dumps(document)
    _LOG.debug(
        "cognition_trace_encoded",
        extra={
            "schema_version": invocation.schema_version,
            "hash_prefix": digest[:12],
            "stage_count": len(invocation.stages),
        },
    )
    return encoded


def cognition_trace_content_hash(invocation: CognitionTraceInvocation) -> str:
    """Return the durable content hash for an invocation (codec identity)."""
    document = _encode_document(invocation)
    payload_for_hash = {
        key: value for key, value in document.items() if key != "content_hash"
    }
    return _sha256_hex(_canonical_dumps(payload_for_hash))


def decode_cognition_trace_invocation(payload: bytes) -> CognitionTraceInvocation:
    """Decode strict canonical cognition-trace bytes."""
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("decode_cognition_trace_invocation requires bytes")
    try:
        decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_keys)
        data = decoder.decode(bytes(payload).decode("utf-8"))
    except CognitionTraceSerializationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CognitionTraceSerializationError("invalid_json", "$") from exc
    if not isinstance(data, dict):
        raise CognitionTraceSerializationError("invalid_object", "$")
    _require_keys(data, _INVOCATION_KEYS, path="$")
    schema_version = data["schema_version"]
    if not isinstance(schema_version, str):
        raise CognitionTraceSerializationError("invalid_string", "$.schema_version")
    if schema_version not in ACCEPTED_COGNITION_TRACE_SCHEMA_VERSIONS:
        _LOG.error(
            "cognition_trace_unsupported_version",
            extra={
                "reason_code": "unsupported_version",
                "schema_version": schema_version,
            },
        )
        raise CognitionTraceSerializationError(
            "unsupported_version", "$.schema_version"
        )
    stages_raw = data["stages"]
    if not isinstance(stages_raw, list):
        raise CognitionTraceSerializationError("invalid_array", "$.stages")
    summaries: list[CognitionTraceStageSummary] = []
    for index, item in enumerate(stages_raw):
        if not isinstance(item, dict):
            raise CognitionTraceSerializationError(
                "invalid_object", f"$.stages[{index}]"
            )
        summaries.append(_decode_stage_summary(item, path=f"$.stages[{index}]"))
    try:
        run_id = RunId(_require_str(data, "run_id", path="$"))
        agent_id = AgentId(_require_str(data, "agent_id", path="$"))
        tick = _require_nonneg_int(data, "tick", path="$")
        invocation_id = _require_str(data, "invocation_id", path="$")
        command_kind = data["command_kind"]
        if command_kind is not None and not isinstance(command_kind, str):
            raise CognitionTraceSerializationError(
                "invalid_string", "$.command_kind"
            )
        final_confidence = data["final_confidence"]
        if final_confidence is not None and (
            isinstance(final_confidence, bool)
            or not isinstance(final_confidence, (int, float))
        ):
            raise CognitionTraceSerializationError(
                "invalid_number", "$.final_confidence"
            )
        stored_hash = _require_str(data, "content_hash", path="$")
        invocation = build_cognition_trace_invocation(
            run_id=run_id,
            agent_id=agent_id,
            tick=tick,
            invocation_id=invocation_id,
            stage_summaries=summaries,
            command_kind=command_kind,
            final_confidence=(
                None if final_confidence is None else float(final_confidence)
            ),
            content_hash=stored_hash,
        )
    except CognitionTraceSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise CognitionTraceSerializationError("invalid_model", "$") from exc
    expected = cognition_trace_content_hash(invocation)
    if expected != stored_hash:
        raise CognitionTraceSerializationError("hash_mismatch", "$.content_hash")
    _LOG.debug(
        "cognition_trace_decoded",
        extra={
            "schema_version": schema_version,
            "hash_prefix": stored_hash[:12],
            "stage_count": len(summaries),
        },
    )
    return invocation


def _encode_document(invocation: CognitionTraceInvocation) -> dict[str, Any]:
    return {
        "agent_id": invocation.agent_id.value,
        "command_kind": invocation.command_kind,
        "content_hash": invocation.content_hash,
        "final_confidence": invocation.final_confidence,
        "invocation_id": invocation.invocation_id,
        "run_id": invocation.run_id.value,
        "schema_version": invocation.schema_version,
        "stages": [_encode_stage(stage) for stage in invocation.stages],
        "tick": invocation.tick,
    }


def _encode_stage(stage: CognitionTraceStageRecord) -> dict[str, Any]:
    summary = stage.summary
    decision = None
    if summary.decision_metadata is not None:
        decision = {
            "candidate_count": summary.decision_metadata.candidate_count,
            "selection_codes": list(summary.decision_metadata.selection_codes),
            "tie_break_applied": summary.decision_metadata.tie_break_applied,
        }
    llm = None
    if summary.llm_meta is not None:
        llm = {
            "attempts": summary.llm_meta.attempts,
            "finish_reason": summary.llm_meta.finish_reason,
            "input_tokens": summary.llm_meta.input_tokens,
            "model_name": summary.llm_meta.model_name,
            "output_tokens": summary.llm_meta.output_tokens,
            "provider_name": summary.llm_meta.provider_name,
            "total_tokens": summary.llm_meta.total_tokens,
        }
    return {
        "command_kind": summary.command_kind,
        "confidence": summary.confidence,
        "counts": None if summary.counts is None else dict(summary.counts),
        "decision_metadata": decision,
        "id_refs": [
            {"kind": ref.kind.value, "value": ref.value} for ref in summary.id_refs
        ],
        "intention_code": summary.intention_code,
        "llm_meta": llm,
        "ordinal": summary.ordinal,
        "reason_code": summary.reason_code,
        "schema_version": summary.schema_version,
        "selection_codes": list(summary.selection_codes),
        "stage_kind": summary.stage_kind.value,
        "status": summary.status.value,
        "uncertainty_band": (
            None if summary.uncertainty_band is None else summary.uncertainty_band.value
        ),
    }


def _decode_stage_summary(
    data: Mapping[str, Any], *, path: str
) -> CognitionTraceStageSummary:
    required = {
        "stage_kind",
        "status",
        "ordinal",
        "confidence",
        "uncertainty_band",
        "selection_codes",
        "id_refs",
        "counts",
        "reason_code",
        "decision_metadata",
        "command_kind",
        "intention_code",
        "llm_meta",
        "schema_version",
    }
    _require_keys(data, required, path=path)
    try:
        stage_kind = CognitionTraceStageKind(
            _require_str(data, "stage_kind", path=path)
        )
        status = CognitionTraceStageStatus(_require_str(data, "status", path=path))
    except ValueError as exc:
        raise CognitionTraceSerializationError("invalid_enum", path) from exc
    selection_codes_raw = data["selection_codes"]
    if not isinstance(selection_codes_raw, list):
        raise CognitionTraceSerializationError(
            "invalid_array", f"{path}.selection_codes"
        )
    selection_codes = tuple(
        _require_list_str(selection_codes_raw, path=f"{path}.selection_codes")
    )
    id_refs_raw = data["id_refs"]
    if not isinstance(id_refs_raw, list):
        raise CognitionTraceSerializationError("invalid_array", f"{path}.id_refs")
    id_refs: list[CognitionTraceIdRef] = []
    for index, item in enumerate(id_refs_raw):
        if not isinstance(item, dict):
            raise CognitionTraceSerializationError(
                "invalid_object", f"{path}.id_refs[{index}]"
            )
        _require_keys(item, {"kind", "value"}, path=f"{path}.id_refs[{index}]")
        try:
            kind = CognitionTraceRefKind(
                _require_str(item, "kind", path=f"{path}.id_refs[{index}]")
            )
        except ValueError as exc:
            raise CognitionTraceSerializationError(
                "invalid_enum", f"{path}.id_refs[{index}].kind"
            ) from exc
        id_refs.append(
            CognitionTraceIdRef(
                kind=kind,
                value=_require_str(item, "value", path=f"{path}.id_refs[{index}]"),
            )
        )
    counts = data["counts"]
    if counts is not None and not isinstance(counts, dict):
        raise CognitionTraceSerializationError("invalid_object", f"{path}.counts")
    band_raw = data["uncertainty_band"]
    band = None
    if band_raw is not None:
        try:
            band = UncertaintyBand(
                _require_str_value(band_raw, f"{path}.uncertainty_band")
            )
        except ValueError as exc:
            raise CognitionTraceSerializationError(
                "invalid_enum", f"{path}.uncertainty_band"
            ) from exc
    decision = None
    decision_raw = data["decision_metadata"]
    if decision_raw is not None:
        if not isinstance(decision_raw, dict):
            raise CognitionTraceSerializationError(
                "invalid_object", f"{path}.decision_metadata"
            )
        _require_keys(
            decision_raw,
            {"selection_codes", "candidate_count", "tie_break_applied"},
            path=f"{path}.decision_metadata",
        )
        codes = decision_raw["selection_codes"]
        if not isinstance(codes, list):
            raise CognitionTraceSerializationError(
                "invalid_array", f"{path}.decision_metadata.selection_codes"
            )
        decision = DecisionMetadata(
            selection_codes=tuple(
                _require_list_str(
                    codes, path=f"{path}.decision_metadata.selection_codes"
                )
            ),
            candidate_count=_require_nonneg_int(
                decision_raw, "candidate_count", path=f"{path}.decision_metadata"
            ),
            tie_break_applied=_require_bool(
                decision_raw, "tie_break_applied", path=f"{path}.decision_metadata"
            ),
        )
    llm = None
    llm_raw = data["llm_meta"]
    if llm_raw is not None:
        if not isinstance(llm_raw, dict):
            raise CognitionTraceSerializationError(
                "invalid_object", f"{path}.llm_meta"
            )
        _require_keys(
            llm_raw,
            {
                "provider_name",
                "model_name",
                "finish_reason",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "attempts",
            },
            path=f"{path}.llm_meta",
        )
        llm = CognitionTraceLlmMeta(
            provider_name=_optional_str(
                llm_raw, "provider_name", path=f"{path}.llm_meta"
            ),
            model_name=_optional_str(
                llm_raw, "model_name", path=f"{path}.llm_meta"
            ),
            finish_reason=_optional_str(
                llm_raw, "finish_reason", path=f"{path}.llm_meta"
            ),
            input_tokens=_optional_nonneg_int(
                llm_raw, "input_tokens", path=f"{path}.llm_meta"
            ),
            output_tokens=_optional_nonneg_int(
                llm_raw, "output_tokens", path=f"{path}.llm_meta"
            ),
            total_tokens=_optional_nonneg_int(
                llm_raw, "total_tokens", path=f"{path}.llm_meta"
            ),
            attempts=_optional_nonneg_int(llm_raw, "attempts", path=f"{path}.llm_meta"),
        )
    confidence = data["confidence"]
    if confidence is not None and (
        isinstance(confidence, bool) or not isinstance(confidence, (int, float))
    ):
        raise CognitionTraceSerializationError("invalid_number", f"{path}.confidence")
    command_kind = data["command_kind"]
    if command_kind is not None and not isinstance(command_kind, str):
        raise CognitionTraceSerializationError(
            "invalid_string", f"{path}.command_kind"
        )
    intention_code = data["intention_code"]
    if intention_code is not None and not isinstance(intention_code, str):
        raise CognitionTraceSerializationError(
            "invalid_string", f"{path}.intention_code"
        )
    reason_code = data["reason_code"]
    if reason_code is not None and not isinstance(reason_code, str):
        raise CognitionTraceSerializationError(
            "invalid_string", f"{path}.reason_code"
        )
    try:
        return CognitionTraceStageSummary(
            stage_kind=stage_kind,
            status=status,
            ordinal=_require_nonneg_int(data, "ordinal", path=path),
            confidence=None if confidence is None else float(confidence),
            uncertainty_band=band,
            selection_codes=selection_codes,
            id_refs=tuple(id_refs),
            counts=counts,
            reason_code=reason_code,
            decision_metadata=decision,
            command_kind=command_kind,
            intention_code=intention_code,
            llm_meta=llm,
            schema_version=_require_str(data, "schema_version", path=path),
        )
    except (TypeError, ValueError) as exc:
        raise CognitionTraceSerializationError("invalid_model", path) from exc


def _canonical_dumps(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _reject_duplicate_keys(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CognitionTraceSerializationError("duplicate_key", f"$.{key}")
        result[key] = value
    return result


def _require_keys(
    data: Mapping[str, Any], required: set[str] | frozenset[str], *, path: str
) -> None:
    keys = set(data)
    missing = required - keys
    extra = keys - required
    if missing:
        raise CognitionTraceSerializationError("missing_field", path)
    if extra:
        raise CognitionTraceSerializationError("invalid_fields", path)


def _require_str(data: Mapping[str, Any], key: str, *, path: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise CognitionTraceSerializationError("invalid_string", f"{path}.{key}")
    return value


def _require_str_value(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise CognitionTraceSerializationError("invalid_string", path)
    return value


def _require_nonneg_int(data: Mapping[str, Any], key: str, *, path: str) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CognitionTraceSerializationError("invalid_int", f"{path}.{key}")
    return value


def _require_bool(data: Mapping[str, Any], key: str, *, path: str) -> bool:
    value = data[key]
    if type(value) is not bool:
        raise CognitionTraceSerializationError("invalid_bool", f"{path}.{key}")
    return value


def _require_list_str(values: Sequence[object], *, path: str) -> list[str]:
    result: list[str] = []
    for index, item in enumerate(values):
        if not isinstance(item, str):
            raise CognitionTraceSerializationError(
                "invalid_string", f"{path}[{index}]"
            )
        result.append(item)
    return result


def _optional_str(
    data: Mapping[str, Any], key: str, *, path: str
) -> str | None:
    value = data[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise CognitionTraceSerializationError("invalid_string", f"{path}.{key}")
    return value


def _optional_nonneg_int(
    data: Mapping[str, Any], key: str, *, path: str
) -> int | None:
    value = data[key]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CognitionTraceSerializationError("invalid_int", f"{path}.{key}")
    return value
