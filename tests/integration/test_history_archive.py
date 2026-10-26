"""Guarded PostgreSQL parity for verified offline history archives."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import func, select
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
from persistence.history_archive_filesystem import create_history_archive_reader
from persistence.orm import TickCommitOrm, WorldEventOrm, WorldSnapshotOrm
from research_runner.history_archive_composition import (
    export_history_archive,
    verify_history_archive,
)
from simulation.clock import Tick
from simulation.history_archive import (
    ArchiveAuxiliarySource,
    HistoryArchiveError,
)
from simulation.models import RunId
from simulation.persistence import ReplayRequest, ReplayStatus
from simulation.replay import ReplayService
from simulation.runner import SimulationRunner

pytestmark = pytest.mark.integration


async def _count(session_factory: Any, model: Any, run_id: RunId) -> int:
    async with session_scope(session_factory) as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(model)
                    .where(model.run_id == run_id.value)
                )
            ).scalar_one()
        )


@pytest.mark.asyncio
async def test_archive_export_parity_restart_and_tamper(
    database_resources: DatabaseResources,
    tmp_path: Path,
) -> None:
    session_factory = database_resources.session_factory
    run_id = unique_run_id("v3-43-archive")
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
    source_counts = (
        await _count(session_factory, TickCommitOrm, run_id),
        await _count(session_factory, WorldEventOrm, run_id),
        await _count(session_factory, WorldSnapshotOrm, run_id),
    )
    assert source_counts[0] > 0
    assert source_counts[1] > 0
    assert source_counts[2] > 0

    auxiliary = tmp_path / "cognition-trace.json"
    auxiliary.write_text('{"trace":"metadata-only"}\n', encoding="utf-8")
    root = tmp_path / "archive"
    archive = await export_history_archive(
        runs=runs,
        journal=journal,
        snapshots=snapshots,
        root=root,
        run_id=run_id,
        auxiliary=(
            ArchiveAuxiliarySource(
                name="cognition-trace",
                capability_class="subjective",
                path=str(auxiliary),
            ),
        ),
    )
    assert archive.coverage.commit_count == source_counts[0]
    assert archive.coverage.event_count == source_counts[1]
    assert archive.coverage.snapshot_count == source_counts[2]

    results = await verify_history_archive(root, full=True)
    assert len(results) == 1
    assert results[0].archive_id == archive.archive_id
    assert results[0].full is True
    assert results[0].replay_boundaries

    reader = create_history_archive_reader(root)
    sql_replay = ReplayService(runs, journal, snapshots)
    archive_replay = ReplayService(reader, reader, reader)
    for boundary in (0, 2, 4, 6):
        request = ReplayRequest(run_id=run_id, target_tick=Tick(boundary))
        expected = await sql_replay.replay(request)
        actual = await archive_replay.replay(request)
        assert expected.result.status is ReplayStatus.OK
        assert actual.result.status is ReplayStatus.OK
        assert actual.result.events_applied == expected.result.events_applied
        assert actual.predecessor_commit_hash == expected.predecessor_commit_hash
        assert actual.result.snapshot_next_tick == expected.result.snapshot_next_tick

    sql_events = await journal.list_events(
        run_id, from_tick=Tick(0), to_tick=None, limit=1000, offset=0
    )
    assert sql_events
    for event in (sql_events[0], sql_events[-1]):
        from_archive = await reader.get_event_by_id(run_id, event.event_id.value)
        assert from_archive == event
    assert await reader.get_latest_tick_commit(run_id) is not None

    restart_reader = create_history_archive_reader(root)
    assert (
        await restart_reader.get_event_by_id(run_id, sql_events[-1].event_id.value)
        == sql_events[-1]
    )

    assert (
        await _count(session_factory, TickCommitOrm, run_id),
        await _count(session_factory, WorldEventOrm, run_id),
        await _count(session_factory, WorldSnapshotOrm, run_id),
    ) == source_counts

    segment = archive.event_segments[0]
    object_path = root / segment.path
    payload = bytearray(object_path.read_bytes())
    payload[0] = ord("{") if payload[0] != ord("{") else ord("[")
    object_path.write_bytes(bytes(payload))
    with pytest.raises(HistoryArchiveError):
        await verify_history_archive(root, full=False)
