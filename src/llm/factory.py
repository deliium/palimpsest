"""Standalone LLM provider factory.

Constructs disabled or OpenAI-compatible providers from **provider-owned**
configuration values. This module does not import ``infrastructure``, read
environment variables, allocate a network connection, or probe an endpoint.

A future cognition consumer owns settings-to-factory mapping and provider
lifecycle composition (API lifespan, ``app.state``, FastAPI dependencies, and
compose wiring remain out of scope until that consumer exists).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from llm.errors import LLMError, LLMErrorCode
from llm.models import (
    FinishReason,
    LLMRequest,
    LLMResult,
    LLMResultMetadata,
    ProviderDefaults,
    RetryPolicy,
    StructuredOutput,
    StructuredOutputMode,
)
from llm.providers.openai_compatible import OpenAICompatibleProvider

__all__ = [
    "ConcurrencyLimitedLLMProvider",
    "DeterministicFakeLLMProvider",
    "DisabledLLMProvider",
    "ProviderAdapterKind",
    "ProviderFactoryConfig",
    "create_llm_provider",
    "wrap_llm_concurrency",
]


_LOG: Final[logging.Logger] = logging.getLogger("llm.factory")

AsyncSleep = Callable[[float], Awaitable[None]]
MonotonicClock = Callable[[], float]

_DEFAULT_MAX_REQUEST_BYTES: Final[int] = 1_048_576
_DEFAULT_MAX_RESPONSE_BYTES: Final[int] = 1_048_576
_DEFAULT_MAX_HEADER_BYTES: Final[int] = 8_192
_EVIDENCE_JSON_RE: Final[re.Pattern[str]] = re.compile(
    r"\{[^{}]*\"sources\"\s*:\s*\[[\s\S]*?\].*?\}"
)


class ProviderAdapterKind(StrEnum):
    """Factory adapter selector (provider-owned; not settings)."""

    DISABLED = "disabled"
    OPENAI_COMPATIBLE = "openai_compatible"


@dataclass(frozen=True, slots=True)
class ProviderFactoryConfig:
    """Immutable provider construction inputs.

    Callers (a future cognition consumer) map validated settings into this
    value. The factory never reads the environment.
    """

    adapter_kind: ProviderAdapterKind = ProviderAdapterKind.DISABLED
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    mode: StructuredOutputMode = StructuredOutputMode.JSON_SCHEMA
    temperature: float | None = None
    max_attempts: int = 3
    per_attempt_timeout_seconds: float = 30.0
    total_deadline_seconds: float | None = None
    max_request_bytes: int = _DEFAULT_MAX_REQUEST_BYTES
    max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES
    max_header_bytes: int = _DEFAULT_MAX_HEADER_BYTES
    send_correlation_header: bool = False
    provider_name: str = "openai_compatible"

    def __repr__(self) -> str:
        return (
            "ProviderFactoryConfig("
            f"adapter_kind={self.adapter_kind.value!r}, "
            f"model={self.model!r}, "
            f"mode={self.mode.value!r}, "
            f"has_api_key={self.api_key is not None}, "
            f"has_base_url={self.base_url is not None}, "
            f"max_attempts={self.max_attempts}, "
            f"per_attempt_timeout_seconds={self.per_attempt_timeout_seconds}, "
            f"send_correlation_header={self.send_correlation_header})"
        )


class DisabledLLMProvider:
    """Provider that fails closed with a safe configuration error.

    Used when the adapter kind is ``disabled``. Construction allocates no
    network resources.
    """

    def __repr__(self) -> str:
        return "DisabledLLMProvider()"

    async def close(self) -> None:
        """No-op close for lifecycle symmetry with real adapters."""
        return None

    async def generate[T: StructuredOutput](
        self, request: LLMRequest[T]
    ) -> LLMResult[T]:
        if type(request) is not LLMRequest:
            raise TypeError("request must be LLMRequest")
        _LOG.error(
            "generate_rejected reason=disabled adapter_kind=%s",
            ProviderAdapterKind.DISABLED.value,
        )
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)


class DeterministicFakeLLMProvider:
    """Closeable deterministic provider for reproducible offline reconstruction.

    Synthesizes structured candidates from request-embedded evidence JSON when
    possible. Never contacts a network endpoint and never logs payloads.
    """

    __slots__ = ("_closed", "_provider_name")

    def __init__(self, *, provider_name: str = "deterministic_fake") -> None:
        self._closed = False
        self._provider_name = provider_name

    def __repr__(self) -> str:
        return (
            f"DeterministicFakeLLMProvider(provider_name={self._provider_name!r}, "
            f"closed={self._closed})"
        )

    async def close(self) -> None:
        self._closed = True
        _LOG.debug(
            "deterministic_fake_closed provider_name=%s",
            self._provider_name,
        )

    async def generate[T: StructuredOutput](
        self, request: LLMRequest[T]
    ) -> LLMResult[T]:
        if type(request) is not LLMRequest:
            raise TypeError("request must be LLMRequest")
        if self._closed:
            _LOG.error(
                "generate_rejected reason=closed adapter_kind=deterministic_fake"
            )
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
        model = request.response_model
        output = _synthesize_structured(model, request=request)
        _LOG.debug(
            "deterministic_fake_generate response_model=%s tick=%s status=ok",
            model.__name__,
            request.context.tick,
        )
        return LLMResult(
            output=output,
            metadata=LLMResultMetadata(
                provider_name=self._provider_name,
                model_name="deterministic-fake-v1",
                finish_reason=FinishReason.STOP,
            ),
        )


def _synthesize_structured[T: StructuredOutput](
    model: type[T],
    *,
    request: LLMRequest[T],
) -> T:
    """Build a deterministic structured candidate from request evidence.

    Uses request evidence when a reconstruction-shaped model is requested.
    """
    if model.__name__ == "ReconstructedMemoryCandidate":
        payload = _extract_evidence_payload(request)
        sources = payload.get("sources", []) if isinstance(payload, dict) else []
        if not isinstance(sources, list):
            sources = []
        source_ids: list[str] = []
        concepts: list[str] = []
        entity_labels: list[str] = []
        entity_ids: list[str | None] = []
        context_tags: list[str] = ["deterministic"]
        location_id: str | None = None
        confidence = 0.5
        salience = 0.3
        for source in sources:
            if not isinstance(source, dict):
                continue
            mid = source.get("memory_id")
            if isinstance(mid, str):
                source_ids.append(mid)
            for concept in source.get("concepts", ()) or ():
                if isinstance(concept, dict):
                    value = concept.get("concept")
                    if isinstance(value, str) and value not in concepts:
                        concepts.append(value)
                elif isinstance(concept, str) and concept not in concepts:
                    concepts.append(concept)
            for entity in source.get("entities", ()) or ():
                if not isinstance(entity, dict):
                    continue
                label = entity.get("label")
                if isinstance(label, str):
                    entity_labels.append(label)
                    eid = entity.get("entity_id")
                    entity_ids.append(eid if isinstance(eid, str) else None)
            conf = source.get("confidence")
            if isinstance(conf, (int, float)):
                confidence = max(confidence, float(conf) * 0.9)
            sal = source.get("emotional_salience")
            if isinstance(sal, (int, float)):
                salience = max(salience, float(sal) * 0.9)
            loc = source.get("location_id")
            if isinstance(loc, str):
                location_id = loc
            for tag in source.get("context_tags", ()) or ():
                if isinstance(tag, str) and tag not in context_tags:
                    context_tags.append(tag)
            ctx = source.get("context")
            if isinstance(ctx, dict):
                loc = ctx.get("location_id")
                if isinstance(loc, str):
                    location_id = loc
                for tag in ctx.get("tags", ()) or ():
                    if isinstance(tag, str) and tag not in context_tags:
                        context_tags.append(tag)
        return model(
            narrative="deterministic-reconstruction",
            concepts=tuple(concepts[:16]),
            entity_labels=tuple(entity_labels[:16]),
            entity_ids=tuple(entity_ids[:16]),
            relation_predicates=(),
            relation_subject_indexes=(),
            relation_object_indexes=(),
            relation_subject_kinds=(),
            relation_object_kinds=(),
            context_tags=tuple(context_tags[:16]),
            location_id=location_id,
            confidence=min(1.0, max(0.0, confidence)),
            emotional_salience=min(1.0, max(0.0, salience)),
            source_memory_ids=tuple(source_ids),
        )
    # Generic fallback: empty construction if the model permits it.
    try:
        return model.model_validate({})  # type: ignore[attr-defined]
    except Exception as exc:
        _LOG.error(
            "deterministic_fake_unsupported response_model=%s reason_code=%s",
            model.__name__,
            type(exc).__name__,
        )
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False) from None


def _extract_evidence_payload(request: LLMRequest[Any]) -> dict[str, Any]:
    for message in reversed(request.messages):
        content = getattr(message, "content", None)
        if not isinstance(content, str):
            continue
        match = _EVIDENCE_JSON_RE.search(content)
        if match is None:
            # Prefer the largest JSON object in the message.
            start = content.find("{")
            end = content.rfind("}")
            if start < 0 or end <= start:
                continue
            candidate = content[start : end + 1]
        else:
            candidate = match.group(0)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "sources" in parsed:
            return parsed
    return {}


def create_llm_provider(
    config: ProviderFactoryConfig,
    *,
    sleep: AsyncSleep,
    monotonic: MonotonicClock,
) -> DisabledLLMProvider | OpenAICompatibleProvider:
    """Build a provider from ``config`` without network I/O or env access.

    ``sleep`` and ``monotonic`` are required so retries stay deterministic and
    injectable. An owned ``httpx.AsyncClient`` is created lazily by
    :class:`OpenAICompatibleProvider` on first ``generate``, not here.
    """
    if type(config) is not ProviderFactoryConfig:
        raise TypeError("config must be ProviderFactoryConfig")
    if not callable(sleep):
        raise TypeError("sleep must be an async callable")
    if not callable(monotonic):
        raise TypeError("monotonic must be a callable")

    enabled = config.adapter_kind is not ProviderAdapterKind.DISABLED
    model_safe = config.model if config.model is not None else "-"
    _LOG.debug(
        "create_llm_provider adapter_kind=%s model=%s mode=%s enabled=%s "
        "has_api_key=%s max_attempts=%s per_attempt_timeout_seconds=%s "
        "has_total_deadline=%s max_request_bytes=%s max_response_bytes=%s "
        "max_header_bytes=%s send_correlation_header=%s",
        config.adapter_kind.value,
        model_safe,
        config.mode.value,
        enabled,
        config.api_key is not None,
        config.max_attempts,
        config.per_attempt_timeout_seconds,
        config.total_deadline_seconds is not None,
        config.max_request_bytes,
        config.max_response_bytes,
        config.max_header_bytes,
        config.send_correlation_header,
    )

    if config.adapter_kind is ProviderAdapterKind.DISABLED:
        _LOG.info(
            "provider_created adapter_kind=%s enabled=%s",
            config.adapter_kind.value,
            False,
        )
        return DisabledLLMProvider()

    if config.adapter_kind is not ProviderAdapterKind.OPENAI_COMPATIBLE:
        _LOG.error(
            "provider_create_failed reason=unsupported_adapter adapter_kind=%s",
            config.adapter_kind.value,
        )
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)

    if config.base_url is None or config.model is None:
        _LOG.error(
            "provider_create_failed reason=missing_required_fields "
            "adapter_kind=%s has_model=%s has_base_url=%s",
            config.adapter_kind.value,
            config.model is not None,
            config.base_url is not None,
        )
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)

    defaults = ProviderDefaults(temperature=config.temperature)
    retry = RetryPolicy(
        max_attempts=config.max_attempts,
        per_attempt_timeout_seconds=config.per_attempt_timeout_seconds,
        total_deadline_seconds=config.total_deadline_seconds,
    )
    provider = OpenAICompatibleProvider(
        base_url=config.base_url,
        model=config.model,
        mode=config.mode,
        sleep=sleep,
        monotonic=monotonic,
        api_key=config.api_key,
        provider_name=config.provider_name,
        defaults=defaults,
        retry=retry,
        send_correlation_header=config.send_correlation_header,
        max_request_bytes=config.max_request_bytes,
        max_response_bytes=config.max_response_bytes,
        max_header_bytes=config.max_header_bytes,
    )
    _LOG.info(
        "provider_created adapter_kind=%s model=%s mode=%s enabled=%s "
        "has_api_key=%s max_attempts=%s",
        config.adapter_kind.value,
        model_safe,
        config.mode.value,
        True,
        config.api_key is not None,
        config.max_attempts,
    )
    return provider


class ConcurrencyLimitedLLMProvider:
    """Process-scoped semaphore around ``generate`` (default max=1)."""

    __slots__ = ("_in_flight", "_inner", "_max", "_semaphore")

    def __init__(self, inner: object, *, max_concurrency: int = 1) -> None:
        if (
            isinstance(max_concurrency, bool)
            or type(max_concurrency) is not int
            or max_concurrency < 1
        ):
            raise ValueError("max_concurrency must be >= 1")
        self._inner = inner
        self._max = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._in_flight = 0

    @property
    def provider_name(self) -> str:
        name = getattr(self._inner, "provider_name", None)
        return str(name) if name is not None else "concurrency_limited"

    async def close(self) -> None:
        close = getattr(self._inner, "close", None)
        if close is not None:
            await close()

    async def generate[T: StructuredOutput](
        self,
        request: LLMRequest[T],
    ) -> LLMResult[T]:
        async with self._semaphore:
            self._in_flight += 1
            try:
                _LOG.debug(
                    "[llm.concurrency] acquired in_flight=%s max=%s",
                    self._in_flight,
                    self._max,
                )
                return await self._inner.generate(request)  # type: ignore[no-any-return]
            finally:
                self._in_flight -= 1


def wrap_llm_concurrency(
    provider: object,
    *,
    max_concurrency: int = 1,
) -> object:
    """Gate ``generate`` with a process-scoped semaphore (identity when max=1)."""
    if max_concurrency == 1 and type(provider) is ConcurrencyLimitedLLMProvider:
        return provider
    return ConcurrencyLimitedLLMProvider(provider, max_concurrency=max_concurrency)
