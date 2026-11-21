"""Atomic quota-bounded filesystem store for scientific-institution snapshots."""

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

from simulation.scientific_institutions_codec import (
    canonical_scientific_institutions_json,
    decode_scientific_institutions_snapshot,
    encode_scientific_institutions_snapshot,
)
from simulation.scientific_institutions_models import (
    MAX_SNAPSHOT_BYTES,
    ScientificInstitutionsPublicationOptions,
    ScientificInstitutionsPublicationReceipt,
    ScientificInstitutionsSnapshot,
)

__all__ = [
    "SCIENTIFIC_INSTITUTIONS_STORE_VERSION",
    "FilesystemScientificInstitutionsStore",
]

SCIENTIFIC_INSTITUTIONS_STORE_VERSION: Final[str] = (
    "scientific-institutions-store-v1"
)
_STATE_FILE: Final[str] = "state.json"
_BLOBS: Final[str] = "blobs"

_LOG: Final[logging.Logger] = logging.getLogger(
    "persistence.scientific_institutions_filesystem"
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
        raise ValueError("scientific_institutions_store_invalid_path")
    return value


class FilesystemScientificInstitutionsStore:
    """Verified reader and atomic publisher; reads never write."""

    def __init__(
        self,
        root: Path,
        *,
        options: ScientificInstitutionsPublicationOptions | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._options = options or ScientificInstitutionsPublicationOptions()

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
                "version": SCIENTIFIC_INSTITUTIONS_STORE_VERSION,
                "publications": [],
            }
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("scientific_institutions_store_corrupt") from exc
        if (
            not isinstance(data, dict)
            or data.get("version") != SCIENTIFIC_INSTITUTIONS_STORE_VERSION
            or not isinstance(data.get("publications"), list)
        ):
            raise ValueError("scientific_institutions_store_corrupt")
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
        self, snapshot: ScientificInstitutionsSnapshot
    ) -> ScientificInstitutionsPublicationReceipt:
        if type(snapshot) is not ScientificInstitutionsSnapshot:
            raise ValueError("scientific_institutions_store_invalid_snapshot")
        material = canonical_scientific_institutions_json(snapshot)
        if len(material) > MAX_SNAPSHOT_BYTES:
            return ScientificInstitutionsPublicationReceipt(
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
                    return ScientificInstitutionsPublicationReceipt(
                        publication_id=snapshot.publication_id,
                        stored=False,
                        reason="published",
                        byte_size=len(material),
                        digest=digest,
                    )
                raise ValueError("scientific_institutions_store_conflict")
            used = sum(
                int(item.get("bytes", 0))
                for item in raw
                if isinstance(item, dict)
            )
            if (
                len(raw) >= self._options.max_publications
                or used + len(material) > self._options.max_bytes
            ):
                return ScientificInstitutionsPublicationReceipt(
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
                        "version": SCIENTIFIC_INSTITUTIONS_STORE_VERSION,
                        "publications": publications,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            if len(state_material) > self._options.max_index_bytes:
                return ScientificInstitutionsPublicationReceipt(
                    publication_id=snapshot.publication_id,
                    stored=False,
                    reason="quota_exceeded",
                    byte_size=len(material),
                    digest=digest,
                )
            self._atomic_write(self._state_path(run_dir), state_material)
        _LOG.info(
            "scientific_institutions_snapshot_published publication_id=%s bytes=%s",
            snapshot.publication_id,
            len(material),
        )
        return ScientificInstitutionsPublicationReceipt(
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
    ) -> ScientificInstitutionsSnapshot | None:
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
            raise ValueError("scientific_institutions_store_corrupt")
        path = self._blob_path(run_dir, digest)
        if not path.exists():
            raise ValueError("scientific_institutions_store_corrupt")
        material = path.read_bytes()
        if len(material) != byte_size:
            raise ValueError("scientific_institutions_store_corrupt")
        if hashlib.sha256(material).hexdigest() != digest:
            raise ValueError("scientific_institutions_store_corrupt")
        payload = json.loads(material.decode("ascii"))
        snapshot = decode_scientific_institutions_snapshot(payload)
        if encode_scientific_institutions_snapshot(snapshot) != payload:
            raise ValueError("scientific_institutions_store_non_canonical")
        return snapshot
