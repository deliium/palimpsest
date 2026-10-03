"""Schema/prompt drift must fail closed on replay and miss on cache."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm.errors import LLMError, LLMErrorCode
from llm.models import (
    FinishReason,
    LLMMessage,
    LLMRequest,
    LLMRequestContext,
    LLMResultMetadata,
    MessageRole,
    PromptReference,
    StructuredOutput,
    StructuredOutputMode,
)
from llm.recording.provider import RecordingLLMProvider, RecordingMode
from llm.recording.store import FilesystemRecordingStore, LookupMode
from tests.fakes.llm import FakeClock, FakeLLMProvider, ScriptedSuccess


class _Out(StructuredOutput):
    kind: str


class _OutV2(StructuredOutput):
    kind: str
    note: str = "x"


def _success() -> ScriptedSuccess:
    return ScriptedSuccess(
        output=_Out(kind="wait"),
        metadata=LLMResultMetadata(
            provider_name="fake",
            model_name="scripted",
            finish_reason=FinishReason.STOP,
        ),
    )


def _request(
    *,
    model: type[StructuredOutput] = _Out,
    prompt: PromptReference | None = None,
    llm_request_id: str = "req-1",
) -> LLMRequest[StructuredOutput]:
    return LLMRequest.create(
        messages=(LLMMessage(role=MessageRole.USER, content="hello"),),
        response_model=model,
        context=LLMRequestContext(
            run_id="run-1",
            agent_id="agent-1",
            tick=0,
            llm_request_id=llm_request_id,
            component="reconstructive_memory",
        ),
        prompt=prompt,
    )


def _wrap(
    tmp_path: Path,
    *,
    mode: RecordingMode,
    clock: FakeClock,
    inner: FakeLLMProvider,
    lookup_mode: LookupMode,
) -> RecordingLLMProvider:
    return RecordingLLMProvider(
        inner=inner,
        mode=mode,
        store=FilesystemRecordingStore(tmp_path),
        cache_namespace="run-1",
        lookup_mode=lookup_mode,
        structured_output_mode=StructuredOutputMode.JSON_SCHEMA,
        provider_name="fake",
        model_name="scripted",
        monotonic=clock.monotonic,
    )


@pytest.mark.asyncio
async def test_schema_field_change_breaks_replay(tmp_path: Path) -> None:
    clock = FakeClock()
    inner = FakeLLMProvider(clock=clock)
    inner.enqueue("req-1", _success())
    await _wrap(
        tmp_path,
        mode=RecordingMode.RECORD,
        clock=clock,
        inner=inner,
        lookup_mode=LookupMode.BY_CORRELATION,
    ).generate(_request())

    with pytest.raises(LLMError) as exc_info:
        await _wrap(
            tmp_path,
            mode=RecordingMode.REPLAY,
            clock=clock,
            inner=FakeLLMProvider(clock=clock),
            lookup_mode=LookupMode.BY_CORRELATION,
        ).generate(_request(model=_OutV2))
    assert exc_info.value.code is LLMErrorCode.CONFIGURATION


@pytest.mark.asyncio
async def test_prompt_digest_change_breaks_replay(tmp_path: Path) -> None:
    clock = FakeClock()
    prompt_a = PromptReference(
        name="reconstructive_memory", version="v1", digest="a" * 64
    )
    prompt_b = PromptReference(
        name="reconstructive_memory", version="v1", digest="b" * 64
    )
    inner = FakeLLMProvider(clock=clock)
    inner.enqueue("req-1", _success())
    await _wrap(
        tmp_path,
        mode=RecordingMode.RECORD,
        clock=clock,
        inner=inner,
        lookup_mode=LookupMode.BY_CORRELATION,
    ).generate(_request(prompt=prompt_a))

    with pytest.raises(LLMError) as exc_info:
        await _wrap(
            tmp_path,
            mode=RecordingMode.REPLAY,
            clock=clock,
            inner=FakeLLMProvider(clock=clock),
            lookup_mode=LookupMode.BY_CORRELATION,
        ).generate(_request(prompt=prompt_b))
    assert exc_info.value.code is LLMErrorCode.CONFIGURATION


@pytest.mark.asyncio
async def test_schema_change_is_cache_miss_not_soft_serve(tmp_path: Path) -> None:
    clock = FakeClock()
    inner = FakeLLMProvider(clock=clock)
    inner.enqueue("req-1", _success())
    await _wrap(
        tmp_path,
        mode=RecordingMode.RECORD,
        clock=clock,
        inner=inner,
        lookup_mode=LookupMode.BY_CACHE_KEY,
    ).generate(_request())

    miss_inner = FakeLLMProvider(clock=clock)
    miss_inner.enqueue(
        "req-1",
        ScriptedSuccess(
            output=_OutV2(kind="wait", note="fresh"),
            metadata=LLMResultMetadata(
                provider_name="fake",
                model_name="scripted",
                finish_reason=FinishReason.STOP,
            ),
        ),
    )
    result = await _wrap(
        tmp_path,
        mode=RecordingMode.CACHE,
        clock=clock,
        inner=miss_inner,
        lookup_mode=LookupMode.BY_CACHE_KEY,
    ).generate(_request(model=_OutV2))
    assert isinstance(result.output, _OutV2)
    assert result.output.note == "fresh"
    assert len(miss_inner.calls()) == 1
