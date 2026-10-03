"""Unit proofs for runtime checkpoint rebase onto child run ids."""

from __future__ import annotations

import pytest

from simulation.models import RunId
from simulation.run_control import RunnerRuntimeCheckpoint, rebase_runtime_checkpoint
from simulation.runner_models import CognitionCounters

pytestmark = pytest.mark.unit


def _checkpoint(run_id: str) -> RunnerRuntimeCheckpoint:
    return RunnerRuntimeCheckpoint(
        run_id=RunId(run_id),
        ticks_committed=3,
        engine_tick=3,
        engine_revision=3,
        runtime_states=(),
        finalized_tick_receipts=(),
        goal_transition_receipts=(),
        cognition_counters=CognitionCounters(),
    )


class _StubRunner:
    def __init__(self, run_id: RunId) -> None:
        self._run_id = run_id
        self.applied: RunnerRuntimeCheckpoint | None = None

    def apply_runtime_checkpoint(self, checkpoint: RunnerRuntimeCheckpoint) -> None:
        if checkpoint.run_id != self._run_id:
            raise ValueError("run_id mismatch")
        self.applied = checkpoint


def test_rebase_rewrites_child_run_id_without_mutating_parent() -> None:
    parent = _checkpoint("parent-run")
    child = rebase_runtime_checkpoint(parent, RunId("child-run"))
    assert parent.run_id == RunId("parent-run")
    assert child.run_id == RunId("child-run")
    assert child.ticks_committed == parent.ticks_committed

    child_runner = _StubRunner(RunId("child-run"))
    child_runner.apply_runtime_checkpoint(child)
    assert child_runner.applied is child

    parent_runner = _StubRunner(RunId("child-run"))
    with pytest.raises(ValueError, match="run_id mismatch"):
        parent_runner.apply_runtime_checkpoint(parent)
