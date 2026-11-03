"""Bounded canonical ``formal-rule-snapshot-v1`` contracts.

The snapshot is an independent read-only artifact. It never grants world
authority, never creates an objective rule, and never reuses organization
snapshot schemas.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, cast

FORMAL_RULE_SNAPSHOT_SCHEMA: Final[str] = "formal-rule-snapshot-v1"
FORMAL_RULE_SNAPSHOT_POLICY_VERSION: Final[str] = "formal-rule-analysis.v1"
SUPPORTED_FORMAL_RULE_SNAPSHOT_SCHEMAS: Final[tuple[str, ...]] = (
    FORMAL_RULE_SNAPSHOT_SCHEMA,
)
FORMAL_RULE_SNAPSHOT_ID_HEX_LEN: Final[int] = 16
FORMAL_RULE_CANDIDATE_ID_PREFIX: Final[str] = "frule-"
FORMAL_RULE_PUBLISHED_RULE_ID_PREFIX: Final[str] = "frul-"
FORMAL_RULE_PUBLISHED_VERSION_ID_PREFIX: Final[str] = "fruv-"
FORMAL_RULE_EDGE_ID_PREFIX: Final[str] = "frule-edge-"
FORMAL_RULE_PUBLICATION_ID_PREFIX: Final[str] = "frule-pub-"

MAX_FORMAL_RULE_SNAPSHOT_BYTES: Final[int] = 4 * 1024 * 1024
MAX_FORMAL_RULE_CANDIDATES: Final[int] = 2048
MAX_FORMAL_RULE_RULES: Final[int] = 4096
MAX_FORMAL_RULE_VERSIONS: Final[int] = 8192
MAX_FORMAL_RULE_WINDOWS: Final[int] = 512
MAX_FORMAL_RULE_OBJECTIVE_ROWS: Final[int] = 4096
MAX_FORMAL_RULE_RULES_PER_CANDIDATE: Final[int] = 64
MAX_FORMAL_RULE_VERSIONS_PER_RULE: Final[int] = 32
MAX_RESPONSE_BYTES: Final[int] = 2 * 1024 * 1024
MAX_PAGE_ROWS: Final[int] = 500

FORMAL_RULE_ARTIFACT_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "formal_rule_invalid_value",
        "formal_rule_digest_mismatch",
        "formal_rule_size_limit",
        "formal_rule_page_offset",
        "formal_rule_page_limit",
        "formal_rule_unknown",
        "formal_rule_cursor_invalid",
        "formal_rule_publication_exists",
        "formal_rule_run_incomplete",
        "formal_rule_publication_failed",
    }
)

_QUANTUM: Final[Decimal] = Decimal("0.000001")
_HEX64_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_OWNER_LOCAL_PREFIXES: Final[tuple[str, ...]] = (
    "frs-",
    "frl-",
    "frv-",
    "fre-",
    "frp-",
    "frr-",
    "frx-",
)
_FOREIGN_PREFIXES: Final[tuple[str, ...]] = (
    "org-",
    "msoc-",
    "orgc-",
    "orgd-",
    "orga-",
    "orgp-",
)
_PROVENANCE_CODES: Final[frozenset[str]] = frozenset(
    {"ok", "partial", "truncated", "empty"}
)
_CANDIDATE_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "recognized",
        "partial",
        "contested",
        "fragmented",
        "temporary",
        "dissolved",
    }
)
_STAGES: Final[frozenset[str]] = frozenset(
    {"habit", "expectation", "norm", "documented", "recognized_enforcement"}
)
_CONSTRAINTS: Final[frozenset[str]] = frozenset(
    {"prohibition", "obligation", "permission"}
)
_RECOGNITIONS: Final[frozenset[str]] = frozenset(
    {"unrecognized", "claimed", "recognized", "contested"}
)
_SCOPES: Final[frozenset[str]] = frozenset(
    {"person", "place", "resource", "action", "collective", "unspecified"}
)
_LINEAGE_KINDS: Final[frozenset[str]] = frozenset(
    {"continued", "transformed", "split", "merge", "dissolved", "emerged"}
)
_WRITTEN_STATUSES: Final[frozenset[str]] = frozenset(
    {"intact", "damaged", "missing", "unknown", "none"}
)


class FormalRuleArtifactError(ValueError):
    """Stable-code snapshot contract violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in FORMAL_RULE_ARTIFACT_ERROR_CODES:
            raise ValueError("formal_rule_invalid_error_code")
        self.code: str = code
        super().__init__(code)


def _fail(code: str = "formal_rule_invalid_value") -> None:
    raise FormalRuleArtifactError(code)


def _text(value: object) -> str:
    if type(value) is not str or not value:
        _fail()
    return cast(str, value)


def _tick(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        _fail()
    return cast(int, value)


def _count(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        _fail()
    return cast(int, value)


def _unit(value: object) -> float:
    if type(value) is not float:
        _fail()
    if value != value or value in (float("inf"), float("-inf")):
        _fail()
    quantized = float(Decimal(str(value)).quantize(_QUANTUM, rounding=ROUND_HALF_UP))
    if quantized < 0.0 or quantized > 1.0:
        _fail()
    return quantized


def _require_enum(value: object, allowed: frozenset[str]) -> str:
    token = _text(value)
    if token not in allowed:
        _fail()
    return token


def _require_id(value: object, prefix: str) -> str:
    token = _text(value)
    pattern = re.compile(
        rf"^{re.escape(prefix)}[0-9a-f]{{{FORMAL_RULE_SNAPSHOT_ID_HEX_LEN}}}$"
    )
    if pattern.match(token) is None:
        _fail()
    return token


def _reject_foreign_ids(token: str) -> None:
    if token.startswith(_OWNER_LOCAL_PREFIXES) or token.startswith(_FOREIGN_PREFIXES):
        _fail()


def require_formal_rule_candidate_id(value: object) -> str:
    return _require_id(value, FORMAL_RULE_CANDIDATE_ID_PREFIX)


def require_formal_rule_rule_id(value: object) -> str:
    return _require_id(value, FORMAL_RULE_PUBLISHED_RULE_ID_PREFIX)


def require_formal_rule_version_id(value: object) -> str:
    return _require_id(value, FORMAL_RULE_PUBLISHED_VERSION_ID_PREFIX)


def require_formal_rule_edge_id(value: object) -> str:
    return _require_id(value, FORMAL_RULE_EDGE_ID_PREFIX)


def require_formal_rule_publication_id(value: object) -> str:
    return _require_id(value, FORMAL_RULE_PUBLICATION_ID_PREFIX)


def _derive(domain: str, material: tuple[str, ...]) -> str:
    payload = "\x1f".join((domain, *material))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[
        :FORMAL_RULE_SNAPSHOT_ID_HEX_LEN
    ]


def derive_formal_rule_rule_id(
    candidate_id: str,
    stage: str,
    constraint_kind: str,
    action_token: str,
    authority_kind: str,
) -> str:
    """Derive a published ``frul-`` id without owner-local fields."""
    body = _derive(
        "formal-rule-public",
        (
            require_formal_rule_candidate_id(candidate_id),
            _require_enum(stage, _STAGES),
            _require_enum(constraint_kind, _CONSTRAINTS),
            _text(action_token),
            _text(authority_kind),
        ),
    )
    return f"{FORMAL_RULE_PUBLISHED_RULE_ID_PREFIX}{body}"


def derive_formal_rule_version_id(
    rule_id: str, version_number: int, content_digest: str
) -> str:
    """Derive a published ``fruv-`` id from rule, number, and content."""
    if type(version_number) is not int or version_number < 1:
        _fail()
    if type(content_digest) is not str or _HEX64_PATTERN.match(content_digest) is None:
        _fail()
    body = _derive(
        "formal-rule-public-version",
        (
            require_formal_rule_rule_id(rule_id),
            str(version_number),
            content_digest,
        ),
    )
    return f"{FORMAL_RULE_PUBLISHED_VERSION_ID_PREFIX}{body}"


def require_snapshot_digest(value: object) -> str:
    if type(value) is not str or _HEX64_PATTERN.match(value) is None:
        _fail()
    return cast(str, value)


@dataclass(frozen=True, slots=True)
class FormalRuleSnapshotRef:
    run_id: str
    input_revision: str
    generated_tick: int
    publication_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id))
        object.__setattr__(self, "input_revision", _text(self.input_revision))
        object.__setattr__(self, "generated_tick", _tick(self.generated_tick))
        object.__setattr__(
            self,
            "publication_id",
            require_formal_rule_publication_id(self.publication_id),
        )


@dataclass(frozen=True, slots=True)
class FormalRuleCoverage:
    observed: int
    expected: int
    partial: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed", _count(self.observed))
        object.__setattr__(self, "expected", _count(self.expected))
        if self.observed > self.expected:
            _fail()
        if type(self.partial) is not bool:
            _fail()
        if self.partial and self.observed >= self.expected:
            _fail()


@dataclass(frozen=True, slots=True)
class FormalRuleWrittenRepresentationRecord:
    status: str = "none"
    artifact_present: bool = False
    artifact_revision: int | None = None
    repository_present: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "status", _require_enum(self.status, _WRITTEN_STATUSES)
        )
        if type(self.artifact_present) is not bool:
            _fail()
        if type(self.repository_present) is not bool:
            _fail()
        if self.artifact_revision is not None:
            object.__setattr__(
                self, "artifact_revision", _count(self.artifact_revision)
            )


@dataclass(frozen=True, slots=True)
class FormalRuleCandidateRecord:
    candidate_id: str
    status: str
    scope_kind: str
    scope_digest: str
    action_token: str
    constraint_kinds: tuple[str, ...]
    stage: str
    authority_kinds: tuple[str, ...]
    system_count: int
    rule_count: int
    version_count: int
    competing_candidate_ids: tuple[str, ...]
    first_tick: int
    last_tick: int
    coverage: FormalRuleCoverage

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "candidate_id", require_formal_rule_candidate_id(self.candidate_id)
        )
        object.__setattr__(
            self, "status", _require_enum(self.status, _CANDIDATE_STATUSES)
        )
        object.__setattr__(self, "scope_kind", _require_enum(self.scope_kind, _SCOPES))
        if (
            type(self.scope_digest) is not str
            or _HEX64_PATTERN.match(self.scope_digest) is None
        ):
            _fail()
        object.__setattr__(self, "action_token", _text(self.action_token))
        object.__setattr__(
            self, "constraint_kinds", tuple(sorted(set(self.constraint_kinds)))
        )
        for token in self.constraint_kinds:
            _require_enum(token, _CONSTRAINTS)
        object.__setattr__(self, "stage", _require_enum(self.stage, _STAGES))
        object.__setattr__(
            self, "authority_kinds", tuple(sorted(set(self.authority_kinds)))
        )
        object.__setattr__(self, "system_count", _count(self.system_count))
        object.__setattr__(self, "rule_count", _count(self.rule_count))
        object.__setattr__(self, "version_count", _count(self.version_count))
        competing = tuple(
            sorted(
                require_formal_rule_candidate_id(item)
                for item in self.competing_candidate_ids
            )
        )
        object.__setattr__(self, "competing_candidate_ids", competing)
        object.__setattr__(self, "first_tick", _tick(self.first_tick))
        object.__setattr__(self, "last_tick", _tick(self.last_tick))
        if self.last_tick < self.first_tick:
            _fail()


@dataclass(frozen=True, slots=True)
class FormalRuleVersionRecord:
    version_id: str
    rule_id: str
    version_number: int
    stage: str
    constraint_kind: str
    scope_kind: str
    scope_digest: str
    action_token: str
    authority_kind: str
    recognition: str
    written_representation: FormalRuleWrittenRepresentationRecord
    sanction_kinds: tuple[str, ...]
    exception_count: int
    tick: int
    revision_kind: str
    supersedes_version_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "version_id", require_formal_rule_version_id(self.version_id)
        )
        object.__setattr__(self, "rule_id", require_formal_rule_rule_id(self.rule_id))
        if self.version_number < 1:
            _fail()
        object.__setattr__(self, "stage", _require_enum(self.stage, _STAGES))
        object.__setattr__(
            self, "constraint_kind", _require_enum(self.constraint_kind, _CONSTRAINTS)
        )
        object.__setattr__(self, "scope_kind", _require_enum(self.scope_kind, _SCOPES))
        if (
            type(self.scope_digest) is not str
            or _HEX64_PATTERN.match(self.scope_digest) is None
        ):
            _fail()
        object.__setattr__(self, "action_token", _text(self.action_token))
        object.__setattr__(self, "authority_kind", _text(self.authority_kind))
        object.__setattr__(
            self, "recognition", _require_enum(self.recognition, _RECOGNITIONS)
        )
        if (
            type(self.written_representation)
            is not FormalRuleWrittenRepresentationRecord
        ):
            _fail()
        object.__setattr__(
            self, "sanction_kinds", tuple(sorted(set(self.sanction_kinds)))
        )
        object.__setattr__(self, "exception_count", _count(self.exception_count))
        object.__setattr__(self, "tick", _tick(self.tick))
        object.__setattr__(self, "revision_kind", _text(self.revision_kind))
        if self.supersedes_version_id is not None:
            object.__setattr__(
                self,
                "supersedes_version_id",
                require_formal_rule_version_id(self.supersedes_version_id),
            )


@dataclass(frozen=True, slots=True)
class FormalRuleRecord:
    rule_id: str
    candidate_id: str
    stage: str
    constraint_kind: str
    scope_kind: str
    action_token: str
    authority_kind: str
    recognition: str
    written_representation: FormalRuleWrittenRepresentationRecord
    sanction_kinds: tuple[str, ...]
    exception_count: int
    version_count: int
    latest_version: int
    proponent_count: int
    response_counts: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", require_formal_rule_rule_id(self.rule_id))
        object.__setattr__(
            self, "candidate_id", require_formal_rule_candidate_id(self.candidate_id)
        )
        object.__setattr__(self, "stage", _require_enum(self.stage, _STAGES))
        object.__setattr__(
            self, "constraint_kind", _require_enum(self.constraint_kind, _CONSTRAINTS)
        )
        object.__setattr__(self, "scope_kind", _require_enum(self.scope_kind, _SCOPES))
        object.__setattr__(self, "action_token", _text(self.action_token))
        object.__setattr__(self, "authority_kind", _text(self.authority_kind))
        object.__setattr__(
            self, "recognition", _require_enum(self.recognition, _RECOGNITIONS)
        )
        if (
            type(self.written_representation)
            is not FormalRuleWrittenRepresentationRecord
        ):
            _fail()
        object.__setattr__(
            self, "sanction_kinds", tuple(sorted(set(self.sanction_kinds)))
        )
        object.__setattr__(self, "exception_count", _count(self.exception_count))
        object.__setattr__(self, "version_count", _count(self.version_count))
        if self.version_count < 1:
            _fail()
        object.__setattr__(self, "latest_version", _count(self.latest_version))
        object.__setattr__(self, "proponent_count", _count(self.proponent_count))
        object.__setattr__(
            self,
            "response_counts",
            tuple(
                sorted(
                    (_text(kind), _count(count)) for kind, count in self.response_counts
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class FormalRuleObjectiveRow:
    tick: int
    observed_artifact_count: int
    observed_repository_count: int
    observed_occurrence_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "tick", _tick(self.tick))
        for name in (
            "observed_artifact_count",
            "observed_repository_count",
            "observed_occurrence_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class FormalRuleWindowRecord:
    start_tick: int
    end_tick: int
    owner_count: int
    candidate_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "start_tick", _tick(self.start_tick))
        object.__setattr__(self, "end_tick", _tick(self.end_tick))
        if self.end_tick < self.start_tick:
            _fail()
        object.__setattr__(self, "owner_count", _count(self.owner_count))
        object.__setattr__(self, "candidate_count", _count(self.candidate_count))


@dataclass(frozen=True, slots=True)
class FormalRuleLineageEdgeRecord:
    edge_id: str
    source_candidate_id: str
    target_candidate_id: str
    kind: str
    tick: int
    jaccard: float
    containment: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", require_formal_rule_edge_id(self.edge_id))
        object.__setattr__(
            self,
            "source_candidate_id",
            require_formal_rule_candidate_id(self.source_candidate_id),
        )
        object.__setattr__(
            self,
            "target_candidate_id",
            require_formal_rule_candidate_id(self.target_candidate_id),
        )
        object.__setattr__(self, "kind", _require_enum(self.kind, _LINEAGE_KINDS))
        object.__setattr__(self, "tick", _tick(self.tick))
        object.__setattr__(self, "jaccard", _unit(self.jaccard))
        object.__setattr__(self, "containment", _unit(self.containment))


@dataclass(frozen=True, slots=True)
class FormalRuleCounts:
    candidates: int = 0
    rules: int = 0
    versions: int = 0
    objective_rows: int = 0
    windows: int = 0

    def __post_init__(self) -> None:
        for name in ("candidates", "rules", "versions", "objective_rows", "windows"):
            object.__setattr__(self, name, _count(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class FormalRuleSnapshot:
    ref: FormalRuleSnapshotRef
    candidates: tuple[FormalRuleCandidateRecord, ...] = ()
    rules: tuple[FormalRuleRecord, ...] = ()
    versions: tuple[FormalRuleVersionRecord, ...] = ()
    lineage: tuple[FormalRuleLineageEdgeRecord, ...] = ()
    objective_rows: tuple[FormalRuleObjectiveRow, ...] = ()
    windows: tuple[FormalRuleWindowRecord, ...] = ()
    coverage: FormalRuleCoverage = FormalRuleCoverage(0, 0)
    counts: FormalRuleCounts = FormalRuleCounts()
    provenance_code: str = "empty"
    schema_version: str = FORMAL_RULE_SNAPSHOT_SCHEMA
    policy_version: str = FORMAL_RULE_SNAPSHOT_POLICY_VERSION

    def __post_init__(self) -> None:
        if type(self.ref) is not FormalRuleSnapshotRef:
            _fail()
        if self.schema_version != FORMAL_RULE_SNAPSHOT_SCHEMA:
            _fail()
        if self.policy_version != FORMAL_RULE_SNAPSHOT_POLICY_VERSION:
            _fail()
        object.__setattr__(
            self,
            "candidates",
            tuple(sorted(self.candidates, key=lambda item: item.candidate_id)),
        )
        object.__setattr__(
            self, "rules", tuple(sorted(self.rules, key=lambda item: item.rule_id))
        )
        object.__setattr__(
            self,
            "versions",
            tuple(
                sorted(
                    self.versions,
                    key=lambda item: (item.rule_id, item.version_number),
                )
            ),
        )
        object.__setattr__(
            self,
            "lineage",
            tuple(sorted(self.lineage, key=lambda item: item.edge_id)),
        )
        object.__setattr__(
            self,
            "objective_rows",
            tuple(sorted(self.objective_rows, key=lambda item: item.tick)),
        )
        object.__setattr__(
            self,
            "windows",
            tuple(sorted(self.windows, key=lambda item: item.start_tick)),
        )
        if type(self.coverage) is not FormalRuleCoverage:
            _fail()
        if type(self.counts) is not FormalRuleCounts:
            _fail()
        object.__setattr__(
            self,
            "provenance_code",
            _require_enum(self.provenance_code, _PROVENANCE_CODES),
        )
        for name, cap in (
            ("candidates", MAX_FORMAL_RULE_CANDIDATES),
            ("rules", MAX_FORMAL_RULE_RULES),
            ("versions", MAX_FORMAL_RULE_VERSIONS),
            ("objective_rows", MAX_FORMAL_RULE_OBJECTIVE_ROWS),
            ("windows", MAX_FORMAL_RULE_WINDOWS),
        ):
            values = getattr(self, name)
            if len(values) > cap:
                raise FormalRuleArtifactError("formal_rule_size_limit")
        candidate_ids = {item.candidate_id for item in self.candidates}
        rule_ids = {item.rule_id for item in self.rules}
        if len(candidate_ids) != len(self.candidates):
            _fail()
        if len(rule_ids) != len(self.rules):
            _fail()
        for candidate in self.candidates:
            for other in candidate.competing_candidate_ids:
                if other not in candidate_ids:
                    _fail()
                target = next(
                    item for item in self.candidates if item.candidate_id == other
                )
                if candidate.candidate_id not in target.competing_candidate_ids:
                    _fail()
        per_candidate: dict[str, int] = {}
        for rule in self.rules:
            if rule.candidate_id not in candidate_ids:
                _fail()
            per_candidate[rule.candidate_id] = (
                per_candidate.get(rule.candidate_id, 0) + 1
            )
        if any(
            count > MAX_FORMAL_RULE_RULES_PER_CANDIDATE
            for count in per_candidate.values()
        ):
            raise FormalRuleArtifactError("formal_rule_size_limit")
        per_rule: dict[str, int] = {}
        for version in self.versions:
            if version.rule_id not in rule_ids:
                _fail()
            per_rule[version.rule_id] = per_rule.get(version.rule_id, 0) + 1
        if any(
            count > MAX_FORMAL_RULE_VERSIONS_PER_RULE for count in per_rule.values()
        ):
            raise FormalRuleArtifactError("formal_rule_size_limit")
        for edge in self.lineage:
            if (
                edge.source_candidate_id not in candidate_ids
                or edge.target_candidate_id not in candidate_ids
            ):
                _fail()
        _ensure_acyclic(self.lineage)
        expected_counts = FormalRuleCounts(
            candidates=len(self.candidates),
            rules=len(self.rules),
            versions=len(self.versions),
            objective_rows=len(self.objective_rows),
            windows=len(self.windows),
        )
        if self.counts != expected_counts:
            _fail()
        _reject_published_owner_ids(self)


def _ensure_acyclic(lineage: tuple[FormalRuleLineageEdgeRecord, ...]) -> None:
    edges: dict[str, set[str]] = {}
    for edge in lineage:
        edges.setdefault(edge.source_candidate_id, set()).add(edge.target_candidate_id)
    visiting: set[str] = set()
    settled: set[str] = set()

    def visit(node: str) -> None:
        if node in settled:
            return
        if node in visiting:
            _fail()
        visiting.add(node)
        for target in sorted(edges.get(node, ())):
            visit(target)
        visiting.discard(node)
        settled.add(node)

    for node in sorted(edges):
        visit(node)


def _reject_published_owner_ids(snapshot: FormalRuleSnapshot) -> None:
    ids = [
        *(item.candidate_id for item in snapshot.candidates),
        *(item.rule_id for item in snapshot.rules),
        *(item.version_id for item in snapshot.versions),
        *(item.edge_id for item in snapshot.lineage),
        *(item.source_candidate_id for item in snapshot.lineage),
        *(item.target_candidate_id for item in snapshot.lineage),
        snapshot.ref.run_id,
        snapshot.ref.input_revision,
        snapshot.ref.publication_id,
    ]
    for token in ids:
        _reject_foreign_ids(token)


def empty_formal_rule_snapshot(
    ref: FormalRuleSnapshotRef, *, coverage: FormalRuleCoverage
) -> FormalRuleSnapshot:
    """Return one empty but valid canonical snapshot."""

    if type(ref) is not FormalRuleSnapshotRef:
        raise TypeError("ref must be FormalRuleSnapshotRef")
    if type(coverage) is not FormalRuleCoverage:
        raise TypeError("coverage must be FormalRuleCoverage")
    return FormalRuleSnapshot(
        ref=ref,
        coverage=coverage,
        counts=FormalRuleCounts(),
        provenance_code="empty",
    )


__all__ = [
    "FORMAL_RULE_ARTIFACT_ERROR_CODES",
    "FORMAL_RULE_CANDIDATE_ID_PREFIX",
    "FORMAL_RULE_EDGE_ID_PREFIX",
    "FORMAL_RULE_PUBLICATION_ID_PREFIX",
    "FORMAL_RULE_PUBLISHED_RULE_ID_PREFIX",
    "FORMAL_RULE_PUBLISHED_VERSION_ID_PREFIX",
    "FORMAL_RULE_SNAPSHOT_ID_HEX_LEN",
    "FORMAL_RULE_SNAPSHOT_POLICY_VERSION",
    "FORMAL_RULE_SNAPSHOT_SCHEMA",
    "MAX_FORMAL_RULE_CANDIDATES",
    "MAX_FORMAL_RULE_OBJECTIVE_ROWS",
    "MAX_FORMAL_RULE_RULES",
    "MAX_FORMAL_RULE_RULES_PER_CANDIDATE",
    "MAX_FORMAL_RULE_SNAPSHOT_BYTES",
    "MAX_FORMAL_RULE_VERSIONS",
    "MAX_FORMAL_RULE_VERSIONS_PER_RULE",
    "MAX_FORMAL_RULE_WINDOWS",
    "MAX_PAGE_ROWS",
    "MAX_RESPONSE_BYTES",
    "SUPPORTED_FORMAL_RULE_SNAPSHOT_SCHEMAS",
    "FormalRuleArtifactError",
    "FormalRuleCandidateRecord",
    "FormalRuleCounts",
    "FormalRuleCoverage",
    "FormalRuleLineageEdgeRecord",
    "FormalRuleObjectiveRow",
    "FormalRuleRecord",
    "FormalRuleSnapshot",
    "FormalRuleSnapshotRef",
    "FormalRuleVersionRecord",
    "FormalRuleWindowRecord",
    "FormalRuleWrittenRepresentationRecord",
    "derive_formal_rule_rule_id",
    "derive_formal_rule_version_id",
    "empty_formal_rule_snapshot",
    "require_formal_rule_candidate_id",
    "require_formal_rule_edge_id",
    "require_formal_rule_publication_id",
    "require_formal_rule_rule_id",
    "require_formal_rule_version_id",
    "require_snapshot_digest",
]
