"""Bounded journal/head contracts without a live database."""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any, cast

import pytest

from persistence.sqlalchemy import SqlAlchemyTickJournalRepository
from simulation.clock import Tick
from simulation.models import RunId
from simulation.persistence import (
    CommitHash,
    DurableHead,
    PayloadHash,
    TickCommit,
    resolve_durable_head,
)
from world.identifiers import WorldRevision


class _Runs:
    def __init__(self) -> None:
        self.manifest = SimpleNamespace(
            event_schema_version=20,
            projector_version="v2",
            persistence_codec_version="v20",
        )

    async def get_run(self, run_id: RunId) -> Any:
        return self.manifest if run_id == RunId("run-1") else None


class _Journal:
    def __init__(self) -> None:
        self.commit = TickCommit(
            run_id=RunId("run-1"),
            tick=Tick(4),
            resulting_tick=Tick(5),
            base_revision=WorldRevision(3),
            resulting_revision=WorldRevision(4),
            predecessor_commit_hash=None,
            commit_hash=CommitHash("a" * 64),
            idempotency_key="idem-1",
            event_count=1,
            payload_hash=PayloadHash("b" * 64),
        )
        self.event = SimpleNamespace(tick=4, sequence=7)

    async def get_latest_tick_commit(
        self, run_id: RunId, *, through_tick: Tick | None = None
    ) -> Any:
        del run_id, through_tick
        return self.commit

    async def get_latest_event(
        self, run_id: RunId, *, through_tick: Tick | None = None
    ) -> Any:
        del run_id, through_tick
        return self.event


class _LegacyJournal:
    async def list_tick_commits(
        self, run_id: RunId, *, from_tick: Tick, to_tick: Tick | None
    ) -> tuple[object, ...]:
        del run_id, from_tick, to_tick
        return ()


def test_durable_head_is_detached_and_validated() -> None:
    head = DurableHead(
        run_id=RunId("run-1"),
        next_tick=Tick(5),
        revision=WorldRevision(4),
        last_commit_hash=CommitHash("a" * 64),
        latest_event_tick=Tick(4),
        latest_event_sequence=7,
        event_schema_version=20,
        projector_version="v2",
        persistence_codec_version="v20",
    )
    assert head.next_tick == Tick(5)
    with pytest.raises(ValueError):
        DurableHead(
            run_id=RunId("run-1"),
            next_tick=Tick(1),
            revision=WorldRevision(0),
            last_commit_hash=None,
            latest_event_tick=Tick(0),
            latest_event_sequence=None,
            event_schema_version=20,
            projector_version="v2",
            persistence_codec_version="v20",
        )


@pytest.mark.asyncio
async def test_resolve_durable_head_uses_bounded_reads() -> None:
    head = await resolve_durable_head(
        cast(Any, _Runs()), cast(Any, _Journal()), RunId("run-1")
    )
    assert head.next_tick == Tick(5)
    assert head.latest_event_tick == Tick(4)
    assert head.latest_event_sequence == 7


@pytest.mark.asyncio
async def test_legacy_journal_yields_empty_head_without_full_scan() -> None:
    head = await resolve_durable_head(
        cast(Any, _Runs()), cast(Any, _LegacyJournal()), RunId("run-1")
    )
    assert head.next_tick == Tick(0)
    assert head.last_commit_hash is None


@pytest.mark.asyncio
async def test_keyset_page_cap_rejects_before_database_access() -> None:
    repository = SqlAlchemyTickJournalRepository(None)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        await repository.list_tick_commits_keyset(
            RunId("run-1"),
            after_tick=Tick(0),
            through_tick=None,
            limit=0,
        )
    with pytest.raises(ValueError):
        await repository.list_tick_commits_keyset(
            RunId("run-1"),
            after_tick=Tick(0),
            through_tick=None,
            limit=1001,
        )


def test_durable_head_requires_run_scope() -> None:
    with pytest.raises(TypeError):
        DurableHead(
            run_id="run-1",  # type: ignore[arg-type]
            next_tick=Tick(0),
            revision=WorldRevision(0),
            last_commit_hash=None,
            latest_event_tick=None,
            latest_event_sequence=None,
            event_schema_version=20,
            projector_version="v2",
            persistence_codec_version="v20",
        )


def _event(sequence: int, *, detail: str = "wait") -> Any:
    from world.effects import ActionCause
    from world.events import OccurrenceContext, Waited, make_physical_replayable_event
    from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

    return make_physical_replayable_event(
        event_id=EventId(f"evt-{sequence}"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=2,
        sequence=sequence,
        resulting_revision=WorldRevision(
            1 + sequence + (10 if detail != "wait" else 0)
        ),
        cause=ActionCause(
            actor_id=EntityId("agent-1"),
            request_id=RequestId(f"req-{sequence}"),
        ),
        occurrence=OccurrenceContext(),
        details=Waited(),
    )


def _commit_for(events: Sequence[Any]) -> TickCommit:
    from simulation.journal import (
        compute_commit_hash,
        hash_tick_events,
        hash_tick_payload,
    )
    from world.identifiers import WorldRevision

    hashes = hash_tick_events(events)
    payload = hash_tick_payload(events)
    commit_hash = compute_commit_hash(
        predecessor_commit_hash=None,
        run_id=RunId("run-1"),
        tick=Tick(2),
        base_revision=WorldRevision(0),
        resulting_revision=WorldRevision(len(events)),
        event_hashes=hashes,
        payload_hash=payload,
    )
    return TickCommit(
        run_id=RunId("run-1"),
        tick=Tick(2),
        resulting_tick=Tick(3),
        base_revision=WorldRevision(0),
        resulting_revision=WorldRevision(len(events)),
        predecessor_commit_hash=None,
        commit_hash=commit_hash,
        idempotency_key="idem-stream",
        event_count=len(events),
        payload_hash=payload,
    )


def test_streamed_verifier_accepts_split_pages_and_unicode() -> None:
    from simulation.journal import StreamedTickCommitVerifier

    events = (_event(0), _event(1), _event(2))
    commit = _commit_for(events)
    verifier = StreamedTickCommitVerifier(commit)
    verifier.feed(events[0])
    verifier.feed(events[1])
    verifier.feed(events[2])
    verifier.finish()
    assert verifier.event_count == 3


def test_streamed_verifier_rejects_tampered_payload_and_order() -> None:
    from simulation.journal import (
        PersistenceSerializationError,
        StreamedTickCommitVerifier,
    )

    events = (_event(0), _event(1))
    commit = _commit_for(events)
    tampered = _event(0, detail="different")
    verifier = StreamedTickCommitVerifier(commit)
    verifier.feed(tampered)
    verifier.feed(events[1])
    with pytest.raises(PersistenceSerializationError):
        verifier.finish()

    verifier = StreamedTickCommitVerifier(commit)
    with pytest.raises(PersistenceSerializationError):
        verifier.feed(events[1])


def test_streamed_verifier_rejects_missing_events() -> None:
    from simulation.journal import (
        PersistenceSerializationError,
        StreamedTickCommitVerifier,
    )

    commit = _commit_for((_event(0), _event(1)))
    verifier = StreamedTickCommitVerifier(commit)
    verifier.feed(_event(0))
    with pytest.raises(PersistenceSerializationError, match="event_count"):
        verifier.finish()


def _empty_commit(tick: int) -> TickCommit:
    from simulation.journal import compute_commit_hash, hash_tick_payload
    from world.identifiers import WorldRevision

    payload = hash_tick_payload(())
    commit_hash = compute_commit_hash(
        predecessor_commit_hash=None,
        run_id=RunId("run-1"),
        tick=Tick(tick),
        base_revision=WorldRevision(tick),
        resulting_revision=WorldRevision(tick + 1),
        event_hashes=(),
        payload_hash=payload,
    )
    return TickCommit(
        run_id=RunId("run-1"),
        tick=Tick(tick),
        resulting_tick=Tick(tick + 1),
        base_revision=WorldRevision(tick),
        resulting_revision=WorldRevision(tick + 1),
        predecessor_commit_hash=None,
        commit_hash=commit_hash,
        idempotency_key=f"idem-{tick}",
        event_count=0,
        payload_hash=payload,
    )


class _PagedJournal:
    def __init__(self, commits: Sequence[TickCommit]) -> None:
        self.commits = commits

    async def get_tick_commit(self, run_id: RunId, tick: Tick) -> TickCommit | None:
        del run_id
        return next(
            (commit for commit in self.commits if commit.tick == tick), None
        )

    async def get_latest_tick_commit(
        self, run_id: RunId, *, through_tick: Tick | None = None
    ) -> Any:
        return self.commits[-1]

    async def list_tick_commits_keyset(
        self,
        run_id: RunId,
        *,
        after_tick: Tick,
        through_tick: Tick | None,
        limit: int,
    ) -> tuple[TickCommit, ...]:
        del run_id, through_tick
        return tuple(
            commit
            for commit in self.commits
            if commit.tick.value > after_tick.value
        )[:limit]

    async def list_tick_commits(
        self, run_id: RunId, *, from_tick: Tick, to_tick: Tick | None
    ) -> tuple[TickCommit, ...]:
        del run_id, from_tick, to_tick
        raise AssertionError("full commit list must not be read")


@pytest.mark.asyncio
async def test_read_commit_page_uses_bounded_keyset() -> None:
    from simulation.replay import ReplayService

    commits = tuple(_empty_commit(tick) for tick in range(5))
    service = ReplayService(
        _Runs(),  # type: ignore[arg-type]
        _PagedJournal(commits),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
    )
    first = await service.read_commit_page(
        RunId("run-1"), from_tick=Tick(0), limit=2
    )
    assert [commit.tick.value for commit in first.commits] == [0, 1]
    assert first.next_from_tick == Tick(2)
    second = await service.read_commit_page(
        RunId("run-1"), from_tick=Tick(2), limit=2
    )
    assert [commit.tick.value for commit in second.commits] == [2, 3]
    assert second.next_from_tick == Tick(4)


class _BoundedFakeJournal:
    """Bounded port surface over the observer replay fixture commits."""

    def __init__(self, journal: Any) -> None:
        self._journal = journal
        self.event_key_page_calls = 0
        self.commit_page_calls = 0

    async def get_tick_commit(self, run_id: RunId, tick: Tick) -> Any:
        return await self._journal.get_tick_commit(run_id, tick)

    async def get_latest_tick_commit(
        self, run_id: RunId, *, through_tick: Tick | None = None
    ) -> Any:
        candidates = [
            commit
            for commit in self._journal.commits
            if commit.run_id == run_id
            and (through_tick is None or commit.tick.value <= through_tick.value)
        ]
        return max(candidates, key=lambda item: item.tick.value, default=None)

    async def list_tick_commits_keyset(
        self,
        run_id: RunId,
        *,
        after_tick: Tick,
        through_tick: Tick | None,
        limit: int,
    ) -> tuple[Any, ...]:
        self.commit_page_calls += 1
        return tuple(
            commit
            for commit in self._journal.commits
            if commit.run_id == run_id
            and commit.tick.value > after_tick.value
            and (through_tick is None or commit.tick.value <= through_tick.value)
        )[:limit]

    async def list_events_keyset(
        self,
        run_id: RunId,
        *,
        after_tick: int,
        after_sequence: int,
        to_tick: Tick | None,
        limit: int,
        actor_id: str | None = None,
        event_type: str | None = None,
    ) -> tuple[Any, ...]:
        del actor_id, event_type
        self.event_key_page_calls += 1
        selected = [
            event
            for event in self._journal.events
            if event.run_id == run_id.value
            and (event.tick, event.sequence) > (after_tick, after_sequence)
            and (to_tick is None or event.tick <= to_tick.value)
        ]
        return tuple(selected[:limit])

    async def get_event_by_id(
        self, run_id: RunId, event_id: str, *, through_tick: Tick | None = None
    ) -> Any:
        del through_tick
        return next(
            (
                event
                for event in self._journal.events
                if event.run_id == run_id.value and event.event_id.value == event_id
            ),
            None,
        )

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
        limit: int,
        offset: int,
    ) -> tuple[Any, ...]:
        return tuple(
            await self._journal.list_events(
            run_id,
            from_tick=from_tick,
            to_tick=to_tick,
            limit=limit,
                offset=offset,
            )
        )


def _bounded_services() -> tuple[Any, Any, _BoundedFakeJournal, Any]:
    from simulation.replay import ReplayService
    from tests.unit.test_observer_replay import (
        FakeRuns,
        FakeSnapshots,
        _manifest,
        _snapshot,
        boundary_replay_service,
    )

    legacy, journal = boundary_replay_service()
    bounded_journal = _BoundedFakeJournal(journal)
    bounded = ReplayService(
        FakeRuns(_manifest()),
        cast(Any, bounded_journal),
        FakeSnapshots(_snapshot()),
    )
    return legacy, bounded, bounded_journal, journal


@pytest.mark.asyncio
@pytest.mark.parametrize("target", [0, 1, 2, 3])
async def test_bounded_replay_matches_legacy_restore(target: int) -> None:
    from simulation.persistence import ReplayRequest, ReplayStatus
    from tests.unit.test_observer_replay import RUN_ID

    legacy, bounded, _, _ = _bounded_services()
    request = ReplayRequest(run_id=RunId(RUN_ID), target_tick=Tick(target))
    expected = await legacy.replay(request)
    actual = await bounded.replay(request)
    assert expected.result.status is ReplayStatus.OK
    assert actual.result.status is ReplayStatus.OK
    assert actual.result.events_applied == expected.result.events_applied
    assert actual.predecessor_commit_hash == expected.predecessor_commit_hash
    assert actual.engine is not None and expected.engine is not None
    assert actual.engine.tick == expected.engine.tick
    assert actual.engine.revision == expected.engine.revision
    assert actual.engine.detached_objective_facts() == (
        expected.engine.detached_objective_facts()
    )


@pytest.mark.asyncio
async def test_scene_through_event_verifies_split_tick_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from simulation import replay as replay_module
    from simulation.replay import scene_through_event
    from tests.unit.test_observer_replay import RUN_ID

    _, bounded, bounded_journal, _ = _bounded_services()
    monkeypatch.setattr(replay_module, "_DEFAULT_PAGE_SIZE", 1)
    history = await scene_through_event(
        bounded, RunId(RUN_ID), tick=Tick(2), through_sequence=0
    )
    assert bounded_journal.event_key_page_calls >= 2
    assert history.result.status.value == "ok"


@pytest.mark.asyncio
async def test_bounded_replay_rejects_tampered_payload() -> None:
    from experiments.reference_scenario import LOC_CAMP
    from simulation.persistence import ReplayRequest, ReplayStatus
    from tests.unit.test_observer_replay import RUN_ID, _wait

    _, bounded, bounded_journal, journal = _bounded_services()
    original = journal.events[0]
    tampered = _wait(
        event_id=original.event_id.value,
        tick=original.tick,
        sequence=original.sequence,
        revision=original.resulting_revision.value,
        location_id=LOC_CAMP,
    )
    assert tampered.tick == original.tick
    assert tampered.sequence == original.sequence
    bounded_journal._journal.events = (tampered, *journal.events[1:])
    outcome = await bounded.replay(
        ReplayRequest(run_id=RunId(RUN_ID), target_tick=Tick(3))
    )
    assert outcome.result.status is ReplayStatus.STREAM_DISCONTINUITY
    assert outcome.engine is None


def _chain_commit(
    events: Sequence[Any],
    *,
    tick: int,
    base_revision: int,
    resulting_revision: int,
    predecessor: CommitHash | None,
    idempotency_key: str,
) -> TickCommit:
    from simulation.journal import (
        compute_commit_hash,
        hash_tick_events,
        hash_tick_payload,
    )
    from world.identifiers import WorldRevision

    payload = hash_tick_payload(events)
    event_hashes = hash_tick_events(events)
    commit_hash = compute_commit_hash(
        predecessor_commit_hash=predecessor,
        run_id=RunId("run-observer"),
        tick=Tick(tick),
        base_revision=WorldRevision(base_revision),
        resulting_revision=WorldRevision(resulting_revision),
        event_hashes=event_hashes,
        payload_hash=payload,
    )
    return TickCommit(
        run_id=RunId("run-observer"),
        tick=Tick(tick),
        resulting_tick=Tick(tick + 1),
        base_revision=WorldRevision(base_revision),
        resulting_revision=WorldRevision(resulting_revision),
        predecessor_commit_hash=predecessor,
        commit_hash=commit_hash,
        idempotency_key=idempotency_key,
        event_count=len(events),
        payload_hash=payload,
    )


def _eventless_journal() -> tuple[tuple[TickCommit, ...], tuple[Any, ...]]:
    from experiments.reference_scenario import LOC_CAMP, LOC_SPRING
    from tests.unit.test_observer_replay import BODY_ID, RUN_ID, WORLD_ID
    from world.effects import ActionCause
    from world.events import (
        Moved,
        build_occurrence_context,
        make_physical_replayable_event,
    )
    from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

    details = Moved(
        destination_id=EntityId(LOC_SPRING),
        resulting_location_id=EntityId(LOC_SPRING),
        fatigue_delta=0.0,
        resulting_fatigue=0.0,
    )
    first = make_physical_replayable_event(
        event_id=EventId("evt-move-0"),
        run_id=RUN_ID,
        world_id=WorldId(WORLD_ID),
        tick=0,
        sequence=0,
        cause=ActionCause(RequestId("req-move-0"), EntityId(BODY_ID)),
        resulting_revision=WorldRevision(1),
        details=details,
        occurrence=build_occurrence_context(
            details, origin_location_id=EntityId(LOC_CAMP)
        ),
    )
    back = Moved(
        destination_id=EntityId(LOC_CAMP),
        resulting_location_id=EntityId(LOC_CAMP),
        fatigue_delta=0.0,
        resulting_fatigue=0.0,
    )
    last = make_physical_replayable_event(
        event_id=EventId("evt-move-2"),
        run_id=RUN_ID,
        world_id=WorldId(WORLD_ID),
        tick=2,
        sequence=0,
        cause=ActionCause(RequestId("req-move-2"), EntityId(BODY_ID)),
        resulting_revision=WorldRevision(2),
        details=back,
        occurrence=build_occurrence_context(
            back, origin_location_id=EntityId(LOC_SPRING)
        ),
    )
    commit0 = _chain_commit(
        (first,),
        tick=0,
        base_revision=0,
        resulting_revision=1,
        predecessor=None,
        idempotency_key="idem-0",
    )
    commit1 = _chain_commit(
        (),
        tick=1,
        base_revision=1,
        resulting_revision=1,
        predecessor=commit0.commit_hash,
        idempotency_key="idem-1",
    )
    commit2 = _chain_commit(
        (last,),
        tick=2,
        base_revision=1,
        resulting_revision=2,
        predecessor=commit1.commit_hash,
        idempotency_key="idem-2",
    )
    return (commit0, commit1, commit2), (first, last)


class _SyntheticJournal:
    def __init__(self, commits: Sequence[TickCommit], events: Sequence[Any]) -> None:
        self.commits = commits
        self.events = events

    async def get_tick_commit(self, run_id: RunId, tick: Tick) -> TickCommit | None:
        return next(
            (
                commit
                for commit in self.commits
                if commit.run_id == run_id and commit.tick == tick
            ),
            None,
        )

    async def list_tick_commits(
        self, run_id: RunId, *, from_tick: Tick, to_tick: Tick | None
    ) -> tuple[TickCommit, ...]:
        del run_id
        return tuple(
            commit
            for commit in self.commits
            if commit.tick.value >= from_tick.value
            and (to_tick is None or commit.tick.value <= to_tick.value)
        )

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
        limit: int,
        offset: int,
    ) -> tuple[Any, ...]:
        selected = tuple(
            event
            for event in self.events
            if event.run_id == run_id.value
            and event.tick >= from_tick.value
            and (to_tick is None or event.tick <= to_tick.value)
        )
        return selected[offset : offset + limit]


class _SyntheticBoundedJournal(_SyntheticJournal):
    async def get_latest_tick_commit(
        self, run_id: RunId, *, through_tick: Tick | None = None
    ) -> Any:
        candidates = [
            commit
            for commit in self.commits
            if commit.run_id == run_id
            and (through_tick is None or commit.tick.value <= through_tick.value)
        ]
        return max(candidates, key=lambda item: item.tick.value, default=None)

    async def list_tick_commits_keyset(
        self,
        run_id: RunId,
        *,
        after_tick: Tick,
        through_tick: Tick | None,
        limit: int,
    ) -> tuple[TickCommit, ...]:
        del run_id
        return tuple(
            commit
            for commit in self.commits
            if commit.tick.value > after_tick.value
            and (through_tick is None or commit.tick.value <= through_tick.value)
        )[:limit]

    async def list_events_keyset(
        self,
        run_id: RunId,
        *,
        after_tick: int,
        after_sequence: int,
        to_tick: Tick | None,
        limit: int,
        actor_id: str | None = None,
        event_type: str | None = None,
    ) -> tuple[Any, ...]:
        del actor_id, event_type
        selected = tuple(
            event
            for event in self.events
            if event.run_id == run_id.value
            and (event.tick, event.sequence) > (after_tick, after_sequence)
            and (to_tick is None or event.tick <= to_tick.value)
        )
        return selected[:limit]


@pytest.mark.asyncio
async def test_bounded_replay_handles_eventless_tick() -> None:
    from simulation.persistence import ReplayRequest, ReplayStatus
    from simulation.replay import ReplayService
    from tests.unit.test_observer_replay import (
        FakeRuns,
        FakeSnapshots,
        _manifest,
        _snapshot,
    )

    commits, events = _eventless_journal()
    legacy = ReplayService(
        FakeRuns(_manifest()),
        cast(Any, _SyntheticJournal(commits, events)),
        FakeSnapshots(_snapshot()),
    )
    bounded = ReplayService(
        FakeRuns(_manifest()),
        cast(Any, _SyntheticBoundedJournal(commits, events)),
        FakeSnapshots(_snapshot()),
    )
    request = ReplayRequest(run_id=RunId("run-observer"), target_tick=Tick(3))
    expected = await legacy.replay(request)
    actual = await bounded.replay(request)
    assert actual.result.status is ReplayStatus.OK
    assert actual.result.events_applied == expected.result.events_applied == 2
    assert actual.engine is not None and expected.engine is not None
    assert actual.engine.tick == expected.engine.tick == Tick(3)
    assert actual.engine.revision == expected.engine.revision


@pytest.mark.asyncio
async def test_bounded_replay_rejects_cross_page_predecessor_corruption() -> None:
    from dataclasses import replace

    from simulation.persistence import (
        CommitHash,
        ReplayRequest,
        ReplayStatus,
    )
    from simulation.replay import ReplayService
    from tests.unit.test_observer_replay import (
        FakeRuns,
        FakeSnapshots,
        _manifest,
        _snapshot,
    )

    commits, events = _eventless_journal()
    corrupted = (
        commits[0],
        replace(commits[1], predecessor_commit_hash=CommitHash("f" * 64)),
        commits[2],
    )
    service = ReplayService(
        FakeRuns(_manifest()),
        cast(Any, _SyntheticBoundedJournal(corrupted, events)),
        FakeSnapshots(_snapshot()),
    )
    outcome = await service.replay(
        ReplayRequest(run_id=RunId("run-observer"), target_tick=Tick(3))
    )
    assert outcome.result.status is ReplayStatus.STREAM_DISCONTINUITY


@pytest.mark.asyncio
async def test_read_event_uses_indexed_lookup_without_event_pages() -> None:
    _, bounded, bounded_journal, _ = _bounded_services()
    event = await bounded.read_event(RunId("run-observer"), "evt-wait-2")
    assert event is not None
    assert event.event_id.value == "evt-wait-2"
    assert bounded_journal.event_key_page_calls == 0
    assert await bounded.read_event(RunId("run-observer"), "evt-missing") is None


@pytest.mark.asyncio
async def test_bounded_replay_rejects_reordered_events() -> None:
    from simulation.persistence import ReplayRequest, ReplayStatus

    _, bounded, bounded_journal, journal = _bounded_services()
    assert len(journal.events) >= 2
    reordered = (journal.events[1], journal.events[0], *journal.events[2:])
    bounded_journal._journal.events = reordered
    outcome = await bounded.replay(
        ReplayRequest(run_id=RunId("run-observer"), target_tick=Tick(3))
    )
    assert outcome.result.status is ReplayStatus.STREAM_DISCONTINUITY


__all__: tuple[str, ...] = ()
