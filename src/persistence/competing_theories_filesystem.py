"""Atomic filesystem store for canonical competing-theory snapshots."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from simulation.competing_theories_codec import (
    canonical_competing_theories_json,
    decode_competing_theories_snapshot,
    encode_competing_theories_snapshot,
)
from simulation.competing_theories_models import (
    MAX_SNAPSHOT_BYTES,
    CompetingTheoriesSnapshot,
)

__all__ = [
    "COMPETING_THEORIES_STORE_VERSION",
    "FilesystemCompetingTheoriesStore",
    "TheoryStoreReceipt",
]

COMPETING_THEORIES_STORE_VERSION: Final[str] = "competing-theories-store-v1"
_MAX_TOTAL_BYTES: Final[int] = 64 * 1024 * 1024

_LOG: Final[logging.Logger] = logging.getLogger(
    "persistence.competing_theories_filesystem"
)


@dataclass(frozen=True, slots=True)
class TheoryStoreReceipt:
    status: str
    publication_id: str | None = None
    digest: str | None = None


def _safe_segment(value: str) -> str:
    if not value or value in {".", ".."}:
        raise ValueError("path: invalid")
    if "/" in value or "\\" in value or "\x00" in value:
        raise ValueError("path: invalid")
    return value


class FilesystemCompetingTheoriesStore:
    """Verified read-only reader plus atomic publisher. Reads never write."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()

    def _run_dir(self, run_id: str) -> Path:
        return self._root / _safe_segment(run_id)

    def _publication_dir(self, run_id: str, publication_id: str) -> Path:
        return self._run_dir(run_id) / _safe_segment(publication_id)

    def _manifest_path(self, run_id: str, publication_id: str) -> Path:
        return self._publication_dir(run_id, publication_id) / "manifest.json"

    def publish(self, snapshot: CompetingTheoriesSnapshot) -> TheoryStoreReceipt:
        if type(snapshot) is not CompetingTheoriesSnapshot:
            raise ValueError("snapshot: invalid_type")
        data = canonical_competing_theories_json(snapshot)
        if len(data) > MAX_SNAPSHOT_BYTES:
            return TheoryStoreReceipt("quota_exceeded")
        digest = hashlib.sha256(data).hexdigest()
        directory = self._publication_dir(snapshot.run_id, snapshot.publication_id)
        directory.mkdir(parents=True, exist_ok=True)
        manifest_path = self._manifest_path(snapshot.run_id, snapshot.publication_id)
        if manifest_path.exists():
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            if existing.get("digest") == digest:
                return TheoryStoreReceipt(
                    "published",
                    snapshot.publication_id,
                    digest,
                )
            raise ValueError("publication: conflicting")
        total = sum(
            len(path.read_bytes())
            for path in self._run_dir(snapshot.run_id).glob("*/*")
            if path.is_file()
        )
        if total + len(data) > _MAX_TOTAL_BYTES:
            return TheoryStoreReceipt("quota_exceeded")
        temporary = directory / "snapshot.json.tmp"
        target = directory / "snapshot.json"
        temporary.write_bytes(data)
        os.replace(temporary, target)
        manifest = {
            "store_version": COMPETING_THEORIES_STORE_VERSION,
            "run_id": snapshot.run_id,
            "publication_id": snapshot.publication_id,
            "digest": digest,
            "bytes": len(data),
        }
        manifest_tmp = directory / "manifest.json.tmp"
        manifest_tmp.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(manifest_tmp, manifest_path)
        _LOG.debug(
            "competing_theories_published run_id=%s publication_id=%s bytes=%s",
            snapshot.run_id,
            snapshot.publication_id,
            len(data),
        )
        return TheoryStoreReceipt("published", snapshot.publication_id, digest)

    def latest_publication_id(self, run_id: str) -> str | None:
        run_dir = self._run_dir(run_id)
        if not run_dir.exists():
            return None
        candidates = sorted(path.name for path in run_dir.iterdir() if path.is_dir())
        return candidates[-1] if candidates else None

    def list_publications(self, run_id: str) -> tuple[str, ...]:
        run_dir = self._run_dir(run_id)
        if not run_dir.exists():
            return ()
        return tuple(sorted(path.name for path in run_dir.iterdir() if path.is_dir()))

    def read(
        self, run_id: str, publication_id: str | None = None
    ) -> CompetingTheoriesSnapshot | None:
        selected = publication_id or self.latest_publication_id(run_id)
        if selected is None:
            return None
        manifest_path = self._manifest_path(run_id, selected)
        if not manifest_path.exists():
            return None
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        data = (self._publication_dir(run_id, selected) / "snapshot.json").read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest.get("digest"):
            raise ValueError("snapshot: corrupt")
        snapshot = decode_competing_theories_snapshot(json.loads(data.decode("ascii")))
        if encode_competing_theories_snapshot(snapshot) != json.loads(
            data.decode("ascii")
        ):
            raise ValueError("snapshot: non_canonical")
        return snapshot
