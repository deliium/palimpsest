"""Soft stop-append caps for cognition traces (no DELETE)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.cognition.trace import (
    CognitionTraceStageKind,
    CognitionTraceStageStatus,
    CognitionTraceStageSummary,
)
from agents.models import AgentId
from simulation.cognition_trace import (
    CognitionTraceInvocation,
    InMemoryCognitionTraceRepository,
    build_cognition_trace_invocation,
    export_cognition_trace_invocations,
    wrap_cognition_trace_soft_caps,
)
from simulation.models import RunId


def _invocation(invocation_id: str, tick: int = 0) -> CognitionTraceInvocation:
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


@pytest.mark.asyncio
async def test_trace_export_iterator_pages_are_read_only() -> None:
    from simulation.cognition_trace import iter_cognition_trace_invocations

    inner = InMemoryCognitionTraceRepository()
    for index in range(5):
        await inner.append_invocation(_invocation(f"inv-{index}", tick=index))
    items = [
        item
        async for item in iter_cognition_trace_invocations(
            inner, run_id=RunId("run-soft"), page_size=2
        )
    ]
    assert [item.invocation_id for item in items] == [
        "inv-0",
        "inv-1",
        "inv-2",
        "inv-3",
        "inv-4",
    ]
    page = await inner.list_invocations(run_id=RunId("run-soft"), limit=10)
    assert len(page.items) == 5
    limited = await export_cognition_trace_invocations(
        inner, run_id=RunId("run-soft"), limit=2
    )
    assert [item.invocation_id for item in limited] == ["inv-0", "inv-1"]


@pytest.mark.asyncio
async def test_trace_export_iterator_rejects_nonadvancing_cursor() -> None:
    from simulation.cognition_trace import (
        CognitionTracePage,
        iter_cognition_trace_invocations,
    )

    class _Stuck(InMemoryCognitionTraceRepository):
        async def list_invocations(self, **_kwargs: object) -> CognitionTracePage:
            return CognitionTracePage(
                items=(_invocation("inv-stuck"),), next_cursor="stuck-cursor"
            )

    with pytest.raises(ValueError, match="cognition_trace_cursor_nonadvancing"):
        async for _item in iter_cognition_trace_invocations(
            _Stuck(),
            run_id=RunId("run-soft"),
        ):
            pass


@pytest.mark.asyncio
async def test_trace_auxiliary_export_is_read_only(tmp_path: Path) -> None:
    from research_runner.history_archive_composition import (
        export_cognition_trace_auxiliary,
    )
    from simulation.cognition_trace_serialization import (
        decode_cognition_trace_invocation,
    )

    repo = InMemoryCognitionTraceRepository()
    for index in range(3):
        await repo.append_invocation(_invocation(f"inv-{index}", tick=index))
    path = tmp_path / "cognition-traces.jsonl"
    source = await export_cognition_trace_auxiliary(
        traces=repo,
        run_id=RunId("run-soft"),
        path=path,
        max_invocations=2,
    )
    assert source.name == "cognition-traces"
    assert source.capability_class == "cognition_trace"
    lines = path.read_bytes().splitlines()
    assert len(lines) == 2
    decoded = [decode_cognition_trace_invocation(line) for line in lines]
    assert [item.invocation_id for item in decoded] == ["inv-0", "inv-1"]
    page = await repo.list_invocations(run_id=RunId("run-soft"), limit=10)
    assert len(page.items) == 3
