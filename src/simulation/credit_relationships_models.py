"""Canonical sibling records for completed-run credit relationship snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "CREDIT_RELATIONSHIPS_ARTIFACT_MAX_BYTES",
    "CREDIT_RELATIONSHIPS_MAX_ALIGNMENTS",
    "CREDIT_RELATIONSHIPS_MAX_CLAIMS",
    "CREDIT_RELATIONSHIPS_MAX_COUNTERPARTIES",
    "CREDIT_RELATIONSHIPS_MAX_DISTRIBUTIONS",
    "CREDIT_RELATIONSHIPS_MAX_PERFORMANCES",
    "CREDIT_RELATIONSHIPS_MAX_RELATIONSHIPS",
    "CREDIT_RELATIONSHIPS_MAX_WINDOWS",
    "CREDIT_RELATIONSHIPS_PUBLICATION_PREFIX",
    "CREDIT_RELATIONSHIPS_SNAPSHOT_POLICY",
    "CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION",
    "CreditAlignmentRecord",
    "CreditClaimRecord",
    "CreditCounterpartyRecord",
    "CreditDistributionRecord",
    "CreditPerformanceRecord",
    "CreditRelationshipRecord",
    "CreditRelationshipsSnapshot",
    "CreditSummaryRecord",
    "empty_credit_relationships_snapshot",
]

CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION: Final[str] = (
    "credit-relationships-snapshot-v1"
)
CREDIT_RELATIONSHIPS_SNAPSHOT_POLICY: Final[str] = "credit-relationships.v1"
CREDIT_RELATIONSHIPS_PUBLICATION_PREFIX: Final[str] = "cred-pub-"
CREDIT_RELATIONSHIPS_MAX_RELATIONSHIPS: Final[int] = 2_048
CREDIT_RELATIONSHIPS_MAX_CLAIMS: Final[int] = 4_096
CREDIT_RELATIONSHIPS_MAX_PERFORMANCES: Final[int] = 2_048
CREDIT_RELATIONSHIPS_MAX_DISTRIBUTIONS: Final[int] = 4_096
CREDIT_RELATIONSHIPS_MAX_COUNTERPARTIES: Final[int] = 1_024
CREDIT_RELATIONSHIPS_MAX_ALIGNMENTS: Final[int] = 4_096
CREDIT_RELATIONSHIPS_MAX_WINDOWS: Final[int] = 512
CREDIT_RELATIONSHIPS_ARTIFACT_MAX_BYTES: Final[int] = 8_388_608

_COVERAGE = {"complete", "partial", "missing"}
_DIRECTIONS = {"owner_debtor", "owner_creditor"}
_STATUSES = {
    "proposed",
    "accepted",
    "open",
    "partially_repaid",
    "repaid",
    "defaulted",
    "forgiven",
    "disputed",
    "withdrawn",
    "declined",
    "expired",
}
_ACTS = {
    "propose",
    "accept",
    "decline",
    "repay",
    "default",
    "renegotiate",
    "forgive",
    "dispute",
    "withdraw",
}
_CONDITIONS = {
    "on_receipt",
    "by_deadline",
    "after_return",
    "shared_witness",
    "unspecified",
}
_COLLATERAL = {
    "none",
    "item_pledge",
    "service_pledge",
    "custody_pledge",
    "reputation_pledge",
    "unspecified",
}
_OUTCOMES = {
    "active",
    "partially_repaid",
    "repaid",
    "defaulted",
    "forgiven",
    "disputed",
    "expired",
    "insufficient_evidence",
}
_ALIGNMENTS = {"consistent", "unresolved", "inconsistent", "not_applicable"}
_SAMPLE_SOURCES = {"proposed", "agreed"}
_DISTRIBUTION_STATUSES = {"available", "insufficient_samples"}


def _count(value: object) -> int:
    return require_exact_nonneg_int("count", value)


def _token(value: object) -> str:
    if type(value) is not str or not value:
        raise ValueError("credit_relationships_snapshot_invalid")
    return require_stable_id("token", value)


def _enum(value: object, allowed: set[str]) -> str:
    token = getattr(value, "value", value)
    if token not in allowed:
        raise ValueError("credit_relationships_snapshot_invalid")
    return str(token)


def _coverage(value: object) -> str:
    return _enum(value, _COVERAGE)


def _optional_tick(value: object) -> int | None:
    if value is None:
        return None
    return _count(value)


@dataclass(frozen=True, slots=True)
class CreditSummaryRecord:
    window_tick: int
    window_count: int
    relationship_count: int
    claim_count: int
    performance_count: int
    distribution_count: int
    counterparty_count: int
    alignment_count: int
    claim_event_count: int
    transfer_event_count: int
    evidence_coverage: str
    owner_coverage: str
    relationship_coverage: str
    performance_coverage: str
    distribution_coverage: str
    counterparty_coverage: str
    alignment_coverage: str
    coverage: str
    truncated: bool

    def __post_init__(self) -> None:
        for name in (
            "window_tick",
            "window_count",
            "relationship_count",
            "claim_count",
            "performance_count",
            "distribution_count",
            "counterparty_count",
            "alignment_count",
            "claim_event_count",
            "transfer_event_count",
        ):
            _count(getattr(self, name))
        for name in (
            "evidence_coverage",
            "owner_coverage",
            "relationship_coverage",
            "performance_coverage",
            "distribution_coverage",
            "counterparty_coverage",
            "alignment_coverage",
            "coverage",
        ):
            object.__setattr__(self, name, _coverage(getattr(self, name)))
        if type(self.truncated) is not bool:
            raise ValueError("credit_relationships_snapshot_invalid")


@dataclass(frozen=True, slots=True)
class CreditRelationshipRecord:
    relationship_id: str
    window_index: int
    owner_token: str
    counterparty_token: str
    direction: str
    anchor_token: str
    principal_kind: str
    principal_quantity: int
    repayment_kind: str
    repayment_quantity: int
    repayment_ratio_milli: int
    due_tick: int | None
    condition: str
    collateral_kind: str
    collateral_quantity: int
    status: str
    confidence_milli: int
    expectation_milli: int
    trust_milli: int
    claim_count: int
    coverage: str

    def __post_init__(self) -> None:
        for name in (
            "relationship_id",
            "owner_token",
            "counterparty_token",
            "anchor_token",
            "principal_kind",
            "repayment_kind",
        ):
            _token(getattr(self, name))
        object.__setattr__(
            self, "direction", _enum(self.direction, _DIRECTIONS)
        )
        for name in (
            "window_index",
            "principal_quantity",
            "repayment_quantity",
            "repayment_ratio_milli",
            "collateral_quantity",
            "confidence_milli",
            "expectation_milli",
            "trust_milli",
            "claim_count",
        ):
            _count(getattr(self, name))
        object.__setattr__(self, "due_tick", _optional_tick(self.due_tick))
        object.__setattr__(
            self, "condition", _enum(self.condition, _CONDITIONS)
        )
        object.__setattr__(
            self, "collateral_kind", _enum(self.collateral_kind, _COLLATERAL)
        )
        object.__setattr__(self, "status", _enum(self.status, _STATUSES))
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class CreditClaimRecord:
    claim_id: str
    window_index: int
    event_token: str
    actor_token: str
    counterparty_token: str
    act: str
    direction: str
    anchor_token: str
    principal_kind: str
    principal_quantity: int
    repayment_kind: str
    repayment_quantity: int
    paid_quantity: int
    opened_tick: int
    due_tick: int | None
    condition: str
    collateral_kind: str
    collateral_quantity: int
    confidence_milli: int
    coverage: str

    def __post_init__(self) -> None:
        for name in (
            "claim_id",
            "event_token",
            "actor_token",
            "counterparty_token",
            "anchor_token",
            "principal_kind",
            "repayment_kind",
        ):
            _token(getattr(self, name))
        object.__setattr__(self, "act", _enum(self.act, _ACTS))
        object.__setattr__(
            self, "direction", _enum(self.direction, _DIRECTIONS)
        )
        for name in (
            "window_index",
            "principal_quantity",
            "repayment_quantity",
            "paid_quantity",
            "opened_tick",
            "collateral_quantity",
            "confidence_milli",
        ):
            _count(getattr(self, name))
        object.__setattr__(self, "due_tick", _optional_tick(self.due_tick))
        object.__setattr__(
            self, "condition", _enum(self.condition, _CONDITIONS)
        )
        object.__setattr__(
            self, "collateral_kind", _enum(self.collateral_kind, _COLLATERAL)
        )
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class CreditPerformanceRecord:
    performance_id: str
    window_index: int
    anchor_token: str
    claim_count: int
    repay_claim_count: int
    default_claim_count: int
    forgive_claim_count: int
    dispute_claim_count: int
    renegotiate_claim_count: int
    observed_transfer_count: int
    repaid_quantity: int
    principal_quantity: int
    repayment_quantity: int
    outcome: str
    coverage: str

    def __post_init__(self) -> None:
        for name in ("performance_id", "anchor_token"):
            _token(getattr(self, name))
        for name in (
            "window_index",
            "claim_count",
            "repay_claim_count",
            "default_claim_count",
            "forgive_claim_count",
            "dispute_claim_count",
            "renegotiate_claim_count",
            "observed_transfer_count",
            "repaid_quantity",
            "principal_quantity",
            "repayment_quantity",
        ):
            _count(getattr(self, name))
        object.__setattr__(self, "outcome", _enum(self.outcome, _OUTCOMES))
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class CreditDistributionRecord:
    distribution_id: str
    window_index: int
    principal_kind: str
    repayment_kind: str
    sample_source: str
    sample_count: int
    min_ratio_milli: int
    p25_ratio_milli: int
    median_ratio_milli: int
    p75_ratio_milli: int
    max_ratio_milli: int
    iqr_milli: int
    dispersion_milli: int
    bin_shares_milli: tuple[int, int, int, int, int]
    status: str
    coverage: str

    def __post_init__(self) -> None:
        for name in ("distribution_id", "principal_kind", "repayment_kind"):
            _token(getattr(self, name))
        object.__setattr__(
            self, "sample_source", _enum(self.sample_source, _SAMPLE_SOURCES)
        )
        for name in (
            "window_index",
            "sample_count",
            "min_ratio_milli",
            "p25_ratio_milli",
            "median_ratio_milli",
            "p75_ratio_milli",
            "max_ratio_milli",
            "iqr_milli",
            "dispersion_milli",
        ):
            _count(getattr(self, name))
        bins = self.bin_shares_milli
        if type(bins) is not tuple or len(bins) != 5:
            raise ValueError("credit_relationships_snapshot_invalid")
        for share in bins:
            if isinstance(share, bool) or type(share) is not int:
                raise ValueError("credit_relationships_snapshot_invalid")
            if not 0 <= share <= 1_000:
                raise ValueError("credit_relationships_snapshot_invalid")
        status = _enum(self.status, _DISTRIBUTION_STATUSES)
        if status == "available" and sum(bins) != 1_000:
            raise ValueError("credit_relationships_snapshot_invalid")
        if status == "available" and not (
            self.min_ratio_milli
            <= self.p25_ratio_milli
            <= self.median_ratio_milli
            <= self.p75_ratio_milli
            <= self.max_ratio_milli
        ):
            raise ValueError("credit_relationships_snapshot_invalid")
        object.__setattr__(self, "bin_shares_milli", bins)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class CreditCounterpartyRecord:
    counterparty_token: str
    window_index: int
    relationship_count: int
    owner_count: int
    claim_count: int
    repay_claim_count: int
    default_claim_count: int
    forgive_claim_count: int
    dispute_claim_count: int
    observed_transfer_count: int
    coverage: str

    def __post_init__(self) -> None:
        _token(self.counterparty_token)
        for name in (
            "window_index",
            "relationship_count",
            "owner_count",
            "claim_count",
            "repay_claim_count",
            "default_claim_count",
            "forgive_claim_count",
            "dispute_claim_count",
            "observed_transfer_count",
        ):
            _count(getattr(self, name))
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class CreditAlignmentRecord:
    alignment_id: str
    window_index: int
    owner_token: str
    anchor_token: str
    alignment: str
    owner_status: str
    analytical_outcome: str
    owner_paid_quantity: int
    declared_repayment_quantity: int
    observed_transfer_count: int
    gap_milli: int
    coverage: str

    def __post_init__(self) -> None:
        for name in ("alignment_id", "owner_token", "anchor_token"):
            _token(getattr(self, name))
        object.__setattr__(
            self, "alignment", _enum(self.alignment, _ALIGNMENTS)
        )
        object.__setattr__(
            self, "owner_status", _enum(self.owner_status, _STATUSES)
        )
        object.__setattr__(
            self, "analytical_outcome", _enum(self.analytical_outcome, _OUTCOMES)
        )
        for name in (
            "window_index",
            "owner_paid_quantity",
            "declared_repayment_quantity",
            "observed_transfer_count",
            "gap_milli",
        ):
            _count(getattr(self, name))
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class CreditRelationshipsSnapshot:
    run_id: str
    schema_version: str
    policy_version: str
    summary: CreditSummaryRecord
    relationships: tuple[CreditRelationshipRecord, ...]
    claims: tuple[CreditClaimRecord, ...]
    performances: tuple[CreditPerformanceRecord, ...]
    distributions: tuple[CreditDistributionRecord, ...]
    counterparties: tuple[CreditCounterpartyRecord, ...]
    alignments: tuple[CreditAlignmentRecord, ...]
    digest: str = ""
    publication_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_stable_id("run_id", self.run_id))
        if self.schema_version != CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION:
            raise ValueError("credit_relationships_snapshot_version")
        if self.policy_version != CREDIT_RELATIONSHIPS_SNAPSHOT_POLICY:
            raise ValueError("credit_relationships_snapshot_version")
        if type(self.summary) is not CreditSummaryRecord:
            raise ValueError("credit_relationships_snapshot_invalid")
        for name, row_type, cap, id_field in (
            (
                "relationships",
                CreditRelationshipRecord,
                CREDIT_RELATIONSHIPS_MAX_RELATIONSHIPS,
                "relationship_id",
            ),
            ("claims", CreditClaimRecord, CREDIT_RELATIONSHIPS_MAX_CLAIMS, "claim_id"),
            (
                "performances",
                CreditPerformanceRecord,
                CREDIT_RELATIONSHIPS_MAX_PERFORMANCES,
                "performance_id",
            ),
            (
                "distributions",
                CreditDistributionRecord,
                CREDIT_RELATIONSHIPS_MAX_DISTRIBUTIONS,
                "distribution_id",
            ),
            (
                "counterparties",
                CreditCounterpartyRecord,
                CREDIT_RELATIONSHIPS_MAX_COUNTERPARTIES,
                "counterparty_token",
            ),
            (
                "alignments",
                CreditAlignmentRecord,
                CREDIT_RELATIONSHIPS_MAX_ALIGNMENTS,
                "alignment_id",
            ),
        ):
            values = getattr(self, name)
            if type(values) is not tuple or len(values) > cap:
                raise ValueError("credit_relationships_snapshot_invalid")
            seen: set[str] = set()
            for row in values:
                if type(row) is not row_type:
                    raise ValueError("credit_relationships_snapshot_invalid")
                identity = getattr(row, id_field)
                if identity in seen:
                    raise ValueError("credit_relationships_snapshot_invalid")
                seen.add(identity)
        if type(self.digest) is not str or type(self.publication_id) is not str:
            raise ValueError("credit_relationships_snapshot_invalid")


def empty_credit_relationships_snapshot(run_id: str) -> CreditRelationshipsSnapshot:
    """Return one empty canonical snapshot with missing coverage."""

    missing = "missing"
    return CreditRelationshipsSnapshot(
        run_id=run_id,
        schema_version=CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION,
        policy_version=CREDIT_RELATIONSHIPS_SNAPSHOT_POLICY,
        summary=CreditSummaryRecord(
            window_tick=0,
            window_count=0,
            relationship_count=0,
            claim_count=0,
            performance_count=0,
            distribution_count=0,
            counterparty_count=0,
            alignment_count=0,
            claim_event_count=0,
            transfer_event_count=0,
            evidence_coverage=missing,
            owner_coverage=missing,
            relationship_coverage=missing,
            performance_coverage=missing,
            distribution_coverage=missing,
            counterparty_coverage=missing,
            alignment_coverage=missing,
            coverage=missing,
            truncated=False,
        ),
        relationships=(),
        claims=(),
        performances=(),
        distributions=(),
        counterparties=(),
        alignments=(),
    )
