"""Canonical ``delegation-representation-snapshot-v1`` records.

The snapshot is an independent analytical sibling. Every identity field is a
hashed token or an owner-safe anchor; raw agent ids and free-text scope subjects
never appear.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, fields
from typing import Any, Final, NoReturn

__all__ = [
    "DELEGATION_REPRESENTATION_ARTIFACT_ERROR_CODES",
    "DELEGATION_REPRESENTATION_MAX_CANDIDATES",
    "DELEGATION_REPRESENTATION_MAX_CONFLICTS",
    "DELEGATION_REPRESENTATION_MAX_LINEAGE_EDGES",
    "DELEGATION_REPRESENTATION_MAX_MANDATES",
    "DELEGATION_REPRESENTATION_MAX_POSITIONS",
    "DELEGATION_REPRESENTATION_PAGE_MAX_ROWS",
    "DELEGATION_REPRESENTATION_SNAPSHOT_MAX_BYTES",
    "DELEGATION_REPRESENTATION_SNAPSHOT_POLICY",
    "DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMA",
    "SUPPORTED_DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMAS",
    "DelegationRepresentationArtifactError",
    "DelegationRepresentationCandidateRow",
    "DelegationRepresentationConflictRow",
    "DelegationRepresentationLineageRow",
    "DelegationRepresentationMandateRow",
    "DelegationRepresentationMetricProvenanceRow",
    "DelegationRepresentationPositionRow",
    "DelegationRepresentationRevocationRow",
    "DelegationRepresentationSnapshot",
    "DelegationRepresentationSummaryRow",
    "empty_delegation_representation_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.delegation_representation_models"
)

DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMA: Final[str] = (
    "delegation-representation-snapshot-v1"
)
DELEGATION_REPRESENTATION_SNAPSHOT_POLICY: Final[str] = (
    "delegation-representation-snapshot-policy.v1"
)
SUPPORTED_DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMAS: Final[tuple[str, ...]] = (
    DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMA,
)

MAX_SNAPSHOT_MANDATES: Final[int] = 8192
MAX_SNAPSHOT_POSITIONS: Final[int] = 16384
MAX_SNAPSHOT_BYTES: Final[int] = 4 * 1024 * 1024
DELEGATION_REPRESENTATION_SNAPSHOT_MAX_BYTES: Final[int] = MAX_SNAPSHOT_BYTES
MAX_SNAPSHOT_CONFLICTS: Final[int] = 4096
MAX_SNAPSHOT_LINEAGE_EDGES: Final[int] = 8192
DELEGATION_REPRESENTATION_MAX_MANDATES: Final[int] = MAX_SNAPSHOT_MANDATES
DELEGATION_REPRESENTATION_MAX_POSITIONS: Final[int] = MAX_SNAPSHOT_POSITIONS
DELEGATION_REPRESENTATION_MAX_CONFLICTS: Final[int] = MAX_SNAPSHOT_CONFLICTS
DELEGATION_REPRESENTATION_MAX_LINEAGE_EDGES: Final[int] = MAX_SNAPSHOT_LINEAGE_EDGES
DELEGATION_REPRESENTATION_MAX_CANDIDATES: Final[int] = 2048
DELEGATION_REPRESENTATION_PAGE_MAX_ROWS: Final[int] = 500

PUBLICATION_ID_PREFIX: Final[str] = "drep-pub-"
_OWNER_LOCAL_PREFIXES: Final[tuple[str, ...]] = ("rmd-", "rmp-", "rmv-", "rmx-")
_FORBIDDEN_FIELDS: Final[frozenset[str]] = frozenset(
    {"truth", "verified", "legitimate", "permission", "authorized", "winner"}
)
_HEX16: Final[str] = "0123456789abcdef"

DELEGATION_REPRESENTATION_ARTIFACT_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "delegation_representation_snapshot_invalid",
        "delegation_representation_snapshot_unsupported",
        "delegation_representation_digest_mismatch",
        "delegation_representation_size_limit",
        "delegation_representation_not_found",
        "delegation_representation_publication_exists",
    }
)


class DelegationRepresentationArtifactError(ValueError):
    """Stable-code snapshot violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in DELEGATION_REPRESENTATION_ARTIFACT_ERROR_CODES:
            raise ValueError("delegation_representation_invalid_error_code")
        self.code = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise DelegationRepresentationArtifactError(code)


def _reject_forbidden(model: type[Any]) -> None:
    if {field.name for field in fields(model)} & _FORBIDDEN_FIELDS:
        _fail("delegation_representation_snapshot_invalid")


def _text(value: object, *, max_len: int = 128) -> str:
    if type(value) is not str or not value or len(value) > max_len:
        _fail("delegation_representation_snapshot_invalid")
    return value


def _optional_text(value: object, *, max_len: int = 128) -> str | None:
    if value is None:
        return None
    return _text(value, max_len=max_len)


def _tick(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        _fail("delegation_representation_snapshot_invalid")
    return value


def _count(value: object) -> int:
    return _tick(value)


def _token(value: object) -> str:
    text = _text(value, max_len=128)
    if len(text) == 16 and all(character in _HEX16 for character in text):
        return text
    return text


def _agent_token(value: object) -> str:
    text = _text(value, max_len=16)
    if len(text) != 16 or any(character not in _HEX16 for character in text):
        _fail("delegation_representation_snapshot_invalid")
    return text


def _principal_token(value: object) -> str | None:
    if value is None:
        return None
    text = _text(value, max_len=128)
    if len(text) == 16 and all(character in _HEX16 for character in text):
        return text
    if text.startswith("orgc-") or text.startswith("region"):
        return text
    _fail("delegation_representation_snapshot_invalid")


def _scope_token(value: object) -> str | None:
    if value is None:
        return None
    text = _text(value, max_len=32)
    if any(
        not (character.islower() or character.isdigit() or character in "_.:-")
        for character in text
    ):
        _fail("delegation_representation_snapshot_invalid")
    return text


def _digest(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _ordered(value: object) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail("delegation_representation_snapshot_invalid")
    return tuple(value)


@dataclass(frozen=True, slots=True)
class DelegationRepresentationSummaryRow:
    mandate_count: int = 0
    position_count: int = 0
    revocation_count: int = 0
    conflict_count: int = 0
    candidate_count: int = 0
    lineage_edge_count: int = 0
    owner_count: int = 0
    coverage: str = "complete"

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        for field in fields(type(self)):
            if field.name == "coverage":
                continue
            _count(getattr(self, field.name))
        if self.coverage not in {"complete", "partial"}:
            _fail("delegation_representation_snapshot_invalid")


@dataclass(frozen=True, slots=True)
class DelegationRepresentationCandidateRow:
    candidate_id: str
    principal_kind: str
    principal_token: str | None
    scope_kind: str
    scope_subject_token: str | None
    status: str
    representative_tokens: tuple[str, ...]
    lineage_kind: str
    coverage: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        if not self.candidate_id.startswith("rep-") or self.candidate_id.startswith(
            "rep-edge-"
        ):
            _fail("delegation_representation_snapshot_invalid")
        _text(self.principal_kind)
        _principal_token(self.principal_token)
        _text(self.scope_kind)
        _scope_token(self.scope_subject_token)
        _text(self.status)
        if isinstance(self.representative_tokens, (str, bytes)) or not isinstance(
            self.representative_tokens, (tuple, list)
        ):
            _fail("delegation_representation_snapshot_invalid")
        tokens = tuple(
            sorted({_agent_token(item) for item in self.representative_tokens})
        )
        object.__setattr__(self, "representative_tokens", tokens)
        _text(self.lineage_kind)
        if self.coverage not in {"complete", "partial"}:
            _fail("delegation_representation_snapshot_invalid")


@dataclass(frozen=True, slots=True)
class DelegationRepresentationMandateRow:
    mandate_id: str
    owner_token: str
    principal_kind: str
    principal_token: str | None
    representative_token: str
    scope_kind: str
    scope_subject_token: str | None
    duration_kind: str
    start_tick: int
    end_tick: int | None
    provenance: str
    status: str
    recognition_basis: str
    support_roots: int
    opposition_roots: int
    confidence_band: str
    coverage: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        if not self.mandate_id.startswith("rmd-"):
            _fail("delegation_representation_snapshot_invalid")
        _agent_token(self.owner_token)
        _text(self.principal_kind)
        _principal_token(self.principal_token)
        _agent_token(self.representative_token)
        _text(self.scope_kind)
        _scope_token(self.scope_subject_token)
        _text(self.duration_kind)
        _tick(self.start_tick)
        if self.end_tick is not None:
            _tick(self.end_tick)
        _text(self.provenance)
        _text(self.status)
        _text(self.recognition_basis)
        _count(self.support_roots)
        _count(self.opposition_roots)
        if self.confidence_band not in {"low", "mid", "high"}:
            _fail("delegation_representation_snapshot_invalid")
        if self.coverage not in {"complete", "partial"}:
            _fail("delegation_representation_snapshot_invalid")


@dataclass(frozen=True, slots=True)
class DelegationRepresentationPositionRow:
    position_id: str
    mandate_id: str
    owner_token: str
    actor_token: str
    stance: str
    provenance: str
    tick: int
    active: bool

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        if not self.position_id.startswith("rmp-") or not self.mandate_id.startswith(
            "rmd-"
        ):
            _fail("delegation_representation_snapshot_invalid")
        _agent_token(self.owner_token)
        _agent_token(self.actor_token)
        _text(self.stance)
        _text(self.provenance)
        _tick(self.tick)
        if type(self.active) is not bool:
            _fail("delegation_representation_snapshot_invalid")


@dataclass(frozen=True, slots=True)
class DelegationRepresentationRevocationRow:
    revocation_id: str
    mandate_id: str
    owner_token: str
    actor_token: str
    kind: str
    provenance: str
    tick: int
    contested: bool

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        if not self.revocation_id.startswith("rmv-") or not self.mandate_id.startswith(
            "rmd-"
        ):
            _fail("delegation_representation_snapshot_invalid")
        _agent_token(self.owner_token)
        _agent_token(self.actor_token)
        _text(self.kind)
        _text(self.provenance)
        _tick(self.tick)
        if type(self.contested) is not bool:
            _fail("delegation_representation_snapshot_invalid")


@dataclass(frozen=True, slots=True)
class DelegationRepresentationConflictRow:
    conflict_id: str
    owner_token: str
    mandate_ids: tuple[str, ...]
    kind: str
    status: str
    tick: int

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        if not self.conflict_id.startswith("rmx-"):
            _fail("delegation_representation_snapshot_invalid")
        _agent_token(self.owner_token)
        if isinstance(self.mandate_ids, (str, bytes)) or not isinstance(
            self.mandate_ids, (tuple, list)
        ):
            _fail("delegation_representation_snapshot_invalid")
        ids = tuple(sorted({_text(item) for item in self.mandate_ids}))
        if not ids or any(not item.startswith("rmd-") for item in ids):
            _fail("delegation_representation_snapshot_invalid")
        object.__setattr__(self, "mandate_ids", ids)
        _text(self.kind)
        if self.status != "unresolved":
            _fail("delegation_representation_snapshot_invalid")
        _tick(self.tick)


@dataclass(frozen=True, slots=True)
class DelegationRepresentationLineageRow:
    edge_id: str
    from_candidate_id: str
    to_candidate_id: str
    kind: str
    tick: int

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        if not self.edge_id.startswith("rep-edge-"):
            _fail("delegation_representation_snapshot_invalid")
        if not self.from_candidate_id.startswith(
            "rep-"
        ) or not self.to_candidate_id.startswith("rep-"):
            _fail("delegation_representation_snapshot_invalid")
        _text(self.kind)
        _tick(self.tick)


@dataclass(frozen=True, slots=True)
class DelegationRepresentationMetricProvenanceRow:
    family_id: str
    family_version: int
    document_digest: str

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        _text(self.family_id)
        _count(self.family_version)
        if (
            type(self.document_digest) is not str
            or len(self.document_digest) != 64
            or any(character not in _HEX16 for character in self.document_digest)
        ):
            _fail("delegation_representation_snapshot_invalid")


@dataclass(frozen=True, slots=True)
class DelegationRepresentationSnapshot:
    """One bounded canonical representation snapshot."""

    run_id: str
    generated_tick: int
    created_from: str
    coverage: str = "complete"
    summary: DelegationRepresentationSummaryRow = DelegationRepresentationSummaryRow()
    candidates: tuple[DelegationRepresentationCandidateRow, ...] = ()
    mandates: tuple[DelegationRepresentationMandateRow, ...] = ()
    positions: tuple[DelegationRepresentationPositionRow, ...] = ()
    revocations: tuple[DelegationRepresentationRevocationRow, ...] = ()
    conflicts: tuple[DelegationRepresentationConflictRow, ...] = ()
    lineage: tuple[DelegationRepresentationLineageRow, ...] = ()
    metric_provenance: tuple[DelegationRepresentationMetricProvenanceRow, ...] = ()
    policy_version: str = DELEGATION_REPRESENTATION_SNAPSHOT_POLICY
    schema_version: str = DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMA
    digest: str = ""
    publication_id: str = ""

    def __post_init__(self) -> None:
        _reject_forbidden(type(self))
        if (
            self.schema_version
            not in SUPPORTED_DELEGATION_REPRESENTATION_SNAPSHOT_SCHEMAS
        ):
            _fail("delegation_representation_snapshot_unsupported")
        if self.policy_version != DELEGATION_REPRESENTATION_SNAPSHOT_POLICY:
            _fail("delegation_representation_snapshot_invalid")
        _text(self.run_id)
        _tick(self.generated_tick)
        _text(self.created_from)
        if self.coverage not in {"complete", "partial"}:
            _fail("delegation_representation_snapshot_invalid")
        if type(self.summary) is not DelegationRepresentationSummaryRow:
            _fail("delegation_representation_snapshot_invalid")
        limits = (
            ("candidates", DELEGATION_REPRESENTATION_MAX_CANDIDATES, "candidate_id"),
            ("mandates", MAX_SNAPSHOT_MANDATES, "mandate_id"),
            ("positions", MAX_SNAPSHOT_POSITIONS, "position_id"),
            ("revocations", MAX_SNAPSHOT_POSITIONS, "revocation_id"),
            ("conflicts", MAX_SNAPSHOT_CONFLICTS, "conflict_id"),
            ("lineage", MAX_SNAPSHOT_LINEAGE_EDGES, "edge_id"),
            ("metric_provenance", 16, "family_id"),
        )
        for name, limit, id_field in limits:
            collection = _ordered(getattr(self, name))
            if len(collection) > limit:
                _fail("delegation_representation_size_limit")
            seen: set[object] = set()
            for row in collection:
                identifier = getattr(row, id_field)
                if identifier in seen:
                    _fail("delegation_representation_snapshot_invalid")
                seen.add(identifier)
            object.__setattr__(
                self,
                name,
                tuple(sorted(collection, key=lambda row: getattr(row, id_field))),
            )
        mandate_ids = {row.mandate_id for row in self.mandates}
        for row in self.positions:
            if row.mandate_id not in mandate_ids:
                _fail("delegation_representation_snapshot_invalid")
        for row in self.revocations:
            if row.mandate_id not in mandate_ids:
                _fail("delegation_representation_snapshot_invalid")
        for row in self.conflicts:
            if any(item not in mandate_ids for item in row.mandate_ids):
                _fail("delegation_representation_snapshot_invalid")
        candidate_ids = {row.candidate_id for row in self.candidates}
        for row in self.lineage:
            if row.from_candidate_id not in candidate_ids or (
                row.to_candidate_id not in candidate_ids
            ):
                _fail("delegation_representation_snapshot_invalid")
        expected = DelegationRepresentationSummaryRow(
            mandate_count=len(self.mandates),
            position_count=len(self.positions),
            revocation_count=len(self.revocations),
            conflict_count=len(self.conflicts),
            candidate_count=len(self.candidates),
            lineage_edge_count=len(self.lineage),
            owner_count=len({row.owner_token for row in self.mandates}),
            coverage=self.coverage,
        )
        if self.summary != expected:
            _fail("delegation_representation_snapshot_invalid")
        if self.digest and (
            type(self.digest) is not str
            or len(self.digest) != 64
            or any(character not in _HEX16 for character in self.digest)
        ):
            _fail("delegation_representation_snapshot_invalid")
        if self.publication_id and not self.publication_id.startswith(
            PUBLICATION_ID_PREFIX
        ):
            _fail("delegation_representation_snapshot_invalid")


def empty_delegation_representation_snapshot(
    run_id: str, *, generated_tick: int = 0
) -> DelegationRepresentationSnapshot:
    """Return one enabled-but-empty canonical snapshot."""

    return DelegationRepresentationSnapshot(
        run_id=run_id,
        generated_tick=generated_tick,
        created_from="0" * 64,
    )
