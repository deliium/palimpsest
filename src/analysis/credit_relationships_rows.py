"""Frozen detached rows for credit relationship evidence and analytics."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final, cast

from analysis.credit_relationships_contract import (
    CREDIT_ALIGNMENT_PREFIX,
    CREDIT_ANALYSIS_FORBIDDEN_KEYS,
    CREDIT_CLAIM_CONDITIONS,
    CREDIT_CLAIM_PREFIX,
    CREDIT_COLLATERAL_KINDS,
    CREDIT_DISTRIBUTION_PREFIX,
    CREDIT_OWNER_PREFIX,
    CREDIT_PERFORMANCE_PREFIX,
    CreditAlignment,
    CreditAnalysisLayer,
    CreditClaimAct,
    CreditClaimDirection,
    CreditCoverage,
    CreditDistributionStatus,
    CreditOwnerLevel,
    CreditOwnerStatus,
    CreditPerformanceOutcome,
    CreditRelationshipAnalysisError,
    CreditSampleSource,
)
from world.identifiers import require_stable_id

__all__ = [
    "AnalyticalCreditRelationshipRow",
    "CreditAlignmentRow",
    "CreditClaimEvidenceRow",
    "CreditCounterpartyRow",
    "CreditDistributionRow",
    "CreditEvidenceHarvest",
    "CreditOwnerInput",
    "CreditPerformanceRow",
    "CreditTransferEvidenceRow",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.credit_relationships.rows"
)


def _forbid_keys(cls: type[object]) -> None:
    if set(getattr(cls, "__dataclass_fields__", {})) & CREDIT_ANALYSIS_FORBIDDEN_KEYS:
        raise CreditRelationshipAnalysisError("credit_analysis_forbidden_key")


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    return value


def _positive(name: str, value: object) -> int:
    number = _count(name, value)
    if number < 1:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    return number


def _token(name: str, value: object) -> str:
    if type(value) is not str or not value:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    try:
        return require_stable_id(name, value)
    except (TypeError, ValueError) as exc:
        raise CreditRelationshipAnalysisError(
            "credit_analysis_invalid_row"
        ) from exc


def _prefixed(value: object, prefix: str) -> str:
    if (
        type(value) is not str
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 16
        or any(
            character not in "0123456789abcdef"
            for character in value[len(prefix) :]
        )
    ):
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    return value


def _enum(value: object, enum_type: type) -> object:
    if type(value) is not enum_type:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    return value


def _optional_tick(name: str, value: object) -> int | None:
    if value is None:
        return None
    return _count(name, value)


@dataclass(frozen=True, slots=True)
class CreditClaimEvidenceRow:
    """One committed ``crd_v1`` claim relation, token-only."""

    claim_id: str
    tick: int
    window_index: int
    event_token: str
    actor_token: str
    counterparty_token: str
    act: CreditClaimAct
    direction: CreditClaimDirection
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
    collateral_item_kind: str | None
    collateral_quantity: int
    confidence_milli: int
    coverage: CreditCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self, "claim_id", _prefixed(self.claim_id, CREDIT_CLAIM_PREFIX)
        )
        object.__setattr__(self, "tick", _count("tick", self.tick))
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(self, "event_token", _token("event_token", self.event_token))
        object.__setattr__(self, "actor_token", _token("actor_token", self.actor_token))
        object.__setattr__(
            self,
            "counterparty_token",
            _token("counterparty_token", self.counterparty_token),
        )
        object.__setattr__(self, "act", _enum(self.act, CreditClaimAct))
        object.__setattr__(
            self, "direction", _enum(self.direction, CreditClaimDirection)
        )
        object.__setattr__(
            self, "anchor_token", _token("anchor_token", self.anchor_token)
        )
        object.__setattr__(
            self, "principal_kind", _token("principal_kind", self.principal_kind)
        )
        object.__setattr__(
            self, "repayment_kind", _token("repayment_kind", self.repayment_kind)
        )
        object.__setattr__(
            self,
            "principal_quantity",
            _positive("principal_quantity", self.principal_quantity),
        )
        object.__setattr__(
            self,
            "repayment_quantity",
            _positive("repayment_quantity", self.repayment_quantity),
        )
        paid = _count("paid_quantity", self.paid_quantity)
        if paid > 16:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        if self.act is not CreditClaimAct.REPAY and paid != 0:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        object.__setattr__(self, "paid_quantity", paid)
        object.__setattr__(self, "opened_tick", _count("opened_tick", self.opened_tick))
        object.__setattr__(self, "due_tick", _optional_tick("due_tick", self.due_tick))
        if self.due_tick is not None and self.due_tick < self.opened_tick:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        if self.condition not in CREDIT_CLAIM_CONDITIONS:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        if self.collateral_kind not in CREDIT_COLLATERAL_KINDS:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        collateral = self.collateral_item_kind
        if collateral is not None:
            object.__setattr__(
                self,
                "collateral_item_kind",
                _token("collateral_item_kind", collateral),
            )
        quantity = _count("collateral_quantity", self.collateral_quantity)
        if self.collateral_kind in {"none", "unspecified"}:
            if collateral is not None or quantity != 0:
                raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        elif self.collateral_kind in {"item_pledge", "custody_pledge"}:
            if collateral is None or not 1 <= quantity <= 16:
                raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        elif collateral is not None or quantity != 0:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        object.__setattr__(self, "collateral_quantity", quantity)
        confidence = _count("confidence_milli", self.confidence_milli)
        if confidence > 1_000:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        object.__setattr__(self, "confidence_milli", confidence)
        object.__setattr__(self, "coverage", _enum(self.coverage, CreditCoverage))


@dataclass(frozen=True, slots=True)
class CreditTransferEvidenceRow:
    """One committed ``Given`` transfer with a resolved item kind or unknown."""

    tick: int
    window_index: int
    event_token: str
    actor_token: str
    recipient_token: str
    item_kind: str
    quantity: int
    coverage: CreditCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "tick", _count("tick", self.tick))
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(self, "event_token", _token("event_token", self.event_token))
        object.__setattr__(self, "actor_token", _token("actor_token", self.actor_token))
        object.__setattr__(
            self, "recipient_token", _token("recipient_token", self.recipient_token)
        )
        object.__setattr__(self, "item_kind", _token("item_kind", self.item_kind))
        object.__setattr__(self, "quantity", _positive("quantity", self.quantity))
        object.__setattr__(self, "coverage", _enum(self.coverage, CreditCoverage))


@dataclass(frozen=True, slots=True)
class CreditEvidenceHarvest:
    """Bounded, token-only claim and transfer evidence with coverage."""

    claims: tuple[CreditClaimEvidenceRow, ...]
    transfers: tuple[CreditTransferEvidenceRow, ...]
    coverage: CreditCoverage
    notices: tuple[str, ...]
    claim_count: int
    transfer_count: int

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "coverage", _enum(self.coverage, CreditCoverage))
        for claim in self.claims:
            if type(claim) is not CreditClaimEvidenceRow:
                raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        for transfer in self.transfers:
            if type(transfer) is not CreditTransferEvidenceRow:
                raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        if self.claim_count != len(self.claims):
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        if self.transfer_count != len(self.transfers):
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        object.__setattr__(self, "notices", tuple(sorted(set(self.notices))))


def _validated_bins(value: object) -> tuple[int, int, int, int, int]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    values = tuple(value)
    if len(values) != 5:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    for item in values:
        if isinstance(item, bool) or type(item) is not int or not 0 <= item <= 1_000:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    return cast(tuple[int, int, int, int, int], values)


@dataclass(frozen=True, slots=True)
class CreditPerformanceRow:
    """One descriptive performance outcome for an anchor in a window."""

    performance_id: str
    window_index: int
    anchor_token: str
    debtor_token: str
    creditor_token: str
    direction: CreditClaimDirection
    principal_kind: str
    repayment_kind: str
    principal_quantity: int
    repayment_quantity: int
    paid_quantity: int
    claim_count: int
    propose_count: int
    accept_count: int
    decline_count: int
    withdraw_count: int
    repay_count: int
    default_count: int
    renegotiate_count: int
    forgive_count: int
    dispute_count: int
    observed_transfer_count: int
    outcome: CreditPerformanceOutcome
    first_tick: int
    last_tick: int
    due_tick: int | None
    direction_conflict: bool
    coverage: CreditCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self,
            "performance_id",
            _prefixed(self.performance_id, CREDIT_PERFORMANCE_PREFIX),
        )
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        for name in ("anchor_token", "debtor_token", "creditor_token"):
            object.__setattr__(self, name, _token(name, getattr(self, name)))
        object.__setattr__(
            self, "direction", _enum(self.direction, CreditClaimDirection)
        )
        for name in (
            "principal_kind",
            "repayment_kind",
        ):
            object.__setattr__(self, name, _token(name, getattr(self, name)))
        for name in (
            "principal_quantity",
            "repayment_quantity",
        ):
            object.__setattr__(self, name, _positive(name, getattr(self, name)))
        for name in (
            "paid_quantity",
            "claim_count",
            "propose_count",
            "accept_count",
            "decline_count",
            "withdraw_count",
            "repay_count",
            "default_count",
            "renegotiate_count",
            "forgive_count",
            "dispute_count",
            "observed_transfer_count",
            "first_tick",
            "last_tick",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        if self.paid_quantity > self.repayment_quantity:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        object.__setattr__(self, "due_tick", _optional_tick("due_tick", self.due_tick))
        object.__setattr__(
            self, "outcome", _enum(self.outcome, CreditPerformanceOutcome)
        )
        if type(self.direction_conflict) is not bool:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        object.__setattr__(self, "coverage", _enum(self.coverage, CreditCoverage))


@dataclass(frozen=True, slots=True)
class CreditDistributionRow:
    """One descriptive repayment-ratio distribution for a kind pair."""

    distribution_id: str
    window_index: int
    principal_kind: str
    repayment_kind: str
    sample_source: CreditSampleSource
    sample_count: int
    min_ratio_milli: int
    p25_ratio_milli: int
    median_ratio_milli: int
    p75_ratio_milli: int
    max_ratio_milli: int
    iqr_milli: int
    dispersion_milli: int
    bin_shares_milli: tuple[int, int, int, int, int]
    status: CreditDistributionStatus
    coverage: CreditCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self,
            "distribution_id",
            _prefixed(self.distribution_id, CREDIT_DISTRIBUTION_PREFIX),
        )
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(
            self, "principal_kind", _token("principal_kind", self.principal_kind)
        )
        object.__setattr__(
            self, "repayment_kind", _token("repayment_kind", self.repayment_kind)
        )
        object.__setattr__(
            self, "sample_source", _enum(self.sample_source, CreditSampleSource)
        )
        object.__setattr__(
            self, "sample_count", _count("sample_count", self.sample_count)
        )
        for name in (
            "min_ratio_milli",
            "p25_ratio_milli",
            "median_ratio_milli",
            "p75_ratio_milli",
            "max_ratio_milli",
            "iqr_milli",
            "dispersion_milli",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        object.__setattr__(
            self, "bin_shares_milli", _validated_bins(self.bin_shares_milli)
        )
        object.__setattr__(
            self, "status", _enum(self.status, CreditDistributionStatus)
        )
        object.__setattr__(self, "coverage", _enum(self.coverage, CreditCoverage))


@dataclass(frozen=True, slots=True)
class CreditCounterpartyRow:
    """Descriptive aggregate over one unordered party pair in a window."""

    counterparty_id: str
    window_index: int
    left_token: str
    right_token: str
    relationship_count: int
    owner_count: int
    claim_count: int
    repay_claim_count: int
    default_claim_count: int
    forgive_claim_count: int
    dispute_claim_count: int
    renegotiate_claim_count: int
    observed_transfer_count: int
    coverage: CreditCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self,
            "counterparty_id",
            _prefixed(self.counterparty_id, "credcp-"),
        )
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        for name in ("left_token", "right_token"):
            object.__setattr__(self, name, _token(name, getattr(self, name)))
        for name in (
            "relationship_count",
            "owner_count",
            "claim_count",
            "repay_claim_count",
            "default_claim_count",
            "forgive_claim_count",
            "dispute_claim_count",
            "renegotiate_claim_count",
            "observed_transfer_count",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        object.__setattr__(self, "coverage", _enum(self.coverage, CreditCoverage))


def infer_credit_layer(row: object) -> CreditAnalysisLayer:
    """Return the strict layer for one detached credit row."""

    if isinstance(row, (CreditClaimEvidenceRow, CreditTransferEvidenceRow)):
        return CreditAnalysisLayer.OBJECTIVE_CLAIM
    if isinstance(row, CreditPerformanceRow):
        return CreditAnalysisLayer.ANALYTICAL_PERFORMANCE
    if isinstance(row, CreditDistributionRow):
        return CreditAnalysisLayer.COMPARISON_VIEW
    return CreditAnalysisLayer.OWNER_CREDIT


@dataclass(frozen=True, slots=True)
class CreditOwnerInput:
    """One detached owner credit export row, peer-token only."""

    owner_token: str
    window_index: int
    anchor_token: str
    counterparty_token: str
    direction: CreditClaimDirection
    principal_kind: str
    principal_quantity: int
    repayment_kind: str
    repayment_quantity: int
    paid_quantity: int
    due_tick: int | None
    condition: str
    collateral_kind: str
    collateral_quantity: int
    status: CreditOwnerStatus
    confidence_milli: int
    level: CreditOwnerLevel
    trust_milli: int
    expectation_milli: int
    claim_count: int
    promise_count: int
    renegotiate_count: int
    first_tick: int
    last_tick: int
    coverage: CreditCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self, "owner_token", _token("owner_token", self.owner_token)
        )
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(
            self, "anchor_token", _token("anchor_token", self.anchor_token)
        )
        if (
            type(self.counterparty_token) is not str
            or not self.counterparty_token.startswith("credpeer-")
            or len(self.counterparty_token) != len("credpeer-") + 16
        ):
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        object.__setattr__(
            self, "direction", _enum(self.direction, CreditClaimDirection)
        )
        for name in ("principal_kind", "repayment_kind"):
            object.__setattr__(self, name, _token(name, getattr(self, name)))
        object.__setattr__(
            self,
            "principal_quantity",
            _positive("principal_quantity", self.principal_quantity),
        )
        object.__setattr__(
            self,
            "repayment_quantity",
            _positive("repayment_quantity", self.repayment_quantity),
        )
        paid = _count("paid_quantity", self.paid_quantity)
        if paid > self.repayment_quantity:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        object.__setattr__(self, "paid_quantity", paid)
        object.__setattr__(self, "due_tick", _optional_tick("due_tick", self.due_tick))
        if self.condition not in CREDIT_CLAIM_CONDITIONS:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        if self.collateral_kind not in CREDIT_COLLATERAL_KINDS:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        if self.collateral_kind in {"item_pledge", "custody_pledge"}:
            if not 1 <= self.collateral_quantity <= 16:
                raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        elif self.collateral_quantity != 0:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        object.__setattr__(
            self,
            "collateral_quantity",
            _count("collateral_quantity", self.collateral_quantity),
        )
        object.__setattr__(self, "status", _enum(self.status, CreditOwnerStatus))
        object.__setattr__(
            self, "level", _enum(self.level, CreditOwnerLevel)
        )
        for name in (
            "confidence_milli",
            "trust_milli",
            "expectation_milli",
        ):
            value = _count(name, getattr(self, name))
            if value > 1_000:
                raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
            object.__setattr__(self, name, value)
        for name in (
            "claim_count",
            "promise_count",
            "renegotiate_count",
            "first_tick",
            "last_tick",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        if self.last_tick < self.first_tick:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        object.__setattr__(self, "coverage", _enum(self.coverage, CreditCoverage))


@dataclass(frozen=True, slots=True)
class AnalyticalCreditRelationshipRow:
    """One analytical projection of an owner credit row."""

    relationship_id: str
    window_index: int
    owner_token: str
    counterparty_token: str
    direction: CreditClaimDirection
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
    status: CreditOwnerStatus
    confidence_milli: int
    expectation_milli: int
    trust_milli: int
    claim_count: int
    renegotiate_count: int
    coverage: CreditCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self,
            "relationship_id",
            _prefixed(self.relationship_id, CREDIT_OWNER_PREFIX),
        )
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        for name in ("owner_token", "anchor_token", "principal_kind", "repayment_kind"):
            object.__setattr__(self, name, _token(name, getattr(self, name)))
        if (
            type(self.counterparty_token) is not str
            or not self.counterparty_token.startswith("credpeer-")
        ):
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        object.__setattr__(
            self, "direction", _enum(self.direction, CreditClaimDirection)
        )
        object.__setattr__(
            self,
            "principal_quantity",
            _positive("principal_quantity", self.principal_quantity),
        )
        object.__setattr__(
            self,
            "repayment_quantity",
            _positive("repayment_quantity", self.repayment_quantity),
        )
        object.__setattr__(
            self,
            "repayment_ratio_milli",
            _count("repayment_ratio_milli", self.repayment_ratio_milli),
        )
        object.__setattr__(self, "due_tick", _optional_tick("due_tick", self.due_tick))
        if self.condition not in CREDIT_CLAIM_CONDITIONS:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        if self.collateral_kind not in CREDIT_COLLATERAL_KINDS:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
        object.__setattr__(
            self,
            "collateral_quantity",
            _count("collateral_quantity", self.collateral_quantity),
        )
        object.__setattr__(self, "status", _enum(self.status, CreditOwnerStatus))
        for name in ("confidence_milli", "expectation_milli", "trust_milli"):
            value = _count(name, getattr(self, name))
            if value > 1_000:
                raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "claim_count", _count("claim_count", self.claim_count))
        object.__setattr__(
            self,
            "renegotiate_count",
            _count("renegotiate_count", self.renegotiate_count),
        )
        object.__setattr__(self, "coverage", _enum(self.coverage, CreditCoverage))


@dataclass(frozen=True, slots=True)
class CreditAlignmentRow:
    """One researcher-only owner-versus-evidence alignment row."""

    alignment_id: str
    window_index: int
    owner_token: str
    anchor_token: str
    alignment: CreditAlignment
    owner_status: CreditOwnerStatus
    analytical_outcome: CreditPerformanceOutcome
    owner_paid_quantity: int
    declared_repayment_quantity: int
    observed_transfer_count: int
    gap_milli: int
    coverage: CreditCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self,
            "alignment_id",
            _prefixed(self.alignment_id, CREDIT_ALIGNMENT_PREFIX),
        )
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        for name in ("owner_token", "anchor_token"):
            object.__setattr__(self, name, _token(name, getattr(self, name)))
        object.__setattr__(
            self, "alignment", _enum(self.alignment, CreditAlignment)
        )
        object.__setattr__(
            self, "owner_status", _enum(self.owner_status, CreditOwnerStatus)
        )
        object.__setattr__(
            self,
            "analytical_outcome",
            _enum(self.analytical_outcome, CreditPerformanceOutcome),
        )
        for name in (
            "owner_paid_quantity",
            "declared_repayment_quantity",
            "observed_transfer_count",
            "gap_milli",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        object.__setattr__(self, "coverage", _enum(self.coverage, CreditCoverage))

