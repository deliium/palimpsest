"""Process-wide LLM concurrency gate."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import Field

from llm.factory import (
    ConcurrencyLimitedLLMProvider,
    DeterministicFakeLLMProvider,
    wrap_llm_concurrency,
)
from llm.models import (
    FinishReason,
    LLMMessage,
    LLMRequest,
    LLMRequestContext,
    LLMResult,
    LLMResultMetadata,
    MessageRole,
    StructuredOutput,
)


class _Out(StructuredOutput):
    value: int = Field(default=1)


@pytest.mark.asyncio
async def test_wrap_llm_concurrency_serializes_under_max_one() -> None:
    inner = DeterministicFakeLLMProvider()
    wrapped = wrap_llm_concurrency(inner, max_concurrency=1)
    assert isinstance(wrapped, ConcurrencyLimitedLLMProvider)

    peaks: list[int] = []

    async def _hold() -> None:
        async with wrapped._semaphore:
            wrapped._in_flight += 1
            peaks.append(wrapped._in_flight)
            await asyncio.sleep(0.02)
            wrapped._in_flight -= 1

    await asyncio.gather(_hold(), _hold(), _hold())
    assert max(peaks) == 1


@pytest.mark.asyncio
async def test_concurrency_wrapper_forwards_generate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Stub:
        provider_name = "stub"

        async def generate(self, request: LLMRequest[_Out]) -> LLMResult[_Out]:
            del request
            return LLMResult(
                output=_Out(),
                metadata=LLMResultMetadata(
                    provider_name="stub",
                    model_name="stub-v1",
                    finish_reason=FinishReason.STOP,
                ),
            )

    provider = wrap_llm_concurrency(_Stub(), max_concurrency=2)
    with caplog.at_level("DEBUG", logger="llm.factory"):
        result = await provider.generate(  # type: ignore[attr-defined]
            LLMRequest.create(
                messages=(
                    LLMMessage(role=MessageRole.SYSTEM, content="Rules."),
                    LLMMessage(role=MessageRole.USER, content="Decide."),
                ),
                response_model=_Out,
                context=LLMRequestContext(
                    run_id="run-1",
                    agent_id="agent-1",
                    tick=0,
                    llm_request_id="req-1",
                    component="test",
                ),
            )
        )
    assert result.output.value == 1
    assert "llm.concurrency" in caplog.text
