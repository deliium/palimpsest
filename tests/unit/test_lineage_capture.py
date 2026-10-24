"""Finalized-boundary lineage capture and fork baseline behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.models import AgentId
from persistence.lineage_filesystem import (
    create_lineage_publisher,
    create_lineage_reader,
)
from simulation.branch_service import rematerialize_snapshot
from simulation.engine import WorldEngine
from simulation.lineage_capture import LineageCaptureOptions, LineageCaptureSession
from simulation.lineage_ports import LineageReadBudget
from simulation.models import RunId, StochasticIdentity
from simulation.persistence import SnapshotId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V27,
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_kinship_spec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _config(*, max_ticks: int = 2) -> SimulationRunnerConfig:
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    parent = AgentId("agent-a")
    child = AgentId("agent-b")
    return SimulationRunnerConfig(
        seed=37,
        schema_version=RUNNER_SCHEMA_VERSION_V27,
        v3_capability_flags=V3CapabilityFlags(kinship_inheritance=True),
        stochastic_identity=StochasticIdentity("capture-e2e"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-capture"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=parent,
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=parent),
            ),
            AgentRunnerSpec(
                agent_id=child,
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=child),
            ),
        ),
        kinship=example_kinship_spec(
            parent_agent_id="agent-a",
            child_agent_id="agent-b",
        ),
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
    )


def _session(tmp_path: Path) -> LineageCaptureSession:
    return LineageCaptureSession(
        reader=create_lineage_reader(tmp_path),
        publisher=create_lineage_publisher(tmp_path),
    )


@pytest.mark.asyncio
async def test_capture_boundary_zero_one_and_retry(tmp_path: Path) -> None:
    session = _session(tmp_path)
    runner = await SimulationRunner.from_config(_config(), run_id=RunId("run-capture"))
    runner.set_lineage_boundary_sink(session)
    try:
        await runner.initialize_finalized_boundary()
        assert session.status.last_boundary == 0
        assert any(receipt.boundary_tick == 0 for receipt in session.receipts)
        before = len(session.receipts)
        await runner.initialize_finalized_boundary()
        assert len(session.receipts) == before
        await runner.run_tick()
        assert any(receipt.boundary_tick == 1 for receipt in session.receipts)
        async with create_lineage_reader(tmp_path).open_read(
            run_id=RunId("run-capture"), budget=LineageReadBudget.for_query()
        ) as read:
            from simulation.lineage_identity import LineageEvidenceClass, LineageFamily
            from simulation.lineage_models import LineageScope

            scope = LineageScope(
                run_id=RunId("run-capture"),
                family=LineageFamily.GENEALOGY,
                evidence_class=LineageEvidenceClass.OBJECTIVE,
            )
            snapshot = await read.resolve_snapshot(scope, 1)
            page = await read.node_page(snapshot, None, 10)
            assert len(page.rows) == 2
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_off_path_and_failing_capture_do_not_change_science(
    tmp_path: Path,
) -> None:
    async with await SimulationRunner.from_config(
        _config(), run_id=RunId("run-off")
    ) as off_path:
        baseline = await off_path.run()

    class _FailingSink:
        def __init__(self) -> None:
            self.calls = 0

        async def capture(self, frame: object) -> None:
            self.calls += 1
            raise RuntimeError("storage failed")

    failing = _FailingSink()
    runner = await SimulationRunner.from_config(_config(), run_id=RunId("run-failing"))
    runner.set_lineage_boundary_sink(failing)
    try:
        result = await runner.run()
    finally:
        await runner.aclose()
    assert failing.calls >= 1
    assert result.stop_reason == baseline.stop_reason
    assert len(result.finalized_tick_receipts) == len(baseline.finalized_tick_receipts)
    assert runner._lineage_capture_failed is True


@pytest.mark.asyncio
async def test_off_path_creates_no_artifacts(tmp_path: Path) -> None:
    async with await SimulationRunner.from_config(
        _config(), run_id=RunId("run-no-capture")
    ) as runner:
        await runner.run()
    assert not any(tmp_path.iterdir())  # noqa: ASYNC240


@pytest.mark.asyncio
async def test_capture_options_skip_boundaries_explicitly(tmp_path: Path) -> None:
    session = LineageCaptureSession(
        reader=create_lineage_reader(tmp_path),
        publisher=create_lineage_publisher(tmp_path),
        options=LineageCaptureOptions(cadence=2),
    )
    runner = await SimulationRunner.from_config(_config(), run_id=RunId("run-cadence"))
    runner.set_lineage_boundary_sink(session)
    try:
        await runner.initialize_finalized_boundary()
        assert session.status.last_boundary == 0
        await runner.run_tick()
        assert all(receipt.boundary_tick != 1 for receipt in session.receipts)
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_fork_installs_lineage_baseline_after_restore(tmp_path: Path) -> None:
    config = _config()
    parent = await SimulationRunner.from_config(config, run_id=RunId("parent-run"))
    try:
        await parent.initialize_finalized_boundary()
        await parent.run_tick()
        checkpoint = await parent.capture_fork_checkpoint()
        child_run = RunId("child-run")
        child_snapshot = rematerialize_snapshot(
            checkpoint.snapshot,
            child_run_id=child_run,
            snapshot_id=SnapshotId("child-lineage-snapshot"),
            predecessor_commit_hash=None,
            next_tick=checkpoint.boundary_tick,
        )
        child_engine = WorldEngine.restore_from_snapshot(
            child_snapshot,
            population_lifecycle=config.population_lifecycle,
            new_agent_initialization=config.new_agent_initialization,
            kinship_spec=config.kinship,
            environmental_dynamics=config.environmental_dynamics,
            artifacts_enabled=config.artifacts_enabled,
        )
        session = _session(tmp_path)
        child = await SimulationRunner.from_fork_checkpoint(
            config,
            run_id=child_run,
            checkpoint=checkpoint,
            restored_engine=child_engine,
            lineage_sink=session,
        )
        try:
            assert checkpoint.boundary_tick.value == 1
            assert session.receipts
            assert all(
                receipt.boundary_tick == checkpoint.boundary_tick.value
                for receipt in session.receipts
            )
            assert all(
                receipt.scope.run_id == child_run for receipt in session.receipts
            )
        finally:
            await child.aclose()
    finally:
        await parent.aclose()


@pytest.mark.asyncio
async def test_repeated_boundary_with_different_data_fails_capture(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    session = _session(tmp_path)
    runner = await SimulationRunner.from_config(
        _config(), run_id=RunId("run-retry-conflict")
    )
    runner.set_lineage_boundary_sink(session)
    try:
        await runner.initialize_finalized_boundary()
        assert session.receipts
        from simulation.lineage_ports import LineageBoundaryFrame

        frames = runner._build_lineage_frames(0)
        frame = next(
            item
            for item in frames
            if isinstance(item, LineageBoundaryFrame) and item.nodes
        )
        conflicting = replace(frame, nodes=frame.nodes[:1])
        result = await session.capture(conflicting)
        assert result is None
        assert session.status.failed is True
        assert session.status.failure_code == "lineage_publication_conflict"
    finally:
        await runner.aclose()
