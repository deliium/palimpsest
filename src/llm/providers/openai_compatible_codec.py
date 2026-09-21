"""Pure OpenAI-compatible chat/completions structured-output codec.

No network I/O and no provider SDKs. Encode typed requests into wire bodies;
decode success envelopes into validated :class:`~llm.models.LLMResult` values.
Failures use :class:`~llm.errors.LLMError` codes only — never provider content,
headers, schemas, or rejected values.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, MutableMapping, Sequence
from copy import deepcopy
from typing import Any, Final

from llm.errors import LLMError, LLMErrorCode, error_from_validation_failure
from llm.models import (
    EffectiveOptions,
    FinishReason,
    LLMRequest,
    LLMResult,
    LLMResultMetadata,
    StructuredOutput,
    StructuredOutputMode,
    TokenUsage,
    require_structured_output_type,
    validate_structured_output,
)

__all__ = [
    "decode_chat_completions_response",
    "encode_chat_completions_body",
]

_MAX_MODEL_NAME_CHARS: Final[int] = 128
_MAX_SCHEMA_CHARS: Final[int] = 32_768
_MAX_ASSISTANT_CONTENT_CHARS: Final[int] = 100_000
_MAX_USAGE_TOKENS: Final[int] = 1_000_000_000
_MAX_UPSTREAM_ID_CHARS: Final[int] = 128

_SCHEMA_NAME_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_HEADER_SAFE_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
)

# Deterministic instruction appended in weaker structured-output modes.
_JSON_INSTRUCTION: Final[str] = (
    "Return exactly one JSON object that conforms to the required schema. "
    "Do not include markdown fences, commentary, or trailing text."
)

_FENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"^```(?:json)?\s*",
    re.IGNORECASE,
)


def encode_chat_completions_body[T: StructuredOutput](
    request: LLMRequest[T],
    *,
    model: str,
    mode: StructuredOutputMode,
    options: EffectiveOptions,
) -> dict[str, object]:
    """Encode ``request`` into an OpenAI-compatible ``chat/completions`` body.

    Forces ``n=1``. Omits ``None`` option fields (never sends JSON ``null``).
    Preflights schema compatibility before returning a body. Does not perform
    network I/O.

    Raises:
        LLMError: ``configuration`` when inputs or schema are unsuitable.
        TypeError: when argument types are wrong.
    """
    if type(request) is not LLMRequest:
        raise TypeError("request must be LLMRequest")
    if not isinstance(mode, StructuredOutputMode):
        raise TypeError("mode must be StructuredOutputMode")
    if type(options) is not EffectiveOptions:
        raise TypeError("options must be EffectiveOptions")
    model_name = _require_local_model_name(model)
    require_structured_output_type(request.response_model)

    schema = _build_openai_schema(request.response_model)
    _preflight_schema(schema, mode=mode)

    body: dict[str, object] = {
        "model": model_name,
        "messages": _encode_messages(request, mode=mode),
        "n": 1,
    }
    _apply_effective_options(body, options)
    _apply_response_format(body, mode=mode, schema=schema, model=request.response_model)
    return body


def decode_chat_completions_response[T: StructuredOutput](
    body: Mapping[str, object],
    *,
    response_model: type[T],
    provider_name: str,
    model_name: str,
    attempts: int = 1,
) -> LLMResult[T]:
    """Decode one OpenAI-compatible success body into ``LLMResult[T]``.

    Accepts exactly one assistant choice with string content, parses one
    top-level JSON object, then validates as ``response_model``. Provider and
    model names are taken from local configuration, not trustable wire fields.

    Raises:
        LLMError: safe Task 2 codes; never retains provider content.
        TypeError: when argument types are wrong.
    """
    if not isinstance(body, Mapping):
        raise TypeError("body must be a mapping")
    require_structured_output_type(response_model)
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
        raise TypeError("attempts must be a positive integer")

    if "error" in body:
        raise LLMError(
            LLMErrorCode.PROVIDER_PROTOCOL,
            retryable=False,
            attempts=attempts,
        )

    choices = body.get("choices")
    if not isinstance(choices, list):
        raise LLMError(
            LLMErrorCode.PROVIDER_PROTOCOL,
            retryable=False,
            attempts=attempts,
        )
    if len(choices) != 1:
        raise LLMError(
            LLMErrorCode.PROVIDER_PROTOCOL,
            retryable=False,
            attempts=attempts,
        )
    choice = choices[0]
    if not isinstance(choice, Mapping):
        raise LLMError(
            LLMErrorCode.PROVIDER_PROTOCOL,
            retryable=False,
            attempts=attempts,
        )

    _reject_tools(choice, attempts=attempts)
    finish = _classify_finish_reason(choice, attempts=attempts)
    content = _extract_assistant_content(choice, attempts=attempts)
    parsed = _parse_one_json_object(content, attempts=attempts)

    try:
        output = validate_structured_output(response_model, parsed)
    except (TypeError, ValueError):
        raise error_from_validation_failure(attempts=attempts) from None
    del parsed

    metadata = LLMResultMetadata(
        provider_name=provider_name,
        model_name=model_name,
        finish_reason=finish,
        usage=_normalize_usage(body.get("usage")),
        upstream_request_id=_normalize_upstream_request_id(body.get("id")),
        attempts=attempts,
    )
    return LLMResult(output=output, metadata=metadata)


def _require_local_model_name(model: str) -> str:
    if not isinstance(model, str):
        raise TypeError("model must be a string")
    if not model or model.strip() != model or not model.strip():
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    if len(model) > _MAX_MODEL_NAME_CHARS:
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    return model


def _encode_messages[T: StructuredOutput](
    request: LLMRequest[T],
    *,
    mode: StructuredOutputMode,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": message.role.value, "content": message.content}
        for message in request.messages
    ]
    if mode is not StructuredOutputMode.JSON_SCHEMA:
        messages.append({"role": "system", "content": _JSON_INSTRUCTION})
    return messages


def _apply_effective_options(
    body: MutableMapping[str, object],
    options: EffectiveOptions,
) -> None:
    if options.temperature is not None:
        body["temperature"] = options.temperature
    if options.max_output_tokens is not None:
        body["max_tokens"] = options.max_output_tokens
    if options.top_p is not None:
        body["top_p"] = options.top_p
    if options.seed is not None:
        body["seed"] = options.seed
    if options.stop is not None:
        body["stop"] = list(options.stop)


def _apply_response_format(
    body: MutableMapping[str, object],
    *,
    mode: StructuredOutputMode,
    schema: dict[str, Any],
    model: type[StructuredOutput],
) -> None:
    if mode is StructuredOutputMode.JSON_SCHEMA:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": _schema_name(model),
                "strict": True,
                "schema": schema,
            },
        }
        return
    if mode is StructuredOutputMode.JSON_OBJECT:
        body["response_format"] = {"type": "json_object"}
        return
    # prompt_only: no response_format


def _schema_name(model: type[StructuredOutput]) -> str:
    name = model.__name__
    if _SCHEMA_NAME_RE.fullmatch(name) is None:
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    return name


def _build_openai_schema(model: type[StructuredOutput]) -> dict[str, Any]:
    try:
        raw = model.model_json_schema()
    except Exception:
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False) from None
    if not isinstance(raw, dict):
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    schema = _to_openai_strict_schema(deepcopy(raw))
    try:
        encoded = json.dumps(
            schema,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False) from None
    if len(encoded) > _MAX_SCHEMA_CHARS:
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    return schema


def _preflight_schema(
    schema: Mapping[str, Any],
    *,
    mode: StructuredOutputMode,
) -> None:
    if schema.get("type") != "object":
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    if schema.get("additionalProperties") is not False:
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    # Weaker modes still require a locally valid object schema for validation.
    del mode
    _assert_schema_compatible(schema, defs=_collect_defs(schema))


def _collect_defs(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    defs = schema.get("$defs")
    if defs is None:
        defs = schema.get("definitions")
    if defs is None:
        return {}
    if not isinstance(defs, Mapping):
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    return defs


def _assert_schema_compatible(
    node: Mapping[str, Any],
    *,
    defs: Mapping[str, Any],
    _seen: frozenset[str] | None = None,
) -> None:
    seen = _seen if _seen is not None else frozenset()
    ref = node.get("$ref")
    if isinstance(ref, str):
        target = _resolve_local_ref(ref, defs=defs)
        if target in seen:
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
        resolved = defs[target]
        if not isinstance(resolved, Mapping):
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
        _assert_schema_compatible(
            resolved,
            defs=defs,
            _seen=seen | {target},
        )
        return

    node_type = node.get("type")
    if node_type == "object" or "properties" in node:
        additional = node.get("additionalProperties", False)
        if additional is not False:
            # Unconstrained / open objects are unsupported.
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
        properties = node.get("properties")
        if properties is None:
            properties = {}
        if not isinstance(properties, Mapping):
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
        required = node.get("required")
        if required is None:
            required = []
        if not isinstance(required, list) or any(
            not isinstance(item, str) for item in required
        ):
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
        if set(required) != set(properties):
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
        for child in properties.values():
            if not isinstance(child, Mapping):
                raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
            _assert_schema_compatible(child, defs=defs, _seen=seen)

    if node_type == "array":
        items = node.get("items")
        if not isinstance(items, Mapping):
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
        _assert_schema_compatible(items, defs=defs, _seen=seen)

    for key in ("anyOf", "oneOf", "allOf"):
        variants = node.get(key)
        if variants is None:
            continue
        if not isinstance(variants, list) or not variants:
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
        for variant in variants:
            if not isinstance(variant, Mapping):
                raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
            _assert_schema_compatible(variant, defs=defs, _seen=seen)


def _resolve_local_ref(ref: str, *, defs: Mapping[str, Any]) -> str:
    prefix = "#/$defs/"
    alt = "#/definitions/"
    if ref.startswith(prefix):
        name = ref[len(prefix) :]
    elif ref.startswith(alt):
        name = ref[len(alt) :]
    else:
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    if not name or "/" in name or name not in defs:
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    return name


def _to_openai_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Pydantic JSON Schema into OpenAI strict ``json_schema`` form."""
    defs_key = "$defs" if "$defs" in schema else "definitions"
    defs = schema.get(defs_key)
    if isinstance(defs, dict):
        for name, node in list(defs.items()):
            if isinstance(node, dict):
                defs[name] = _strictify_object_node(node)
    return _strictify_object_node(schema)


def _strictify_object_node(node: dict[str, Any]) -> dict[str, Any]:
    ref = node.get("$ref")
    if isinstance(ref, str):
        # Keep only the reference; sibling keywords are not required on the wire.
        return {"$ref": ref}

    for key in ("anyOf", "oneOf", "allOf"):
        variants = node.get(key)
        if isinstance(variants, list):
            node[key] = [
                _strictify_object_node(variant)
                if isinstance(variant, dict)
                else variant
                for variant in variants
            ]

    if node.get("type") == "array" and isinstance(node.get("items"), dict):
        node["items"] = _strictify_object_node(node["items"])

    properties = node.get("properties")
    if isinstance(properties, dict):
        node["additionalProperties"] = False
        node["required"] = sorted(properties.keys())
        node["properties"] = {
            key: _strictify_object_node(value) if isinstance(value, dict) else value
            for key, value in properties.items()
        }
        if "type" not in node:
            node["type"] = "object"
    return node


def _reject_tools(choice: Mapping[str, object], *, attempts: int) -> None:
    if "tool_calls" in choice or "function_call" in choice:
        raise LLMError(
            LLMErrorCode.PROVIDER_PROTOCOL,
            retryable=False,
            attempts=attempts,
        )
    message = choice.get("message")
    if isinstance(message, Mapping):
        if message.get("tool_calls") not in (None, []):
            raise LLMError(
                LLMErrorCode.PROVIDER_PROTOCOL,
                retryable=False,
                attempts=attempts,
            )
        if message.get("function_call") is not None:
            raise LLMError(
                LLMErrorCode.PROVIDER_PROTOCOL,
                retryable=False,
                attempts=attempts,
            )


def _classify_finish_reason(
    choice: Mapping[str, object],
    *,
    attempts: int,
) -> FinishReason:
    message = choice.get("message")
    if isinstance(message, Mapping):
        refusal = message.get("refusal")
        if isinstance(refusal, str) and refusal.strip():
            raise LLMError(LLMErrorCode.REFUSAL, retryable=False, attempts=attempts)

    raw = choice.get("finish_reason")
    if raw is None:
        raise LLMError(
            LLMErrorCode.PROVIDER_PROTOCOL,
            retryable=False,
            attempts=attempts,
        )
    if not isinstance(raw, str):
        raise LLMError(
            LLMErrorCode.PROVIDER_PROTOCOL,
            retryable=False,
            attempts=attempts,
        )
    if raw == FinishReason.STOP.value:
        return FinishReason.STOP
    if raw == FinishReason.LENGTH.value:
        raise LLMError(LLMErrorCode.INCOMPLETE, retryable=False, attempts=attempts)
    if raw == FinishReason.CONTENT_FILTER.value:
        raise LLMError(LLMErrorCode.REFUSAL, retryable=False, attempts=attempts)
    if raw == FinishReason.REFUSAL.value:
        raise LLMError(LLMErrorCode.REFUSAL, retryable=False, attempts=attempts)
    if raw in {"tool_calls", "function_call"}:
        raise LLMError(
            LLMErrorCode.PROVIDER_PROTOCOL,
            retryable=False,
            attempts=attempts,
        )
    raise LLMError(LLMErrorCode.INCOMPLETE, retryable=False, attempts=attempts)


def _extract_assistant_content(
    choice: Mapping[str, object],
    *,
    attempts: int,
) -> str:
    message = choice.get("message")
    if not isinstance(message, Mapping):
        raise LLMError(
            LLMErrorCode.PROVIDER_PROTOCOL,
            retryable=False,
            attempts=attempts,
        )
    role = message.get("role")
    if role is not None and role != "assistant":
        raise LLMError(
            LLMErrorCode.PROVIDER_PROTOCOL,
            retryable=False,
            attempts=attempts,
        )
    content = message.get("content")
    if content is None:
        raise LLMError(
            LLMErrorCode.OUTPUT_FORMAT,
            retryable=True,
            attempts=attempts,
        )
    if isinstance(content, list):
        raise LLMError(
            LLMErrorCode.OUTPUT_FORMAT,
            retryable=True,
            attempts=attempts,
        )
    if not isinstance(content, str):
        raise LLMError(
            LLMErrorCode.OUTPUT_FORMAT,
            retryable=True,
            attempts=attempts,
        )
    if len(content) > _MAX_ASSISTANT_CONTENT_CHARS:
        raise LLMError(
            LLMErrorCode.PROVIDER_PROTOCOL,
            retryable=False,
            attempts=attempts,
        )
    return content


def _parse_one_json_object(content: str, *, attempts: int) -> dict[str, object]:
    text = content.strip()
    if not text:
        raise LLMError(
            LLMErrorCode.OUTPUT_FORMAT,
            retryable=True,
            attempts=attempts,
        )
    if text.startswith("```") or _FENCE_RE.match(text) is not None:
        raise LLMError(
            LLMErrorCode.OUTPUT_FORMAT,
            retryable=True,
            attempts=attempts,
        )
    if "```" in text:
        raise LLMError(
            LLMErrorCode.OUTPUT_FORMAT,
            retryable=True,
            attempts=attempts,
        )

    def reject_constant(_name: str) -> None:
        raise LLMError(
            LLMErrorCode.OUTPUT_FORMAT,
            retryable=True,
            attempts=attempts,
        )

    def reject_duplicate_keys(
        pairs: Sequence[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise LLMError(
                    LLMErrorCode.OUTPUT_FORMAT,
                    retryable=True,
                    attempts=attempts,
                )
            result[key] = value
        return result

    decoder = json.JSONDecoder(
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_constant,
    )
    try:
        value, end = decoder.raw_decode(text)
    except LLMError:
        raise
    except json.JSONDecodeError:
        raise LLMError(
            LLMErrorCode.OUTPUT_FORMAT,
            retryable=True,
            attempts=attempts,
        ) from None
    if end != len(text):
        raise LLMError(
            LLMErrorCode.OUTPUT_FORMAT,
            retryable=True,
            attempts=attempts,
        )
    if not isinstance(value, dict):
        raise LLMError(
            LLMErrorCode.OUTPUT_FORMAT,
            retryable=True,
            attempts=attempts,
        )
    cleaned: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise LLMError(
                LLMErrorCode.OUTPUT_FORMAT,
                retryable=True,
                attempts=attempts,
            )
        cleaned[key] = item
    return cleaned


def _normalize_usage(raw: object) -> TokenUsage | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return None
    input_tokens = _usage_int(
        raw,
        "prompt_tokens",
        "input_tokens",
    )
    output_tokens = _usage_int(
        raw,
        "completion_tokens",
        "output_tokens",
    )
    total_tokens = _usage_int(raw, "total_tokens")
    if input_tokens is None or output_tokens is None or total_tokens is None:
        return None
    try:
        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
    except (TypeError, ValueError):
        return None


def _usage_int(raw: Mapping[str, object], *keys: str) -> int | None:
    for key in keys:
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        if value < 0 or value > _MAX_USAGE_TOKENS:
            return None
        return value
    return None


def _normalize_upstream_request_id(raw: object) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    if not raw or len(raw) > _MAX_UPSTREAM_ID_CHARS:
        return None
    if _HEADER_SAFE_RE.fullmatch(raw) is None:
        return None
    return raw
