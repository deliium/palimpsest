# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Bounded canonical ``borders-snapshot-v1`` document."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Final

__all__ = [
    "BORDERS_FORBIDDEN_FIELD_NAMES",
    "BORDERS_MAX_DETAIL_ROWS",
    "BORDERS_MAX_LINEAGE_EDGES",
    "BORDERS_MAX_ROWS_PER_FAMILY",
    "BORDERS_PUBLICATION_PREFIX",
    "BORDERS_SNAPSHOT_MAX_BYTES",
    "BORDERS_SNAPSHOT_POLICY",
    "BORDERS_SNAPSHOT_SCHEMA",
    "BordersAccessRow",
    "BordersAgreementRow",
    "BordersAlignmentRow",
    "BordersCandidateRow",
    "BordersClaimRow",
    "BordersDisputeRow",
    "BordersLineageRow",
    "BordersMetricProvenanceRow",
    "BordersOverlapRow",
    "BordersPatternRow",
    "BordersPhysicalRow",
    "BordersRecognitionRow",
    "BordersSnapshot",
    "BordersSummaryRow",
    "empty_borders_snapshot",
]

BORDERS_SNAPSHOT_SCHEMA: Final[str] = "borders-snapshot-v1"
BORDERS_SNAPSHOT_POLICY: Final[str] = "borders-snapshot.v1"
BORDERS_SNAPSHOT_MAX_BYTES: Final[int] = 4 * 1024 * 1024
BORDERS_MAX_ROWS_PER_FAMILY: Final[int] = 5000
BORDERS_MAX_LINEAGE_EDGES: Final[int] = 32
BORDERS_MAX_DETAIL_ROWS: Final[int] = 500
BORDERS_PUBLICATION_PREFIX: Final[str] = "bd-pub-"

BORDERS_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "country_owner",
        "sovereignty",
        "sovereign",
        "legitimate",
        "legitimacy",
        "winner",
        "loser",
        "score",
        "composite",
        "enforced",
        "enforcement",
        "border_truth",
        "ownership",
        "title",
        "raw_owner_id",
        "raw_entity_id",
        "raw_agent_id",
        "frame_body",
        "evidence_body",
    }
)

_HEX64: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_HEX16: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{16}$")


def _token(name: str, value: object) -> str:
    if type(value) is not str or not value or len(value) > 128:
        raise ValueError(f"{name}: invalid_token")
    return value


def _id_token(name: str, value: object, prefix: str) -> str:
    text = _token(name, value)
    if not text.startswith(prefix):
        raise ValueError(f"{name}: invalid_identifier")
    return text


def _tokens(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise ValueError(f"{name}: invalid_type")
    return tuple(_token(name, item) for item in values)


def _edges(name: str, values: object) -> tuple[tuple[str, str], ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise ValueError(f"{name}: invalid_type")
    pairs: list[tuple[str, str]] = []
    for item in values:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError(f"{name}: invalid_edge")
        pairs.append((_token(name, item[0]), _token(name, item[1])))
    return tuple(pairs)


def _nonneg(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name}: invalid_count")
    return value


def _unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_finite")
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise ValueError(f"{name}: out_of_range")
    return round(number, 6)


@dataclass(frozen=True, slots=True)
class BordersSummaryRow:
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    policy_version: str
    catalog_version: str
    claim_count: int = 0
    agreement_count: int = 0
    dispute_count: int = 0
    physical_row_count: int = 0
    pattern_count: int = 0
    candidate_count: int = 0
    coverage: str = "not_applicable"

    def __post_init__(self) -> None:
        _token("run_id", self.run_id)
        _token("publication_id", self.publication_id)
        if self.digest and _HEX64.match(self.digest) is None:
            raise ValueError("digest: invalid_digest")
        if self.schema_version != BORDERS_SNAPSHOT_SCHEMA:
            raise ValueError("schema_version: unsupported")
        if self.policy_version != BORDERS_SNAPSHOT_POLICY:
            raise ValueError("policy_version: unsupported")
        _token("catalog_version", self.catalog_version)
        for name in (
            "claim_count",
            "agreement_count",
            "dispute_count",
            "physical_row_count",
            "pattern_count",
            "candidate_count",
        ):
            object.__setattr__(self, name, _nonneg(name, getattr(self, name)))
        if self.coverage not in {
            "complete",
            "partial",
            "not_applicable",
            "observed",
        }:
            raise ValueError("coverage: unknown_coverage")


@dataclass(frozen=True, slots=True)
class BordersCandidateRow:
    candidate_token: str
    location_tokens: tuple[str, ...]
    boundary_edge_tokens: tuple[tuple[str, str], ...]
    status: str
    evidence_count: int
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _id_token("candidate_token", self.candidate_token, "bord-")
        object.__setattr__(
            self, "location_tokens", _tokens("location_tokens", self.location_tokens)
        )
        object.__setattr__(
            self,
            "boundary_edge_tokens",
            _edges("boundary_edge_tokens", self.boundary_edge_tokens),
        )
        _token("status", self.status)
        for name in ("evidence_count", "first_tick", "last_tick"):
            object.__setattr__(self, name, _nonneg(name, getattr(self, name)))


@dataclass(frozen=True, slots=True)
class BordersClaimRow:
    claim_token: str
    owner_token: str
    domain_token: str
    location_tokens: tuple[str, ...]
    boundary_edge_tokens: tuple[tuple[str, str], ...]
    status: str
    strength: float
    anchor_token: str = ""

    def __post_init__(self) -> None:
        _token("claim_token", self.claim_token)
        _token("owner_token", self.owner_token)
        _token("domain_token", self.domain_token)
        object.__setattr__(
            self, "location_tokens", _tokens("location_tokens", self.location_tokens)
        )
        object.__setattr__(
            self,
            "boundary_edge_tokens",
            _edges("boundary_edge_tokens", self.boundary_edge_tokens),
        )
        _token("status", self.status)
        object.__setattr__(self, "strength", _unit("strength", self.strength))


@dataclass(frozen=True, slots=True)
class BordersRecognitionRow:
    recognition_token: str
    domain_token: str
    edge_tokens: tuple[tuple[str, str], ...]
    basis: str
    status: str

    def __post_init__(self) -> None:
        _token("recognition_token", self.recognition_token)
        _token("domain_token", self.domain_token)
        object.__setattr__(self, "edge_tokens", _edges("edge_tokens", self.edge_tokens))
        _token("basis", self.basis)
        _token("status", self.status)


@dataclass(frozen=True, slots=True)
class BordersAccessRow:
    access_token: str
    domain_token: str
    subject_token: str
    mode: str
    status: str

    def __post_init__(self) -> None:
        _token("access_token", self.access_token)
        _token("domain_token", self.domain_token)
        _token("mode", self.mode)
        _token("status", self.status)


@dataclass(frozen=True, slots=True)
class BordersAgreementRow:
    agreement_token: str
    domain_token: str
    counterparty_token: str
    provision_tokens: tuple[str, ...]
    status: str
    recognition: str
    effective_tick: int | None = None
    expiry_tick: int | None = None

    def __post_init__(self) -> None:
        _token("agreement_token", self.agreement_token)
        _token("domain_token", self.domain_token)
        object.__setattr__(
            self,
            "provision_tokens",
            _tokens("provision_tokens", self.provision_tokens),
        )
        _token("status", self.status)
        _token("recognition", self.recognition)
        if self.effective_tick is not None:
            object.__setattr__(
                self,
                "effective_tick",
                _nonneg("effective_tick", self.effective_tick),
            )
        if self.expiry_tick is not None:
            object.__setattr__(
                self, "expiry_tick", _nonneg("expiry_tick", self.expiry_tick)
            )


@dataclass(frozen=True, slots=True)
class BordersDisputeRow:
    dispute_token: str
    domain_token: str
    counterparty_token: str
    contested_location_tokens: tuple[str, ...]
    status: str

    def __post_init__(self) -> None:
        _token("dispute_token", self.dispute_token)
        _token("domain_token", self.domain_token)
        object.__setattr__(
            self,
            "contested_location_tokens",
            _tokens("contested_location_tokens", self.contested_location_tokens),
        )
        _token("status", self.status)


@dataclass(frozen=True, slots=True)
class BordersPhysicalRow:
    location_token: str
    window_start: int
    window_end: int
    actor_count: int
    action_count: int
    hostile_count: int
    assistance_count: int
    presence_ticks: int
    classification: str

    def __post_init__(self) -> None:
        _token("location_token", self.location_token)
        for name in (
            "window_start",
            "window_end",
            "actor_count",
            "action_count",
            "hostile_count",
            "assistance_count",
            "presence_ticks",
        ):
            object.__setattr__(self, name, _nonneg(name, getattr(self, name)))
        _token("classification", self.classification)


@dataclass(frozen=True, slots=True)
class BordersPatternRow:
    pattern_token: str
    domain_token: str
    location_tokens: tuple[str, ...]
    pattern: str
    physical_actions: int = 0
    claim_count: int = 0
    agreement_count: int = 0
    dispute_count: int = 0

    def __post_init__(self) -> None:
        _token("pattern_token", self.pattern_token)
        _token("domain_token", self.domain_token)
        object.__setattr__(
            self, "location_tokens", _tokens("location_tokens", self.location_tokens)
        )
        _token("pattern", self.pattern)
        for name in (
            "physical_actions",
            "claim_count",
            "agreement_count",
            "dispute_count",
        ):
            object.__setattr__(self, name, _nonneg(name, getattr(self, name)))


@dataclass(frozen=True, slots=True)
class BordersOverlapRow:
    left_domain_token: str
    right_domain_token: str
    overlap_location_tokens: tuple[str, ...]
    overlap_count: int
    dispute_status: str

    def __post_init__(self) -> None:
        _token("left_domain_token", self.left_domain_token)
        _token("right_domain_token", self.right_domain_token)
        object.__setattr__(
            self,
            "overlap_location_tokens",
            _tokens("overlap_location_tokens", self.overlap_location_tokens),
        )
        object.__setattr__(
            self, "overlap_count", _nonneg("overlap_count", self.overlap_count)
        )
        _token("dispute_status", self.dispute_status)


@dataclass(frozen=True, slots=True)
class BordersLineageRow:
    edge_token: str
    parent_token: str
    child_token: str
    kind: str
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _token("edge_token", self.edge_token)
        _token("parent_token", self.parent_token)
        _token("child_token", self.child_token)
        _token("kind", self.kind)
        object.__setattr__(self, "first_tick", _nonneg("first_tick", self.first_tick))
        object.__setattr__(self, "last_tick", _nonneg("last_tick", self.last_tick))


@dataclass(frozen=True, slots=True)
class BordersAlignmentRow:
    candidate_token: str
    alignment: str
    claim_alignment: str
    agreement_alignment: str
    pattern_alignment: str
    basis_counts: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        _id_token("candidate_token", self.candidate_token, "bord-")
        for name in (
            "alignment",
            "claim_alignment",
            "agreement_alignment",
            "pattern_alignment",
        ):
            _token(name, getattr(self, name))
        counts: list[tuple[str, int]] = []
        for item in self.basis_counts:
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise ValueError("basis_counts: invalid_entry")
            counts.append(
                (_token("basis_counts", item[0]), _nonneg("basis_counts", item[1]))
            )
        object.__setattr__(self, "basis_counts", tuple(sorted(counts)))


@dataclass(frozen=True, slots=True)
class BordersMetricProvenanceRow:
    family: str
    algorithm_version: str
    catalog_version: str
    value_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        _token("family", self.family)
        _token("algorithm_version", self.algorithm_version)
        _token("catalog_version", self.catalog_version)
        object.__setattr__(self, "value_keys", _tokens("value_keys", self.value_keys))


@dataclass(frozen=True, slots=True)
class BordersSnapshot:
    schema_version: str
    policy_version: str
    catalog_version: str
    run_id: str
    publication_id: str
    digest: str
    summary: BordersSummaryRow
    candidates: tuple[BordersCandidateRow, ...] = ()
    claims: tuple[BordersClaimRow, ...] = ()
    recognitions: tuple[BordersRecognitionRow, ...] = ()
    access_expectations: tuple[BordersAccessRow, ...] = ()
    agreements: tuple[BordersAgreementRow, ...] = ()
    disputes: tuple[BordersDisputeRow, ...] = ()
    physical: tuple[BordersPhysicalRow, ...] = ()
    patterns: tuple[BordersPatternRow, ...] = ()
    overlaps: tuple[BordersOverlapRow, ...] = ()
    lineage: tuple[BordersLineageRow, ...] = ()
    alignment: tuple[BordersAlignmentRow, ...] = ()
    metric_provenance: tuple[BordersMetricProvenanceRow, ...] = ()

    def __post_init__(self) -> None:
        for item in fields(type(self)):
            if item.name in BORDERS_FORBIDDEN_FIELD_NAMES:
                raise ValueError(f"borders_forbidden_field:{item.name}")
        if self.schema_version != BORDERS_SNAPSHOT_SCHEMA:
            raise ValueError("borders_snapshot_schema")
        if self.policy_version != BORDERS_SNAPSHOT_POLICY:
            raise ValueError("borders_snapshot_schema")
        _token("catalog_version", self.catalog_version)
        _token("run_id", self.run_id)
        _token("publication_id", self.publication_id)
        if self.digest and _HEX64.match(self.digest) is None:
            raise ValueError("borders_snapshot_digest")
        if type(self.summary) is not BordersSummaryRow:
            raise TypeError("summary must be BordersSummaryRow")
        for row_type in (
            BordersCandidateRow,
            BordersClaimRow,
            BordersRecognitionRow,
            BordersAccessRow,
            BordersAgreementRow,
            BordersDisputeRow,
            BordersPhysicalRow,
            BordersPatternRow,
            BordersOverlapRow,
            BordersLineageRow,
            BordersAlignmentRow,
            BordersMetricProvenanceRow,
        ):
            for item in fields(row_type):
                if item.name in BORDERS_FORBIDDEN_FIELD_NAMES:
                    raise ValueError(
                        f"borders_forbidden_field:{item.name}"
                    )
        caps = (
            ("candidates", self.candidates, "candidate_token"),
            ("claims", self.claims, "domain_token"),
            ("recognitions", self.recognitions, "domain_token"),
            ("access_expectations", self.access_expectations, "domain_token"),
            ("agreements", self.agreements, "domain_token"),
            ("disputes", self.disputes, "domain_token"),
            ("physical", self.physical, "window_start"),
            ("patterns", self.patterns, "domain_token"),
            ("overlaps", self.overlaps, "left_domain_token"),
            ("lineage", self.lineage, "parent_token"),
            ("alignment", self.alignment, "candidate_token"),
            ("metric_provenance", self.metric_provenance, "family"),
        )
        for name, rows, key_name in caps:
            if not isinstance(rows, tuple):
                raise ValueError(f"borders_snapshot_{name}_order")
            if len(rows) > BORDERS_MAX_ROWS_PER_FAMILY:
                raise ValueError(f"borders_snapshot_cap:{name}")
            if name == "lineage" and len(rows) > BORDERS_MAX_LINEAGE_EDGES:
                raise ValueError("borders_snapshot_cap:lineage")
            if name == "physical":
                keys = [(row.location_token, row.window_start) for row in rows]
            elif name in {"claims"}:
                keys = [(row.domain_token, row.owner_token) for row in rows]
            elif name == "recognitions":
                keys = [(row.domain_token, row.basis) for row in rows]
            elif name == "access_expectations":
                keys = [(row.domain_token, row.subject_token, row.mode) for row in rows]
            elif name in {"agreements", "disputes"}:
                keys = [
                    (
                        row.domain_token,
                        getattr(row, "agreement_token", None)
                        or getattr(row, "dispute_token", None),
                    )
                    for row in rows
                ]
            elif name == "patterns":
                keys = [(row.domain_token, row.pattern_token) for row in rows]
            elif name == "overlaps":
                keys = [(row.left_domain_token, row.right_domain_token) for row in rows]
            elif name == "lineage":
                keys = [
                    (row.parent_token, row.child_token, row.edge_token) for row in rows
                ]
            elif name == "alignment":
                keys = [row.candidate_token for row in rows]
            elif name == "metric_provenance":
                keys = [row.family for row in rows]
            else:
                keys = [getattr(row, key_name) for row in rows]
            if keys != sorted(keys):
                raise ValueError(f"borders_snapshot_{name}_order")
            if len(set(keys)) != len(keys):
                raise ValueError("borders_snapshot_duplicate_id")
        domain_tokens = {row.domain_token for row in self.claims}
        for name in (
            "recognitions",
            "access_expectations",
            "agreements",
            "disputes",
            "patterns",
        ):
            for row in getattr(self, name):
                if row.domain_token not in domain_tokens:
                    raise ValueError(f"borders_snapshot_ref:{name}")
        candidate_tokens = {row.candidate_token for row in self.candidates}
        for row in self.alignment:
            if row.candidate_token not in candidate_tokens:
                raise ValueError("borders_snapshot_ref:alignment")
        for row in self.lineage:
            if (
                not _terminal(row.parent_token)
                and row.parent_token not in candidate_tokens
            ):
                raise ValueError("borders_snapshot_ref:lineage_parent")
            if (
                not _terminal(row.child_token)
                and row.child_token not in candidate_tokens
            ):
                raise ValueError("borders_snapshot_ref:lineage_child")
        summary = self.summary
        if (
            summary.claim_count != len(self.claims)
            or summary.agreement_count != len(self.agreements)
            or summary.dispute_count != len(self.disputes)
            or summary.physical_row_count != len(self.physical)
            or summary.pattern_count != len(self.patterns)
            or summary.candidate_count != len(self.candidates)
        ):
            raise ValueError("borders_snapshot_summary_counts")
        if (
            summary.run_id != self.run_id
            or summary.publication_id != self.publication_id
        ):
            raise ValueError("borders_snapshot_summary_identity")


def _terminal(token: str) -> bool:
    return token.startswith("bord-start-") or token.startswith("bord-end-")


def empty_borders_snapshot(
    run_id: str,
    *,
    publication_id: str,
    digest: str,
    catalog_version: str = "metric-catalog-v1",
) -> BordersSnapshot:
    summary = BordersSummaryRow(
        run_id=run_id,
        publication_id=publication_id,
        digest=digest,
        schema_version=BORDERS_SNAPSHOT_SCHEMA,
        policy_version=BORDERS_SNAPSHOT_POLICY,
        catalog_version=catalog_version,
    )
    return BordersSnapshot(
        schema_version=BORDERS_SNAPSHOT_SCHEMA,
        policy_version=BORDERS_SNAPSHOT_POLICY,
        catalog_version=catalog_version,
        run_id=run_id,
        publication_id=publication_id,
        digest=digest,
        summary=summary,
    )
