"""Runner result exports owner-ordered naming and symbolic ledgers."""

from __future__ import annotations

import pytest

from agents.cognition.semantic_naming import empty_terminology_ledger
from agents.cognition.symbolic_language import SymbolicLedger
from agents.models import AgentId
from simulation.models import RunId
from simulation.runner_models import (
    CognitionCounters,
    RunnerStopReasonCode,
    SimulationRunnerResult,
)


def _result(**kwargs: object) -> SimulationRunnerResult:
    return SimulationRunnerResult(
        run_id=RunId("run-ledger-export"),
        ticks_committed=1,
        stop_reason=RunnerStopReasonCode.MAX_TICKS,
        attempt_receipts=(),
        cognition_counters=CognitionCounters(),
        **kwargs,
    )


def test_result_accepts_owner_ordered_ledger_tuples() -> None:
    owner = AgentId("owner-a")
    naming = empty_terminology_ledger(owner)
    symbolic = SymbolicLedger(owner_id=owner)
    result = _result(terminology_ledgers=(naming,), symbolic_ledgers=(symbolic,))
    assert result.terminology_ledgers == (naming,)
    assert result.symbolic_ledgers == (symbolic,)


def test_disabled_export_is_empty_and_re_export_is_idempotent() -> None:
    result = _result()
    assert result.terminology_ledgers == ()
    assert result.symbolic_ledgers == ()
    again = _result(
        terminology_ledgers=result.terminology_ledgers,
        symbolic_ledgers=result.symbolic_ledgers,
    )
    assert again.terminology_ledgers == result.terminology_ledgers


def test_result_rejects_unordered_and_foreign_ledger_items() -> None:
    with pytest.raises(TypeError, match="must be ordered"):
        _result(terminology_ledgers=frozenset())
    with pytest.raises(TypeError, match="invalid_item"):
        _result(terminology_ledgers=("not-a-ledger",))
    with pytest.raises(TypeError, match="invalid_item"):
        _result(symbolic_ledgers=("not-a-ledger",))
