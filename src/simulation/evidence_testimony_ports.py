"""Read/publication ports and purpose-bound cursors for evidence snapshots.

Cursors bind run, publication, digest, purpose, filter, and offset. A cursor
never authorizes a different run, publication, digest, purpose, or filter.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from simulation.evidence_testimony_models import (
    EVIDENCE_TESTIMONY_PAGE_MAX_ROWS,
    EvidenceTestimonyArtifactError,
    EvidenceTestimonySnapshot,
    EvidenceTestimonySnapshotRef,
)

__all__ = [
    "EVIDENCE_TESTIMONY_CURSOR_PURPOSES",
    "MAX_CANDIDATE_DETAIL_ROWS",
    "EvidenceTestimonyCandidateDetail",
    "EvidenceTestimonyCursor",
    "EvidenceTestimonyPublication",
    "EvidenceTestimonyPublicationPort",
    "EvidenceTestimonyReadPort",
    "EvidenceTestimonySummary",
    "evidence_testimony_cursor_matches",
    "evidence_testimony_query_fingerprint",
    "require_known_evidence_candidate",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.evidence_testimony_ports")

EVIDENCE_TESTIMONY_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "candidates",
    "candidate",
    "sources",
    "contradictions",
    "lineage",
)
MAX_CANDIDATE_DETAIL_ROWS: Final[int] = 500


class EvidenceTestimonyPortError(ValueError):
    """Stable-code evidence port violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class EvidenceTestimonyPublication:
    """One committed publication payload plus its identity."""

    run_id: str
    publication_id: str
    snapshot_digest: str
    payload: str
    generated_tick: int

    def __post_init__(self) -> None:
        if type(self.payload) is not str or not self.payload:
            raise EvidenceTestimonyPortError("evidence_testimony_not_found")


@dataclass(frozen=True, slots=True)
class EvidenceTestimonySummary:
    """Run-scoped evidence summary. Counts and coverage only."""

    run_id: str
    publication_id: str
    snapshot_digest: str
    generated_tick: int
    candidate_count: int
    source_count: int
    testimony_count: int
    item_count: int
    custody_link_count: int
    contradiction_count: int
    evaluation_count: int
    edge_count: int
    coverage: str
    schema_version: str
    window_count: int
    provenance_code: str


@dataclass(frozen=True, slots=True)
class EvidenceTestimonyCandidateDetail:
    """One candidate detail page with bounded related rows."""

    candidate_id: str
    subject_token: str
    source_kind_family: str
    owner_count: int
    status: str
    coverage: str
    item_count: int
    source_count: int
    testimony_count: int
    contradiction_count: int
    first_tick: int
    last_tick: int
    sources: tuple[object, ...] = ()
    contradictions: tuple[object, ...] = ()
    custody_complete_count: int = 0
    custody_incomplete_count: int = 0
    custody_conflicting_count: int = 0
    sources_truncated: bool = False
    contradictions_truncated: bool = False


@dataclass(frozen=True, slots=True)
class EvidenceTestimonyCursor:
    """Signed cursor binding run, publication, digest, purpose, filter, offset."""

    purpose: str
    run_id: str
    publication_id: str
    snapshot_digest: str
    offset: int
    query_fingerprint: str

    def __post_init__(self) -> None:
        if self.purpose not in EVIDENCE_TESTIMONY_CURSOR_PURPOSES:
            raise EvidenceTestimonyPortError("evidence_testimony_cursor_invalid")
        if type(self.offset) is not int or self.offset < 0:
            raise EvidenceTestimonyPortError("evidence_testimony_cursor_invalid")


def evidence_testimony_query_fingerprint(
    *,
    purpose: str,
    run_id: str,
    publication_id: str,
    snapshot_digest: str,
    filters: Sequence[tuple[str, str]] = (),
) -> str:
    """Return a deterministic fingerprint over the query identity and filters."""

    if purpose not in EVIDENCE_TESTIMONY_CURSOR_PURPOSES:
        raise EvidenceTestimonyPortError("evidence_testimony_cursor_invalid")
    payload = {
        "purpose": purpose,
        "run_id": run_id,
        "publication_id": publication_id,
        "snapshot_digest": snapshot_digest,
        "filters": [list(item) for item in sorted(filters)],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def evidence_testimony_cursor_matches(
    cursor: EvidenceTestimonyCursor,
    *,
    purpose: str,
    run_id: str,
    publication_id: str,
    snapshot_digest: str,
    query_fingerprint: str,
) -> bool:
    """Return whether the cursor may serve the requested page."""

    if type(cursor) is not EvidenceTestimonyCursor:
        return False
    return (
        cursor.purpose == purpose
        and cursor.run_id == run_id
        and cursor.publication_id == publication_id
        and cursor.snapshot_digest == snapshot_digest
        and cursor.query_fingerprint == query_fingerprint
    )


def require_known_evidence_candidate(
    snapshot: EvidenceTestimonySnapshot, candidate_id: str
) -> object:
    """Return one candidate record or fail closed."""

    if type(snapshot) is not EvidenceTestimonySnapshot:
        raise TypeError("snapshot must be EvidenceTestimonySnapshot")
    for candidate in snapshot.candidates:
        if candidate.candidate_id == candidate_id:
            return candidate
    raise EvidenceTestimonyArtifactError("evidence_testimony_not_found")


def bounded_detail_rows(
    rows: Sequence[object], *, maximum: int = MAX_CANDIDATE_DETAIL_ROWS
) -> tuple[tuple[object, ...], bool]:
    """Return a bounded detail row set and an explicit truncation flag."""

    limit = min(max(maximum, 0), EVIDENCE_TESTIMONY_PAGE_MAX_ROWS)
    if len(rows) <= limit:
        return tuple(rows), False
    return tuple(rows[:limit]), True


class EvidenceTestimonyReadPort(Protocol):
    """Read-only evidence port used by the API layer."""

    def summary(self, *, run_id: str) -> EvidenceTestimonySummary: ...

    def candidates(
        self, *, run_id: str, offset: int = 0, limit: int = 100
    ) -> object: ...

    def candidate(self, *, run_id: str, candidate_id: str) -> object: ...

    def sources(self, *, run_id: str, offset: int = 0, limit: int = 100) -> object: ...

    def contradictions(
        self, *, run_id: str, offset: int = 0, limit: int = 100
    ) -> object: ...

    def lineage(self, *, run_id: str, offset: int = 0, limit: int = 100) -> object: ...


class EvidenceTestimonyPublicationPort(Protocol):
    """Opt-in publication port used by the research runner."""

    def publish(self, publication: EvidenceTestimonyPublication) -> None: ...

    def read(self, *, run_id: str) -> EvidenceTestimonySnapshotRef | None: ...
