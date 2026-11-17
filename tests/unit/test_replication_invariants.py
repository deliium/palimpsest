# mypy: ignore-errors
"""V4-28 depth invariants: no new authority, truth, or capability."""

from __future__ import annotations

import dataclasses

import pytest

from agents.cognition import (
    REPLICATION_POLICY_VERSION,
    ReplicationLedger,
    empty_replication_ledger,
)
from agents.models import AgentId
from simulation.runner_models import SimulationRunnerResult

pytestmark = pytest.mark.unit


def test_replication_ledger_has_no_truth_or_world_authority_fields() -> None:
    names = {field.name for field in dataclasses.fields(ReplicationLedger)}
    for forbidden in (
        "truth",
        "proven",
        "verified",
        "consensus",
        "majority",
        "world_state",
        "action_request",
        "authority_token",
        "objective_probability",
    ):
        assert forbidden not in names
    assert REPLICATION_POLICY_VERSION == "scientific-replication.v1"


def test_runner_result_replication_ledgers_are_ordered_and_owner_unique() -> None:
    owner = AgentId("owner-1")
    first = empty_replication_ledger(owner)
    result = SimulationRunnerResult(
        run_id=__import__("simulation.models", fromlist=["RunId"]).RunId("run-1"),
        ticks_committed=0,
        stop_reason=__import__(
            "simulation.runner_models", fromlist=["RunnerStopReasonCode"]
        ).RunnerStopReasonCode.MAX_TICKS,
        attempt_receipts=(),
        replication_ledgers=(first,),
    )
    assert result.replication_ledgers == (first,)
    with pytest.raises(TypeError):
        SimulationRunnerResult(
            run_id=result.run_id,
            ticks_committed=0,
            stop_reason=result.stop_reason,
            attempt_receipts=(),
            replication_ledgers=(first, first),
        )


def test_replication_does_not_add_a_capability_flag() -> None:
    from simulation.v4_architecture import V4_CONTEXTS

    names = {context.context_id.value for context in V4_CONTEXTS}
    assert "scientific_replication" not in names
    assert "science" in names
    flags = {
        context.capability_flag
        for context in V4_CONTEXTS
        if context.capability_flag is not None
    }
    assert "scientific_replication" not in flags
