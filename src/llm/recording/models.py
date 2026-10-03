"""Frozen exchange-record contracts for LLM recording / replay.

Response payloads are carried only inside store files. ``__repr__`` exposes
counts and digests — never prompts, messages, schemas, or validated dumps.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from llm.models import StructuredOutputMode

LLM_EXCHANGE_SCHEMA_ID: Final[str] = "llm-exchange-v1"

_MAX_ID_CHARS: Final[int] = 128
_MAX_PROVIDER_NAME_CHARS: Final[int] = 64
_MAX_MODEL_NAME_CHARS: Final[int] = 128
_MAX_QUALNAME_CHARS: Final[int] = 256
_MAX_NAMESPACE_CHARS: Final[int] = 256
_MAX_SEGMENT_CHARS: Final[int] = 64
_MAX_RESPONSE_KEYS: Final[int] = 256

_SAFE_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SAFE_SEGMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
)
_SAFE_DIGEST_RE: Final[re.Pattern[str]] = re.compile(r"^[a-f0-9]{64}$")
_HEADER_SAFE_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
)


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


def _require_segment(name: str, value: str) -> str:
    text = _require_non_blank(name, value, max_chars=_MAX_SEGMENT_CHARS)
    if _SAFE_SEGMENT_RE.fullmatch(text) is None:
        raise ValueError(f"{name} must be a safe single path segment")
    if text in {".", ".."} or "/" in text or "\\" in text:
        raise ValueError(f"{name} must be a safe single path segment")
    return text


def _require_digest(name: str, value: str) -> str:
    text = _require_non_blank(name, value, max_chars=64)
    if _SAFE_DIGEST_RE.fullmatch(text) is None:
        raise ValueError(f"{name} must be a lowercase sha256 hex digest")
    return text


def _require_non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _require_finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    number = float(value)
    if number != number or number in {float("inf"), float("-inf")}:
        raise ValueError(f"{name} must be finite")
    return number


class ExchangeValidationStatus(StrEnum):
    """Closed validation outcomes persisted on exchange records."""

    VALIDATED = "validated"
    SCHEMA_MISMATCH = "schema_mismatch"
    FORMAT_MISMATCH = "format_mismatch"
    REFUSED = "refused"


@dataclass(frozen=True, slots=True)
class SchemaIdentity:
    """Import qualname plus canonical JSON Schema digest."""

    qualname: str
    digest: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "qualname",
            _require_non_blank(
                "SchemaIdentity.qualname",
                self.qualname,
                max_chars=_MAX_QUALNAME_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "digest",
            _require_digest("SchemaIdentity.digest", self.digest),
        )

    def __repr__(self) -> str:
        return (
            "SchemaIdentity("
            f"qualname={self.qualname!r}, "
            f"digest={self.digest[:12]!r}…)"
        )


@dataclass(frozen=True, slots=True)
class ExchangePromptRef:
    """Nullable prompt identity embedded in an exchange record."""

    name: str
    version: str
    digest: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "name",
            _require_segment("ExchangePromptRef.name", self.name),
        )
        object.__setattr__(
            self,
            "version",
            _require_segment("ExchangePromptRef.version", self.version),
        )
        object.__setattr__(
            self,
            "digest",
            _require_digest("ExchangePromptRef.digest", self.digest),
        )

    def __repr__(self) -> str:
        return (
            "ExchangePromptRef("
            f"name={self.name!r}, "
            f"version={self.version!r}, "
            f"digest={self.digest[:12]!r}…)"
        )


@dataclass(frozen=True, slots=True)
class ExchangeEffectiveOptions:
    """Effective generation options snapshot (temperature=0 preserved)."""

    temperature: float | None = None
    max_output_tokens: int | None = None
    top_p: float | None = None
    seed: int | None = None
    stop: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.temperature is not None:
            object.__setattr__(
                self,
                "temperature",
                _require_finite_number("temperature", self.temperature),
            )
        if self.max_output_tokens is not None:
            tokens = _require_non_negative_int(
                "max_output_tokens", self.max_output_tokens
            )
            if tokens < 1:
                raise ValueError("max_output_tokens must be >= 1")
            object.__setattr__(self, "max_output_tokens", tokens)
        if self.top_p is not None:
            object.__setattr__(
                self, "top_p", _require_finite_number("top_p", self.top_p)
            )
        if self.seed is not None:
            object.__setattr__(
                self, "seed", _require_non_negative_int("seed", self.seed)
            )
        if self.stop is not None:
            if not isinstance(self.stop, tuple):
                raise TypeError("stop must be a tuple of strings")
            if len(self.stop) > 8:
                raise ValueError("stop exceeds maximum entries")
            cleaned = tuple(
                _require_non_blank("stop entry", item, max_chars=64)
                for item in self.stop
            )
            object.__setattr__(self, "stop", cleaned)

    def __repr__(self) -> str:
        return (
            "ExchangeEffectiveOptions("
            f"temperature={self.temperature!r}, "
            f"max_output_tokens={self.max_output_tokens!r}, "
            f"top_p={self.top_p!r}, "
            f"seed={self.seed!r}, "
            f"stop_count={0 if self.stop is None else len(self.stop)})"
        )


@dataclass(frozen=True, slots=True)
class ExchangeValidation:
    """Closed validation status plus stable reason code."""

    status: ExchangeValidationStatus
    reason_code: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, ExchangeValidationStatus):
            raise TypeError("status must be ExchangeValidationStatus")
        object.__setattr__(
            self,
            "reason_code",
            _require_segment("ExchangeValidation.reason_code", self.reason_code),
        )

    def __repr__(self) -> str:
        return (
            "ExchangeValidation("
            f"status={self.status.value!r}, "
            f"reason_code={self.reason_code!r})"
        )


@dataclass(frozen=True, slots=True)
class ExchangeUsage:
    """Allowlisted token usage snapshot."""

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
            "ExchangeUsage("
            f"input_tokens={self.input_tokens}, "
            f"output_tokens={self.output_tokens}, "
            f"total_tokens={self.total_tokens})"
        )


@dataclass(frozen=True, slots=True)
class ExchangeCorrelation:
    """Correlation ids stored with an exchange (never logged as payloads)."""

    run_id: str
    agent_id: str
    tick: int
    llm_request_id: str
    upstream_request_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "run_id", _require_safe_id("ExchangeCorrelation.run_id", self.run_id)
        )
        object.__setattr__(
            self,
            "agent_id",
            _require_safe_id("ExchangeCorrelation.agent_id", self.agent_id),
        )
        object.__setattr__(
            self,
            "tick",
            _require_non_negative_int("ExchangeCorrelation.tick", self.tick),
        )
        object.__setattr__(
            self,
            "llm_request_id",
            _require_header_safe_id(
                "ExchangeCorrelation.llm_request_id",
                self.llm_request_id,
            ),
        )
        if self.upstream_request_id is not None:
            object.__setattr__(
                self,
                "upstream_request_id",
                _require_header_safe_id(
                    "ExchangeCorrelation.upstream_request_id",
                    self.upstream_request_id,
                ),
            )

    def __repr__(self) -> str:
        return (
            "ExchangeCorrelation("
            f"run_id={self.run_id!r}, "
            f"agent_id={self.agent_id!r}, "
            f"tick={self.tick}, "
            f"llm_request_id={self.llm_request_id!r}, "
            f"has_upstream_request_id={self.upstream_request_id is not None})"
        )


@dataclass(frozen=True, slots=True)
class LLMExchangeRecord:
    """Versioned LLM exchange document (``llm-exchange-v1``)."""

    provider: str
    model: str
    structured_output_mode: StructuredOutputMode
    schema_identity: SchemaIdentity
    prompt: ExchangePromptRef | None
    request_digest: str
    effective_options: ExchangeEffectiveOptions
    validation: ExchangeValidation
    response: Mapping[str, object] | None
    usage: ExchangeUsage | None
    latency_ms: int
    correlation: ExchangeCorrelation
    component: str
    cache_namespace: str
    recorded_at_monotonic_offset: float | None = None
    schema_id: str = LLM_EXCHANGE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != LLM_EXCHANGE_SCHEMA_ID:
            raise ValueError("unsupported exchange schema_id")
        object.__setattr__(
            self,
            "provider",
            _require_non_blank(
                "LLMExchangeRecord.provider",
                self.provider,
                max_chars=_MAX_PROVIDER_NAME_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "model",
            _require_non_blank(
                "LLMExchangeRecord.model",
                self.model,
                max_chars=_MAX_MODEL_NAME_CHARS,
            ),
        )
        if not isinstance(self.structured_output_mode, StructuredOutputMode):
            raise TypeError("structured_output_mode must be StructuredOutputMode")
        if type(self.schema_identity) is not SchemaIdentity:
            raise TypeError("schema_identity must be SchemaIdentity")
        if self.prompt is not None and type(self.prompt) is not ExchangePromptRef:
            raise TypeError("prompt must be ExchangePromptRef")
        object.__setattr__(
            self,
            "request_digest",
            _require_digest("LLMExchangeRecord.request_digest", self.request_digest),
        )
        if type(self.effective_options) is not ExchangeEffectiveOptions:
            raise TypeError("effective_options must be ExchangeEffectiveOptions")
        if type(self.validation) is not ExchangeValidation:
            raise TypeError("validation must be ExchangeValidation")
        if self.response is not None:
            if not isinstance(self.response, Mapping):
                raise TypeError("response must be a mapping or None")
            if len(self.response) > _MAX_RESPONSE_KEYS:
                raise ValueError("response exceeds maximum key count")
            object.__setattr__(self, "response", dict(self.response))
        if self.usage is not None and type(self.usage) is not ExchangeUsage:
            raise TypeError("usage must be ExchangeUsage")
        object.__setattr__(
            self,
            "latency_ms",
            _require_non_negative_int("LLMExchangeRecord.latency_ms", self.latency_ms),
        )
        if type(self.correlation) is not ExchangeCorrelation:
            raise TypeError("correlation must be ExchangeCorrelation")
        object.__setattr__(
            self,
            "component",
            _require_segment("LLMExchangeRecord.component", self.component),
        )
        object.__setattr__(
            self,
            "cache_namespace",
            _require_non_blank(
                "LLMExchangeRecord.cache_namespace",
                self.cache_namespace,
                max_chars=_MAX_NAMESPACE_CHARS,
            ),
        )
        if self.recorded_at_monotonic_offset is not None:
            offset = _require_finite_number(
                "recorded_at_monotonic_offset",
                self.recorded_at_monotonic_offset,
            )
            if offset < 0.0:
                raise ValueError("recorded_at_monotonic_offset must be >= 0")
            object.__setattr__(self, "recorded_at_monotonic_offset", offset)

    def __repr__(self) -> str:
        response_keys = 0 if self.response is None else len(self.response)
        return (
            "LLMExchangeRecord("
            f"schema_id={self.schema_id!r}, "
            f"provider={self.provider!r}, "
            f"model={self.model!r}, "
            f"structured_output_mode={self.structured_output_mode.value!r}, "
            f"schema_digest={self.schema_identity.digest[:12]!r}…, "
            f"request_digest={self.request_digest[:12]!r}…, "
            f"has_prompt={self.prompt is not None}, "
            f"validation={self.validation.status.value!r}, "
            f"response_keys={response_keys}, "
            f"has_usage={self.usage is not None}, "
            f"latency_ms={self.latency_ms}, "
            f"component={self.component!r}, "
            f"cache_namespace_chars={len(self.cache_namespace)}, "
            f"has_monotonic_offset="
            f"{self.recorded_at_monotonic_offset is not None})"
        )
