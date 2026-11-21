"""Atomic quota-bounded filesystem store for diffusion snapshots."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import logging
import os
import stat
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Final

from simulation.science_diffusion_codec import (
    canonical_science_diffusion_json,
    decode_science_diffusion_snapshot,
    encode_science_diffusion_snapshot,
    load_science_diffusion_payload,
    science_diffusion_publication_id,
)
from simulation.science_diffusion_models import (
    MAX_SNAPSHOT_BYTES,
    ScienceDiffusionPublicationOptions,
    ScienceDiffusionPublicationReceipt,
    ScienceDiffusionSnapshot,
)

__all__ = [
    "SCIENCE_DIFFUSION_STORE_VERSION",
    "FilesystemScienceDiffusionStore",
]

SCIENCE_DIFFUSION_STORE_VERSION: Final[str] = "science-diffusion-store-v1"
_STATE_FILE: Final[str] = "state.json"
_BLOBS: Final[str] = "blobs"

_LOG: Final[logging.Logger] = logging.getLogger(
    "persistence.science_diffusion_filesystem"
)


def _safe_component(value: str) -> str:
    if (
        type(value) is not str
        or not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or "\x00" in value
    ):
        raise ValueError("science_diffusion_store_invalid_path")
    return value


def _read_regular(path: Path, limit: int) -> bytes:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise ValueError("science_diffusion_store_corrupt") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ValueError("science_diffusion_store_corrupt")
    if info.st_size > limit:
        raise ValueError("science_diffusion_store_corrupt")
    try:
        with open(path, "rb") as handle:
            material = handle.read(limit + 1)
    except OSError as exc:
        raise ValueError("science_diffusion_store_corrupt") from exc
    if len(material) > limit:
        raise ValueError("science_diffusion_store_corrupt")
    return material


class FilesystemScienceDiffusionStore:
    """Verified reader and atomic publisher; reads never write."""

    def __init__(
        self,
        root: Path,
        *,
        options: ScienceDiffusionPublicationOptions | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._options = options or ScienceDiffusionPublicationOptions()

    def _run_dir(self, run_id: str) -> Path:
        return self._root / _safe_component(run_id)

    def _state_path(self, run_dir: Path) -> Path:
        return run_dir / _STATE_FILE

    def _blob_path(self, run_dir: Path, digest: str) -> Path:
        return run_dir / _BLOBS / f"{_safe_component(digest)}.json"

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
        path = self._state_path(run_dir)
        if not path.exists():
            return {
                "version": SCIENCE_DIFFUSION_STORE_VERSION,
                "publications": [],
            }
        material = _read_regular(path, self._options.max_index_bytes)
        try:
            data = json.loads(material.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("science_diffusion_store_corrupt") from exc
        if (
            not isinstance(data, dict)
            or data.get("version") != SCIENCE_DIFFUSION_STORE_VERSION
            or not isinstance(data.get("publications"), list)
        ):
            raise ValueError("science_diffusion_store_corrupt")
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
        self, snapshot: ScienceDiffusionSnapshot
    ) -> ScienceDiffusionPublicationReceipt:
        if type(snapshot) is not ScienceDiffusionSnapshot:
            raise ValueError("science_diffusion_store_invalid_snapshot")
        expected_id = science_diffusion_publication_id(snapshot)
        if snapshot.publication_id != expected_id:
            raise ValueError("science_diffusion_store_identity")
        material = canonical_science_diffusion_json(snapshot)
        if len(material) > MAX_SNAPSHOT_BYTES:
            return ScienceDiffusionPublicationReceipt(
                publication_id=snapshot.publication_id,
                stored=False,
                reason="quota_exceeded",
                byte_size=len(material),
            )
        digest = hashlib.sha256(material).hexdigest()
        run_dir = self._run_dir(snapshot.run_id)
        with self._lock(run_dir):
            state = self._read_state(run_dir)
            raw = state["publications"]
            assert isinstance(raw, list)
            existing = next(
                (
                    item
                    for item in raw
                    if isinstance(item, dict)
                    and item.get("publication_id") == snapshot.publication_id
                ),
                None,
            )
            if existing is not None:
                if existing.get("digest") == digest:
                    return ScienceDiffusionPublicationReceipt(
                        publication_id=snapshot.publication_id,
                        stored=False,
                        reason="published",
                        byte_size=len(material),
                        digest=digest,
                    )
                raise ValueError("science_diffusion_store_conflict")
            unique: dict[str, int] = {}
            for item in raw:
                if isinstance(item, dict):
                    unique[str(item.get("digest", ""))] = int(item.get("bytes", 0))
            used = sum(unique.values())
            if (
                len(raw) >= self._options.max_publications
                or used + len(material) > self._options.max_bytes
            ):
                return ScienceDiffusionPublicationReceipt(
                    publication_id=snapshot.publication_id,
                    stored=False,
                    reason="quota_exceeded",
                    byte_size=len(material),
                    digest=digest,
                )
            self._atomic_write(self._blob_path(run_dir, digest), material)
            publications = [
                *raw,
                {
                    "publication_id": snapshot.publication_id,
                    "digest": digest,
                    "bytes": len(material),
                },
            ]
            state_material = (
                json.dumps(
                    {
                        "version": SCIENCE_DIFFUSION_STORE_VERSION,
                        "publications": publications,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            if len(state_material) > self._options.max_index_bytes:
                return ScienceDiffusionPublicationReceipt(
                    publication_id=snapshot.publication_id,
                    stored=False,
                    reason="quota_exceeded",
                    byte_size=len(material),
                    digest=digest,
                )
            self._atomic_write(self._state_path(run_dir), state_material)
        _LOG.info(
            "science_diffusion_snapshot_published publication_id=%s bytes=%s",
            snapshot.publication_id,
            len(material),
        )
        return ScienceDiffusionPublicationReceipt(
            publication_id=snapshot.publication_id,
            stored=True,
            reason="published",
            byte_size=len(material),
            digest=digest,
        )

    def list_publications(self, run_id: str) -> tuple[str, ...]:
        run_dir = self._run_dir(run_id)
        if not run_dir.exists():
            return ()
        state = self._read_state(run_dir)
        raw = state["publications"]
        assert isinstance(raw, list)
        return tuple(
            str(item["publication_id"])
            for item in raw
            if isinstance(item, dict) and "publication_id" in item
        )

    def latest_publication_id(self, run_id: str) -> str | None:
        publications = self.list_publications(run_id)
        return publications[-1] if publications else None

    def read(
        self, run_id: str, publication_id: str | None = None
    ) -> ScienceDiffusionSnapshot | None:
        run_dir = self._run_dir(run_id)
        if not run_dir.exists():
            return None
        state = self._read_state(run_dir)
        raw = state["publications"]
        assert isinstance(raw, list)
        if not raw:
            return None
        selected = (
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
        if not isinstance(selected, dict):
            return None
        digest = str(selected.get("digest", ""))
        byte_size = int(selected.get("bytes", 0))
        if not digest or byte_size <= 0 or byte_size > MAX_SNAPSHOT_BYTES:
            raise ValueError("science_diffusion_store_corrupt")
        material = _read_regular(self._blob_path(run_dir, digest), byte_size)
        if len(material) != byte_size:
            raise ValueError("science_diffusion_store_corrupt")
        if hashlib.sha256(material).hexdigest() != digest:
            raise ValueError("science_diffusion_store_corrupt")
        payload = load_science_diffusion_payload(material)
        snapshot = decode_science_diffusion_snapshot(payload)
        if encode_science_diffusion_snapshot(snapshot) != payload:
            raise ValueError("science_diffusion_store_non_canonical")
        if (
            snapshot.run_id != run_id
            or (
                publication_id is not None and snapshot.publication_id != publication_id
            )
            or science_diffusion_publication_id(snapshot) != snapshot.publication_id
        ):
            raise ValueError("science_diffusion_store_corrupt")
        return snapshot
