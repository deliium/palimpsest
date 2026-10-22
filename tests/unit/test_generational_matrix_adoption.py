"""Matrix resume adoption for completed generational archives."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from experiments.generational_artifacts import (
    HistoricalBoundaryReference,
    SnapshotReference,
)
from experiments.matrix_expand import expand_matrix
from experiments.matrix_manifest import FilesystemMatrixManifestStore
from experiments.matrix_runner import MatrixBatchDependencies, MatrixBatchRunner
from research_runner.generational_composition import open_generational_archive
from simulation.runner import SimulationRunner
from tests.unit.test_generational_matrix_schema import _base, _matrix


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


async def _write_archive(root: Path, config, run_id: str) -> None:
    session = open_generational_archive(
        config=config,
        run_id=__import__("simulation.models", fromlist=["RunId"]).RunId(run_id),
        root=root,
        code_revision="abc123",
        source_clean=True,
    )
    factories = session.dependencies(
        reader=_Reader(),
        cadence_ticks=None,
        sample_on_generation_change=True,
    )
    runner = await SimulationRunner.from_config(
        config,
        run_id=__import__("simulation.models", fromlist=["RunId"]).RunId(run_id),
        factories=factories,
    )
    try:
        result = await runner.run()
        session.write_completion(result)
    finally:
        await runner.aclose()


@pytest.mark.asyncio
async def test_matrix_resume_adopts_completed_archive_without_execution(
    tmp_path: Path,
) -> None:
    base = _base()
    spec = _matrix(base)
    definition, cells = expand_matrix(spec)
    adopted_cell = cells[0]
    condition = next(
        item
        for item in definition.conditions
        if item.condition_id == adopted_cell.condition_id
    )
    archive_config = replace(condition.runner_config, seed=adopted_cell.seed)
    archive_root = tmp_path / "archives"
    await _write_archive(archive_root, archive_config, adopted_cell.cell_id)

    store = FilesystemMatrixManifestStore(tmp_path / "matrix")
    runner = MatrixBatchRunner(
        MatrixBatchDependencies(
            package_version="0.0.0-test",
            code_revision="abc123",
            archive_root=archive_root,
        )
    )
    result = await runner.run(spec, store)
    assert result.skipped_valid >= 1
    record = store.get_cell(adopted_cell.cell_id)
    assert record.state.value == "skipped_valid"
    assert store.has_valid_completion(
        adopted_cell,
        matrix_fingerprint=__import__(
            "experiments.matrix_models", fromlist=["matrix_spec_fingerprint"]
        ).matrix_spec_fingerprint(spec),
    )


@pytest.mark.asyncio
async def test_incomplete_durable_origin_is_not_retried(tmp_path: Path) -> None:
    from simulation.runner_models import RunnerPersistenceSpec

    base = replace(
        _base(),
        persistence=RunnerPersistenceSpec(durable=True),
    )
    spec = _matrix(base)
    store = FilesystemMatrixManifestStore(tmp_path / "matrix")
    runner = MatrixBatchRunner(
        MatrixBatchDependencies(
            package_version="0.0.0-test",
            code_revision="abc123",
            archive_root=tmp_path / "archives",
            durable_origin_exists=lambda run_id: True,
        )
    )
    result = await runner.run(spec, store)
    assert result.failed >= 1
    codes = {
        store.get_cell(cell.cell_id).last_error_code for cell in result.cells
    }
    assert "durable_origin_rerun_unsupported" in codes
