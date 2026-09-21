"""Pure OpenAI-compatible structured-output codec (no network)."""

from __future__ import annotations

import json

import pytest

from llm.errors import LLMError, LLMErrorCode
from llm.models import (
    EffectiveOptions,
    FinishReason,
    LLMMessage,
    LLMRequest,
    LLMRequestContext,
    MessageRole,
    StructuredOutput,
    StructuredOutputMode,
    TokenUsage,
)
from llm.providers.openai_compatible_codec import (
    decode_chat_completions_response,
    encode_chat_completions_body,
)

pytestmark = pytest.mark.unit


class _Decision(StructuredOutput):
    kind: str
    note: str | None = None


class _OpenDict(StructuredOutput):
    data: dict[str, str]


def _context() -> LLMRequestContext:
    return LLMRequestContext(
        run_id="run-1",
        agent_id="agent-1",
        tick=0,
        llm_request_id="req-abc",
    )


def _request(
    *,
    options: EffectiveOptions | None = None,
) -> LLMRequest[_Decision]:
    del options
    return LLMRequest.create(
        messages=(
            LLMMessage(role=MessageRole.SYSTEM, content="System rules."),
            LLMMessage(role=MessageRole.USER, content="Choose an action."),
        ),
        response_model=_Decision,
        context=_context(),
    )


def _success_body(
    content: str,
    *,
    finish_reason: str = "stop",
    usage: dict[str, object] | None = None,
    response_id: str | None = "chatcmpl-abc123",
    extra_choice: dict[str, object] | None = None,
) -> dict[str, object]:
    message: dict[str, object] = {
        "role": "assistant",
        "content": content,
    }
    choice: dict[str, object] = {
        "index": 0,
        "message": message,
        "finish_reason": finish_reason,
    }
    if extra_choice:
        choice.update(extra_choice)
    body: dict[str, object] = {
        "id": response_id,
        "object": "chat.completion",
        "choices": [choice],
    }
    if usage is not None:
        body["usage"] = usage
    return body


def test_encode_json_schema_mode_wire_shape() -> None:
    body = encode_chat_completions_body(
        _request(),
        model="gpt-test",
        mode=StructuredOutputMode.JSON_SCHEMA,
        options=EffectiveOptions(temperature=0.0, max_output_tokens=128, seed=7),
    )
    assert body["model"] == "gpt-test"
    assert body["n"] == 1
    assert body["temperature"] == 0.0
    assert body["max_tokens"] == 128
    assert body["seed"] == 7
    assert "top_p" not in body
    assert "stop" not in body
    messages = body["messages"]
    assert isinstance(messages, list)
    assert len(messages) == 2
    assert all(set(item) == {"role", "content"} for item in messages)
    # Local correlation must never appear on the wire.
    encoded = json.dumps(body)
    assert "run-1" not in encoded
    assert "agent-1" not in encoded
    assert "req-abc" not in encoded

    response_format = body["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_schema"
    json_schema = response_format["json_schema"]
    assert isinstance(json_schema, dict)
    assert json_schema["name"] == "_Decision"
    assert json_schema["strict"] is True
    schema = json_schema["schema"]
    assert isinstance(schema, dict)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"kind", "note"}


def test_encode_json_object_and_prompt_only_add_instruction() -> None:
    base = _request()
    options = EffectiveOptions(temperature=0.5)

    object_body = encode_chat_completions_body(
        base,
        model="local-model",
        mode=StructuredOutputMode.JSON_OBJECT,
        options=options,
    )
    assert object_body["response_format"] == {"type": "json_object"}
    object_messages = object_body["messages"]
    assert isinstance(object_messages, list)
    assert object_messages[-1]["role"] == "system"
    assert "JSON object" in object_messages[-1]["content"]
    assert "markdown fences" in object_messages[-1]["content"]

    prompt_body = encode_chat_completions_body(
        base,
        model="local-model",
        mode=StructuredOutputMode.PROMPT_ONLY,
        options=options,
    )
    assert "response_format" not in prompt_body
    prompt_messages = prompt_body["messages"]
    assert isinstance(prompt_messages, list)
    assert prompt_messages[-1] == object_messages[-1]


def test_encode_omits_null_options_and_forces_n_one() -> None:
    body = encode_chat_completions_body(
        _request(),
        model="m",
        mode=StructuredOutputMode.PROMPT_ONLY,
        options=EffectiveOptions(),
    )
    assert body["n"] == 1
    for key in ("temperature", "max_tokens", "top_p", "seed", "stop"):
        assert key not in body


def test_encode_rejects_unconstrained_mapping_schema() -> None:
    request = LLMRequest.create(
        messages=(LLMMessage(role=MessageRole.USER, content="x"),),
        response_model=_OpenDict,
        context=_context(),
    )
    with pytest.raises(LLMError) as captured:
        encode_chat_completions_body(
            request,
            model="m",
            mode=StructuredOutputMode.JSON_SCHEMA,
            options=EffectiveOptions(),
        )
    assert captured.value.code is LLMErrorCode.CONFIGURATION
    assert captured.value.retryable is False
    assert "data" not in str(captured.value)
    assert "additionalProperties" not in repr(captured.value)


def test_decode_success_validates_and_discards_raw() -> None:
    body = _success_body(
        '{"kind":"wait","note":null}',
        usage={
            "prompt_tokens": 11,
            "completion_tokens": 5,
            "total_tokens": 16,
        },
    )
    result = decode_chat_completions_response(
        body,
        response_model=_Decision,
        provider_name="openai_compatible",
        model_name="local-gpt",
        attempts=2,
    )
    assert result.output == _Decision(kind="wait", note=None)
    assert type(result.output) is _Decision
    assert result.metadata.provider_name == "openai_compatible"
    assert result.metadata.model_name == "local-gpt"
    assert result.metadata.finish_reason is FinishReason.STOP
    assert result.metadata.attempts == 2
    assert result.metadata.upstream_request_id == "chatcmpl-abc123"
    assert result.metadata.usage == TokenUsage(
        input_tokens=11,
        output_tokens=5,
        total_tokens=16,
    )
    # Public surfaces stay free of payload text.
    assert "wait" not in repr(result)
    assert '{"kind"' not in repr(result)


def test_decode_uses_local_model_not_wire_model() -> None:
    body = _success_body('{"kind":"go","note":"x"}')
    body["model"] = "wire-model-should-be-ignored"
    result = decode_chat_completions_response(
        body,
        response_model=_Decision,
        provider_name="ollama",
        model_name="configured-name",
    )
    assert result.metadata.model_name == "configured-name"
    assert result.metadata.provider_name == "ollama"


@pytest.mark.parametrize(
    ("body_factory", "code"),
    [
        (
            lambda: {"error": {"message": "boom", "type": "server_error"}},
            LLMErrorCode.PROVIDER_PROTOCOL,
        ),
        (
            lambda: _success_body('{"kind":"a"}') | {"choices": []},
            LLMErrorCode.PROVIDER_PROTOCOL,
        ),
        (
            lambda: {
                **_success_body('{"kind":"a"}'),
                "choices": [
                    _success_body('{"kind":"a"}')["choices"][0],  # type: ignore[index]
                    _success_body('{"kind":"b"}')["choices"][0],  # type: ignore[index]
                ],
            },
            LLMErrorCode.PROVIDER_PROTOCOL,
        ),
        (
            lambda: _success_body('{"kind":"a"}', finish_reason="length"),
            LLMErrorCode.INCOMPLETE,
        ),
        (
            lambda: _success_body('{"kind":"a"}', finish_reason="content_filter"),
            LLMErrorCode.REFUSAL,
        ),
        (
            lambda: _success_body('{"kind":"a"}', finish_reason="tool_calls"),
            LLMErrorCode.PROVIDER_PROTOCOL,
        ),
    ],
)
def test_decode_rejects_envelope_failures(
    body_factory: object,
    code: LLMErrorCode,
) -> None:
    assert callable(body_factory)
    body = body_factory()
    with pytest.raises(LLMError) as captured:
        decode_chat_completions_response(
            body,
            response_model=_Decision,
            provider_name="p",
            model_name="m",
            attempts=3,
        )
    assert captured.value.code is code
    assert captured.value.attempts == 3
    assert captured.value.retryable is False
    assert "boom" not in repr(captured.value)
    assert "kind" not in repr(captured.value)


def test_decode_rejects_null_multipart_and_tool_content() -> None:
    null_body = _success_body("ignored")
    null_body["choices"][0]["message"]["content"] = None  # type: ignore[index]
    with pytest.raises(LLMError) as null_err:
        decode_chat_completions_response(
            null_body,
            response_model=_Decision,
            provider_name="p",
            model_name="m",
        )
    assert null_err.value.code is LLMErrorCode.OUTPUT_FORMAT

    multi = _success_body("ignored")
    multi["choices"][0]["message"]["content"] = [  # type: ignore[index]
        {"type": "text", "text": '{"kind":"a"}'}
    ]
    with pytest.raises(LLMError) as multi_err:
        decode_chat_completions_response(
            multi,
            response_model=_Decision,
            provider_name="p",
            model_name="m",
        )
    assert multi_err.value.code is LLMErrorCode.OUTPUT_FORMAT

    tools = _success_body('{"kind":"a"}')
    tools["choices"][0]["message"]["tool_calls"] = [  # type: ignore[index]
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "x", "arguments": "{}"},
        }
    ]
    with pytest.raises(LLMError) as tools_err:
        decode_chat_completions_response(
            tools,
            response_model=_Decision,
            provider_name="p",
            model_name="m",
        )
    assert tools_err.value.code is LLMErrorCode.PROVIDER_PROTOCOL
    assert "call_1" not in repr(tools_err.value)


def test_decode_rejects_refusal_field() -> None:
    body = _success_body("ignored")
    body["choices"][0]["message"]["content"] = None  # type: ignore[index]
    body["choices"][0]["message"]["refusal"] = "I cannot help."  # type: ignore[index]
    with pytest.raises(LLMError) as captured:
        decode_chat_completions_response(
            body,
            response_model=_Decision,
            provider_name="p",
            model_name="m",
        )
    assert captured.value.code is LLMErrorCode.REFUSAL
    assert "cannot help" not in repr(captured.value)


@pytest.mark.parametrize(
    "content",
    [
        '```json\n{"kind":"a"}\n```',
        '{"kind":"a"} trailing',
        '{"kind":"a","kind":"b"}',
        "NaN",
        "Infinity",
        "[1,2,3]",
        '"just-a-string"',
        "",
        "   ",
    ],
)
def test_decode_rejects_bad_json_payloads(content: str) -> None:
    # Duplicate-key case needs raw text that the strict decoder rejects.
    if content == '{"kind":"a","kind":"b"}':
        body = _success_body('{"kind":"a","kind":"b"}')
    else:
        body = _success_body(content)
    with pytest.raises(LLMError) as captured:
        decode_chat_completions_response(
            body,
            response_model=_Decision,
            provider_name="p",
            model_name="m",
            attempts=1,
        )
    assert captured.value.code is LLMErrorCode.OUTPUT_FORMAT
    if content.strip():
        assert content.strip()[:12] not in repr(captured.value)


def test_decode_schema_mismatch_is_output_schema() -> None:
    body = _success_body('{"kind":1}')
    with pytest.raises(LLMError) as captured:
        decode_chat_completions_response(
            body,
            response_model=_Decision,
            provider_name="p",
            model_name="m",
            attempts=4,
        )
    assert captured.value.code is LLMErrorCode.OUTPUT_SCHEMA
    assert captured.value.attempts == 4
    assert captured.value.retryable is True


def test_decode_omits_unsafe_usage_and_upstream_id() -> None:
    body = _success_body(
        '{"kind":"ok"}',
        usage={"prompt_tokens": True, "completion_tokens": 1, "total_tokens": 1},
        response_id="not safe id!",
    )
    result = decode_chat_completions_response(
        body,
        response_model=_Decision,
        provider_name="p",
        model_name="m",
    )
    assert result.metadata.usage is None
    assert result.metadata.upstream_request_id is None


def test_decode_accepts_missing_optional_metadata() -> None:
    body = _success_body('{"kind":"ok"}', response_id=None)
    del body["id"]
    result = decode_chat_completions_response(
        body,
        response_model=_Decision,
        provider_name="p",
        model_name="m",
    )
    assert result.metadata.usage is None
    assert result.metadata.upstream_request_id is None
    assert result.output.kind == "ok"


def test_decode_rejects_oversized_content() -> None:
    huge = "{" + ("a" * 100_001) + "}"
    body = _success_body(huge)
    with pytest.raises(LLMError) as captured:
        decode_chat_completions_response(
            body,
            response_model=_Decision,
            provider_name="p",
            model_name="m",
        )
    assert captured.value.code is LLMErrorCode.PROVIDER_PROTOCOL
    assert captured.value.retryable is False


def test_codec_is_log_free_and_has_no_network_imports() -> None:
    from pathlib import Path

    import llm.providers.openai_compatible_codec as codec

    source_path = codec.__file__
    assert source_path is not None
    text = Path(source_path).read_text(encoding="utf-8")
    assert "import logging" not in text
    assert "import httpx" not in text
    assert "from httpx" not in text
    assert "import openai" not in text
    assert "from openai" not in text
    assert "getLogger" not in text
