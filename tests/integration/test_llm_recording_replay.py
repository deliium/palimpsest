"""Network-free integration: record then exact replay via RecordingLLMProvider."""

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
    StructuredOutput,
    StructuredOutputMode,
)
from llm.recording.provider import RecordingLLMProvider, RecordingMode
from llm.recording.store import FilesystemRecordingStore, LookupMode
from tests.fakes.llm import FakeClock, FakeLLMProvider, ScriptedSuccess

pytestmark = pytest.mark.integration


class _Decision(StructuredOutput):
    kind: str
    confidence: float


def _request(
    *,
    llm_request_id: str = "req-1",
    component: str | None = "reconstructive_memory",
    content: str = "recall-evidence",
) -> LLMRequest[_Decision]:
    return LLMRequest.create(
        messages=(LLMMessage(role=MessageRole.USER, content=content),),
        response_model=_Decision,
        context=LLMRequestContext(
            run_id="run-integration-1",
            agent_id="agent-1",
            tick=3,
            llm_request_id=llm_request_id,
            component=component,
        ),
    )


def _success() -> ScriptedSuccess:
    return ScriptedSuccess(
        output=_Decision(kind="wait", confidence=0.75),
        metadata=LLMResultMetadata(
            provider_name="fake",
            model_name="scripted",
            finish_reason=FinishReason.STOP,
        ),
    )


def _provider(
    tmp_path: Path,
    *,
    mode: RecordingMode,
    clock: FakeClock,
    inner: FakeLLMProvider,
    lookup_mode: LookupMode = LookupMode.BY_CORRELATION,
) -> RecordingLLMProvider:
    return RecordingLLMProvider(
        inner=inner,
        mode=mode,
        store=FilesystemRecordingStore(tmp_path),
        cache_namespace="run-integration-1",
        lookup_mode=lookup_mode,
        structured_output_mode=StructuredOutputMode.JSON_SCHEMA,
        provider_name="fake",
        model_name="scripted",
        monotonic=clock.monotonic,
    )


@pytest.mark.asyncio
async def test_record_then_replay_identical_structured_output(tmp_path: Path) -> None:
    clock = FakeClock(start=1.0)
    record_inner = FakeLLMProvider(clock=clock)
    record_inner.enqueue("req-1", _success())
    recorded = await _provider(
        tmp_path, mode=RecordingMode.RECORD, clock=clock, inner=record_inner
    ).generate(_request())
    assert recorded.output == _Decision(kind="wait", confidence=0.75)
    assert len(record_inner.calls()) == 1

    replay_inner = FakeLLMProvider(clock=clock)
    replayed = await _provider(
        tmp_path, mode=RecordingMode.REPLAY, clock=clock, inner=replay_inner
    ).generate(_request())
    assert replayed.output == recorded.output
    assert len(replay_inner.calls()) == 0


@pytest.mark.asyncio
async def test_replay_miss_fails_closed(tmp_path: Path) -> None:
    clock = FakeClock()
    with pytest.raises(LLMError) as exc_info:
        await _provider(
            tmp_path,
            mode=RecordingMode.REPLAY,
            clock=clock,
            inner=FakeLLMProvider(clock=clock),
        ).generate(_request(llm_request_id="missing"))
    assert exc_info.value.code is LLMErrorCode.CONFIGURATION


@pytest.mark.asyncio
async def test_replay_component_mismatch_fails_closed(tmp_path: Path) -> None:
    clock = FakeClock()
    inner = FakeLLMProvider(clock=clock)
    inner.enqueue("req-1", _success())
    await _provider(
        tmp_path, mode=RecordingMode.RECORD, clock=clock, inner=inner
    ).generate(_request(component="reconstructive_memory"))

    with pytest.raises(LLMError) as exc_info:
        await _provider(
            tmp_path,
            mode=RecordingMode.REPLAY,
            clock=clock,
            inner=FakeLLMProvider(clock=clock),
        ).generate(_request(component="reflection"))
    assert exc_info.value.code is LLMErrorCode.CONFIGURATION


@pytest.mark.asyncio
async def test_replay_schema_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    class _Drifted(StructuredOutput):
        kind: str
        confidence: float
        tag: str = "x"

    clock = FakeClock()
    inner = FakeLLMProvider(clock=clock)
    inner.enqueue("req-1", _success())
    await _provider(
        tmp_path, mode=RecordingMode.RECORD, clock=clock, inner=inner
    ).generate(_request())

    drifted = LLMRequest.create(
        messages=(LLMMessage(role=MessageRole.USER, content="recall-evidence"),),
        response_model=_Drifted,
        context=LLMRequestContext(
            run_id="run-integration-1",
            agent_id="agent-1",
            tick=3,
            llm_request_id="req-1",
            component="reconstructive_memory",
        ),
    )
    with pytest.raises(LLMError) as exc_info:
        await _provider(
            tmp_path,
            mode=RecordingMode.REPLAY,
            clock=clock,
            inner=FakeLLMProvider(clock=clock),
        ).generate(drifted)  # type: ignore[arg-type]
    assert exc_info.value.code is LLMErrorCode.CONFIGURATION
