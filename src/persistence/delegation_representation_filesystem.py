"""Atomic quota-bounded filesystem store for representation snapshots."""

from __future__ import annotations

import fcntl
import json
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final, cast

from simulation.delegation_representation_codec import (
    decode_delegation_representation_snapshot,
)
from simulation.delegation_representation_models import (
    DelegationRepresentationArtifactError,
    DelegationRepresentationSnapshot,
)
from simulation.delegation_representation_paging import (
    RepresentationRowSelection,
    select_representation_candidates,
    select_representation_lineage,
    select_representation_mandates,
)
from simulation.delegation_representation_ports import (
    MAX_CANDIDATE_DETAIL_ROWS,
    DelegationRepresentationCandidateDetail,
    DelegationRepresentationPortError,
    DelegationRepresentationPublication,
    DelegationRepresentationSummary,
    bounded_detail_rows,
)

__all__ = [
    "DELEGATION_REPRESENTATION_STORE_SCHEMA",
    "FilesystemDelegationRepresentationPublisher",
    "FilesystemDelegationRepresentationReader",
    "create_delegation_representation_publisher",
    "create_delegation_representation_reader",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "persistence.delegation_representation_filesystem"
)

DELEGATION_REPRESENTATION_STORE_SCHEMA: Final[str] = (
    "delegation-representation-store-v1"
)


def _atomic_json(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


@contextmanager
def _publish_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_state(root: Path) -> dict[str, object]:
    path = root / "state.json"
    if not path.exists():
        return {
            "schema": DELEGATION_REPRESENTATION_STORE_SCHEMA,
            "publications": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DelegationRepresentationArtifactError(
            "delegation_representation_snapshot_invalid"
        ) from exc
    if type(payload) is not dict or payload.get("schema") != (
        DELEGATION_REPRESENTATION_STORE_SCHEMA
    ):
        raise DelegationRepresentationArtifactError(
            "delegation_representation_snapshot_invalid"
        )
    if type(payload.get("publications")) is not list:
        raise DelegationRepresentationArtifactError(
            "delegation_representation_snapshot_invalid"
        )
    return payload


class FilesystemDelegationRepresentationPublisher:
    """Publisher port with per-run publication and cumulative byte quotas."""

    def __init__(
        self,
        root: Path | str,
        *,
        max_publications: int = 16,
        max_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self._root = Path(root)
        if type(max_publications) is not int or not 1 <= max_publications <= 1024:
            raise ValueError("representation publication cap is outside range")
        if type(max_bytes) is not int or not 1 <= max_bytes <= 268_435_456:
            raise ValueError("representation byte cap is outside range")
        self._max_publications = max_publications
        self._max_bytes = max_bytes

    def publish(self, publication: DelegationRepresentationPublication) -> None:
        payload_bytes = publication.payload
        try:
            decoded = decode_delegation_representation_snapshot(payload_bytes)
        except DelegationRepresentationArtifactError:
            raise
        if decoded.digest != publication.snapshot_digest:
            raise DelegationRepresentationArtifactError(
                "delegation_representation_digest_mismatch"
            )
        if decoded.publication_id != publication.publication_id:
            raise DelegationRepresentationArtifactError(
                "delegation_representation_snapshot_invalid"
            )
        with _publish_lock(self._root / ".publish.lock"):
            state = _read_state(self._root)
            entries = cast(list[dict[str, Any]], state["publications"])
            same_run = [
                entry for entry in entries if entry.get("run_id") == publication.run_id
            ]
            for entry in entries:
                if entry.get("publication_id") == publication.publication_id:
                    existing = self._root / str(entry.get("path"))
                    if existing.exists() and (existing.read_bytes() == payload_bytes):
                        return
                    raise DelegationRepresentationArtifactError(
                        "delegation_representation_publication_exists"
                    )
            if len(same_run) >= self._max_publications:
                raise DelegationRepresentationArtifactError(
                    "delegation_representation_size_limit"
                )
            total_bytes = sum(int(entry.get("bytes", 0)) for entry in entries)
            if total_bytes + len(payload_bytes) > self._max_bytes:
                raise DelegationRepresentationArtifactError(
                    "delegation_representation_size_limit"
                )
            relative = f"publications/{publication.publication_id}.json"
            path = self._root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.tmp")
            temporary.write_bytes(payload_bytes)
            os.replace(temporary, path)
            entries.append(
                {
                    "run_id": publication.run_id,
                    "publication_id": publication.publication_id,
                    "snapshot_digest": publication.snapshot_digest,
                    "generated_tick": publication.generated_tick,
                    "path": relative,
                    "bytes": len(payload_bytes),
                }
            )
            state["publications"] = entries
            _atomic_json(self._root / "state.json", state)
        _LOG.info("representation_store_published status=published")


class FilesystemDelegationRepresentationReader:
    """Reader port over committed representation publications."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    def _snapshot(self, run_id: str) -> DelegationRepresentationSnapshot:
        state = _read_state(self._root)
        entries = [
            entry
            for entry in cast(list[dict[str, Any]], state["publications"])
            if entry.get("run_id") == run_id
        ]
        if not entries:
            raise DelegationRepresentationPortError(
                "delegation_representation_not_found"
            )
        entry = entries[-1]
        path = self._root / str(entry.get("path"))
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise DelegationRepresentationPortError(
                "delegation_representation_not_found"
            ) from exc
        try:
            snapshot = decode_delegation_representation_snapshot(payload)
        except DelegationRepresentationArtifactError as exc:
            raise DelegationRepresentationPortError(exc.code) from exc
        if snapshot.digest != entry.get("snapshot_digest"):
            raise DelegationRepresentationPortError(
                "delegation_representation_not_found"
            )
        return snapshot

    def summary(self, *, run_id: str) -> DelegationRepresentationSummary:
        snapshot = self._snapshot(run_id)
        return DelegationRepresentationSummary(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            snapshot_digest=snapshot.digest,
            generated_tick=snapshot.generated_tick,
            mandate_count=snapshot.summary.mandate_count,
            position_count=snapshot.summary.position_count,
            revocation_count=snapshot.summary.revocation_count,
            conflict_count=snapshot.summary.conflict_count,
            candidate_count=snapshot.summary.candidate_count,
            lineage_edge_count=snapshot.summary.lineage_edge_count,
            owner_count=snapshot.summary.owner_count,
            coverage=snapshot.coverage,
            schema_version=snapshot.schema_version,
        )

    def candidates(
        self, *, run_id: str, offset: int = 0, limit: int = 100
    ) -> RepresentationRowSelection:
        return select_representation_candidates(
            self._snapshot(run_id), cursor_offset=offset, limit=limit
        )

    def candidate(
        self, *, run_id: str, candidate_id: str
    ) -> DelegationRepresentationCandidateDetail:
        snapshot = self._snapshot(run_id)
        candidate = next(
            (row for row in snapshot.candidates if row.candidate_id == candidate_id),
            None,
        )
        if candidate is None:
            raise DelegationRepresentationPortError(
                "delegation_representation_not_found"
            )
        mandates, truncated = bounded_detail_rows(
            tuple(
                row
                for row in snapshot.mandates
                if row.principal_kind == candidate.principal_kind
                and row.principal_token == candidate.principal_token
                and row.scope_kind == candidate.scope_kind
                and row.scope_subject_token == candidate.scope_subject_token
            ),
            maximum=MAX_CANDIDATE_DETAIL_ROWS,
        )
        return DelegationRepresentationCandidateDetail(
            candidate_id=candidate.candidate_id,
            principal_kind=candidate.principal_kind,
            principal_token=candidate.principal_token,
            scope_kind=candidate.scope_kind,
            scope_subject_token=candidate.scope_subject_token,
            status=candidate.status,
            coverage=candidate.coverage,
            representative_tokens=candidate.representative_tokens,
            mandate_count=len(mandates),
            mandates=mandates,
            mandates_truncated=truncated,
        )

    def mandate(self, *, run_id: str, mandate_id: str) -> object:
        snapshot = self._snapshot(run_id)
        for row in snapshot.mandates:
            if row.mandate_id == mandate_id:
                return row
        raise DelegationRepresentationPortError("delegation_representation_not_found")

    def mandates(
        self,
        *,
        run_id: str,
        offset: int = 0,
        limit: int = 100,
        candidate_id: str | None = None,
    ) -> RepresentationRowSelection:
        snapshot = self._snapshot(run_id)
        if candidate_id is None:
            return select_representation_mandates(
                snapshot, cursor_offset=offset, limit=limit
            )
        candidate = next(
            (row for row in snapshot.candidates if row.candidate_id == candidate_id),
            None,
        )
        if candidate is None:
            raise DelegationRepresentationPortError(
                "delegation_representation_not_found"
            )
        filtered = tuple(
            row
            for row in snapshot.mandates
            if row.principal_kind == candidate.principal_kind
            and row.principal_token == candidate.principal_token
            and row.scope_kind == candidate.scope_kind
            and row.scope_subject_token == candidate.scope_subject_token
        )
        return _select_rows(filtered, offset, limit)

    def positions(
        self,
        *,
        run_id: str,
        mandate_id: str,
        offset: int = 0,
        limit: int = 100,
    ) -> RepresentationRowSelection:
        snapshot = self._snapshot(run_id)
        filtered = tuple(
            row for row in snapshot.positions if row.mandate_id == mandate_id
        )
        return _select_rows(filtered, offset, limit)

    def revocations(
        self,
        *,
        run_id: str,
        mandate_id: str,
        offset: int = 0,
        limit: int = 100,
    ) -> RepresentationRowSelection:
        snapshot = self._snapshot(run_id)
        filtered = tuple(
            row for row in snapshot.revocations if row.mandate_id == mandate_id
        )
        return _select_rows(filtered, offset, limit)

    def lineage(
        self, *, run_id: str, offset: int = 0, limit: int = 100
    ) -> RepresentationRowSelection:
        return select_representation_lineage(
            self._snapshot(run_id), cursor_offset=offset, limit=limit
        )


def _select_rows(
    rows: tuple[object, ...], offset: int, limit: int
) -> RepresentationRowSelection:
    from simulation.delegation_representation_models import (
        DELEGATION_REPRESENTATION_PAGE_MAX_ROWS,
    )

    if type(offset) is not int or offset < 0:
        raise DelegationRepresentationPortError(
            "delegation_representation_cursor_invalid"
        )
    if type(limit) is not int or limit < 0:
        raise DelegationRepresentationPortError(
            "delegation_representation_cursor_invalid"
        )
    bounded = min(limit, DELEGATION_REPRESENTATION_PAGE_MAX_ROWS)
    selected = tuple(rows[offset : offset + bounded])
    next_offset = offset + len(selected)
    truncated = next_offset < len(rows)
    return RepresentationRowSelection(
        rows=selected,
        offset=offset,
        next_offset=next_offset if truncated else None,
        truncated=truncated,
    )


def create_delegation_representation_publisher(
    root: Path | str | None,
    *,
    max_publications: int = 16,
    max_bytes: int = 8 * 1024 * 1024,
) -> FilesystemDelegationRepresentationPublisher | None:
    if root is None:
        return None
    return FilesystemDelegationRepresentationPublisher(
        root, max_publications=max_publications, max_bytes=max_bytes
    )


def create_delegation_representation_reader(
    root: Path | str | None,
) -> FilesystemDelegationRepresentationReader | None:
    if root is None:
        return None
    return FilesystemDelegationRepresentationReader(root)
