"""Recorded cognition replay in a real independent generational run.

RECORD wraps the default inner-provider seam with a schema-correct deterministic
fake. REPLAY consumes archived outputs through the same archival composition
and must never generate or fall back for recorded requests.
"""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from agents.cognition.reconstruction import ReconstructedMemoryCandidate
from agents.cognition.reflection import ReflectionSelectionOutput
from experiments.civilization_benchmark_forks import _materialize_engine
from experiments.civilization_benchmark_population import (
    build_population_benchmark,
)
from experiments.civilization_benchmark_suite import V3_BENCH_01_BLANK_SLATE
from experiments.coordinator import ExperimentAssignment
from experiments.generational_archive import GenerationalExecutionRecipe
from experiments.generational_artifacts import GenerationalUsageStore
from experiments.generational_execution import (
    PLAIN_RECIPE_ID,
    GenerationalExecutionContext,
    execute_generational_assignment,
)
from llm.factory import DeterministicFakeLLMProvider, ProviderAdapterKind
from llm.models import FinishReason, LLMResult, LLMResultMetadata
from llm.recording.store import LookupMode
from simulation.fork_checkpoint import ForkCheckpointError
from simulation.models import RunId
from simulation.runner import (
    RecordingStoreSettings,
    RunnerConstructionError,
    RunnerDependencyFactories,
    SimulationRunner,
)
from simulation.runner_models import (
    ExactReproducibilityMode,
    RecordingPolicy,
    ReflectionMode,
    SimulationRunnerConfig,
)

pytestmark = pytest.mark.integration


class _RecordingFake:
    """Schema-correct deterministic inner provider for recorded cognition."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, request: Any) -> LLMResult[Any]:
        self.calls += 1
        if request.response_model is ReflectionSelectionOutput:
            output: Any = ReflectionSelectionOutput(selected_ids=())
        elif request.response_model is ReconstructedMemoryCandidate:
            output = ReconstructedMemoryCandidate(
                narrative="recalled",
                concepts=(),
                entity_labels=(),
                entity_ids=(),
                relation_predicates=(),
                relation_subject_indexes=(),
                relation_object_indexes=(),
                relation_subject_kinds=(),
                relation_object_kinds=(),
                context_tags=(),
                confidence=0.5,
                emotional_salience=0.0,
                source_memory_ids=(),
            )
        else:
            raise AssertionError("unexpected recording schema")
        return LLMResult(
            output=output,
            metadata=LLMResultMetadata(
                provider_name="fake",
                model_name="scripted",
                finish_reason=FinishReason.STOP,
            ),
        )

    async def close(self) -> None:
        return None


class _ReplayStub(DeterministicFakeLLMProvider):
    """Replay inner provider that must never generate."""

    calls = 0

    async def generate(self, request: Any) -> LLMResult[Any]:
        type(self).calls += 1
        raise AssertionError("replay fallback must not generate")


async def _noop_sleep(_seconds: float) -> None:
    return None


def _config(
    *, policy: RecordingPolicy, exact: ExactReproducibilityMode
) -> SimulationRunnerConfig:
    base = build_population_benchmark(V3_BENCH_01_BLANK_SLATE).arms[0].config
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition, reflection_mode=ReflectionMode.LLM_ASSISTED
            ),
        )
        for agent in base.agents
    )
    return replace(
        base,
        agents=agents,
        stop_policy=replace(base.stop_policy, max_ticks=8),
        provider=replace(
            base.provider,
            adapter_kind=ProviderAdapterKind.OPENAI_COMPATIBLE,
            model="scripted",
            recording_policy=policy,
            exact_reproducibility=exact,
            retry_count=1,
            per_attempt_timeout_seconds=1.0,
            total_deadline_seconds=5.0,
        ),
    )


async def _execute(
    config: SimulationRunnerConfig,
    *,
    archive_root: Path,
    store_root: Path,
    attempt_id: str,
) -> Any:
    factories = RunnerDependencyFactories(
        recording_store=RecordingStoreSettings(
            root_dir=store_root,
            cache_namespace="v3-civ-bench",
            lookup_mode=LookupMode.BY_CORRELATION,
        ),
        sleep=_noop_sleep,
        monotonic=time.monotonic,
    )
    assignment = ExperimentAssignment(
        experiment_id="v3-recorded-cognition",
        condition_id="case-01",
        condition_ordinal=0,
        seed=config.seed,
        seed_ordinal=0,
        replicate_index=0,
        run_id=RunId("v3-recorded-run"),
        runner_config=config,
    )
    context = GenerationalExecutionContext(
        artifact_root=archive_root,
        source_identity={"code_revision": "deadbeef", "source_clean": True},
        recipe=GenerationalExecutionRecipe(
            recipe_id=PLAIN_RECIPE_ID, version="1", params={}
        ),
        factories=factories,
        attempt_id=attempt_id,
        recording_identity={
            "lookup_mode": "by_correlation",
            "recording_artifact_id": "v3-recording-store-v1",
            "recording_namespace": "v3-civ-bench",
        },
    )
    return await execute_generational_assignment(assignment, context)


def _records(store_root: Path) -> tuple[Path, ...]:
    return tuple(store_root.glob("ns/*/keys/*.json"))


@pytest.mark.asyncio
async def test_record_then_replay_independent_generational_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import simulation.runner as runner_module

    record_fake = _RecordingFake()
    monkeypatch.setattr(
        runner_module, "create_llm_provider", lambda *_a, **_k: record_fake
    )
    store_root = tmp_path / "recordings"
    recorded = await _execute(
        _config(
            policy=RecordingPolicy.RECORD,
            exact=ExactReproducibilityMode.NOT_REQUIRED,
        ),
        archive_root=tmp_path / "record-archive",
        store_root=store_root,
        attempt_id="record",
    )
    assert record_fake.calls > 0
    assert _records(store_root)
    assert recorded.runner_result.objective_state_hash is not None
    assert (
        GenerationalUsageStore(
            root=tmp_path / "record-archive",
            run_id="v3-recorded-run",
            attempt_id="record",
        ).count()
        == 0
    )

    _ReplayStub.calls = 0
    monkeypatch.setattr(runner_module, "DeterministicFakeLLMProvider", _ReplayStub)
    replayed = await _execute(
        _config(
            policy=RecordingPolicy.REPLAY,
            exact=ExactReproducibilityMode.REQUIRED,
        ),
        archive_root=tmp_path / "replay-archive",
        store_root=store_root,
        attempt_id="replay",
    )
    assert replayed.runner_result.objective_state_hash == (
        recorded.runner_result.objective_state_hash
    )
    assert _ReplayStub.calls == 0
    usage = GenerationalUsageStore(
        root=tmp_path / "replay-archive",
        run_id="v3-recorded-run",
        attempt_id="replay",
    )
    assert usage.count() > 0


@pytest.mark.asyncio
async def test_missing_record_fails_closed_without_replay_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import simulation.runner as runner_module

    monkeypatch.setattr(runner_module, "DeterministicFakeLLMProvider", _ReplayStub)
    _ReplayStub.calls = 0
    with pytest.raises(RunnerConstructionError):
        await _execute(
            _config(
                policy=RecordingPolicy.REPLAY,
                exact=ExactReproducibilityMode.REQUIRED,
            ),
            archive_root=tmp_path / "empty-archive",
            store_root=tmp_path / "empty-store",
            attempt_id="replay",
        )
    usage = GenerationalUsageStore(
        root=tmp_path / "empty-archive",
        run_id="v3-recorded-run",
        attempt_id="replay",
    )
    assert usage.count() == 0
    assert _ReplayStub.calls == 0


def test_custom_provider_factory_is_rejected_for_archival_usage() -> None:
    class _UnusedProvider:
        async def close(self) -> None:
            return None

    factories = RunnerDependencyFactories(
        provider_factory=lambda *_a, **_k: _UnusedProvider()
    )
    with pytest.raises(RunnerConstructionError) as excinfo:
        factories.with_generational_control(
            boundary_observer=None, recording_usage_sink=object()
        )
    assert excinfo.value.code == "untracked_custom_provider"


@pytest.mark.asyncio
async def test_recorded_provider_forks_remain_rejected() -> None:
    base = build_population_benchmark(V3_BENCH_01_BLANK_SLATE).arms[0].config
    deterministic = replace(base, stop_policy=replace(base.stop_policy, max_ticks=4))
    parent = await SimulationRunner.from_config(
        deterministic, run_id=RunId("recorded-fork-parent")
    )
    try:
        for _ in range(2):
            await parent.run_tick()
        checkpoint = await parent.capture_fork_checkpoint()
    finally:
        await parent.aclose()
    replay = _config(
        policy=RecordingPolicy.REPLAY,
        exact=ExactReproducibilityMode.REQUIRED,
    )
    with pytest.raises(ForkCheckpointError):
        await SimulationRunner.from_fork_checkpoint(
            replay,
            run_id=RunId("recorded-fork-child"),
            checkpoint=checkpoint,
            restored_engine=await _materialize_engine(
                checkpoint, RunId("recorded-fork-child")
            ),
        )
