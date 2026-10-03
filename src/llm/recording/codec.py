"""Exact key-set canonical JSON codec for ``llm-exchange-v1`` records.

Codec helpers are log-free. Unknown schema versions and key-set drift fail closed.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Final

from llm.models import StructuredOutputMode
from llm.recording.models import (
    LLM_EXCHANGE_SCHEMA_ID,
    ExchangeCorrelation,
    ExchangeEffectiveOptions,
    ExchangePromptRef,
    ExchangeUsage,
    ExchangeValidation,
    ExchangeValidationStatus,
    LLMExchangeRecord,
    SchemaIdentity,
)

_TOP_LEVEL_REQUIRED: Final[frozenset[str]] = frozenset(
    {
        "schema_id",
        "provider",
        "model",
        "structured_output_mode",
        "schema_identity",
        "prompt",
        "request_digest",
        "effective_options",
        "validation",
        "response",
        "usage",
        "latency_ms",
        "correlation",
        "component",
        "cache_namespace",
    }
)
_TOP_LEVEL_OPTIONAL: Final[frozenset[str]] = frozenset(
    {"recorded_at_monotonic_offset"}
)
_TOP_LEVEL_ALLOWED: Final[frozenset[str]] = _TOP_LEVEL_REQUIRED | _TOP_LEVEL_OPTIONAL

_SCHEMA_IDENTITY_KEYS: Final[frozenset[str]] = frozenset({"qualname", "digest"})
_PROMPT_KEYS: Final[frozenset[str]] = frozenset({"name", "version", "digest"})
_OPTIONS_KEYS: Final[frozenset[str]] = frozenset(
    {"temperature", "max_output_tokens", "top_p", "seed", "stop"}
)
_VALIDATION_KEYS: Final[frozenset[str]] = frozenset({"status", "reason_code"})
_USAGE_KEYS: Final[frozenset[str]] = frozenset(
    {"input_tokens", "output_tokens", "total_tokens"}
)
_CORRELATION_REQUIRED: Final[frozenset[str]] = frozenset(
    {"run_id", "agent_id", "tick", "llm_request_id"}
)
_CORRELATION_OPTIONAL: Final[frozenset[str]] = frozenset({"upstream_request_id"})
_CORRELATION_ALLOWED: Final[frozenset[str]] = (
    _CORRELATION_REQUIRED | _CORRELATION_OPTIONAL
)


def _require_mapping(name: str, value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    for key in value:
        if not isinstance(key, str):
            raise ValueError(f"{name} keys must be strings")
    return value


def _require_exact_keys(
    name: str,
    payload: Mapping[str, object],
    *,
    required: frozenset[str],
    allowed: frozenset[str],
) -> None:
    keys = frozenset(payload)
    missing = required - keys
    if missing:
        raise ValueError(f"{name} missing keys: {sorted(missing)}")
    extras = keys - allowed
    if extras:
        raise ValueError(f"{name} has unknown keys: {sorted(extras)}")


def _encode_prompt(prompt: ExchangePromptRef | None) -> dict[str, str] | None:
    if prompt is None:
        return None
    return {
        "name": prompt.name,
        "version": prompt.version,
        "digest": prompt.digest,
    }


def _encode_options(options: ExchangeEffectiveOptions) -> dict[str, object]:
    return {
        "temperature": options.temperature,
        "max_output_tokens": options.max_output_tokens,
        "top_p": options.top_p,
        "seed": options.seed,
        "stop": None if options.stop is None else list(options.stop),
    }


def _encode_usage(usage: ExchangeUsage | None) -> dict[str, int] | None:
    if usage is None:
        return None
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
    }


def _encode_correlation(correlation: ExchangeCorrelation) -> dict[str, object]:
    document: dict[str, object] = {
        "run_id": correlation.run_id,
        "agent_id": correlation.agent_id,
        "tick": correlation.tick,
        "llm_request_id": correlation.llm_request_id,
    }
    if correlation.upstream_request_id is not None:
        document["upstream_request_id"] = correlation.upstream_request_id
    return document


def encode_exchange_record(record: LLMExchangeRecord) -> dict[str, object]:
    """Encode ``record`` to a plain JSON-compatible mapping (exact key-set)."""
    if type(record) is not LLMExchangeRecord:
        raise TypeError("record must be LLMExchangeRecord")
    document: dict[str, object] = {
        "schema_id": record.schema_id,
        "provider": record.provider,
        "model": record.model,
        "structured_output_mode": record.structured_output_mode.value,
        "schema_identity": {
            "qualname": record.schema_identity.qualname,
            "digest": record.schema_identity.digest,
        },
        "prompt": _encode_prompt(record.prompt),
        "request_digest": record.request_digest,
        "effective_options": _encode_options(record.effective_options),
        "validation": {
            "status": record.validation.status.value,
            "reason_code": record.validation.reason_code,
        },
        "response": None if record.response is None else dict(record.response),
        "usage": _encode_usage(record.usage),
        "latency_ms": record.latency_ms,
        "correlation": _encode_correlation(record.correlation),
        "component": record.component,
        "cache_namespace": record.cache_namespace,
    }
    if record.recorded_at_monotonic_offset is not None:
        document["recorded_at_monotonic_offset"] = record.recorded_at_monotonic_offset
    return document


def encode_exchange_record_bytes(record: LLMExchangeRecord) -> bytes:
    """Canonical UTF-8 JSON bytes (sorted keys, compact separators)."""
    document = encode_exchange_record(record)
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _decode_prompt(raw: object) -> ExchangePromptRef | None:
    if raw is None:
        return None
    payload = _require_mapping("prompt", raw)
    _require_exact_keys(
        "prompt", payload, required=_PROMPT_KEYS, allowed=_PROMPT_KEYS
    )
    name = payload["name"]
    version = payload["version"]
    digest = payload["digest"]
    if not isinstance(name, str) or not isinstance(version, str) or not isinstance(
        digest, str
    ):
        raise ValueError("prompt fields must be strings")
    return ExchangePromptRef(name=name, version=version, digest=digest)


def _decode_options(raw: object) -> ExchangeEffectiveOptions:
    payload = _require_mapping("effective_options", raw)
    _require_exact_keys(
        "effective_options", payload, required=_OPTIONS_KEYS, allowed=_OPTIONS_KEYS
    )
    stop_raw = payload["stop"]
    stop: tuple[str, ...] | None
    if stop_raw is None:
        stop = None
    elif isinstance(stop_raw, list):
        if not all(isinstance(item, str) for item in stop_raw):
            raise ValueError("stop entries must be strings")
        stop = tuple(stop_raw)
    else:
        raise ValueError("stop must be an array or null")
    return ExchangeEffectiveOptions(
        temperature=payload["temperature"],  # type: ignore[arg-type]
        max_output_tokens=payload["max_output_tokens"],  # type: ignore[arg-type]
        top_p=payload["top_p"],  # type: ignore[arg-type]
        seed=payload["seed"],  # type: ignore[arg-type]
        stop=stop,
    )


def _decode_usage(raw: object) -> ExchangeUsage | None:
    if raw is None:
        return None
    payload = _require_mapping("usage", raw)
    _require_exact_keys("usage", payload, required=_USAGE_KEYS, allowed=_USAGE_KEYS)
    return ExchangeUsage(
        input_tokens=payload["input_tokens"],  # type: ignore[arg-type]
        output_tokens=payload["output_tokens"],  # type: ignore[arg-type]
        total_tokens=payload["total_tokens"],  # type: ignore[arg-type]
    )


def _decode_correlation(raw: object) -> ExchangeCorrelation:
    payload = _require_mapping("correlation", raw)
    _require_exact_keys(
        "correlation",
        payload,
        required=_CORRELATION_REQUIRED,
        allowed=_CORRELATION_ALLOWED,
    )
    upstream = payload.get("upstream_request_id")
    if upstream is not None and not isinstance(upstream, str):
        raise ValueError("upstream_request_id must be a string")
    run_id = payload["run_id"]
    agent_id = payload["agent_id"]
    llm_request_id = payload["llm_request_id"]
    tick = payload["tick"]
    if (
        not isinstance(run_id, str)
        or not isinstance(agent_id, str)
        or not isinstance(llm_request_id, str)
    ):
        raise ValueError("correlation string fields must be strings")
    if isinstance(tick, bool) or not isinstance(tick, int):
        raise ValueError("tick must be an integer")
    return ExchangeCorrelation(
        run_id=run_id,
        agent_id=agent_id,
        tick=tick,
        llm_request_id=llm_request_id,
        upstream_request_id=upstream,
    )


def decode_exchange_record(document: Mapping[str, object]) -> LLMExchangeRecord:
    """Decode and validate an exact key-set exchange document."""
    payload = _require_mapping("exchange", document)
    _require_exact_keys(
        "exchange",
        payload,
        required=_TOP_LEVEL_REQUIRED,
        allowed=_TOP_LEVEL_ALLOWED,
    )
    schema_id = payload["schema_id"]
    if schema_id != LLM_EXCHANGE_SCHEMA_ID:
        raise ValueError("unsupported exchange schema_id")

    schema_raw = _require_mapping("schema_identity", payload["schema_identity"])
    _require_exact_keys(
        "schema_identity",
        schema_raw,
        required=_SCHEMA_IDENTITY_KEYS,
        allowed=_SCHEMA_IDENTITY_KEYS,
    )
    qualname = schema_raw["qualname"]
    digest = schema_raw["digest"]
    if not isinstance(qualname, str) or not isinstance(digest, str):
        raise ValueError("schema_identity fields must be strings")

    mode_raw = payload["structured_output_mode"]
    if not isinstance(mode_raw, str):
        raise ValueError("structured_output_mode must be a string")
    try:
        mode = StructuredOutputMode(mode_raw)
    except ValueError as exc:
        raise ValueError("unsupported structured_output_mode") from exc

    validation_raw = _require_mapping("validation", payload["validation"])
    _require_exact_keys(
        "validation",
        validation_raw,
        required=_VALIDATION_KEYS,
        allowed=_VALIDATION_KEYS,
    )
    status_raw = validation_raw["status"]
    reason_code = validation_raw["reason_code"]
    if not isinstance(status_raw, str) or not isinstance(reason_code, str):
        raise ValueError("validation fields must be strings")
    try:
        status = ExchangeValidationStatus(status_raw)
    except ValueError as exc:
        raise ValueError("unsupported validation status") from exc

    response_raw = payload["response"]
    response: dict[str, object] | None
    if response_raw is None:
        response = None
    else:
        response = dict(_require_mapping("response", response_raw))

    provider = payload["provider"]
    model = payload["model"]
    request_digest = payload["request_digest"]
    component = payload["component"]
    cache_namespace = payload["cache_namespace"]
    latency_ms = payload["latency_ms"]
    if (
        not isinstance(provider, str)
        or not isinstance(model, str)
        or not isinstance(request_digest, str)
        or not isinstance(component, str)
        or not isinstance(cache_namespace, str)
    ):
        raise ValueError("exchange string fields must be strings")
    if isinstance(latency_ms, bool) or not isinstance(latency_ms, int):
        raise ValueError("latency_ms must be an integer")

    offset_raw = payload.get("recorded_at_monotonic_offset")
    offset: float | None
    if offset_raw is None and "recorded_at_monotonic_offset" not in payload:
        offset = None
    elif offset_raw is None:
        offset = None
    elif isinstance(offset_raw, bool) or not isinstance(offset_raw, (int, float)):
        raise ValueError("recorded_at_monotonic_offset must be a number")
    else:
        offset = float(offset_raw)

    return LLMExchangeRecord(
        schema_id=LLM_EXCHANGE_SCHEMA_ID,
        provider=provider,
        model=model,
        structured_output_mode=mode,
        schema_identity=SchemaIdentity(qualname=qualname, digest=digest),
        prompt=_decode_prompt(payload["prompt"]),
        request_digest=request_digest,
        effective_options=_decode_options(payload["effective_options"]),
        validation=ExchangeValidation(status=status, reason_code=reason_code),
        response=response,
        usage=_decode_usage(payload["usage"]),
        latency_ms=latency_ms,
        correlation=_decode_correlation(payload["correlation"]),
        component=component,
        cache_namespace=cache_namespace,
        recorded_at_monotonic_offset=offset,
    )


def decode_exchange_record_bytes(raw: bytes) -> LLMExchangeRecord:
    """Decode canonical JSON bytes into an exchange record."""
    if not isinstance(raw, (bytes, bytearray)):
        raise TypeError("raw must be bytes")
    try:
        loaded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("corrupt exchange record") from exc
    if not isinstance(loaded, dict):
        raise ValueError("exchange document must be an object")
    return decode_exchange_record(loaded)
