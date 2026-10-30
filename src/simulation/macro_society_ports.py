"""Read and publication ports for macro-society snapshots."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from simulation.macro_society_models import (
    MacroSocietyArtifactError,
    MacroSocietyCoverage,
    MacroSocietySnapshot,
    MacroSocietySnapshotRef,
    require_macro_society_id,
    require_publication_id,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MAX_RESPONSE_BYTES",
    "MacroSocietyCursor",
    "MacroSocietyPublication",
    "MacroSocietyPublicationPort",
    "MacroSocietyReadPort",
    "MacroSocietyReadSession",
    "macro_society_query_fingerprint",
]

MAX_RESPONSE_BYTES: Final[int] = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class MacroSocietyPublication:
    """One snapshot plus its storage hints (metadata only)."""

    snapshot: MacroSocietySnapshot
    payload: bytes
    created_at_utc: str

    def __post_init__(self) -> None:
        if type(self.snapshot) is not MacroSocietySnapshot:
            raise MacroSocietyArtifactError("macro_society_invalid_snapshot")
        if not isinstance(self.payload, (bytes, bytearray)) or not self.payload:
            raise MacroSocietyArtifactError("macro_society_invalid_value")
        require_stable_id("created_at_utc", self.created_at_utc)

    @property
    def publication_id(self) -> str:
        return self.snapshot.publication_id


@dataclass(frozen=True, slots=True)
class MacroSocietyCursor:
    """A purpose-bound keyset cursor pinned to one publication."""

    purpose: str
    run_id: str
    publication_id: str
    snapshot_digest: str
    offset: int
    query_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "purpose", require_stable_id("purpose", self.purpose))
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        object.__setattr__(
            self, "publication_id", require_publication_id(self.publication_id)
        )
        digest = require_stable_id("snapshot_digest", self.snapshot_digest)
        if len(digest) != 64:
            raise MacroSocietyArtifactError("macro_society_invalid_digest")
        fingerprint = require_stable_id(
            "query_fingerprint", self.query_fingerprint
        )
        if len(fingerprint) != 64:
            raise MacroSocietyArtifactError("macro_society_invalid_digest")
        object.__setattr__(
            self, "offset", require_exact_nonneg_int("offset", self.offset)
        )


def macro_society_query_fingerprint(
    *,
    run_id: str,
    publication_id: str,
    purpose: str,
    filters: Mapping[str, object] | None = None,
) -> str:
    """Canonical fingerprint of a read query."""
    payload = {
        "run_id": require_stable_id("run_id", run_id),
        "publication_id": require_publication_id(publication_id),
        "purpose": require_stable_id("purpose", purpose),
        "filters": dict(sorted((filters or {}).items())),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class MacroSocietyReadSession:
    """A pinned publication and remaining response budget."""

    publication_id: str
    snapshot_digest: str
    remaining_bytes: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "publication_id", require_publication_id(self.publication_id)
        )
        digest = require_stable_id("snapshot_digest", self.snapshot_digest)
        if len(digest) != 64:
            raise MacroSocietyArtifactError("macro_society_invalid_digest")
        object.__setattr__(
            self,
            "remaining_bytes",
            require_exact_nonneg_int("remaining_bytes", self.remaining_bytes),
        )

    def charge(self, byte_count: int) -> MacroSocietyReadSession:
        """Return a session with ``byte_count`` deducted or fail closed."""
        amount = require_exact_nonneg_int("byte_count", byte_count)
        if amount > self.remaining_bytes:
            raise MacroSocietyArtifactError("macro_society_response_too_large")
        return MacroSocietyReadSession(
            publication_id=self.publication_id,
            snapshot_digest=self.snapshot_digest,
            remaining_bytes=self.remaining_bytes - amount,
        )


@dataclass(frozen=True, slots=True)
class MacroSocietySummary:
    """Publication summary served by the read adapter."""

    publication_id: str
    snapshot_digest: str
    schema_version: str
    policy_version: str
    run_id: str
    input_revision: str
    generated_tick: int
    window_count: int
    candidate_count: int
    edge_count: int
    coverage: MacroSocietyCoverage
    provenance_code: str


@runtime_checkable
class MacroSocietyReadPort(Protocol):
    """Read-only access to one committed publication."""

    def read_summary(self, run_id: str) -> MacroSocietySummary: ...

    def read_candidates(
        self,
        run_id: str,
        *,
        publication_id: str | None,
        offset: int,
        limit: int,
    ) -> tuple[tuple[object, ...], int | None]: ...

    def read_candidate(
        self, run_id: str, macro_society_id: str, *, publication_id: str | None
    ) -> object: ...

    def read_lineage(
        self,
        run_id: str,
        *,
        publication_id: str | None,
        offset: int,
        limit: int,
    ) -> tuple[tuple[object, ...], int | None]: ...


@runtime_checkable
class MacroSocietyPublicationPort(Protocol):
    """Append one immutable publication."""

    def publish(
        self, publication: MacroSocietyPublication
    ) -> MacroSocietySnapshotRef: ...


def require_known_candidate(
    snapshot: MacroSocietySnapshot, macro_society_id: str
) -> object:
    """Return one candidate record or fail closed."""
    wanted = require_macro_society_id(macro_society_id)
    for candidate in snapshot.candidates:
        if candidate.macro_society_id == wanted:
            return candidate
    raise MacroSocietyArtifactError("macro_society_unknown_society")
