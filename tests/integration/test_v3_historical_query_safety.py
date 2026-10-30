"""Historical query safety across genuine generational evidence.

Covers death/checkpoint/end boundaries, long-dead owner reads after runner
teardown, bounded objective/subjective pages, and exact replay identity. The
synthetic high-volume lane lives separately in the benchmark module.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from tests.benchmarks.harness import durable_factories, unique_run_id
from tests.unit.test_generational_population_runner import _v55_config

from experiments.generational_artifacts import decode_generational_document
from infrastructure.database import DatabaseResources
from persistence import (
    create_analysis_evidence_loader,
    create_objective_evidence_loader,
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from research_runner.generational_composition import (
    PostgresHistoricalBoundaryReader,
    open_generational_archive,
)
from simulation.clock import Tick
from simulation.inspection import EventKeysetCursor
from simulation.persistence import ReplayRequest, ReplayStatus
from simulation.replay import ReplayService
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RunnerCheckpointPolicy,
    RunnerPersistenceSpec,
    SimulationRunnerConfig,
)
from world.events import Died, WorldEvent

pytestmark = pytest.mark.integration

_MAX_TICKS = 10
_CHECKPOINT_CADENCE = 2
_LIFESPAN_TICKS = 6


def _historical_config() -> SimulationRunnerConfig:
    base = _v55_config()
    generational = base.generational_run
    lifecycle = base.population_lifecycle
    assert generational is not None
    assert lifecycle is not None
    return replace(
        base,
        persistence=RunnerPersistenceSpec(
            durable=True,
            checkpoint=RunnerCheckpointPolicy(
                enabled=True, cadence_ticks=_CHECKPOINT_CADENCE
            ),
        ),
        stop_policy=replace(base.stop_policy, max_ticks=_MAX_TICKS),
        population_lifecycle=replace(lifecycle, lifespan_ticks=_LIFESPAN_TICKS),
        generational_run=replace(
            generational,
            historical_checkpoint_cadence_ticks=_CHECKPOINT_CADENCE,
            max_generation_index=None,
        ),
    )


@pytest.mark.asyncio
async def test_generational_history_survives_runner_teardown(
    database_resources: DatabaseResources,
    tmp_path: Path,
) -> None:
    config = _historical_config()
    run_id = unique_run_id("v3hist")
    session = open_generational_archive(
        config=config,
        run_id=run_id,
        root=tmp_path,
        code_revision="historical-safety",
        source_clean=True,
    )
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    journal = create_tick_journal_repository(factory)
    snapshots = create_snapshot_repository(factory)
    reader = PostgresHistoricalBoundaryReader(
        runs=runs, journal=journal, snapshots=snapshots
    )
    factories = session.dependencies(
        reader=reader,
        cadence_ticks=_CHECKPOINT_CADENCE,
        sample_on_generation_change=True,
        base=durable_factories(factory),
    )
    async with await SimulationRunner.from_config(
        config, run_id=run_id, factories=factories
    ) as runner:
        await runner.run()

    # Runner is torn down here: every remaining assertion is historical only.
    history_refs = session.store.history_refs()
    assert history_refs
    retained_boundaries: set[int] = set()
    for ref in history_refs:
        boundary_tick = decode_generational_document(
            (tmp_path / ref["path"]).read_bytes(),
            schema_version="generational-history-v1",
        )["boundary_tick"]
        assert isinstance(boundary_tick, int)
        retained_boundaries.add(boundary_tick)
    boundaries = sorted(retained_boundaries)
    assert any(boundary >= _LIFESPAN_TICKS for boundary in boundaries)

    replay = ReplayService(runs, journal, snapshots)
    for boundary in (0, *boundaries):
        reference = await reader.reference(run_id.value, boundary)
        assert reference.objective_commit_hash
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

    events = await journal.list_events(
        run_id, from_tick=Tick(0), to_tick=None, limit=100_000, offset=0
    )
    assert events
    deaths = [event for event in events if type(event.details).__name__ == "Died"]
    assert deaths, "lifespan horizon should produce a genuine death"

    objective = create_objective_evidence_loader(factory)
    collected: list[str] = []
    cursor: EventKeysetCursor | None = None
    while True:
        page = await objective.load_events_page(
            run_id=run_id.value, after=cursor, limit=250
        )
        assert len(page.events) <= 250
        collected.extend(event.event_id.value for event in page.events)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert collected == [event.event_id.value for event in events]
    assert len(collected) == len(set(collected))

    analysis = create_analysis_evidence_loader(factory)
    objective_cursor: tuple[int, int] | None = None
    analysis_ids: list[str] = []
    while True:
        analysis_page = await analysis.load_objective_event_page(
            run_id=run_id.value,
            after_tick=None if objective_cursor is None else objective_cursor[0],
            after_sequence=(None if objective_cursor is None else objective_cursor[1]),
            limit=250,
        )
        for retained_event in analysis_page.events:
            assert isinstance(retained_event, WorldEvent)
            analysis_ids.append(retained_event.event_id.value)
        if analysis_page.next_tick is None or analysis_page.next_sequence is None:
            break
        objective_cursor = (analysis_page.next_tick, analysis_page.next_sequence)
    assert analysis_ids == collected

    body_to_owner = {
        spec.entity_id.value: spec.agent_id.value for spec in config.agents
    }
    dead_body = cast(Died, deaths[0].details).body_id.value
    dead_owner = body_to_owner.get(dead_body)
    assert dead_owner is not None
    for lane in (
        "direct_traces",
        "communicated_traces",
        "reconstructions",
        "derivation_edges",
    ):
        subjective_page = await analysis.load_subjective_evidence_page(
            run_id=run_id.value,
            owner_id=dead_owner,
            lane=lane,
            limit=50,
        )
        assert subjective_page.lane == lane
        row_count = (
            len(subjective_page.traces)
            + len(subjective_page.reconstructions)
            + len(subjective_page.derivation_edges)
        )
        assert row_count <= 50
        # Long-dead subjective evidence stays explicitly queryable; empty is a
        # valid availability result, not an error or reconstructed history.
        assert subjective_page.owner_id == dead_owner

    # Exact death-boundary replay remains reachable from persisted history.
    death_tick = int(deaths[0].tick)
    death_reference = await reader.reference(run_id.value, death_tick)
    death_outcome = await replay.replay(
        ReplayRequest(
            run_id=run_id,
            target_tick=Tick(death_tick),
            population_lifecycle=config.population_lifecycle,
        )
    )
    assert death_reference.snapshot_ref.next_tick <= death_tick
    assert death_outcome.result.status is ReplayStatus.OK
    assert death_outcome.engine is not None
    assert death_outcome.engine.tick.value == death_tick
