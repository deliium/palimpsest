"""Unit tests for event → cognition-trace invocation resolution."""

from __future__ import annotations

import pytest

from agents.cognition.trace import (
    CognitionTraceStageKind,
    CognitionTraceStageStatus,
    CognitionTraceStageSummary,
)
from agents.models import AgentId
from simulation import (
    CausalTraceAvailability,
    DebuggerEventRecord,
    InMemoryDebuggerEventLookup,
    RunId,
    build_cognition_trace_invocation,
    resolve_invocation_for_event,
)
from simulation.cognition_trace import InMemoryCognitionTraceRepository
from tests.fakes.debugger import seed_attack_event


def _minimal_stages() -> tuple[CognitionTraceStageSummary, ...]:
    return (
        CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.OBSERVATION,
            status=CognitionTraceStageStatus.COMPLETED,
            ordinal=0,
            confidence=0.5,
        ),
        CognitionTraceStageSummary(
            stage_kind=CognitionTraceStageKind.PLANNED_ACTION,
            status=CognitionTraceStageStatus.COMPLETED,
            ordinal=1,
            confidence=0.9,
            command_kind="attack",
        ),
    )


@pytest.mark.asyncio
async def test_alice_attacked_bob_resolves_attack_invocation() -> None:
    run_id = RunId("run-attack")
    agent = AgentId("alice")
    traces = InMemoryCognitionTraceRepository()
    events = InMemoryDebuggerEventLookup()
    record = seed_attack_event(events, run_id=run_id)
    await traces.append_invocation(
        build_cognition_trace_invocation(
            run_id=run_id,
            agent_id=agent,
            tick=record.tick,
            invocation_id="inv-attack-1",
            stage_summaries=_minimal_stages(),
            command_kind="attack",
        )
    )

    result = await resolve_invocation_for_event(
        run_id=run_id,
        traces=traces,
        events=events,
        tick=record.tick,
        sequence=record.sequence,
    )
    assert result.availability is CausalTraceAvailability.AVAILABLE
    assert result.invocation_id == "inv-attack-1"
    assert result.command_kind == "attack"
    assert result.ambiguity is False
    assert result.address.agent_id == agent
    assert result.address.sequence == 17


@pytest.mark.asyncio
async def test_missing_trace_unavailable() -> None:
    run_id = RunId("run-missing")
    events = InMemoryDebuggerEventLookup()
    seed_attack_event(events, run_id=run_id)
    result = await resolve_invocation_for_event(
        run_id=run_id,
        traces=InMemoryCognitionTraceRepository(),
        events=events,
        event_id="evt-attack-1",
    )
    assert result.availability is CausalTraceAvailability.UNAVAILABLE
    assert result.reason_code == "cognition_trace_missing"


@pytest.mark.asyncio
async def test_multi_invocation_ambiguity_picks_lexicographic_min() -> None:
    run_id = RunId("run-ambig")
    agent = AgentId("alice")
    traces = InMemoryCognitionTraceRepository()
    events = InMemoryDebuggerEventLookup()
    record = seed_attack_event(events, run_id=run_id)
    for inv_id in ("inv-b", "inv-a"):
        await traces.append_invocation(
            build_cognition_trace_invocation(
                run_id=run_id,
                agent_id=agent,
                tick=record.tick,
                invocation_id=inv_id,
                stage_summaries=_minimal_stages(),
                command_kind="attack",
            )
        )
    result = await resolve_invocation_for_event(
        run_id=run_id,
        traces=traces,
        events=events,
        event_id=record.event_id,
    )
    assert result.availability is CausalTraceAvailability.AVAILABLE
    assert result.invocation_id == "inv-a"
    assert result.ambiguity is True
    assert result.reason_code == "multiple_invocations"


@pytest.mark.asyncio
async def test_environmental_event_without_actor_not_applicable() -> None:
    run_id = RunId("run-env")
    events = InMemoryDebuggerEventLookup()
    events.seed(
        run_id=run_id,
        record=DebuggerEventRecord(
            event_id="evt-weather",
            tick=5,
            sequence=0,
            actor_id=None,
            detail_kind="weather_changed",
            semantic_type="WEATHER_CHANGED",
            detail_type_name="WeatherChanged",
        ),
    )
    result = await resolve_invocation_for_event(
        run_id=run_id,
        traces=InMemoryCognitionTraceRepository(),
        events=events,
        event_id="evt-weather",
    )
    assert result.availability is CausalTraceAvailability.NOT_APPLICABLE
    assert result.reason_code == "causal_trace_not_applicable"


@pytest.mark.asyncio
async def test_died_without_actor_not_applicable() -> None:
    run_id = RunId("run-died")
    events = InMemoryDebuggerEventLookup()
    events.seed(
        run_id=run_id,
        record=DebuggerEventRecord(
            event_id="evt-died",
            tick=9,
            sequence=2,
            actor_id=None,
            detail_kind="died",
            semantic_type="AGENT_DIED",
            detail_type_name="Died",
        ),
    )
    result = await resolve_invocation_for_event(
        run_id=run_id,
        traces=InMemoryCognitionTraceRepository(),
        events=events,
        tick=9,
        sequence=2,
    )
    assert result.availability is CausalTraceAvailability.NOT_APPLICABLE
    assert result.reason_code == "causal_trace_not_applicable"


@pytest.mark.asyncio
async def test_died_with_attacking_actor_resolves_attack() -> None:
    run_id = RunId("run-lethal")
    agent = AgentId("alice")
    traces = InMemoryCognitionTraceRepository()
    events = InMemoryDebuggerEventLookup()
    events.seed(
        run_id=run_id,
        record=DebuggerEventRecord(
            event_id="evt-died-lethal",
            tick=11,
            sequence=3,
            actor_id="alice",
            agent_id="alice",
            detail_kind="died",
            semantic_type="AGENT_DIED",
            detail_type_name="Died",
        ),
    )
    await traces.append_invocation(
        build_cognition_trace_invocation(
            run_id=run_id,
            agent_id=agent,
            tick=11,
            invocation_id="inv-lethal",
            stage_summaries=_minimal_stages(),
            command_kind="attack",
        )
    )
    result = await resolve_invocation_for_event(
        run_id=run_id,
        traces=traces,
        events=events,
        event_id="evt-died-lethal",
    )
    assert result.availability is CausalTraceAvailability.AVAILABLE
    assert result.invocation_id == "inv-lethal"
    assert result.command_kind == "attack"
