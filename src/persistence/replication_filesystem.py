"""Atomic quota-bounded filesystem store for replication snapshots."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import logging
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Final

from simulation.replication_codec import (
    decode_replication_snapshot,
    encode_replication_snapshot,
)
from simulation.replication_models import ScientificReplicationSnapshot
from simulation.replication_ports import (
    ReplicationPublicationError,
    ReplicationPublicationOptions,
    ReplicationPublicationReceipt,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "persistence.replication_filesystem"
)

STORE_VERSION: Final[str] = "scientific-replication-store-v1"
STATE_FILE: Final[str] = "state.json"


def _safe_component(value: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ReplicationPublicationError("replication_store_invalid_path")
    return value


class FilesystemReplicationStore:
    def __init__(self, root: Path, *, options: ReplicationPublicationOptions) -> None:
        self._root = Path(root)
        self._options = options

    def _run_dir(self, run_id: str) -> Path:
        return self._root / _safe_component(run_id)

    @contextlib.contextmanager
    def _lock(self, run_dir: Path) -> Iterator[None]:
        run_dir.mkdir(parents=True, exist_ok=True)
        lock_path = run_dir / "store.lock"
        with open(lock_path, "a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _read_state(self, run_dir: Path) -> dict[str, object]:
        path = run_dir / STATE_FILE
        if not path.exists():
            return {"version": STORE_VERSION, "publications": []}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReplicationPublicationError("replication_store_corrupt") from exc
        if not isinstance(data, dict) or data.get("version") != STORE_VERSION:
            raise ReplicationPublicationError("replication_store_corrupt")
        publications = data.get("publications")
        if not isinstance(publications, list):
            raise ReplicationPublicationError("replication_store_corrupt")
        return data

    @staticmethod
    def _atomic_write(path: Path, material: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(material)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
            dir_fd = os.open(path.parent, os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def publish(
        self, snapshot: ScientificReplicationSnapshot
    ) -> ReplicationPublicationReceipt:
        if not self._options.enabled:
            return ReplicationPublicationReceipt(
                publication_id=snapshot.publication_id,
                stored=False,
                reason="disabled",
            )
        if not snapshot.publication_id or not snapshot.internal_digest:
            raise ReplicationPublicationError("replication_store_invalid_snapshot")
        material = encode_replication_snapshot(snapshot)
        run_dir = self._run_dir(snapshot.run_id)
        with self._lock(run_dir):
            state = self._read_state(run_dir)
            raw_publications = state["publications"]
            assert isinstance(raw_publications, list)
            existing = {
                str(item["publication_id"]): item
                for item in raw_publications
                if isinstance(item, dict) and "publication_id" in item
            }
            known = existing.get(snapshot.publication_id)
            if known is not None:
                path = run_dir / f"{snapshot.publication_id}.json"
                if path.exists() and path.read_bytes() == material:
                    return ReplicationPublicationReceipt(
                        publication_id=snapshot.publication_id,
                        stored=False,
                        reason="published",
                        byte_size=len(material),
                    )
                raise ReplicationPublicationError("replication_store_corrupt")
            used = sum(int(item.get("byte_size", 0)) for item in raw_publications)
            if (
                len(raw_publications) >= self._options.max_publications
                or used + len(material) > self._options.max_bytes
            ):
                return ReplicationPublicationReceipt(
                    publication_id=snapshot.publication_id,
                    stored=False,
                    reason="quota_exceeded",
                    byte_size=len(material),
                )
            path = run_dir / f"{snapshot.publication_id}.json"
            self._atomic_write(path, material)
            entry = {
                "publication_id": snapshot.publication_id,
                "internal_digest": snapshot.internal_digest,
                "byte_size": len(material),
                "content_hash": hashlib.sha256(material).hexdigest(),
            }
            publications = [*raw_publications, entry]
            self._atomic_write(
                run_dir / STATE_FILE,
                (json.dumps(
                    {"version": STORE_VERSION, "publications": publications},
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ) + "\n").encode("utf-8"),
            )
        _LOG.info(
            "replication_snapshot_published publication_id=%s bytes=%s",
            snapshot.publication_id,
            len(material),
        )
        return ReplicationPublicationReceipt(
            publication_id=snapshot.publication_id,
            stored=True,
            reason="published",
            byte_size=len(material),
        )

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> ScientificReplicationSnapshot:
        run_dir = self._run_dir(run_id)
        state = self._read_state(run_dir)
        raw = state["publications"]
        assert isinstance(raw, list)
        if not raw:
            raise ReplicationPublicationError("replication_store_missing")
        chosen = (
            raw[-1]
            if publication_id is None
            else next(
                (
                    item
                    for item in raw
                    if isinstance(item, dict)
                    and item.get("publication_id") == publication_id
                ),
                None,
            )
        )
        if not isinstance(chosen, dict):
            raise ReplicationPublicationError("replication_store_missing")
        path = run_dir / f"{_safe_component(str(chosen['publication_id']))}.json"
        try:
            material = path.read_bytes()
        except OSError as exc:
            raise ReplicationPublicationError("replication_store_missing") from exc
        snapshot = decode_replication_snapshot(material)
        if snapshot.run_id != run_id:
            raise ReplicationPublicationError("replication_store_corrupt")
        return snapshot


def replication_store_reader(
    root: Path, *, options: ReplicationPublicationOptions
) -> FilesystemReplicationStore:
    return FilesystemReplicationStore(root, options=options)


def replication_store_publisher(
    root: Path, *, options: ReplicationPublicationOptions
) -> FilesystemReplicationStore:
    return FilesystemReplicationStore(root, options=options)


__all__ = [
    "STORE_VERSION",
    "FilesystemReplicationStore",
    "replication_store_publisher",
    "replication_store_reader",
]
