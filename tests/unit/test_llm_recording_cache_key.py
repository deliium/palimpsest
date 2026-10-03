"""Unit tests for safe LLM recording cache-key derivation."""

from __future__ import annotations

import logging

import pytest

from llm.models import (
    EffectiveOptions,
    LLMMessage,
    MessageRole,
    PromptReference,
    StructuredOutput,
    StructuredOutputMode,
)
from llm.recording.cache_key import (
    derive_cache_key,
    digest_json_schema,
    digest_request_messages,
    normalize_message_content,
    schema_identity_for,
)
from llm.recording.models import SchemaIdentity


class _SampleA(StructuredOutput):
    kind: str


class _SampleB(StructuredOutput):
    kind: str
    note: str = "x"


_DIGEST = "c" * 64


def _identity(model: type[StructuredOutput] = _SampleA) -> SchemaIdentity:
    return schema_identity_for(model)


def _key(**overrides: object) -> str:
    base: dict[str, object] = {
        "cache_namespace": "run-1",
        "provider_name": "fake",
        "model_name": "scripted",
        "structured_output_mode": StructuredOutputMode.JSON_SCHEMA,
        "schema_identity": _identity(),
        "prompt": PromptReference(
            name="reconstructive_memory",
            version="v1",
            digest=_DIGEST,
        ),
        "request_digest": digest_request_messages(
            (
                LLMMessage(role=MessageRole.SYSTEM, content="sys"),
                LLMMessage(role=MessageRole.USER, content="user"),
            )
        ),
        "effective_options": EffectiveOptions(temperature=0.0, seed=7),
        "agent_id": "agent-1",
        "component": "reconstructive_memory",
    }
    base.update(overrides)
    return derive_cache_key(**base)  # type: ignore[arg-type]


def test_cache_key_is_stable() -> None:
    assert _key() == _key()


def test_distinct_namespaces_never_collide() -> None:
    a = _key(cache_namespace="run-parent")
    b = _key(cache_namespace="run-child")
    assert a != b


def test_schema_digest_change_changes_key() -> None:
    a = _key(schema_identity=_identity(_SampleA))
    b = _key(schema_identity=_identity(_SampleB))
    assert a != b
    assert digest_json_schema(_SampleA) != digest_json_schema(_SampleB)


def test_prompt_digest_change_changes_key() -> None:
    a = _key(
        prompt=PromptReference(
            name="reconstructive_memory", version="v1", digest="a" * 64
        )
    )
    b = _key(
        prompt=PromptReference(
            name="reconstructive_memory", version="v1", digest="b" * 64
        )
    )
    assert a != b


def test_prompt_absent_differs_from_present() -> None:
    assert _key(prompt=None) != _key()


def test_temperature_zero_is_preserved_in_key() -> None:
    with_zero = _key(effective_options=EffectiveOptions(temperature=0.0))
    with_none = _key(effective_options=EffectiveOptions(temperature=None))
    assert with_zero != with_none


def test_agent_and_component_isolation() -> None:
    assert _key(agent_id="agent-1") != _key(agent_id="agent-2")
    assert _key(component="reflection") != _key(component="reconstructive_memory")


def test_message_normalization_crlf() -> None:
    assert normalize_message_content("a\r\nb\rc") == "a\nb\nc"
    crlf = digest_request_messages(
        (LLMMessage(role=MessageRole.USER, content="a\r\nb"),)
    )
    lf = digest_request_messages(
        (LLMMessage(role=MessageRole.USER, content="a\nb"),)
    )
    assert crlf == lf


def test_cache_key_logs_never_include_raw_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "TOP-SECRET-PROMPT-BODY"
    with caplog.at_level(logging.DEBUG, logger="llm.recording"):
        _key(
            request_digest=digest_request_messages(
                (LLMMessage(role=MessageRole.USER, content=secret),)
            )
        )
    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert secret not in joined
    assert "cache_key_derived" in joined
