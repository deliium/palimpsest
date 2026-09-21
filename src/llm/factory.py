"""Standalone LLM provider factory.

Constructs disabled or OpenAI-compatible providers from **provider-owned**
configuration values. This module does not import ``infrastructure``, read
environment variables, allocate a network connection, or probe an endpoint.

A future cognition consumer owns settings-to-factory mapping and provider
lifecycle composition (API lifespan, ``app.state``, FastAPI dependencies, and
compose wiring remain out of scope until that consumer exists).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from llm.errors import LLMError, LLMErrorCode
from llm.models import (
    LLMRequest,
    LLMResult,
    ProviderDefaults,
    RetryPolicy,
    StructuredOutput,
    StructuredOutputMode,
)
from llm.providers.openai_compatible import OpenAICompatibleProvider

__all__ = [
    "DisabledLLMProvider",
    "ProviderAdapterKind",
    "ProviderFactoryConfig",
    "create_llm_provider",
]

_LOG: Final[logging.Logger] = logging.getLogger("llm.factory")

AsyncSleep = Callable[[float], Awaitable[None]]
MonotonicClock = Callable[[], float]

_DEFAULT_MAX_REQUEST_BYTES: Final[int] = 1_048_576
_DEFAULT_MAX_RESPONSE_BYTES: Final[int] = 1_048_576
_DEFAULT_MAX_HEADER_BYTES: Final[int] = 8_192


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
