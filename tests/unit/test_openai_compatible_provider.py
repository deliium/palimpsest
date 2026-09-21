"""OpenAI-compatible provider transport, retries, lifecycle, and logs."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from llm.errors import LLMError, LLMErrorCode
from llm.models import (
    LLMMessage,
    LLMRequest,
    LLMRequestContext,
    LLMRequestOptions,
    MessageRole,
    ProviderDefaults,
    RetryPolicy,
    StructuredOutput,
    StructuredOutputMode,
)
from llm.providers.openai_compatible import OpenAICompatibleProvider

pytestmark = pytest.mark.unit


class _Decision(StructuredOutput):
    kind: str


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _context(
    *,
    run_id: str = "run-secret",
    agent_id: str = "agent-secret",
    tick: int = 42,
    llm_request_id: str = "req-corr-1",
) -> LLMRequestContext:
    return LLMRequestContext(
        run_id=run_id,
        agent_id=agent_id,
        tick=tick,
        llm_request_id=llm_request_id,
    )


def _request(**kwargs: Any) -> LLMRequest[_Decision]:
    context = kwargs.pop("context", None) or _context()
    return LLMRequest.create(
        messages=(
            LLMMessage(role=MessageRole.SYSTEM, content="Rules."),
            LLMMessage(role=MessageRole.USER, content="Decide."),
        ),
        response_model=_Decision,
        context=context,
        **kwargs,
    )


def _success_json(content: str = '{"kind":"ok"}') -> bytes:
    body = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 3,
            "completion_tokens": 5,
            "total_tokens": 8,
        },
    }
    return json.dumps(body).encode("utf-8")


def _provider(
    *,
    handler: Any,
    clock: _Clock | None = None,
    base_url: str = "http://llm.test/v1",
    api_key: str | None = "sk-test",
    send_correlation_header: bool = False,
    retry: RetryPolicy | None = None,
    mode: StructuredOutputMode = StructuredOutputMode.JSON_SCHEMA,
    defaults: ProviderDefaults | None = None,
    provider_name: str = "openai_compatible",
    max_request_bytes: int = 1_048_576,
    max_response_bytes: int = 1_048_576,
) -> tuple[OpenAICompatibleProvider, _Clock, httpx.AsyncClient]:
    clock = clock or _Clock()
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        transport=transport,
        base_url=base_url if base_url.endswith("/") else f"{base_url}/",
        follow_redirects=False,
        trust_env=False,
    )
    provider = OpenAICompatibleProvider(
        base_url=base_url,
        model="gpt-test",
        mode=mode,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        api_key=api_key,
        client=client,
        provider_name=provider_name,
        defaults=defaults,
        send_correlation_header=send_correlation_header,
        retry=retry or RetryPolicy(max_attempts=3, initial_backoff_seconds=0.5),
        max_request_bytes=max_request_bytes,
        max_response_bytes=max_response_bytes,
    )
    return provider, clock, client


@pytest.fixture
def caplog_llm(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    with caplog.at_level(logging.DEBUG, logger="llm.openai_compatible"):
        yield caplog


async def test_generate_success_path_and_log_matrix(
    caplog_llm: pytest.LogCaptureFixture,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=_success_json())

    provider, _clock, client = _provider(handler=handler)
    try:
        result = await provider.generate(_request())
    finally:
        await client.aclose()

    assert result.output.kind == "ok"
    assert result.metadata.attempts == 1
    assert result.metadata.usage is not None
    assert result.metadata.usage.input_tokens == 3
    assert result.metadata.usage.output_tokens == 5
    assert len(seen) == 1
    assert seen[0].url.path == "/v1/chat/completions"

    events = [(record.levelno, record.getMessage()) for record in caplog_llm.records]
    assert any(
        level == logging.DEBUG and message.startswith("generate_started ")
        for level, message in events
    )
    assert any(
        level == logging.DEBUG and message.startswith("attempt_started ")
        for level, message in events
    )
    assert any(
        level == logging.INFO and message.startswith("generate_succeeded ")
        for level, message in events
    )
    success = next(
        message
        for level, message in events
        if level == logging.INFO and message.startswith("generate_succeeded ")
    )
    assert "input_tokens=3" in success
    assert "output_tokens=5" in success
    assert " token=" not in f" {success} "
    assert "agent-secret" not in success
    assert "run-secret" not in success


async def test_preserves_v1_prefix_and_trailing_slash_normalization() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, content=_success_json())

    provider, _clock, client = _provider(
        handler=handler,
        base_url="http://llm.test/v1",
    )
    try:
        await provider.generate(_request())
    finally:
        await client.aclose()
    assert paths == ["/v1/chat/completions"]


async def test_redirect_not_followed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"Location": "http://evil.test/leak"},
            content=b"",
        )

    provider, _clock, client = _provider(
        handler=handler,
        retry=RetryPolicy(max_attempts=1),
    )
    try:
        with pytest.raises(LLMError) as captured:
            await provider.generate(_request())
    finally:
        await client.aclose()
    assert captured.value.code is LLMErrorCode.PROVIDER_PROTOCOL
    assert captured.value.status == 302


async def test_retry_backoff_exhaustion_and_warning_logs(
    caplog_llm: pytest.LogCaptureFixture,
) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, content=b'{"error":"busy"}')

    clock = _Clock()
    provider, clock, client = _provider(
        handler=handler,
        clock=clock,
        retry=RetryPolicy(
            max_attempts=3,
            initial_backoff_seconds=0.5,
            backoff_multiplier=2.0,
            max_backoff_seconds=30.0,
        ),
    )
    try:
        with pytest.raises(LLMError) as captured:
            await provider.generate(_request())
    finally:
        await client.aclose()

    assert captured.value.code is LLMErrorCode.RETRY_EXHAUSTION
    assert captured.value.last_code is LLMErrorCode.UPSTREAM
    assert captured.value.attempts == 3
    assert calls["n"] == 3
    assert clock.sleeps == [0.5, 1.0]

    messages = [record.getMessage() for record in caplog_llm.records]
    assert any(message.startswith("attempt_failed_retryable ") for message in messages)
    assert any(message.startswith("retry_scheduled ") for message in messages)
    assert any(
        record.levelno == logging.ERROR
        and record.getMessage().startswith("generate_failed ")
        for record in caplog_llm.records
    )


async def test_retry_after_delta_seconds_preferred() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "2"},
                content=b"{}",
            )
        return httpx.Response(200, content=_success_json())

    clock = _Clock()
    provider, clock, client = _provider(
        handler=handler,
        clock=clock,
        retry=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.5),
    )
    try:
        result = await provider.generate(_request())
    finally:
        await client.aclose()
    assert result.output.kind == "ok"
    assert clock.sleeps == [2.0]


async def test_cancellation_during_sleep_propagates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"{}")

    class _CancelClock(_Clock):
        async def sleep(self, seconds: float) -> None:
            raise asyncio.CancelledError()

    provider, _clock, client = _provider(
        handler=handler,
        clock=_CancelClock(),
        retry=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.1),
    )
    try:
        with pytest.raises(asyncio.CancelledError):
            await provider.generate(_request())
    finally:
        await client.aclose()


async def test_owned_client_closed_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closes = {"count": 0}
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=_success_json())
    )

    class _TrackingClient(httpx.AsyncClient):
        async def aclose(self) -> None:
            closes["count"] += 1
            await super().aclose()

    def factory(**kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return _TrackingClient(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)

    clock = _Clock()
    provider = OpenAICompatibleProvider(
        base_url="http://llm.test/v1/",
        model="gpt-test",
        mode=StructuredOutputMode.JSON_SCHEMA,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        api_key=None,
        client=None,
        retry=RetryPolicy(max_attempts=1),
    )
    assert provider._client is None
    await provider.generate(_request())
    assert provider._client is not None
    await provider.close()
    await provider.close()
    assert closes["count"] == 1


async def test_injected_client_never_closed_by_provider() -> None:
    closes = {"count": 0}
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=_success_json())
    )

    class _TrackingClient(httpx.AsyncClient):
        async def aclose(self) -> None:
            closes["count"] += 1
            await super().aclose()

    client = _TrackingClient(
        transport=transport,
        base_url="http://llm.test/v1/",
        follow_redirects=False,
        trust_env=False,
    )
    clock = _Clock()
    provider = OpenAICompatibleProvider(
        base_url="http://llm.test/v1/",
        model="gpt-test",
        mode=StructuredOutputMode.JSON_SCHEMA,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        api_key=None,
        client=client,
        retry=RetryPolicy(max_attempts=1),
    )
    await provider.generate(_request())
    await provider.close()
    await provider.close()
    assert closes["count"] == 0
    await client.aclose()
    assert closes["count"] == 1


async def test_generate_after_close_fails_safely() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_success_json())

    provider, _clock, client = _provider(handler=handler)
    await provider.close()
    with pytest.raises(LLMError) as captured:
        await provider.generate(_request())
    assert captured.value.code is LLMErrorCode.CLOSED
    await client.aclose()


async def test_response_byte_limit_not_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 100)

    provider, _clock, client = _provider(
        handler=handler,
        max_response_bytes=32,
        retry=RetryPolicy(max_attempts=3),
    )
    try:
        with pytest.raises(LLMError) as captured:
            await provider.generate(_request())
    finally:
        await client.aclose()
    assert captured.value.code is LLMErrorCode.PROVIDER_PROTOCOL
    assert captured.value.retryable is False
    assert captured.value.attempts == 1


async def test_auth_header_only_when_configured() -> None:
    headers_seen: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        headers_seen.append(request.headers)
        return httpx.Response(200, content=_success_json())

    provider, _clock, client = _provider(handler=handler, api_key=None)
    try:
        await provider.generate(_request())
    finally:
        await client.aclose()
    assert "authorization" not in headers_seen[0]

    provider2, _clock2, client2 = _provider(handler=handler, api_key="sk-abc")
    try:
        await provider2.generate(_request())
    finally:
        await client2.aclose()
    assert headers_seen[1].get("Authorization") == "Bearer sk-abc"


async def test_non_retryable_auth_logs_error_once(
    caplog_llm: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, content=b"{}")

    provider, _clock, client = _provider(
        handler=handler,
        retry=RetryPolicy(max_attempts=5),
    )
    try:
        with pytest.raises(LLMError) as captured:
            await provider.generate(_request())
    finally:
        await client.aclose()
    assert captured.value.code is LLMErrorCode.AUTHENTICATION
    assert captured.value.attempts == 1
    assert (
        sum(
            1
            for record in caplog_llm.records
            if record.levelno == logging.ERROR
            and record.getMessage().startswith("generate_failed ")
        )
        == 1
    )
    assert not any(
        record.getMessage().startswith("attempt_failed_retryable ")
        for record in caplog_llm.records
    )


async def test_owned_client_sets_trust_env_false_and_no_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kwargs_seen: dict[str, Any] = {}
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=_success_json())
    )

    real = httpx.AsyncClient

    def factory(**kwargs: Any) -> httpx.AsyncClient:
        kwargs_seen.update(kwargs)
        kwargs["transport"] = transport
        return real(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    clock = _Clock()
    provider = OpenAICompatibleProvider(
        base_url="http://llm.test/v1",
        model="gpt-test",
        mode=StructuredOutputMode.JSON_SCHEMA,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        api_key=None,
        client=None,
        retry=RetryPolicy(max_attempts=1),
    )
    await provider.generate(_request())
    await provider.close()
    assert kwargs_seen.get("follow_redirects") is False
    assert kwargs_seen.get("trust_env") is False
    assert kwargs_seen.get("base_url") == "http://llm.test/v1/"


@pytest.mark.parametrize(
    ("base_url", "provider_name", "expected_host", "expected_port"),
    [
        ("http://127.0.0.1:11434/v1", "ollama", "127.0.0.1", 11434),
        ("http://127.0.0.1:8000/v1", "vllm", "127.0.0.1", 8000),
        ("http://[::1]:11434/v1", "ollama", "::1", 11434),
        ("http://localhost:8000/v1/", "vllm", "localhost", 8000),
    ],
)
async def test_local_ollama_vllm_ipv6_endpoint_profiles(
    base_url: str,
    provider_name: str,
    expected_host: str,
    expected_port: int,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=_success_json())

    provider, _clock, client = _provider(
        handler=handler,
        base_url=base_url,
        provider_name=provider_name,
        mode=StructuredOutputMode.JSON_OBJECT,
        api_key=None,
        retry=RetryPolicy(max_attempts=1),
    )
    try:
        result = await provider.generate(_request())
    finally:
        await client.aclose()

    assert result.metadata.provider_name == provider_name
    assert len(seen) == 1
    outbound = seen[0]
    assert outbound.url.path == "/v1/chat/completions"
    assert outbound.url.host == expected_host
    assert outbound.url.port == expected_port
    body = json.loads(outbound.content.decode("utf-8"))
    assert body["response_format"] == {"type": "json_object"}
    assert body["n"] == 1
    assert "run-secret" not in outbound.content.decode("utf-8")


async def test_option_precedence_temperature_zero_on_wire() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, content=_success_json())

    provider, _clock, client = _provider(
        handler=handler,
        defaults=ProviderDefaults(temperature=0.7, max_output_tokens=256),
        retry=RetryPolicy(max_attempts=1),
    )
    try:
        await provider.generate(_request(options=LLMRequestOptions(temperature=0.0)))
    finally:
        await client.aclose()

    assert bodies[0]["temperature"] == 0.0
    assert bodies[0]["max_tokens"] == 256


@pytest.mark.parametrize(
    ("status", "expected_code", "retryable", "attempts"),
    [
        (408, LLMErrorCode.RETRY_EXHAUSTION, False, 2),
        (429, LLMErrorCode.RETRY_EXHAUSTION, False, 2),
        (500, LLMErrorCode.RETRY_EXHAUSTION, False, 2),
        (502, LLMErrorCode.RETRY_EXHAUSTION, False, 2),
        (400, LLMErrorCode.PROVIDER_PROTOCOL, False, 1),
        (404, LLMErrorCode.PROVIDER_PROTOCOL, False, 1),
        (501, LLMErrorCode.UPSTREAM, False, 1),
    ],
)
async def test_retry_matrix_by_status(
    status: int,
    expected_code: LLMErrorCode,
    retryable: bool,
    attempts: int,
) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(status, content=b'{"error":"x"}')

    provider, clock, client = _provider(
        handler=handler,
        retry=RetryPolicy(max_attempts=2, initial_backoff_seconds=0.25),
    )
    try:
        with pytest.raises(LLMError) as captured:
            await provider.generate(_request())
    finally:
        await client.aclose()

    assert captured.value.code is expected_code
    assert captured.value.retryable is retryable
    assert captured.value.attempts == attempts
    assert calls["n"] == attempts
    if attempts > 1:
        assert clock.sleeps == [0.25]
        assert captured.value.last_code is not None
    assert "error" not in repr(captured.value)
    assert captured.value.__cause__ is None


async def test_connection_and_timeout_errors_retry_without_leaking_httpx() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("https://evil.example/v1?key=sekrit")
        if calls["n"] == 2:
            raise httpx.ReadTimeout("secret-timeout-url")
        return httpx.Response(200, content=_success_json())

    provider, clock, client = _provider(
        handler=handler,
        retry=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.1),
    )
    try:
        result = await provider.generate(_request())
    finally:
        await client.aclose()

    assert result.output.kind == "ok"
    assert result.metadata.attempts == 3
    assert calls["n"] == 3
    assert clock.sleeps == [0.1, 0.2]
    assert "evil.example" not in repr(result)
    assert "sekrit" not in repr(result)


async def test_schema_retry_then_success_and_format_not_retried_when_disabled(
    caplog_llm: pytest.LogCaptureFixture,
) -> None:
    schema_calls = {"n": 0}

    def schema_handler(request: httpx.Request) -> httpx.Response:
        schema_calls["n"] += 1
        if schema_calls["n"] == 1:
            return httpx.Response(200, content=_success_json('{"kind":1}'))
        return httpx.Response(200, content=_success_json('{"kind":"ok"}'))

    provider, clock, client = _provider(
        handler=schema_handler,
        retry=RetryPolicy(
            max_attempts=3,
            initial_backoff_seconds=0.5,
            retry_output_schema=True,
            retry_output_format=True,
        ),
    )
    try:
        result = await provider.generate(_request())
    finally:
        await client.aclose()
    assert result.output.kind == "ok"
    assert schema_calls["n"] == 2
    assert clock.sleeps == [0.5]
    assert any(
        record.levelno == logging.WARNING
        and "attempt_failed_retryable" in record.getMessage()
        and "output_schema" in record.getMessage()
        for record in caplog_llm.records
    )

    format_calls = {"n": 0}

    def format_handler(request: httpx.Request) -> httpx.Response:
        format_calls["n"] += 1
        return httpx.Response(200, content=_success_json("not-json"))

    provider2, _clock2, client2 = _provider(
        handler=format_handler,
        retry=RetryPolicy(
            max_attempts=3,
            retry_output_format=False,
            retry_output_schema=True,
        ),
    )
    try:
        with pytest.raises(LLMError) as captured:
            await provider2.generate(_request())
    finally:
        await client2.aclose()
    assert captured.value.code is LLMErrorCode.OUTPUT_FORMAT
    assert format_calls["n"] == 1
    assert "not-json" not in repr(captured.value)


async def test_cancellation_during_request_propagates() -> None:
    request_started = asyncio.Event()
    sleep_started = asyncio.Event()

    def handler(request: httpx.Request) -> httpx.Response:
        request_started.set()
        raise httpx.ConnectError("should-not-leak")

    class _HangClock(_Clock):
        async def sleep(self, seconds: float) -> None:
            sleep_started.set()
            await asyncio.Event().wait()

    provider, _clock, client = _provider(
        handler=handler,
        clock=_HangClock(),
        retry=RetryPolicy(max_attempts=3, initial_backoff_seconds=1.0),
    )
    task = asyncio.create_task(provider.generate(_request()))
    await request_started.wait()
    await sleep_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await client.aclose()


async def test_public_errors_and_logs_omit_sensitive_surfaces(
    caplog_llm: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("https://provider.example/v1/chat?api_key=sekrit")

    provider, _clock, client = _provider(
        handler=handler,
        api_key="sk-live-sekrit",
        base_url="http://127.0.0.1:11434/v1",
        retry=RetryPolicy(max_attempts=1),
    )
    try:
        with pytest.raises(LLMError) as captured:
            await provider.generate(
                _request(
                    context=_context(
                        run_id="run-leak",
                        agent_id="agent-leak",
                        tick=99,
                        llm_request_id="safe-corr",
                    )
                )
            )
    finally:
        await client.aclose()

    err = captured.value
    assert err.code is LLMErrorCode.RETRY_EXHAUSTION
    assert err.last_code is LLMErrorCode.CONNECTION
    assert err.__cause__ is None
    assert err.__context__ is None
    surfaces = " ".join(
        [
            repr(err),
            str(err),
            *(record.getMessage() for record in caplog_llm.records),
        ]
    )
    for forbidden in (
        "sekrit",
        "provider.example",
        "11434",
        "sk-live",
        "run-leak",
        "agent-leak",
        "Rules.",
        "Decide.",
        "ConnectError",
    ):
        assert forbidden not in surfaces
    assert "safe-corr" in surfaces
    assert any(
        record.levelno == logging.ERROR
        and record.getMessage().startswith("generate_failed ")
        for record in caplog_llm.records
    )


async def test_full_safe_event_level_matrix(
    caplog_llm: pytest.LogCaptureFixture,
) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, content=b"{}")
        return httpx.Response(200, content=_success_json())

    provider, _clock, client = _provider(
        handler=handler,
        retry=RetryPolicy(max_attempts=2, initial_backoff_seconds=0.1),
    )
    try:
        await provider.generate(_request(context=_context(llm_request_id="evt-1")))
    finally:
        await client.aclose()

    by_prefix: dict[str, list[tuple[int, str]]] = {}
    for record in caplog_llm.records:
        if record.name != "llm.openai_compatible":
            continue
        message = record.getMessage()
        prefix = message.split(" ", 1)[0]
        by_prefix.setdefault(prefix, []).append((record.levelno, message))

    assert by_prefix["generate_started"][0][0] == logging.DEBUG
    assert by_prefix["attempt_started"][0][0] == logging.DEBUG
    assert by_prefix["attempt_failed_retryable"][0][0] == logging.WARNING
    assert by_prefix["retry_scheduled"][0][0] == logging.DEBUG
    assert by_prefix["generate_succeeded"][0][0] == logging.INFO
    all_messages = [message for entries in by_prefix.values() for _, message in entries]
    assert all("evt-1" in message for message in all_messages)
    assert all(
        "run-secret" not in message and "agent-secret" not in message
        for message in all_messages
    )


async def test_concurrent_generates_preserve_distinct_payloads() -> None:
    bodies: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content.decode("utf-8"))
        return httpx.Response(200, content=_success_json())

    provider, _clock, client = _provider(
        handler=handler,
        retry=RetryPolicy(max_attempts=1),
    )
    try:
        await asyncio.gather(
            provider.generate(
                _request(
                    context=_context(llm_request_id="corr-a"),
                    options=LLMRequestOptions(temperature=0.0, seed=1),
                )
            ),
            provider.generate(
                _request(
                    context=_context(llm_request_id="corr-b"),
                    options=LLMRequestOptions(temperature=0.5, seed=2),
                )
            ),
        )
    finally:
        await client.aclose()

    assert len(bodies) == 2
    parsed = [json.loads(body) for body in bodies]
    seeds = sorted(item["seed"] for item in parsed)
    assert seeds == [1, 2]
    temps = sorted(item["temperature"] for item in parsed)
    assert temps == [0.0, 0.5]
