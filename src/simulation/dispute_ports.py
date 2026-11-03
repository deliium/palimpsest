"""Read and publication ports for ``dispute-resolution-snapshot-v1``.

Simulation owns the cursor payload and matching only. The API layer signs and
expires cursors; no HTTP, analysis, or persistence type is imported here.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Final, Protocol

from simulation.dispute_models import (
    MAX_DISPUTE_SNAPSHOT_BYTES,
    DisputeArtifactError,
    DisputeAuthorityReferenceRecord,
    DisputeCandidateRecord,
    DisputeCoverage,
    DisputeEvidenceRecord,
    DisputeMediationReferenceRecord,
    DisputePortError,
    DisputeResolutionResponseRecord,
    DisputeRuleReferenceRecord,
    DisputeTestimonyRecord,
    require_dispute_candidate_id,
    require_dispute_publication_id,
    require_dispute_snapshot_digest,
)
from simulation.dispute_paging import DisputeRowSelection

__all__ = [
    "DISPUTE_CURSOR_PURPOSES",
    "MAX_CANDIDATE_DETAIL_ROWS",
    "DisputeCandidateDetail",
    "DisputeCursor",
    "DisputePortError",
    "DisputePublication",
    "DisputePublicationPort",
    "DisputeReadPort",
    "DisputeSummary",
    "dispute_cursor_matches",
    "dispute_query_fingerprint",
    "require_known_dispute_candidate",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.dispute_ports")

DISPUTE_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "candidates",
    "candidate",
    "claims",
    "resolutions",
    "lineage",
)

MAX_CANDIDATE_DETAIL_ROWS: Final[int] = 500


def _fingerprint(value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise DisputePortError("dispute_cursor_invalid")
    return value


@dataclass(frozen=True, slots=True)
class DisputePublication:
    run_id: str
    publication_id: str
    snapshot_digest: str
    payload: bytes
    generated_tick: int

    def __post_init__(self) -> None:
        if type(self.run_id) is not str or not self.run_id:
            raise DisputePortError("dispute_not_found")
        if type(self.publication_id) is not str:
            raise DisputePortError("dispute_not_found")
        try:
            require_dispute_publication_id(self.publication_id)
            require_dispute_snapshot_digest(self.snapshot_digest)
        except DisputeArtifactError as exc:
            raise DisputePortError("dispute_not_found") from exc
        if not isinstance(self.payload, (bytes, bytearray)) or not self.payload:
            raise DisputePortError("dispute_not_found")
        if len(self.payload) > MAX_DISPUTE_SNAPSHOT_BYTES:
            raise DisputePortError("dispute_cursor_invalid")
        if type(self.generated_tick) is not int or self.generated_tick < 0:
            raise DisputePortError("dispute_not_found")


@dataclass(frozen=True, slots=True)
class DisputeSummary:
    run_id: str
    publication_id: str
    snapshot_digest: str
    generated_tick: int
    candidate_count: int
    case_count: int
    claim_count: int
    counterclaim_count: int
    testimony_count: int
    evidence_count: int
    resolution_count: int
    accepted_count: int
    rejected_count: int
    edge_count: int
    coverage: DisputeCoverage
    schema_version: str = "dispute-resolution-snapshot-v1"
    window_count: int = 0
    provenance_code: str = "ok"

    def __post_init__(self) -> None:
        if type(self.run_id) is not str or not self.run_id:
            raise DisputePortError("dispute_not_found")
        try:
            require_dispute_publication_id(self.publication_id)
            require_dispute_snapshot_digest(self.snapshot_digest)
        except DisputeArtifactError as exc:
            raise DisputePortError("dispute_not_found") from exc
        if type(self.generated_tick) is not int or self.generated_tick < 0:
            raise DisputePortError("dispute_not_found")
        for name in (
            "candidate_count",
            "case_count",
            "claim_count",
            "counterclaim_count",
            "testimony_count",
            "evidence_count",
            "resolution_count",
            "accepted_count",
            "rejected_count",
            "edge_count",
            "window_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise DisputeArtifactError("dispute_invalid_value")
        if type(self.coverage) is not DisputeCoverage:
            raise DisputeArtifactError("dispute_invalid_value")
        if self.schema_version != "dispute-resolution-snapshot-v1":
            raise DisputeArtifactError("dispute_invalid_value")
        if self.provenance_code not in {"ok", "partial", "truncated", "empty"}:
            raise DisputeArtifactError("dispute_invalid_value")


@dataclass(frozen=True, slots=True)
class DisputeCandidateDetail:
    """Bounded server-derived relations for one published candidate."""

    candidate: DisputeCandidateRecord
    testimony: tuple[DisputeTestimonyRecord, ...] = ()
    evidence: tuple[DisputeEvidenceRecord, ...] = ()
    rule_references: tuple[DisputeRuleReferenceRecord, ...] = ()
    authority_references: tuple[DisputeAuthorityReferenceRecord, ...] = ()
    mediation_references: tuple[DisputeMediationReferenceRecord, ...] = ()
    responses: tuple[DisputeResolutionResponseRecord, ...] = ()
    truncated: bool = False

    def __post_init__(self) -> None:
        if type(self.candidate) is not DisputeCandidateRecord:
            raise DisputePortError("dispute_not_found")
        for name, expected in (
            ("testimony", DisputeTestimonyRecord),
            ("evidence", DisputeEvidenceRecord),
            ("rule_references", DisputeRuleReferenceRecord),
            ("authority_references", DisputeAuthorityReferenceRecord),
            ("mediation_references", DisputeMediationReferenceRecord),
            ("responses", DisputeResolutionResponseRecord),
        ):
            rows = getattr(self, name)
            if type(rows) is not tuple:
                raise DisputeArtifactError("dispute_invalid_value")
            if len(rows) > MAX_CANDIDATE_DETAIL_ROWS:
                raise DisputeArtifactError("dispute_size_limit")
            if any(type(row) is not expected for row in rows):
                raise DisputeArtifactError("dispute_invalid_value")
        if type(self.truncated) is not bool:
            raise DisputeArtifactError("dispute_invalid_value")

    @property
    def coverage(self) -> DisputeCoverage:
        return self.candidate.coverage


@dataclass(frozen=True, slots=True)
class DisputeCursor:
    purpose: str
    run_id: str
    publication_id: str
    snapshot_digest: str
    offset: int
    query_fingerprint: str

    def __post_init__(self) -> None:
        if self.purpose not in DISPUTE_CURSOR_PURPOSES:
            raise DisputePortError("dispute_cursor_purpose")
        if type(self.offset) is not int or self.offset < 0:
            raise DisputePortError("dispute_cursor_invalid")
        if type(self.run_id) is not str or not self.run_id:
            raise DisputePortError("dispute_cursor_invalid")
        try:
            require_dispute_publication_id(self.publication_id)
            require_dispute_snapshot_digest(self.snapshot_digest)
        except DisputeArtifactError as exc:
            raise DisputePortError("dispute_cursor_invalid") from exc
        _fingerprint(self.query_fingerprint)


class DisputeReadPort(Protocol):
    def summary(self, run_id: str) -> DisputeSummary: ...

    def candidates(
        self,
        run_id: str,
        *,
        status: str | None,
        offset: int,
        limit: int,
    ) -> DisputeRowSelection: ...

    def candidate(self, run_id: str, candidate_id: str) -> DisputeCandidateRecord: ...

    def detail(self, run_id: str, candidate_id: str) -> DisputeCandidateDetail: ...

    def claims(
        self,
        run_id: str,
        *,
        candidate_id: str,
        role: str | None,
        offset: int,
        limit: int,
    ) -> DisputeRowSelection: ...

    def resolutions(
        self,
        run_id: str,
        *,
        candidate_id: str,
        status: str | None,
        offset: int,
        limit: int,
    ) -> DisputeRowSelection: ...

    def lineage(
        self,
        run_id: str,
        *,
        kind: str | None,
        offset: int,
        limit: int,
    ) -> DisputeRowSelection: ...


class DisputePublicationPort(Protocol):
    def publish(self, publication: DisputePublication) -> str: ...


def dispute_query_fingerprint(
    purpose: str,
    run_id: str,
    publication_id: str,
    filters: tuple[tuple[str, str], ...] = (),
) -> str:
    """Return a sorted canonical fingerprint for one query shape."""
    if purpose not in DISPUTE_CURSOR_PURPOSES:
        raise DisputePortError("dispute_cursor_purpose")
    payload = {
        "purpose": purpose,
        "run_id": run_id,
        "publication_id": publication_id,
        "filters": sorted(filters),
    }
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def dispute_cursor_matches(
    cursor: DisputeCursor,
    *,
    purpose: str,
    run_id: str,
    publication_id: str,
    snapshot_digest: str,
    offset: int,
    fingerprint: str,
) -> bool:
    """Return whether a cursor still binds to the same publication and query."""
    if type(cursor) is not DisputeCursor:
        return False
    return (
        cursor.purpose == purpose
        and cursor.run_id == run_id
        and cursor.publication_id == publication_id
        and cursor.snapshot_digest == snapshot_digest
        and cursor.offset == offset
        and cursor.query_fingerprint == fingerprint
    )


def require_known_dispute_candidate(value: object | None, field_name: str) -> object:
    """Require one known candidate-record value; unknown values fail closed."""
    if value is None:
        _LOG.warning(
            "dispute_unknown field=%s reason_code=dispute_not_found",
            field_name,
        )
        raise DisputePortError("dispute_not_found")
    return value


def require_known_dispute_candidate_id(value: object) -> str:
    """Require one syntactically valid published candidate id."""
    return require_dispute_candidate_id(value)
