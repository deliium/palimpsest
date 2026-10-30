"""Generational archive composition over a real runner."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from experiments.generational_artifacts import (
    HistoricalBoundaryReference,
    SnapshotReference,
)
from research_runner.generational_composition import open_generational_archive
from simulation.clock import Tick
from simulation.models import RunId
from simulation.persistence import (
    RunCreateRequest,
    RunManifest,
    SnapshotId,
    TickAppendRequest,
    TickCommit,
    WorldSnapshot,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import SimulationRunnerConfig
from tests.unit.test_generational_population_runner import _v55_config
from tests.unit.test_persistence_serialization import _commit, _manifest, _snapshot
from world.events import WorldEvent
from world.identifiers import WorldRevision


class _Reader:
    async def reference(
        self, run_id: str, boundary_tick: int
    ) -> HistoricalBoundaryReference:
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


async def _completed_archive(tmp_path: Path) -> tuple[SimulationRunnerConfig, RunId]:
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
    async def get_run(self, run_id: RunId) -> RunManifest:
        return _manifest()

    async def create_run(self, request: RunCreateRequest) -> RunManifest:
        raise AssertionError("historical reader must not create runs")


class _Journal:
    def __init__(self, commit: TickCommit | None = None) -> None:
        self.commit = commit

    async def get_tick_commit(self, run_id: RunId, tick: Tick) -> TickCommit | None:
        return self.commit

    async def append_tick(self, request: TickAppendRequest) -> TickCommit:
        raise AssertionError("historical reader must not append ticks")

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
        limit: int,
        offset: int,
    ) -> tuple[WorldEvent, ...]:
        raise AssertionError("historical reader must not list events")

    async def list_tick_commits(
        self, run_id: RunId, *, from_tick: Tick, to_tick: Tick | None
    ) -> tuple[TickCommit, ...]:
        raise AssertionError("historical reader must not list commits")


def _boundary_snapshot(*, next_tick: int = 4) -> WorldSnapshot:
    return replace(
        _snapshot(integrity="b" * 64),
        snapshot_id=SnapshotId("snap-4"),
        next_tick=Tick(next_tick),
        revision=WorldRevision(4),
    )


class _Snaps:
    def __init__(self, snapshot: WorldSnapshot | None = None) -> None:
        self.snapshot = snapshot

    async def get_latest_at_or_before(
        self, run_id: RunId, tick: Tick
    ) -> WorldSnapshot | None:
        return self.snapshot

    async def get_snapshot(self, snapshot_id: SnapshotId) -> WorldSnapshot | None:
        raise AssertionError("historical reader must use boundary lookup")


@pytest.mark.asyncio
async def test_postgres_boundary_reader_reads_exact_commit_and_snapshot() -> None:
    from research_runner.generational_composition import (
        PostgresHistoricalBoundaryReader,
    )

    reader = PostgresHistoricalBoundaryReader(
        runs=_Runs(),
        journal=_Journal(_commit(tick=3, predecessor=None, commit="a" * 64)),
        snapshots=_Snaps(_boundary_snapshot()),
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
            runs=_Runs(), journal=_Journal(None), snapshots=_Snaps(_boundary_snapshot())
        ).reference("run-1", 4)

    with pytest.raises(ValueError, match="historical_snapshot_after_boundary"):
        await PostgresHistoricalBoundaryReader(
            runs=_Runs(),
            journal=_Journal(_commit(tick=3, predecessor=None, commit="a" * 64)),
            snapshots=_Snaps(_boundary_snapshot(next_tick=5)),
        ).reference("run-1", 4)


@pytest.mark.asyncio
async def test_community_provider_builds_sample_and_criterion() -> None:
    from experiments.persistence import (
        PersistedAnalysisSnapshot,
        PersistedRegionalContext,
        PersistedRegionalInitialPlacement,
        PersistedRegionalLocation,
    )
    from research_runner.generational_composition import (
        PostgresCommunitySampleProvider,
    )
    from simulation.generational_models import (
        ExperimentCriterionSpec,
        GenerationalBoundary,
        PopulationProgress,
    )

    snapshot = PersistedAnalysisSnapshot(
        experiment_id="",
        run_id="run-community-1",
        owner_id="agent-1",
        traces=(),
        reconstructions=(),
        derivation_edges=(),
        events=(),
        regional_context=PersistedRegionalContext(
            region_ids=("region-1",),
            known_location_ids=("loc-1",),
            locations=(PersistedRegionalLocation("loc-1", "region-1"),),
            initial_placements=(
                PersistedRegionalInitialPlacement("body-1", "loc-1", True),
            ),
            owner_ids=("agent-1",),
            residence_min_ticks=1,
        ),
        objective_complete_through_boundary=5,
    )

    class _Loader:
        async def load(self, *, run_id: str, owner_id: str) -> object:
            assert run_id == "run-community-1"
            assert owner_id == "agent-1"
            return snapshot

    provider = PostgresCommunitySampleProvider(
        loader=_Loader(),
        run_id="run-community-1",
        owner_id="agent-1",
        window_ticks=5,
    )
    boundary = GenerationalBoundary(
        progress=PopulationProgress(
            boundary_tick=5,
            living_population=1,
            total_admitted=1,
            total_deaths=0,
            max_generation_index_seen=0,
        ),
        objective_revision=5,
        last_completed_tick=4,
    )
    payload = await provider.sample(boundary)
    assert payload is not None
    assert isinstance(payload, dict)
    assert payload["living_count"] == 1
    assert payload["coverage_complete"] is True

    factory = provider.criterion_factory()
    criterion = factory(
        ExperimentCriterionSpec(
            criterion_id="community_count_at_least",
            version="1",
            params={"count": 1, "window_ticks": 5},
        )
    )
    from experiments.generational_sampling import CommunityCountCriterion

    assert isinstance(criterion, CommunityCountCriterion)
    decision = await criterion.evaluate(boundary)
    assert decision.measurements["coverage_complete"] is True
    assert decision.measurements["candidate_community_count"] == 0
