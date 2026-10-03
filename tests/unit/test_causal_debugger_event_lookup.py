"""Unit tests for DebuggerEventLookupPort in-memory fake."""

from __future__ import annotations

import pytest

from simulation import (
    CausalDebuggerError,
    DebuggerEventRecord,
    InMemoryDebuggerEventLookup,
    RunId,
    resolve_invocation_for_event,
)
from simulation.cognition_trace import InMemoryCognitionTraceRepository
from tests.fakes.debugger import seed_attack_event


@pytest.mark.asyncio
async def test_lookup_by_event_id_and_tick_sequence() -> None:
    run_id = RunId("run-lookup")
    lookup = InMemoryDebuggerEventLookup()
    record = seed_attack_event(lookup, run_id=run_id)
    by_id = await lookup.get_by_event_id(run_id=run_id, event_id=record.event_id)
    by_cursor = await lookup.get_by_tick_sequence(
        run_id=run_id, tick=record.tick, sequence=record.sequence
    )
    assert by_id == record
    assert by_cursor == record


@pytest.mark.asyncio
async def test_lookup_not_found_returns_none() -> None:
    run_id = RunId("run-lookup")
    lookup = InMemoryDebuggerEventLookup()
    assert (
        await lookup.get_by_event_id(run_id=run_id, event_id="missing")
    ) is None
    assert (
        await lookup.get_by_tick_sequence(run_id=run_id, tick=1, sequence=0)
    ) is None


@pytest.mark.asyncio
async def test_incomplete_cursor_raises() -> None:
    with pytest.raises(CausalDebuggerError) as exc:
        await resolve_invocation_for_event(
            run_id=RunId("run-x"),
            traces=InMemoryCognitionTraceRepository(),
            events=InMemoryDebuggerEventLookup(),
            tick=1,
        )
    assert exc.value.code == "incomplete_event_cursor"


def test_event_record_rejects_payloadish_construction_fields() -> None:
    record = DebuggerEventRecord(
        event_id="e1",
        tick=0,
        sequence=0,
        actor_id="alice",
        detail_kind="attack",
        semantic_type="AGENT_ATTACKED",
    )
    assert not hasattr(record, "rationale")
    assert not hasattr(record, "utterance_text")
