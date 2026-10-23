"""Boundary-qualified cultural evidence capture."""

from __future__ import annotations

import pytest

from experiments.cultural_evidence import CulturalEvidenceRecorder
from experiments.path_dependence_evidence import (
    CAPTURE_LIMIT_CODE,
    PathDependenceEvidenceRecorder,
    collect_path_dependence_boundary,
)
from experiments.path_dependence_models import OutcomeWindow
from experiments.path_dependence_scenario import historical_contingency_scenario
from simulation.branch_service import rematerialize_snapshot
from simulation.clock import Tick
from simulation.cultural_evidence import CulturalBoundaryExport
from simulation.engine import WorldEngine
from simulation.models import RunId
from simulation.persistence import SnapshotId
from simulation.runner import RunnerDependencyFactories, SimulationRunner

pytestmark = pytest.mark.unit


def _frame(tick: int) -> CulturalBoundaryExport:
    return CulturalBoundaryExport(run_id="run", boundary_tick=tick, owners=())


def test_baseline_rejects_earlier_and_duplicate_initialization() -> None:
    recorder = CulturalEvidenceRecorder()
    recorder.start_at_boundary(4)
    with pytest.raises(ValueError, match="cultural_evidence_baseline_already_set"):
        recorder.start_at_boundary(4)
    with pytest.raises(ValueError, match="cultural_evidence_before_baseline"):
        recorder.capture(_frame(3))
    recorder.capture(_frame(4))
    recorder.capture(_frame(4))
    assert [frame.boundary_tick for frame in recorder.result().frames] == [4]
    with pytest.raises(ValueError, match="cultural_evidence_baseline_after_capture"):
        recorder.start_at_boundary(5)


def test_no_baseline_preserves_default_tick_zero_behavior() -> None:
    recorder = CulturalEvidenceRecorder()
    recorder.capture(_frame(0))
    recorder.capture(_frame(1))
    assert [frame.boundary_tick for frame in recorder.result().frames] == [0, 1]


@pytest.mark.asyncio
async def test_collector_records_exact_requested_boundary_and_evidence() -> None:
    spec = historical_contingency_scenario(profile="smoke")
    runner = await SimulationRunner.from_config(
        spec.base,
        run_id=RunId("pd-evidence-recorder"),
        factories=RunnerDependencyFactories(),
    )
    try:
        recorder = PathDependenceEvidenceRecorder(
            requested_boundaries=(0, 4, 8), max_rows=1_000_000
        )
        await runner.initialize_finalized_boundary()
        await collect_path_dependence_boundary(runner, 0, recorder)
        for _ in range(8):
            await runner.run_tick()
        await collect_path_dependence_boundary(runner, 8, recorder)
        assert [item.boundary_tick.value for item in recorder.result().boundaries] == [
            0,
            8,
        ]
        window = OutcomeWindow("post", Tick(4), Tick(4), Tick(8))
        evidence = recorder.analysis_evidence(window)
        assert evidence.action_rows
        assert evidence.relationship_rows
        assert evidence.resource_holdings
        assert set(evidence.living_agent_ids) <= {
            owner.owner_id.value for owner in recorder.result().boundaries[-1].owners
        }
        assert evidence.cultural_inputs is not None
        boundary = recorder.result().boundaries[-1]
        limited = PathDependenceEvidenceRecorder(max_rows=1)
        assert limited.capture(boundary) is False
        assert CAPTURE_LIMIT_CODE in limited.result().gaps
        missing = recorder.analysis_evidence(
            OutcomeWindow("later", Tick(4), Tick(4), Tick(12))
        )
        assert missing.run_id == "path-dependence-evidence"
        assert missing.input_revision == "missing-endpoint"
    finally:
        await runner.aclose()


def test_recorder_honours_requested_cadence() -> None:
    recorder = PathDependenceEvidenceRecorder(cadence=2)
    assert recorder.accepts(2) is True
    assert recorder.accepts(3) is False


@pytest.mark.asyncio
async def test_restored_child_publishes_exactly_one_f_baseline_and_next() -> None:
    spec = historical_contingency_scenario(profile="smoke")
    parent = await SimulationRunner.from_config(
        spec.base,
        run_id=RunId("pd-boundary-parent"),
        factories=RunnerDependencyFactories(),
    )
    try:
        await parent.initialize_finalized_boundary()
        for _ in range(4):
            await parent.run_tick()
        checkpoint = await parent.capture_fork_checkpoint()
    finally:
        await parent.aclose()
    child_run = RunId("pd-boundary-child")
    engine = WorldEngine.restore_from_snapshot(
        rematerialize_snapshot(
            checkpoint.snapshot,
            child_run_id=child_run,
            snapshot_id=SnapshotId(f"child-{child_run.value}"),
            predecessor_commit_hash=None,
            next_tick=Tick(4),
        ),
        population_lifecycle=checkpoint.config.population_lifecycle,
        new_agent_initialization=checkpoint.config.new_agent_initialization,
        kinship_spec=checkpoint.config.kinship,
        environmental_dynamics=checkpoint.config.environmental_dynamics,
        artifacts_enabled=checkpoint.config.artifacts_enabled,
    )
    recorder = CulturalEvidenceRecorder()
    recorder.start_at_boundary(4)
    child = await SimulationRunner.from_fork_checkpoint(
        checkpoint.config,
        run_id=child_run,
        checkpoint=checkpoint,
        restored_engine=engine,
        factories=RunnerDependencyFactories(),
        cultural_sink=recorder,
    )
    try:
        assert [frame.boundary_tick for frame in recorder.result().frames] == [4]
        await child.run_tick()
        assert [frame.boundary_tick for frame in recorder.result().frames] == [4, 5]
    finally:
        await child.aclose()
