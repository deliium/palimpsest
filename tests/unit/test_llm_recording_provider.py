"""Unit tests for RecordingLLMProvider mode machine."""

from __future__ import annotations

import logging
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


class _OutDrift(StructuredOutput):
    kind: str
    extra: str = "x"


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(start=10.0)


def _request(
    *,
    component: str | None = "reconstructive_memory",
    llm_request_id: str = "req-1",
    tick: int = 0,
    prompt: PromptReference | None = None,
    content: str = "hello",
) -> LLMRequest[_Out]:
    return LLMRequest.create(
        messages=(LLMMessage(role=MessageRole.USER, content=content),),
        response_model=_Out,
        context=LLMRequestContext(
            run_id="run-1",
            agent_id="agent-1",
            tick=tick,
            llm_request_id=llm_request_id,
            component=component,
        ),
        prompt=prompt,
    )


def _success() -> ScriptedSuccess:
    return ScriptedSuccess(
        output=_Out(kind="wait"),
        metadata=LLMResultMetadata(
            provider_name="fake",
            model_name="scripted",
            finish_reason=FinishReason.STOP,
        ),
    )


def _wrap(
    tmp_path: Path,
    *,
    mode: RecordingMode,
    clock: FakeClock,
    inner: FakeLLMProvider,
    lookup_mode: LookupMode = LookupMode.BY_CACHE_KEY,
    namespace: str = "run-1",
) -> RecordingLLMProvider:
    store: FilesystemRecordingStore | None
    if mode is RecordingMode.LIVE:
        store = None
        namespace = ""
    else:
        store = FilesystemRecordingStore(tmp_path)
    return RecordingLLMProvider(
        inner=inner,
        mode=mode,
        store=store,
        cache_namespace=namespace,
        lookup_mode=lookup_mode,
        structured_output_mode=StructuredOutputMode.JSON_SCHEMA,
        provider_name="fake",
        model_name="scripted",
        monotonic=clock.monotonic,
    )


@pytest.mark.asyncio
async def test_live_passthrough_never_touches_store(
    tmp_path: Path, clock: FakeClock
) -> None:
    inner = FakeLLMProvider(clock=clock)
    inner.enqueue("req-1", _success())
    wrapped = _wrap(tmp_path, mode=RecordingMode.LIVE, clock=clock, inner=inner)
    result = await wrapped.generate(_request())
    assert result.output.kind == "wait"
    assert FilesystemRecordingStore(tmp_path).count() == 0


@pytest.mark.asyncio
async def test_record_persists_and_replay_avoids_inner(
    tmp_path: Path, clock: FakeClock
) -> None:
    inner = FakeLLMProvider(clock=clock)
    inner.enqueue("req-1", _success())
    recorder = _wrap(tmp_path, mode=RecordingMode.RECORD, clock=clock, inner=inner)
    first = await recorder.generate(_request())
    assert first.output.kind == "wait"
    assert len(inner.calls()) == 1

    inner2 = FakeLLMProvider(clock=clock)
    replay = _wrap(tmp_path, mode=RecordingMode.REPLAY, clock=clock, inner=inner2)
    second = await replay.generate(_request())
    assert second.output == first.output
    assert len(inner2.calls()) == 0


@pytest.mark.asyncio
async def test_replay_miss_fails_closed(tmp_path: Path, clock: FakeClock) -> None:
    replay = _wrap(
        tmp_path,
        mode=RecordingMode.REPLAY,
        clock=clock,
        inner=FakeLLMProvider(clock=clock),
    )
    with pytest.raises(LLMError) as exc_info:
        await replay.generate(_request())
    assert exc_info.value.code is LLMErrorCode.CONFIGURATION


@pytest.mark.asyncio
async def test_component_required(tmp_path: Path, clock: FakeClock) -> None:
    inner = FakeLLMProvider(clock=clock)
    inner.enqueue("req-1", _success())
    wrapped = _wrap(tmp_path, mode=RecordingMode.RECORD, clock=clock, inner=inner)
    with pytest.raises(LLMError) as exc_info:
        await wrapped.generate(_request(component=None))
    assert exc_info.value.code is LLMErrorCode.CONFIGURATION


@pytest.mark.asyncio
async def test_cache_hit_skips_inner(tmp_path: Path, clock: FakeClock) -> None:
    inner = FakeLLMProvider(clock=clock)
    inner.enqueue("req-1", _success())
    recorder = _wrap(tmp_path, mode=RecordingMode.RECORD, clock=clock, inner=inner)
    await recorder.generate(_request())

    inner2 = FakeLLMProvider(clock=clock)
    cached = _wrap(tmp_path, mode=RecordingMode.CACHE, clock=clock, inner=inner2)
    result = await cached.generate(_request())
    assert result.output.kind == "wait"
    assert len(inner2.calls()) == 0


@pytest.mark.asyncio
async def test_replay_schema_digest_mismatch_fails_closed(
    tmp_path: Path, clock: FakeClock
) -> None:
    inner = FakeLLMProvider(clock=clock)
    inner.enqueue("req-1", _success())
    recorder = _wrap(
        tmp_path,
        mode=RecordingMode.RECORD,
        clock=clock,
        inner=inner,
        lookup_mode=LookupMode.BY_CORRELATION,
    )
    await recorder.generate(_request())

    replay = _wrap(
        tmp_path,
        mode=RecordingMode.REPLAY,
        clock=clock,
        inner=FakeLLMProvider(clock=clock),
        lookup_mode=LookupMode.BY_CORRELATION,
    )
    drifted = LLMRequest.create(
        messages=(LLMMessage(role=MessageRole.USER, content="hello"),),
        response_model=_OutDrift,
        context=LLMRequestContext(
            run_id="run-1",
            agent_id="agent-1",
            tick=0,
            llm_request_id="req-1",
            component="reconstructive_memory",
        ),
    )
    with pytest.raises(LLMError) as exc_info:
        await replay.generate(drifted)
    assert exc_info.value.code is LLMErrorCode.CONFIGURATION


@pytest.mark.asyncio
async def test_replay_prompt_digest_mismatch_fails_closed(
    tmp_path: Path, clock: FakeClock
) -> None:
    prompt_a = PromptReference(
        name="reconstructive_memory", version="v1", digest="a" * 64
    )
    prompt_b = PromptReference(
        name="reconstructive_memory", version="v1", digest="b" * 64
    )
    inner = FakeLLMProvider(clock=clock)
    inner.enqueue("req-1", _success())
    recorder = _wrap(
        tmp_path,
        mode=RecordingMode.RECORD,
        clock=clock,
        inner=inner,
        lookup_mode=LookupMode.BY_CORRELATION,
    )
    await recorder.generate(_request(prompt=prompt_a))

    replay = _wrap(
        tmp_path,
        mode=RecordingMode.REPLAY,
        clock=clock,
        inner=FakeLLMProvider(clock=clock),
        lookup_mode=LookupMode.BY_CORRELATION,
    )
    with pytest.raises(LLMError) as exc_info:
        await replay.generate(_request(prompt=prompt_b))
    assert exc_info.value.code is LLMErrorCode.CONFIGURATION


@pytest.mark.asyncio
async def test_metadata_only_logs(
    tmp_path: Path, clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    inner = FakeLLMProvider(clock=clock)
    inner.enqueue("req-1", _success())
    recorder = _wrap(tmp_path, mode=RecordingMode.RECORD, clock=clock, inner=inner)
    with caplog.at_level(logging.DEBUG, logger="llm.recording"):
        await recorder.generate(_request(content="TOP-SECRET-BODY"))
        replay = _wrap(
            tmp_path,
            mode=RecordingMode.REPLAY,
            clock=clock,
            inner=FakeLLMProvider(clock=clock),
        )
        await replay.generate(_request(content="TOP-SECRET-BODY"))
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "TOP-SECRET-BODY" not in joined
