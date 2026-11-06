# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Atomic filesystem store for ``organized-conflict-store-v1``."""

from __future__ import annotations

import base64
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from simulation.organized_conflict_codec import (
    decode_organized_conflict_snapshot,
    encode_organized_conflict_snapshot,
)
from simulation.organized_conflict_models import OrganizedConflictSnapshot
from simulation.organized_conflict_ports import (
    OrganizedConflictSummary,
)

__all__ = [
    "ORGANIZED_CONFLICT_STORE_SCHEMA",
    "OrganizedConflictPublisherOptions",
    "create_organized_conflict_publisher",
    "create_organized_conflict_reader",
]

ORGANIZED_CONFLICT_STORE_SCHEMA: Final[str] = "organized-conflict-store-v1"
_STATE_FILE: Final[str] = "state.json"
_LOCK_FILE: Final[str] = "store.lock"


@dataclass(frozen=True, slots=True)
class OrganizedConflictPublisherOptions:
    max_publications: int = 16
    max_bytes: int = 8 * 1024 * 1024

    def __post_init__(self) -> None:
        if not 1 <= self.max_publications <= 1024:
            raise ValueError("organized_conflict_publications_range")
        if not 1 <= self.max_bytes <= 268_435_456:
            raise ValueError("organized_conflict_bytes_range")


def _empty_state() -> dict[str, object]:
    return {"schema": ORGANIZED_CONFLICT_STORE_SCHEMA, "publications": []}


def _load_state(root: Path) -> dict[str, object]:
    path = root / _STATE_FILE
    if not path.exists():
        return _empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("organized_conflict_store_corrupt") from exc
    if type(data) is not dict or data.get("schema") != ORGANIZED_CONFLICT_STORE_SCHEMA:
        raise ValueError("organized_conflict_store_corrupt")
    if not isinstance(data.get("publications"), list):
        raise ValueError("organized_conflict_store_corrupt")
    return data


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class _Publisher:
    def __init__(self, root: Path, options: OrganizedConflictPublisherOptions) -> None:
        self._root = root
        self._options = options

    def publish(self, snapshot: OrganizedConflictSnapshot) -> None:
        root = self._root
        root.mkdir(parents=True, exist_ok=True)
        import fcntl

        lock_path = root / _LOCK_FILE
        with lock_path.open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                state = _load_state(root)
                publications = state["publications"]
                payload = encode_organized_conflict_snapshot(snapshot)
                encoded = base64.b64encode(payload).decode("ascii")
                for entry in publications:
                    if entry.get("publication_id") != snapshot.publication_id:
                        continue
                    if entry.get("payload") == encoded:
                        return
                    raise ValueError("organized_conflict_publication_exists")
                run_entries = [
                    entry
                    for entry in publications
                    if entry.get("run_id") == snapshot.run_id
                ]
                if len(run_entries) >= self._options.max_publications:
                    raise ValueError("organized_conflict_quota_exceeded")
                existing_bytes = sum(
                    len(str(entry.get("payload", ""))) for entry in run_entries
                )
                if existing_bytes + len(encoded) > self._options.max_bytes:
                    raise ValueError("organized_conflict_quota_exceeded")
                publications.append(
                    {
                        "run_id": snapshot.run_id,
                        "publication_id": snapshot.publication_id,
                        "digest": snapshot.digest,
                        "schema_version": snapshot.schema_version,
                        "payload": encoded,
                    }
                )
                content = json.dumps(
                    state, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
                _atomic_write(root / _STATE_FILE, content)
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


class _Reader:
    def __init__(self, root: Path) -> None:
        self._root = root

    def _latest_entry(self, run_id: str) -> dict[str, object] | None:
        state = _load_state(self._root)
        entries = [
            entry for entry in state["publications"] if entry.get("run_id") == run_id
        ]
        return entries[-1] if entries else None

    def summary(self, run_id: str) -> OrganizedConflictSummary | None:
        snapshot = self.snapshot(run_id)
        if snapshot is None:
            return None
        return OrganizedConflictSummary(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            schema_version=snapshot.schema_version,
            episode_count=snapshot.summary.episode_count,
            plan_count=snapshot.summary.plan_count,
            interpretation_count=snapshot.summary.interpretation_count,
            coverage=snapshot.coverage,
        )

    def snapshot(self, run_id: str) -> OrganizedConflictSnapshot | None:
        entry = self._latest_entry(run_id)
        if entry is None:
            return None
        try:
            payload = base64.b64decode(str(entry["payload"]))
            snapshot = decode_organized_conflict_snapshot(payload)
        except Exception as exc:
            raise ValueError("organized_conflict_store_corrupt") from exc
        if snapshot.publication_id != entry.get("publication_id"):
            raise ValueError("organized_conflict_store_corrupt")
        return snapshot


def create_organized_conflict_reader(root: Path) -> _Reader:
    return _Reader(Path(root))


def create_organized_conflict_publisher(
    root: Path, options: OrganizedConflictPublisherOptions | None = None
) -> _Publisher:
    return _Publisher(Path(root), options or OrganizedConflictPublisherOptions())
