"""Provider-neutral LLM errors with safe public surfaces.

Public errors expose only a stable code, retryability, total attempts, and an
optional HTTP status. They must never retain provider bodies, URLs, credentials,
offending inputs, raw exception text, unsafe causes/context, or Pydantic
``ValidationError`` details.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

__all__ = [
    "LLMError",
    "LLMErrorCode",
    "default_retryable",
    "error_from_http_status",
    "error_from_httpx",
    "error_from_validation_failure",
    "retry_exhausted",
]


class LLMErrorCode(StrEnum):
    """Stable provider-neutral failure codes."""

    CONFIGURATION = "configuration"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    UPSTREAM = "upstream"
    PROVIDER_PROTOCOL = "provider_protocol"
    OUTPUT_FORMAT = "output_format"
    OUTPUT_SCHEMA = "output_schema"
    REFUSAL = "refusal"
    INCOMPLETE = "incomplete"
    CLOSED = "closed"
    RETRY_EXHAUSTION = "retry_exhaustion"


# Default retryability by code. Status-specific factories may override.
# Retry: connection, selected timeouts, 408/429, selected 5xx, and (when
# configured) format/schema failures. Do not retry configuration, auth,
# refusal/filtering, malformed envelopes, ordinary 4xx, or size-limit failures.
_DEFAULT_RETRYABLE: Final[dict[LLMErrorCode, bool]] = {
    LLMErrorCode.CONFIGURATION: False,
    LLMErrorCode.TIMEOUT: True,
    LLMErrorCode.CONNECTION: True,
    LLMErrorCode.AUTHENTICATION: False,
    LLMErrorCode.RATE_LIMIT: True,
    LLMErrorCode.UPSTREAM: True,
    LLMErrorCode.PROVIDER_PROTOCOL: False,
    LLMErrorCode.OUTPUT_FORMAT: True,
    LLMErrorCode.OUTPUT_SCHEMA: True,
    LLMErrorCode.REFUSAL: False,
    LLMErrorCode.INCOMPLETE: False,
    LLMErrorCode.CLOSED: False,
    LLMErrorCode.RETRY_EXHAUSTION: False,
}

_RETRYABLE_HTTP_STATUSES: Final[frozenset[int]] = frozenset(
    {408, 429, 500, 502, 503, 504}
)
_AUTH_HTTP_STATUSES: Final[frozenset[int]] = frozenset({401, 403})


def default_retryable(code: LLMErrorCode) -> bool:
    """Return the default retryability for ``code``."""
    return _DEFAULT_RETRYABLE[code]


def _require_attempts(attempts: int) -> int:
    if isinstance(attempts, bool) or not isinstance(attempts, int):
        raise TypeError("attempts must be a positive integer")
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    return attempts


def _require_status(status: int | None) -> int | None:
    if status is None:
        return None
    if isinstance(status, bool) or not isinstance(status, int):
        raise TypeError("status must be an HTTP status integer")
    if status < 100 or status > 599:
        raise ValueError("status out of range")
    return status


def _detach(exc: BaseException) -> BaseException:
    """Ensure no unsafe cause/context is retained on the public error."""
    exc.__cause__ = None
    exc.__context__ = None
    exc.__suppress_context__ = True
    return exc


class LLMError(Exception):
    """Safe provider-neutral failure.

    Attributes:
        code: Stable machine-readable failure code.
        retryable: Whether a fresh attempt may be warranted.
        attempts: Total attempts consumed when this error was produced.
        status: Optional HTTP status from the final attempt.
        last_code: When ``code`` is ``retry_exhaustion``, the last attempt code.
    """

    def __init__(
        self,
        code: LLMErrorCode,
        *,
        retryable: bool | None = None,
        attempts: int = 1,
        status: int | None = None,
        last_code: LLMErrorCode | None = None,
    ) -> None:
        if not isinstance(code, LLMErrorCode):
            raise TypeError("code must be LLMErrorCode")
        self.code = code
        self.retryable = (
            default_retryable(code) if retryable is None else bool(retryable)
        )
        self.attempts = _require_attempts(attempts)
        self.status = _require_status(status)
        if last_code is not None and not isinstance(last_code, LLMErrorCode):
            raise TypeError("last_code must be LLMErrorCode")
        if last_code is not None and code is not LLMErrorCode.RETRY_EXHAUSTION:
            raise ValueError("last_code is only valid for retry_exhaustion")
        if code is LLMErrorCode.RETRY_EXHAUSTION and last_code is None:
            raise ValueError("retry_exhaustion requires last_code")
        self.last_code = last_code
        super().__init__(code.value)
        _detach(self)

    def log_fields(self) -> dict[str, object]:
        """Allowlisted projection suitable for metadata-only logging."""
        fields: dict[str, object] = {
            "code": self.code.value,
            "retryable": self.retryable,
            "attempts": self.attempts,
        }
        if self.status is not None:
            fields["status"] = self.status
        if self.last_code is not None:
            fields["last_code"] = self.last_code.value
        return fields

    def __repr__(self) -> str:
        parts = [
            f"code={self.code.value!r}",
            f"retryable={self.retryable}",
            f"attempts={self.attempts}",
        ]
        if self.status is not None:
            parts.append(f"status={self.status}")
        if self.last_code is not None:
            parts.append(f"last_code={self.last_code.value!r}")
        return f"LLMError({', '.join(parts)})"

    def __str__(self) -> str:
        return self.code.value


def retry_exhausted(last: LLMError) -> LLMError:
    """Build a terminal exhaustion error from the last safe attempt error."""
    if type(last) is not LLMError:
        raise TypeError("last must be LLMError")
    if last.code is LLMErrorCode.RETRY_EXHAUSTION:
        raise ValueError("cannot exhaust an exhaustion error")
    return LLMError(
        LLMErrorCode.RETRY_EXHAUSTION,
        retryable=False,
        attempts=last.attempts,
        status=last.status,
        last_code=last.code,
    )


def error_from_validation_failure(*, attempts: int = 1) -> LLMError:
    """Map a Pydantic validation failure without retaining details or causes."""
    return LLMError(
        LLMErrorCode.OUTPUT_SCHEMA,
        retryable=default_retryable(LLMErrorCode.OUTPUT_SCHEMA),
        attempts=attempts,
    )


def error_from_http_status(status: int, *, attempts: int = 1) -> LLMError:
    """Map an HTTP status to a safe error without retaining bodies or URLs."""
    code_status = _require_status(status)
    assert code_status is not None
    if code_status in _AUTH_HTTP_STATUSES:
        return LLMError(
            LLMErrorCode.AUTHENTICATION,
            retryable=False,
            attempts=attempts,
            status=code_status,
        )
    if code_status == 429:
        return LLMError(
            LLMErrorCode.RATE_LIMIT,
            retryable=True,
            attempts=attempts,
            status=code_status,
        )
    if code_status == 408:
        return LLMError(
            LLMErrorCode.TIMEOUT,
            retryable=True,
            attempts=attempts,
            status=code_status,
        )
    if code_status in _RETRYABLE_HTTP_STATUSES:
        return LLMError(
            LLMErrorCode.UPSTREAM,
            retryable=True,
            attempts=attempts,
            status=code_status,
        )
    if 400 <= code_status < 500:
        return LLMError(
            LLMErrorCode.PROVIDER_PROTOCOL,
            retryable=False,
            attempts=attempts,
            status=code_status,
        )
    if 500 <= code_status < 600:
        return LLMError(
            LLMErrorCode.UPSTREAM,
            retryable=False,
            attempts=attempts,
            status=code_status,
        )
    return LLMError(
        LLMErrorCode.PROVIDER_PROTOCOL,
        retryable=False,
        attempts=attempts,
        status=code_status,
    )


def _exception_class_names(exc: BaseException) -> set[str]:
    names: set[str] = set()
    for cls in type(exc).mro():
        names.add(cls.__name__)
    return names


def error_from_httpx(exc: BaseException, *, attempts: int = 1) -> LLMError:
    """Convert an httpx-like failure without retaining URL, body, or text.

    Accepts ``httpx`` exceptions when available and otherwise classifies by
    duck-typed attributes / class names. Never chains ``exc`` as cause.
    """
    if not isinstance(exc, BaseException):
        raise TypeError("exc must be a BaseException")

    names = _exception_class_names(exc)
    status = _status_from_exception(exc)

    if status is not None:
        return error_from_http_status(status, attempts=attempts)

    if "TimeoutException" in names or "TimeoutError" in names:
        return LLMError(LLMErrorCode.TIMEOUT, attempts=attempts)

    if {
        "ConnectError",
        "ConnectTimeout",
        "NetworkError",
        "ProxyError",
    } & names:
        return LLMError(LLMErrorCode.CONNECTION, attempts=attempts)

    if "HTTPStatusError" in names:
        # Status missing or non-integer: treat as protocol failure.
        return LLMError(
            LLMErrorCode.PROVIDER_PROTOCOL,
            retryable=False,
            attempts=attempts,
        )

    if "RequestError" in names or "TransportError" in names:
        return LLMError(LLMErrorCode.CONNECTION, attempts=attempts)

    return LLMError(
        LLMErrorCode.PROVIDER_PROTOCOL,
        retryable=False,
        attempts=attempts,
    )


def _status_from_exception(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    status = getattr(response, "status_code", None)
    if isinstance(status, bool) or not isinstance(status, int):
        return None
    if status < 100 or status > 599:
        return None
    return status
