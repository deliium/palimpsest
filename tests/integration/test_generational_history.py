"""Durable generational history references and read-only replay parity."""

from __future__ import annotations

from dataclasses import replace

import pytest
from tests.benchmarks.harness import durable_factories, unique_run_id
from tests.unit.test_generational_population_runner import _v55_config

from experiments.generational_artifacts import (
    decode_generational_document,
)
from infrastructure.database import DatabaseResources
from persistence import (
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from research_runner.generational_composition import (
    PostgresHistoricalBoundaryReader,
    open_generational_archive,
)
from simulation.clock import Tick
from simulation.persistence import ReplayRequest, ReplayStatus
from simulation.replay import ReplayService
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RunnerCheckpointPolicy,
    RunnerPersistenceSpec,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_durable_history_refs_match_replay_at_boundaries(
    database_resources: DatabaseResources,
    tmp_path,
) -> None:
    base = _v55_config()
    generational = base.generational_run
    assert generational is not None
    config = replace(
        base,
        persistence=RunnerPersistenceSpec(
            durable=True,
            checkpoint=RunnerCheckpointPolicy(enabled=True, cadence_ticks=2),
        ),
        stop_policy=replace(base.stop_policy, max_ticks=4),
        generational_run=replace(
            generational,
            historical_checkpoint_cadence_ticks=2,
            max_generation_index=None,
        ),
    )
    run_id = unique_run_id("genhist")
    session = open_generational_archive(
        config=config,
        run_id=run_id,
        root=tmp_path,
        code_revision="abc123",
        source_clean=True,
    )
    session_factory = database_resources.session_factory
    runs = create_run_repository(session_factory)
    journal = create_tick_journal_repository(session_factory)
    snapshots = create_snapshot_repository(session_factory)
    reader = PostgresHistoricalBoundaryReader(
        runs=runs, journal=journal, snapshots=snapshots
    )
    factories = session.dependencies(
        reader=reader,
        cadence_ticks=2,
        sample_on_generation_change=True,
        base=durable_factories(session_factory),
    )
    async with await SimulationRunner.from_config(
        config, run_id=run_id, factories=factories
    ) as runner:
        result = await runner.run()
    assert result.stop_evidence is not None

    history_refs = session.store.history_refs()
    assert history_refs
    replay = ReplayService(runs, journal, snapshots)
    for ref in history_refs:
        payload = (tmp_path / ref["path"]).read_bytes()
        history = decode_generational_document(
            payload, schema_version="generational-history-v1"
        )
        boundary = int(history["boundary_tick"])
        outcome = await replay.replay(
            ReplayRequest(
                run_id=run_id,
                target_tick=Tick(boundary),
                population_lifecycle=config.population_lifecycle,
            )
        )
        assert outcome.result.status is ReplayStatus.OK
        assert outcome.engine is not None
        assert outcome.engine.tick.value == boundary
        reference = await reader.reference(run_id.value, boundary)
        assert reference.objective_commit_hash == history["objective_commit_hash"]
        assert (
            reference.snapshot_ref.snapshot_id
            == history["snapshot_ref"]["snapshot_id"]
        )

    # Non-cadence lookup may use the nearest checkpoint while folding to B.
    nearest = await reader.reference(run_id.value, 3)
    assert nearest.snapshot_ref.next_tick <= 3
    folded = await replay.replay(
        ReplayRequest(
            run_id=run_id,
            target_tick=Tick(3),
            population_lifecycle=config.population_lifecycle,
        )
    )
    assert folded.result.status is ReplayStatus.OK
    assert folded.engine is not None
    assert folded.engine.tick.value == 3
