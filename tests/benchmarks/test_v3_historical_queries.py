"""Opt-in historical-query scale evidence for V3.

Run with a guarded disposable database::

    uv run pytest -m 'integration and scale' \\
      tests/benchmarks/test_v3_historical_queries.py

Two labelled lanes:

* ``synthetic-log`` writes a deliberately large synthetic journal commit and
  measures keyset page traversal plus indexed late-event lookup. It is not a
  scientific simulation.
* ``generational`` runs a short genuine v55 slice and measures historical
  boundary resolution and bounded replay.

No universal latency promise is derived from these measurements.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import cast

import pytest

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
from simulation.models import RunId
from simulation.persistence import (
    BoundedTickJournalRepository,
    ReplayRequest,
    ReplayStatus,
    RunCreateRequest,
    TickAppendRequest,
    WorldRevision,
)
from simulation.replay import ReplayService
from simulation.runner import SimulationRunner
from simulation.runner_models import RunnerStopReasonCode
from tests.benchmarks.harness import durable_factories, unique_run_id
from tests.integration.test_api_event_pagination import _bootstrap, _unique
from tests.integration.test_v3_historical_query_safety import _historical_config
from world.effects import ActionCause
from world.events import (
    OccurrenceContext,
    Waited,
    WorldEvent,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId

pytestmark = [pytest.mark.integration, pytest.mark.scale]

_LOG = logging.getLogger("scale.v3.historical")

_HIGH_VOLUME_EVENTS = 10_100
_PAGE_LIMIT = 250


def _synthetic_event(
    *, run_id: str, tick: int, sequence: int, revision: int
) -> WorldEvent:
    """Unique synthetic event IDs let repeated guarded-DB runs coexist."""
    actor = EntityId("body-1")
    return make_physical_replayable_event(
        event_id=EventId(f"{run_id}-evt-{tick}-{sequence}"),
        run_id=run_id,
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=sequence,
        cause=ActionCause(RequestId(f"req-{tick}-{sequence}"), actor),
        resulting_revision=WorldRevision(revision),
        details=Waited(),
        occurrence=OccurrenceContext(
            origin_location_id=EntityId("loc-1"),
            private_recipient_ids=(),
            affected_entity_ids=(actor,),
        ),
    )


@pytest.mark.asyncio
async def test_synthetic_large_journal_late_event_lookup(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    journal = create_tick_journal_repository(factory)
    analysis = create_analysis_evidence_loader(factory)
    objective = create_objective_evidence_loader(factory)
    run_id = _unique("v3hist-synthetic")
    bootstrap = _bootstrap(run_id=run_id)
    await runs.create_run(
        RunCreateRequest(
            run_id=RunId(run_id),
            world_id=bootstrap.world_id,
            seed=bootstrap.seed,
            config=bootstrap.config,
            bootstrap=bootstrap,
        )
    )
    events = tuple(
        _synthetic_event(
            run_id=run_id,
            tick=0,
            sequence=sequence,
            revision=1,
        )
        for sequence in range(_HIGH_VOLUME_EVENTS)
    )
    started = time.perf_counter()
    commit = await journal.append_tick(
        TickAppendRequest(
            run_id=RunId(run_id),
            tick=Tick(0),
            expected_base_revision=WorldRevision(0),
            expected_predecessor_commit_hash=None,
            idempotency_key=_unique("v3hist-synthetic-idem"),
            events=events,
        )
    )
    write_ms = (time.perf_counter() - started) * 1000.0
    assert commit.event_count == _HIGH_VOLUME_EVENTS

    started = time.perf_counter()
    collected: list[str] = []
    cursor = None
    pages = 0
    while True:
        analysis_page = await analysis.load_objective_event_page(
            run_id=run_id,
            after_tick=None if cursor is None else cursor[0],
            after_sequence=None if cursor is None else cursor[1],
            limit=_PAGE_LIMIT,
        )
        pages += 1
        assert len(analysis_page.events) <= _PAGE_LIMIT
        collected.extend(event.event_id.value for event in analysis_page.events)
        if analysis_page.next_tick is None or analysis_page.next_sequence is None:
            break
        cursor = (analysis_page.next_tick, analysis_page.next_sequence)
    page_ms = (time.perf_counter() - started) * 1000.0
    assert collected == [event.event_id.value for event in events]
    assert len(collected) == len(set(collected))

    started = time.perf_counter()
    bounded = cast(BoundedTickJournalRepository, journal)
    latest = await bounded.get_latest_event(RunId(run_id), through_tick=Tick(0))
    late = await bounded.get_event_by_id(
        RunId(run_id), f"{run_id}-evt-0-{_HIGH_VOLUME_EVENTS - 1}", through_tick=Tick(0)
    )
    lookup_ms = (time.perf_counter() - started) * 1000.0
    assert isinstance(latest, WorldEvent)
    assert isinstance(late, WorldEvent)
    assert latest.event_id == late.event_id
    assert late.sequence == _HIGH_VOLUME_EVENTS - 1

    started = time.perf_counter()
    objective_page = await objective.load_events_page(
        run_id=run_id,
        after=None,
        limit=min(_PAGE_LIMIT, 1000),
    )
    first_page_ms = (time.perf_counter() - started) * 1000.0
    assert len(objective_page.events) <= 1000

    _LOG.info(
        "[scale.v3.historical] lane=synthetic-log events=%s pages=%s "
        "write_ms=%.1f page_ms=%.1f lookup_ms=%.2f first_page_ms=%.1f",
        _HIGH_VOLUME_EVENTS,
        pages,
        write_ms,
        page_ms,
        lookup_ms,
        first_page_ms,
    )


@pytest.mark.asyncio
async def test_generational_historical_seek_and_replay(
    database_resources: DatabaseResources,
    tmp_path: Path,
) -> None:
    config = _historical_config()
    run_id = unique_run_id("v3hist-gen")
    session = open_generational_archive(
        config=config,
        run_id=run_id,
        root=tmp_path,
        code_revision="historical-bench",
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
        cadence_ticks=2,
        sample_on_generation_change=True,
        base=durable_factories(factory),
    )
    async with await SimulationRunner.from_config(
        config, run_id=run_id, factories=factories
    ) as runner:
        result = await runner.run()
    assert result.stop_reason is RunnerStopReasonCode.MAX_TICKS

    end_tick = int(config.stop_policy.max_ticks)
    seek_samples: list[float] = []
    replay_samples: list[float] = []
    for target in (0, end_tick // 2, end_tick):
        started = time.perf_counter()
        reference = await reader.reference(run_id.value, target)
        seek_samples.append((time.perf_counter() - started) * 1000.0)
        started = time.perf_counter()
        outcome = await ReplayService(runs, journal, snapshots).replay(
            ReplayRequest(
                run_id=run_id,
                target_tick=Tick(target),
                population_lifecycle=config.population_lifecycle,
            )
        )
        replay_samples.append((time.perf_counter() - started) * 1000.0)
        assert outcome.result.status is ReplayStatus.OK
        assert outcome.engine is not None
        assert outcome.engine.tick.value == target
        assert reference.objective_commit_hash

    _LOG.info(
        "[scale.v3.historical] lane=generational ticks=%s seeks=%s "
        "seek_ms=%s replay_ms=%s",
        end_tick,
        len(seek_samples),
        ",".join(f"{value:.1f}" for value in seek_samples),
        ",".join(f"{value:.1f}" for value in replay_samples),
    )
