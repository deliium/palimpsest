"""Neutral contracts for verified offline objective-history archives.

The archive is a copy-only historical read tier. It never replaces the
authoritative SQL journal, and it cannot accept appended ticks or revive a
subjective run. Events, commits and snapshots stay in separate canonical lanes
using the existing persistence codecs.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from simulation.models import RunId
from simulation.persistence import RunManifest

ARCHIVE_MANIFEST_SCHEMA: Final[str] = "objective-history-archive-v1"
ARCHIVE_SEGMENT_SCHEMA: Final[str] = "objective-history-segment-v1"
ARCHIVE_INDEX_SCHEMA: Final[str] = "objective-history-index-v1"
ARCHIVE_STATE_SCHEMA: Final[str] = "objective-history-archive-state-v1"

ARCHIVE_MANIFEST_MAX_BYTES: Final[int] = 2 * 1024 * 1024
ARCHIVE_RECORD_MAX_BYTES: Final[int] = 32 * 1024 * 1024
ARCHIVE_AUXILIARY_MAX_BYTES: Final[int] = 512 * 1024 * 1024

EVENT_SEGMENT_ROWS: Final[int] = 512
EVENT_SEGMENT_BYTES: Final[int] = 512 * 1024
COMMIT_SEGMENT_ROWS: Final[int] = 1000
COMMIT_SEGMENT_BYTES: Final[int] = 512 * 1024
SNAPSHOT_SEGMENT_ROWS: Final[int] = 32
SNAPSHOT_SEGMENT_BYTES: Final[int] = 8 * 1024 * 1024
INDEX_SEGMENT_ROWS: Final[int] = 1024
INDEX_SEGMENT_BYTES: Final[int] = 256 * 1024

_EVENT_LANE: Final[str] = "events"
_COMMIT_LANE: Final[str] = "commits"
_SNAPSHOT_LANE: Final[str] = "snapshots"

_LANES: Final[frozenset[str]] = frozenset(
    {_EVENT_LANE, _COMMIT_LANE, _SNAPSHOT_LANE}
)


class HistoryArchiveError(ValueError):
    """Closed archive failure with a stable code and no payload contents."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_archive_bytes(value: object) -> bytes:
    """Deterministic JSON bytes used for manifests and index pages."""
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def archive_digest(payload: bytes) -> str:
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes")
    return hashlib.sha256(bytes(payload)).hexdigest()


def archive_object_path(digest: str) -> str:
    _require_digest("digest", digest)
    return f"objects/sha256/{digest[:2]}/{digest}"


def _require_digest(name: str, value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _require_nonneg(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative int")
    return value


def _require_optional_nonneg(name: str, value: object) -> int | None:
    if value is None:
        return None
    return _require_nonneg(name, value)


def _require_text(name: str, value: object, *, allow_empty: bool = False) -> str:
    if type(value) is not str or (not allow_empty and not value):
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _require_optional_text(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _require_text(name, value)


def _require_mapping(name: str, value: object) -> Mapping[str, object]:
    if type(value) is not dict:
        raise ValueError(f"{name} must be an object")
    return value


def _require_keys(value: Mapping[str, object], keys: set[str]) -> None:
    if set(value) != keys:
        raise ValueError("archive document has an unexpected key set")


def _require_sequence(name: str, value: object) -> Sequence[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(f"{name} must be a sequence")
    return value


def _require_bool(name: str, value: object) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a bool")
    return value


@dataclass(frozen=True, slots=True)
class ArchiveSegment:
    """One immutable canonical data segment in one archive lane."""

    schema_version: str
    lane: str
    path: str
    digest: str
    row_count: int
    byte_count: int
    first_tick: int
    last_tick: int
    first_sequence: int | None
    last_sequence: int | None
    first_commit_hash: str | None
    last_commit_hash: str | None

    def __post_init__(self) -> None:
        if self.schema_version != ARCHIVE_SEGMENT_SCHEMA:
            raise ValueError("unsupported archive segment schema")
        if self.lane not in _LANES:
            raise ValueError("unsupported archive lane")
        _require_text("path", self.path)
        _require_digest("digest", self.digest)
        object.__setattr__(
            self, "row_count", _require_nonneg("row_count", self.row_count)
        )
        object.__setattr__(
            self, "byte_count", _require_nonneg("byte_count", self.byte_count)
        )
        object.__setattr__(
            self, "first_tick", _require_nonneg("first_tick", self.first_tick)
        )
        object.__setattr__(
            self, "last_tick", _require_nonneg("last_tick", self.last_tick)
        )
        if self.last_tick < self.first_tick:
            raise ValueError("archive segment tick range is inverted")
        object.__setattr__(
            self,
            "first_sequence",
            _require_optional_nonneg("first_sequence", self.first_sequence),
        )
        object.__setattr__(
            self,
            "last_sequence",
            _require_optional_nonneg("last_sequence", self.last_sequence),
        )
        if self.first_commit_hash is not None:
            _require_digest("first_commit_hash", self.first_commit_hash)
        if self.last_commit_hash is not None:
            _require_digest("last_commit_hash", self.last_commit_hash)
        if self.row_count == 0:
            raise ValueError("archive segments must not be empty")

    def payload(self) -> dict[str, object]:
        return {
            "byte_count": self.byte_count,
            "digest": self.digest,
            "first_commit_hash": self.first_commit_hash,
            "first_sequence": self.first_sequence,
            "first_tick": self.first_tick,
            "lane": self.lane,
            "last_commit_hash": self.last_commit_hash,
            "last_sequence": self.last_sequence,
            "last_tick": self.last_tick,
            "path": self.path,
            "row_count": self.row_count,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_payload(cls, value: object) -> ArchiveSegment:
        data = _require_mapping("segment", value)
        _require_keys(
            data,
            {
                "byte_count",
                "digest",
                "first_commit_hash",
                "first_sequence",
                "first_tick",
                "lane",
                "last_commit_hash",
                "last_sequence",
                "last_tick",
                "path",
                "row_count",
                "schema_version",
            },
        )
        return cls(
            schema_version=_require_text("schema_version", data["schema_version"]),
            lane=_require_text("lane", data["lane"]),
            path=_require_text("path", data["path"]),
            digest=_require_digest("digest", data["digest"]),
            row_count=_require_nonneg("row_count", data["row_count"]),
            byte_count=_require_nonneg("byte_count", data["byte_count"]),
            first_tick=_require_nonneg("first_tick", data["first_tick"]),
            last_tick=_require_nonneg("last_tick", data["last_tick"]),
            first_sequence=_require_optional_nonneg(
                "first_sequence", data["first_sequence"]
            ),
            last_sequence=_require_optional_nonneg(
                "last_sequence", data["last_sequence"]
            ),
            first_commit_hash=_require_optional_text(
                "first_commit_hash", data["first_commit_hash"]
            ),
            last_commit_hash=_require_optional_text(
                "last_commit_hash", data["last_commit_hash"]
            ),
        )


@dataclass(frozen=True, slots=True)
class ArchiveIndexSegment:
    """One sorted index page referencing canonical data segments."""

    schema_version: str
    path: str
    digest: str
    row_count: int
    byte_count: int
    first_key: str
    last_key: str

    def __post_init__(self) -> None:
        if self.schema_version != ARCHIVE_INDEX_SCHEMA:
            raise ValueError("unsupported archive index schema")
        _require_text("path", self.path)
        _require_digest("digest", self.digest)
        object.__setattr__(
            self, "row_count", _require_nonneg("row_count", self.row_count)
        )
        object.__setattr__(
            self, "byte_count", _require_nonneg("byte_count", self.byte_count)
        )
        _require_text("first_key", self.first_key)
        _require_text("last_key", self.last_key)
        if self.last_key < self.first_key:
            raise ValueError("archive index key range is inverted")
        if self.row_count == 0:
            raise ValueError("archive index segments must not be empty")

    def payload(self) -> dict[str, object]:
        return {
            "byte_count": self.byte_count,
            "digest": self.digest,
            "first_key": self.first_key,
            "last_key": self.last_key,
            "path": self.path,
            "row_count": self.row_count,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_payload(cls, value: object) -> ArchiveIndexSegment:
        data = _require_mapping("index segment", value)
        _require_keys(
            data,
            {
                "byte_count",
                "digest",
                "first_key",
                "last_key",
                "path",
                "row_count",
                "schema_version",
            },
        )
        return cls(
            schema_version=_require_text("schema_version", data["schema_version"]),
            path=_require_text("path", data["path"]),
            digest=_require_digest("digest", data["digest"]),
            row_count=_require_nonneg("row_count", data["row_count"]),
            byte_count=_require_nonneg("byte_count", data["byte_count"]),
            first_key=_require_text("first_key", data["first_key"]),
            last_key=_require_text("last_key", data["last_key"]),
        )


@dataclass(frozen=True, slots=True)
class ArchivePinnedHead:
    """Verified durable head copied into one archive publication."""

    next_tick: int
    revision: int
    last_commit_hash: str | None
    latest_event_tick: int | None
    latest_event_sequence: int | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "next_tick", _require_nonneg("next_tick", self.next_tick)
        )
        object.__setattr__(self, "revision", _require_nonneg("revision", self.revision))
        if self.last_commit_hash is not None:
            _require_digest("last_commit_hash", self.last_commit_hash)
        object.__setattr__(
            self,
            "latest_event_tick",
            _require_optional_nonneg("latest_event_tick", self.latest_event_tick),
        )
        object.__setattr__(
            self,
            "latest_event_sequence",
            _require_optional_nonneg(
                "latest_event_sequence", self.latest_event_sequence
            ),
        )
        if (self.latest_event_tick is None) != (self.latest_event_sequence is None):
            raise ValueError(
                "pinned head latest event tick and sequence must both be set or None"
            )

    def payload(self) -> dict[str, object]:
        return {
            "last_commit_hash": self.last_commit_hash,
            "latest_event_sequence": self.latest_event_sequence,
            "latest_event_tick": self.latest_event_tick,
            "next_tick": self.next_tick,
            "revision": self.revision,
        }

    @classmethod
    def from_payload(cls, value: object) -> ArchivePinnedHead:
        data = _require_mapping("pinned_head", value)
        _require_keys(
            data,
            {
                "last_commit_hash",
                "latest_event_sequence",
                "latest_event_tick",
                "next_tick",
                "revision",
            },
        )
        return cls(
            next_tick=_require_nonneg("next_tick", data["next_tick"]),
            revision=_require_nonneg("revision", data["revision"]),
            last_commit_hash=_require_optional_text(
                "last_commit_hash", data["last_commit_hash"]
            ),
            latest_event_tick=_require_optional_nonneg(
                "latest_event_tick", data["latest_event_tick"]
            ),
            latest_event_sequence=_require_optional_nonneg(
                "latest_event_sequence", data["latest_event_sequence"]
            ),
        )


@dataclass(frozen=True, slots=True)
class ArchiveCoverage:
    """Exact tick and row coverage declared by one archive manifest."""

    first_tick: int | None
    last_tick: int | None
    commit_count: int
    event_count: int
    snapshot_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "first_tick",
            _require_optional_nonneg("first_tick", self.first_tick),
        )
        object.__setattr__(
            self,
            "last_tick",
            _require_optional_nonneg("last_tick", self.last_tick),
        )
        if (self.first_tick is None) != (self.last_tick is None):
            raise ValueError("archive coverage tick bounds must both be set or None")
        if (
            self.first_tick is not None
            and self.last_tick is not None
            and self.last_tick < self.first_tick
        ):
            raise ValueError("archive coverage tick range is inverted")
        object.__setattr__(
            self, "commit_count", _require_nonneg("commit_count", self.commit_count)
        )
        object.__setattr__(
            self, "event_count", _require_nonneg("event_count", self.event_count)
        )
        object.__setattr__(
            self,
            "snapshot_count",
            _require_nonneg("snapshot_count", self.snapshot_count),
        )

    def payload(self) -> dict[str, object]:
        return {
            "commit_count": self.commit_count,
            "event_count": self.event_count,
            "first_tick": self.first_tick,
            "last_tick": self.last_tick,
            "snapshot_count": self.snapshot_count,
        }

    @classmethod
    def from_payload(cls, value: object) -> ArchiveCoverage:
        data = _require_mapping("coverage", value)
        _require_keys(
            data,
            {
                "commit_count",
                "event_count",
                "first_tick",
                "last_tick",
                "snapshot_count",
            },
        )
        return cls(
            first_tick=_require_optional_nonneg("first_tick", data["first_tick"]),
            last_tick=_require_optional_nonneg("last_tick", data["last_tick"]),
            commit_count=_require_nonneg("commit_count", data["commit_count"]),
            event_count=_require_nonneg("event_count", data["event_count"]),
            snapshot_count=_require_nonneg("snapshot_count", data["snapshot_count"]),
        )


@dataclass(frozen=True, slots=True)
class ArchiveAuxiliary:
    """Independently hashed optional artifact copied beside objective lanes."""

    name: str
    capability_class: str
    path: str
    digest: str
    byte_count: int
    availability: str

    def __post_init__(self) -> None:
        _require_text("name", self.name)
        _require_text("capability_class", self.capability_class)
        _require_text("path", self.path)
        _require_digest("digest", self.digest)
        object.__setattr__(
            self, "byte_count", _require_nonneg("byte_count", self.byte_count)
        )
        _require_text("availability", self.availability)

    def payload(self) -> dict[str, object]:
        return {
            "availability": self.availability,
            "byte_count": self.byte_count,
            "capability_class": self.capability_class,
            "digest": self.digest,
            "name": self.name,
            "path": self.path,
        }

    @classmethod
    def from_payload(cls, value: object) -> ArchiveAuxiliary:
        data = _require_mapping("auxiliary", value)
        _require_keys(
            data,
            {
                "availability",
                "byte_count",
                "capability_class",
                "digest",
                "name",
                "path",
            },
        )
        return cls(
            name=_require_text("name", data["name"]),
            capability_class=_require_text(
                "capability_class", data["capability_class"]
            ),
            path=_require_text("path", data["path"]),
            digest=_require_digest("digest", data["digest"]),
            byte_count=_require_nonneg("byte_count", data["byte_count"]),
            availability=_require_text("availability", data["availability"]),
        )


@dataclass(frozen=True, slots=True)
class ArchiveOmission:
    """Evidence deliberately not reconstructed from objective events."""

    kind: str
    available: bool
    reason: str

    def __post_init__(self) -> None:
        _require_text("kind", self.kind)
        _require_bool("available", self.available)
        _require_text("reason", self.reason)

    def payload(self) -> dict[str, object]:
        return {
            "available": self.available,
            "kind": self.kind,
            "reason": self.reason,
        }

    @classmethod
    def from_payload(cls, value: object) -> ArchiveOmission:
        data = _require_mapping("omission", value)
        _require_keys(data, {"available", "kind", "reason"})
        return cls(
            kind=_require_text("kind", data["kind"]),
            available=_require_bool("available", data["available"]),
            reason=_require_text("reason", data["reason"]),
        )


@dataclass(frozen=True, slots=True)
class ArchiveAuxiliarySource:
    """Caller-supplied already-versioned artifact to copy unchanged."""

    name: str
    capability_class: str
    path: str

    def __post_init__(self) -> None:
        _require_text("name", self.name)
        _require_text("capability_class", self.capability_class)
        _require_text("path", self.path)


@dataclass(frozen=True, slots=True)
class ArchiveManifest:
    """Immutable objective-history archive-v1 publication manifest."""

    archive_id: str
    source_manifest_digest: str
    run_manifest_digest: str
    run_manifest_path: str
    run_id: str
    world_id: str
    seed: int
    derivation_version: str
    event_schema_version: int
    projector_version: str
    persistence_codec_version: str
    pinned_head: ArchivePinnedHead
    commit_segments: tuple[ArchiveSegment, ...]
    event_segments: tuple[ArchiveSegment, ...]
    snapshot_segments: tuple[ArchiveSegment, ...]
    event_index_segments: tuple[ArchiveIndexSegment, ...]
    snapshot_index_segments: tuple[ArchiveIndexSegment, ...]
    auxiliary: tuple[ArchiveAuxiliary, ...]
    omitted: tuple[ArchiveOmission, ...]
    coverage: ArchiveCoverage

    def __post_init__(self) -> None:
        _require_digest("archive_id", self.archive_id)
        _require_digest("source_manifest_digest", self.source_manifest_digest)
        _require_digest("run_manifest_digest", self.run_manifest_digest)
        _require_text("run_manifest_path", self.run_manifest_path)
        _require_text("run_id", self.run_id)
        _require_text("world_id", self.world_id)
        object.__setattr__(self, "seed", _require_nonneg("seed", self.seed))
        _require_text("derivation_version", self.derivation_version)
        object.__setattr__(
            self,
            "event_schema_version",
            _require_nonneg("event_schema_version", self.event_schema_version),
        )
        _require_text("projector_version", self.projector_version)
        _require_text(
            "persistence_codec_version", self.persistence_codec_version
        )
        if type(self.pinned_head) is not ArchivePinnedHead:
            raise TypeError("pinned_head must be ArchivePinnedHead")
        object.__setattr__(
            self,
            "commit_segments",
            _copy_segments(self.commit_segments, _COMMIT_LANE),
        )
        object.__setattr__(
            self,
            "event_segments",
            _copy_segments(self.event_segments, _EVENT_LANE),
        )
        object.__setattr__(
            self,
            "snapshot_segments",
            _copy_segments(self.snapshot_segments, _SNAPSHOT_LANE),
        )
        object.__setattr__(
            self,
            "event_index_segments",
            _copy_index_segments(self.event_index_segments),
        )
        object.__setattr__(
            self,
            "snapshot_index_segments",
            _copy_index_segments(self.snapshot_index_segments),
        )
        object.__setattr__(self, "auxiliary", _copy_auxiliary(self.auxiliary))
        object.__setattr__(self, "omitted", _copy_omissions(self.omitted))
        if type(self.coverage) is not ArchiveCoverage:
            raise TypeError("coverage must be ArchiveCoverage")

    def payload(self, *, include_id: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "auxiliary": [item.payload() for item in self.auxiliary],
            "commit_segments": [item.payload() for item in self.commit_segments],
            "coverage": self.coverage.payload(),
            "derivation_version": self.derivation_version,
            "event_index_segments": [
                item.payload() for item in self.event_index_segments
            ],
            "event_schema_version": self.event_schema_version,
            "event_segments": [item.payload() for item in self.event_segments],
            "omitted": [item.payload() for item in self.omitted],
            "persistence_codec_version": self.persistence_codec_version,
            "pinned_head": self.pinned_head.payload(),
            "projector_version": self.projector_version,
            "run_id": self.run_id,
            "run_manifest_digest": self.run_manifest_digest,
            "run_manifest_path": self.run_manifest_path,
            "schema_version": ARCHIVE_MANIFEST_SCHEMA,
            "seed": self.seed,
            "snapshot_index_segments": [
                item.payload() for item in self.snapshot_index_segments
            ],
            "snapshot_segments": [item.payload() for item in self.snapshot_segments],
            "source_manifest_digest": self.source_manifest_digest,
            "world_id": self.world_id,
        }
        if include_id:
            document["archive_id"] = self.archive_id
        return document

    @classmethod
    def from_payload(cls, value: object) -> ArchiveManifest:
        data = _require_mapping("manifest", value)
        _require_keys(
            data,
            {
                "archive_id",
                "auxiliary",
                "commit_segments",
                "coverage",
                "derivation_version",
                "event_index_segments",
                "event_schema_version",
                "event_segments",
                "omitted",
                "persistence_codec_version",
                "pinned_head",
                "projector_version",
                "run_id",
                "run_manifest_digest",
                "run_manifest_path",
                "schema_version",
                "seed",
                "snapshot_index_segments",
                "snapshot_segments",
                "source_manifest_digest",
                "world_id",
            },
        )
        if data["schema_version"] != ARCHIVE_MANIFEST_SCHEMA:
            raise ValueError("unsupported archive manifest schema")
        return cls(
            archive_id=_require_digest("archive_id", data["archive_id"]),
            source_manifest_digest=_require_digest(
                "source_manifest_digest", data["source_manifest_digest"]
            ),
            run_manifest_digest=_require_digest(
                "run_manifest_digest", data["run_manifest_digest"]
            ),
            run_manifest_path=_require_text(
                "run_manifest_path", data["run_manifest_path"]
            ),
            run_id=_require_text("run_id", data["run_id"]),
            world_id=_require_text("world_id", data["world_id"]),
            seed=_require_nonneg("seed", data["seed"]),
            derivation_version=_require_text(
                "derivation_version", data["derivation_version"]
            ),
            event_schema_version=_require_nonneg(
                "event_schema_version", data["event_schema_version"]
            ),
            projector_version=_require_text(
                "projector_version", data["projector_version"]
            ),
            persistence_codec_version=_require_text(
                "persistence_codec_version", data["persistence_codec_version"]
            ),
            pinned_head=ArchivePinnedHead.from_payload(data["pinned_head"]),
            commit_segments=_parse_segments(data["commit_segments"]),
            event_segments=_parse_segments(data["event_segments"]),
            snapshot_segments=_parse_segments(data["snapshot_segments"]),
            event_index_segments=_parse_index_segments(
                data["event_index_segments"]
            ),
            snapshot_index_segments=_parse_index_segments(
                data["snapshot_index_segments"]
            ),
            auxiliary=_parse_auxiliary(data["auxiliary"]),
            omitted=_parse_omissions(data["omitted"]),
            coverage=ArchiveCoverage.from_payload(data["coverage"]),
        )


@dataclass(frozen=True, slots=True)
class ArchiveVerification:
    """Metadata-only result of verifying one sealed archive."""

    archive_id: str
    run_id: str
    full: bool
    segment_count: int
    event_count: int
    commit_count: int
    snapshot_count: int
    auxiliary_count: int
    replay_boundaries: tuple[int, ...]
    verified_through_tick: int | None

    def payload(self) -> dict[str, object]:
        return {
            "archive_id": self.archive_id,
            "auxiliary_count": self.auxiliary_count,
            "commit_count": self.commit_count,
            "event_count": self.event_count,
            "full": self.full,
            "replay_boundaries": list(self.replay_boundaries),
            "run_id": self.run_id,
            "segment_count": self.segment_count,
            "snapshot_count": self.snapshot_count,
            "verified_through_tick": self.verified_through_tick,
        }


def archive_manifest_id(manifest: ArchiveManifest) -> str:
    """Content identity of a manifest excluding its own ``archive_id``."""
    return archive_digest(canonical_archive_bytes(manifest.payload(include_id=False)))


class SnapshotInventory(Protocol):
    """Read-only snapshot enumeration used by offline export composition."""

    async def list_snapshots(self, run_id: RunId) -> tuple[object, ...]: ...


def source_manifest_digest(manifest: RunManifest) -> str:
    """Canonical digest of the authoritative SQL run manifest."""
    from simulation.journal import encode_persistence

    return archive_digest(encode_persistence(manifest))


def _copy_segments(
    values: object, lane: str
) -> tuple[ArchiveSegment, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("segments must be a sequence")
    copied: list[ArchiveSegment] = []
    for value in values:
        if type(value) is not ArchiveSegment:
            raise TypeError("segments entries must be ArchiveSegment")
        if value.lane != lane:
            raise ValueError("segment lane mismatch")
        copied.append(value)
    return tuple(copied)


def _copy_index_segments(
    values: object,
) -> tuple[ArchiveIndexSegment, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("index segments must be a sequence")
    copied: list[ArchiveIndexSegment] = []
    for value in values:
        if type(value) is not ArchiveIndexSegment:
            raise TypeError("index segments entries must be ArchiveIndexSegment")
        copied.append(value)
    return tuple(copied)


def _copy_auxiliary(values: object) -> tuple[ArchiveAuxiliary, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("auxiliary must be a sequence")
    copied: list[ArchiveAuxiliary] = []
    for value in values:
        if type(value) is not ArchiveAuxiliary:
            raise TypeError("auxiliary entries must be ArchiveAuxiliary")
        copied.append(value)
    return tuple(copied)


def _copy_omissions(values: object) -> tuple[ArchiveOmission, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("omitted must be a sequence")
    copied: list[ArchiveOmission] = []
    for value in values:
        if type(value) is not ArchiveOmission:
            raise TypeError("omitted entries must be ArchiveOmission")
        copied.append(value)
    return tuple(copied)


def _parse_segments(value: object) -> tuple[ArchiveSegment, ...]:
    rows = _require_sequence("segments", value)
    return tuple(ArchiveSegment.from_payload(item) for item in rows)


def _parse_index_segments(value: object) -> tuple[ArchiveIndexSegment, ...]:
    rows = _require_sequence("index segments", value)
    return tuple(ArchiveIndexSegment.from_payload(item) for item in rows)


def _parse_auxiliary(value: object) -> tuple[ArchiveAuxiliary, ...]:
    rows = _require_sequence("auxiliary", value)
    return tuple(ArchiveAuxiliary.from_payload(item) for item in rows)


def _parse_omissions(value: object) -> tuple[ArchiveOmission, ...]:
    rows = _require_sequence("omitted", value)
    return tuple(ArchiveOmission.from_payload(item) for item in rows)


__all__ = [
    "ARCHIVE_AUXILIARY_MAX_BYTES",
    "ARCHIVE_INDEX_SCHEMA",
    "ARCHIVE_MANIFEST_MAX_BYTES",
    "ARCHIVE_MANIFEST_SCHEMA",
    "ARCHIVE_RECORD_MAX_BYTES",
    "ARCHIVE_SEGMENT_SCHEMA",
    "ARCHIVE_STATE_SCHEMA",
    "COMMIT_SEGMENT_BYTES",
    "COMMIT_SEGMENT_ROWS",
    "EVENT_SEGMENT_BYTES",
    "EVENT_SEGMENT_ROWS",
    "INDEX_SEGMENT_BYTES",
    "INDEX_SEGMENT_ROWS",
    "SNAPSHOT_SEGMENT_BYTES",
    "SNAPSHOT_SEGMENT_ROWS",
    "ArchiveAuxiliary",
    "ArchiveAuxiliarySource",
    "ArchiveCoverage",
    "ArchiveIndexSegment",
    "ArchiveManifest",
    "ArchiveOmission",
    "ArchivePinnedHead",
    "ArchiveSegment",
    "ArchiveVerification",
    "HistoryArchiveError",
    "SnapshotInventory",
    "archive_digest",
    "archive_manifest_id",
    "archive_object_path",
    "canonical_archive_bytes",
    "source_manifest_digest",
]
