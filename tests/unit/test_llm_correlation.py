"""Correlation privacy: local run/agent/tick never leave the process."""

from __future__ import annotations

import json
import logging

import httpx
import pytest

from llm.models import (
    LLMMessage,
    LLMRequest,
    LLMRequestContext,
    MessageRole,
    RetryPolicy,
    StructuredOutput,
    StructuredOutputMode,
)
from llm.providers.openai_compatible import (
    CORRELATION_HEADER_NAME,
    OpenAICompatibleProvider,
)

pytestmark = pytest.mark.unit


class _Decision(StructuredOutput):
    kind: str


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds


def _success_json() -> bytes:
    body = {
        "id": "chatcmpl-1",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": '{"kind":"ok"}'},
                "finish_reason": "stop",
            }
        ],
    }
    return json.dumps(body).encode("utf-8")


async def test_correlation_header_off_by_default() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=_success_json())

    clock = _Clock()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://llm.test/v1/",
        follow_redirects=False,
        trust_env=False,
    )
    provider = OpenAICompatibleProvider(
        base_url="http://llm.test/v1/",
        model="m",
        mode=StructuredOutputMode.JSON_OBJECT,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        api_key="sk-test",
        client=client,
        send_correlation_header=False,
        retry=RetryPolicy(max_attempts=1),
    )
    request = LLMRequest.create(
        messages=(LLMMessage(role=MessageRole.USER, content="hi"),),
        response_model=_Decision,
        context=LLMRequestContext(
            run_id="run-local",
            agent_id="agent-local",
            tick=9,
            llm_request_id="corr-opaque-1",
        ),
    )
    try:
        await provider.generate(request)
    finally:
        await client.aclose()

    outbound = captured[0]
    header_blob = " ".join(
        f"{key}:{value}" for key, value in outbound.headers.multi_items()
    )
    body_text = outbound.content.decode("utf-8")
    assert CORRELATION_HEADER_NAME.lower() not in {
        key.lower() for key in outbound.headers
    }
    assert "run-local" not in header_blob
    assert "agent-local" not in header_blob
    assert "run-local" not in body_text
    assert "agent-local" not in body_text
    assert '"tick"' not in body_text
    assert "corr-opaque-1" not in body_text
    assert "corr-opaque-1" not in header_blob


async def test_correlation_header_sends_only_opaque_id_across_retries() -> None:
    captured: list[httpx.Request] = []
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, content=b"{}")
        return httpx.Response(200, content=_success_json())

    clock = _Clock()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://llm.test/v1/",
        follow_redirects=False,
        trust_env=False,
    )
    provider = OpenAICompatibleProvider(
        base_url="http://llm.test/v1/",
        model="m",
        mode=StructuredOutputMode.PROMPT_ONLY,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        api_key=None,
        client=client,
        send_correlation_header=True,
        retry=RetryPolicy(max_attempts=3, initial_backoff_seconds=0.1),
    )
    context = LLMRequestContext(
        run_id="run-keep-local",
        agent_id="agent-keep-local",
        tick=77,
        llm_request_id="stable-corr-id",
    )
    request = LLMRequest.create(
        messages=(LLMMessage(role=MessageRole.USER, content="hi"),),
        response_model=_Decision,
        context=context,
    )
    try:
        await provider.generate(request)
    finally:
        await client.aclose()

    assert len(captured) == 2
    for outbound in captured:
        assert outbound.headers.get(CORRELATION_HEADER_NAME) == "stable-corr-id"
        header_values = list(outbound.headers.values())
        assert "run-keep-local" not in header_values
        assert "agent-keep-local" not in header_values
        body_text = outbound.content.decode("utf-8")
        assert "run-keep-local" not in body_text
        assert "agent-keep-local" not in body_text
        assert '"tick"' not in body_text
        assert "x-request-id" not in {key.lower() for key in outbound.headers}

    # Local context object remains unchanged after retries.
    assert request.context.run_id == "run-keep-local"
    assert request.context.agent_id == "agent-keep-local"
    assert request.context.tick == 77
    assert request.context.llm_request_id == "stable-corr-id"


async def test_logs_never_include_local_run_agent_tick(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_success_json())

    clock = _Clock()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://llm.test/v1/",
        follow_redirects=False,
        trust_env=False,
    )
    provider = OpenAICompatibleProvider(
        base_url="http://llm.test/v1/",
        model="m",
        mode=StructuredOutputMode.JSON_SCHEMA,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        api_key="sk-secret-key",
        client=client,
        send_correlation_header=True,
        retry=RetryPolicy(max_attempts=1),
    )
    with caplog.at_level(logging.DEBUG, logger="llm.openai_compatible"):
        try:
            await provider.generate(
                LLMRequest.create(
                    messages=(
                        LLMMessage(
                            role=MessageRole.USER,
                            content="secret prompt",
                        ),
                    ),
                    response_model=_Decision,
                    context=LLMRequestContext(
                        run_id="run-must-not-log",
                        agent_id="agent-must-not-log",
                        tick=12345,
                        llm_request_id="log-safe-corr",
                    ),
                )
            )
        finally:
            await client.aclose()

    joined = "\n".join(record.getMessage() for record in caplog.records)
    assert "run-must-not-log" not in joined
    assert "agent-must-not-log" not in joined
    assert "12345" not in joined
    assert "sk-secret-key" not in joined
    assert "secret prompt" not in joined
    assert "http://llm.test" not in joined
    assert "log-safe-corr" in joined
