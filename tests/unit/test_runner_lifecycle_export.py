"""Runner result exports lifecycle records and derives generation indexes."""

from __future__ import annotations

from experiments.collectors import generation_index_from_lifecycle_records
from simulation.models import RunId
from simulation.runner_models import (
    CognitionCounters,
    RunnerStopReasonCode,
    SimulationRunnerResult,
)
from world.identifiers import EntityId
from world.lifecycle import (
    AgentLifecycleRecord,
    DependencyStatus,
    LifecycleStageId,
    OriginProvenance,
)


def _record(agent: str, generation: int, entry_tick: int = 0) -> AgentLifecycleRecord:
    return AgentLifecycleRecord(
        body_id=EntityId(f"body-{agent}"),
        agent_id=agent,
        entry_tick=entry_tick,
        stage=LifecycleStageId("adult"),
        dependency_status=DependencyStatus.INDEPENDENT,
        generation_index=generation,
        cohort_id="cohort-a",
        provenance=OriginProvenance.BOOTSTRAP,
        assigned_lifespan_ticks=12,
    )


def _result(**kwargs: object) -> SimulationRunnerResult:
    return SimulationRunnerResult(
        run_id=RunId("run-lifecycle-export"),
        ticks_committed=1,
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        attempt_receipts=(),
        cognition_counters=CognitionCounters(),
        **kwargs,
    )


def test_result_accepts_deterministic_lifecycle_tuple() -> None:
    first = _record("agent-a", 0)
    second = _record("agent-b", 1, entry_tick=8)
    result = _result(initial_lifecycle_records=(first, second))
    assert result.initial_lifecycle_records == (first, second)
    assert _result().initial_lifecycle_records == ()


def test_result_rejects_unordered_or_invalid_lifecycle_items() -> None:
    try:
        _result(initial_lifecycle_records=frozenset())
    except TypeError as error:
        assert "must be ordered" in str(error)
    else:  # pragma: no cover - defensive
        raise AssertionError("unordered lifecycle records must be rejected")
    try:
        _result(initial_lifecycle_records=("record",))
    except TypeError as error:
        assert "invalid_item" in str(error)
    else:  # pragma: no cover - defensive
        raise AssertionError("invalid lifecycle records must be rejected")


def test_generation_index_derived_from_lifecycle_records() -> None:
    records = (_record("agent-a", 0), _record("agent-b", 2, entry_tick=8))
    assert generation_index_from_lifecycle_records(records) == {
        "agent-a": 0,
        "agent-b": 2,
    }
    assert generation_index_from_lifecycle_records(()) is None


def test_generation_index_from_lifecycle_records_skips_invalid_rows() -> None:
    class _Bad:
        agent_id = "agent-c"
        generation_index = -1

    assert generation_index_from_lifecycle_records((_Bad(),)) is None
