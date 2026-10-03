"""Isolation proofs for recording namespaces and fingerprint hygiene."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from agents.models import AgentId
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
from simulation.models import StochasticIdentity
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    MemoryMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from simulation.runner_serialization import (
    encode_runner_config,
    provider_fingerprint,
)
from tests.fakes.llm import FakeClock, FakeLLMProvider, ScriptedSuccess
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules


class _Out(StructuredOutput):
    kind: str


def _success(kind: str = "wait") -> ScriptedSuccess:
    return ScriptedSuccess(
        output=_Out(kind=kind),
        metadata=LLMResultMetadata(
            provider_name="fake",
            model_name="scripted",
            finish_reason=FinishReason.STOP,
        ),
    )


def _request(
    *,
    agent_id: str = "agent-1",
    content: str = "identical-prompt",
    component: str = "reconstructive_memory",
) -> LLMRequest[_Out]:
    return LLMRequest.create(
        messages=(LLMMessage(role=MessageRole.USER, content=content),),
        response_model=_Out,
        context=LLMRequestContext(
            run_id="ignored-for-key",
            agent_id=agent_id,
            tick=0,
            llm_request_id="req-1",
            component=component,
        ),
    )


def _wrap(
    store: FilesystemRecordingStore,
    *,
    mode: RecordingMode,
    clock: FakeClock,
    inner: FakeLLMProvider,
    namespace: str,
    lookup_mode: LookupMode = LookupMode.BY_CACHE_KEY,
) -> RecordingLLMProvider:
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
async def test_distinct_namespaces_never_hit_even_with_identical_prompts(
    tmp_path: Path,
) -> None:
    clock = FakeClock()
    store = FilesystemRecordingStore(tmp_path)
    parent_inner = FakeLLMProvider(clock=clock)
    parent_inner.enqueue("req-1", _success("parent"))
    await _wrap(
        store,
        mode=RecordingMode.RECORD,
        clock=clock,
        inner=parent_inner,
        namespace="run-parent",
    ).generate(_request())

    child_inner = FakeLLMProvider(clock=clock)
    child_inner.enqueue("req-1", _success("child"))
    result = await _wrap(
        store,
        mode=RecordingMode.CACHE,
        clock=clock,
        inner=child_inner,
        namespace="run-child",
    ).generate(_request())
    assert result.output.kind == "child"
    assert len(child_inner.calls()) == 1


@pytest.mark.asyncio
async def test_fork_style_run_id_namespaces_do_not_share(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    clock = FakeClock()
    store = FilesystemRecordingStore(tmp_path)
    recorder_inner = FakeLLMProvider(clock=clock)
    recorder_inner.enqueue("req-1", _success())
    await _wrap(
        store,
        mode=RecordingMode.RECORD,
        clock=clock,
        inner=recorder_inner,
        namespace="run-abc",
    ).generate(_request())

    with caplog.at_level(logging.DEBUG, logger="llm.recording"):
        miss_inner = FakeLLMProvider(clock=clock)
        miss_inner.enqueue("req-1", _success("fresh"))
        result = await _wrap(
            store,
            mode=RecordingMode.CACHE,
            clock=clock,
            inner=miss_inner,
            namespace="run-abc-fork-1",
        ).generate(_request())
    assert result.output.kind == "fresh"
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "identical-prompt" not in joined


def test_recording_store_settings_do_not_alter_provider_fingerprint() -> None:
    agent_id = AgentId("agent-1")
    config = SimulationRunnerConfig(
        seed=7,
        stochastic_identity=StochasticIdentity("cmp-1"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(alive_body("body-1"),),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=EntityId("body-1"),
                cognition=AgentCognitionSpec(
                    agent_id=agent_id, memory_mode=MemoryMode.REFERENCE
                ),
            ),
        ),
        stop_policy=RunnerStopPolicy(max_ticks=1),
    )
    baseline = provider_fingerprint(config)
    encoded = encode_runner_config(config)
    assert b"cache_namespace" not in encoded
    assert b"lookup_mode" not in encoded
    assert b"root_dir" not in encoded
    assert provider_fingerprint(config) == baseline
