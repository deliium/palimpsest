"""Immutable LLM request/result contracts and strict structured-output base.

Pydantic validation on :class:`StructuredOutput` establishes **structure only**.
It never establishes truth, policy validity, actor identity, authorization, or
world authority. Validated values remain untrusted input to later cognition.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, ValidationError

from llm.errors import LLMError, LLMErrorCode

_MAX_MESSAGE_CONTENT_CHARS: Final[int] = 100_000
_MAX_ID_CHARS: Final[int] = 128
_MAX_PROMPT_SEGMENT_CHARS: Final[int] = 64
_MAX_DIGEST_CHARS: Final[int] = 64
_MAX_PROVIDER_NAME_CHARS: Final[int] = 64
_MAX_MODEL_NAME_CHARS: Final[int] = 128
_MAX_MESSAGES: Final[int] = 64

_SAFE_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_SEGMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
)
_SAFE_DIGEST_RE: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{64}$")
_HEADER_SAFE_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
)


class MessageRole(StrEnum):
    """V1 portable message roles."""

    SYSTEM = "system"
    USER = "user"


class FinishReason(StrEnum):
    """Closed set of normalized finish reasons."""

    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    REFUSAL = "refusal"
    UNKNOWN = "unknown"


class StructuredOutputMode(StrEnum):
    """Explicit structured-output capability modes (adapter configuration).

    Mode is provider-owned configuration and is not overridable per request.
    Local strict validation is mandatory in every mode.
    """

    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"
    PROMPT_ONLY = "prompt_only"


class StructuredOutput(BaseModel):
    """Project-owned strict base for provider-validated structured output.

    Validation proves shape conformance only. It does not prove semantic
    correctness, policy compliance, actor identity, authorization, or world
    authority. Do not treat instances as commands or world mutations.
    """

    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        config = cls.model_config
        if config.get("extra") != "forbid":
            raise TypeError(f"{cls.__name__} must keep extra='forbid'")
        if config.get("frozen") is not True:
            raise TypeError(f"{cls.__name__} must keep frozen=True")
        if config.get("strict") is not True:
            raise TypeError(f"{cls.__name__} must keep strict=True")
        if config.get("allow_inf_nan") is not False:
            raise TypeError(f"{cls.__name__} must keep allow_inf_nan=False")

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


def require_structured_output_type(model: object) -> type[StructuredOutput]:
    """Accept only ``StructuredOutput`` subclasses supplied as classes."""
    if not isinstance(model, type):
        raise TypeError(
            "response_model must be a StructuredOutput class, not an instance"
        )
    if not issubclass(model, StructuredOutput):
        raise TypeError("response_model must inherit StructuredOutput")
    if model is StructuredOutput:
        raise TypeError("response_model must be a concrete StructuredOutput subclass")
    return model


def validate_structured_output[T: StructuredOutput](
    model: type[T], data: Mapping[str, object]
) -> T:
    """Validate ``data`` as exactly ``model``; discard the mapping afterward.

    Raises:
        TypeError: when ``model`` is not an allowed structured-output class.
        ValueError: when validation fails or the result type is not exact.
    """
    require_structured_output_type(model)
    try:
        validated = model.model_validate(dict(data))
    except ValidationError:
        raise ValueError("structured output failed schema validation") from None
    if type(validated) is not model:
        raise ValueError("structured output type mismatch")
    return validated


def _require_non_blank(name: str, value: str, *, max_chars: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value or value.strip() != value or not value.strip():
        raise ValueError(f"{name} must be a non-blank string")
    if len(value) > max_chars:
        raise ValueError(f"{name} exceeds maximum length")
    return value


def _require_safe_id(name: str, value: str) -> str:
    text = _require_non_blank(name, value, max_chars=_MAX_ID_CHARS)
    if _SAFE_ID_RE.fullmatch(text) is None:
        raise ValueError(f"{name} contains unsupported characters")
    return text


def _require_header_safe_id(name: str, value: str) -> str:
    text = _require_non_blank(name, value, max_chars=_MAX_ID_CHARS)
    if _HEADER_SAFE_RE.fullmatch(text) is None:
        raise ValueError(f"{name} is not header-safe")
    return text


def _require_prompt_segment(name: str, value: str) -> str:
    text = _require_non_blank(name, value, max_chars=_MAX_PROMPT_SEGMENT_CHARS)
    if _SAFE_SEGMENT_RE.fullmatch(text) is None:
        raise ValueError(f"{name} must be a safe single path segment")
    if text in {".", ".."} or "/" in text or "\\" in text:
        raise ValueError(f"{name} must be a safe single path segment")
    return text


def _require_digest(name: str, value: str) -> str:
    text = _require_non_blank(name, value, max_chars=_MAX_DIGEST_CHARS)
    if _SAFE_DIGEST_RE.fullmatch(text) is None:
        raise ValueError(f"{name} must be a lowercase sha256 hex digest")
    return text


def _require_non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


@dataclass(frozen=True, slots=True)
class PromptReference:
    """Immutable identity of a versioned prompt resource."""

    name: str
    version: str
    digest: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "name", _require_prompt_segment("PromptReference.name", self.name)
        )
        object.__setattr__(
            self,
            "version",
            _require_prompt_segment("PromptReference.version", self.version),
        )
        object.__setattr__(
            self,
            "digest",
            _require_digest("PromptReference.digest", self.digest),
        )

    def __repr__(self) -> str:
        return (
            "PromptReference("
            f"name={self.name!r}, version={self.version!r}, digest={self.digest!r})"
        )


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """Ordered immutable chat message using V1 portable roles."""

    role: MessageRole
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, MessageRole):
            raise TypeError("LLMMessage.role must be MessageRole")
        text = _require_non_blank(
            "LLMMessage.content",
            self.content,
            max_chars=_MAX_MESSAGE_CONTENT_CHARS,
        )
        object.__setattr__(self, "content", text)

    def __repr__(self) -> str:
        return (
            f"LLMMessage(role={self.role.value!r}, content_chars={len(self.content)})"
        )


@dataclass(frozen=True, slots=True)
class LLMRequestContext:
    """Local correlation context. Never send run/agent/tick upstream."""

    run_id: str
    agent_id: str
    tick: int
    llm_request_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "run_id", _require_safe_id("LLMRequestContext.run_id", self.run_id)
        )
        object.__setattr__(
            self,
            "agent_id",
            _require_safe_id("LLMRequestContext.agent_id", self.agent_id),
        )
        object.__setattr__(
            self,
            "tick",
            _require_non_negative_int("LLMRequestContext.tick", self.tick),
        )
        object.__setattr__(
            self,
            "llm_request_id",
            _require_header_safe_id(
                "LLMRequestContext.llm_request_id",
                self.llm_request_id,
            ),
        )

    def __repr__(self) -> str:
        return (
            "LLMRequestContext("
            f"run_id={self.run_id!r}, "
            f"agent_id={self.agent_id!r}, "
            f"tick={self.tick}, "
            f"llm_request_id={self.llm_request_id!r})"
        )


@dataclass(frozen=True, slots=True)
class LLMRequestOptions:
    """Per-request generation options. ``None`` means omit / use provider default."""

    temperature: float | None = None
    max_output_tokens: int | None = None
    top_p: float | None = None
    seed: int | None = None
    stop: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.temperature is not None:
            if isinstance(self.temperature, bool) or not isinstance(
                self.temperature, (int, float)
            ):
                raise TypeError("temperature must be a finite number")
            temp = float(self.temperature)
            if temp != temp or temp in {float("inf"), float("-inf")}:
                raise ValueError("temperature must be finite")
            if temp < 0.0 or temp > 2.0:
                raise ValueError("temperature out of range")
            object.__setattr__(self, "temperature", temp)
        if self.max_output_tokens is not None:
            tokens = _require_non_negative_int(
                "max_output_tokens", self.max_output_tokens
            )
            if tokens < 1:
                raise ValueError("max_output_tokens must be >= 1")
            object.__setattr__(self, "max_output_tokens", tokens)
        if self.top_p is not None:
            if isinstance(self.top_p, bool) or not isinstance(self.top_p, (int, float)):
                raise TypeError("top_p must be a finite number")
            top_p = float(self.top_p)
            if top_p != top_p or top_p in {float("inf"), float("-inf")}:
                raise ValueError("top_p must be finite")
            if top_p <= 0.0 or top_p > 1.0:
                raise ValueError("top_p out of range")
            object.__setattr__(self, "top_p", top_p)
        if self.seed is not None:
            object.__setattr__(
                self, "seed", _require_non_negative_int("seed", self.seed)
            )
        if self.stop is not None:
            if not isinstance(self.stop, tuple):
                raise TypeError("stop must be a tuple of strings")
            if len(self.stop) > 8:
                raise ValueError("stop exceeds maximum entries")
            cleaned: list[str] = []
            for item in self.stop:
                text = _require_non_blank("stop entry", item, max_chars=64)
                cleaned.append(text)
            object.__setattr__(self, "stop", tuple(cleaned))

    def __repr__(self) -> str:
        return (
            "LLMRequestOptions("
            f"temperature={self.temperature!r}, "
            f"max_output_tokens={self.max_output_tokens!r}, "
            f"top_p={self.top_p!r}, "
            f"seed={self.seed!r}, "
            f"stop_count={0 if self.stop is None else len(self.stop)})"
        )


@dataclass(frozen=True, slots=True)
class ProviderDefaults:
    """Immutable provider-owned generation defaults.

    Endpoint, credentials, provider identity, and
    :class:`StructuredOutputMode` are adapter configuration and must not be
    supplied through :class:`LLMRequestOptions`.
    """

    temperature: float | None = None
    max_output_tokens: int | None = None
    top_p: float | None = None
    seed: int | None = None
    stop: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        validated = LLMRequestOptions(
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            top_p=self.top_p,
            seed=self.seed,
            stop=self.stop,
        )
        object.__setattr__(self, "temperature", validated.temperature)
        object.__setattr__(self, "max_output_tokens", validated.max_output_tokens)
        object.__setattr__(self, "top_p", validated.top_p)
        object.__setattr__(self, "seed", validated.seed)
        object.__setattr__(self, "stop", validated.stop)

    def __repr__(self) -> str:
        return (
            "ProviderDefaults("
            f"temperature={self.temperature!r}, "
            f"max_output_tokens={self.max_output_tokens!r}, "
            f"top_p={self.top_p!r}, "
            f"seed={self.seed!r}, "
            f"stop_count={0 if self.stop is None else len(self.stop)})"
        )


@dataclass(frozen=True, slots=True)
class EffectiveOptions:
    """Resolved generation options after applying request overrides to defaults.

    ``None`` fields are omitted from the wire body (never sent as JSON ``null``).
    """

    temperature: float | None = None
    max_output_tokens: int | None = None
    top_p: float | None = None
    seed: int | None = None
    stop: tuple[str, ...] | None = None

    def __repr__(self) -> str:
        return (
            "EffectiveOptions("
            f"temperature={self.temperature!r}, "
            f"max_output_tokens={self.max_output_tokens!r}, "
            f"top_p={self.top_p!r}, "
            f"seed={self.seed!r}, "
            f"stop_count={0 if self.stop is None else len(self.stop)})"
        )


def _coalesce[T](request_value: T | None, default: T | None) -> T | None:
    """Prefer a non-``None`` request value; preserve valid falsey values."""
    if request_value is not None:
        return request_value
    return default


def resolve_effective_options(
    defaults: ProviderDefaults,
    request: LLMRequestOptions | None,
) -> EffectiveOptions:
    """Resolve options once: non-``None`` request fields override defaults.

    Falsey values such as ``temperature=0`` override defaults because they are
    not ``None``. Endpoint, credentials, provider identity, and structured-output
    mode are not part of this resolution.
    """
    if type(defaults) is not ProviderDefaults:
        raise TypeError("defaults must be ProviderDefaults")
    if request is not None and type(request) is not LLMRequestOptions:
        raise TypeError("request must be LLMRequestOptions")
    options = request if request is not None else LLMRequestOptions()
    return EffectiveOptions(
        temperature=_coalesce(options.temperature, defaults.temperature),
        max_output_tokens=_coalesce(
            options.max_output_tokens, defaults.max_output_tokens
        ),
        top_p=_coalesce(options.top_p, defaults.top_p),
        seed=_coalesce(options.seed, defaults.seed),
        stop=_coalesce(options.stop, defaults.stop),
    )


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Deterministic retry policy for provider transport.

    ``max_attempts`` is the **total** number of attempts (not retries-after-first).
    Backoff is deterministic exponential with no jitter. ``Retry-After`` is
    accepted only as bounded delta-seconds.

    Retryable by default:
        connection establishment, timeout, rate limit (429), HTTP 408, selected
        5xx (500/502/503/504), and (when enabled) output format/schema failures.

    Not retryable:
        configuration, authentication/authorization, refusal/filtering,
        incomplete generation, closed provider, provider protocol / malformed
        envelopes, ordinary 4xx, non-selected 5xx, size-limit failures, and
        retry exhaustion. Cancellation must propagate unchanged and is never
        wrapped or retried.
    """

    max_attempts: int = 3
    per_attempt_timeout_seconds: float = 30.0
    total_deadline_seconds: float | None = None
    initial_backoff_seconds: float = 0.5
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 30.0
    max_retry_after_seconds: float = 60.0
    retry_output_format: bool = True
    retry_output_schema: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "max_attempts",
            _require_positive_int("max_attempts", self.max_attempts),
        )
        object.__setattr__(
            self,
            "per_attempt_timeout_seconds",
            _require_positive_float(
                "per_attempt_timeout_seconds",
                self.per_attempt_timeout_seconds,
            ),
        )
        if self.total_deadline_seconds is not None:
            object.__setattr__(
                self,
                "total_deadline_seconds",
                _require_positive_float(
                    "total_deadline_seconds",
                    self.total_deadline_seconds,
                ),
            )
        object.__setattr__(
            self,
            "initial_backoff_seconds",
            _require_non_negative_float(
                "initial_backoff_seconds",
                self.initial_backoff_seconds,
            ),
        )
        object.__setattr__(
            self,
            "backoff_multiplier",
            _require_positive_float("backoff_multiplier", self.backoff_multiplier),
        )
        object.__setattr__(
            self,
            "max_backoff_seconds",
            _require_positive_float("max_backoff_seconds", self.max_backoff_seconds),
        )
        object.__setattr__(
            self,
            "max_retry_after_seconds",
            _require_positive_float(
                "max_retry_after_seconds",
                self.max_retry_after_seconds,
            ),
        )
        if not isinstance(self.retry_output_format, bool):
            raise TypeError("retry_output_format must be bool")
        if not isinstance(self.retry_output_schema, bool):
            raise TypeError("retry_output_schema must be bool")

    def backoff_seconds(self, failure_ordinal: int) -> float:
        """Deterministic delay after failure ``failure_ordinal`` (1-based)."""
        ordinal = _require_positive_int("failure_ordinal", failure_ordinal)
        delay = self.initial_backoff_seconds * (
            self.backoff_multiplier ** (ordinal - 1)
        )
        return min(delay, self.max_backoff_seconds)

    def bound_retry_after_seconds(self, value: object) -> float | None:
        """Accept finite delta-seconds ``Retry-After`` values; otherwise omit.

        HTTP-date forms and non-positive / non-finite values are rejected.
        Accepted values are clamped to ``max_retry_after_seconds``.
        """
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        seconds = float(value)
        if seconds != seconds or seconds in {float("inf"), float("-inf")}:
            return None
        if seconds <= 0.0:
            return None
        return min(seconds, self.max_retry_after_seconds)

    def resolve_delay_seconds(
        self,
        failure_ordinal: int,
        *,
        retry_after_seconds: object = None,
    ) -> float:
        """Prefer bounded ``Retry-After`` when present; else deterministic backoff."""
        bounded = self.bound_retry_after_seconds(retry_after_seconds)
        if bounded is not None:
            return bounded
        return self.backoff_seconds(failure_ordinal)

    def should_retry(self, error: LLMError) -> bool:
        """Whether another attempt is allowed for ``error`` under this policy."""
        if type(error) is not LLMError:
            raise TypeError("error must be LLMError")
        if error.attempts >= self.max_attempts:
            return False
        if error.code is LLMErrorCode.RETRY_EXHAUSTION:
            return False
        if error.code is LLMErrorCode.OUTPUT_FORMAT:
            return bool(self.retry_output_format and error.retryable)
        if error.code is LLMErrorCode.OUTPUT_SCHEMA:
            return bool(self.retry_output_schema and error.retryable)
        return bool(error.retryable)

    def __repr__(self) -> str:
        return (
            "RetryPolicy("
            f"max_attempts={self.max_attempts}, "
            f"per_attempt_timeout_seconds={self.per_attempt_timeout_seconds}, "
            f"has_total_deadline={self.total_deadline_seconds is not None}, "
            f"retry_output_format={self.retry_output_format}, "
            f"retry_output_schema={self.retry_output_schema})"
        )


def _require_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a positive integer")
    if value < 1:
        raise ValueError(f"{name} must be >= 1")
    return value


def _require_positive_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a positive finite number")
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        raise ValueError(f"{name} must be finite")
    if number <= 0.0:
        raise ValueError(f"{name} must be > 0")
    return number


def _require_non_negative_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a non-negative finite number")
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        raise ValueError(f"{name} must be finite")
    if number < 0.0:
        raise ValueError(f"{name} must be >= 0")
    return number


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Bounded non-negative token usage from the final attempt only."""

    input_tokens: int
    output_tokens: int
    total_tokens: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "input_tokens",
            _require_non_negative_int("input_tokens", self.input_tokens),
        )
        object.__setattr__(
            self,
            "output_tokens",
            _require_non_negative_int("output_tokens", self.output_tokens),
        )
        object.__setattr__(
            self,
            "total_tokens",
            _require_non_negative_int("total_tokens", self.total_tokens),
        )

    def __repr__(self) -> str:
        return (
            "TokenUsage("
            f"input_tokens={self.input_tokens}, "
            f"output_tokens={self.output_tokens}, "
            f"total_tokens={self.total_tokens})"
        )


@dataclass(frozen=True, slots=True)
class LLMResultMetadata:
    """Normalized metadata. Provider/model names are local configuration labels."""

    provider_name: str
    model_name: str
    finish_reason: FinishReason
    usage: TokenUsage | None = None
    upstream_request_id: str | None = None
    attempts: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provider_name",
            _require_non_blank(
                "provider_name",
                self.provider_name,
                max_chars=_MAX_PROVIDER_NAME_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "model_name",
            _require_non_blank(
                "model_name",
                self.model_name,
                max_chars=_MAX_MODEL_NAME_CHARS,
            ),
        )
        if not isinstance(self.finish_reason, FinishReason):
            raise TypeError("finish_reason must be FinishReason")
        if self.usage is not None and type(self.usage) is not TokenUsage:
            raise TypeError("usage must be TokenUsage")
        if self.upstream_request_id is not None:
            object.__setattr__(
                self,
                "upstream_request_id",
                _require_header_safe_id(
                    "upstream_request_id",
                    self.upstream_request_id,
                ),
            )
        object.__setattr__(
            self,
            "attempts",
            _require_non_negative_int("attempts", self.attempts),
        )
        if self.attempts < 1:
            raise ValueError("attempts must be >= 1")

    def __repr__(self) -> str:
        return (
            "LLMResultMetadata("
            f"provider_name={self.provider_name!r}, "
            f"model_name={self.model_name!r}, "
            f"finish_reason={self.finish_reason.value!r}, "
            f"attempts={self.attempts}, "
            f"has_usage={self.usage is not None}, "
            f"has_upstream_request_id={self.upstream_request_id is not None})"
        )


@dataclass(frozen=True, slots=True)
class LLMRequest[T: StructuredOutput]:
    """Immutable typed generation request.

    ``response_model`` must be a concrete :class:`StructuredOutput` subclass.
    Validation of the eventual output establishes structure only.
    """

    messages: tuple[LLMMessage, ...]
    response_model: type[T]
    context: LLMRequestContext
    prompt: PromptReference | None = None
    options: LLMRequestOptions | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.messages, tuple):
            raise TypeError("messages must be a tuple")
        if not self.messages:
            raise ValueError("messages must not be empty")
        if len(self.messages) > _MAX_MESSAGES:
            raise ValueError("messages exceed maximum count")
        for message in self.messages:
            if type(message) is not LLMMessage:
                raise TypeError("messages must contain LLMMessage values")
        require_structured_output_type(self.response_model)
        if type(self.context) is not LLMRequestContext:
            raise TypeError("context must be LLMRequestContext")
        if self.prompt is not None and type(self.prompt) is not PromptReference:
            raise TypeError("prompt must be PromptReference")
        if self.options is not None and type(self.options) is not LLMRequestOptions:
            raise TypeError("options must be LLMRequestOptions")

    @classmethod
    def create(
        cls,
        *,
        messages: Sequence[LLMMessage],
        response_model: type[T],
        context: LLMRequestContext,
        prompt: PromptReference | None = None,
        options: LLMRequestOptions | None = None,
    ) -> LLMRequest[T]:
        return cls(
            messages=tuple(messages),
            response_model=response_model,
            context=context,
            prompt=prompt,
            options=options,
        )

    def __repr__(self) -> str:
        return (
            "LLMRequest("
            f"message_count={len(self.messages)}, "
            f"response_model={self.response_model.__name__!r}, "
            f"llm_request_id={self.context.llm_request_id!r}, "
            f"has_prompt={self.prompt is not None})"
        )


@dataclass(frozen=True, slots=True)
class LLMResult[T: StructuredOutput]:
    """Structurally validated output plus normalized metadata.

    ``output`` is not an agent command, action request, or world authority.
    """

    output: T
    metadata: LLMResultMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.output, StructuredOutput):
            raise TypeError("output must be a StructuredOutput instance")
        if type(self.metadata) is not LLMResultMetadata:
            raise TypeError("metadata must be LLMResultMetadata")

    def __repr__(self) -> str:
        return (
            "LLMResult("
            f"output_type={type(self.output).__name__!r}, "
            f"provider_name={self.metadata.provider_name!r}, "
            f"model_name={self.metadata.model_name!r}, "
            f"finish_reason={self.metadata.finish_reason.value!r})"
        )
