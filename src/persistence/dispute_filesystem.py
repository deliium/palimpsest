"""Atomic append-only filesystem store for ``dispute-resolution-snapshot-v1``."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final, cast

from simulation.dispute_codec import (
    decode_dispute_snapshot,
    dispute_snapshot_digest,
    encode_dispute_snapshot,
)
from simulation.dispute_models import (
    DisputeArtifactError,
    DisputeCandidateRecord,
    DisputeSnapshot,
)
from simulation.dispute_paging import (
    DisputeRowSelection,
    select_dispute_candidate_rows,
    select_dispute_claim_rows,
    select_dispute_lineage_rows,
    select_dispute_resolution_rows,
)
from simulation.dispute_ports import (
    MAX_CANDIDATE_DETAIL_ROWS,
    DisputeCandidateDetail,
    DisputePortError,
    DisputePublication,
    DisputeSummary,
)

__all__ = [
    "FilesystemDisputePublisher",
    "FilesystemDisputeReader",
    "create_dispute_publisher",
    "create_dispute_reader",
]

_LOG: Final[logging.Logger] = logging.getLogger("persistence.dispute_filesystem")

_STORE_SCHEMA: Final[str] = "dispute-resolution-store-v1"
_STATE_FILE: Final[str] = "state.json"
_PUBLICATION_DIR: Final[str] = "publications"
_LOCK_FILE: Final[str] = ".publish.lock"
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _fail(code: str = "dispute_invalid_value") -> None:
    raise DisputeArtifactError(code)


def _token(value: object) -> str:
    if type(value) is not str or not value or ".." in value:
        _fail()
    token = cast(str, value)
    if _TOKEN_PATTERN.match(token) is None:
        _fail()
    return token


def _fsync_dir(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def _publish_lock(root: Path) -> Iterator[None]:
    """Serialize publishers across processes when file locking is available."""
    try:
        import fcntl
    except ImportError:
        yield
        return
    root.mkdir(parents=True, exist_ok=True)
    with (root / _LOCK_FILE).open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_state(path: Path, *, missing_code: str) -> dict[str, object]:
    if not path.is_file():
        if missing_code == "dispute_invalid_value":
            _fail()
        raise DisputePortError(missing_code)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        _fail()
    state = cast(dict[str, object], data)
    if state.get("schema_version") != _STORE_SCHEMA:
        if missing_code == "dispute_invalid_value":
            _fail()
        _fail("dispute_digest_mismatch")
    if not isinstance(state.get("publications"), dict):
        _fail()
    return state


def _write_json_atomic(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


class FilesystemDisputePublisher:
    """Append-only publisher with one atomic state commit point."""

    def __init__(
        self,
        root: Path,
        *,
        max_publications: int = 16,
        max_artifact_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self._root = Path(root)
        self._publications = self._root / _PUBLICATION_DIR
        self._max_publications = max_publications
        self._max_artifact_bytes = max_artifact_bytes

    def _state(self) -> dict[str, object]:
        path = self._root / _STATE_FILE
        if not path.is_file():
            return {"schema_version": _STORE_SCHEMA, "publications": {}}
        return _read_state(path, missing_code="dispute_invalid_value")

    def publish(self, publication: DisputePublication) -> str:
        if type(publication) is not DisputePublication:
            raise TypeError("publication must be DisputePublication")
        run_id = _token(publication.run_id)
        publication_id = _token(publication.publication_id)
        payload = bytes(publication.payload)
        if len(payload) > self._max_artifact_bytes:
            _fail("dispute_quota_exceeded")
        if dispute_snapshot_digest(payload) != publication.snapshot_digest:
            _fail("dispute_digest_mismatch")
        self._root.mkdir(parents=True, exist_ok=True)
        self._publications.mkdir(parents=True, exist_ok=True)
        with _publish_lock(self._root):
            state = self._state()
            entries = cast(dict[str, object], state["publications"])
            existing = entries.get(publication_id)
            if isinstance(existing, dict):
                existing_path = self._publications / f"{publication_id}.json"
                if existing_path.is_file() and existing_path.read_bytes() == payload:
                    return publication_id
                _LOG.warning(
                    "dispute_store duplicate publication_id=%s run=%s",
                    publication_id,
                    run_id,
                )
                _fail("dispute_publication_exists")
            if len(entries) >= self._max_publications:
                _fail("dispute_quota_exceeded")
            cumulative = sum(
                int(cast(Any, cast(dict[str, object], entry).get("bytes", 0)))
                for entry in entries.values()
            )
            if cumulative + len(payload) > self._max_artifact_bytes:
                _fail("dispute_quota_exceeded")
            target = self._publications / f"{publication_id}.json"
            temporary = self._publications / f".{publication_id}.tmp"
            try:
                temporary.write_bytes(payload)
                with temporary.open("rb") as handle:
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            except BaseException:
                try:
                    temporary.unlink()
                except OSError:
                    pass
                raise
            _fsync_dir(self._publications)
            entries[publication_id] = {
                "run_id": run_id,
                "generated_tick": int(publication.generated_tick),
                "snapshot_digest": publication.snapshot_digest,
                "bytes": len(payload),
            }
            _write_json_atomic(self._root / _STATE_FILE, state)
            _fsync_dir(self._root)
        _LOG.info("dispute_store published=%s run=%s", publication_id, run_id)
        return publication_id


class FilesystemDisputeReader:
    """Read-only reader over one committed store state."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._publications = self._root / _PUBLICATION_DIR

    def _state(self) -> dict[str, object]:
        return _read_state(
            self._root / _STATE_FILE,
            missing_code="dispute_not_found",
        )

    def _snapshot(self, run_id: str) -> tuple[DisputeSnapshot, dict[str, object]]:
        state = self._state()
        entries = cast(dict[str, object], state["publications"])
        matches = [
            (publication_id, cast(dict[str, object], entry))
            for publication_id, entry in entries.items()
            if cast(dict[str, object], entry).get("run_id") == run_id
        ]
        if not matches:
            raise DisputePortError("dispute_not_found")
        publication_id, entry = max(
            matches,
            key=lambda item: (
                int(cast(Any, item[1].get("generated_tick", 0))),
                item[0],
            ),
        )
        path = self._publications / f"{publication_id}.json"
        if not path.is_file():
            raise DisputePortError("dispute_not_found")
        payload = path.read_bytes()
        if dispute_snapshot_digest(payload) != entry.get("snapshot_digest"):
            _fail("dispute_digest_mismatch")
        snapshot = decode_dispute_snapshot(payload)
        if (
            snapshot.ref.publication_id != publication_id
            or snapshot.ref.generated_tick
            != int(cast(Any, entry.get("generated_tick", 0)))
        ):
            _fail("dispute_digest_mismatch")
        return snapshot, entry

    def summary(self, run_id: str) -> DisputeSummary:
        snapshot, _ = self._snapshot(run_id)
        return DisputeSummary(
            run_id=snapshot.ref.run_id,
            publication_id=snapshot.ref.publication_id,
            snapshot_digest=dispute_snapshot_digest(encode_dispute_snapshot(snapshot)),
            generated_tick=snapshot.ref.generated_tick,
            candidate_count=len(snapshot.candidates),
            case_count=len(snapshot.cases),
            claim_count=len(snapshot.claims),
            counterclaim_count=snapshot.counts.counterclaim_count,
            testimony_count=len(snapshot.testimony),
            evidence_count=len(snapshot.evidence),
            resolution_count=len(snapshot.resolutions),
            accepted_count=snapshot.counts.accepted_count,
            rejected_count=snapshot.counts.rejected_count,
            edge_count=len(snapshot.lineage),
            coverage=snapshot.coverage,
            schema_version=snapshot.schema_version,
            window_count=len(snapshot.windows),
            provenance_code=snapshot.provenance_code,
        )

    def candidates(
        self,
        run_id: str,
        *,
        status: str | None,
        offset: int,
        limit: int,
    ) -> DisputeRowSelection:
        snapshot, _ = self._snapshot(run_id)
        return select_dispute_candidate_rows(
            snapshot.candidates,
            status=status,
            offset=offset,
            limit=limit,
        )

    def candidate(self, run_id: str, candidate_id: str) -> DisputeCandidateRecord:
        snapshot, _ = self._snapshot(run_id)
        for item in snapshot.candidates:
            if item.candidate_id == candidate_id:
                return item
        raise DisputePortError("dispute_not_found")

    def detail(self, run_id: str, candidate_id: str) -> DisputeCandidateDetail:
        snapshot, _ = self._snapshot(run_id)
        candidate = next(
            (item for item in snapshot.candidates if item.candidate_id == candidate_id),
            None,
        )
        if candidate is None:
            raise DisputePortError("dispute_not_found")
        claims = tuple(
            item for item in snapshot.claims if item.candidate_id == candidate_id
        )
        resolutions = tuple(
            item for item in snapshot.resolutions if item.candidate_id == candidate_id
        )
        case_refs = {item.case_ref for item in claims} | {
            item.case_ref for item in resolutions
        }
        claim_ids = {item.claim_id for item in claims}
        resolution_refs = {item.resolution_ref for item in resolutions}
        testimony = tuple(
            item for item in snapshot.testimony if item.claim_id in claim_ids
        )
        evidence = tuple(
            item for item in snapshot.evidence if item.claim_id in claim_ids
        )
        rule_references = tuple(
            item
            for item in snapshot.rule_references
            if item.case_ref in case_refs and item.claim_ref in claim_ids
        )
        authority_references = tuple(
            item for item in snapshot.authority_references if item.case_ref in case_refs
        )
        mediation_references = tuple(
            item for item in snapshot.mediation_references if item.case_ref in case_refs
        )
        responses = tuple(
            item
            for item in snapshot.responses
            if item.resolution_ref in resolution_refs
        )
        cap = MAX_CANDIDATE_DETAIL_ROWS
        truncated = any(
            len(rows) > cap
            for rows in (
                testimony,
                evidence,
                rule_references,
                authority_references,
                mediation_references,
                responses,
            )
        )
        return DisputeCandidateDetail(
            candidate=candidate,
            testimony=testimony[:cap],
            evidence=evidence[:cap],
            rule_references=rule_references[:cap],
            authority_references=authority_references[:cap],
            mediation_references=mediation_references[:cap],
            responses=responses[:cap],
            truncated=truncated,
        )

    def claims(
        self,
        run_id: str,
        *,
        candidate_id: str,
        role: str | None,
        offset: int,
        limit: int,
    ) -> DisputeRowSelection:
        snapshot, _ = self._snapshot(run_id)
        return select_dispute_claim_rows(
            snapshot.claims,
            candidate_id=candidate_id,
            role=role,
            offset=offset,
            limit=limit,
        )

    def resolutions(
        self,
        run_id: str,
        *,
        candidate_id: str,
        status: str | None,
        offset: int,
        limit: int,
    ) -> DisputeRowSelection:
        snapshot, _ = self._snapshot(run_id)
        return select_dispute_resolution_rows(
            snapshot.resolutions,
            candidate_id=candidate_id,
            status=status,
            offset=offset,
            limit=limit,
        )

    def lineage(
        self,
        run_id: str,
        *,
        kind: str | None,
        offset: int,
        limit: int,
    ) -> DisputeRowSelection:
        snapshot, _ = self._snapshot(run_id)
        return select_dispute_lineage_rows(
            snapshot.lineage,
            kind=kind,
            offset=offset,
            limit=limit,
        )


def create_dispute_publisher(
    root: Path | None,
    *,
    max_publications: int = 16,
    max_artifact_bytes: int = 8 * 1024 * 1024,
) -> FilesystemDisputePublisher | None:
    if root is None:
        return None
    return FilesystemDisputePublisher(
        root,
        max_publications=max_publications,
        max_artifact_bytes=max_artifact_bytes,
    )


def create_dispute_reader(root: Path | None) -> FilesystemDisputeReader | None:
    if root is None:
        return None
    return FilesystemDisputeReader(root)
