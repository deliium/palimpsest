"""Atomic, quota-bounded filesystem store for macro-society snapshots."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from simulation.macro_society_codec import decode_macro_society_snapshot
from simulation.macro_society_models import (
    MACRO_SOCIETY_STORE_SCHEMA_VERSION,
    MacroSocietyArtifactError,
    MacroSocietySnapshot,
    MacroSocietySnapshotRef,
)
from simulation.macro_society_paging import select_macro_society_rows
from simulation.macro_society_ports import (
    MacroSocietyPublication,
    MacroSocietyPublicationPort,
    MacroSocietyReadPort,
    MacroSocietySummary,
    require_known_candidate,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "FilesystemMacroSocietyPublisher",
    "FilesystemMacroSocietyReader",
    "create_macro_society_publisher",
    "create_macro_society_reader",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "persistence.macro_society_filesystem"
)

_STATE_MAX_BYTES: Final[int] = 4096
_MANIFEST_MAX_BYTES: Final[int] = 16384
_QUOTA_ALLOWANCE: Final[int] = 256 * 1024


@dataclass(frozen=True, slots=True)
class _StoredState:
    publication_id: str
    snapshot_digest: str
    publications: int
    total_bytes: int


def _atomic_write(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


class FilesystemMacroSocietyPublisher(MacroSocietyPublicationPort):
    """Append-only publisher with a single atomic ``state.json`` commit point."""

    def __init__(
        self,
        root: Path,
        *,
        max_publications: int = 16,
        max_artifact_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self._root = Path(root)
        self._max_publications = require_exact_nonneg_int(
            "max_publications", max_publications
        )
        self._max_artifact_bytes = require_exact_nonneg_int(
            "max_artifact_bytes", max_artifact_bytes
        )

    def _run_dir(self, run_id: str) -> Path:
        return self._root / require_stable_id("run_id", run_id)

    def _state(self, run_dir: Path) -> _StoredState | None:
        state_path = run_dir / "state.json"
        if not state_path.exists():
            return None
        payload = state_path.read_bytes()
        if len(payload) > _STATE_MAX_BYTES:
            raise MacroSocietyArtifactError("macro_society_store_corrupt")
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise MacroSocietyArtifactError("macro_society_store_corrupt") from exc
        if not isinstance(data, dict):
            raise MacroSocietyArtifactError("macro_society_store_corrupt")
        return _StoredState(
            publication_id=str(data["publication_id"]),
            snapshot_digest=str(data["snapshot_digest"]),
            publications=int(data["publications"]),
            total_bytes=int(data["total_bytes"]),
        )

    def publish(self, publication: MacroSocietyPublication) -> MacroSocietySnapshotRef:
        snapshot = publication.snapshot
        run_dir = self._run_dir(snapshot.run_id)
        lock_path = run_dir / "writer.lock"
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.close(
                os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            )
        except FileExistsError as exc:
            raise MacroSocietyArtifactError("macro_society_store_locked") from exc
        try:
            state = self._state(run_dir)
            if state is not None:
                if state.publication_id == snapshot.publication_id:
                    raise MacroSocietyArtifactError(
                        "macro_society_publication_exists"
                    )
                if state.publications + 1 > self._max_publications:
                    raise MacroSocietyArtifactError("macro_society_quota_exceeded")
                if (
                    state.total_bytes + len(publication.payload) + _QUOTA_ALLOWANCE
                    > self._max_artifact_bytes
                ):
                    raise MacroSocietyArtifactError("macro_society_quota_exceeded")
            publication_dir = run_dir / "publications" / snapshot.publication_id
            snapshot_path = publication_dir / "snapshot.json"
            if snapshot_path.exists():
                raise MacroSocietyArtifactError("macro_society_publication_exists")
            manifest = {
                "publication_id": snapshot.publication_id,
                "snapshot_digest": hashlib.sha256(publication.payload).hexdigest(),
                "run_id": snapshot.run_id,
                "created_at_utc": publication.created_at_utc,
            }
            manifest_bytes = json.dumps(
                manifest, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            if len(manifest_bytes) > _MANIFEST_MAX_BYTES:
                raise MacroSocietyArtifactError("macro_society_size_limit")
            _atomic_write(snapshot_path, publication.payload)
            _atomic_write(publication_dir / "manifest.json", manifest_bytes)
            new_state = _StoredState(
                publication_id=snapshot.publication_id,
                snapshot_digest=manifest["snapshot_digest"],
                publications=1 if state is None else state.publications + 1,
                total_bytes=(0 if state is None else state.total_bytes)
                + len(publication.payload),
            )
            state_bytes = json.dumps(
                {
                    "store_schema_version": MACRO_SOCIETY_STORE_SCHEMA_VERSION,
                    "run_id": snapshot.run_id,
                    "publication_id": new_state.publication_id,
                    "snapshot_digest": new_state.snapshot_digest,
                    "publications": new_state.publications,
                    "total_bytes": new_state.total_bytes,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(state_bytes) > _STATE_MAX_BYTES:
                raise MacroSocietyArtifactError("macro_society_size_limit")
            _atomic_write(run_dir / "state.json", state_bytes)
            _LOG.info(
                "macro_society_store_published run=%s publication=%s bytes=%s",
                snapshot.run_id,
                snapshot.publication_id,
                len(publication.payload),
            )
            return MacroSocietySnapshotRef(
                publication_id=snapshot.publication_id,
                digest=new_state.snapshot_digest,
            )
        finally:
            lock_path.unlink(missing_ok=True)


class FilesystemMacroSocietyReader(MacroSocietyReadPort):
    """Read committed publications without repairing or rewriting them."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def _load(self, run_id: str, publication_id: str | None) -> MacroSocietySnapshot:
        run_dir = self._root / require_stable_id("run_id", run_id)
        state_path = run_dir / "state.json"
        if not state_path.exists():
            raise MacroSocietyArtifactError("macro_society_publication_missing")
        state = json.loads(state_path.read_bytes())
        committed = str(state["publication_id"])
        if publication_id is not None and publication_id != committed:
            raise MacroSocietyArtifactError("macro_society_publication_missing")
        snapshot_path = run_dir / "publications" / committed / "snapshot.json"
        if not snapshot_path.exists():
            raise MacroSocietyArtifactError("macro_society_publication_missing")
        payload = snapshot_path.read_bytes()
        snapshot = decode_macro_society_snapshot(payload)
        digest = hashlib.sha256(payload).hexdigest()
        if digest != state["snapshot_digest"]:
            raise MacroSocietyArtifactError("macro_society_digest_mismatch")
        return snapshot

    def read_summary(self, run_id: str) -> MacroSocietySummary:
        snapshot = self._load(run_id, None)
        payload = (self._root / run_id / "state.json").read_bytes()
        state = json.loads(payload)
        return MacroSocietySummary(
            publication_id=snapshot.publication_id,
            snapshot_digest=str(state["snapshot_digest"]),
            schema_version=snapshot.schema_version,
            policy_version=snapshot.policy_version,
            run_id=snapshot.run_id,
            input_revision=snapshot.input_revision,
            generated_tick=snapshot.generated_tick,
            window_count=len(snapshot.windows),
            candidate_count=len(snapshot.candidates),
            edge_count=len(snapshot.edges),
            coverage=snapshot.coverage,
            provenance_code=snapshot.provenance_code,
        )

    def read_candidates(
        self,
        run_id: str,
        *,
        publication_id: str | None,
        offset: int,
        limit: int,
    ) -> tuple[tuple[object, ...], int | None]:
        snapshot = self._load(run_id, publication_id)
        page = select_macro_society_rows(
            snapshot.candidates, offset=offset, limit=limit, max_bytes=2 * 1024 * 1024
        )
        return page.rows, page.next_offset

    def read_candidate(
        self, run_id: str, macro_society_id: str, *, publication_id: str | None
    ) -> object:
        snapshot = self._load(run_id, publication_id)
        return require_known_candidate(snapshot, macro_society_id)

    def read_lineage(
        self,
        run_id: str,
        *,
        publication_id: str | None,
        offset: int,
        limit: int,
    ) -> tuple[tuple[object, ...], int | None]:
        snapshot = self._load(run_id, publication_id)
        page = select_macro_society_rows(
            snapshot.edges, offset=offset, limit=limit, max_bytes=2 * 1024 * 1024
        )
        return page.rows, page.next_offset


def create_macro_society_publisher(
    root: Path | None,
    *,
    max_publications: int = 16,
    max_artifact_bytes: int = 8 * 1024 * 1024,
) -> FilesystemMacroSocietyPublisher | None:
    """Return a publisher, or ``None`` when publication is disabled."""
    if root is None:
        return None
    return FilesystemMacroSocietyPublisher(
        root,
        max_publications=max_publications,
        max_artifact_bytes=max_artifact_bytes,
    )


def create_macro_society_reader(
    root: Path | None,
) -> FilesystemMacroSocietyReader | None:
    """Return a reader, or ``None`` when the API surface is disabled."""
    if root is None:
        return None
    return FilesystemMacroSocietyReader(root)
