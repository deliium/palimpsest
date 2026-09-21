"""Safe LLM error surfaces: codes, projections, and conversion hygiene."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel, ValidationError

from llm.errors import (
    LLMError,
    LLMErrorCode,
    default_retryable,
    error_from_http_status,
    error_from_httpx,
    error_from_validation_failure,
    retry_exhausted,
)


def test_public_error_exposes_only_safe_fields() -> None:
    err = LLMError(LLMErrorCode.TIMEOUT, attempts=2, status=408)
    assert err.code is LLMErrorCode.TIMEOUT
    assert err.retryable is True
    assert err.attempts == 2
    assert err.status == 408
    assert err.last_code is None
    assert str(err) == "timeout"
    assert "timeout" in repr(err)
    assert err.__cause__ is None
    assert err.__context__ is None


def test_log_fields_are_allowlisted() -> None:
    err = LLMError(LLMErrorCode.RATE_LIMIT, attempts=3, status=429)
    assert err.log_fields() == {
        "code": "rate_limit",
        "retryable": True,
        "attempts": 3,
        "status": 429,
    }


def test_default_retryability_matrix() -> None:
    assert default_retryable(LLMErrorCode.CONNECTION) is True
    assert default_retryable(LLMErrorCode.TIMEOUT) is True
    assert default_retryable(LLMErrorCode.RATE_LIMIT) is True
    assert default_retryable(LLMErrorCode.UPSTREAM) is True
    assert default_retryable(LLMErrorCode.OUTPUT_FORMAT) is True
    assert default_retryable(LLMErrorCode.OUTPUT_SCHEMA) is True
    assert default_retryable(LLMErrorCode.CONFIGURATION) is False
    assert default_retryable(LLMErrorCode.AUTHENTICATION) is False
    assert default_retryable(LLMErrorCode.PROVIDER_PROTOCOL) is False
    assert default_retryable(LLMErrorCode.REFUSAL) is False
    assert default_retryable(LLMErrorCode.INCOMPLETE) is False
    assert default_retryable(LLMErrorCode.CLOSED) is False
    assert default_retryable(LLMErrorCode.RETRY_EXHAUSTION) is False


def test_error_from_validation_failure_drops_pydantic_details() -> None:
    class _Model(BaseModel):
        kind: str

    with pytest.raises(ValidationError) as captured:
        _Model.model_validate({"kind": 1})
    secret = "hunter2-schema-input"
    raw = str(captured.value)
    assert "kind" in raw

    err = error_from_validation_failure(attempts=2)
    assert err.code is LLMErrorCode.OUTPUT_SCHEMA
    assert err.attempts == 2
    assert err.__cause__ is None
    assert err.__context__ is None
    assert secret not in repr(err)
    assert secret not in str(err)
    assert "kind" not in repr(err)
    assert "ValidationError" not in repr(err)
    assert err.log_fields() == {
        "code": "output_schema",
        "retryable": True,
        "attempts": 2,
    }


def test_error_from_http_status_classifies_safely() -> None:
    assert error_from_http_status(401).code is LLMErrorCode.AUTHENTICATION
    assert error_from_http_status(401).retryable is False
    assert error_from_http_status(429).code is LLMErrorCode.RATE_LIMIT
    assert error_from_http_status(408).code is LLMErrorCode.TIMEOUT
    assert error_from_http_status(503).code is LLMErrorCode.UPSTREAM
    assert error_from_http_status(503).retryable is True
    assert error_from_http_status(500).retryable is True
    assert error_from_http_status(501).retryable is False
    assert error_from_http_status(400).code is LLMErrorCode.PROVIDER_PROTOCOL
    assert error_from_http_status(400).retryable is False


def test_error_from_httpx_timeout_and_connection() -> None:
    timeout = error_from_httpx(httpx.ReadTimeout("secret-timeout"), attempts=1)
    assert timeout.code is LLMErrorCode.TIMEOUT
    assert timeout.retryable is True
    assert "secret-timeout" not in repr(timeout)
    assert "secret-timeout" not in str(timeout)
    assert timeout.__cause__ is None

    connect = error_from_httpx(
        httpx.ConnectError("https://evil.example/v1/chat?key=sekrit"),
        attempts=2,
    )
    assert connect.code is LLMErrorCode.CONNECTION
    assert connect.attempts == 2
    assert "evil.example" not in repr(connect)
    assert "sekrit" not in repr(connect)
    assert "evil.example" not in str(connect)


def test_error_from_httpx_status_without_body_or_url() -> None:
    request = httpx.Request("POST", "https://evil.example/v1/chat/completions")
    response = httpx.Response(
        429,
        request=request,
        text='{"error":{"message":"quota exceeded for sk-live-secret"}}',
    )
    exc = httpx.HTTPStatusError(
        "Client error '429' for url 'https://evil.example/v1/chat/completions'",
        request=request,
        response=response,
    )
    err = error_from_httpx(exc, attempts=4)
    assert err.code is LLMErrorCode.RATE_LIMIT
    assert err.status == 429
    assert err.attempts == 4
    text = repr(err) + str(err) + str(err.log_fields())
    assert "evil.example" not in text
    assert "sk-live-secret" not in text
    assert "quota" not in text
    assert err.__cause__ is None
    assert err.__context__ is None


def test_error_from_httpx_duck_typed_without_retaining_payload() -> None:
    class _FakeResponse:
        status_code = 503
        text = "upstream body with token=super-secret"

    class _FakeStatusError(Exception):
        def __init__(self) -> None:
            super().__init__("https://leak.example with token=super-secret")
            self.response = _FakeResponse()

    err = error_from_httpx(_FakeStatusError(), attempts=1)
    assert err.code is LLMErrorCode.UPSTREAM
    assert err.status == 503
    assert "super-secret" not in repr(err)
    assert "leak.example" not in repr(err)


def test_retry_exhausted_exposes_last_safe_code_and_status() -> None:
    last = LLMError(LLMErrorCode.TIMEOUT, attempts=3, status=408)
    exhausted = retry_exhausted(last)
    assert exhausted.code is LLMErrorCode.RETRY_EXHAUSTION
    assert exhausted.retryable is False
    assert exhausted.attempts == 3
    assert exhausted.status == 408
    assert exhausted.last_code is LLMErrorCode.TIMEOUT
    assert exhausted.log_fields() == {
        "code": "retry_exhaustion",
        "retryable": False,
        "attempts": 3,
        "status": 408,
        "last_code": "timeout",
    }
    assert exhausted.__cause__ is None


def test_raising_from_none_does_not_leak_cause_chain() -> None:
    secret = "provider-body-sk-abc"

    def _boom() -> None:
        try:
            raise RuntimeError(secret)
        except RuntimeError:
            raise LLMError(LLMErrorCode.PROVIDER_PROTOCOL, retryable=False) from None

    with pytest.raises(LLMError) as captured:
        _boom()
    err = captured.value
    assert err.__cause__ is None
    assert secret not in repr(err)
    assert secret not in str(err)


def test_invalid_construction_rejects_unsafe_shapes() -> None:
    with pytest.raises(ValueError, match="attempts"):
        LLMError(LLMErrorCode.TIMEOUT, attempts=0)
    with pytest.raises(ValueError, match="status"):
        LLMError(LLMErrorCode.TIMEOUT, status=99)
    with pytest.raises(ValueError, match="last_code"):
        LLMError(LLMErrorCode.TIMEOUT, last_code=LLMErrorCode.CONNECTION)
    with pytest.raises(ValueError, match="last_code"):
        LLMError(LLMErrorCode.RETRY_EXHAUSTION)


def test_namespace_status_helper_path_ignored_for_non_exceptions() -> None:
    # Ensure helpers stay strict about exception inputs.
    with pytest.raises(TypeError):
        error_from_httpx(SimpleNamespace(response=SimpleNamespace(status_code=500)))  # type: ignore[arg-type]
