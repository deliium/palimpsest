"""Atomic, quota-bounded filesystem store for organization snapshots."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from simulation.organization_codec import decode_organization_snapshot
from simulation.organization_models import (
    MAX_RESPONSE_BYTES,
    OrganizationArtifactError,
    OrganizationCandidateRecord,
    OrganizationCoverage,
    OrganizationSnapshot,
    require_publication_id,
)
from simulation.organization_paging import (
    OrganizationRowSelection,
    select_organization_rows,
)
from simulation.organization_ports import (
    OrganizationPublication,
    OrganizationPublicationPort,
    OrganizationReadPort,
    OrganizationSummary,
)

__all__ = [
    "FilesystemOrganizationPublisher",
    "FilesystemOrganizationReader",
    "create_organization_publisher",
    "create_organization_reader",
]

_LOG: Final[logging.Logger] = logging.getLogger("persistence.organization_filesystem")

_SNAPSHOT_SCHEMA: Final[str] = "organization-snapshot-v1"
_STORE_SCHEMA: Final[str] = "organization-store-v1"
_STATE_MAX_BYTES: Final[int] = 4096
_MANIFEST_MAX_BYTES: Final[int] = 16384
_QUOTA_ALLOWANCE: Final[int] = 256 * 1024
_SAFE_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _safe(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not _SAFE_TOKEN_PATTERN.match(value)
        or ".." in value
        or "/" in value
        or "\\" in value
        or "\x00" in value
    ):
        raise OrganizationArtifactError("organization_invalid_value")
    return value


def _int(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise OrganizationArtifactError("organization_invalid_value")
    return value


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


@dataclass(frozen=True, slots=True)
class _StoredState:
    publication_id: str
    snapshot_digest: str
    publications: int
    total_bytes: int


class FilesystemOrganizationPublisher(OrganizationPublicationPort):
    """Append-only publisher with a single atomic ``state.json`` commit point."""

    def __init__(
        self,
        root: Path,
        *,
        max_publications: int = 16,
        max_artifact_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self._root = Path(root)
        self._max_publications = _int("max_publications", max_publications)
        self._max_artifact_bytes = _int("max_artifact_bytes", max_artifact_bytes)

    def _run_dir(self, run_id: str) -> Path:
        return self._root / _safe("run_id", run_id)

    def _state(self, run_dir: Path) -> _StoredState | None:
        state_path = run_dir / "state.json"
        if not state_path.exists():
            return None
        payload = state_path.read_bytes()
        if len(payload) > _STATE_MAX_BYTES:
            raise OrganizationArtifactError("organization_store_corrupt")
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise OrganizationArtifactError("organization_store_corrupt") from exc
        if not isinstance(data, dict) or data.get("store_schema_version") != (
            _STORE_SCHEMA
        ):
            raise OrganizationArtifactError("organization_store_corrupt")
        try:
            return _StoredState(
                publication_id=str(data["publication_id"]),
                snapshot_digest=str(data["snapshot_digest"]),
                publications=int(data["publications"]),
                total_bytes=int(data["total_bytes"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise OrganizationArtifactError("organization_store_corrupt") from exc

    def publish(self, publication: OrganizationPublication) -> None:
        if type(publication) is not OrganizationPublication:
            raise OrganizationArtifactError("organization_invalid_value")
        run_id = _safe("run_id", publication.run_id)
        publication_id = require_publication_id(publication.publication_id)
        if len(publication.payload) > self._max_artifact_bytes:
            raise OrganizationArtifactError("organization_size_limit")
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        lock_path = run_dir / "writer.lock"
        try:
            os.close(os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        except FileExistsError as exc:
            _LOG.warning("organization_store_locked run_id=%s", run_id)
            raise OrganizationArtifactError("organization_store_locked") from exc
        try:
            state = self._state(run_dir)
            publication_dir = run_dir / "publications" / publication_id
            snapshot_path = publication_dir / "snapshot.json"
            digest = hashlib.sha256(publication.payload).hexdigest()
            if publication_dir.exists():
                if (
                    snapshot_path.exists()
                    and hashlib.sha256(snapshot_path.read_bytes()).hexdigest() == digest
                ):
                    return
                raise OrganizationArtifactError("organization_publication_exists")
            if state is not None:
                if state.publications + 1 > self._max_publications:
                    raise OrganizationArtifactError("organization_quota_exceeded")
                if (
                    state.total_bytes + len(publication.payload) + _QUOTA_ALLOWANCE
                    > self._max_artifact_bytes
                ):
                    raise OrganizationArtifactError("organization_quota_exceeded")
            manifest = {
                "publication_id": publication_id,
                "snapshot_digest": digest,
                "run_id": run_id,
                "generated_tick": publication.generated_tick,
            }
            manifest_bytes = json.dumps(
                manifest, sort_keys=True, separators=(",", ":")
            ).encode()
            if len(manifest_bytes) > _MANIFEST_MAX_BYTES:
                raise OrganizationArtifactError("organization_size_limit")
            _atomic_write(snapshot_path, publication.payload)
            _atomic_write(publication_dir / "manifest.json", manifest_bytes)
            new_state = _StoredState(
                publication_id=publication_id,
                snapshot_digest=digest,
                publications=1 if state is None else state.publications + 1,
                total_bytes=(0 if state is None else state.total_bytes)
                + len(publication.payload),
            )
            state_bytes = json.dumps(
                {
                    "store_schema_version": _STORE_SCHEMA,
                    "run_id": run_id,
                    "publication_id": new_state.publication_id,
                    "snapshot_digest": new_state.snapshot_digest,
                    "publications": new_state.publications,
                    "total_bytes": new_state.total_bytes,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            if len(state_bytes) > _STATE_MAX_BYTES:
                raise OrganizationArtifactError("organization_size_limit")
            _atomic_write(run_dir / "state.json", state_bytes)
            _LOG.info(
                "organization_published run_id=%s publication_id=%s bytes=%s",
                run_id,
                publication_id,
                len(publication.payload),
            )
        finally:
            lock_path.unlink(missing_ok=True)


class FilesystemOrganizationReader(OrganizationReadPort):
    """Read committed publications without repairing or rewriting them."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def _load(self, run_id: str) -> OrganizationSnapshot:
        run_dir = self._root / _safe("run_id", run_id)
        state_path = run_dir / "state.json"
        if not state_path.exists():
            raise OrganizationArtifactError("organization_publication_missing")
        try:
            state = json.loads(state_path.read_bytes())
            committed = str(state["publication_id"])
            digest = str(state["snapshot_digest"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            _LOG.error("organization_store_corrupt run_id=%s code=state", run_id)
            raise OrganizationArtifactError("organization_store_corrupt") from exc
        snapshot_path = run_dir / "publications" / committed / "snapshot.json"
        if not snapshot_path.exists():
            raise OrganizationArtifactError("organization_publication_missing")
        payload = snapshot_path.read_bytes()
        snapshot = decode_organization_snapshot(payload)
        if snapshot.publication_id != committed:
            raise OrganizationArtifactError("organization_store_corrupt")
        if hashlib.sha256(payload).hexdigest() != digest:
            raise OrganizationArtifactError("organization_digest_mismatch")
        return snapshot

    def summary(self, run_id: str) -> OrganizationSummary | None:
        try:
            snapshot = self._load(run_id)
        except OrganizationArtifactError as exc:
            if exc.code == "organization_publication_missing":
                return None
            raise
        return OrganizationSummary(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            schema_version=snapshot.schema_version,
            generated_tick=snapshot.generated_tick,
            candidate_count=len(snapshot.candidates),
            edge_count=len(snapshot.edges),
            window_count=len(snapshot.windows),
            coverage=OrganizationCoverage(
                observed=snapshot.coverage.observed,
                expected=snapshot.coverage.expected,
                ratio=snapshot.coverage.ratio,
            ),
            provenance_code=snapshot.provenance_code,
        )

    def candidates(
        self,
        run_id: str,
        publication_id: str,
        offset: int,
        limit: int,
        status: str | None = None,
    ) -> OrganizationRowSelection:
        snapshot = self._load(run_id)
        if publication_id and snapshot.publication_id != publication_id:
            raise OrganizationArtifactError("organization_publication_missing")
        rows = tuple(
            candidate
            for candidate in snapshot.candidates
            if status is None or candidate.status == status
        )
        return select_organization_rows(
            rows, offset=offset, limit=limit, max_bytes=MAX_RESPONSE_BYTES
        )

    def candidate(
        self, run_id: str, publication_id: str, organization_id: str
    ) -> OrganizationCandidateRecord | None:
        snapshot = self._load(run_id)
        if publication_id and snapshot.publication_id != publication_id:
            raise OrganizationArtifactError("organization_publication_missing")
        for candidate in snapshot.candidates:
            if candidate.organization_id == organization_id:
                return candidate
        return None

    def lineage(
        self,
        run_id: str,
        publication_id: str,
        offset: int,
        limit: int,
        kind: str | None = None,
    ) -> OrganizationRowSelection:
        snapshot = self._load(run_id)
        if publication_id and snapshot.publication_id != publication_id:
            raise OrganizationArtifactError("organization_publication_missing")
        rows = tuple(
            edge for edge in snapshot.edges if kind is None or edge.kind == kind
        )
        return select_organization_rows(
            rows, offset=offset, limit=limit, max_bytes=MAX_RESPONSE_BYTES
        )


def create_organization_publisher(
    root: Path | None,
    *,
    max_publications: int = 16,
    max_artifact_bytes: int = 8 * 1024 * 1024,
) -> FilesystemOrganizationPublisher | None:
    """Return a publisher, or ``None`` when publication is disabled."""
    if root is None:
        return None
    return FilesystemOrganizationPublisher(
        root,
        max_publications=max_publications,
        max_artifact_bytes=max_artifact_bytes,
    )


def create_organization_reader(
    root: Path | None,
) -> FilesystemOrganizationReader | None:
    """Return a reader, or ``None`` when publication is disabled."""
    if root is None:
        return None
    return FilesystemOrganizationReader(root)
