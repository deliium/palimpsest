"""Bounded append-only evidence spool with atomic state and indexed lookup."""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.persistence import EvidenceSpoolStatus

_SPOOL_STATE_SCHEMA: Final[str] = "evidence-spool-state-v1"
_SPOOL_ENTRY_SCHEMA: Final[str] = "evidence-spool-entry-v1"
_LANE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_STATE_MAX_BYTES: Final[int] = 1024 * 1024
_INDEX_MAX_BYTES: Final[int] = 8 * 1024 * 1024


class EvidenceSpoolError(ValueError):
    """Closed spool failure with a stable code and no payload content."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class EvidenceSpoolConflict(EvidenceSpoolError):
    def __init__(self) -> None:
        super().__init__("evidence_spool_conflict")


class EvidenceSpoolFull(EvidenceSpoolError):
    def __init__(self) -> None:
        super().__init__("evidence_spool_full")


class EvidenceSpoolSealed(EvidenceSpoolError):
    def __init__(self) -> None:
        super().__init__("evidence_spool_sealed")


def _canonical(value: object) -> bytes:
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


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode(payload: bytes, *, max_bytes: int) -> object:
    if len(payload) > max_bytes:
        raise EvidenceSpoolError("evidence_spool_corrupt")
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise EvidenceSpoolError("evidence_spool_corrupt") from exc


def _positive(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive int")
    return value


def _boundary(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative int")
    return value


def _identity(value: object) -> str:
    if type(value) is not str or not 1 <= len(value) <= 128:
        raise ValueError("identity must be a bounded non-empty str")
    if value != value.strip() or any(ord(char) < 32 for char in value):
        raise ValueError("identity must not contain whitespace edges or controls")
    return value


def _lane(value: object) -> str:
    if type(value) is not str or _LANE.fullmatch(value) is None:
        raise ValueError("lane must match [a-z][a-z0-9_-]*")
    return value


def _safe_path(root: Path, *parts: str) -> Path:
    for part in parts:
        if (
            type(part) is not str
            or not part
            or part in {".", ".."}
            or "/" in part
            or "\\" in part
        ):
            raise EvidenceSpoolError("evidence_spool_path_violation")
    target = root.joinpath(*parts)
    if not target.resolve(strict=False).is_relative_to(root):
        raise EvidenceSpoolError("evidence_spool_path_violation")
    return target


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.tmp")
    descriptor = os.open(
        temporary,
        os.O_CREAT | os.O_TRUNC | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
        0o600,
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
def _locked(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = root / "writer.lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@dataclass(slots=True)
class _LaneState:
    segment_index: int = 0
    segment_rows: int = 0
    segment_bytes: int = 0
    record_count: int = 0
    byte_count: int = 0
    first_boundary: int | None = None
    last_boundary: int | None = None
    sealed: bool = False

    def payload(self) -> dict[str, object]:
        return {
            "byte_count": self.byte_count,
            "first_boundary": self.first_boundary,
            "last_boundary": self.last_boundary,
            "record_count": self.record_count,
            "sealed": self.sealed,
            "segment_bytes": self.segment_bytes,
            "segment_index": self.segment_index,
            "segment_rows": self.segment_rows,
        }

    @classmethod
    def from_payload(cls, value: object) -> _LaneState:
        if type(value) is not dict:
            raise EvidenceSpoolError("evidence_spool_corrupt")
        expected = {
            "byte_count",
            "first_boundary",
            "last_boundary",
            "record_count",
            "sealed",
            "segment_bytes",
            "segment_index",
            "segment_rows",
        }
        if set(value) != expected:
            raise EvidenceSpoolError("evidence_spool_corrupt")
        return cls(
            segment_index=_boundary("segment_index", value["segment_index"]),
            segment_rows=_boundary("segment_rows", value["segment_rows"]),
            segment_bytes=_boundary("segment_bytes", value["segment_bytes"]),
            record_count=_boundary("record_count", value["record_count"]),
            byte_count=_boundary("byte_count", value["byte_count"]),
            first_boundary=(
                None
                if value["first_boundary"] is None
                else _boundary("first_boundary", value["first_boundary"])
            ),
            last_boundary=(
                None
                if value["last_boundary"] is None
                else _boundary("last_boundary", value["last_boundary"])
            ),
            sealed=bool(value["sealed"]),
        )


class FilesystemEvidenceSpool:
    """Append-only segment spool; one atomic state reference per mutation."""

    __slots__ = (
        "_max_bytes",
        "_max_payload_bytes",
        "_max_records",
        "_root",
        "_segment_bytes",
        "_segment_rows",
    )

    def __init__(
        self,
        root: Path | str,
        *,
        max_records: int = 1_000_000,
        max_bytes: int = 256 * 1024 * 1024,
        segment_rows: int = 512,
        segment_bytes: int = 1024 * 1024,
        max_payload_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        resolved = Path(root)
        if resolved.exists() and resolved.is_symlink():
            raise EvidenceSpoolError("evidence_spool_path_violation")
        resolved.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._root = resolved.resolve()
        self._max_records = _positive("max_records", max_records)
        self._max_bytes = _positive("max_bytes", max_bytes)
        self._segment_rows = _positive("segment_rows", segment_rows)
        self._segment_bytes = _positive("segment_bytes", segment_bytes)
        self._max_payload_bytes = _positive("max_payload_bytes", max_payload_bytes)

    def append(
        self,
        *,
        lane: str,
        boundary_tick: int,
        identity: str,
        payload: bytes,
    ) -> bool:
        lane = _lane(lane)
        boundary_tick = _boundary("boundary_tick", boundary_tick)
        identity = _identity(identity)
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("payload must be bytes")
        payload = bytes(payload)
        if len(payload) > self._max_payload_bytes:
            raise EvidenceSpoolFull()
        with _locked(self._root):
            lanes, sealed = self._load_state()
            if sealed or lanes.get(lane, _LaneState()).sealed:
                raise EvidenceSpoolSealed()
            state = lanes.setdefault(lane, _LaneState())
            identity_path = self._identity_path(lane, identity)
            identities = self._load_index(identity_path)
            existing = identities.get(identity)
            if existing is not None:
                if self._read_existing(lane, existing) == payload:
                    return False
                raise EvidenceSpoolConflict()
            if (
                self._total_records(lanes) + 1 > self._max_records
                or self._total_bytes(lanes) + len(payload) > self._max_bytes
            ):
                raise EvidenceSpoolFull()
            record = {
                "boundary_tick": boundary_tick,
                "identity": identity,
                "payload": base64.b64encode(payload).decode("ascii"),
            }
            line = _canonical(record)
            if state.segment_rows and (
                state.segment_rows >= self._segment_rows
                or state.segment_bytes + len(line) > self._segment_bytes
            ):
                state.segment_index += 1
                state.segment_rows = 0
                state.segment_bytes = 0
            segment_path = self._segment_path(lane, state.segment_index)
            segment_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            offset = state.segment_bytes
            descriptor = os.open(
                segment_path,
                os.O_CREAT | os.O_APPEND | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                os.write(descriptor, line)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            entry = {
                "boundary_tick": boundary_tick,
                "digest": _digest(payload),
                "identity": identity,
                "length": len(line),
                "offset": offset,
                "segment": state.segment_index,
            }
            identities[identity] = entry
            self._write_index(identity_path, identities)
            boundary_path = self._boundary_path(lane, boundary_tick)
            boundary_entries = self._load_index(boundary_path)
            boundary_entries[identity] = entry
            self._write_index(boundary_path, boundary_entries)
            state.segment_rows += 1
            state.segment_bytes += len(line)
            state.record_count += 1
            state.byte_count += len(payload)
            if state.first_boundary is None:
                state.first_boundary = boundary_tick
            else:
                state.first_boundary = min(state.first_boundary, boundary_tick)
            state.last_boundary = (
                boundary_tick
                if state.last_boundary is None
                else max(state.last_boundary, boundary_tick)
            )
            self._write_state(lanes, sealed=False)
            return True

    def get(self, *, lane: str, identity: str) -> bytes | None:
        lane = _lane(lane)
        identity = _identity(identity)
        entry = self._load_index(self._identity_path(lane, identity)).get(identity)
        if entry is None:
            return None
        return self._read_existing(lane, entry)

    def read_boundary(
        self, *, lane: str, boundary_tick: int
    ) -> tuple[bytes, ...]:
        lane = _lane(lane)
        boundary_tick = _boundary("boundary_tick", boundary_tick)
        entries = self._load_index(self._boundary_path(lane, boundary_tick))
        return tuple(
            self._read_existing(lane, entry)
            for _identity, entry in sorted(entries.items())
        )

    def iter_lane(
        self,
        *,
        lane: str,
        after_boundary: int | None,
        limit: int,
    ) -> tuple[bytes, ...]:
        lane = _lane(lane)
        if after_boundary is not None:
            after_boundary = _boundary("after_boundary", after_boundary)
        if type(limit) is not int or limit < 0:
            raise ValueError("limit must be a non-negative int")
        if limit == 0:
            return ()
        boundary_root = _safe_path(self._root, "lanes", lane, "boundaries")
        if not boundary_root.is_dir():
            return ()
        payloads: list[bytes] = []
        for path in sorted(boundary_root.glob("*.json")):
            tick = int(path.stem)
            if after_boundary is not None and tick <= after_boundary:
                continue
            entries = self._load_index(path)
            for _identity, entry in sorted(entries.items()):
                payloads.append(self._read_existing(lane, entry))
                if len(payloads) >= limit:
                    return tuple(payloads)
        return tuple(payloads)

    def seal(self) -> EvidenceSpoolStatus:
        with _locked(self._root):
            lanes, _sealed = self._load_state()
            for state in lanes.values():
                state.sealed = True
            self._write_state(lanes, sealed=True)
        return self.status()

    def status(self) -> EvidenceSpoolStatus:
        lanes, sealed = self._load_state()
        records = self._total_records(lanes)
        byte_count = self._total_bytes(lanes)
        first = min(
            (
                state.first_boundary
                for state in lanes.values()
                if state.first_boundary is not None
            ),
            default=None,
        )
        last = max(
            (
                state.last_boundary
                for state in lanes.values()
                if state.last_boundary is not None
            ),
            default=None,
        )
        return EvidenceSpoolStatus(
            active=not sealed,
            failed=False,
            sealed=sealed,
            truncated=False,
            failure_code=None,
            record_count=records,
            byte_count=byte_count,
            first_boundary=first,
            last_boundary=last,
        )

    def lane_status(self, lane: str) -> EvidenceSpoolStatus:
        lane = _lane(lane)
        lanes, sealed = self._load_state()
        state = lanes.get(lane)
        return EvidenceSpoolStatus(
            active=not sealed and (state is None or not state.sealed),
            failed=False,
            sealed=sealed or (state is not None and state.sealed),
            truncated=False,
            failure_code=None,
            record_count=0 if state is None else state.record_count,
            byte_count=0 if state is None else state.byte_count,
            first_boundary=None if state is None else state.first_boundary,
            last_boundary=None if state is None else state.last_boundary,
        )

    def _load_state(self) -> tuple[dict[str, _LaneState], bool]:
        path = _safe_path(self._root, "state.json")
        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            return {}, False
        value = _decode(payload, max_bytes=_STATE_MAX_BYTES)
        if type(value) is not dict or set(value) != {
            "lanes",
            "schema_version",
            "sealed",
        }:
            raise EvidenceSpoolError("evidence_spool_corrupt")
        if value["schema_version"] != _SPOOL_STATE_SCHEMA:
            raise EvidenceSpoolError("evidence_spool_corrupt")
        raw_lanes = value["lanes"]
        if type(raw_lanes) is not dict:
            raise EvidenceSpoolError("evidence_spool_corrupt")
        lanes = {
            str(name): _LaneState.from_payload(item)
            for name, item in raw_lanes.items()
        }
        return lanes, bool(value["sealed"])

    def _write_state(self, lanes: Mapping[str, _LaneState], *, sealed: bool) -> None:
        payload = _canonical(
            {
                "lanes": {name: state.payload() for name, state in lanes.items()},
                "schema_version": _SPOOL_STATE_SCHEMA,
                "sealed": sealed,
            }
        )
        if len(payload) > _STATE_MAX_BYTES:
            raise EvidenceSpoolError("evidence_spool_corrupt")
        _atomic_write(_safe_path(self._root, "state.json"), payload)

    def _identity_path(self, lane: str, identity: str) -> Path:
        shard = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:2]
        return _safe_path(self._root, "lanes", lane, "identity", f"{shard}.json")

    def _boundary_path(self, lane: str, boundary_tick: int) -> Path:
        return _safe_path(
            self._root, "lanes", lane, "boundaries", f"{boundary_tick:08d}.json"
        )

    def _segment_path(self, lane: str, segment_index: int) -> Path:
        return _safe_path(
            self._root, "lanes", lane, "segments", f"part-{segment_index:08d}.jsonl"
        )

    def _load_index(self, path: Path) -> dict[str, dict[str, object]]:
        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            return {}
        value = _decode(payload, max_bytes=_INDEX_MAX_BYTES)
        if (
            type(value) is not dict
            or value.get("schema_version") != _SPOOL_ENTRY_SCHEMA
        ):
            raise EvidenceSpoolError("evidence_spool_corrupt")
        entries = value.get("entries")
        if type(entries) is not dict:
            raise EvidenceSpoolError("evidence_spool_corrupt")
        rows: dict[str, dict[str, object]] = {}
        for identity, entry in entries.items():
            if type(entry) is not dict or set(entry) != {
                "boundary_tick",
                "digest",
                "identity",
                "length",
                "offset",
                "segment",
            }:
                raise EvidenceSpoolError("evidence_spool_corrupt")
            rows[str(identity)] = entry
        return rows

    def _write_index(
        self, path: Path, entries: Mapping[str, Mapping[str, object]]
    ) -> None:
        payload = _canonical(
            {
                "entries": {
                    identity: dict(entry) for identity, entry in entries.items()
                },
                "schema_version": _SPOOL_ENTRY_SCHEMA,
            }
        )
        if len(payload) > _INDEX_MAX_BYTES:
            raise EvidenceSpoolFull()
        _atomic_write(path, payload)

    def _read_existing(self, lane: str, entry: Mapping[str, object]) -> bytes:
        try:
            segment = _entry_int(entry, "segment")
            offset = _entry_int(entry, "offset")
            length = _entry_int(entry, "length")
            digest = str(entry["digest"])
        except (KeyError, TypeError, ValueError) as exc:
            raise EvidenceSpoolError("evidence_spool_corrupt") from exc
        path = self._segment_path(lane, segment)
        try:
            with path.open("rb") as handle:
                handle.seek(offset)
                content = handle.read(length)
        except OSError as exc:
            raise EvidenceSpoolError("evidence_spool_corrupt") from exc
        if len(content) != length:
            raise EvidenceSpoolError("evidence_spool_corrupt")
        value = _decode(content, max_bytes=self._max_payload_bytes * 2 + 4096)
        if type(value) is not dict:
            raise EvidenceSpoolError("evidence_spool_corrupt")
        encoded_payload = value.get("payload")
        if type(encoded_payload) is not str:
            raise EvidenceSpoolError("evidence_spool_corrupt")
        try:
            payload = base64.b64decode(encoded_payload.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError) as exc:
            raise EvidenceSpoolError("evidence_spool_corrupt") from exc
        if _digest(payload) != digest:
            raise EvidenceSpoolError("evidence_spool_corrupt")
        return payload

    @staticmethod
    def _total_records(lanes: Mapping[str, _LaneState]) -> int:
        return sum(state.record_count for state in lanes.values())

    @staticmethod
    def _total_bytes(lanes: Mapping[str, _LaneState]) -> int:
        return sum(state.byte_count for state in lanes.values())


def _entry_int(entry: Mapping[str, object], key: str) -> int:
    value = entry[key]
    if type(value) is not int or value < 0:
        raise ValueError("entry value must be a non-negative int")
    return value


def create_evidence_spool(root: Path | str, **options: int) -> FilesystemEvidenceSpool:
    return FilesystemEvidenceSpool(root, **options)


__all__ = [
    "EvidenceSpoolConflict",
    "EvidenceSpoolError",
    "EvidenceSpoolFull",
    "EvidenceSpoolSealed",
    "FilesystemEvidenceSpool",
    "create_evidence_spool",
]
