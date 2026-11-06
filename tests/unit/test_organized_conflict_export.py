# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

import pytest

from agents.cognition.organized_conflict import (
    ConflictLedger,
    empty_organized_conflict_ledger,
    export_organized_conflict_ledger,
)
from agents.models import AgentId
from simulation.models import RunId
from simulation.runner_models import RunnerStopReasonCode, SimulationRunnerResult


def test_export_is_owner_scoped_and_deterministic() -> None:
    owner = AgentId("agent-owner")
    ledger = empty_organized_conflict_ledger(owner, tick=3)
    exported = export_organized_conflict_ledger(ledger)
    assert exported == ledger
    assert exported.owner_id == owner


def test_runner_result_rejects_foreign_ledger_type() -> None:
    with pytest.raises(TypeError):
        SimulationRunnerResult(
            run_id=RunId("run-conflict-export"),
            ticks_committed=1,
            stop_reason=RunnerStopReasonCode.MAX_TICKS,
            attempt_receipts=(),
            organized_conflict_ledgers=(object(),),
        )


def test_runner_result_accepts_owner_sorted_ledgers() -> None:
    first = empty_organized_conflict_ledger(AgentId("agent-a"), tick=1)
    second = empty_organized_conflict_ledger(AgentId("agent-b"), tick=1)
    result = SimulationRunnerResult(
        run_id=RunId("run-conflict-export"),
        ticks_committed=1,
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        attempt_receipts=(),
        organized_conflict_ledgers=(first, second),
    )
    assert result.organized_conflict_ledgers == (first, second)
    assert all(
        type(ledger) is ConflictLedger for ledger in result.organized_conflict_ledgers
    )
