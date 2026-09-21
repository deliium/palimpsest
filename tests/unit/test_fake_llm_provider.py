"""Deterministic FakeLLMProvider and FakeClock behavior."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator

import pytest

from llm.errors import LLMError, LLMErrorCode
from llm.models import (
    FinishReason,
    LLMMessage,
    LLMRequest,
    LLMRequestContext,
    LLMRequestOptions,
    LLMResult,
    LLMResultMetadata,
    MessageRole,
    PromptReference,
    StructuredOutput,
    TokenUsage,
)
from tests.fakes import (
    FakeCallRecord,
    FakeClock,
    FakeLLMFailureCode,
    FakeLLMProvider,
    FakeLLMProviderError,
    ScriptedFailure,
    ScriptedSuccess,
)

pytestmark = pytest.mark.unit

_DIGEST = "a" * 64


class _Decision(StructuredOutput):
    kind: str


class _Other(StructuredOutput):
    value: int


def _context(
    *,
    llm_request_id: str = "req-1",
    run_id: str = "run-1",
    agent_id: str = "agent-1",
    tick: int = 0,
) -> LLMRequestContext:
    return LLMRequestContext(
        run_id=run_id,
        agent_id=agent_id,
        tick=tick,
        llm_request_id=llm_request_id,
    )


def _request(
    *,
    llm_request_id: str = "req-1",
    content: str = "secret-prompt-payload",
) -> LLMRequest[_Decision]:
    return LLMRequest.create(
        messages=(
            LLMMessage(role=MessageRole.SYSTEM, content="Rules."),
            LLMMessage(role=MessageRole.USER, content=content),
        ),
        response_model=_Decision,
        context=_context(llm_request_id=llm_request_id),
        prompt=PromptReference(name="structured", version="v1", digest=_DIGEST),
        options=LLMRequestOptions(temperature=0.0),
    )


@pytest.fixture
def caplog_fake(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    with caplog.at_level(logging.DEBUG, logger="tests.fakes.llm"):
        yield caplog


async def test_fake_clock_records_exact_delays() -> None:
    clock = FakeClock(start=2.0)
    await clock.sleep(1.5)
    await clock.sleep(0.25)
    assert clock.monotonic() == 3.75
    first = clock.sleeps
    second = clock.sleeps
    assert first == (1.5, 0.25)
    assert second == (1.5, 0.25)
    assert first is not second


async def test_fake_clock_sleep_propagates_cancellation() -> None:
    clock = FakeClock()
    gate = asyncio.Event()

    async def sleeper() -> None:
        gate.set()
        await clock.sleep(5.0)

    task = asyncio.create_task(sleeper())
    await gate.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert clock.sleeps == (5.0,)
    assert clock.monotonic() == 0.0


async def test_scripted_success_returns_copied_output_and_metadata() -> None:
    provider = FakeLLMProvider()
    usage = TokenUsage(input_tokens=1, output_tokens=2, total_tokens=3)
    metadata = LLMResultMetadata(
        provider_name="fake",
        model_name="scripted",
        finish_reason=FinishReason.STOP,
        usage=usage,
        upstream_request_id="up-1",
        attempts=1,
    )
    original = _Decision(kind="ok")
    provider.script(
        llm_request_id="req-1",
        ordinal=1,
        outcome=ScriptedSuccess(output=original, metadata=metadata),
    )

    result = await provider.generate(_request())
    assert type(result.output) is _Decision
    assert result.output.kind == "ok"
    assert result.output is not original
    assert result.metadata.usage is not None
    assert result.metadata.usage is not usage
    assert result.metadata.usage.total_tokens == 3

    calls = provider.calls()
    assert len(calls) == 1
    assert calls[0].invocation_ordinal == 1
    assert calls[0].outcome == "success"
    assert calls[0].response_model == "_Decision"
    assert "secret-prompt-payload" not in repr(calls[0])
    assert "ok" not in repr(calls[0])


async def test_enqueue_assigns_consecutive_ordinals() -> None:
    provider = FakeLLMProvider()
    provider.enqueue(
        "req-1",
        ScriptedSuccess(output=_Decision(kind="a")),
        ScriptedSuccess(output=_Decision(kind="b")),
    )
    first = await provider.generate(_request())
    second = await provider.generate(_request())
    assert first.output.kind == "a"
    assert second.output.kind == "b"
    assert [c.invocation_ordinal for c in provider.calls()] == [1, 2]


async def test_scripted_failure_raises_copied_llm_error() -> None:
    provider = FakeLLMProvider()
    error = LLMError(LLMErrorCode.RATE_LIMIT, attempts=2, status=429)
    provider.enqueue("req-1", ScriptedFailure(error=error))

    with pytest.raises(LLMError) as exc_info:
        await provider.generate(_request())
    raised = exc_info.value
    assert raised is not error
    assert raised.code is LLMErrorCode.RATE_LIMIT
    assert raised.attempts == 2
    assert raised.status == 429
    assert provider.calls()[0].outcome == "failure"
    assert provider.calls()[0].error_code == "rate_limit"


async def test_unexpected_request_id_logs_safe_metadata(
    caplog_fake: pytest.LogCaptureFixture,
) -> None:
    provider = FakeLLMProvider()
    with pytest.raises(FakeLLMProviderError) as exc_info:
        await provider.generate(_request(llm_request_id="unknown-id"))
    err = exc_info.value
    assert err.code is FakeLLMFailureCode.UNEXPECTED_REQUEST_ID
    assert err.llm_request_id == "unknown-id"
    assert err.response_model == "_Decision"
    messages = " ".join(r.getMessage() for r in caplog_fake.records)
    assert "unexpected_request_id" in messages
    assert "unknown-id" in messages
    assert "_Decision" in messages
    assert "secret-prompt-payload" not in messages


async def test_exhausted_script_rejects_extra_call() -> None:
    provider = FakeLLMProvider()
    provider.enqueue("req-1", ScriptedSuccess(output=_Decision(kind="once")))
    await provider.generate(_request())
    with pytest.raises(FakeLLMProviderError) as exc_info:
        await provider.generate(_request())
    assert exc_info.value.code is FakeLLMFailureCode.EXHAUSTED_SCRIPT
    assert exc_info.value.ordinal == 2


async def test_response_model_mismatch_rejects_incompatible_output(
    caplog_fake: pytest.LogCaptureFixture,
) -> None:
    provider = FakeLLMProvider()
    provider.enqueue("req-1", ScriptedSuccess(output=_Other(value=7)))
    with pytest.raises(FakeLLMProviderError) as exc_info:
        await provider.generate(_request())
    assert exc_info.value.code is FakeLLMFailureCode.RESPONSE_MODEL_MISMATCH
    messages = " ".join(r.getMessage() for r in caplog_fake.records)
    assert "response_model_mismatch" in messages
    assert "secret-prompt-payload" not in messages
    assert "7" not in messages


async def test_duplicate_ordinal_rejected_at_script_time() -> None:
    provider = FakeLLMProvider()
    provider.script(
        llm_request_id="req-1",
        ordinal=1,
        outcome=ScriptedSuccess(output=_Decision(kind="a")),
    )
    with pytest.raises(FakeLLMProviderError) as exc_info:
        provider.script(
            llm_request_id="req-1",
            ordinal=1,
            outcome=ScriptedSuccess(output=_Decision(kind="b")),
        )
    assert exc_info.value.code is FakeLLMFailureCode.DUPLICATE_ORDINAL


async def test_duplicate_concurrent_active_id_rejected() -> None:
    provider = FakeLLMProvider()
    provider.enqueue(
        "req-1",
        ScriptedSuccess(output=_Decision(kind="slow"), delay_seconds=1.0),
        ScriptedSuccess(output=_Decision(kind="unused")),
    )
    started = asyncio.Event()
    original = provider.clock.sleep

    async def marked(seconds: float) -> None:
        started.set()
        await original(seconds)

    provider.clock.sleep = marked  # type: ignore[method-assign]

    task = asyncio.create_task(provider.generate(_request()))
    await started.wait()
    with pytest.raises(FakeLLMProviderError) as exc_info:
        await provider.generate(_request())
    assert exc_info.value.code is FakeLLMFailureCode.DUPLICATE_ACTIVE_ID
    result = await task
    assert isinstance(result, LLMResult)
    assert result.output.kind == "slow"


async def test_concurrent_distinct_ids_are_isolated() -> None:
    clock = FakeClock()
    provider = FakeLLMProvider(clock=clock)
    provider.enqueue(
        "req-a",
        ScriptedSuccess(output=_Decision(kind="a"), delay_seconds=1.0),
    )
    provider.enqueue(
        "req-b",
        ScriptedSuccess(output=_Decision(kind="b"), delay_seconds=1.0),
    )

    results = await asyncio.gather(
        provider.generate(_request(llm_request_id="req-a")),
        provider.generate(_request(llm_request_id="req-b")),
    )
    kinds = sorted(result.output.kind for result in results)
    assert kinds == ["a", "b"]
    assert clock.sleeps == (1.0, 1.0)
    assert {c.llm_request_id for c in provider.calls()} == {"req-a", "req-b"}
    assert provider.remaining("req-a") == {}
    assert provider.remaining("req-b") == {}


async def test_scripted_delay_uses_fake_clock() -> None:
    clock = FakeClock()
    provider = FakeLLMProvider(clock=clock)
    provider.enqueue(
        "req-1",
        ScriptedSuccess(output=_Decision(kind="ok"), delay_seconds=2.5),
    )
    result = await provider.generate(_request())
    assert result.output.kind == "ok"
    assert clock.sleeps == (2.5,)
    assert clock.monotonic() == 2.5
    call = provider.calls()[0]
    assert call.started_at == 0.0
    assert call.finished_at == 2.5


async def test_cancellation_during_delay_propagates_and_clears_active() -> None:
    provider = FakeLLMProvider()
    provider.enqueue(
        "req-1",
        ScriptedSuccess(output=_Decision(kind="x"), delay_seconds=3.0),
    )
    started = asyncio.Event()
    original = provider.clock.sleep

    async def marked(seconds: float) -> None:
        started.set()
        await original(seconds)

    provider.clock.sleep = marked  # type: ignore[method-assign]
    task = asyncio.create_task(provider.generate(_request()))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert provider.active_ids() == frozenset()
    assert provider.calls()[0].outcome == "cancelled"


async def test_calls_returns_defensive_copies() -> None:
    provider = FakeLLMProvider()
    provider.enqueue("req-1", ScriptedSuccess(output=_Decision(kind="ok")))
    await provider.generate(_request())
    first = provider.calls()
    second = provider.calls()
    assert first == second
    assert first is not second
    assert first[0] is not second[0]
    assert isinstance(first[0], FakeCallRecord)


async def test_mutated_script_inputs_do_not_affect_provider() -> None:
    provider = FakeLLMProvider()
    error = LLMError(LLMErrorCode.TIMEOUT, attempts=1)
    outcome = ScriptedFailure(error=error, delay_seconds=0.0)
    provider.enqueue("req-1", outcome)
    # Mutating the original error object must not change the scripted copy.
    error.attempts = 99
    with pytest.raises(LLMError) as exc_info:
        await provider.generate(_request())
    assert exc_info.value.attempts == 1


async def test_default_metadata_when_omitted() -> None:
    provider = FakeLLMProvider()
    provider.enqueue("req-1", ScriptedSuccess(output=_Decision(kind="ok")))
    result = await provider.generate(_request())
    assert result.metadata.provider_name == "fake"
    assert result.metadata.model_name == "scripted"
    assert result.metadata.finish_reason is FinishReason.STOP


async def test_no_payload_logs_on_success(
    caplog_fake: pytest.LogCaptureFixture,
) -> None:
    provider = FakeLLMProvider()
    provider.enqueue(
        "req-1",
        ScriptedSuccess(output=_Decision(kind="secret-output")),
    )
    await provider.generate(_request(content="secret-prompt-payload"))
    assert caplog_fake.records == []
