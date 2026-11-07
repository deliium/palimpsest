"""Closed detached-analysis vocabulary and rows for border claims.

Analysis rows are read-only projections. They never feed cognition, prompts,
memory, world state, stop selectors, or observer semantics. No row is a truth,
a winner, a sovereignty finding, or a composite score.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from decimal import Decimal
from typing import Final

__all__ = [
    "BORDER_ALIGNMENTS",
    "BORDER_ANALYSIS_POLICY_VERSION",
    "BORDER_CANDIDATE_PREFIX",
    "BORDER_CONTROL_PATTERNS",
    "BORDER_EDGE_PREFIX",
    "BORDER_FORBIDDEN_RESULT_FIELDS",
    "BORDER_LAYERS",
    "BorderAccessRow",
    "BorderAgreementRow",
    "BorderAlignmentRow",
    "BorderAnalysisSummary",
    "BorderCandidate",
    "BorderClaimRow",
    "BorderControlSummary",
    "BorderDisputeRow",
    "BorderLayer",
    "BorderLineageEdge",
    "BorderOverlapRow",
    "BorderPatternRow",
    "BorderRecognitionRow",
]

BORDER_ANALYSIS_POLICY_VERSION: Final[str] = "borders-analysis.v1"
BORDER_CANDIDATE_PREFIX: Final[str] = "bord-"
BORDER_EDGE_PREFIX: Final[str] = "bord-edge-"
BORDER_LAYERS: Final[frozenset[str]] = frozenset(
    {"physical", "subjective_claim", "agreement", "analytical_pattern"}
)
BORDER_CONTROL_PATTERNS: Final[frozenset[str]] = frozenset(
    {
        "unclaimed",
        "claim_only",
        "claim_aligned",
        "claim_overlap",
        "agreement_aligned",
        "agreement_contested",
        "physical_unclaimed",
        "contested",
        "unknown",
    }
)
BORDER_ALIGNMENTS: Final[frozenset[str]] = frozenset(
    {"consistent", "unresolved", "inconsistent", "not_applicable"}
)
BORDER_FORBIDDEN_RESULT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "sovereign",
        "sovereignty",
        "legitimate",
        "legitimacy",
        "winner",
        "loser",
        "score",
        "composite",
        "enforced",
        "enforcement",
        "ownership",
        "country_owner",
        "raw_owner_id",
        "raw_entity_id",
        "raw_agent_id",
    }
)

_QUANTUM: Final[Decimal] = Decimal("0.000001")
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")


class BorderLayer:
    """Closed layer names. Plain constants keep analysis import-closed."""

    PHYSICAL = "physical"
    SUBJECTIVE_CLAIM = "subjective_claim"
    AGREEMENT = "agreement"
    ANALYTICAL_PATTERN = "analytical_pattern"


def _fail(name: str, code: str) -> ValueError:
    return ValueError(f"{name}: {code}")


def _token(name: str, value: object) -> str:
    if type(value) is not str or not value:
        raise _fail(name, "invalid_token")
    return value


def _tokens(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, set, frozenset, Mapping)) or not isinstance(
        values, Sequence
    ):
        raise _fail(name, "invalid_type")
    return tuple(_token(name, item) for item in values)


def _edges(name: str, values: object) -> tuple[tuple[str, str], ...]:
    raw = _tokens_pair(name, values)
    for left, right in raw:
        if left == right:
            raise _fail(name, "self_edge")
    return tuple(sorted(raw))


def _tokens_pair(name: str, values: object) -> list[tuple[str, str]]:
    if isinstance(values, (str, bytes, set, frozenset, Mapping)) or not isinstance(
        values, Sequence
    ):
        raise _fail(name, "invalid_type")
    pairs: list[tuple[str, str]] = []
    for item in values:
        if type(item) is not tuple or len(item) != 2:
            raise _fail(name, "invalid_edge")
        pairs.append((_token(name, item[0]), _token(name, item[1])))
    if len(set(pairs)) != len(pairs):
        raise _fail(name, "duplicate")
    return pairs


def _nonneg(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise _fail(name, "invalid_count")
    return value


def _unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(name, "not_finite")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise _fail(name, "out_of_range")
    steps = round(number / 1e-6)
    quantized = float(Decimal(steps) * _QUANTUM)
    return 0.0 if quantized == 0.0 else quantized


def _forbid(result_type: type) -> None:
    for item in fields(result_type):
        if item.name in BORDER_FORBIDDEN_RESULT_FIELDS:
            raise _fail(result_type.__name__, item.name)


@dataclass(frozen=True, slots=True)
class BorderClaimRow:
    owner_token: str
    domain_token: str
    location_tokens: tuple[str, ...]
    boundary_edge_tokens: tuple[tuple[str, str], ...]
    status: str
    strength: float
    anchor_token: str = ""

    def __post_init__(self) -> None:
        _forbid(type(self))
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
class BorderRecognitionRow:
    recognition_token: str
    domain_token: str
    edge_tokens: tuple[tuple[str, str], ...]
    basis: str
    status: str

    def __post_init__(self) -> None:
        _forbid(type(self))
        _token("recognition_token", self.recognition_token)
        _token("domain_token", self.domain_token)
        object.__setattr__(self, "edge_tokens", _edges("edge_tokens", self.edge_tokens))
        _token("basis", self.basis)
        _token("status", self.status)


@dataclass(frozen=True, slots=True)
class BorderAccessRow:
    access_token: str
    domain_token: str
    subject_token: str
    mode: str
    status: str

    def __post_init__(self) -> None:
        _forbid(type(self))
        _token("access_token", self.access_token)
        _token("domain_token", self.domain_token)
        _token("mode", self.mode)
        _token("status", self.status)


@dataclass(frozen=True, slots=True)
class BorderAgreementRow:
    agreement_token: str
    domain_token: str
    counterparty_token: str
    provision_tokens: tuple[str, ...]
    status: str
    recognition: str
    effective_tick: int | None = None
    expiry_tick: int | None = None

    def __post_init__(self) -> None:
        _forbid(type(self))
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
class BorderDisputeRow:
    dispute_token: str
    domain_token: str
    counterparty_token: str
    contested_location_tokens: tuple[str, ...]
    status: str

    def __post_init__(self) -> None:
        _forbid(type(self))
        _token("dispute_token", self.dispute_token)
        _token("domain_token", self.domain_token)
        object.__setattr__(
            self,
            "contested_location_tokens",
            _tokens("contested_location_tokens", self.contested_location_tokens),
        )
        _token("status", self.status)


@dataclass(frozen=True, slots=True)
class BorderPatternRow:
    pattern_token: str
    domain_token: str
    location_tokens: tuple[str, ...]
    pattern: str
    physical_actions: int = 0
    claim_count: int = 0
    agreement_count: int = 0
    dispute_count: int = 0

    def __post_init__(self) -> None:
        _forbid(type(self))
        _token("pattern_token", self.pattern_token)
        _token("domain_token", self.domain_token)
        object.__setattr__(
            self, "location_tokens", _tokens("location_tokens", self.location_tokens)
        )
        if self.pattern not in BORDER_CONTROL_PATTERNS:
            raise _fail("pattern", "unknown_pattern")
        for name in (
            "physical_actions",
            "claim_count",
            "agreement_count",
            "dispute_count",
        ):
            object.__setattr__(self, name, _nonneg(name, getattr(self, name)))


@dataclass(frozen=True, slots=True)
class BorderOverlapRow:
    left_domain_token: str
    right_domain_token: str
    overlap_location_tokens: tuple[str, ...]
    overlap_count: int
    dispute_status: str

    def __post_init__(self) -> None:
        _forbid(type(self))
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
class BorderCandidate:
    candidate_id: str
    location_tokens: tuple[str, ...]
    boundary_edge_tokens: tuple[tuple[str, str], ...]
    status: str
    evidence_count: int
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _forbid(type(self))
        _token("candidate_id", self.candidate_id)
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
        if self.first_tick > self.last_tick:
            raise _fail("first_tick", "tick_order")


@dataclass(frozen=True, slots=True)
class BorderLineageEdge:
    edge_id: str
    parent_token: str
    child_token: str
    kind: str
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _forbid(type(self))
        _token("edge_id", self.edge_id)
        _token("parent_token", self.parent_token)
        _token("child_token", self.child_token)
        if self.kind not in {
            "emerged",
            "continued",
            "transformed",
            "split",
            "merge",
            "dissolved",
        }:
            raise _fail("kind", "unknown_lineage_kind")
        object.__setattr__(self, "first_tick", _nonneg("first_tick", self.first_tick))
        object.__setattr__(self, "last_tick", _nonneg("last_tick", self.last_tick))


@dataclass(frozen=True, slots=True)
class BorderAlignmentRow:
    candidate_id: str
    alignment: str
    claim_alignment: str
    agreement_alignment: str
    pattern_alignment: str
    basis_counts: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        _forbid(type(self))
        _token("candidate_id", self.candidate_id)
        for name in (
            "alignment",
            "claim_alignment",
            "agreement_alignment",
            "pattern_alignment",
        ):
            value = getattr(self, name)
            if value not in BORDER_ALIGNMENTS:
                raise _fail(name, "unknown_alignment")
        counts = tuple(self.basis_counts)
        for item in counts:
            if type(item) is not tuple or len(item) != 2:
                raise _fail("basis_counts", "invalid_entry")
            _token("basis_counts", item[0])
            _nonneg("basis_counts", item[1])
        object.__setattr__(self, "basis_counts", tuple(sorted(counts)))


@dataclass(frozen=True, slots=True)
class BorderControlSummary:
    pattern_counts: tuple[tuple[str, int], ...] = ()
    denominator_kind: str = "observed_domains"
    coverage: str = "not_applicable"


@dataclass(frozen=True, slots=True)
class BorderAnalysisSummary:
    candidate_count: int = 0
    claim_count: int = 0
    agreement_count: int = 0
    dispute_count: int = 0
    physical_row_count: int = 0
    pattern_count: int = 0
    alignment_counts: tuple[tuple[str, int], ...] = ()
    coverage: str = "not_applicable"
    policy_version: str = BORDER_ANALYSIS_POLICY_VERSION
    catalog_version: str = ""

    def __post_init__(self) -> None:
        _forbid(type(self))
        for name in (
            "candidate_count",
            "claim_count",
            "agreement_count",
            "dispute_count",
            "physical_row_count",
            "pattern_count",
        ):
            object.__setattr__(self, name, _nonneg(name, getattr(self, name)))
        if self.coverage not in {"complete", "partial", "not_applicable", "observed"}:
            raise _fail("coverage", "unknown_coverage")


assert _HEX
