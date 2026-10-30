"""Bounded canonical ``organization-snapshot-v1`` artifact.

``simulation`` owns this schema and never imports ``analysis``. The artifact
publishes objective aggregate rows plus analytical candidates; owner-scoped claim
detail stays in the detached analysis layer. No owner id, ``orgc-`` id, label,
speech body, memory content, or resource balance appears here.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn, cast

from world.identifiers import require_exact_nonneg_int

__all__ = [
    "MAX_PAGE_ROWS",
    "MAX_RESPONSE_BYTES",
    "MAX_SNAPSHOT_BYTES",
    "MAX_SNAPSHOT_CANDIDATES",
    "MAX_SNAPSHOT_EDGES",
    "MAX_SNAPSHOT_MEMBERS",
    "MAX_SNAPSHOT_OBJECTIVE_ROWS",
    "MAX_SNAPSHOT_WINDOWS",
    "ORGANIZATION_SNAPSHOT_POLICY_VERSION",
    "ORGANIZATION_SNAPSHOT_SCHEMA_VERSION",
    "OrganizationArtifactError",
    "OrganizationCandidateRecord",
    "OrganizationCoverage",
    "OrganizationLineageEdgeRecord",
    "OrganizationMemberRecord",
    "OrganizationObjectiveRow",
    "OrganizationSnapshot",
    "OrganizationSnapshotRef",
    "OrganizationStructuralKind",
    "OrganizationStructuralRecord",
    "OrganizationWindowRecord",
    "empty_organization_snapshot",
    "require_organization_id",
    "require_publication_id",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.organization_models")

ORGANIZATION_SNAPSHOT_SCHEMA_VERSION: Final[str] = "organization-snapshot-v1"
ORGANIZATION_SNAPSHOT_POLICY_VERSION: Final[str] = "organization-analysis.v1"

MAX_SNAPSHOT_BYTES: Final[int] = 4 * 1024 * 1024
MAX_SNAPSHOT_CANDIDATES: Final[int] = 2048
MAX_SNAPSHOT_MEMBERS: Final[int] = 512
MAX_SNAPSHOT_EDGES: Final[int] = 16384
MAX_SNAPSHOT_WINDOWS: Final[int] = 512
MAX_SNAPSHOT_OBJECTIVE_ROWS: Final[int] = 4096
MAX_RESPONSE_BYTES: Final[int] = 2 * 1024 * 1024
MAX_PAGE_ROWS: Final[int] = 500

ORGANIZATION_ID_PREFIX: Final[str] = "org-"
PUBLICATION_ID_PREFIX: Final[str] = "org-edge-"
_ID_HEX_CHARS: Final[int] = 16

_ORGANIZATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^org-[0-9a-f]{{{_ID_HEX_CHARS}}}$"
)
_PUBLICATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^org-edge-[0-9a-f]{{{_ID_HEX_CHARS}}}$"
)
_SAFE_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

PROVENANCE_CODES: Final[frozenset[str]] = frozenset(
    {"ok", "member_list_truncated", "history_truncated", "lane_absent"}
)
CANDIDATE_STATUSES: Final[frozenset[str]] = frozenset(
    {"recognized", "partial", "disputed", "fragmented", "temporary", "dissolved"}
)
MEMBERSHIP_STATUSES: Final[frozenset[str]] = frozenset(
    {"explicit", "perceived", "disputed", "unknown", "former"}
)
TEMPORAL_SCOPES: Final[frozenset[str]] = frozenset({"ongoing", "temporary", "unknown"})
LINEAGE_KINDS: Final[frozenset[str]] = frozenset(
    {"continued", "transformed", "split", "merge", "dissolved", "emerged"}
)


class OrganizationStructuralKind(StrEnum):
    """Closed structural anchor family in the published artifact."""

    ROLE = "role"
    GOAL = "goal"
    RESOURCE = "resource"
    PROCEDURE = "procedure"
    RECORD = "record"
    COMMITMENT = "commitment"
    IDENTITY = "identity"


class OrganizationArtifactError(ValueError):
    """Fail-closed artifact error with a stable reason code only."""

    def __init__(self, code: str) -> None:
        self.code: str = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise OrganizationArtifactError(code)


def _tick(name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(name, value)
    except (TypeError, ValueError) as exc:
        raise OrganizationArtifactError("organization_invalid_value") from exc


def _string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        _fail("organization_invalid_value")
    return value


def _optional_string(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _string(name, value)


def _safe_token(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not _SAFE_TOKEN_PATTERN.match(value)
        or ".." in value
    ):
        _fail("organization_invalid_value")
    return value


def _sorted_ids(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        _fail("organization_invalid_value")
    items = tuple(_string(name, value) for value in cast('list[object]', values))
    if len(set(items)) != len(items) or items != tuple(sorted(items)):
        _fail("organization_invalid_value")
    return items


def require_organization_id(value: object) -> str:
    """Validate an exact ``org-`` plus 16 lowercase hex characters id."""
    if not isinstance(value, str) or not _ORGANIZATION_ID_PATTERN.match(value):
        _fail("organization_invalid_value")
    return value


def require_publication_id(value: object) -> str:
    """Validate an exact ``org-edge-`` plus 16 lowercase hex characters id."""
    if not isinstance(value, str) or not _PUBLICATION_ID_PATTERN.match(value):
        _fail("organization_invalid_value")
    return value


def require_snapshot_digest(value: object) -> str:
    """Validate a 64-character lowercase SHA-256 digest."""
    if not isinstance(value, str) or len(value) != 64:
        _fail("organization_invalid_value")
    if any(character not in "0123456789abcdef" for character in value):
        _fail("organization_invalid_value")
    return value


@dataclass(frozen=True, slots=True)
class OrganizationSnapshotRef:
    publication_id: str
    snapshot_digest: str
    schema_version: str
    run_id: str
    generated_tick: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "publication_id", require_publication_id(self.publication_id)
        )
        object.__setattr__(
            self, "snapshot_digest", require_snapshot_digest(self.snapshot_digest)
        )
        if self.schema_version != ORGANIZATION_SNAPSHOT_SCHEMA_VERSION:
            _fail("organization_invalid_value")
        object.__setattr__(self, "run_id", _safe_token("run_id", self.run_id))
        object.__setattr__(
            self, "generated_tick", _tick("generated_tick", self.generated_tick)
        )


@dataclass(frozen=True, slots=True)
class OrganizationMemberRecord:
    member_id: str
    status: str
    basis: str
    temporal_scope: str
    first_tick: int
    last_tick: int
    strength: float
    owner_support_count: int
    expires_tick: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "member_id", _string("member_id", self.member_id))
        if self.status not in MEMBERSHIP_STATUSES:
            _fail("organization_invalid_value")
        object.__setattr__(self, "basis", _string("basis", self.basis))
        if self.temporal_scope not in TEMPORAL_SCOPES:
            _fail("organization_invalid_value")
        first = _tick("first_tick", self.first_tick)
        last = _tick("last_tick", self.last_tick)
        if last < first:
            _fail("organization_invalid_value")
        if self.expires_tick is not None:
            object.__setattr__(
                self, "expires_tick", _tick("expires_tick", self.expires_tick)
            )
        if type(self.strength) is not float or not (0.0 <= self.strength <= 1.0):
            _fail("organization_invalid_value")
        object.__setattr__(
            self,
            "owner_support_count",
            require_exact_nonneg_int("owner_support_count", self.owner_support_count),
        )


@dataclass(frozen=True, slots=True)
class OrganizationStructuralRecord:
    kind: str
    anchor_id: str
    status: str
    first_tick: int
    last_tick: int
    resolved: bool = True

    def __post_init__(self) -> None:
        try:
            kind = OrganizationStructuralKind(self.kind)
        except ValueError as exc:
            raise OrganizationArtifactError("organization_invalid_value") from exc
        object.__setattr__(self, "kind", kind.value)
        object.__setattr__(self, "anchor_id", _string("anchor_id", self.anchor_id))
        object.__setattr__(self, "status", _string("status", self.status))
        first = _tick("first_tick", self.first_tick)
        last = _tick("last_tick", self.last_tick)
        if last < first:
            _fail("organization_invalid_value")
        if type(self.resolved) is not bool:
            _fail("organization_invalid_value")


@dataclass(frozen=True, slots=True)
class OrganizationCandidateRecord:
    organization_id: str
    creation_tick: int
    first_tick: int
    last_tick: int
    status: str
    temporal_scope: str
    self_identified: bool
    members: tuple[OrganizationMemberRecord, ...] = ()
    structure: tuple[OrganizationStructuralRecord, ...] = ()
    window_indexes: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "organization_id", require_organization_id(self.organization_id)
        )
        object.__setattr__(
            self, "creation_tick", _tick("creation_tick", self.creation_tick)
        )
        first = _tick("first_tick", self.first_tick)
        last = _tick("last_tick", self.last_tick)
        if last < first:
            _fail("organization_invalid_value")
        if self.status not in CANDIDATE_STATUSES:
            _fail("organization_invalid_value")
        if self.temporal_scope not in TEMPORAL_SCOPES:
            _fail("organization_invalid_value")
        if type(self.self_identified) is not bool:
            _fail("organization_invalid_value")
        members = tuple(self.members)
        if len(members) > MAX_SNAPSHOT_MEMBERS:
            _fail("organization_size_limit")
        seen_members: set[str] = set()
        for member in members:
            if type(member) is not OrganizationMemberRecord:
                _fail("organization_invalid_value")
            if member.member_id in seen_members:
                _fail("organization_duplicate_member")
            seen_members.add(member.member_id)
        object.__setattr__(
            self, "members", tuple(sorted(members, key=lambda item: item.member_id))
        )
        structure = tuple(self.structure)
        seen_structure: set[tuple[str, str]] = set()
        for item in structure:
            if type(item) is not OrganizationStructuralRecord:
                _fail("organization_invalid_value")
            key = (item.kind, item.anchor_id)
            if key in seen_structure:
                _fail("organization_invalid_value")
            seen_structure.add(key)
        object.__setattr__(
            self,
            "structure",
            tuple(sorted(structure, key=lambda item: (item.kind, item.anchor_id))),
        )
        indexes = tuple(self.window_indexes)
        if indexes != tuple(sorted(set(indexes))):
            _fail("organization_invalid_value")
        object.__setattr__(self, "window_indexes", indexes)

    @property
    def member_count(self) -> int:
        return len(self.members)

    def count(self, kind: OrganizationStructuralKind) -> int:
        return sum(1 for item in self.structure if item.kind == kind.value)

    @property
    def structural_channel_count(self) -> int:
        return len({item.kind for item in self.structure})


@dataclass(frozen=True, slots=True)
class OrganizationWindowRecord:
    window_index: int
    start_tick: int
    end_tick: int
    candidate_ids: tuple[str, ...]
    member_count: int
    overlap_member_count: int
    lane_presence: tuple[tuple[str, bool], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "window_index", _tick("window_index", self.window_index)
        )
        start = _tick("start_tick", self.start_tick)
        end = _tick("end_tick", self.end_tick)
        if end < start:
            _fail("organization_invalid_value")
        ids = tuple(require_organization_id(item) for item in self.candidate_ids)
        if len(set(ids)) != len(ids):
            _fail("organization_duplicate_candidate")
        object.__setattr__(self, "candidate_ids", tuple(sorted(ids)))
        object.__setattr__(
            self, "member_count", _tick("member_count", self.member_count)
        )
        object.__setattr__(
            self,
            "overlap_member_count",
            _tick("overlap_member_count", self.overlap_member_count),
        )
        lanes = tuple(self.lane_presence)
        for name, value in lanes:
            _string("lane", name)
            if type(value) is not bool:
                _fail("organization_invalid_value")
        object.__setattr__(self, "lane_presence", tuple(sorted(lanes)))


@dataclass(frozen=True, slots=True)
class OrganizationLineageEdgeRecord:
    kind: str
    tick: int
    from_id: str | None = None
    to_id: str | None = None
    jaccard: float | None = None
    containment: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in LINEAGE_KINDS:
            _fail("organization_invalid_value")
        object.__setattr__(self, "tick", _tick("tick", self.tick))
        for name in ("from_id", "to_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_organization_id(value))
        if self.kind == "emerged" and self.from_id is not None:
            _fail("organization_unknown_candidate")
        if self.kind == "dissolved" and self.to_id is not None:
            _fail("organization_unknown_candidate")
        for name in ("jaccard", "containment"):
            value = getattr(self, name)
            if value is not None:
                if type(value) is not float or not (0.0 <= value <= 1.0):
                    _fail("organization_invalid_value")


@dataclass(frozen=True, slots=True)
class OrganizationObjectiveRow:
    window_index: int
    tick: int
    member_count: int
    role_count: int
    goal_count: int
    resource_count: int
    procedure_count: int
    record_count: int
    commitment_count: int
    identity_count: int
    resolved_anchor_count: int
    unresolved_anchor_count: int

    def __post_init__(self) -> None:
        for name in (
            "window_index",
            "tick",
            "member_count",
            "role_count",
            "goal_count",
            "resource_count",
            "procedure_count",
            "record_count",
            "commitment_count",
            "identity_count",
            "resolved_anchor_count",
            "unresolved_anchor_count",
        ):
            _tick(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class OrganizationCoverage:
    observed: int
    expected: int
    ratio: float | None

    def __post_init__(self) -> None:
        observed = require_exact_nonneg_int("observed", self.observed)
        expected = require_exact_nonneg_int("expected", self.expected)
        if observed > expected:
            raise OrganizationArtifactError("organization_invalid_coverage")
        if expected == 0:
            ratio = None
        else:
            ratio = observed / expected
            if self.ratio is not None and abs(self.ratio - ratio) > 1e-9:
                raise OrganizationArtifactError("organization_invalid_coverage")
        if self.ratio is not None and not (0.0 <= self.ratio <= 1.0):
            raise OrganizationArtifactError("organization_invalid_coverage")
        object.__setattr__(self, "observed", observed)
        object.__setattr__(self, "expected", expected)
        object.__setattr__(self, "ratio", ratio)


@dataclass(frozen=True, slots=True)
class OrganizationSnapshot:
    schema_version: str
    policy_version: str
    run_id: str
    input_revision: str
    generated_tick: int
    publication_id: str
    coverage: OrganizationCoverage
    windows: tuple[OrganizationWindowRecord, ...] = ()
    candidates: tuple[OrganizationCandidateRecord, ...] = ()
    edges: tuple[OrganizationLineageEdgeRecord, ...] = ()
    objective_rows: tuple[OrganizationObjectiveRow, ...] = ()
    provenance_code: str = "ok"

    def __post_init__(self) -> None:
        if self.schema_version != ORGANIZATION_SNAPSHOT_SCHEMA_VERSION:
            _fail("organization_invalid_value")
        if self.policy_version != ORGANIZATION_SNAPSHOT_POLICY_VERSION:
            _fail("organization_invalid_value")
        object.__setattr__(self, "run_id", _safe_token("run_id", self.run_id))
        object.__setattr__(
            self, "input_revision", _safe_token("input_revision", self.input_revision)
        )
        object.__setattr__(
            self, "generated_tick", _tick("generated_tick", self.generated_tick)
        )
        if self.publication_id != "":
            require_publication_id(self.publication_id)
        if type(self.coverage) is not OrganizationCoverage:
            _fail("organization_invalid_coverage")
        candidates = tuple(self.candidates)
        if len(candidates) > MAX_SNAPSHOT_CANDIDATES:
            _fail("organization_size_limit")
        seen: set[str] = set()
        for candidate in candidates:
            if type(candidate) is not OrganizationCandidateRecord:
                _fail("organization_invalid_value")
            if candidate.organization_id in seen:
                _fail("organization_duplicate_candidate")
            seen.add(candidate.organization_id)
        object.__setattr__(
            self,
            "candidates",
            tuple(sorted(candidates, key=lambda item: item.organization_id)),
        )
        windows = tuple(self.windows)
        if len(windows) > MAX_SNAPSHOT_WINDOWS:
            _fail("organization_size_limit")
        for window in windows:
            if type(window) is not OrganizationWindowRecord:
                _fail("organization_invalid_value")
            for candidate_id in window.candidate_ids:
                if candidate_id not in seen:
                    _fail("organization_unknown_candidate")
        object.__setattr__(
            self, "windows", tuple(sorted(windows, key=lambda item: item.window_index))
        )
        edges = tuple(self.edges)
        if len(edges) > MAX_SNAPSHOT_EDGES:
            _fail("organization_size_limit")
        for edge in edges:
            if type(edge) is not OrganizationLineageEdgeRecord:
                _fail("organization_invalid_value")
            for endpoint in (edge.from_id, edge.to_id):
                if endpoint is not None and endpoint not in seen:
                    _fail("organization_unknown_candidate")
        object.__setattr__(self, "edges", edges)
        rows = tuple(self.objective_rows)
        if len(rows) > MAX_SNAPSHOT_OBJECTIVE_ROWS:
            _fail("organization_size_limit")
        for row in rows:
            if type(row) is not OrganizationObjectiveRow:
                _fail("organization_invalid_value")
        object.__setattr__(self, "objective_rows", rows)
        if self.provenance_code not in PROVENANCE_CODES:
            _fail("organization_invalid_value")


def empty_organization_snapshot(
    run_id: str, input_revision: str, generated_tick: int
) -> OrganizationSnapshot:
    """Return an absent-but-valid snapshot shell for one completed run."""
    return OrganizationSnapshot(
        schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
        policy_version=ORGANIZATION_SNAPSHOT_POLICY_VERSION,
        run_id=run_id,
        input_revision=input_revision,
        generated_tick=generated_tick,
        publication_id="",
        coverage=OrganizationCoverage(observed=0, expected=0, ratio=None),
    )
