"""Durable bounded read bounds and shared manifest anchors."""

from __future__ import annotations

from typing import Any, cast

import pytest
from sqlalchemy import select, text
from tests.benchmarks.harness import (
    build_scale_config,
    durable_factories,
    unique_run_id,
)

from infrastructure.database import DatabaseResources, session_scope
from persistence import (
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from persistence.errors import PersistenceAdapterError
from persistence.evidence_boundary import resolve_objective_evidence_boundary
from persistence.inspection_sqlalchemy import SqlAlchemyObjectiveEvidenceLoader
from persistence.orm import SimulationRunOrm, TickCommitOrm, WorldSnapshotOrm
from simulation.clock import Tick
from simulation.evidence import EvidenceHighWaterMarks, build_evidence_manifest
from simulation.models import RunId
from simulation.persistence import resolve_durable_head
from simulation.runner import SimulationRunner

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_bounded_reads_and_manifest_anchor(
    database_resources: DatabaseResources,
) -> None:
    session_factory = database_resources.session_factory
    run_id = unique_run_id("v3-43-bounded")
    config = build_scale_config(max_ticks=6, checkpoint_cadence=2)
    async with await SimulationRunner.from_config(
        config,
        run_id=run_id,
        factories=durable_factories(session_factory),
    ) as runner:
        await runner.run()

    runs = create_run_repository(session_factory)
    journal = cast(Any, create_tick_journal_repository(session_factory))
    snapshots = create_snapshot_repository(session_factory)
    head = await resolve_durable_head(runs, journal, run_id)
    assert head.next_tick == Tick(6)
    assert head.last_commit_hash is not None
    assert head.latest_event_tick is not None

    all_commits = await journal.list_tick_commits(
        run_id, from_tick=Tick(0), to_tick=None
    )
    paged = []
    cursor = Tick(0)
    while True:
        page = await journal.list_tick_commits_keyset(
            run_id,
            after_tick=cursor,
            through_tick=None,
            limit=2,
        )
        if not page:
            break
        paged.extend(page)
        cursor = Tick(page[-1].tick.value)
    assert tuple(paged) == tuple(
        commit for commit in all_commits if commit.tick.value > 0
    )
    assert len(paged) == len(all_commits) - 1

    events = await journal.list_events(
        run_id, from_tick=Tick(0), to_tick=None, limit=100, offset=0
    )
    assert events
    first = await journal.get_event_by_id(run_id, events[0].event_id.value)
    assert first == events[0]
    assert (
        await journal.get_event_by_id(
            RunId("other-run"), events[0].event_id.value
        )
        is None
    )

    anchor_commit = all_commits[1]
    manifest = build_evidence_manifest(
        run_id=run_id.value,
        objective_commit_hash=anchor_commit.commit_hash.value,
        high_water=EvidenceHighWaterMarks(
            direct_memories=0,
            communicated_memories=0,
            reconstructions=0,
            beliefs=0,
            relationships=0,
            goals=0,
            resolutions=0,
            truth_specs=0,
        ),
    )
    async with session_scope(session_factory) as session:
        boundary = await resolve_objective_evidence_boundary(
            session, run_id=run_id.value, manifest=manifest
        )
    assert boundary.through_tick == anchor_commit.tick
    assert boundary.boundary_tick == anchor_commit.resulting_tick

    loader = SqlAlchemyObjectiveEvidenceLoader(session_factory)
    page = await loader.load_events_page(
        run_id=run_id.value, limit=100, manifest=manifest
    )
    assert page.events
    assert all(event.tick <= anchor_commit.tick.value for event in page.events)
    assert page.manifest_hash == manifest.manifest_hash

    bad = build_evidence_manifest(
        run_id=run_id.value,
        objective_commit_hash="f" * 64,
        high_water=manifest.high_water,
    )
    async with session_scope(session_factory) as session:
        with pytest.raises(PersistenceAdapterError, match="not_found"):
            await resolve_objective_evidence_boundary(
                session, run_id=run_id.value, manifest=bad
            )

    async with session_scope(session_factory) as session:
        run_row = await session.get(SimulationRunOrm, run_id.value)
        assert run_row is not None
        bootstrap = await session.get(
            WorldSnapshotOrm, run_row.bootstrap_snapshot_id
        )
        assert bootstrap is not None
        bootstrap_hash = bootstrap.integrity_hash
        # Confirm the commit anchor is whole-tick and not an event-count mark.
        commit_rows = (
            await session.execute(
                select(TickCommitOrm).where(
                    TickCommitOrm.run_id == run_id.value
                )
            )
        ).scalars().all()
        assert commit_rows
    bootstrap_manifest = build_evidence_manifest(
        run_id=run_id.value,
        objective_commit_hash=bootstrap_hash,
        high_water=manifest.high_water,
    )
    async with session_scope(session_factory) as session:
        bootstrap_boundary = await resolve_objective_evidence_boundary(
            session, run_id=run_id.value, manifest=bootstrap_manifest
        )
    assert bootstrap_boundary.bootstrap_only is True
    assert bootstrap_boundary.boundary_tick == Tick(0)
    empty_page = await loader.load_events_page(
        run_id=run_id.value, limit=100, manifest=bootstrap_manifest
    )
    assert empty_page.events == ()

    assert await snapshots.get_latest_at_or_before(run_id, Tick(6)) is not None

    async with session_scope(session_factory) as session:
        keyset_plan = (
            await session.execute(
                text(
                    "EXPLAIN (FORMAT JSON) SELECT * FROM world_events "
                    "WHERE run_id = :run_id AND (tick > :tick OR "
                    "(tick = :tick AND sequence > :sequence)) "
                    "ORDER BY tick, sequence LIMIT :limit"
                ),
                {
                    "run_id": run_id.value,
                    "tick": 0,
                    "sequence": -1,
                    "limit": 101,
                },
            )
        ).scalar_one()
        event_id_plan = (
            await session.execute(
                text(
                    "EXPLAIN (FORMAT JSON) SELECT * FROM world_events "
                    "WHERE run_id = :run_id AND event_id = :event_id LIMIT 1"
                ),
                {"run_id": run_id.value, "event_id": events[0].event_id.value},
            )
        ).scalar_one()
    assert keyset_plan
    assert event_id_plan


__all__: tuple[str, ...] = ()
