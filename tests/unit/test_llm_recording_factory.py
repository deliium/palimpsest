"""Unit tests for llm.recording factory helpers."""

from __future__ import annotations

from pathlib import Path

from llm.models import StructuredOutputMode
from llm.recording.factory import (
    create_filesystem_recording_store,
    wrap_recording_provider,
)
from llm.recording.provider import RecordingMode
from llm.recording.store import LookupMode
from tests.fakes.llm import FakeClock, FakeLLMProvider


def test_create_filesystem_recording_store(tmp_path: Path) -> None:
    store = create_filesystem_recording_store(tmp_path / "recs")
    assert store.root_dir.name == "recs"
    assert store.count() == 0


def test_wrap_recording_provider_live(tmp_path: Path) -> None:
    clock = FakeClock()
    inner = FakeLLMProvider(clock=clock)
    wrapped = wrap_recording_provider(
        inner=inner,
        mode=RecordingMode.LIVE,
        store=None,
        cache_namespace="",
        lookup_mode=LookupMode.BY_CACHE_KEY,
        structured_output_mode=StructuredOutputMode.JSON_SCHEMA,
        provider_name="fake",
        model_name="scripted",
        monotonic=clock.monotonic,
    )
    assert wrapped.mode is RecordingMode.LIVE
    assert wrapped.inner is inner


def test_wrap_recording_provider_record_requires_store(tmp_path: Path) -> None:
    clock = FakeClock()
    store = create_filesystem_recording_store(tmp_path)
    wrapped = wrap_recording_provider(
        inner=FakeLLMProvider(clock=clock),
        mode=RecordingMode.RECORD,
        store=store,
        cache_namespace="run-1",
        lookup_mode=LookupMode.BY_CACHE_KEY,
        structured_output_mode=StructuredOutputMode.JSON_SCHEMA,
        provider_name="fake",
        model_name="scripted",
        monotonic=clock.monotonic,
    )
    assert wrapped.mode is RecordingMode.RECORD
