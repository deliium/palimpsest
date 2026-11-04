"""Read/publication ports and purpose-bound cursors for representation."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from simulation.delegation_representation_models import (
    DELEGATION_REPRESENTATION_PAGE_MAX_ROWS,
    DelegationRepresentationArtifactError,
    DelegationRepresentationSnapshot,
)

__all__ = [
    "DELEGATION_REPRESENTATION_CURSOR_PURPOSES",
    "MAX_CANDIDATE_DETAIL_ROWS",
    "DelegationRepresentationCandidateDetail",
    "DelegationRepresentationCursor",
    "DelegationRepresentationPublication",
    "DelegationRepresentationPublicationPort",
    "DelegationRepresentationReadPort",
    "DelegationRepresentationSummary",
    "bounded_detail_rows",
    "delegation_representation_cursor_matches",
    "delegation_representation_query_fingerprint",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.delegation_representation_ports"
)

DELEGATION_REPRESENTATION_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "mandates",
    "mandate",
    "positions",
    "revocations",
    "lineage",
)
MAX_CANDIDATE_DETAIL_ROWS: Final[int] = 500


class DelegationRepresentationPortError(ValueError):
    """Stable-code representation port violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DelegationRepresentationPublication:
    run_id: str
    publication_id: str
    snapshot_digest: str
    payload: bytes
    generated_tick: int

    def __post_init__(self) -> None:
        if type(self.payload) is not bytes or not self.payload:
            raise DelegationRepresentationPortError(
                "delegation_representation_not_found"
            )


@dataclass(frozen=True, slots=True)
class DelegationRepresentationSummary:
    run_id: str
    publication_id: str
    snapshot_digest: str
    generated_tick: int
    mandate_count: int
    position_count: int
    revocation_count: int
    conflict_count: int
    candidate_count: int
    lineage_edge_count: int
    owner_count: int
    coverage: str
    schema_version: str


@dataclass(frozen=True, slots=True)
class DelegationRepresentationCandidateDetail:
    candidate_id: str
    principal_kind: str
    principal_token: str | None
    scope_kind: str
    scope_subject_token: str | None
    status: str
    coverage: str
    representative_tokens: tuple[str, ...]
    mandate_count: int
    mandates: tuple[object, ...] = ()
    mandates_truncated: bool = False


@dataclass(frozen=True, slots=True)
class DelegationRepresentationCursor:
    purpose: str
    run_id: str
    publication_id: str
    snapshot_digest: str
    offset: int
    query_fingerprint: str

    def __post_init__(self) -> None:
        if self.purpose not in DELEGATION_REPRESENTATION_CURSOR_PURPOSES:
            raise DelegationRepresentationPortError(
                "delegation_representation_cursor_invalid"
            )
        if type(self.offset) is not int or self.offset < 0:
            raise DelegationRepresentationPortError(
                "delegation_representation_cursor_invalid"
            )


def delegation_representation_query_fingerprint(
    *,
    purpose: str,
    run_id: str,
    publication_id: str,
    snapshot_digest: str,
    filters: Sequence[tuple[str, str]] = (),
) -> str:
    if purpose not in DELEGATION_REPRESENTATION_CURSOR_PURPOSES:
        raise DelegationRepresentationPortError(
            "delegation_representation_cursor_invalid"
        )
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


def delegation_representation_cursor_matches(
    cursor: DelegationRepresentationCursor,
    *,
    run_id: str,
    publication_id: str,
    snapshot_digest: str,
    fingerprint: str,
) -> bool:
    if type(cursor) is not DelegationRepresentationCursor:
        return False
    return (
        cursor.run_id == run_id
        and cursor.publication_id == publication_id
        and cursor.snapshot_digest == snapshot_digest
        and cursor.query_fingerprint == fingerprint
    )


def bounded_detail_rows(
    rows: Sequence[object], *, maximum: int = MAX_CANDIDATE_DETAIL_ROWS
) -> tuple[tuple[object, ...], bool]:
    limit = min(max(maximum, 0), DELEGATION_REPRESENTATION_PAGE_MAX_ROWS)
    if len(rows) <= limit:
        return tuple(rows), False
    return tuple(rows[:limit]), True


class DelegationRepresentationReadPort(Protocol):
    """Read-only representation port used by the API layer."""

    def summary(self, *, run_id: str) -> DelegationRepresentationSummary: ...

    def candidates(
        self, *, run_id: str, offset: int = 0, limit: int = 100
    ) -> object: ...

    def candidate(self, *, run_id: str, candidate_id: str) -> object: ...

    def mandate(self, *, run_id: str, mandate_id: str) -> object: ...

    def mandates(
        self,
        *,
        run_id: str,
        offset: int = 0,
        limit: int = 100,
        candidate_id: str | None = None,
    ) -> object: ...

    def positions(
        self,
        *,
        run_id: str,
        mandate_id: str,
        offset: int = 0,
        limit: int = 100,
    ) -> object: ...

    def revocations(
        self,
        *,
        run_id: str,
        mandate_id: str,
        offset: int = 0,
        limit: int = 100,
    ) -> object: ...

    def lineage(self, *, run_id: str, offset: int = 0, limit: int = 100) -> object: ...


class DelegationRepresentationPublicationPort(Protocol):
    """Opt-in publication port used by the research runner."""

    def publish(self, publication: DelegationRepresentationPublication) -> None: ...


def require_known_mandate(
    snapshot: DelegationRepresentationSnapshot, mandate_id: str
) -> object:
    if type(snapshot) is not DelegationRepresentationSnapshot:
        raise TypeError("snapshot must be DelegationRepresentationSnapshot")
    for mandate in snapshot.mandates:
        if mandate.mandate_id == mandate_id:
            return mandate
    raise DelegationRepresentationArtifactError("delegation_representation_not_found")
