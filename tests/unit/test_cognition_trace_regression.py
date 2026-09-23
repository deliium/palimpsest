"""Volume control, determinism, and V1 regression gates for cognition tracing."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from agents.cognition.trace import (
    CognitionTraceStageKind,
    CognitionTraceStageStatus,
    CognitionTraceStageSummary,
    project_cognition_trace_stages,
)
from agents.models import AgentId
from experiments.catalog import v1_regression_profile
from simulation.cognition_trace import (
    InMemoryCognitionTraceRepository,
    maybe_append_cognition_trace,
)
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    CognitionTraceDetail,
    CognitionTraceSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V2CapabilityFlags,
)
from simulation.runner_serialization import (
    build_runner_result_document,
    decode_runner_config,
    runner_config_fingerprint,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "runner_configs"
    / "catalog_a_condition_v2.json"
)


def _short_pair(
    *,
    cognition_trace: CognitionTraceSpec,
) -> SimulationRunnerConfig:
    legacy = decode_runner_config(FIXTURE.read_bytes())
    return SimulationRunnerConfig(
        seed=legacy.seed,
        stochastic_identity=legacy.stochastic_identity,
        scenario=legacy.scenario,
        agents=legacy.agents,
        stop_policy=RunnerStopPolicy(max_ticks=2),
        mortality_mode=legacy.mortality_mode,
        cognition_failure_policy=legacy.cognition_failure_policy,
        provider=legacy.provider,
        persistence=legacy.persistence,
        experiment=legacy.experiment,
        capability_flags=V2CapabilityFlags(),
        cognition_trace=cognition_trace,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
    )


@pytest.mark.asyncio
async def test_tracing_on_vs_off_same_exact_trajectory_hash() -> None:
    off = _short_pair(cognition_trace=CognitionTraceSpec())
    on = _short_pair(
        cognition_trace=CognitionTraceSpec(
            enabled=True,
            detail=CognitionTraceDetail.STRUCTURED,
        )
    )
    assert runner_config_fingerprint(off) != runner_config_fingerprint(on)

    run_id = RunId("run-trace-traj")
    async with await SimulationRunner.from_config(off, run_id=run_id) as runner:
        result_off = await runner.run()
    async with await SimulationRunner.from_config(on, run_id=run_id) as runner:
        result_on = await runner.run()

    doc_off = build_runner_result_document(result=result_off, config=off)
    doc_on = build_runner_result_document(result=result_on, config=on)
    assert doc_off.exact_trajectory_hash == doc_on.exact_trajectory_hash
    assert (
        doc_off.replica_normalized_trajectory_hash
        == doc_on.replica_normalized_trajectory_hash
    )
    assert doc_off.config_fingerprint != doc_on.config_fingerprint


@pytest.mark.asyncio
async def test_sample_every_n_ticks_skips_non_multiples(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo = InMemoryCognitionTraceRepository()
    spec = CognitionTraceSpec(enabled=True, sample_every_n_ticks=2)
    with caplog.at_level(logging.DEBUG, logger="simulation.cognition_trace"):
        assert await maybe_append_cognition_trace(
            repository=repo,
            spec=spec,
            run_id=RunId("run-1"),
            agent_id=AgentId("agent-1"),
            tick=0,
            invocation_id="inv-0",
            command_kind="wait",
        )
        assert not await maybe_append_cognition_trace(
            repository=repo,
            spec=spec,
            run_id=RunId("run-1"),
            agent_id=AgentId("agent-1"),
            tick=1,
            invocation_id="inv-1",
            command_kind="wait",
        )
        assert await maybe_append_cognition_trace(
            repository=repo,
            spec=spec,
            run_id=RunId("run-1"),
            agent_id=AgentId("agent-1"),
            tick=2,
            invocation_id="inv-2",
            command_kind="wait",
        )
    page = await repo.list_invocations(run_id=RunId("run-1"), limit=10)
    assert {item.tick for item in page.items} == {0, 2}
    assert any(
        r.message == "cognition_trace_skipped"
        and getattr(r, "reason_code", None) == "sample_skip"
        for r in caplog.records
        if hasattr(r, "reason_code") or "sample_skip" in str(getattr(r, "msg", ""))
    ) or any("sample_skip" in str(r.__dict__) for r in caplog.records)


@pytest.mark.asyncio
async def test_max_bytes_truncates_with_reason_code(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo = InMemoryCognitionTraceRepository()
    stages = project_cognition_trace_stages(loop_result=None)
    # Force a tiny budget so only a prefix survives.
    with caplog.at_level(logging.WARNING, logger="simulation.cognition_trace"):
        ok = await maybe_append_cognition_trace(
            repository=repo,
            spec=CognitionTraceSpec(enabled=True, max_bytes_per_invocation=80),
            run_id=RunId("run-1"),
            agent_id=AgentId("agent-1"),
            tick=0,
            invocation_id="inv-trunc",
            command_kind="wait",
        )
    assert ok is True
    loaded = await repo.get_invocation(
        run_id=RunId("run-1"),
        agent_id=AgentId("agent-1"),
        tick=0,
        invocation_id="inv-trunc",
    )
    assert loaded is not None
    assert len(loaded.stages) < len(stages) or any(
        s.status is CognitionTraceStageStatus.TRUNCATED
        or s.reason_code == "max_bytes_per_invocation"
        for s in loaded.stages
    )
    assert any(
        getattr(r, "msg", r.message) == "cognition_trace_truncated"
        or "cognition_trace_truncated" in str(r.msg)
        for r in caplog.records
    )


def test_v1_regression_profile_rejects_enabled_tracing() -> None:
    legacy = decode_runner_config(FIXTURE.read_bytes())
    enabled = SimulationRunnerConfig(
        seed=legacy.seed,
        stochastic_identity=legacy.stochastic_identity,
        scenario=legacy.scenario,
        agents=legacy.agents,
        stop_policy=RunnerStopPolicy(max_ticks=1),
        mortality_mode=legacy.mortality_mode,
        cognition_failure_policy=legacy.cognition_failure_policy,
        provider=legacy.provider,
        persistence=legacy.persistence,
        experiment=legacy.experiment,
        capability_flags=V2CapabilityFlags(),
        cognition_trace=CognitionTraceSpec(enabled=True),
        schema_version=RUNNER_SCHEMA_VERSION_V4,
    )
    with pytest.raises(ValueError, match="v1_regression_trace_enabled"):
        v1_regression_profile(enabled)
    off = SimulationRunnerConfig(
        seed=legacy.seed,
        stochastic_identity=legacy.stochastic_identity,
        scenario=legacy.scenario,
        agents=legacy.agents,
        stop_policy=RunnerStopPolicy(max_ticks=1),
        mortality_mode=legacy.mortality_mode,
        cognition_failure_policy=legacy.cognition_failure_policy,
        provider=legacy.provider,
        persistence=legacy.persistence,
        experiment=legacy.experiment,
        capability_flags=V2CapabilityFlags(),
        cognition_trace=CognitionTraceSpec(),
        schema_version=RUNNER_SCHEMA_VERSION_V4,
    )
    assert v1_regression_profile(off) is off


@pytest.mark.asyncio
async def test_soft_fail_preserves_command_kind_metadata() -> None:
    """Sink boom must not raise; caller still owns the original command_kind."""

    class BoomRepo:
        async def append_invocation(self, invocation: object) -> None:
            raise RuntimeError("boom")

        async def get_invocation(self, **kwargs: object) -> None:
            return None

        async def list_invocations(self, **kwargs: object) -> object:
            raise AssertionError("unused")

    command_kind = "wait"
    ok = await maybe_append_cognition_trace(
        repository=BoomRepo(),  # type: ignore[arg-type]
        spec=CognitionTraceSpec(enabled=True),
        run_id=RunId("run-1"),
        agent_id=AgentId("agent-1"),
        tick=0,
        invocation_id="inv-soft",
        command_kind=command_kind,
        final_confidence=0.5,
    )
    assert ok is False
    assert command_kind == "wait"


def test_projector_stage_order_and_forbidden_fields() -> None:
    stages = project_cognition_trace_stages(loop_result=None)
    kinds = [s.stage_kind for s in stages]
    assert CognitionTraceStageKind.THEORY_OF_MIND in kinds
    tom = next(
        s
        for s in stages
        if s.stage_kind is CognitionTraceStageKind.THEORY_OF_MIND
    )
    assert tom.status is CognitionTraceStageStatus.UNAVAILABLE
    for stage in stages:
        assert not hasattr(stage, "rationale")
        assert not hasattr(stage, "chain_of_thought")
        assert not hasattr(stage, "prompt")
        assert isinstance(stage, CognitionTraceStageSummary)
