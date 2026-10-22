"""Generational archive composition over a real runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from experiments.generational_artifacts import (
    HistoricalBoundaryReference,
    SnapshotReference,
)
from research_runner.generational_composition import open_generational_archive
from simulation.models import RunId
from simulation.runner import SimulationRunner
from tests.unit.test_generational_population_runner import _v55_config


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
