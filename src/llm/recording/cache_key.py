"""Safe content-addressed cache keys for LLM recording / replay.

Key material is SHA-256 over canonical length-prefixed bytes. Message and schema
content are hashed into the key and never logged.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from typing import Final

from llm.models import (
    EffectiveOptions,
    LLMMessage,
    PromptReference,
    StructuredOutput,
    StructuredOutputMode,
    require_structured_output_type,
)
from llm.recording.models import ExchangePromptRef, SchemaIdentity

_LOG: Final[logging.Logger] = logging.getLogger("llm.recording")

_CACHE_KEY_DOMAIN: Final[bytes] = b"llm.recording.cache_key.v1"
_SCHEMA_DIGEST_DOMAIN: Final[bytes] = b"llm.recording.schema_digest.v1"
_REQUEST_DIGEST_DOMAIN: Final[bytes] = b"llm.recording.request_digest.v1"
_PROMPT_ABSENT: Final[bytes] = b"prompt_absent"
_NULL: Final[bytes] = b"\x00"
_DIGEST_PREFIX_CHARS: Final[int] = 12


def _length_prefixed(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def _require_non_blank(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value or value.strip() != value or not value.strip():
        raise ValueError(f"{name} must be a non-blank string")
    return value


def normalize_message_content(content: str) -> str:
    """Normalize message text to UTF-8 LF (CRLF/CR → LF)."""
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    return content.replace("\r\n", "\n").replace("\r", "\n")


def response_model_qualname(model: type[StructuredOutput]) -> str:
    """Stable import qualname for a structured-output class."""
    require_structured_output_type(model)
    return f"{model.__module__}.{model.__qualname__}"


def digest_json_schema(model: type[StructuredOutput]) -> str:
    """SHA-256 of canonical Pydantic JSON Schema (sorted keys, compact)."""
    require_structured_output_type(model)
    schema = model.model_json_schema()
    encoded = json.dumps(
        schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    hasher = hashlib.sha256()
    hasher.update(_length_prefixed(_SCHEMA_DIGEST_DOMAIN))
    hasher.update(_length_prefixed(encoded))
    digest = hasher.hexdigest()
    _LOG.debug(
        "schema_digest_computed reason=ok digest_prefix=%s",
        digest[:_DIGEST_PREFIX_CHARS],
    )
    return digest


def schema_identity_for(model: type[StructuredOutput]) -> SchemaIdentity:
    """Build schema identity (qualname + digest) for ``model``."""
    return SchemaIdentity(
        qualname=response_model_qualname(model),
        digest=digest_json_schema(model),
    )


def digest_request_messages(messages: Sequence[LLMMessage]) -> str:
    """SHA-256 over ordered roles and normalized UTF-8 LF message bytes."""
    if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
        raise TypeError("messages must be a sequence of LLMMessage")
    if not messages:
        raise ValueError("messages must not be empty")
    hasher = hashlib.sha256()
    hasher.update(_length_prefixed(_REQUEST_DIGEST_DOMAIN))
    for message in messages:
        if type(message) is not LLMMessage:
            raise TypeError("messages must contain LLMMessage values")
        normalized = normalize_message_content(message.content)
        hasher.update(_length_prefixed(message.role.value.encode("utf-8")))
        hasher.update(_length_prefixed(normalized.encode("utf-8")))
    digest = hasher.hexdigest()
    _LOG.debug(
        "request_digest_computed reason=ok digest_prefix=%s message_count=%s",
        digest[:_DIGEST_PREFIX_CHARS],
        len(messages),
    )
    return digest


def _encode_optional_float(value: float | None) -> bytes:
    if value is None:
        return _NULL
    return repr(float(value)).encode("ascii")


def _encode_optional_int(value: int | None) -> bytes:
    if value is None:
        return _NULL
    return str(int(value)).encode("ascii")


def _encode_stop(stop: tuple[str, ...] | None) -> bytes:
    if stop is None:
        return _NULL
    hasher = hashlib.sha256()
    for item in stop:
        hasher.update(_length_prefixed(item.encode("utf-8")))
    return hasher.digest()


def _encode_effective_options(options: EffectiveOptions) -> bytes:
    if type(options) is not EffectiveOptions:
        raise TypeError("options must be EffectiveOptions")
    hasher = hashlib.sha256()
    hasher.update(_length_prefixed(b"temperature"))
    hasher.update(_length_prefixed(_encode_optional_float(options.temperature)))
    hasher.update(_length_prefixed(b"max_output_tokens"))
    hasher.update(_length_prefixed(_encode_optional_int(options.max_output_tokens)))
    hasher.update(_length_prefixed(b"top_p"))
    hasher.update(_length_prefixed(_encode_optional_float(options.top_p)))
    hasher.update(_length_prefixed(b"seed"))
    hasher.update(_length_prefixed(_encode_optional_int(options.seed)))
    hasher.update(_length_prefixed(b"stop"))
    hasher.update(_length_prefixed(_encode_stop(options.stop)))
    return hasher.digest()


def _encode_prompt_identity(
    prompt: PromptReference | ExchangePromptRef | None,
) -> bytes:
    if prompt is None:
        return _PROMPT_ABSENT
    if type(prompt) not in {PromptReference, ExchangePromptRef}:
        raise TypeError("prompt must be PromptReference, ExchangePromptRef, or None")
    hasher = hashlib.sha256()
    hasher.update(_length_prefixed(prompt.name.encode("utf-8")))
    hasher.update(_length_prefixed(prompt.version.encode("utf-8")))
    hasher.update(_length_prefixed(prompt.digest.encode("ascii")))
    return hasher.digest()


def derive_cache_key(
    *,
    cache_namespace: str,
    provider_name: str,
    model_name: str,
    structured_output_mode: StructuredOutputMode | str,
    schema_identity: SchemaIdentity,
    prompt: PromptReference | ExchangePromptRef | None,
    request_digest: str,
    effective_options: EffectiveOptions,
    agent_id: str,
    component: str,
) -> str:
    """Derive a collision-resistant cache key hex digest.

    Namespace is the first field. Tick / llm_request_id are intentionally
    excluded from the key material (correlation lookup is separate).
    """
    namespace = _require_non_blank("cache_namespace", cache_namespace)
    provider = _require_non_blank("provider_name", provider_name)
    model = _require_non_blank("model_name", model_name)
    agent = _require_non_blank("agent_id", agent_id)
    component_label = _require_non_blank("component", component)
    if type(schema_identity) is not SchemaIdentity:
        raise TypeError("schema_identity must be SchemaIdentity")
    if not isinstance(request_digest, str) or len(request_digest) != 64:
        raise ValueError("request_digest must be a sha256 hex digest")
    if isinstance(structured_output_mode, StructuredOutputMode):
        mode_value = structured_output_mode.value
    elif isinstance(structured_output_mode, str):
        mode_value = StructuredOutputMode(structured_output_mode).value
    else:
        raise TypeError("structured_output_mode must be StructuredOutputMode or str")

    hasher = hashlib.sha256()
    hasher.update(_length_prefixed(_CACHE_KEY_DOMAIN))
    hasher.update(_length_prefixed(namespace.encode("utf-8")))
    hasher.update(_length_prefixed(provider.encode("utf-8")))
    hasher.update(_length_prefixed(model.encode("utf-8")))
    hasher.update(_length_prefixed(mode_value.encode("utf-8")))
    hasher.update(_length_prefixed(schema_identity.qualname.encode("utf-8")))
    hasher.update(_length_prefixed(schema_identity.digest.encode("ascii")))
    hasher.update(_length_prefixed(_encode_prompt_identity(prompt)))
    hasher.update(_length_prefixed(request_digest.encode("ascii")))
    hasher.update(_length_prefixed(_encode_effective_options(effective_options)))
    hasher.update(_length_prefixed(agent.encode("utf-8")))
    hasher.update(_length_prefixed(component_label.encode("utf-8")))
    key = hasher.hexdigest()
    _LOG.debug(
        "cache_key_derived reason=ok key_prefix=%s namespace_prefix=%s",
        key[:_DIGEST_PREFIX_CHARS],
        hashlib.sha256(namespace.encode("utf-8")).hexdigest()[:_DIGEST_PREFIX_CHARS],
    )
    return key
