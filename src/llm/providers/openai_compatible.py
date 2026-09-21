"""Bounded async OpenAI-compatible HTTP provider.

Uses :mod:`httpx` for transport only. Wire encoding/decoding stays in
:mod:`llm.providers.openai_compatible_codec`. Logging is metadata-only via
``logging.getLogger("llm.openai_compatible")``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Final

import httpx

from llm.errors import (
    LLMError,
    LLMErrorCode,
    error_from_http_status,
    error_from_httpx,
    retry_exhausted,
)
from llm.models import (
    LLMRequest,
    LLMResult,
    ProviderDefaults,
    RetryPolicy,
    StructuredOutput,
    StructuredOutputMode,
    resolve_effective_options,
)
from llm.providers.openai_compatible_codec import (
    decode_chat_completions_response,
    encode_chat_completions_body,
)

__all__ = [
    "CORRELATION_HEADER_NAME",
    "OpenAICompatibleProvider",
]

_LOG: Final[logging.Logger] = logging.getLogger("llm.openai_compatible")

CORRELATION_HEADER_NAME: Final[str] = "X-LLM-Request-ID"

_DEFAULT_PROVIDER_NAME: Final[str] = "openai_compatible"
_DEFAULT_MAX_REQUEST_BYTES: Final[int] = 1_048_576
_DEFAULT_MAX_RESPONSE_BYTES: Final[int] = 1_048_576
_DEFAULT_MAX_HEADER_BYTES: Final[int] = 8_192
_CHAT_COMPLETIONS_PATH: Final[str] = "chat/completions"

AsyncSleep = Callable[[float], Awaitable[None]]
MonotonicClock = Callable[[], float]


class _AttemptFailure(Exception):
    """Internal retryable/terminal attempt failure with optional Retry-After."""

    def __init__(
        self,
        error: LLMError,
        *,
        retry_after_seconds: float | None = None,
    ) -> None:
        self.error = error
        self.retry_after_seconds = retry_after_seconds
        super().__init__(error.code.value)
        self.__cause__ = None
        self.__context__ = None
        self.__suppress_context__ = True


def _normalize_base_url(base_url: str) -> str:
    """Ensure a single trailing slash so relative paths preserve ``/v1/``."""
    if not isinstance(base_url, str):
        raise TypeError("base_url must be a string")
    if not base_url or base_url.strip() != base_url or not base_url.strip():
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    if base_url.endswith("/"):
        return base_url
    return f"{base_url}/"


def _require_positive_byte_limit(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a positive integer")
    if value < 1:
        raise ValueError(f"{name} must be >= 1")
    return value


def _require_non_blank_config(name: str, value: object, *, max_chars: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value or value.strip() != value or not value.strip():
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    if len(value) > max_chars:
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    return value


class OpenAICompatibleProvider:
    """Async OpenAI-compatible chat/completions adapter.

    Constructor is pure configuration: no network I/O. An owned
    :class:`httpx.AsyncClient` is built lazily on first ``generate`` when
    ``client`` is omitted. Injected clients are never closed by this provider.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        mode: StructuredOutputMode,
        sleep: AsyncSleep,
        monotonic: MonotonicClock,
        api_key: str | None = None,
        provider_name: str = _DEFAULT_PROVIDER_NAME,
        defaults: ProviderDefaults | None = None,
        retry: RetryPolicy | None = None,
        client: httpx.AsyncClient | None = None,
        send_correlation_header: bool = False,
        correlation_header_name: str = CORRELATION_HEADER_NAME,
        max_request_bytes: int = _DEFAULT_MAX_REQUEST_BYTES,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
        max_header_bytes: int = _DEFAULT_MAX_HEADER_BYTES,
    ) -> None:
        if not callable(sleep):
            raise TypeError("sleep must be an async callable")
        if not callable(monotonic):
            raise TypeError("monotonic must be a callable")
        if not isinstance(mode, StructuredOutputMode):
            raise TypeError("mode must be StructuredOutputMode")
        if not isinstance(send_correlation_header, bool):
            raise TypeError("send_correlation_header must be bool")
        if client is not None and not isinstance(client, httpx.AsyncClient):
            raise TypeError("client must be httpx.AsyncClient")
        if defaults is not None and type(defaults) is not ProviderDefaults:
            raise TypeError("defaults must be ProviderDefaults")
        if retry is not None and type(retry) is not RetryPolicy:
            raise TypeError("retry must be RetryPolicy")

        self._base_url = _normalize_base_url(base_url)
        self._model = _require_non_blank_config("model", model, max_chars=128)
        self._mode = mode
        self._sleep = sleep
        self._monotonic = monotonic
        self._api_key = _normalize_api_key(api_key)
        self._provider_name = _require_non_blank_config(
            "provider_name",
            provider_name,
            max_chars=64,
        )
        self._defaults = defaults if defaults is not None else ProviderDefaults()
        self._retry = retry if retry is not None else RetryPolicy()
        self._send_correlation_header = send_correlation_header
        self._correlation_header_name = _require_header_name(correlation_header_name)
        self._max_request_bytes = _require_positive_byte_limit(
            "max_request_bytes",
            max_request_bytes,
        )
        self._max_response_bytes = _require_positive_byte_limit(
            "max_response_bytes",
            max_response_bytes,
        )
        self._max_header_bytes = _require_positive_byte_limit(
            "max_header_bytes",
            max_header_bytes,
        )

        self._owns_client = client is None
        self._client: httpx.AsyncClient | None = client
        self._closed = False
        self._close_started = False

    @property
    def closed(self) -> bool:
        """Whether ``close`` has completed (idempotent)."""
        return self._closed

    def __repr__(self) -> str:
        return (
            "OpenAICompatibleProvider("
            f"provider_name={self._provider_name!r}, "
            f"model={self._model!r}, "
            f"mode={self._mode.value!r}, "
            f"owns_client={self._owns_client}, "
            f"closed={self._closed})"
        )

    async def close(self) -> None:
        """Close an owned client exactly once. Injected clients are untouched."""
        if self._closed or self._close_started:
            return
        self._close_started = True
        try:
            if self._owns_client and self._client is not None:
                await self._client.aclose()
        finally:
            self._closed = True

    async def generate[T: StructuredOutput](
        self, request: LLMRequest[T]
    ) -> LLMResult[T]:
        """Generate structured output for ``request`` with deterministic retries."""
        if type(request) is not LLMRequest:
            raise TypeError("request must be LLMRequest")
        if self._closed or self._close_started:
            raise LLMError(LLMErrorCode.CLOSED, retryable=False)

        effective = resolve_effective_options(self._defaults, request.options)
        encode_error: LLMError | None = None
        try:
            body = encode_chat_completions_body(
                request,
                model=self._model,
                mode=self._mode,
                options=effective,
            )
        except LLMError as exc:
            encode_error = _with_attempts(exc, attempts=1)
        if encode_error is not None:
            _log_terminal(
                encode_error,
                llm_request_id=request.context.llm_request_id,
            )
            raise encode_error

        prepare_error: LLMError | None = None
        try:
            payload = _encode_request_bytes(body, max_bytes=self._max_request_bytes)
            headers = self._build_headers(request.context.llm_request_id)
        except LLMError as exc:
            prepare_error = _with_attempts(exc, attempts=1)
        if prepare_error is not None:
            _log_terminal(
                prepare_error,
                llm_request_id=request.context.llm_request_id,
            )
            raise prepare_error

        llm_request_id = request.context.llm_request_id
        _LOG.debug(
            "generate_started llm_request_id=%s model=%s mode=%s max_attempts=%s",
            llm_request_id,
            self._model,
            self._mode.value,
            self._retry.max_attempts,
        )

        started = self._monotonic()
        last_error: LLMError | None = None
        attempt = 0

        while attempt < self._retry.max_attempts:
            if self._closed or self._close_started:
                raise LLMError(LLMErrorCode.CLOSED, retryable=False)

            deadline_error = self._deadline_exceeded(started, attempts=max(attempt, 1))
            if deadline_error is not None:
                if last_error is not None:
                    exhausted = retry_exhausted(
                        _with_attempts(last_error, attempts=last_error.attempts)
                    )
                    _log_terminal(
                        exhausted,
                        llm_request_id=llm_request_id,
                    )
                    raise exhausted
                _log_terminal(deadline_error, llm_request_id=llm_request_id)
                raise deadline_error

            attempt += 1
            _LOG.debug(
                "attempt_started llm_request_id=%s attempt=%s",
                llm_request_id,
                attempt,
            )

            pending: LLMError | None = None
            try:
                result = await self._attempt(
                    request,
                    payload=payload,
                    headers=headers,
                    attempts=attempt,
                )
            except _AttemptFailure as failure:
                error = _with_attempts(failure.error, attempts=attempt)
                last_error = error
                if self._policy_retryable(error) and attempt < self._retry.max_attempts:
                    _LOG.warning(
                        "attempt_failed_retryable llm_request_id=%s attempt=%s "
                        "code=%s status=%s",
                        llm_request_id,
                        attempt,
                        error.code.value,
                        error.status if error.status is not None else "-",
                    )
                    delay = self._resolve_delay(
                        failure_ordinal=attempt,
                        retry_after_seconds=failure.retry_after_seconds,
                        started=started,
                    )
                    if delay is None:
                        pending = retry_exhausted(error)
                        _log_terminal(pending, llm_request_id=llm_request_id)
                    else:
                        _LOG.debug(
                            "retry_scheduled llm_request_id=%s attempt=%s "
                            "code=%s delay_seconds=%s",
                            llm_request_id,
                            attempt,
                            error.code.value,
                            delay,
                        )
                        await self._sleep(delay)
                        continue
                elif self._policy_retryable(error):
                    pending = retry_exhausted(error)
                    _log_terminal(pending, llm_request_id=llm_request_id)
                else:
                    pending = error
                    _log_terminal(pending, llm_request_id=llm_request_id)
            if pending is not None:
                # Raise outside the ``except`` so ``__context__`` stays empty.
                raise pending

            usage = result.metadata.usage
            _LOG.info(
                "generate_succeeded llm_request_id=%s attempt=%s "
                "finish_reason=%s input_tokens=%s output_tokens=%s",
                llm_request_id,
                attempt,
                result.metadata.finish_reason.value,
                usage.input_tokens if usage is not None else "-",
                usage.output_tokens if usage is not None else "-",
            )
            return result

        assert last_error is not None
        exhausted = retry_exhausted(last_error)
        _log_terminal(exhausted, llm_request_id=llm_request_id)
        raise exhausted

    def _policy_retryable(self, error: LLMError) -> bool:
        """Whether ``error`` is retryable under policy, ignoring attempt count."""
        if error.code is LLMErrorCode.RETRY_EXHAUSTION:
            return False
        if error.code is LLMErrorCode.OUTPUT_FORMAT:
            return bool(self._retry.retry_output_format and error.retryable)
        if error.code is LLMErrorCode.OUTPUT_SCHEMA:
            return bool(self._retry.retry_output_schema and error.retryable)
        return bool(error.retryable)

    async def _attempt[T: StructuredOutput](
        self,
        request: LLMRequest[T],
        *,
        payload: bytes,
        headers: dict[str, str],
        attempts: int,
    ) -> LLMResult[T]:
        client = self._ensure_client()
        timeout = httpx.Timeout(self._retry.per_attempt_timeout_seconds)
        try:
            async with client.stream(
                "POST",
                _CHAT_COMPLETIONS_PATH,
                content=payload,
                headers=headers,
                timeout=timeout,
            ) as response:
                status = int(response.status_code)
                retry_after = _parse_retry_after_header(response.headers)
                raw = await _read_bounded_response(
                    response,
                    max_bytes=self._max_response_bytes,
                )
        except LLMError as exc:
            raise _AttemptFailure(_with_attempts(exc, attempts=attempts)) from None
        except httpx.HTTPError as exc:
            raise _AttemptFailure(
                error_from_httpx(exc, attempts=attempts)
            ) from None

        if status < 200 or status >= 300:
            raise _AttemptFailure(
                error_from_http_status(status, attempts=attempts),
                retry_after_seconds=retry_after,
            )

        try:
            parsed = _parse_json_object(raw)
        except LLMError as exc:
            raise _AttemptFailure(_with_attempts(exc, attempts=attempts)) from None
        del raw

        try:
            return decode_chat_completions_response(
                parsed,
                response_model=request.response_model,
                provider_name=self._provider_name,
                model_name=self._model,
                attempts=attempts,
            )
        except LLMError as exc:
            raise _AttemptFailure(_with_attempts(exc, attempts=attempts)) from None
        finally:
            del parsed

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._closed or self._close_started:
            raise LLMError(LLMErrorCode.CLOSED, retryable=False)
        if self._client is not None:
            return self._client
        # Owned client: construct without network I/O.
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            follow_redirects=False,
            trust_env=False,
            timeout=httpx.Timeout(self._retry.per_attempt_timeout_seconds),
        )
        return self._client

    def _build_headers(self, llm_request_id: str) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._api_key is not None:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if self._send_correlation_header:
            headers[self._correlation_header_name] = llm_request_id

        encoded_size = sum(
            len(key.encode("ascii")) + len(value.encode("utf-8")) + 4
            for key, value in headers.items()
        )
        if encoded_size > self._max_header_bytes:
            raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
        return headers

    def _deadline_exceeded(
        self,
        started: float,
        *,
        attempts: int,
    ) -> LLMError | None:
        deadline = self._retry.total_deadline_seconds
        if deadline is None:
            return None
        elapsed = self._monotonic() - started
        if elapsed < deadline:
            return None
        return LLMError(LLMErrorCode.TIMEOUT, retryable=True, attempts=attempts)

    def _resolve_delay(
        self,
        *,
        failure_ordinal: int,
        retry_after_seconds: object,
        started: float,
    ) -> float | None:
        delay = self._retry.resolve_delay_seconds(
            failure_ordinal,
            retry_after_seconds=retry_after_seconds,
        )
        deadline = self._retry.total_deadline_seconds
        if deadline is None:
            return delay
        remaining = deadline - (self._monotonic() - started)
        if remaining <= 0.0:
            return None
        return min(delay, remaining)


def _normalize_api_key(api_key: str | None) -> str | None:
    if api_key is None:
        return None
    if not isinstance(api_key, str):
        raise TypeError("api_key must be a string")
    if not api_key or api_key.strip() != api_key or not api_key.strip():
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    return api_key


def _require_header_name(name: object) -> str:
    if not isinstance(name, str):
        raise TypeError("correlation_header_name must be a string")
    if not name or name.strip() != name:
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    # Token-ish header names only (no spaces / control chars).
    if any(ord(ch) < 33 or ord(ch) > 126 or ch == ":" for ch in name):
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    return name


def _encode_request_bytes(body: Mapping[str, object], *, max_bytes: int) -> bytes:
    try:
        text = json.dumps(
            body,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False) from None
    payload = text.encode("utf-8")
    if len(payload) > max_bytes:
        raise LLMError(LLMErrorCode.CONFIGURATION, retryable=False)
    return payload


async def _read_bounded_response(
    response: httpx.Response,
    *,
    max_bytes: int,
) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise LLMError(
                LLMErrorCode.PROVIDER_PROTOCOL,
                retryable=False,
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _parse_json_object(raw: bytes) -> dict[str, object]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise LLMError(LLMErrorCode.PROVIDER_PROTOCOL, retryable=False) from None
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        raise LLMError(LLMErrorCode.PROVIDER_PROTOCOL, retryable=False) from None
    if not isinstance(value, dict):
        raise LLMError(LLMErrorCode.PROVIDER_PROTOCOL, retryable=False)
    return value


def _parse_retry_after_header(headers: httpx.Headers) -> float | None:
    raw = headers.get("Retry-After")
    if raw is None:
        return None
    try:
        # Delta-seconds only; HTTP-date forms are rejected by RetryPolicy.
        return float(raw)
    except (TypeError, ValueError):
        return None


def _with_attempts(error: LLMError, *, attempts: int) -> LLMError:
    if error.attempts == attempts:
        return error
    return LLMError(
        error.code,
        retryable=error.retryable,
        attempts=attempts,
        status=error.status,
        last_code=error.last_code,
    )


def _log_terminal(error: LLMError, *, llm_request_id: str) -> None:
    fields = error.log_fields()
    _LOG.error(
        "generate_failed llm_request_id=%s code=%s retryable=%s attempts=%s "
        "status=%s last_code=%s",
        llm_request_id,
        fields["code"],
        fields["retryable"],
        fields["attempts"],
        fields.get("status", "-"),
        fields.get("last_code", "-"),
    )
