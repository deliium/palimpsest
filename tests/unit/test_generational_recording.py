"""Validated replay-consumption metadata for generational runs."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm.errors import LLMError
from llm.models import StructuredOutputMode
from llm.recording.provider import RecordingLLMProvider, RecordingMode
from llm.recording.store import FilesystemRecordingStore, LookupMode
from tests.unit.test_llm_recording_provider import (
    FakeClock,
    FakeLLMProvider,
    _request,
    _success,
)


def _replay(
    tmp_path: Path,
    *,
    clock: FakeClock,
    callback,
) -> RecordingLLMProvider:
    return RecordingLLMProvider(
        inner=FakeLLMProvider(clock=clock),
        mode=RecordingMode.REPLAY,
        store=FilesystemRecordingStore(tmp_path),
        cache_namespace="run-1",
        lookup_mode=LookupMode.BY_CACHE_KEY,
        structured_output_mode=StructuredOutputMode.JSON_SCHEMA,
        provider_name="fake",
        model_name="scripted",
        monotonic=clock.monotonic,
        on_replay_consumed=callback,
    )


@pytest.mark.asyncio
async def test_successful_replay_emits_payload_free_usage(
    tmp_path: Path
) -> None:
    from llm.recording.provider import RecordingLLMProvider as _Recorder

    clock = FakeClock(start=10.0)
    inner = FakeLLMProvider(clock=clock)
    inner.enqueue("req-1", _success())
    recorder = _Recorder(
        inner=inner,
        mode=RecordingMode.RECORD,
        store=FilesystemRecordingStore(tmp_path),
        cache_namespace="run-1",
        lookup_mode=LookupMode.BY_CACHE_KEY,
        structured_output_mode=StructuredOutputMode.JSON_SCHEMA,
        provider_name="fake",
        model_name="scripted",
        monotonic=clock.monotonic,
    )
    await recorder.generate(_request())

    seen = []
    replay = _replay(tmp_path, clock=FakeClock(start=10.0), callback=seen.append)
    result = await replay.generate(_request())
    assert result.output.kind == "wait"
    assert len(seen) == 1
    usage = seen[0]
    assert usage.request_id == "req-1"
    assert usage.lookup_mode == "by_cache_key"
    assert usage.record_integrity_hash
    assert usage.schema_digest


@pytest.mark.asyncio
async def test_replay_miss_emits_no_usage(tmp_path: Path) -> None:
    seen = []
    replay = _replay(tmp_path, clock=FakeClock(start=10.0), callback=seen.append)
    with pytest.raises(LLMError):
        await replay.generate(_request())
    assert seen == []
