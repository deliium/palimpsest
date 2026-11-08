"""Bounded canonical ``migration-displacement-snapshot-v1`` document.

The snapshot is a publication document only. It mirrors already-derived rows and
never imports analysis, reconstructs classifications, or invents causes. Tokens
are opaque; no raw agent, entity, frame, or evidence body is retained.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Final

__all__ = [
    "MIGRATION_DISPLACEMENT_FORBIDDEN_FIELD_NAMES",
    "MIGRATION_DISPLACEMENT_MAX_ALIGNMENT",
    "MIGRATION_DISPLACEMENT_MAX_BYTES",
    "MIGRATION_DISPLACEMENT_MAX_CANDIDATES",
    "MIGRATION_DISPLACEMENT_MAX_CAUSES",
    "MIGRATION_DISPLACEMENT_MAX_CLUSTERS",
    "MIGRATION_DISPLACEMENT_MAX_LINEAGE",
    "MIGRATION_DISPLACEMENT_MAX_METRIC_PROVENANCE",
    "MIGRATION_DISPLACEMENT_MAX_MOVEMENTS",
    "MIGRATION_DISPLACEMENT_MAX_OUTCOMES",
    "MIGRATION_DISPLACEMENT_MAX_ROUTES",
    "MIGRATION_DISPLACEMENT_MAX_WAVES",
    "MIGRATION_DISPLACEMENT_PUBLICATION_PREFIX",
    "MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY",
    "MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION",
    "MigrationAlignmentSnapshotRow",
    "MigrationCauseSnapshotRow",
    "MigrationClusterSnapshotRow",
    "MigrationDisplacementCandidateRow",
    "MigrationDisplacementSnapshot",
    "MigrationDisplacementSummaryRow",
    "MigrationLineageSnapshotRow",
    "MigrationMetricProvenanceRow",
    "MigrationMovementRow",
    "MigrationOutcomeSnapshotRow",
    "MigrationRouteSnapshotRow",
    "MigrationWaveSnapshotRow",
    "empty_migration_displacement_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.migration_displacement.models"
)

MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION: Final[str] = (
    "migration-displacement-snapshot-v1"
)
MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY: Final[str] = (
    "migration-displacement-analysis.v1"
)
MIGRATION_DISPLACEMENT_PUBLICATION_PREFIX: Final[str] = "md-pub-"
MIGRATION_DISPLACEMENT_MAX_BYTES: Final[int] = 4 * 1024 * 1024
MIGRATION_DISPLACEMENT_MAX_CANDIDATES: Final[int] = 2048
MIGRATION_DISPLACEMENT_MAX_MOVEMENTS: Final[int] = 4096
MIGRATION_DISPLACEMENT_MAX_CAUSES: Final[int] = 4096
MIGRATION_DISPLACEMENT_MAX_ROUTES: Final[int] = 4096
MIGRATION_DISPLACEMENT_MAX_CLUSTERS: Final[int] = 2048
MIGRATION_DISPLACEMENT_MAX_WAVES: Final[int] = 2048
MIGRATION_DISPLACEMENT_MAX_OUTCOMES: Final[int] = 2048
MIGRATION_DISPLACEMENT_MAX_LINEAGE: Final[int] = 4096
MIGRATION_DISPLACEMENT_MAX_ALIGNMENT: Final[int] = 4096
MIGRATION_DISPLACEMENT_MAX_METRIC_PROVENANCE: Final[int] = 64

MIGRATION_DISPLACEMENT_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "refugee",
        "asylum",
        "forced",
        "displaced",
        "threat",
        "hardship",
        "wellbeing",
        "assimilation",
        "integration_score",
        "score",
        "composite",
        "raw_owner_id",
        "raw_entity_id",
        "raw_agent_id",
        "frame_body",
        "evidence_body",
        "cause_text",
    }
)

_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_HEX64: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_NONE_TOKEN: Final[str] = "none"

_COVERAGES: Final[frozenset[str]] = frozenset(
    {"complete", "partial", "missing", "not_applicable", "observed"}
)
_CANDIDATE_KINDS: Final[frozenset[str]] = frozenset({"wave", "cluster", "outcome"})
_CANDIDATE_STATUSES: Final[frozenset[str]] = frozenset({"observed", "partial"})
_DISPLACEMENT_CLASSES: Final[frozenset[str]] = frozenset(
    {"not_displacement_like", "displacement_like", "mixed", "unknown"}
)
_INTEGRATION_CLASSES: Final[frozenset[str]] = frozenset(
    {"settled", "transient", "returned", "onward", "unknown"}
)
_CAUSE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "resource_scarcity",
        "environmental_hazard",
        "conflict",
        "opportunity",
        "social_network",
        "institution",
        "unknown",
    }
)
_CAUSE_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "direct_observation",
        "own_need",
        "own_journey",
        "own_relationship",
        "own_kinship",
        "organization_belief",
        "institution_belief",
        "formal_rule_belief",
        "dispute_belief",
        "evidence_belief",
        "diplomacy_belief",
        "conflict_belief",
        "border_belief",
        "testimony",
        "inference",
        "unknown",
    }
)
_CAUSE_STATUSES: Final[frozenset[str]] = frozenset(
    {"active", "superseded", "contradicted", "expired", "unknown"}
)
_ROUTE_BASES: Final[frozenset[str]] = frozenset(
    {
        "direct_observation",
        "own_journey",
        "testimony",
        "inference",
        "unresolved",
        "unknown",
    }
)
_ROUTE_STATUSES: Final[frozenset[str]] = frozenset(
    {"open", "blocked_belief", "unresolved", "expired", "unknown"}
)
_CLUSTER_BASES: Final[frozenset[str]] = frozenset(
    {"kinship", "organization", "co_movement", "communication", "relationship"}
)
_RELOCATION_KINDS: Final[frozenset[str]] = frozenset(
    {"move", "transport", "flee", "journey"}
)
_ARRIVAL_STATUSES: Final[frozenset[str]] = frozenset(
    {"arrived", "timeout", "dead", "pending", "unknown"}
)
_LINEAGE_RELATIONS: Final[frozenset[str]] = frozenset(
    {"continued", "transformed", "split", "merge", "dissolved", "emerged"}
)
_ALIGNMENTS: Final[frozenset[str]] = frozenset(
    {"consistent", "unresolved", "inconsistent", "not_applicable"}
)
_MOVEMENT_COVERAGES: Final[frozenset[str]] = frozenset(
    {"complete", "partial", "missing"}
)


def _reject(code: str) -> None:
    raise ValueError(f"migration_displacement_snapshot: {code}")


def _token(name: str, value: object) -> str:
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        _reject(f"invalid_token:{name}")
    return value  # type: ignore[return-value]


def _optional_token(name: str, value: object) -> str:
    if value == "":
        return ""
    return _token(name, value)


def _tokens(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        _reject(f"invalid_type:{name}")
    return tuple(_token(name, item) for item in values)


def _pairs(name: str, values: object, *, labels: frozenset[str] | None = None) -> (
    tuple[tuple[str, int], ...]
):
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        _reject(f"invalid_type:{name}")
    out: list[tuple[str, int]] = []
    for item in values:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            _reject(f"invalid_pair:{name}")
        label, number = item
        if type(label) is not str or not label:
            _reject(f"invalid_pair:{name}")
        if labels is not None and label not in labels:
            _reject(f"unknown_label:{name}")
        if type(number) is not int or number < 0:
            _reject(f"invalid_count:{name}")
        out.append((label, number))
    if out != sorted(out):
        _reject(f"unsorted:{name}")
    return tuple(out)


def _nonneg(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        _reject(f"invalid_count:{name}")
    return value


def _unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _reject(f"not_finite:{name}")
    number = float(value)
    if number < 0.0 or number > 1.0:
        _reject(f"out_of_range:{name}")
    return round(number, 6)


def _nonneg_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _reject(f"not_finite:{name}")
    number = float(value)
    if number < 0.0:
        _reject(f"out_of_range:{name}")
    return round(number, 6)


def _closed(name: str, value: object, allowed: frozenset[str]) -> str:
    if type(value) is not str or value not in allowed:
        _reject(f"unknown_label:{name}")
    return value


def _ordered_ticks(first_name: str, first: object, last_name: str, last: object) -> (
    tuple[int, int]
):
    start = _nonneg(first_name, first)
    end = _nonneg(last_name, last)
    if end < start:
        _reject(f"tick_order:{last_name}")
    return start, end


def _forbid_field_names(row_type: type) -> None:
    for item in fields(row_type):
        if item.name in MIGRATION_DISPLACEMENT_FORBIDDEN_FIELD_NAMES:
            _reject(f"forbidden_field:{item.name}")


@dataclass(frozen=True, slots=True)
class MigrationDisplacementSummaryRow:
    """Required summary row. Counts must match snapshot families."""

    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    policy_version: str
    candidate_count: int = 0
    wave_count: int = 0
    cluster_count: int = 0
    outcome_count: int = 0
    movement_count: int = 0
    cause_count: int = 0
    displacement_like_count: int = 0
    mixed_count: int = 0
    not_displacement_like_count: int = 0
    unknown_count: int = 0
    integration_settled_count: int = 0
    integration_transient_count: int = 0
    integration_returned_count: int = 0
    integration_onward_count: int = 0
    integration_unknown_count: int = 0
    coverage: str = "not_applicable"
    unresolved_anchor_count: int = 0
    truncated: bool = False

    def __post_init__(self) -> None:
        _forbid_field_names(type(self))
        _token("run_id", self.run_id)
        if self.publication_id:
            _token("publication_id", self.publication_id)
        if self.digest and _HEX64.match(self.digest) is None:
            _reject("invalid_digest")
        if self.schema_version != MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION:
            _reject("unsupported_schema")
        if self.policy_version != MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY:
            _reject("unsupported_policy")
        for name in (
            "candidate_count",
            "wave_count",
            "cluster_count",
            "outcome_count",
            "movement_count",
            "cause_count",
            "displacement_like_count",
            "mixed_count",
            "not_displacement_like_count",
            "unknown_count",
            "integration_settled_count",
            "integration_transient_count",
            "integration_returned_count",
            "integration_onward_count",
            "integration_unknown_count",
            "unresolved_anchor_count",
        ):
            object.__setattr__(self, name, _nonneg(name, getattr(self, name)))
        _closed("coverage", self.coverage, _COVERAGES)
        if type(self.truncated) is not bool:
            _reject("invalid_truncated")


@dataclass(frozen=True, slots=True)
class MigrationDisplacementCandidateRow:
    """Content-addressed ``mig-`` candidate summary for lineage and alignment."""

    candidate_token: str
    kind: str
    status: str
    first_tick: int
    last_tick: int
    member_count: int
    origin_token: str
    destination_token: str
    classification: str
    coverage: str

    def __post_init__(self) -> None:
        _forbid_field_names(type(self))
        token = _token("candidate_token", self.candidate_token)
        if not token.startswith("mig-"):
            _reject("invalid_candidate_token")
        _closed("kind", self.kind, _CANDIDATE_KINDS)
        _closed("status", self.status, _CANDIDATE_STATUSES)
        first, last = _ordered_ticks(
            "first_tick", self.first_tick, "last_tick", self.last_tick
        )
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(
            self, "member_count", _nonneg("member_count", self.member_count)
        )
        _token("origin_token", self.origin_token)
        _token("destination_token", self.destination_token)
        if self.kind == "wave":
            _closed("classification", self.classification, _DISPLACEMENT_CLASSES)
        elif self.kind == "outcome":
            _closed("classification", self.classification, _INTEGRATION_CLASSES)
        elif self.classification != "unknown":
            _reject("unknown_label:classification")
        _closed("coverage", self.coverage, _MOVEMENT_COVERAGES)


@dataclass(frozen=True, slots=True)
class MigrationMovementRow:
    """Objective participant movement. No cause or classification."""

    participant_token: str
    origin_token: str
    destination_token: str
    route_tokens: tuple[str, ...]
    start_tick: int
    end_tick: int
    relocation_kind: str
    group_size: int
    arrival_status: str
    coverage: str

    def __post_init__(self) -> None:
        _forbid_field_names(type(self))
        _token("participant_token", self.participant_token)
        _token("origin_token", self.origin_token)
        _token("destination_token", self.destination_token)
        object.__setattr__(
            self, "route_tokens", _tokens("route_tokens", self.route_tokens)
        )
        start, end = _ordered_ticks(
            "start_tick", self.start_tick, "end_tick", self.end_tick
        )
        object.__setattr__(self, "start_tick", start)
        object.__setattr__(self, "end_tick", end)
        _closed("relocation_kind", self.relocation_kind, _RELOCATION_KINDS)
        if type(self.group_size) is not int or self.group_size < 1 or self.group_size > 8:
            _reject("invalid_group_size")
        _closed("arrival_status", self.arrival_status, _ARRIVAL_STATUSES)
        _closed("coverage", self.coverage, _MOVEMENT_COVERAGES)


@dataclass(frozen=True, slots=True)
class MigrationCauseSnapshotRow:
    """Subjective owner cause belief. Never an objective cause."""

    owner_token: str
    cause_token: str
    cause_kind: str
    source_kind: str
    anchor_token: str
    confidence: float
    tick: int
    status: str

    def __post_init__(self) -> None:
        _forbid_field_names(type(self))
        _token("owner_token", self.owner_token)
        _token("cause_token", self.cause_token)
        _closed("cause_kind", self.cause_kind, _CAUSE_KINDS)
        _closed("source_kind", self.source_kind, _CAUSE_SOURCES)
        object.__setattr__(
            self, "anchor_token", _optional_token("anchor_token", self.anchor_token)
        )
        object.__setattr__(self, "confidence", _unit("confidence", self.confidence))
        object.__setattr__(self, "tick", _nonneg("tick", self.tick))
        _closed("status", self.status, _CAUSE_STATUSES)


@dataclass(frozen=True, slots=True)
class MigrationRouteSnapshotRow:
    """Subjective owner route belief about an ordered logical path."""

    owner_token: str
    route_token: str
    origin_token: str
    destination_token: str
    route_tokens: tuple[str, ...]
    observed_duration_ticks: int
    fatigue_cost: float
    basis: str
    status: str
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _forbid_field_names(type(self))
        _token("owner_token", self.owner_token)
        _token("route_token", self.route_token)
        _token("origin_token", self.origin_token)
        _token("destination_token", self.destination_token)
        object.__setattr__(
            self, "route_tokens", _tokens("route_tokens", self.route_tokens)
        )
        object.__setattr__(
            self,
            "observed_duration_ticks",
            _nonneg("observed_duration_ticks", self.observed_duration_ticks),
        )
        object.__setattr__(
            self, "fatigue_cost", _nonneg_float("fatigue_cost", self.fatigue_cost)
        )
        _closed("basis", self.basis, _ROUTE_BASES)
        _closed("status", self.status, _ROUTE_STATUSES)
        first, last = _ordered_ticks(
            "first_tick", self.first_tick, "last_tick", self.last_tick
        )
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class MigrationClusterSnapshotRow:
    """Analytical social-cluster candidate. Not a household registry."""

    cluster_token: str
    member_tokens: tuple[str, ...]
    basis_counts: tuple[tuple[str, int], ...]
    coverage: str
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _forbid_field_names(type(self))
        _token("cluster_token", self.cluster_token)
        object.__setattr__(
            self, "member_tokens", _tokens("member_tokens", self.member_tokens)
        )
        object.__setattr__(
            self,
            "basis_counts",
            _pairs("basis_counts", self.basis_counts, labels=_CLUSTER_BASES),
        )
        _closed("coverage", self.coverage, _MOVEMENT_COVERAGES)
        first, last = _ordered_ticks(
            "first_tick", self.first_tick, "last_tick", self.last_tick
        )
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class MigrationWaveSnapshotRow:
    """Analytical wave with a researcher-only displacement classification."""

    wave_token: str
    origin_token: str
    destination_token: str
    participant_tokens: tuple[str, ...]
    route_tokens: tuple[str, ...]
    start_tick: int
    end_tick: int
    cause_support_counts: tuple[tuple[str, int], ...]
    displacement_classification: str
    displacement_bases: tuple[str, ...]
    independent_cause_count: int
    cluster_tokens: tuple[str, ...]
    coverage: str

    def __post_init__(self) -> None:
        _forbid_field_names(type(self))
        _token("wave_token", self.wave_token)
        _token("origin_token", self.origin_token)
        _token("destination_token", self.destination_token)
        object.__setattr__(
            self,
            "participant_tokens",
            _tokens("participant_tokens", self.participant_tokens),
        )
        object.__setattr__(
            self, "route_tokens", _tokens("route_tokens", self.route_tokens)
        )
        start, end = _ordered_ticks(
            "start_tick", self.start_tick, "end_tick", self.end_tick
        )
        object.__setattr__(self, "start_tick", start)
        object.__setattr__(self, "end_tick", end)
        object.__setattr__(
            self,
            "cause_support_counts",
            _pairs(
                "cause_support_counts",
                self.cause_support_counts,
                labels=_CAUSE_KINDS,
            ),
        )
        _closed(
            "displacement_classification",
            self.displacement_classification,
            _DISPLACEMENT_CLASSES,
        )
        if isinstance(self.displacement_bases, (str, bytes, set, frozenset)) or (
            not isinstance(self.displacement_bases, Sequence)
        ):
            _reject("invalid_type:displacement_bases")
        bases = tuple(str(item) for item in self.displacement_bases)
        if bases != tuple(sorted(bases)):
            _reject("unsorted:displacement_bases")
        object.__setattr__(self, "displacement_bases", bases)
        object.__setattr__(
            self,
            "independent_cause_count",
            _nonneg("independent_cause_count", self.independent_cause_count),
        )
        object.__setattr__(
            self, "cluster_tokens", _tokens("cluster_tokens", self.cluster_tokens)
        )
        _closed("coverage", self.coverage, _MOVEMENT_COVERAGES)


@dataclass(frozen=True, slots=True)
class MigrationOutcomeSnapshotRow:
    """Descriptive integration outcome with counts only. Never a score."""

    outcome_token: str
    participant_token: str
    destination_token: str
    residence_ticks: int
    access_evidence_count: int
    participation_evidence_count: int
    relationship_evidence_count: int
    conflict_evidence_count: int
    classification: str
    coverage: str
    censored: bool

    def __post_init__(self) -> None:
        _forbid_field_names(type(self))
        _token("outcome_token", self.outcome_token)
        _token("participant_token", self.participant_token)
        _token("destination_token", self.destination_token)
        for name in (
            "residence_ticks",
            "access_evidence_count",
            "participation_evidence_count",
            "relationship_evidence_count",
            "conflict_evidence_count",
        ):
            object.__setattr__(self, name, _nonneg(name, getattr(self, name)))
        _closed("classification", self.classification, _INTEGRATION_CLASSES)
        _closed("coverage", self.coverage, _MOVEMENT_COVERAGES)
        if type(self.censored) is not bool:
            _reject("invalid_censored")


@dataclass(frozen=True, slots=True)
class MigrationLineageSnapshotRow:
    """Forward-only lineage edge between analytical candidates."""

    candidate_token: str
    previous_token: str
    relation: str
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _forbid_field_names(type(self))
        _token("candidate_token", self.candidate_token)
        _token("previous_token", self.previous_token)
        _closed("relation", self.relation, _LINEAGE_RELATIONS)
        first, last = _ordered_ticks(
            "first_tick", self.first_tick, "last_tick", self.last_tick
        )
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)


@dataclass(frozen=True, slots=True)
class MigrationAlignmentSnapshotRow:
    """Researcher-only owner-versus-analysis alignment."""

    owner_token: str
    candidate_token: str
    alignment: str
    basis: str

    def __post_init__(self) -> None:
        _forbid_field_names(type(self))
        _token("owner_token", self.owner_token)
        _token("candidate_token", self.candidate_token)
        _closed("alignment", self.alignment, _ALIGNMENTS)
        _token("basis", self.basis)


_FAMILY_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


@dataclass(frozen=True, slots=True)
class MigrationMetricProvenanceRow:
    """Metric family digest provenance retained with the publication."""

    family: str
    version: str
    document_digest: str
    coverage: str

    def __post_init__(self) -> None:
        _forbid_field_names(type(self))
        if type(self.family) is not str or _FAMILY_RE.fullmatch(self.family) is None:
            _reject("invalid_token:family")
        _token("version", self.version)
        if self.document_digest and _HEX64.match(self.document_digest) is None:
            _reject("invalid_document_digest")
        _closed("coverage", self.coverage, _COVERAGES)


@dataclass(frozen=True, slots=True)
class MigrationDisplacementSnapshot:
    """Immutable bounded publication document for migration displacement."""

    summary: MigrationDisplacementSummaryRow
    candidates: tuple[MigrationDisplacementCandidateRow, ...] = ()
    movements: tuple[MigrationMovementRow, ...] = ()
    causes: tuple[MigrationCauseSnapshotRow, ...] = ()
    routes: tuple[MigrationRouteSnapshotRow, ...] = ()
    clusters: tuple[MigrationClusterSnapshotRow, ...] = ()
    waves: tuple[MigrationWaveSnapshotRow, ...] = ()
    outcomes: tuple[MigrationOutcomeSnapshotRow, ...] = ()
    lineage: tuple[MigrationLineageSnapshotRow, ...] = ()
    alignment: tuple[MigrationAlignmentSnapshotRow, ...] = ()
    metric_provenance: tuple[MigrationMetricProvenanceRow, ...] = ()
    digest: str = ""
    publication_id: str = ""
    schema_version: str = MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION
    policy_version: str = MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY

    def __post_init__(self) -> None:
        _forbid_field_names(type(self))
        for row_type in (
            MigrationDisplacementSummaryRow,
            MigrationDisplacementCandidateRow,
            MigrationMovementRow,
            MigrationCauseSnapshotRow,
            MigrationRouteSnapshotRow,
            MigrationClusterSnapshotRow,
            MigrationWaveSnapshotRow,
            MigrationOutcomeSnapshotRow,
            MigrationLineageSnapshotRow,
            MigrationAlignmentSnapshotRow,
            MigrationMetricProvenanceRow,
        ):
            _forbid_field_names(row_type)
        if type(self.summary) is not MigrationDisplacementSummaryRow:
            raise TypeError("summary must be MigrationDisplacementSummaryRow")
        if self.schema_version != MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION:
            _reject("unsupported_schema")
        if self.policy_version != MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY:
            _reject("unsupported_policy")
        if self.digest and _HEX64.match(self.digest) is None:
            _reject("invalid_digest")
        if self.publication_id:
            _token("publication_id", self.publication_id)
        caps: tuple[tuple[str, tuple[object, ...], int], ...] = (
            ("candidates", self.candidates, MIGRATION_DISPLACEMENT_MAX_CANDIDATES),
            ("movements", self.movements, MIGRATION_DISPLACEMENT_MAX_MOVEMENTS),
            ("causes", self.causes, MIGRATION_DISPLACEMENT_MAX_CAUSES),
            ("routes", self.routes, MIGRATION_DISPLACEMENT_MAX_ROUTES),
            ("clusters", self.clusters, MIGRATION_DISPLACEMENT_MAX_CLUSTERS),
            ("waves", self.waves, MIGRATION_DISPLACEMENT_MAX_WAVES),
            ("outcomes", self.outcomes, MIGRATION_DISPLACEMENT_MAX_OUTCOMES),
            ("lineage", self.lineage, MIGRATION_DISPLACEMENT_MAX_LINEAGE),
            ("alignment", self.alignment, MIGRATION_DISPLACEMENT_MAX_ALIGNMENT),
            (
                "metric_provenance",
                self.metric_provenance,
                MIGRATION_DISPLACEMENT_MAX_METRIC_PROVENANCE,
            ),
        )
        for name, rows, limit in caps:
            if not isinstance(rows, tuple):
                _reject(f"invalid_type:{name}")
            if len(rows) > limit:
                _reject(f"cap:{name}")
        candidate_keys = [row.candidate_token for row in self.candidates]
        movement_keys = [
            (
                row.start_tick,
                row.participant_token,
                row.origin_token,
                row.destination_token,
            )
            for row in self.movements
        ]
        cause_keys = [
            (row.owner_token, row.tick, row.cause_token) for row in self.causes
        ]
        route_keys = [
            (row.owner_token, row.first_tick, row.route_token) for row in self.routes
        ]
        cluster_keys = [row.cluster_token for row in self.clusters]
        wave_keys = [(row.start_tick, row.wave_token) for row in self.waves]
        outcome_keys = [
            (row.participant_token, row.destination_token, row.outcome_token)
            for row in self.outcomes
        ]
        lineage_keys = [
            (row.first_tick, row.candidate_token, row.previous_token, row.relation)
            for row in self.lineage
        ]
        alignment_keys = [
            (row.owner_token, row.candidate_token) for row in self.alignment
        ]
        provenance_keys = [row.family for row in self.metric_provenance]
        ordered = (
            ("candidates", candidate_keys),
            ("movements", movement_keys),
            ("causes", cause_keys),
            ("routes", route_keys),
            ("clusters", cluster_keys),
            ("waves", wave_keys),
            ("outcomes", outcome_keys),
            ("lineage", lineage_keys),
            ("alignment", alignment_keys),
            ("metric_provenance", provenance_keys),
        )
        for name, keys in ordered:
            if keys != sorted(keys):
                _reject(f"order:{name}")
            if len(set(keys)) != len(keys):
                _reject(f"duplicate:{name}")
        candidate_tokens = set(candidate_keys)
        for row in self.alignment:
            if row.candidate_token not in candidate_tokens:
                _reject("unresolved_candidate")
        for row in self.lineage:
            if (
                row.candidate_token != _NONE_TOKEN
                and row.candidate_token not in candidate_tokens
            ):
                _reject("unresolved_candidate")
            if (
                row.previous_token != _NONE_TOKEN
                and row.previous_token not in candidate_tokens
            ):
                _reject("unresolved_candidate")
        summary = self.summary
        displacement_counts = {
            "displacement_like": 0,
            "mixed": 0,
            "not_displacement_like": 0,
            "unknown": 0,
        }
        for row in self.waves:
            displacement_counts[row.displacement_classification] += 1
        integration_counts = {
            "settled": 0,
            "transient": 0,
            "returned": 0,
            "onward": 0,
            "unknown": 0,
        }
        for row in self.outcomes:
            integration_counts[row.classification] += 1
        if (
            summary.candidate_count != len(self.candidates)
            or summary.wave_count != len(self.waves)
            or summary.cluster_count != len(self.clusters)
            or summary.outcome_count != len(self.outcomes)
            or summary.movement_count != len(self.movements)
            or summary.cause_count != len(self.causes)
            or summary.displacement_like_count != displacement_counts["displacement_like"]
            or summary.mixed_count != displacement_counts["mixed"]
            or summary.not_displacement_like_count
            != displacement_counts["not_displacement_like"]
            or summary.unknown_count != displacement_counts["unknown"]
            or summary.integration_settled_count != integration_counts["settled"]
            or summary.integration_transient_count != integration_counts["transient"]
            or summary.integration_returned_count != integration_counts["returned"]
            or summary.integration_onward_count != integration_counts["onward"]
            or summary.integration_unknown_count != integration_counts["unknown"]
        ):
            _reject("summary_counts")
        if (
            summary.schema_version != self.schema_version
            or summary.policy_version != self.policy_version
        ):
            _reject("summary_identity")
        if self.digest and summary.digest and summary.digest != self.digest:
            _reject("summary_identity")
        if (
            self.publication_id
            and summary.publication_id
            and summary.publication_id != self.publication_id
        ):
            _reject("summary_identity")


def empty_migration_displacement_snapshot(
    run_id: str,
    *,
    digest: str,
    publication_id: str,
    policy_version: str = MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY,
) -> MigrationDisplacementSnapshot:
    """Build a required-summary-only snapshot for disabled or unavailable runs."""
    summary = MigrationDisplacementSummaryRow(
        run_id=run_id,
        publication_id=publication_id,
        digest=digest,
        schema_version=MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION,
        policy_version=policy_version,
    )
    snapshot = MigrationDisplacementSnapshot(
        summary=summary,
        digest=digest,
        publication_id=publication_id,
        schema_version=MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION,
        policy_version=policy_version,
    )
    _LOG.debug(
        "migration_displacement_snapshot_empty run_present=%s digest_present=%s",
        bool(run_id),
        bool(digest),
    )
    return snapshot
