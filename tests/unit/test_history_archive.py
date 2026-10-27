"""Offline objective-history archive writer and read-only adapter."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from persistence.history_archive_filesystem import (
    create_history_archive_reader,
    create_history_archive_writer,
)
from simulation.clock import Tick
from simulation.history_archive import (
    ARCHIVE_STATE_SCHEMA,
    ArchiveAuxiliarySource,
    ArchiveManifest,
    ArchivePinnedHead,
    HistoryArchiveError,
    archive_manifest_id,
)
from simulation.journal import (
    compute_commit_hash,
    hash_snapshot,
    hash_tick_events,
    hash_tick_payload,
)
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    PERSISTENCE_CODEC_VERSION,
    CommitHash,
    PayloadHash,
    RunManifest,
    SnapshotId,
    TickCommit,
    WorldSnapshot,
)
from tests.simulation_helpers import make_location, make_weather
from world.events import (
    EVENT_SCHEMA_REPLAY_V2,
    Waited,
    WorldEvent,
    make_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit


def _run_manifest(run_id: str = "run-archive") -> RunManifest:
    return RunManifest(
        run_id=RunId(run_id),
        world_id=WorldId("world-archive"),
        seed=7,
        config=SimulationRunConfig(seed=7),
        derivation_version=DERIVATION_VERSION,
        event_schema_version=EVENT_SCHEMA_REPLAY_V2,
        projector_version="v1",
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
    )


def _snapshot(
    *,
    run_id: str,
    next_tick: int,
    revision: int,
    predecessor: CommitHash | None,
) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(f"snap-{next_tick}"),
        run_id=RunId(run_id),
        world_id=WorldId("world-archive"),
        seed=7,
        config=SimulationRunConfig(seed=7),
        registrations=(),
        locations=(make_location("loc-1", name="Camp"),),
        bodies=(),
        items=(),
        resources=(),
        weather=(make_weather(),),
        next_tick=Tick(next_tick),
        revision=WorldRevision(revision),
        event_schema_version=EVENT_SCHEMA_REPLAY_V2,
        projector_version="v1",
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("0" * 64),
        predecessor_commit_hash=predecessor,
    )
    return replace(draft, integrity_hash=hash_snapshot(draft))


def _event(*, run_id: str, tick: int, sequence: int) -> WorldEvent:
    return make_replayable_event(
        event_id=EventId(f"evt-{tick}-{sequence}"),
        run_id=run_id,
        world_id=WorldId("world-archive"),
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"req-{tick}-{sequence}"),
        resulting_revision=WorldRevision(tick + 1),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )


def _commits(run_id: str, *, split_tick: bool = False) -> tuple[TickCommit, ...]:
    commits: list[TickCommit] = []
    predecessor: CommitHash | None = None
    for tick in range(4):
        sequence_count = 3 if split_tick and tick == 2 else 2
        events = tuple(
            _event(run_id=run_id, tick=tick, sequence=sequence)
            for sequence in range(sequence_count)
        )
        payload = hash_tick_payload(events)
        commit_hash = compute_commit_hash(
            predecessor_commit_hash=predecessor,
            run_id=RunId(run_id),
            tick=Tick(tick),
            base_revision=WorldRevision(tick),
            resulting_revision=WorldRevision(tick + 1),
            event_hashes=hash_tick_events(events),
            payload_hash=payload,
        )
        commits.append(
            TickCommit(
                run_id=RunId(run_id),
                tick=Tick(tick),
                resulting_tick=Tick(tick + 1),
                base_revision=WorldRevision(tick),
                resulting_revision=WorldRevision(tick + 1),
                predecessor_commit_hash=predecessor,
                commit_hash=commit_hash,
                idempotency_key=f"idem-{tick}",
                event_count=len(events),
                payload_hash=payload,
            )
        )
        predecessor = commit_hash
    return tuple(commits)


def _pinned(
    commits: tuple[TickCommit, ...], *, split_tick: bool = False
) -> ArchivePinnedHead:
    del split_tick
    last = commits[-1]
    return ArchivePinnedHead(
        next_tick=last.tick.value + 1,
        revision=last.resulting_revision.value,
        last_commit_hash=last.commit_hash.value,
        latest_event_tick=last.tick.value,
        latest_event_sequence=last.event_count - 1,
    )


async def _publish(
    root: Path,
    *,
    run_id: str = "run-archive",
    split_tick: bool = False,
    auxiliary: tuple[ArchiveAuxiliarySource, ...] = (),
) -> ArchiveManifest:
    manifest = _run_manifest(run_id)
    commits = _commits(run_id, split_tick=split_tick)
    events: list[WorldEvent] = []
    for commit in commits:
        events.extend(
            _event(run_id=run_id, tick=commit.tick.value, sequence=sequence)
            for sequence in range(commit.event_count)
        )
    snapshots = (
        _snapshot(run_id=run_id, next_tick=0, revision=0, predecessor=None),
        _snapshot(
            run_id=run_id,
            next_tick=4,
            revision=4,
            predecessor=commits[-1].commit_hash,
        ),
    )
    writer = create_history_archive_writer(
        root,
        event_segment_rows=2,
        event_segment_bytes=64 * 1024,
        commit_segment_rows=2,
        commit_segment_bytes=64 * 1024,
        snapshot_segment_rows=1,
        snapshot_segment_bytes=256 * 1024,
        index_segment_rows=2,
        index_segment_bytes=4096,
    )
    return await writer.publish(
        run_manifest=manifest,
        pinned_head=_pinned(commits, split_tick=split_tick),
        commits=_iterator(commits),
        events=_iterator(tuple(events)),
        snapshots=_iterator(snapshots),
        auxiliary=auxiliary,
    )


async def _iterator(values: tuple[Any, ...]) -> AsyncIterator[Any]:
    for value in values:
        yield value


@pytest.mark.asyncio
async def test_round_trip_split_ticks_and_deep_event_lookup(tmp_path: Path) -> None:
    archive = await _publish(tmp_path / "archive", split_tick=True)
    reader = create_history_archive_reader(tmp_path / "archive")
    run_id = RunId("run-archive")
    manifest = reader.get_manifest(run_id)
    assert manifest is not None
    assert archive.archive_id == archive_manifest_id(manifest)
    assert manifest.archive_id == archive_manifest_id(manifest)
    assert manifest.coverage.event_count == 9
    assert manifest.coverage.commit_count == 4
    assert len(manifest.event_segments) >= 4

    commits = await reader.list_tick_commits(run_id, from_tick=Tick(0), to_tick=None)
    assert len(commits) == 4
    assert await reader.get_tick_commit(run_id, Tick(2)) == commits[2]
    assert await reader.get_latest_tick_commit(run_id) == commits[-1]

    page = await reader.list_events_keyset(
        run_id,
        after_tick=0,
        after_sequence=1,
        to_tick=None,
        limit=100,
    )
    assert [(item.tick, item.sequence) for item in page] == [
        (1, 0),
        (1, 1),
        (2, 0),
        (2, 1),
        (2, 2),
        (3, 0),
        (3, 1),
    ]
    last = await reader.get_event_by_id(run_id, "evt-3-1")
    assert last is not None and last.tick == 3
    assert await reader.get_event_by_id(run_id, "evt-3-1", through_tick=Tick(2)) is None
    latest = await reader.get_latest_event(run_id, through_tick=Tick(2))
    assert latest is not None and latest.sequence == 2

    snapshot = await reader.get_latest_at_or_before(run_id, Tick(3))
    assert snapshot is not None and snapshot.next_tick == Tick(0)
    final = await reader.get_snapshot(SnapshotId("snap-4"))
    assert final is not None and final.next_tick == Tick(4)
    assert len(await reader.list_snapshots(run_id)) == 2


@pytest.mark.asyncio
async def test_retry_is_idempotent_and_uncommitted_archive_is_hidden(
    tmp_path: Path,
) -> None:
    first = await _publish(tmp_path / "archive")
    second = await _publish(tmp_path / "archive")
    assert first.archive_id == second.archive_id
    reader = create_history_archive_reader(tmp_path / "archive")
    state_path = next((tmp_path / "archive" / "runs").glob("*/state.json"))
    original = state_path.read_bytes()
    state = json.loads(original)
    assert state["schema_version"] == ARCHIVE_STATE_SCHEMA
    state_path.unlink()
    assert reader.get_manifest(RunId("run-archive")) is None
    assert await reader.get_run(RunId("run-archive")) is None
    state_path.write_bytes(original)
    assert reader.get_manifest(RunId("run-archive")) is not None


@pytest.mark.asyncio
async def test_wrong_run_missing_segment_and_append_are_rejected(
    tmp_path: Path,
) -> None:
    manifest = await _publish(tmp_path / "archive")
    reader = create_history_archive_reader(tmp_path / "archive")
    assert await reader.get_run(RunId("other-run")) is None
    assert await reader.get_event_by_id(RunId("other-run"), "evt-0-0") is None
    with pytest.raises(HistoryArchiveError):
        await reader.append_tick(object())

    segment = manifest.commit_segments[-1]
    (tmp_path / "archive" / segment.path).unlink()
    with pytest.raises(HistoryArchiveError):
        await reader.get_latest_tick_commit(RunId("run-archive"))

    fresh = create_history_archive_reader(tmp_path / "archive")
    with pytest.raises(HistoryArchiveError):
        await fresh.get_latest_tick_commit(RunId("run-archive"))


@pytest.mark.asyncio
async def test_conflicting_publication_same_head_is_rejected(tmp_path: Path) -> None:
    await _publish(tmp_path / "archive")
    manifest = _run_manifest()
    commits = _commits("run-archive")
    other_events = tuple(
        _event(run_id="run-archive", tick=0, sequence=sequence) for sequence in range(2)
    )
    writer = create_history_archive_writer(tmp_path / "archive")
    with pytest.raises(HistoryArchiveError) as error:
        await writer.publish(
            run_manifest=manifest,
            pinned_head=_pinned(commits),
            commits=_iterator(commits),
            events=_iterator(other_events),
            snapshots=_iterator(
                (
                    _snapshot(
                        run_id="run-archive",
                        next_tick=0,
                        revision=0,
                        predecessor=None,
                    ),
                )
            ),
        )
    assert error.value.code == "history_archive_publication_conflict"


@pytest.mark.asyncio
async def test_auxiliary_copy_and_explicit_omissions(tmp_path: Path) -> None:
    auxiliary = tmp_path / "trace.json"
    auxiliary.write_text('{"trace":true}\n', encoding="utf-8")
    manifest = await _publish(
        tmp_path / "archive",
        auxiliary=(
            ArchiveAuxiliarySource(
                name="cognition-trace",
                capability_class="subjective",
                path=str(auxiliary),
            ),
        ),
    )
    assert len(manifest.auxiliary) == 1
    assert manifest.auxiliary[0].availability == "copied"
    assert {item.kind for item in manifest.omitted} == {
        "cognition_trace",
        "subjective_state",
        "scientific_evidence",
    }
    assert all(item.available is False for item in manifest.omitted)
    reader = create_history_archive_reader(tmp_path / "archive")
    payload = reader._read_object(manifest.auxiliary[0].digest)
    assert payload == auxiliary.read_bytes()
    assert reader.verify_storage(RunId("run-archive"))[0] >= 1


@pytest.mark.asyncio
async def test_verify_archive_and_corruption(tmp_path: Path) -> None:
    from research_runner.history_archive_composition import verify_history_archive

    archive = await _publish(tmp_path / "archive", split_tick=True)
    results = await verify_history_archive(tmp_path / "archive", full=True)
    assert len(results) == 1
    assert results[0].archive_id == archive.archive_id
    assert results[0].event_count == 9
    assert results[0].commit_count == 4
    assert set(results[0].replay_boundaries) == {0, 4}

    segment = archive.event_segments[0]
    path = tmp_path / "archive" / segment.path
    payload = bytearray(path.read_bytes())
    payload[0] = ord("{") if payload[0] != ord("{") else ord("[")
    path.write_bytes(bytes(payload))
    with pytest.raises(HistoryArchiveError):
        await verify_history_archive(tmp_path / "archive")


def test_history_verify_cli_success_and_tamper(tmp_path: Path) -> None:
    import asyncio

    from research_runner.cli import main

    asyncio.run(_publish(tmp_path / "archive", split_tick=True))
    assert main(["history-verify", "--archive", str(tmp_path / "archive")]) == 0
    archive = asyncio.run(_publish(tmp_path / "archive", split_tick=True))
    segment = archive.event_segments[0]
    path = tmp_path / "archive" / segment.path
    payload = bytearray(path.read_bytes())
    payload[0] = ord("{") if payload[0] != ord("{") else ord("[")
    path.write_bytes(bytes(payload))
    assert main(["history-verify", "--archive", str(tmp_path / "archive")]) == 2


@pytest.mark.asyncio
async def test_storage_verification_detects_tampered_event_object(
    tmp_path: Path,
) -> None:
    manifest = await _publish(tmp_path / "archive")
    reader = create_history_archive_reader(tmp_path / "archive")
    assert reader.verify_storage(RunId("run-archive"))[2] == 8
    segment = manifest.event_segments[1]
    path = tmp_path / "archive" / segment.path
    payload = bytearray(path.read_bytes())
    payload[0] = ord("{") if payload[0] != ord("{") else ord("[")
    path.write_bytes(bytes(payload))
    with pytest.raises(HistoryArchiveError):
        reader.verify_storage(RunId("run-archive"))


class _FakeRuns:
    def __init__(self, manifest: RunManifest) -> None:
        self._manifest = manifest

    async def get_run(self, run_id: RunId) -> RunManifest | None:
        return self._manifest if run_id == self._manifest.run_id else None


class _FakeJournal:
    def __init__(
        self, commits: tuple[TickCommit, ...], events: tuple[WorldEvent, ...]
    ) -> None:
        self._commits = commits
        self._events = events

    async def get_latest_tick_commit(
        self, run_id: RunId, *, through_tick: Tick | None = None
    ) -> TickCommit | None:
        rows = [
            item
            for item in self._commits
            if item.run_id == run_id
            and (through_tick is None or item.tick.value <= through_tick.value)
        ]
        return rows[-1] if rows else None

    async def get_latest_event(
        self, run_id: RunId, *, through_tick: Tick | None = None
    ) -> WorldEvent | None:
        rows = [
            item
            for item in self._events
            if item.run_id == run_id.value
            and (through_tick is None or item.tick <= through_tick.value)
        ]
        return rows[-1] if rows else None

    async def get_tick_commit(self, run_id: RunId, tick: Tick) -> TickCommit | None:
        for item in self._commits:
            if item.run_id == run_id and item.tick == tick:
                return item
        return None

    async def list_tick_commits_keyset(
        self,
        run_id: RunId,
        *,
        after_tick: Tick,
        through_tick: Tick | None,
        limit: int,
    ) -> tuple[TickCommit, ...]:
        rows = [
            item
            for item in self._commits
            if item.run_id == run_id
            and item.tick.value > after_tick.value
            and (through_tick is None or item.tick.value <= through_tick.value)
        ]
        return tuple(rows[:limit])

    async def list_events_keyset(
        self,
        run_id: RunId,
        *,
        after_tick: int,
        after_sequence: int,
        to_tick: Tick | None,
        limit: int,
    ) -> tuple[WorldEvent, ...]:
        rows = [
            item
            for item in self._events
            if item.run_id == run_id.value
            and (item.tick, item.sequence) > (after_tick, after_sequence)
            and (to_tick is None or item.tick <= to_tick.value)
        ]
        return tuple(rows[:limit])


class _FakeSnapshots:
    def __init__(self, snapshots: tuple[WorldSnapshot, ...]) -> None:
        self._snapshots = snapshots

    async def list_snapshots(self, run_id: RunId) -> tuple[WorldSnapshot, ...]:
        return tuple(item for item in self._snapshots if item.run_id == run_id)

    async def get_latest_at_or_before(
        self, run_id: RunId, tick: Tick
    ) -> WorldSnapshot | None:
        rows = [
            item
            for item in self._snapshots
            if item.run_id == run_id and item.next_tick.value <= tick.value
        ]
        return rows[-1] if rows else None


@pytest.mark.asyncio
async def test_export_composition_and_pinned_through_tick(tmp_path: Path) -> None:
    from research_runner.history_archive_composition import (
        export_history_archive,
        verify_history_archive,
    )

    run_id = RunId("run-archive")
    manifest = _run_manifest()
    commits = _commits("run-archive")
    events = tuple(
        _event(run_id="run-archive", tick=commit.tick.value, sequence=sequence)
        for commit in commits
        for sequence in range(commit.event_count)
    )
    snapshots = (
        _snapshot(run_id="run-archive", next_tick=0, revision=0, predecessor=None),
        _snapshot(
            run_id="run-archive",
            next_tick=2,
            revision=2,
            predecessor=commits[1].commit_hash,
        ),
        _snapshot(
            run_id="run-archive",
            next_tick=4,
            revision=4,
            predecessor=commits[3].commit_hash,
        ),
    )
    root = tmp_path / "archive"
    archive = await export_history_archive(
        runs=cast(Any, _FakeRuns(manifest)),
        journal=cast(Any, _FakeJournal(commits, events)),
        snapshots=cast(Any, _FakeSnapshots(snapshots)),
        root=root,
        run_id=run_id,
        through_tick=Tick(1),
    )
    assert archive.coverage.commit_count == 2
    assert archive.coverage.event_count == 4
    assert archive.coverage.snapshot_count == 2
    assert archive.coverage.last_tick == 1
    results = await verify_history_archive(root, full=True)
    assert results[0].verified_through_tick == 1
    assert results[0].replay_boundaries == (0, 2)


def test_trace_auxiliary_marks_omission_available() -> None:
    import persistence.history_archive_filesystem as module
    from simulation.history_archive import ArchiveAuxiliarySource

    without = {row.kind: row for row in module._omissions(())}
    assert without["cognition_trace"].available is False
    assert without["cognition_trace"].reason == "not_copied"
    with_trace = {
        row.kind: row
        for row in module._omissions(
            (
                ArchiveAuxiliarySource(
                    name="cognition-traces",
                    capability_class="cognition_trace",
                    path="/tmp/traces.jsonl",
                ),
            )
        )
    }
    assert with_trace["cognition_trace"].available is True
    assert with_trace["cognition_trace"].reason == "auxiliary_copy"
    assert with_trace["subjective_state"].available is False
