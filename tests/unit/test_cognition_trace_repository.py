"""Unit tests for simulation cognition-trace ports, codec, and Null sink."""

from __future__ import annotations

import pytest

from agents.cognition.trace import (
    CognitionTraceStageKind,
    CognitionTraceStageStatus,
    CognitionTraceStageSummary,
    unavailable_stage_summary,
)
from agents.models import AgentId
from simulation.cognition_trace import (
    CognitionTraceConflictError,
    InMemoryCognitionTraceRepository,
    NullCognitionTraceRepository,
    build_cognition_trace_invocation,
    maybe_append_cognition_trace,
    select_cognition_trace_repository,
)
from simulation.cognition_trace_serialization import (
    cognition_trace_content_hash,
    decode_cognition_trace_invocation,
    encode_cognition_trace_invocation,
)
from simulation.models import RunId
from simulation.runner_models import CognitionTraceSpec


def _stages() -> tuple[CognitionTraceStageSummary, ...]:
    return (
        CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.OBSERVATION,
            status=CognitionTraceStageStatus.COMPLETED,
            ordinal=0,
            confidence=1.0,
        ),
        unavailable_stage_summary(
            CognitionTraceStageKind.THEORY_OF_MIND,
            ordinal=8,
            reason_code="tom_not_implemented",
        ),
    )


def _invocation(*, command_kind: str = "wait"):
    stages = _stages()
    base = build_cognition_trace_invocation(
        run_id=RunId("run-1"),
        agent_id=AgentId("agent-1"),
        tick=0,
        invocation_id="inv-1",
        stage_summaries=stages,
        command_kind=command_kind,
        final_confidence=0.9,
    )
    digest = cognition_trace_content_hash(base)
    return build_cognition_trace_invocation(
        run_id=RunId("run-1"),
        agent_id=AgentId("agent-1"),
        tick=0,
        invocation_id="inv-1",
        stage_summaries=stages,
        command_kind=command_kind,
        final_confidence=0.9,
        content_hash=digest,
    )


@pytest.mark.asyncio
async def test_in_memory_append_idempotent_and_page() -> None:
    repo = InMemoryCognitionTraceRepository()
    inv = _invocation()
    await repo.append_invocation(inv)
    await repo.append_invocation(inv)  # identical retry
    loaded = await repo.get_invocation(
        run_id=RunId("run-1"),
        agent_id=AgentId("agent-1"),
        tick=0,
        invocation_id="inv-1",
    )
    assert loaded is not None
    assert loaded.content_hash == inv.content_hash
    page = await repo.list_invocations(run_id=RunId("run-1"), limit=10)
    assert len(page.items) == 1


@pytest.mark.asyncio
async def test_in_memory_divergent_conflict() -> None:
    repo = InMemoryCognitionTraceRepository()
    await repo.append_invocation(_invocation(command_kind="wait"))
    with pytest.raises(CognitionTraceConflictError) as exc:
        await repo.append_invocation(_invocation(command_kind="move"))
    assert exc.value.code == "divergent_content_hash"


@pytest.mark.asyncio
async def test_null_repository_records_nothing() -> None:
    repo = NullCognitionTraceRepository()
    await repo.append_invocation(_invocation())
    assert (
        await repo.get_invocation(
            run_id=RunId("run-1"),
            agent_id=AgentId("agent-1"),
            tick=0,
            invocation_id="inv-1",
        )
        is None
    )
    page = await repo.list_invocations(run_id=RunId("run-1"))
    assert page.items == ()


def test_select_repository_null_when_disabled() -> None:
    repo = select_cognition_trace_repository(enabled=False)
    assert type(repo) is NullCognitionTraceRepository
    repo_on = select_cognition_trace_repository(enabled=True)
    assert type(repo_on) is InMemoryCognitionTraceRepository


def test_codec_round_trip_stable_hash() -> None:
    inv = _invocation()
    encoded = encode_cognition_trace_invocation(inv)
    decoded = decode_cognition_trace_invocation(encoded)
    assert decoded.run_id == inv.run_id
    assert decoded.agent_id == inv.agent_id
    assert decoded.tick == inv.tick
    assert decoded.invocation_id == inv.invocation_id
    assert decoded.command_kind == inv.command_kind
    assert len(decoded.stages) == len(inv.stages)
    assert decoded.content_hash == cognition_trace_content_hash(decoded)
    assert encode_cognition_trace_invocation(decoded) == encoded


@pytest.mark.asyncio
async def test_maybe_append_soft_fails_without_changing_outcome() -> None:
    class BoomRepo:
        async def append_invocation(self, invocation: object) -> None:
            raise RuntimeError("sink_boom")

        async def get_invocation(self, **kwargs: object) -> None:
            return None

        async def list_invocations(self, **kwargs: object) -> object:
            raise AssertionError("unused")

    ok = await maybe_append_cognition_trace(
        repository=BoomRepo(),  # type: ignore[arg-type]
        spec=CognitionTraceSpec(enabled=True),
        run_id=RunId("run-1"),
        agent_id=AgentId("agent-1"),
        tick=0,
        invocation_id="inv-1",
        command_kind="wait",
        final_confidence=1.0,
    )
    assert ok is False

    skipped = await maybe_append_cognition_trace(
        repository=InMemoryCognitionTraceRepository(),
        spec=CognitionTraceSpec(enabled=False),
        run_id=RunId("run-1"),
        agent_id=AgentId("agent-1"),
        tick=0,
        invocation_id="inv-1",
    )
    assert skipped is False
