"""Generational archive composition over a real runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from experiments.generational_artifacts import (
    HistoricalBoundaryReference,
    SnapshotReference,
)
from research_runner.generational_composition import open_generational_archive
from simulation.clock import Tick
from simulation.models import RunId
from simulation.runner import SimulationRunner
from tests.unit.test_generational_population_runner import _v55_config
from world.identifiers import WorldRevision


class _Reader:
    async def reference(self, run_id: str, boundary_tick: int):
        return HistoricalBoundaryReference(
            revision=boundary_tick,
            objective_commit_hash=f"{boundary_tick:064d}",
            snapshot_ref=SnapshotReference(
                snapshot_id=f"snap-{boundary_tick}",
                integrity_hash=f"{boundary_tick:064d}",
                next_tick=boundary_tick,
            ),
        )


@pytest.mark.asyncio
async def test_real_runner_writes_terminal_history_and_completion(
    tmp_path: Path,
) -> None:
    config = _v55_config()
    run_id = RunId("run-compose-1")
    session = open_generational_archive(
        config=config,
        run_id=run_id,
        root=tmp_path,
        code_revision="abc123",
        source_clean=True,
    )
    factories = session.dependencies(
        reader=_Reader(),
        cadence_ticks=None,
        sample_on_generation_change=True,
    )
    runner = await SimulationRunner.from_config(
        config, run_id=run_id, factories=factories
    )
    try:
        result = await runner.run()
        assert result.stop_evidence is not None
        assert session.store.history_refs()
        completion = session.write_completion(result)
        assert completion
        assert session.store.read_completion()["history_refs"]
    finally:
        await runner.aclose()


async def _completed_archive(tmp_path: Path):
    from research_runner.generational_composition import open_generational_archive

    config = _v55_config()
    run_id = RunId("run-adopt-1")
    session = open_generational_archive(
        config=config,
        run_id=run_id,
        root=tmp_path,
        code_revision="abc123",
        source_clean=True,
    )
    factories = session.dependencies(
        reader=_Reader(),
        cadence_ticks=None,
        sample_on_generation_change=True,
    )
    runner = await SimulationRunner.from_config(
        config, run_id=run_id, factories=factories
    )
    try:
        result = await runner.run()
        session.write_completion(result)
    finally:
        await runner.aclose()
    return config, run_id


@pytest.mark.asyncio
async def test_completed_archive_is_verified_for_adoption(tmp_path: Path) -> None:
    from experiments.generational_adoption import verify_completed_archive

    config, run_id = await _completed_archive(tmp_path)
    verified = verify_completed_archive(
        root=tmp_path,
        run_id=run_id,
        expected_config=config,
        expected_code_revision="abc123",
    )
    assert verified is not None
    assert verified.run_id == run_id


@pytest.mark.asyncio
async def test_archive_adoption_rejects_identity_drift(tmp_path: Path) -> None:
    from experiments.generational_adoption import verify_completed_archive

    config, run_id = await _completed_archive(tmp_path)
    assert (
        verify_completed_archive(
            root=tmp_path,
            run_id=run_id,
            expected_config=config,
            expected_code_revision="different",
        )
        is None
    )


@pytest.mark.asyncio
async def test_archive_adoption_rejects_incomplete_output(tmp_path: Path) -> None:
    from experiments.generational_adoption import verify_completed_archive

    config, run_id = await _completed_archive(tmp_path)
    completion = tmp_path / run_id.value / "single" / "completion.json"
    completion.unlink()
    assert (
        verify_completed_archive(
            root=tmp_path,
            run_id=run_id,
            expected_config=config,
        )
        is None
    )


class _Runs:
    async def get_run(self, run_id):
        return object()


class _Commit:
    resulting_tick = Tick(4)
    resulting_revision = WorldRevision(4)
    commit_hash = type("H", (), {"value": "a" * 64})()


class _Journal:
    def __init__(self, commit=None) -> None:
        self.commit = commit

    async def get_tick_commit(self, run_id, tick):
        return self.commit


class _Snap:
    next_tick = Tick(4)
    snapshot_id = type("S", (), {"value": "snap-4"})()
    integrity_hash = type("I", (), {"value": "b" * 64})()


class _Snaps:
    def __init__(self, snapshot=None) -> None:
        self.snapshot = snapshot

    async def get_latest_at_or_before(self, run_id, tick):
        return self.snapshot


@pytest.mark.asyncio
async def test_postgres_boundary_reader_reads_exact_commit_and_snapshot() -> None:
    from research_runner.generational_composition import (
        PostgresHistoricalBoundaryReader,
    )

    reader = PostgresHistoricalBoundaryReader(
        runs=_Runs(), journal=_Journal(_Commit()), snapshots=_Snaps(_Snap())
    )
    reference = await reader.reference("run-1", 4)
    assert reference.revision == 4
    assert reference.objective_commit_hash == "a" * 64
    assert reference.snapshot_ref.next_tick == 4


@pytest.mark.asyncio
async def test_postgres_boundary_reader_rejects_bad_evidence() -> None:
    from research_runner.generational_composition import (
        PostgresHistoricalBoundaryReader,
    )

    with pytest.raises(ValueError, match="historical_commit_missing"):
        await PostgresHistoricalBoundaryReader(
            runs=_Runs(), journal=_Journal(None), snapshots=_Snaps(_Snap())
        ).reference("run-1", 4)

    class _LateSnap(_Snap):
        next_tick = Tick(5)

    with pytest.raises(ValueError, match="historical_snapshot_after_boundary"):
        await PostgresHistoricalBoundaryReader(
            runs=_Runs(),
            journal=_Journal(_Commit()),
            snapshots=_Snaps(_LateSnap()),
        ).reference("run-1", 4)
