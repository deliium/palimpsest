"""Unit tests for llm-exchange-v1 contracts and exact key-set codec."""

from __future__ import annotations

import json

import pytest

from llm.models import LLMRequestContext, StructuredOutputMode
from llm.recording import (
    LLM_EXCHANGE_SCHEMA_ID,
    ExchangeCorrelation,
    ExchangeEffectiveOptions,
    ExchangePromptRef,
    ExchangeUsage,
    ExchangeValidation,
    ExchangeValidationStatus,
    LLMExchangeRecord,
    SchemaIdentity,
    decode_exchange_record,
    decode_exchange_record_bytes,
    encode_exchange_record,
    encode_exchange_record_bytes,
)

_DIGEST = "a" * 64
_DIGEST_B = "b" * 64


def _record(**overrides: object) -> LLMExchangeRecord:
    base: dict[str, object] = {
        "provider": "fake",
        "model": "scripted",
        "structured_output_mode": StructuredOutputMode.JSON_SCHEMA,
        "schema_identity": SchemaIdentity(
            qualname="tests.SampleOutput",
            digest=_DIGEST,
        ),
        "prompt": ExchangePromptRef(
            name="reconstructive_memory",
            version="v1",
            digest=_DIGEST_B,
        ),
        "request_digest": _DIGEST,
        "effective_options": ExchangeEffectiveOptions(temperature=0.0, seed=1),
        "validation": ExchangeValidation(
            status=ExchangeValidationStatus.VALIDATED,
            reason_code="validated",
        ),
        "response": {"kind": "wait"},
        "usage": ExchangeUsage(input_tokens=1, output_tokens=2, total_tokens=3),
        "latency_ms": 12,
        "correlation": ExchangeCorrelation(
            run_id="run-1",
            agent_id="agent-1",
            tick=0,
            llm_request_id="req-1",
        ),
        "component": "reconstructive_memory",
        "cache_namespace": "run-1",
    }
    base.update(overrides)
    return LLMExchangeRecord(**base)  # type: ignore[arg-type]


def test_request_context_component_defaults_none() -> None:
    context = LLMRequestContext(
        run_id="run-1",
        agent_id="agent-1",
        tick=0,
        llm_request_id="req-1",
    )
    assert context.component is None


def test_request_context_component_safe_segment() -> None:
    context = LLMRequestContext(
        run_id="run-1",
        agent_id="agent-1",
        tick=0,
        llm_request_id="req-1",
        component="reconstructive_memory",
    )
    assert context.component == "reconstructive_memory"


@pytest.mark.parametrize("bad", ["../x", "a/b", "", " bad", "has space"])
def test_request_context_component_rejects_unsafe(bad: str) -> None:
    with pytest.raises(ValueError):
        LLMRequestContext(
            run_id="run-1",
            agent_id="agent-1",
            tick=0,
            llm_request_id="req-1",
            component=bad,
        )


def test_exchange_round_trip() -> None:
    record = _record(recorded_at_monotonic_offset=1.5)
    encoded = encode_exchange_record(record)
    decoded = decode_exchange_record(encoded)
    assert decoded == record
    raw = encode_exchange_record_bytes(record)
    assert decode_exchange_record_bytes(raw) == record
    # Canonical JSON is sorted and compact.
    assert raw == json.dumps(
        encoded, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def test_exchange_rejects_extra_top_level_key() -> None:
    document = encode_exchange_record(_record())
    document["extra"] = "nope"
    with pytest.raises(ValueError, match="unknown keys"):
        decode_exchange_record(document)


def test_exchange_rejects_missing_required_key() -> None:
    document = encode_exchange_record(_record())
    del document["component"]
    with pytest.raises(ValueError, match="missing keys"):
        decode_exchange_record(document)


def test_exchange_rejects_unknown_schema_id() -> None:
    document = encode_exchange_record(_record())
    document["schema_id"] = "llm-exchange-v0"
    with pytest.raises(ValueError, match="unsupported exchange schema_id"):
        decode_exchange_record(document)


def test_exchange_construction_rejects_bad_schema_id() -> None:
    with pytest.raises(ValueError, match="unsupported exchange schema_id"):
        _record(schema_id="llm-exchange-v0")


def test_exchange_repr_is_metadata_only() -> None:
    record = _record(response={"secret": "payload-text", "kind": "wait"})
    text = repr(record)
    assert "payload-text" not in text
    assert "secret" not in text
    assert "response_keys=2" in text
    assert LLM_EXCHANGE_SCHEMA_ID in text
    assert _DIGEST[:12] in text


def test_optional_monotonic_offset_may_be_absent() -> None:
    document = encode_exchange_record(_record())
    assert "recorded_at_monotonic_offset" not in document
    decoded = decode_exchange_record(document)
    assert decoded.recorded_at_monotonic_offset is None
