"""Composition for exporting and verifying offline objective-history archives."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any, Final, Protocol, cast

from persistence.history_archive_filesystem import (
    FilesystemHistoryArchiveReader,
    create_history_archive_reader,
    create_history_archive_writer,
)
from simulation.clock import Tick
from simulation.history_archive import (
    COMMIT_SEGMENT_BYTES,
    COMMIT_SEGMENT_ROWS,
    EVENT_SEGMENT_BYTES,
    EVENT_SEGMENT_ROWS,
    INDEX_SEGMENT_BYTES,
    INDEX_SEGMENT_ROWS,
    SNAPSHOT_SEGMENT_BYTES,
    SNAPSHOT_SEGMENT_ROWS,
    ArchiveAuxiliarySource,
    ArchiveManifest,
    ArchivePinnedHead,
    ArchiveVerification,
    HistoryArchiveError,
)
from simulation.journal import hash_snapshot, hash_tick_payload, verify_commit_chain
from simulation.models import RunId
from simulation.persistence import (
    BoundedTickJournalRepository,
    ReplayFallbackPolicy,
    ReplayRequest,
    ReplayStatus,
    RunManifest,
    SimulationRunRepository,
    SnapshotRepository,
    TickCommit,
    TickJournalRepository,
    WorldEvent,
    WorldSnapshot,
    resolve_durable_head,
)
from simulation.replay import ReplayService

_LOG: Final[logging.Logger] = logging.getLogger(
    "research_runner.history_archive_composition"
)


class _ExportJournal(BoundedTickJournalRepository, Protocol):
    async def get_tick_commit(self, run_id: RunId, tick: Tick) -> TickCommit | None: ...

    async def list_events_keyset(
        self,
        run_id: RunId,
        *,
        after_tick: int,
        after_sequence: int,
        to_tick: Tick | None,
        limit: int,
    ) -> tuple[WorldEvent, ...]: ...


_PAGE_SIZE: Final[int] = 500


async def export_history_archive(
    *,
    runs: SimulationRunRepository,
    journal: TickJournalRepository,
    snapshots: SnapshotRepository,
    root: Path | str,
    run_id: RunId,
    through_tick: Tick | None = None,
    auxiliary: Sequence[ArchiveAuxiliarySource] = (),
    event_segment_rows: int = EVENT_SEGMENT_ROWS,
    event_segment_bytes: int = EVENT_SEGMENT_BYTES,
    commit_segment_rows: int = COMMIT_SEGMENT_ROWS,
    commit_segment_bytes: int = COMMIT_SEGMENT_BYTES,
    snapshot_segment_rows: int = SNAPSHOT_SEGMENT_ROWS,
    snapshot_segment_bytes: int = SNAPSHOT_SEGMENT_BYTES,
    index_segment_rows: int = INDEX_SEGMENT_ROWS,
    index_segment_bytes: int = INDEX_SEGMENT_BYTES,
) -> ArchiveManifest:
    """Copy one verified durable head into a sealed immutable archive."""
    if type(run_id) is not RunId:
        raise TypeError("run_id must be RunId")
    if through_tick is not None and type(through_tick) is not Tick:
        raise TypeError("through_tick must be Tick or None")
    manifest = await runs.get_run(run_id)
    if manifest is None:
        raise HistoryArchiveError("history_archive_run_not_found")
    if not hasattr(journal, "get_tick_commit") or not hasattr(
        journal, "list_events_keyset"
    ):
        raise HistoryArchiveError("history_archive_bounded_journal_required")
    bounded = cast(_ExportJournal, journal)
    head = await resolve_durable_head(runs, journal, run_id, through_tick=through_tick)
    pinned = ArchivePinnedHead(
        next_tick=head.next_tick.value,
        revision=head.revision.value,
        last_commit_hash=(
            None if head.last_commit_hash is None else head.last_commit_hash.value
        ),
        latest_event_tick=(
            None if head.latest_event_tick is None else head.latest_event_tick.value
        ),
        latest_event_sequence=head.latest_event_sequence,
    )
    writer = create_history_archive_writer(
        root,
        event_segment_rows=event_segment_rows,
        event_segment_bytes=event_segment_bytes,
        commit_segment_rows=commit_segment_rows,
        commit_segment_bytes=commit_segment_bytes,
        snapshot_segment_rows=snapshot_segment_rows,
        snapshot_segment_bytes=snapshot_segment_bytes,
        index_segment_rows=index_segment_rows,
        index_segment_bytes=index_segment_bytes,
    )
    _LOG.info(
        "history_archive_export_started run_id=%s next_tick=%s revision=%s",
        run_id.value,
        head.next_tick.value,
        head.revision.value,
    )
    archive = await writer.publish(
        run_manifest=manifest,
        pinned_head=pinned,
        commits=_iter_commits(bounded, run_id, head.next_tick),
        events=_iter_events(bounded, run_id, head.next_tick),
        snapshots=_iter_snapshots(snapshots, run_id, manifest, pinned.next_tick),
        auxiliary=auxiliary,
    )
    _LOG.info(
        "history_archive_export_completed run_id=%s archive_id=%s "
        "commits=%s events=%s snapshots=%s",
        run_id.value,
        archive.archive_id,
        archive.coverage.commit_count,
        archive.coverage.event_count,
        archive.coverage.snapshot_count,
    )
    return archive


async def _iter_commits(
    journal: _ExportJournal,
    run_id: RunId,
    next_tick: Tick,
) -> AsyncIterator[TickCommit]:
    if next_tick.value == 0:
        return
    through = Tick(next_tick.value - 1)
    first = await journal.get_tick_commit(run_id, Tick(0))
    if first is not None:
        yield first
    cursor = Tick(0)
    while True:
        page = await journal.list_tick_commits_keyset(
            run_id,
            after_tick=cursor,
            through_tick=through,
            limit=_PAGE_SIZE,
        )
        if not page:
            return
        for commit in page:
            if commit.tick.value > through.value:
                return
            yield commit
        cursor = page[-1].tick
        if len(page) < _PAGE_SIZE:
            return


async def _iter_events(
    journal: _ExportJournal,
    run_id: RunId,
    next_tick: Tick,
) -> AsyncIterator[WorldEvent]:
    if next_tick.value == 0:
        return
    through = Tick(next_tick.value - 1)
    after_tick = 0
    after_sequence = -1
    while True:
        page = await journal.list_events_keyset(
            run_id,
            after_tick=after_tick,
            after_sequence=after_sequence,
            to_tick=through,
            limit=_PAGE_SIZE,
        )
        if not page:
            return
        for event in page:
            yield event
        last = page[-1]
        after_tick = last.tick
        after_sequence = last.sequence
        if len(page) < _PAGE_SIZE:
            return


async def _iter_snapshots(
    snapshots: SnapshotRepository,
    run_id: RunId,
    manifest: RunManifest,
    next_tick: int,
) -> AsyncIterator[WorldSnapshot]:
    lister = getattr(snapshots, "list_snapshots", None)
    rows: tuple[WorldSnapshot, ...]
    if callable(lister):
        rows = tuple(await lister(run_id))
    else:
        head = await snapshots.get_latest_at_or_before(run_id, Tick(1 << 62))
        rows = () if head is None else (head,)
    seen: set[str] = set()
    for snapshot in sorted(rows, key=lambda item: item.next_tick.value):
        if type(snapshot) is not WorldSnapshot:
            raise HistoryArchiveError("history_archive_snapshot_corrupt")
        if snapshot.run_id != run_id:
            raise HistoryArchiveError("history_archive_run_mismatch")
        if snapshot.next_tick.value > next_tick:
            continue
        if (
            snapshot.event_schema_version != manifest.event_schema_version
            or snapshot.projector_version != manifest.projector_version
            or snapshot.persistence_codec_version != manifest.persistence_codec_version
            or snapshot.derivation_version != manifest.derivation_version
        ):
            continue
        if snapshot.snapshot_id.value in seen:
            continue
        seen.add(snapshot.snapshot_id.value)
        yield snapshot


async def verify_history_archive(
    root: Path | str,
    *,
    run_id: RunId | None = None,
    full: bool = False,
    sample: int = 3,
) -> tuple[ArchiveVerification, ...]:
    """Validate hashes, identity, coverage and sampled objective replay."""
    if type(full) is not bool:
        raise TypeError("full must be bool")
    if isinstance(sample, bool) or type(sample) is not int or sample < 1:
        raise ValueError("sample must be a positive int")
    reader = create_history_archive_reader(root)
    manifests = reader.committed_manifests()
    if run_id is not None:
        manifests = tuple(item for item in manifests if item.run_id == run_id.value)
    if not manifests:
        raise HistoryArchiveError("history_archive_missing")
    results: list[ArchiveVerification] = []
    for manifest in manifests:
        results.append(
            await _verify_manifest(
                reader,
                manifest,
                full=full,
                sample=sample,
            )
        )
    return tuple(results)


async def _verify_manifest(
    reader: FilesystemHistoryArchiveReader,
    manifest: ArchiveManifest,
    *,
    full: bool,
    sample: int,
) -> ArchiveVerification:
    run_id = RunId(manifest.run_id)
    run_manifest = await reader.get_run(run_id)
    if run_manifest is None:
        raise HistoryArchiveError("history_archive_corrupt")
    _verify_identity(manifest, run_manifest)
    _verify_layout(manifest)
    segment_count, commits_count, events_count, snapshots_count = reader.verify_storage(
        run_id
    )
    if (
        commits_count != manifest.coverage.commit_count
        or events_count != manifest.coverage.event_count
        or snapshots_count != manifest.coverage.snapshot_count
    ):
        raise HistoryArchiveError("history_archive_coverage_mismatch")
    commits = await reader.list_tick_commits(run_id, from_tick=Tick(0), to_tick=None)
    events = await reader.list_events(
        run_id, from_tick=Tick(0), to_tick=None, limit=1 << 31, offset=0
    )
    snapshots = await reader.list_snapshots(run_id)
    if (
        len(commits) != manifest.coverage.commit_count
        or len(events) != manifest.coverage.event_count
        or len(snapshots) != manifest.coverage.snapshot_count
    ):
        raise HistoryArchiveError("history_archive_coverage_mismatch")
    _verify_commits(manifest, commits)
    _verify_events(manifest, commits, events)
    _verify_snapshots(manifest, commits, snapshots)
    _verify_coverage(manifest, commits, events, snapshots)
    boundaries = _replay_boundaries(snapshots, manifest, full=full, sample=sample)
    if boundaries:
        await _verify_replay(reader, run_id, boundaries)
    return ArchiveVerification(
        archive_id=manifest.archive_id,
        run_id=manifest.run_id,
        full=full,
        segment_count=segment_count,
        event_count=events_count,
        commit_count=commits_count,
        snapshot_count=snapshots_count,
        auxiliary_count=len(manifest.auxiliary),
        replay_boundaries=boundaries,
        verified_through_tick=manifest.pinned_head.next_tick - 1
        if manifest.pinned_head.next_tick > 0
        else None,
    )


def _verify_identity(manifest: ArchiveManifest, run_manifest: RunManifest) -> None:
    if (
        manifest.run_id != run_manifest.run_id.value
        or manifest.world_id != run_manifest.world_id.value
        or manifest.seed != run_manifest.seed
        or manifest.derivation_version != run_manifest.derivation_version
        or manifest.event_schema_version != run_manifest.event_schema_version
        or manifest.projector_version != run_manifest.projector_version
        or manifest.persistence_codec_version != run_manifest.persistence_codec_version
    ):
        raise HistoryArchiveError("history_archive_identity_mismatch")


def _verify_layout(manifest: ArchiveManifest) -> None:
    commit_ranges = [
        (segment.first_tick, segment.last_tick) for segment in manifest.commit_segments
    ]
    _require_nonoverlapping(commit_ranges, "commit")
    event_ranges = [
        (
            (segment.first_tick, segment.first_sequence or 0),
            (segment.last_tick, segment.last_sequence or 0),
        )
        for segment in manifest.event_segments
    ]
    _require_nonoverlapping(event_ranges, "event")
    snapshot_ranges = [
        (segment.first_tick, segment.last_tick)
        for segment in manifest.snapshot_segments
    ]
    _require_nonoverlapping(snapshot_ranges, "snapshot")
    _require_nonoverlapping(
        [
            (segment.first_key, segment.last_key)
            for segment in manifest.event_index_segments
        ],
        "event index",
    )
    _require_nonoverlapping(
        [
            (segment.first_key, segment.last_key)
            for segment in manifest.snapshot_index_segments
        ],
        "snapshot index",
    )


def _require_nonoverlapping(ranges: Sequence[tuple[Any, Any]], name: str) -> None:
    previous: Any = None
    for first, last in ranges:
        if previous is not None and first <= previous:
            raise HistoryArchiveError(f"history_archive_{name}_order_corrupt")
        if last < first:
            raise HistoryArchiveError(f"history_archive_{name}_order_corrupt")
        previous = last


def _verify_commits(manifest: ArchiveManifest, commits: Sequence[TickCommit]) -> None:
    for commit in commits:
        if commit.run_id.value != manifest.run_id:
            raise HistoryArchiveError("history_archive_run_mismatch")
    if not commits:
        if manifest.pinned_head.last_commit_hash is not None:
            raise HistoryArchiveError("history_archive_coverage_mismatch")
        return
    try:
        verify_commit_chain(commits)
    except (TypeError, ValueError) as exc:
        raise HistoryArchiveError("history_archive_commit_chain_corrupt") from exc
    last = commits[-1]
    if (
        last.commit_hash.value != manifest.pinned_head.last_commit_hash
        or last.tick.value + 1 != manifest.pinned_head.next_tick
        or last.resulting_revision.value != manifest.pinned_head.revision
    ):
        raise HistoryArchiveError("history_archive_head_mismatch")


def _verify_events(
    manifest: ArchiveManifest,
    commits: Sequence[TickCommit],
    events: Sequence[WorldEvent],
) -> None:
    by_tick: dict[int, list[WorldEvent]] = {}
    previous: tuple[int, int] | None = None
    for event in events:
        if (
            event.run_id != manifest.run_id
            or event.world_id.value != manifest.world_id
            or event.schema_version != manifest.event_schema_version
        ):
            raise HistoryArchiveError("history_archive_identity_mismatch")
        key = (event.tick, event.sequence)
        if previous is not None and key <= previous:
            raise HistoryArchiveError("history_archive_event_order_corrupt")
        previous = key
        by_tick.setdefault(event.tick, []).append(event)
    commit_ticks = {commit.tick.value for commit in commits}
    if set(by_tick) - commit_ticks:
        raise HistoryArchiveError("history_archive_event_without_commit")
    for commit in commits:
        tick_events = tuple(by_tick.get(commit.tick.value, ()))
        if len(tick_events) != commit.event_count:
            raise HistoryArchiveError("history_archive_event_count_mismatch")
        if hash_tick_payload(tick_events) != commit.payload_hash:
            raise HistoryArchiveError("history_archive_payload_mismatch")
    if events:
        last = events[-1]
        if (
            last.tick != manifest.pinned_head.latest_event_tick
            or last.sequence != manifest.pinned_head.latest_event_sequence
        ):
            raise HistoryArchiveError("history_archive_head_mismatch")
    elif manifest.pinned_head.latest_event_tick is not None:
        raise HistoryArchiveError("history_archive_head_mismatch")


def _verify_snapshots(
    manifest: ArchiveManifest,
    commits: Sequence[TickCommit],
    snapshots: Sequence[WorldSnapshot],
) -> None:
    commit_by_tick = {commit.tick.value: commit for commit in commits}
    previous: int | None = None
    for snapshot in snapshots:
        if (
            snapshot.run_id.value != manifest.run_id
            or snapshot.world_id.value != manifest.world_id
        ):
            raise HistoryArchiveError("history_archive_identity_mismatch")
        if previous is not None and snapshot.next_tick.value <= previous:
            raise HistoryArchiveError("history_archive_snapshot_order_corrupt")
        previous = snapshot.next_tick.value
        if hash_snapshot(snapshot) != snapshot.integrity_hash:
            raise HistoryArchiveError("history_archive_snapshot_corrupt")
        if (
            snapshot.event_schema_version != manifest.event_schema_version
            or snapshot.projector_version != manifest.projector_version
            or snapshot.persistence_codec_version != manifest.persistence_codec_version
            or snapshot.derivation_version != manifest.derivation_version
        ):
            raise HistoryArchiveError("history_archive_identity_mismatch")
        if snapshot.next_tick.value > manifest.pinned_head.next_tick:
            raise HistoryArchiveError("history_archive_snapshot_beyond_head")
        if snapshot.next_tick.value == 0:
            if snapshot.predecessor_commit_hash is not None:
                raise HistoryArchiveError("history_archive_snapshot_corrupt")
            continue
        commit = commit_by_tick.get(snapshot.next_tick.value - 1)
        if commit is None:
            if manifest.pinned_head.next_tick > snapshot.next_tick.value:
                raise HistoryArchiveError("history_archive_snapshot_corrupt")
            continue
        if snapshot.predecessor_commit_hash != commit.commit_hash:
            raise HistoryArchiveError("history_archive_snapshot_corrupt")


def _verify_coverage(
    manifest: ArchiveManifest,
    commits: Sequence[TickCommit],
    events: Sequence[WorldEvent],
    snapshots: Sequence[WorldSnapshot],
) -> None:
    first: int | None = None
    last: int | None = None
    for value in (
        (commit.tick.value for commit in commits),
        (event.tick for event in events),
    ):
        for tick in value:
            first = tick if first is None else min(first, tick)
            last = tick if last is None else max(last, tick)
    expected = manifest.coverage
    if (
        expected.first_tick != first
        or expected.last_tick != last
        or expected.commit_count != len(commits)
        or expected.event_count != len(events)
        or expected.snapshot_count != len(snapshots)
    ):
        raise HistoryArchiveError("history_archive_coverage_mismatch")


def _replay_boundaries(
    snapshots: Sequence[WorldSnapshot],
    manifest: ArchiveManifest,
    *,
    full: bool,
    sample: int,
) -> tuple[int, ...]:
    ticks = sorted(
        {
            snapshot.next_tick.value
            for snapshot in snapshots
            if snapshot.next_tick.value <= manifest.pinned_head.next_tick
        }
    )
    if manifest.pinned_head.next_tick not in ticks:
        ticks.append(manifest.pinned_head.next_tick)
    if full or len(ticks) <= sample:
        return tuple(ticks)
    indexes = {
        0,
        len(ticks) // 2,
        len(ticks) - 1,
    }
    if sample > 3:
        step = max(1, (len(ticks) - 1) // (sample - 1))
        indexes.update(range(0, len(ticks), step))
    return tuple(sorted({ticks[index] for index in indexes if index < len(ticks)}))


async def _verify_replay(
    reader: FilesystemHistoryArchiveReader,
    run_id: RunId,
    boundaries: Sequence[int],
) -> None:
    service = ReplayService(reader, reader, reader)
    for boundary in boundaries:
        outcome = await service.replay(
            ReplayRequest(
                run_id=run_id,
                target_tick=Tick(boundary),
                fallback_policy=ReplayFallbackPolicy.LATEST_AT_OR_BEFORE,
            )
        )
        if outcome.result.status is not ReplayStatus.OK:
            raise HistoryArchiveError("history_archive_replay_mismatch")
        _LOG.debug(
            "history_archive_replay_verified run_id=%s target_tick=%s "
            "events_applied=%s",
            run_id.value,
            boundary,
            outcome.result.events_applied,
        )


__all__ = ["export_history_archive", "verify_history_archive"]


async def export_cognition_trace_auxiliary(
    *,
    traces: object,
    run_id: RunId,
    path: Path,
    max_invocations: int | None = None,
) -> ArchiveAuxiliarySource:
    """Write a read-only canonical trace artifact for cold-copy archiving.

    Trace rows remain outside scientific history and are never deleted. The
    resulting auxiliary is copied unchanged by the archive writer and declared
    as an available cognition-trace artifact rather than a silent omission.
    """
    from simulation.cognition_trace import (
        CognitionTraceRepository,
        iter_cognition_trace_invocations,
    )
    from simulation.cognition_trace_serialization import (
        encode_cognition_trace_invocation,
    )

    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")
    if max_invocations is not None and max_invocations < 0:
        raise ValueError("max_invocations must be non-negative or None")
    repository = traces
    if not hasattr(repository, "list_invocations"):
        raise TypeError("traces must implement CognitionTraceRepository")
    typed = cast(CognitionTraceRepository, repository)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    count = 0
    byte_count = 0
    try:
        with temporary.open("wb") as handle:
            async for invocation in iter_cognition_trace_invocations(
                typed,
                run_id=run_id,
                page_size=250,
                max_invocations=max_invocations,
            ):
                line = encode_cognition_trace_invocation(invocation)
                handle.write(line)
                handle.write(b"\n")
                count += 1
                byte_count += len(line) + 1
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    _LOG.info(
        "cognition_trace_auxiliary_exported run_id=%s invocation_count=%s "
        "byte_count=%s",
        run_id.value,
        count,
        byte_count,
    )
    return ArchiveAuxiliarySource(
        name="cognition-traces",
        capability_class="cognition_trace",
        path=str(target),
    )
