"""Neutral organization read and publication ports."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from simulation.organization_models import (
    MAX_RESPONSE_BYTES,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    OrganizationArtifactError,
    OrganizationCandidateRecord,
    OrganizationCoverage,
    OrganizationSnapshot,
    require_organization_id,
    require_publication_id,
    require_snapshot_digest,
)
from simulation.organization_paging import OrganizationRowSelection

__all__ = [
    "ORGANIZATION_CURSOR_PURPOSES",
    "OrganizationCursor",
    "OrganizationPublication",
    "OrganizationPublicationPort",
    "OrganizationReadPort",
    "OrganizationReadSession",
    "OrganizationSummary",
    "organization_query_fingerprint",
    "require_known_organization",
]

ORGANIZATION_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "organization_summary",
    "organization_candidates",
    "organization_candidate",
    "organization_lineage",
)


class OrganizationReadPort(Protocol):
    """Read-only surface over one committed publication."""

    def summary(self, run_id: str) -> OrganizationSummary | None: ...

    def candidates(
        self,
        run_id: str,
        publication_id: str,
        offset: int,
        limit: int,
        status: str | None = None,
    ) -> OrganizationRowSelection: ...

    def candidate(
        self, run_id: str, publication_id: str, organization_id: str
    ) -> OrganizationCandidateRecord | None: ...

    def lineage(
        self,
        run_id: str,
        publication_id: str,
        offset: int,
        limit: int,
        kind: str | None = None,
    ) -> OrganizationRowSelection: ...


class OrganizationPublicationPort(Protocol):
    """Write-only surface for one completed-run publication."""

    def publish(self, publication: OrganizationPublication) -> None: ...


@dataclass(frozen=True, slots=True)
class OrganizationPublication:
    run_id: str
    publication_id: str
    snapshot_digest: str
    payload: bytes
    generated_tick: int

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id:
            raise OrganizationArtifactError("organization_invalid_value")
        require_publication_id(self.publication_id)
        require_snapshot_digest(self.snapshot_digest)
        if not isinstance(self.payload, (bytes, bytearray)):
            raise OrganizationArtifactError("organization_invalid_value")
        if type(self.generated_tick) is not int or self.generated_tick < 0:
            raise OrganizationArtifactError("organization_invalid_value")


@dataclass(frozen=True, slots=True)
class OrganizationSummary:
    run_id: str
    publication_id: str
    schema_version: str
    generated_tick: int
    candidate_count: int
    edge_count: int
    window_count: int
    coverage: OrganizationCoverage
    provenance_code: str

    def __post_init__(self) -> None:
        require_publication_id(self.publication_id)
        if self.schema_version != ORGANIZATION_SNAPSHOT_SCHEMA_VERSION:
            raise OrganizationArtifactError("organization_invalid_value")
        for name in (
            "generated_tick",
            "candidate_count",
            "edge_count",
            "window_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise OrganizationArtifactError("organization_invalid_value")
        if type(self.coverage) is not OrganizationCoverage:
            raise OrganizationArtifactError("organization_invalid_coverage")


@dataclass(frozen=True, slots=True)
class OrganizationCursor:
    purpose: str
    run_id: str
    publication_id: str
    snapshot_digest: str
    offset: int
    query_fingerprint: str

    def __post_init__(self) -> None:
        if self.purpose not in ORGANIZATION_CURSOR_PURPOSES:
            raise OrganizationArtifactError("organization_cursor_invalid")
        require_publication_id(self.publication_id)
        require_snapshot_digest(self.snapshot_digest)
        if type(self.offset) is not int or self.offset < 0:
            raise OrganizationArtifactError("organization_cursor_invalid")
        if (
            not isinstance(self.query_fingerprint, str)
            or len(self.query_fingerprint) != 64
        ):
            raise OrganizationArtifactError("organization_cursor_invalid")


@dataclass(slots=True)
class OrganizationReadSession:
    """A byte budget for one read response."""

    charged: int = 0
    max_bytes: int = MAX_RESPONSE_BYTES

    def charge(self, size: int) -> None:
        if type(size) is not int or size < 0:
            raise OrganizationArtifactError("organization_response_limit")
        if self.charged + size > self.max_bytes:
            raise OrganizationArtifactError("organization_response_limit")
        self.charged += size


def organization_query_fingerprint(
    run_id: str,
    publication_id: str,
    purpose: str,
    filters: Mapping[str, object] | None = None,
) -> str:
    """Bind purpose, run, publication, and filters into one 64-hex digest."""
    if purpose not in ORGANIZATION_CURSOR_PURPOSES:
        raise OrganizationArtifactError("organization_cursor_invalid")
    require_publication_id(publication_id)
    payload = {
        "run_id": run_id,
        "publication_id": publication_id,
        "purpose": purpose,
        "filters": dict(sorted((filters or {}).items())),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def require_known_organization(
    snapshot: OrganizationSnapshot, organization_id: str
) -> OrganizationCandidateRecord:
    """Return one published candidate or fail with a stable code."""
    require_organization_id(organization_id)
    for candidate in snapshot.candidates:
        if candidate.organization_id == organization_id:
            return candidate
    raise OrganizationArtifactError("organization_unknown_candidate")
