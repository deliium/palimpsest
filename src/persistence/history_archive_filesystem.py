"""Content-addressed filesystem writer and read-only adapter for history archives.

Objects and manifests are written before one atomic run-state reference. A
reader never discovers uncommitted files and never appends to the copy. The
archive stays a queryable copy; SQL remains the authoritative journal.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from simulation.clock import Tick
from simulation.history_archive import (
    ARCHIVE_AUXILIARY_MAX_BYTES,
    ARCHIVE_INDEX_SCHEMA,
    ARCHIVE_MANIFEST_MAX_BYTES,
    ARCHIVE_RECORD_MAX_BYTES,
    ARCHIVE_SEGMENT_SCHEMA,
    ARCHIVE_STATE_SCHEMA,
    COMMIT_SEGMENT_BYTES,
    COMMIT_SEGMENT_ROWS,
    EVENT_SEGMENT_BYTES,
    EVENT_SEGMENT_ROWS,
    INDEX_SEGMENT_BYTES,
    INDEX_SEGMENT_ROWS,
    SNAPSHOT_SEGMENT_BYTES,
    SNAPSHOT_SEGMENT_ROWS,
    ArchiveAuxiliary,
    ArchiveAuxiliarySource,
    ArchiveCoverage,
    ArchiveIndexSegment,
    ArchiveManifest,
    ArchiveOmission,
    ArchivePinnedHead,
    ArchiveSegment,
    HistoryArchiveError,
    archive_digest,
    archive_manifest_id,
    archive_object_path,
    canonical_archive_bytes,
    source_manifest_digest,
)
from simulation.journal import (
    decode_persistence,
    encode_persistence,
    hash_snapshot,
)
from simulation.models import RunId
from simulation.persistence import (
    RunManifest,
    TickCommit,
    WorldEvent,
    WorldSnapshot,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "persistence.history_archive_filesystem"
)

_STATE_MAX_BYTES: Final[int] = 16 * 1024
_OMISSIONS: Final[tuple[ArchiveOmission, ...]] = (
    ArchiveOmission("cognition_trace", False, "not_copied"),
    ArchiveOmission("subjective_state", False, "not_copied"),
    ArchiveOmission("scientific_evidence", False, "not_copied"),
)


def _canonical(value: object) -> bytes:
    return canonical_archive_bytes(value)


def _decode_document(payload: bytes, *, max_bytes: int) -> object:
    if len(payload) > max_bytes:
        raise HistoryArchiveError("history_archive_metadata_too_large")
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise HistoryArchiveError("history_archive_corrupt") from exc


def _safe_root(root: Path, *, create: bool) -> Path:
    if root.exists() and root.is_symlink():
        raise HistoryArchiveError("history_archive_path_violation")
    if create:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        return root.resolve()
    if not root.exists():
        raise HistoryArchiveError("history_archive_missing")
    return root.resolve()


def _safe_path(root: Path, *parts: str) -> Path:
    current = root
    for part in parts:
        if (
            type(part) is not str
            or not part
            or part in {".", ".."}
            or "/" in part
            or "\\" in part
        ):
            raise HistoryArchiveError("history_archive_path_violation")
        current = current / part
        if current.is_symlink():
            raise HistoryArchiveError("history_archive_path_violation")
    resolved = current.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise HistoryArchiveError("history_archive_path_violation")
    return resolved


def _atomic_write(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.tmp")
    descriptor = os.open(
        temporary,
        os.O_CREAT | os.O_TRUNC | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


@contextmanager
def _locked(run_root: Path) -> Iterator[None]:
    run_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = run_root / "writer.lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _run_root(root: Path, run_id: RunId) -> Path:
    if type(run_id) is not RunId:
        raise TypeError("run_id must be RunId")
    return _safe_path(root, "runs", hashlib.sha256(run_id.value.encode()).hexdigest())


def _positive(name: str, value: object, maximum: int | None = None) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive int")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} exceeds the supported maximum")
    return value


@dataclass(frozen=True, slots=True)
class _State:
    run_id: RunId
    committed_archive_id: str
    manifest_digest: str
    source_manifest_digest: str

    def payload(self) -> dict[str, object]:
        return {
            "committed_archive_id": self.committed_archive_id,
            "manifest_digest": self.manifest_digest,
            "run_id": self.run_id.value,
            "schema_version": ARCHIVE_STATE_SCHEMA,
            "source_manifest_digest": self.source_manifest_digest,
        }


def _state_payload(state: _State) -> bytes:
    payload = _canonical(state.payload())
    if len(payload) > _STATE_MAX_BYTES:
        raise HistoryArchiveError("history_archive_metadata_too_large")
    return payload


def _parse_state(payload: object) -> _State:
    if type(payload) is not dict:
        raise HistoryArchiveError("history_archive_corrupt")
    if set(payload) != {
        "committed_archive_id",
        "manifest_digest",
        "run_id",
        "schema_version",
        "source_manifest_digest",
    }:
        raise HistoryArchiveError("history_archive_corrupt")
    if payload["schema_version"] != ARCHIVE_STATE_SCHEMA:
        raise HistoryArchiveError("history_archive_corrupt")
    try:
        return _State(
            run_id=RunId(str(payload["run_id"])),
            committed_archive_id=str(payload["committed_archive_id"]),
            manifest_digest=str(payload["manifest_digest"]),
            source_manifest_digest=str(payload["source_manifest_digest"]),
        )
    except (TypeError, ValueError) as exc:
        raise HistoryArchiveError("history_archive_corrupt") from exc


class FilesystemHistoryArchiveWriter:
    """Single-writer immutable archive publisher."""

    __slots__ = (
        "_commit_bytes",
        "_commit_rows",
        "_event_bytes",
        "_event_rows",
        "_index_bytes",
        "_index_rows",
        "_root",
        "_snapshot_bytes",
        "_snapshot_rows",
    )

    def __init__(
        self,
        root: Path | str,
        *,
        event_segment_rows: int = EVENT_SEGMENT_ROWS,
        event_segment_bytes: int = EVENT_SEGMENT_BYTES,
        commit_segment_rows: int = COMMIT_SEGMENT_ROWS,
        commit_segment_bytes: int = COMMIT_SEGMENT_BYTES,
        snapshot_segment_rows: int = SNAPSHOT_SEGMENT_ROWS,
        snapshot_segment_bytes: int = SNAPSHOT_SEGMENT_BYTES,
        index_segment_rows: int = INDEX_SEGMENT_ROWS,
        index_segment_bytes: int = INDEX_SEGMENT_BYTES,
    ) -> None:
        self._root = _safe_root(Path(root), create=True)
        self._event_rows = _positive("event_segment_rows", event_segment_rows)
        self._event_bytes = _positive(
            "event_segment_bytes", event_segment_bytes, ARCHIVE_RECORD_MAX_BYTES
        )
        self._commit_rows = _positive("commit_segment_rows", commit_segment_rows)
        self._commit_bytes = _positive(
            "commit_segment_bytes", commit_segment_bytes, ARCHIVE_RECORD_MAX_BYTES
        )
        self._snapshot_rows = _positive("snapshot_segment_rows", snapshot_segment_rows)
        self._snapshot_bytes = _positive(
            "snapshot_segment_bytes", snapshot_segment_bytes, ARCHIVE_RECORD_MAX_BYTES
        )
        self._index_rows = _positive("index_segment_rows", index_segment_rows)
        self._index_bytes = _positive("index_segment_bytes", index_segment_bytes)

    async def publish(
        self,
        *,
        run_manifest: RunManifest,
        pinned_head: ArchivePinnedHead,
        commits: AsyncIterator[TickCommit],
        events: AsyncIterator[WorldEvent],
        snapshots: AsyncIterator[WorldSnapshot],
        auxiliary: Sequence[ArchiveAuxiliarySource] = (),
    ) -> ArchiveManifest:
        if type(run_manifest) is not RunManifest:
            raise TypeError("run_manifest must be RunManifest")
        if type(pinned_head) is not ArchivePinnedHead:
            raise TypeError("pinned_head must be ArchivePinnedHead")
        run_id = run_manifest.run_id
        run_root = _run_root(self._root, run_id)
        run_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with _locked(run_root):
            state = self._load_state(run_id)
            manifest = await self._build(
                run_manifest=run_manifest,
                pinned_head=pinned_head,
                commits=commits,
                events=events,
                snapshots=snapshots,
                auxiliary=auxiliary,
            )
            assert manifest.archive_id == archive_manifest_id(manifest)
            if state is not None:
                if state.committed_archive_id == manifest.archive_id:
                    existing = self._load_manifest(run_id, state.manifest_digest)
                    if existing.archive_id == manifest.archive_id:
                        return existing
                prior = self._load_manifest(run_id, state.manifest_digest)
                if (
                    prior.source_manifest_digest
                    == manifest.source_manifest_digest
                    and prior.pinned_head == manifest.pinned_head
                ):
                    raise HistoryArchiveError("history_archive_publication_conflict")
            manifest_bytes = _canonical(manifest.payload())
            if len(manifest_bytes) > ARCHIVE_MANIFEST_MAX_BYTES:
                raise HistoryArchiveError("history_archive_manifest_too_large")
            manifest_digest = archive_digest(manifest_bytes)
            manifest_path = _safe_path(
                self._root, "manifests", f"{manifest_digest}.json"
            )
            _atomic_write(manifest_path, manifest_bytes)
            new_state = _State(
                run_id=run_id,
                committed_archive_id=manifest.archive_id,
                manifest_digest=manifest_digest,
                source_manifest_digest=manifest.source_manifest_digest,
            )
            _atomic_write(run_root / "state.json", _state_payload(new_state))
            _LOG.info(
                "history_archive_published run_id=%s archive_id=%s "
                "commit_segments=%s event_segments=%s snapshot_segments=%s "
                "commits=%s events=%s snapshots=%s",
                run_id.value,
                manifest.archive_id,
                len(manifest.commit_segments),
                len(manifest.event_segments),
                len(manifest.snapshot_segments),
                manifest.coverage.commit_count,
                manifest.coverage.event_count,
                manifest.coverage.snapshot_count,
            )
            return manifest

    def _load_state(self, run_id: RunId) -> _State | None:
        path = _run_root(self._root, run_id) / "state.json"
        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            return None
        state = _parse_state(_decode_document(payload, max_bytes=_STATE_MAX_BYTES))
        if state.run_id != run_id:
            raise HistoryArchiveError("history_archive_corrupt")
        return state

    def _load_manifest(self, run_id: RunId, manifest_digest: str) -> ArchiveManifest:
        path = _safe_path(self._root, "manifests", f"{manifest_digest}.json")
        try:
            payload = path.read_bytes()
        except FileNotFoundError as exc:
            raise HistoryArchiveError("history_archive_missing") from exc
        if archive_digest(payload) != manifest_digest:
            raise HistoryArchiveError("history_archive_corrupt")
        manifest = _parse_manifest(payload)
        if manifest.run_id != run_id.value:
            raise HistoryArchiveError("history_archive_corrupt")
        return manifest

    async def _build(
        self,
        *,
        run_manifest: RunManifest,
        pinned_head: ArchivePinnedHead,
        commits: AsyncIterator[TickCommit],
        events: AsyncIterator[WorldEvent],
        snapshots: AsyncIterator[WorldSnapshot],
        auxiliary: Sequence[ArchiveAuxiliarySource],
    ) -> ArchiveManifest:
        run_id = run_manifest.run_id
        source_digest = source_manifest_digest(run_manifest)
        run_manifest_bytes = encode_persistence(run_manifest)
        _require_record_size("run_manifest", run_manifest_bytes)
        run_manifest_path, run_manifest_digest = self._write_object(run_manifest_bytes)

        commit_segments, _first, _last, commit_count = (
            await self._commit_lane(commits, run_id)
        )
        event_segments, event_index_segments, event_count, event_first, event_last = (
            await self._event_lane(events, run_id)
        )
        snapshot_segments, snapshot_index_segments, snapshot_count = (
            await self._snapshot_lane(snapshots, run_id)
        )
        auxiliary_rows = self._copy_auxiliary(auxiliary)

        first_covered = commit_first = _first_tick(commit_segments)
        last_covered = _last_tick(commit_segments)
        if event_first is not None:
            first_covered = (
                event_first
                if first_covered is None
                else min(first_covered, event_first)
            )
        if event_last is not None:
            last_covered = (
                event_last
                if last_covered is None
                else max(last_covered, event_last)
            )
        if commit_count:
            first_covered = commit_first if first_covered is None else first_covered
        coverage = ArchiveCoverage(
            first_tick=first_covered,
            last_tick=last_covered,
            commit_count=commit_count,
            event_count=event_count,
            snapshot_count=snapshot_count,
        )
        draft = ArchiveManifest(
            archive_id="0" * 64,
            source_manifest_digest=source_digest,
            run_manifest_digest=run_manifest_digest,
            run_manifest_path=run_manifest_path,
            run_id=run_id.value,
            world_id=run_manifest.world_id.value,
            seed=run_manifest.seed,
            derivation_version=run_manifest.derivation_version,
            event_schema_version=run_manifest.event_schema_version,
            projector_version=run_manifest.projector_version,
            persistence_codec_version=run_manifest.persistence_codec_version,
            pinned_head=pinned_head,
            commit_segments=commit_segments,
            event_segments=event_segments,
            snapshot_segments=snapshot_segments,
            event_index_segments=event_index_segments,
            snapshot_index_segments=snapshot_index_segments,
            auxiliary=auxiliary_rows,
            omitted=_OMISSIONS,
            coverage=coverage,
        )
        payload = draft.payload()
        payload["archive_id"] = archive_manifest_id(draft)
        return ArchiveManifest.from_payload(payload)

    async def _commit_lane(
        self, commits: AsyncIterator[TickCommit], run_id: RunId
    ) -> tuple[tuple[ArchiveSegment, ...], int | None, int | None, int]:
        segments: list[ArchiveSegment] = []
        buffer: list[TickCommit] = []
        encoded: list[bytes] = []
        size = 0
        count = 0
        first: int | None = None
        last: int | None = None

        def flush() -> None:
            nonlocal buffer, encoded, size
            content = b"".join(item + b"\n" for item in encoded)
            path, digest = self._write_object(content)
            segment = ArchiveSegment(
                schema_version=ARCHIVE_SEGMENT_SCHEMA,
                lane="commits",
                path=path,
                digest=digest,
                row_count=len(buffer),
                byte_count=len(content),
                first_tick=buffer[0].tick.value,
                last_tick=buffer[-1].tick.value,
                first_sequence=None,
                last_sequence=None,
                first_commit_hash=buffer[0].commit_hash.value,
                last_commit_hash=buffer[-1].commit_hash.value,
            )
            segments.append(segment)
            buffer = []
            encoded = []
            size = 0

        async for commit in commits:
            if type(commit) is not TickCommit:
                raise TypeError("commits must contain TickCommit")
            if commit.run_id != run_id:
                raise HistoryArchiveError("history_archive_run_mismatch")
            item = encode_persistence(commit)
            _require_record_size("commit", item)
            if buffer and (
                len(buffer) >= self._commit_rows
                or size + len(item) + 1 > self._commit_bytes
            ):
                flush()
            first = (
                commit.tick.value
                if first is None
                else min(first, commit.tick.value)
            )
            last = (
                commit.tick.value if last is None else max(last, commit.tick.value)
            )
            buffer.append(commit)
            encoded.append(item)
            size += len(item) + 1
            count += 1
        if buffer:
            flush()
        return tuple(segments), first, last, count

    async def _event_lane(
        self, events: AsyncIterator[WorldEvent], run_id: RunId
    ) -> tuple[
        tuple[ArchiveSegment, ...],
        tuple[ArchiveIndexSegment, ...],
        int,
        int | None,
        int | None,
    ]:
        segments: list[ArchiveSegment] = []
        buffer: list[WorldEvent] = []
        encoded: list[bytes] = []
        offsets: list[int] = []
        size = 0
        count = 0
        first: int | None = None
        last: int | None = None
        index_rows: list[dict[str, object]] = []

        def flush() -> None:
            nonlocal buffer, encoded, offsets, size
            content = b"".join(item + b"\n" for item in encoded)
            path, digest = self._write_object(content)
            segment = ArchiveSegment(
                schema_version=ARCHIVE_SEGMENT_SCHEMA,
                lane="events",
                path=path,
                digest=digest,
                row_count=len(buffer),
                byte_count=len(content),
                first_tick=buffer[0].tick,
                last_tick=buffer[-1].tick,
                first_sequence=buffer[0].sequence,
                last_sequence=buffer[-1].sequence,
                first_commit_hash=None,
                last_commit_hash=None,
            )
            segments.append(segment)
            for event, offset in zip(buffer, offsets, strict=True):
                index_rows.append(
                    {
                        "digest": digest,
                        "event_id": event.event_id.value,
                        "offset": offset,
                        "path": path,
                        "sequence": event.sequence,
                        "tick": event.tick,
                    }
                )
            buffer = []
            encoded = []
            offsets = []
            size = 0

        async for event in events:
            if type(event) is not WorldEvent:
                raise TypeError("events must contain WorldEvent")
            if event.run_id != run_id.value:
                raise HistoryArchiveError("history_archive_run_mismatch")
            item = encode_persistence(event)
            _require_record_size("event", item)
            if buffer and (
                len(buffer) >= self._event_rows
                or size + len(item) + 1 > self._event_bytes
            ):
                flush()
            first = event.tick if first is None else min(first, event.tick)
            last = event.tick if last is None else max(last, event.tick)
            buffer.append(event)
            encoded.append(item)
            offsets.append(size)
            size += len(item) + 1
            count += 1
        if buffer:
            flush()
        _require_unique_event_ids(index_rows)
        index_segments = self._write_index(index_rows, key="event_id")
        return tuple(segments), index_segments, count, first, last

    async def _snapshot_lane(
        self, snapshots: AsyncIterator[WorldSnapshot], run_id: RunId
    ) -> tuple[
        tuple[ArchiveSegment, ...], tuple[ArchiveIndexSegment, ...], int
    ]:
        segments: list[ArchiveSegment] = []
        buffer: list[WorldSnapshot] = []
        encoded: list[bytes] = []
        offsets: list[int] = []
        size = 0
        count = 0
        index_rows: list[dict[str, object]] = []

        def flush() -> None:
            nonlocal buffer, encoded, offsets, size
            content = b"".join(item + b"\n" for item in encoded)
            path, digest = self._write_object(content)
            segment = ArchiveSegment(
                schema_version=ARCHIVE_SEGMENT_SCHEMA,
                lane="snapshots",
                path=path,
                digest=digest,
                row_count=len(buffer),
                byte_count=len(content),
                first_tick=buffer[0].next_tick.value,
                last_tick=buffer[-1].next_tick.value,
                first_sequence=None,
                last_sequence=None,
                first_commit_hash=None,
                last_commit_hash=None,
            )
            segments.append(segment)
            for snapshot, offset in zip(buffer, offsets, strict=True):
                index_rows.append(
                    {
                        "digest": digest,
                        "offset": offset,
                        "path": path,
                        "snapshot_id": snapshot.snapshot_id.value,
                    }
                )
            buffer = []
            encoded = []
            offsets = []
            size = 0

        async for snapshot in snapshots:
            if type(snapshot) is not WorldSnapshot:
                raise TypeError("snapshots must contain WorldSnapshot")
            if snapshot.run_id != run_id:
                raise HistoryArchiveError("history_archive_run_mismatch")
            if hash_snapshot(snapshot) != snapshot.integrity_hash:
                raise HistoryArchiveError("history_archive_snapshot_corrupt")
            item = encode_persistence(snapshot)
            _require_record_size("snapshot", item)
            if buffer and (
                len(buffer) >= self._snapshot_rows
                or size + len(item) + 1 > self._snapshot_bytes
            ):
                flush()
            buffer.append(snapshot)
            encoded.append(item)
            offsets.append(size)
            size += len(item) + 1
            count += 1
        if buffer:
            flush()
        _require_unique_snapshot_ids(index_rows)
        index_segments = self._write_index(index_rows, key="snapshot_id")
        return tuple(segments), index_segments, count

    def _write_index(
        self, rows: Sequence[Mapping[str, object]], *, key: str
    ) -> tuple[ArchiveIndexSegment, ...]:
        ordered = sorted(rows, key=lambda item: str(item[key]))
        segments: list[ArchiveIndexSegment] = []
        buffer: list[Mapping[str, object]] = []
        encoded: list[bytes] = []
        size = 0

        def flush() -> None:
            nonlocal buffer, encoded, size
            content = b"".join(encoded)
            path, digest = self._write_object(content)
            segments.append(
                ArchiveIndexSegment(
                    schema_version=ARCHIVE_INDEX_SCHEMA,
                    path=path,
                    digest=digest,
                    row_count=len(buffer),
                    byte_count=len(content),
                    first_key=str(buffer[0][key]),
                    last_key=str(buffer[-1][key]),
                )
            )
            buffer = []
            encoded = []
            size = 0

        for row in ordered:
            item = _canonical(dict(row))
            _require_record_size("index", item)
            if buffer and (
                len(buffer) >= self._index_rows
                or size + len(item) > self._index_bytes
            ):
                flush()
            buffer.append(dict(row))
            encoded.append(item)
            size += len(item)
        if buffer:
            flush()
        return tuple(segments)

    def _copy_auxiliary(
        self, sources: Sequence[ArchiveAuxiliarySource]
    ) -> tuple[ArchiveAuxiliary, ...]:
        copied: list[ArchiveAuxiliary] = []
        names: set[str] = set()
        for source in sources:
            if type(source) is not ArchiveAuxiliarySource:
                raise TypeError("auxiliary entries must be ArchiveAuxiliarySource")
            if source.name in names:
                raise ValueError("auxiliary names must be unique")
            names.add(source.name)
            if source.capability_class not in {
                "objective",
                "subjective",
                "analysis",
            }:
                raise ValueError("unsupported auxiliary capability_class")
            path = Path(source.path)
            if path.is_symlink():
                raise HistoryArchiveError("history_archive_path_violation")
            try:
                content = path.read_bytes()
            except OSError as exc:
                raise HistoryArchiveError("history_archive_auxiliary_missing") from exc
            if len(content) > ARCHIVE_AUXILIARY_MAX_BYTES:
                raise HistoryArchiveError("history_archive_auxiliary_too_large")
            object_path, digest = self._write_object(content)
            if source.capability_class != "objective":
                target = _safe_path(self._root, *object_path.split("/"))
                os.chmod(target, 0o600)
            copied.append(
                ArchiveAuxiliary(
                    name=source.name,
                    capability_class=source.capability_class,
                    path=object_path,
                    digest=digest,
                    byte_count=len(content),
                    availability="copied",
                )
            )
        return tuple(copied)

    def _write_object(self, payload: bytes) -> tuple[str, str]:
        digest = archive_digest(payload)
        relative = archive_object_path(digest)
        target = _safe_path(self._root, *relative.split("/"))
        if target.exists():
            try:
                existing = target.read_bytes()
            except OSError as exc:
                raise HistoryArchiveError(
                    "history_archive_storage_unavailable"
                ) from exc
            if archive_digest(existing) != digest:
                raise HistoryArchiveError("history_archive_object_conflict")
            return relative, digest
        _atomic_write(target, payload)
        return relative, digest


def _parse_manifest(payload: bytes) -> ArchiveManifest:
    document = _decode_document(payload, max_bytes=ARCHIVE_MANIFEST_MAX_BYTES)
    try:
        manifest = ArchiveManifest.from_payload(document)
    except (TypeError, ValueError) as exc:
        raise HistoryArchiveError("history_archive_corrupt") from exc
    if archive_manifest_id(manifest) != manifest.archive_id:
        raise HistoryArchiveError("history_archive_manifest_digest_mismatch")
    return manifest


def _require_record_size(name: str, payload: bytes) -> None:
    if len(payload) > ARCHIVE_RECORD_MAX_BYTES:
        raise HistoryArchiveError(f"history_archive_{name}_too_large")


def _require_unique_event_ids(rows: Sequence[Mapping[str, object]]) -> None:
    seen: set[str] = set()
    for row in rows:
        key = str(row["event_id"])
        if key in seen:
            raise HistoryArchiveError("history_archive_duplicate_event_id")
        seen.add(key)


def _require_unique_snapshot_ids(rows: Sequence[Mapping[str, object]]) -> None:
    seen: set[str] = set()
    for row in rows:
        key = str(row["snapshot_id"])
        if key in seen:
            raise HistoryArchiveError("history_archive_duplicate_snapshot_id")
        seen.add(key)


def _verify_commit_descriptor(
    segment: ArchiveSegment, records: Sequence[object]
) -> None:
    if not records:
        raise HistoryArchiveError("history_archive_corrupt")
    first = records[0]
    last = records[-1]
    if (
        type(first) is not TickCommit
        or type(last) is not TickCommit
        or first.tick.value != segment.first_tick
        or last.tick.value != segment.last_tick
        or segment.first_sequence is not None
        or segment.last_sequence is not None
        or first.commit_hash.value != segment.first_commit_hash
        or last.commit_hash.value != segment.last_commit_hash
    ):
        raise HistoryArchiveError("history_archive_corrupt")
    previous: int | None = None
    for record in records:
        assert type(record) is TickCommit
        if previous is not None and record.tick.value <= previous:
            raise HistoryArchiveError("history_archive_corrupt")
        previous = record.tick.value


def _verify_event_descriptor(
    segment: ArchiveSegment, records: Sequence[object]
) -> None:
    if not records:
        raise HistoryArchiveError("history_archive_corrupt")
    first = records[0]
    last = records[-1]
    if (
        type(first) is not WorldEvent
        or type(last) is not WorldEvent
        or first.tick != segment.first_tick
        or last.tick != segment.last_tick
        or first.sequence != segment.first_sequence
        or last.sequence != segment.last_sequence
        or segment.first_commit_hash is not None
        or segment.last_commit_hash is not None
    ):
        raise HistoryArchiveError("history_archive_corrupt")
    previous: tuple[int, int] | None = None
    for record in records:
        assert type(record) is WorldEvent
        key = (record.tick, record.sequence)
        if previous is not None and key <= previous:
            raise HistoryArchiveError("history_archive_corrupt")
        previous = key


def _verify_snapshot_descriptor(
    segment: ArchiveSegment, records: Sequence[object]
) -> None:
    if not records:
        raise HistoryArchiveError("history_archive_corrupt")
    first = records[0]
    last = records[-1]
    if (
        type(first) is not WorldSnapshot
        or type(last) is not WorldSnapshot
        or first.next_tick.value != segment.first_tick
        or last.next_tick.value != segment.last_tick
        or segment.first_sequence is not None
        or segment.last_sequence is not None
        or segment.first_commit_hash is not None
        or segment.last_commit_hash is not None
    ):
        raise HistoryArchiveError("history_archive_corrupt")
    previous: int | None = None
    for record in records:
        assert type(record) is WorldSnapshot
        if previous is not None and record.next_tick.value <= previous:
            raise HistoryArchiveError("history_archive_corrupt")
        if hash_snapshot(record) != record.integrity_hash:
            raise HistoryArchiveError("history_archive_snapshot_corrupt")
        previous = record.next_tick.value


def _verify_index_references(
    rows: Sequence[Mapping[str, object]],
    segments: Mapping[str, ArchiveSegment],
    key: str,
) -> None:
    del key
    for row in rows:
        segment = segments.get(str(row.get("digest")))
        offset = row.get("offset")
        if (
            segment is None
            or isinstance(offset, bool)
            or type(offset) is not int
            or offset < 0
            or offset >= segment.byte_count
        ):
            raise HistoryArchiveError("history_archive_corrupt")


def _verify_index_descriptor(
    segment: ArchiveIndexSegment,
    rows: Sequence[Mapping[str, object]],
    key: str,
) -> None:
    if not rows:
        raise HistoryArchiveError("history_archive_corrupt")
    keys = [str(row[key]) for row in rows]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        raise HistoryArchiveError("history_archive_corrupt")
    if keys[0] != segment.first_key or keys[-1] != segment.last_key:
        raise HistoryArchiveError("history_archive_corrupt")
    for row in rows:
        if set(row) not in (
            {"event_id", "tick", "sequence", "digest", "path", "offset"},
            {"snapshot_id", "digest", "path", "offset"},
        ):
            raise HistoryArchiveError("history_archive_corrupt")


def _first_tick(segments: Sequence[ArchiveSegment]) -> int | None:
    return segments[0].first_tick if segments else None


def _last_tick(segments: Sequence[ArchiveSegment]) -> int | None:
    return segments[-1].last_tick if segments else None


class FilesystemHistoryArchiveReader:
    """Read-only archive adapter usable as runs/journal/snapshots ports."""

    __slots__ = ("_manifest_cache", "_root", "_run_manifest_cache")

    def __init__(self, root: Path | str) -> None:
        self._root = _safe_root(Path(root), create=False)
        self._manifest_cache: dict[str, ArchiveManifest] = {}
        self._run_manifest_cache: dict[str, RunManifest] = {}

    def get_manifest(self, run_id: RunId) -> ArchiveManifest | None:
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        cached = self._manifest_cache.get(run_id.value)
        if cached is not None:
            return cached
        state = self._load_state(run_id)
        if state is None:
            return None
        manifest = self._load_manifest(run_id, state.manifest_digest)
        if manifest.archive_id != state.committed_archive_id:
            raise HistoryArchiveError("history_archive_corrupt")
        self._manifest_cache[run_id.value] = manifest
        return manifest

    def _load_state(self, run_id: RunId) -> _State | None:
        path = _run_root(self._root, run_id) / "state.json"
        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            return None
        state = _parse_state(_decode_document(payload, max_bytes=_STATE_MAX_BYTES))
        if state.run_id != run_id:
            raise HistoryArchiveError("history_archive_corrupt")
        return state

    def _load_manifest(self, run_id: RunId, manifest_digest: str) -> ArchiveManifest:
        path = _safe_path(self._root, "manifests", f"{manifest_digest}.json")
        try:
            payload = path.read_bytes()
        except FileNotFoundError as exc:
            raise HistoryArchiveError("history_archive_missing") from exc
        if archive_digest(payload) != manifest_digest:
            raise HistoryArchiveError("history_archive_corrupt")
        manifest = _parse_manifest(payload)
        if manifest.run_id != run_id.value:
            raise HistoryArchiveError("history_archive_corrupt")
        return manifest

    def _manifest(self, run_id: RunId) -> ArchiveManifest | None:
        return self.get_manifest(run_id)


    def verify_storage(self, run_id: RunId) -> tuple[int, int, int, int]:
        """Read and validate every referenced lane, index and auxiliary object."""
        manifest = self._manifest(run_id)
        if manifest is None:
            raise HistoryArchiveError("history_archive_missing")
        segment_count = 0
        event_count = 0
        commit_count = 0
        snapshot_count = 0
        for commit_segment in manifest.commit_segments:
            records = self._segment_records(commit_segment, TickCommit)
            _verify_commit_descriptor(commit_segment, records)
            commit_count += len(records)
            segment_count += 1
        for event_segment in manifest.event_segments:
            records = self._segment_records(event_segment, WorldEvent)
            _verify_event_descriptor(event_segment, records)
            event_count += len(records)
            segment_count += 1
        for snapshot_segment in manifest.snapshot_segments:
            records = self._segment_records(snapshot_segment, WorldSnapshot)
            _verify_snapshot_descriptor(snapshot_segment, records)
            snapshot_count += len(records)
            segment_count += 1
        event_by_digest = {
            segment.digest: segment for segment in manifest.event_segments
        }
        snapshot_by_digest = {
            segment.digest: segment for segment in manifest.snapshot_segments
        }
        for event_index in manifest.event_index_segments:
            rows = self._index_rows(event_index)
            _verify_index_descriptor(event_index, rows, "event_id")
            _verify_index_references(rows, event_by_digest, "event_id")
            segment_count += 1
        for snapshot_index in manifest.snapshot_index_segments:
            rows = self._index_rows(snapshot_index)
            _verify_index_descriptor(snapshot_index, rows, "snapshot_id")
            _verify_index_references(rows, snapshot_by_digest, "snapshot_id")
            segment_count += 1
        for artifact in manifest.auxiliary:
            if artifact.path != archive_object_path(artifact.digest):
                raise HistoryArchiveError("history_archive_corrupt")
            payload = self._read_object(artifact.digest)
            if len(payload) != artifact.byte_count:
                raise HistoryArchiveError("history_archive_corrupt")
            segment_count += 1
        return segment_count, commit_count, event_count, snapshot_count

    def committed_manifests(self) -> tuple[ArchiveManifest, ...]:
        """Manifests reachable from an atomic run-state reference only."""
        return self._committed_manifests()

    def _read_object(self, digest: str, *, expected_bytes: int | None = None) -> bytes:
        path = _safe_path(self._root, *archive_object_path(digest).split("/"))
        try:
            payload = path.read_bytes()
        except FileNotFoundError as exc:
            raise HistoryArchiveError("history_archive_missing") from exc
        if archive_digest(payload) != digest:
            raise HistoryArchiveError("history_archive_corrupt")
        if expected_bytes is not None and len(payload) != expected_bytes:
            raise HistoryArchiveError("history_archive_corrupt")
        return payload

    def _descriptor_path(self, path: str, digest: str) -> bytes:
        target = _safe_path(self._root, *path.split("/"))
        try:
            payload = target.read_bytes()
        except FileNotFoundError as exc:
            raise HistoryArchiveError("history_archive_missing") from exc
        if archive_digest(payload) != digest:
            raise HistoryArchiveError("history_archive_corrupt")
        return payload

    def _segment_records(
        self, segment: ArchiveSegment, expected: type[object]
    ) -> tuple[object, ...]:
        payload = self._descriptor_path(segment.path, segment.digest)
        if len(payload) != segment.byte_count:
            raise HistoryArchiveError("history_archive_corrupt")
        values: list[object] = []
        for line in payload.splitlines(keepends=True):
            if not line.endswith(b"\n"):
                raise HistoryArchiveError("history_archive_corrupt")
            try:
                value = decode_persistence(line[:-1], expected)
            except (TypeError, ValueError) as exc:
                raise HistoryArchiveError("history_archive_corrupt") from exc
            values.append(value)
        if len(values) != segment.row_count:
            raise HistoryArchiveError("history_archive_corrupt")
        return tuple(values)

    def _index_rows(
        self, segment: ArchiveIndexSegment
    ) -> tuple[dict[str, object], ...]:
        payload = self._descriptor_path(segment.path, segment.digest)
        if len(payload) != segment.byte_count:
            raise HistoryArchiveError("history_archive_corrupt")
        rows: list[dict[str, object]] = []
        for line in payload.splitlines(keepends=True):
            if not line.endswith(b"\n"):
                raise HistoryArchiveError("history_archive_corrupt")
            try:
                value = json.loads(line[:-1].decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as exc:
                raise HistoryArchiveError("history_archive_corrupt") from exc
            if type(value) is not dict:
                raise HistoryArchiveError("history_archive_corrupt")
            rows.append(cast(dict[str, object], value))
        if len(rows) != segment.row_count:
            raise HistoryArchiveError("history_archive_corrupt")
        return tuple(rows)

    async def get_run(self, run_id: RunId) -> RunManifest | None:
        cached = self._run_manifest_cache.get(run_id.value)
        if cached is not None:
            return cached
        manifest = self._manifest(run_id)
        if manifest is None:
            return None
        payload = self._read_object(manifest.run_manifest_digest)
        try:
            value = decode_persistence(payload, RunManifest)
        except (TypeError, ValueError) as exc:
            raise HistoryArchiveError("history_archive_corrupt") from exc
        if type(value) is not RunManifest or value.run_id != run_id:
            raise HistoryArchiveError("history_archive_corrupt")
        self._run_manifest_cache[run_id.value] = value
        return value

    async def create_run(self, request: object) -> RunManifest:
        del request
        raise HistoryArchiveError("history_archive_read_only")

    async def append_tick(self, request: object) -> TickCommit:
        del request
        raise HistoryArchiveError("history_archive_read_only")

    async def get_tick_commit(self, run_id: RunId, tick: Tick) -> TickCommit | None:
        manifest = self._manifest(run_id)
        if manifest is None:
            return None
        for segment in manifest.commit_segments:
            if segment.first_tick <= tick.value <= segment.last_tick:
                records = self._segment_records(segment, TickCommit)
                for record in records:
                    assert type(record) is TickCommit
                    if record.tick == tick:
                        return record
                return None
        return None

    async def get_latest_tick_commit(
        self, run_id: RunId, *, through_tick: Tick | None = None
    ) -> TickCommit | None:
        manifest = self._manifest(run_id)
        if manifest is None:
            return None
        for segment in reversed(manifest.commit_segments):
            if through_tick is not None and segment.first_tick > through_tick.value:
                continue
            records = self._segment_records(segment, TickCommit)
            for record in reversed(records):
                assert type(record) is TickCommit
                if through_tick is None or record.tick.value <= through_tick.value:
                    return record
        return None

    async def list_tick_commits_keyset(
        self,
        run_id: RunId,
        *,
        after_tick: Tick,
        through_tick: Tick | None,
        limit: int,
    ) -> tuple[TickCommit, ...]:
        if type(after_tick) is not Tick:
            raise TypeError("after_tick must be Tick")
        if through_tick is not None and type(through_tick) is not Tick:
            raise TypeError("through_tick must be Tick or None")
        if type(limit) is not int or limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        manifest = self._manifest(run_id)
        if manifest is None:
            return ()
        rows: list[TickCommit] = []
        for segment in manifest.commit_segments:
            if segment.last_tick <= after_tick.value:
                continue
            records = self._segment_records(segment, TickCommit)
            for record in records:
                assert type(record) is TickCommit
                if record.tick.value <= after_tick.value:
                    continue
                if through_tick is not None and record.tick.value > through_tick.value:
                    continue
                rows.append(record)
                if len(rows) >= limit:
                    return tuple(rows)
        return tuple(rows)

    async def list_tick_commits(
        self, run_id: RunId, *, from_tick: Tick, to_tick: Tick | None
    ) -> tuple[TickCommit, ...]:
        manifest = self._manifest(run_id)
        if manifest is None:
            return ()
        rows: list[TickCommit] = []
        for segment in manifest.commit_segments:
            if segment.last_tick < from_tick.value:
                continue
            if to_tick is not None and segment.first_tick > to_tick.value:
                continue
            records = self._segment_records(segment, TickCommit)
            for record in records:
                assert type(record) is TickCommit
                if record.tick.value < from_tick.value:
                    continue
                if to_tick is not None and record.tick.value > to_tick.value:
                    continue
                rows.append(record)
        return tuple(rows)

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
        limit: int,
        offset: int,
    ) -> tuple[WorldEvent, ...]:
        if type(from_tick) is not Tick:
            raise TypeError("from_tick must be Tick")
        if to_tick is not None and type(to_tick) is not Tick:
            raise TypeError("to_tick must be Tick or None")
        if type(limit) is not int or limit < 0:
            raise ValueError("limit must be a non-negative int")
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be a non-negative int")
        if limit == 0:
            return ()
        manifest = self._manifest(run_id)
        if manifest is None:
            return ()
        skipped = 0
        rows: list[WorldEvent] = []
        for segment in manifest.event_segments:
            if segment.last_tick < from_tick.value:
                continue
            if to_tick is not None and segment.first_tick > to_tick.value:
                continue
            records = self._segment_records(segment, WorldEvent)
            for record in records:
                assert type(record) is WorldEvent
                if record.tick < from_tick.value:
                    continue
                if to_tick is not None and record.tick > to_tick.value:
                    continue
                if skipped < offset:
                    skipped += 1
                    continue
                rows.append(record)
                if len(rows) >= limit:
                    return tuple(rows)
        return tuple(rows)

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
    ) -> tuple[WorldEvent, ...]:
        if type(limit) is not int or limit < 0:
            raise ValueError("limit must be a non-negative int")
        if limit == 0:
            return ()
        manifest = self._manifest(run_id)
        if manifest is None:
            return ()
        rows: list[WorldEvent] = []
        for segment in manifest.event_segments:
            if (segment.last_tick, segment.last_sequence or 0) <= (
                after_tick,
                after_sequence,
            ):
                continue
            if to_tick is not None and segment.first_tick > to_tick.value:
                continue
            records = self._segment_records(segment, WorldEvent)
            for record in records:
                assert type(record) is WorldEvent
                if (record.tick, record.sequence) <= (after_tick, after_sequence):
                    continue
                if to_tick is not None and record.tick > to_tick.value:
                    continue
                if actor_id is not None and actor_id not in {
                    event_actor(record),
                    event_target(record),
                }:
                    continue
                if event_type is not None and record.details.kind != event_type:
                    continue
                rows.append(record)
                if len(rows) >= limit:
                    return tuple(rows)
        return tuple(rows)

    async def get_event_by_id(
        self,
        run_id: RunId,
        event_id: str,
        *,
        through_tick: Tick | None = None,
    ) -> WorldEvent | None:
        if type(event_id) is not str or not event_id:
            raise ValueError("event_id must be a non-empty string")
        manifest = self._manifest(run_id)
        if manifest is None:
            return None
        row = self._lookup_index(manifest.event_index_segments, event_id)
        if row is None:
            return None
        tick = int(cast(int, row["tick"]))
        if through_tick is not None and tick > through_tick.value:
            return None
        segment = self._segment_for_digest(
            manifest.event_segments, str(row["digest"])
        )
        payload = self._descriptor_path(segment.path, segment.digest)
        offset = int(cast(int, row["offset"]))
        if offset < 0 or offset >= len(payload):
            raise HistoryArchiveError("history_archive_corrupt")
        end = payload.find(b"\n", offset)
        if end < 0:
            raise HistoryArchiveError("history_archive_corrupt")
        try:
            value = decode_persistence(payload[offset:end], WorldEvent)
        except (TypeError, ValueError) as exc:
            raise HistoryArchiveError("history_archive_corrupt") from exc
        if type(value) is not WorldEvent or value.event_id.value != event_id:
            raise HistoryArchiveError("history_archive_corrupt")
        return value

    async def get_latest_event(
        self, run_id: RunId, *, through_tick: Tick | None = None
    ) -> WorldEvent | None:
        manifest = self._manifest(run_id)
        if manifest is None:
            return None
        for segment in reversed(manifest.event_segments):
            if through_tick is not None and segment.first_tick > through_tick.value:
                continue
            records = self._segment_records(segment, WorldEvent)
            for record in reversed(records):
                assert type(record) is WorldEvent
                if through_tick is None or record.tick <= through_tick.value:
                    return record
        return None

    async def get_snapshot(self, snapshot_id: object) -> WorldSnapshot | None:
        key = getattr(snapshot_id, "value", None)
        if type(key) is not str:
            raise TypeError("snapshot_id must be SnapshotId")
        for manifest in self._committed_manifests():
            row = self._lookup_index(manifest.snapshot_index_segments, key)
            if row is None:
                continue
            return self._decode_indexed_snapshot(manifest, row, key)
        return None

    def _decode_indexed_snapshot(
        self,
        manifest: ArchiveManifest,
        row: Mapping[str, object],
        key: str,
    ) -> WorldSnapshot:
        segment = self._segment_for_digest(
            manifest.snapshot_segments, str(row["digest"])
        )
        payload = self._descriptor_path(segment.path, segment.digest)
        offset = int(cast(int, row["offset"]))
        if offset < 0 or offset >= len(payload):
            raise HistoryArchiveError("history_archive_corrupt")
        end = payload.find(b"\n", offset)
        if end < 0:
            raise HistoryArchiveError("history_archive_corrupt")
        try:
            value = decode_persistence(payload[offset:end], WorldSnapshot)
        except (TypeError, ValueError) as exc:
            raise HistoryArchiveError("history_archive_corrupt") from exc
        if type(value) is not WorldSnapshot or value.snapshot_id.value != key:
            raise HistoryArchiveError("history_archive_corrupt")
        return value

    async def get_latest_at_or_before(
        self, run_id: RunId, tick: Tick
    ) -> WorldSnapshot | None:
        manifest = self._manifest(run_id)
        if manifest is None:
            return None
        for segment in reversed(manifest.snapshot_segments):
            if segment.first_tick > tick.value:
                continue
            records = self._segment_records(segment, WorldSnapshot)
            best: WorldSnapshot | None = None
            for record in records:
                assert type(record) is WorldSnapshot
                if record.next_tick.value <= tick.value and (
                    best is None or record.next_tick.value > best.next_tick.value
                ):
                    best = record
            if best is not None:
                return best
        return None

    async def list_snapshots(self, run_id: RunId) -> tuple[WorldSnapshot, ...]:
        manifest = self._manifest(run_id)
        if manifest is None:
            return ()
        rows: list[WorldSnapshot] = []
        for segment in manifest.snapshot_segments:
            records = self._segment_records(segment, WorldSnapshot)
            for record in records:
                assert type(record) is WorldSnapshot
                rows.append(record)
        return tuple(rows)

    def _committed_manifests(self) -> tuple[ArchiveManifest, ...]:
        rows: list[ArchiveManifest] = []
        runs_root = self._root / "runs"
        if not runs_root.exists():
            return ()
        for run_dir in sorted(runs_root.iterdir()):
            if not run_dir.is_dir() or run_dir.is_symlink():
                continue
            state_path = run_dir / "state.json"
            try:
                payload = state_path.read_bytes()
            except FileNotFoundError:
                continue
            state = _parse_state(
                _decode_document(payload, max_bytes=_STATE_MAX_BYTES)
            )
            manifest = self._load_manifest(state.run_id, state.manifest_digest)
            if manifest.archive_id != state.committed_archive_id:
                raise HistoryArchiveError("history_archive_corrupt")
            rows.append(manifest)
        return tuple(rows)

    def _segment_for_digest(
        self, segments: Sequence[ArchiveSegment], digest: str
    ) -> ArchiveSegment:
        for segment in segments:
            if segment.digest == digest:
                return segment
        raise HistoryArchiveError("history_archive_corrupt")

    def _lookup_index(
        self, segments: Sequence[ArchiveIndexSegment], key: str
    ) -> dict[str, object] | None:
        for segment in segments:
            if segment.last_key < key:
                continue
            if segment.first_key > key:
                return None
            rows = self._index_rows(segment)
            for row in rows:
                if str(row.get("event_id", row.get("snapshot_id"))) == key:
                    return row
            return None
        return None


def event_actor(event: WorldEvent) -> str | None:
    return None if event.actor_id is None else event.actor_id.value


def event_target(event: WorldEvent) -> str | None:
    return None if event.target_id is None else event.target_id.value


def create_history_archive_writer(
    root: Path | str, **options: int
) -> FilesystemHistoryArchiveWriter:
    return FilesystemHistoryArchiveWriter(root, **options)


def create_history_archive_reader(root: Path | str) -> FilesystemHistoryArchiveReader:
    return FilesystemHistoryArchiveReader(root)


__all__ = [
    "FilesystemHistoryArchiveReader",
    "FilesystemHistoryArchiveWriter",
    "create_history_archive_reader",
    "create_history_archive_writer",
]
