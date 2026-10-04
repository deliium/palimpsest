"""Soft stop-append caps for cognition traces (no DELETE)."""

from __future__ import annotations

import pytest

from agents.cognition.trace import (
    CognitionTraceStageKind,
    CognitionTraceStageStatus,
    CognitionTraceStageSummary,
)
from agents.models import AgentId
from simulation.cognition_trace import (
    InMemoryCognitionTraceRepository,
    build_cognition_trace_invocation,
    export_cognition_trace_invocations,
    wrap_cognition_trace_soft_caps,
)
from simulation.models import RunId


def _invocation(invocation_id: str, tick: int = 0):
    stage = CognitionTraceStageSummary(
        stage_kind=CognitionTraceStageKind.OBSERVATION,
        status=CognitionTraceStageStatus.COMPLETED,
        ordinal=0,
        confidence=1.0,
    )
    return build_cognition_trace_invocation(
        run_id=RunId("run-soft"),
        agent_id=AgentId("agent-1"),
        tick=tick,
        invocation_id=invocation_id,
        stage_summaries=(stage,),
    )


@pytest.mark.asyncio
async def test_soft_cap_stops_append_without_deleting_prior(
    caplog: pytest.LogCaptureFixture,
) -> None:
    inner = InMemoryCognitionTraceRepository()
    repo = wrap_cognition_trace_soft_caps(inner, max_invocations=1)
    first = _invocation("inv-1", tick=0)
    second = _invocation("inv-2", tick=1)
    with caplog.at_level("WARNING"):
        await repo.append_invocation(first)
        await repo.append_invocation(second)
    page = await repo.list_invocations(run_id=RunId("run-soft"), limit=10)
    assert len(page.items) == 1
    assert page.items[0].invocation_id == "inv-1"
    assert "soft_cap_reached" in caplog.text
    assert "soft_cap_invocations" in caplog.text


@pytest.mark.asyncio
async def test_export_copy_is_read_only() -> None:
    inner = InMemoryCognitionTraceRepository()
    await inner.append_invocation(_invocation("inv-a"))
    await inner.append_invocation(_invocation("inv-b", tick=1))
    exported = await export_cognition_trace_invocations(
        inner, run_id=RunId("run-soft"), limit=10
    )
    assert [item.invocation_id for item in exported] == ["inv-a", "inv-b"]
    page = await inner.list_invocations(run_id=RunId("run-soft"), limit=10)
    assert len(page.items) == 2
