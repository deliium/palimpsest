"""Atomic quota-bounded filesystem store for evidence-testimony snapshots.

Layout: ``<root>/state.json``, ``<root>/publications/<id>.json``, and
``<root>/.publish.lock``. Writers commit one immutable publication at a time;
readers never repair or mutate state.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final, cast

from simulation.evidence_testimony_codec import decode_evidence_testimony_snapshot
from simulation.evidence_testimony_models import (
    EvidenceTestimonyArtifactError,
    EvidenceTestimonySnapshot,
)
from simulation.evidence_testimony_paging import (
    EvidenceTestimonyRowSelection,
    select_evidence_candidates,
    select_evidence_contradictions,
    select_evidence_lineage,
    select_evidence_sources,
)
from simulation.evidence_testimony_ports import (
    MAX_CANDIDATE_DETAIL_ROWS,
    EvidenceTestimonyCandidateDetail,
    EvidenceTestimonyPortError,
    EvidenceTestimonyPublication,
    EvidenceTestimonySummary,
    bounded_detail_rows,
)

__all__ = [
    "EVIDENCE_TESTIMONY_STORE_SCHEMA",
    "FilesystemEvidenceTestimonyPublisher",
    "FilesystemEvidenceTestimonyReader",
    "create_evidence_testimony_publisher",
    "create_evidence_testimony_reader",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "persistence.evidence_testimony_filesystem"
)

EVIDENCE_TESTIMONY_STORE_SCHEMA: Final[str] = "evidence-testimony-store-v1"


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
            "schema": EVIDENCE_TESTIMONY_STORE_SCHEMA,
            "publications": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EvidenceTestimonyArtifactError(
            "evidence_testimony_invalid_snapshot"
        ) from exc
    if type(payload) is not dict or payload.get("schema") != (
        EVIDENCE_TESTIMONY_STORE_SCHEMA
    ):
        raise EvidenceTestimonyArtifactError("evidence_testimony_invalid_snapshot")
    if type(payload.get("publications")) is not list:
        raise EvidenceTestimonyArtifactError("evidence_testimony_invalid_snapshot")
    return payload


class FilesystemEvidenceTestimonyPublisher:
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
            raise ValueError("evidence publication cap is outside the supported range")
        if type(max_bytes) is not int or not 1 <= max_bytes <= 268_435_456:
            raise ValueError("evidence byte cap is outside the supported range")
        self._max_publications = max_publications
        self._max_bytes = max_bytes

    def publish(self, publication: EvidenceTestimonyPublication) -> None:
        payload_bytes = publication.payload.encode("utf-8")
        try:
            decoded = decode_evidence_testimony_snapshot(publication.payload)
        except EvidenceTestimonyArtifactError:
            raise
        if decoded.snapshot_digest != publication.snapshot_digest:
            raise EvidenceTestimonyArtifactError("evidence_testimony_digest_mismatch")
        if decoded.publication_id != publication.publication_id:
            raise EvidenceTestimonyArtifactError("evidence_testimony_invalid_snapshot")

        with _publish_lock(self._root / ".publish.lock"):
            state = _read_state(self._root)
            entries = cast(list[dict[str, Any]], state["publications"])
            same_run = [
                entry for entry in entries if entry.get("run_id") == publication.run_id
            ]
            for entry in entries:
                if entry.get("publication_id") == publication.publication_id:
                    existing = self._root / str(entry.get("path"))
                    if existing.exists() and (
                        existing.read_text(encoding="utf-8").rstrip("\n")
                        == publication.payload
                    ):
                        return
                    raise EvidenceTestimonyArtifactError(
                        "evidence_testimony_publication_exists"
                    )
            if len(same_run) >= self._max_publications:
                raise EvidenceTestimonyArtifactError("evidence_testimony_size_limit")
            total_bytes = sum(int(entry.get("bytes", 0)) for entry in entries)
            if total_bytes + len(payload_bytes) > self._max_bytes:
                raise EvidenceTestimonyArtifactError("evidence_testimony_size_limit")
            relative = f"publications/{publication.publication_id}.json"
            path = self._root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.tmp")
            temporary.write_text(publication.payload + "\n", encoding="utf-8")
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
        _LOG.info("evidence_testimony_published status=published")


class FilesystemEvidenceTestimonyReader:
    """Reader port over committed publications."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    def _snapshot(self, run_id: str) -> EvidenceTestimonySnapshot:
        try:
            state = _read_state(self._root)
        except EvidenceTestimonyArtifactError:
            raise
        entries = [
            entry
            for entry in cast(list[dict[str, Any]], state["publications"])
            if entry.get("run_id") == run_id
        ]
        if not entries:
            raise EvidenceTestimonyPortError("evidence_testimony_not_found")
        entry = entries[-1]
        path = self._root / str(entry.get("path"))
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise EvidenceTestimonyPortError("evidence_testimony_not_found") from exc
        try:
            snapshot = decode_evidence_testimony_snapshot(text.strip())
        except EvidenceTestimonyArtifactError as exc:
            raise EvidenceTestimonyPortError(exc.code) from exc
        if snapshot.snapshot_digest != entry.get("snapshot_digest"):
            raise EvidenceTestimonyPortError("evidence_testimony_not_found")
        return snapshot

    def summary(self, *, run_id: str) -> EvidenceTestimonySummary:
        snapshot = self._snapshot(run_id)
        return EvidenceTestimonySummary(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            snapshot_digest=snapshot.snapshot_digest,
            generated_tick=snapshot.generated_tick,
            candidate_count=snapshot.counts.candidate_count,
            source_count=snapshot.counts.source_count,
            testimony_count=snapshot.counts.testimony_count,
            item_count=snapshot.counts.item_count,
            custody_link_count=snapshot.counts.custody_link_count,
            contradiction_count=snapshot.counts.contradiction_count,
            evaluation_count=snapshot.counts.evaluation_count,
            edge_count=snapshot.counts.edge_count,
            coverage=snapshot.coverage,
            schema_version=snapshot.schema_version,
            window_count=snapshot.counts.window_count,
            provenance_code="evidence_testimony_published",
        )

    def candidates(
        self, *, run_id: str, offset: int = 0, limit: int = 100
    ) -> EvidenceTestimonyRowSelection:
        return select_evidence_candidates(
            self._snapshot(run_id), offset=offset, limit=limit
        )

    def sources(
        self, *, run_id: str, offset: int = 0, limit: int = 100
    ) -> EvidenceTestimonyRowSelection:
        return select_evidence_sources(
            self._snapshot(run_id), offset=offset, limit=limit
        )

    def contradictions(
        self, *, run_id: str, offset: int = 0, limit: int = 100
    ) -> EvidenceTestimonyRowSelection:
        return select_evidence_contradictions(
            self._snapshot(run_id), offset=offset, limit=limit
        )

    def lineage(
        self, *, run_id: str, offset: int = 0, limit: int = 100
    ) -> EvidenceTestimonyRowSelection:
        return select_evidence_lineage(
            self._snapshot(run_id), offset=offset, limit=limit
        )

    def candidate(
        self, *, run_id: str, candidate_id: str
    ) -> EvidenceTestimonyCandidateDetail:
        snapshot = self._snapshot(run_id)
        candidate = next(
            (row for row in snapshot.candidates if row.candidate_id == candidate_id),
            None,
        )
        if candidate is None:
            raise EvidenceTestimonyPortError("evidence_testimony_not_found")
        sources, sources_truncated = bounded_detail_rows(
            tuple(
                row
                for row in snapshot.sources
                if row.subject_token == candidate.subject_token
            ),
            maximum=MAX_CANDIDATE_DETAIL_ROWS,
        )
        contradictions, contradictions_truncated = bounded_detail_rows(
            tuple(
                row
                for row in snapshot.contradictions
                if row.candidate_id == candidate.candidate_id
            ),
            maximum=MAX_CANDIDATE_DETAIL_ROWS,
        )
        return EvidenceTestimonyCandidateDetail(
            candidate_id=candidate.candidate_id,
            subject_token=candidate.subject_token,
            source_kind_family=candidate.source_kind_family,
            owner_count=len(candidate.owner_tokens),
            status=candidate.status,
            coverage=candidate.coverage,
            item_count=candidate.item_count,
            source_count=candidate.source_count,
            testimony_count=candidate.testimony_count,
            contradiction_count=candidate.contradiction_count,
            first_tick=candidate.first_tick,
            last_tick=candidate.last_tick,
            sources=sources,
            contradictions=contradictions,
            custody_complete_count=sum(
                1
                for row in snapshot.sources
                if row.subject_token == candidate.subject_token
                and row.custody_status == "complete_belief"
            ),
            custody_incomplete_count=sum(
                1
                for row in snapshot.sources
                if row.subject_token == candidate.subject_token
                and row.custody_status == "incomplete_belief"
            ),
            custody_conflicting_count=sum(
                1
                for row in snapshot.sources
                if row.subject_token == candidate.subject_token
                and row.custody_status == "conflicting_belief"
            ),
            sources_truncated=sources_truncated,
            contradictions_truncated=contradictions_truncated,
        )


def create_evidence_testimony_publisher(
    root: Path | str | None,
    *,
    max_publications: int = 16,
    max_bytes: int = 8 * 1024 * 1024,
) -> FilesystemEvidenceTestimonyPublisher | None:
    if root is None:
        return None
    return FilesystemEvidenceTestimonyPublisher(
        root, max_publications=max_publications, max_bytes=max_bytes
    )


def create_evidence_testimony_reader(
    root: Path | str | None,
) -> FilesystemEvidenceTestimonyReader | None:
    if root is None:
        return None
    return FilesystemEvidenceTestimonyReader(root)
