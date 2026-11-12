"""One owner's beliefs about credit terms and repayment.

Nothing here creates a bank, money, enforceable debt, or an objective credit
record. The ledger records what one owner believes about receive-now /
repay-later terms; it never moves an item, collects a debt, or grants a
permission. Physical principal and repayment remain ordinary world commands.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NoReturn

from agents.cognition.emergent_prices import EmergentPriceLedger
from agents.cognition.structured_commitments import (
    CommitmentInterpretation,
    StructuredCommitmentLedger,
)
from agents.models import AgentId
from world.identifiers import EntityId
from world.values import ItemKind

__all__ = [
    "CREDIT_ACCEPT_MIN_WILLINGNESS_MILLI",
    "CREDIT_ANCHOR_PREFIX",
    "CREDIT_CONFIDENCE_MAX_MILLI",
    "CREDIT_DUE_HORIZON_TICKS",
    "CREDIT_FORBIDDEN_FIELD_NAMES",
    "CREDIT_GRACE_TICKS",
    "CREDIT_HEX_LEN",
    "CREDIT_MAX_CLAIMS_PER_ROW",
    "CREDIT_MAX_COLLATERAL_QUANTITY",
    "CREDIT_MAX_COUNTERPARTIES",
    "CREDIT_MAX_NOTICES",
    "CREDIT_MAX_PRINCIPAL_QUANTITY",
    "CREDIT_MAX_REPAYMENT_QUANTITY",
    "CREDIT_MAX_REVISIONS_PER_ROW",
    "CREDIT_MAX_ROWS",
    "CREDIT_NOTICE_CODES",
    "CREDIT_RATIO_MAX_MILLI",
    "CREDIT_RELATIONSHIPS_POLICY_VERSION",
    "CREDIT_RELATIONSHIP_LOCKED_POLICY",
    "CREDIT_REVISION_REASONS",
    "CREDIT_ROW_PREFIX",
    "CREDIT_STALE_AFTER_TICKS",
    "CREDIT_STRONG_MIN_CONFIDENCE_MILLI",
    "CREDIT_WEAK_MAX_CONFIDENCE_MILLI",
    "CreditAct",
    "CreditClaim",
    "CreditClaimSource",
    "CreditCollateralKind",
    "CreditCondition",
    "CreditCounterpartySignal",
    "CreditDirection",
    "CreditExpectationLevel",
    "CreditRelationshipError",
    "CreditRelationshipLedger",
    "CreditRelationshipPolicy",
    "CreditRelationshipRow",
    "CreditRepaymentObservation",
    "CreditStatus",
    "CreditTerms",
    "CreditTermsRevision",
    "apply_credit_relationship_update",
    "credit_anchor",
    "credit_row_id",
    "default_credit_relationship_policy",
    "empty_credit_relationships",
    "require_credit_anchor",
    "require_credit_row_id",
    "require_owner_credit_relationships",
    "validate_credit_relationship_caps",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.credit_relationships"
)

CREDIT_RELATIONSHIPS_POLICY_VERSION: Final[str] = "credit-relationships.v1"
CREDIT_ROW_PREFIX: Final[str] = "cred-"
CREDIT_ANCHOR_PREFIX: Final[str] = "crd-"
CREDIT_HEX_LEN: Final[int] = 16
CREDIT_MAX_ROWS: Final[int] = 32
CREDIT_MAX_CLAIMS_PER_ROW: Final[int] = 16
CREDIT_MAX_REVISIONS_PER_ROW: Final[int] = 8
CREDIT_MAX_COUNTERPARTIES: Final[int] = 8
CREDIT_MAX_NOTICES: Final[int] = 8
CREDIT_MAX_PRINCIPAL_QUANTITY: Final[int] = 16
CREDIT_MAX_REPAYMENT_QUANTITY: Final[int] = 16
CREDIT_MAX_COLLATERAL_QUANTITY: Final[int] = 16
CREDIT_RATIO_MAX_MILLI: Final[int] = 64_000
CREDIT_CONFIDENCE_MAX_MILLI: Final[int] = 1_000
CREDIT_DUE_HORIZON_TICKS: Final[int] = 64
CREDIT_GRACE_TICKS: Final[int] = 8
CREDIT_STALE_AFTER_TICKS: Final[int] = 128
CREDIT_ACCEPT_MIN_WILLINGNESS_MILLI: Final[int] = 500
CREDIT_STRONG_MIN_CONFIDENCE_MILLI: Final[int] = 750
CREDIT_WEAK_MAX_CONFIDENCE_MILLI: Final[int] = 449


class CreditDirection(StrEnum):
    """Owner-relative direction of one credit relationship."""

    OWNER_DEBTOR = "owner_debtor"
    OWNER_CREDITOR = "owner_creditor"


class CreditStatus(StrEnum):
    """Closed owner-local credit status; never an objective obligation."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    OPEN = "open"
    PARTIALLY_REPAID = "partially_repaid"
    REPAID = "repaid"
    DEFAULTED = "defaulted"
    FORGIVEN = "forgiven"
    DISPUTED = "disputed"
    WITHDRAWN = "withdrawn"
    DECLINED = "declined"
    EXPIRED = "expired"


class CreditAct(StrEnum):
    """Closed credit speech acts. Every act is a declaration."""

    PROPOSE = "propose"
    ACCEPT = "accept"
    DECLINE = "decline"
    REPAY = "repay"
    DEFAULT = "default"
    RENEGOTIATE = "renegotiate"
    FORGIVE = "forgive"
    DISPUTE = "dispute"
    WITHDRAW = "withdraw"


class CreditCondition(StrEnum):
    """Closed qualitative repayment condition."""

    ON_RECEIPT = "on_receipt"
    BY_DEADLINE = "by_deadline"
    AFTER_RETURN = "after_return"
    SHARED_WITNESS = "shared_witness"
    UNSPECIFIED = "unspecified"


class CreditCollateralKind(StrEnum):
    """Closed collateral-like claim; never a lien or enforceable security."""

    NONE = "none"
    ITEM_PLEDGE = "item_pledge"
    SERVICE_PLEDGE = "service_pledge"
    CUSTODY_PLEDGE = "custody_pledge"
    REPUTATION_PLEDGE = "reputation_pledge"
    UNSPECIFIED = "unspecified"


class CreditExpectationLevel(StrEnum):
    """Closed qualitative expectation level; never a score or rank."""

    NONE = "none"
    WEAK = "weak"
    EXPECTED = "expected"
    STRONG = "strong"


class CreditClaimSource(StrEnum):
    """Closed provenance of one owner credit claim."""

    SELF_AUTHORED = "self_authored"
    COMMUNICATED = "communicated"


CREDIT_NOTICE_CODES: Final[frozenset[str]] = frozenset(
    {
        "credit_ledger_truncated",
        "credit_terms_unresolved",
        "credit_claim_rejected",
        "credit_terms_mismatch",
        "credit_anchor_ambiguous",
        "credit_frame_malformed",
        "credit_counterparty_unresolved",
        "credit_overdue",
        "credit_repayment_ambiguous",
        "credit_repayment_unmatched",
    }
)

CREDIT_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "bank",
        "banker",
        "loan",
        "interest",
        "interest_rate",
        "apr",
        "credit_score",
        "credit_limit",
        "deposit",
        "reserve",
        "money",
        "currency",
        "legal_tender",
        "collateral_lien",
        "enforcement",
        "collection",
        "allocation",
        "quota",
        "planner",
        "ranking",
        "recommendation",
        "default_probability",
    }
)


class CreditRelationshipError(ValueError):
    """Fail-closed owner credit error; ``args[0]`` is a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "credit_invalid_policy"
        return str(self.args[0])


def _fail(code: str) -> NoReturn:
    _LOG.error("credit_relationship_invalid reason_code=%s", code)
    raise CreditRelationshipError(code)


def _digest16(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:CREDIT_HEX_LEN]


def _reject_forbidden_fields(cls: type[object]) -> None:
    names = set(getattr(cls, "__dataclass_fields__", {}))
    if names & CREDIT_FORBIDDEN_FIELD_NAMES:
        _fail("credit_invalid_policy")


def _require_owner_id(value: object) -> AgentId:
    if type(value) is not AgentId:
        _fail("credit_invalid_identifier")
    return value


def _require_party(value: object) -> str:
    if type(value) is not str or not value:
        _fail("credit_invalid_identifier")
    return value


def _require_item_kind(value: object) -> ItemKind:
    if type(value) is not ItemKind:
        _fail("credit_invalid_terms")
    return value


def _require_tick(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _fail("credit_invalid_identifier")
    return value


def credit_anchor(
    *,
    party_a: str,
    party_b: str,
    principal_kind: ItemKind,
    repayment_kind: ItemKind,
    opened_tick: int,
) -> str:
    """Mint the symmetric ``crd-`` anchor for one credit agreement."""

    first = _require_party(party_a)
    second = _require_party(party_b)
    principal = _require_item_kind(principal_kind)
    repayment = _require_item_kind(repayment_kind)
    tick = _require_tick(opened_tick)
    parties = tuple(sorted((first, second)))
    return CREDIT_ANCHOR_PREFIX + _digest16(
        "|".join(
            (
                parties[0],
                parties[1],
                principal.value,
                repayment.value,
                str(tick),
            )
        )
    )


def require_credit_anchor(value: object) -> str:
    """Validate one exact symmetric ``crd-`` anchor."""

    if (
        type(value) is not str
        or not value.startswith(CREDIT_ANCHOR_PREFIX)
        or len(value) != len(CREDIT_ANCHOR_PREFIX) + CREDIT_HEX_LEN
        or any(
            character not in "0123456789abcdef"
            for character in value[len(CREDIT_ANCHOR_PREFIX) :]
        )
    ):
        _fail("credit_invalid_anchor")
    return value


def credit_row_id(owner_id: AgentId, anchor: str) -> str:
    """Mint one deterministic owner-local ``cred-`` row id."""

    owner = _require_owner_id(owner_id)
    exact_anchor = require_credit_anchor(anchor)
    return CREDIT_ROW_PREFIX + _digest16(owner.value + "|" + exact_anchor)


def require_credit_row_id(value: object) -> str:
    """Validate one exact owner-local ``cred-`` row id."""

    if (
        type(value) is not str
        or not value.startswith(CREDIT_ROW_PREFIX)
        or len(value) != len(CREDIT_ROW_PREFIX) + CREDIT_HEX_LEN
        or any(
            character not in "0123456789abcdef"
            for character in value[len(CREDIT_ROW_PREFIX) :]
        )
    ):
        _fail("credit_invalid_identifier")
    return value


@dataclass(frozen=True, slots=True)
class CreditRelationshipPolicy:
    """Locked owner-local credit bounds and formula constants."""

    max_rows: int = 32
    max_claims_per_row: int = 16
    max_revisions_per_row: int = 8
    max_counterparties: int = 8
    max_notices: int = 8
    due_horizon_ticks: int = 64
    grace_ticks: int = 8
    stale_after_ticks: int = 128
    accept_min_willingness_milli: int = 500
    strong_min_confidence_milli: int = 750
    weak_max_confidence_milli: int = 449
    max_principal_quantity: int = 16
    max_repayment_quantity: int = 16
    max_collateral_quantity: int = 16
    ratio_max_milli: int = 64_000
    confidence_base: int = 200
    confidence_per_own_claim: int = 150
    confidence_per_received_claim: int = 100
    confidence_per_promise: int = 100

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        for name, expected in CREDIT_RELATIONSHIP_LOCKED_POLICY.items():
            actual = getattr(self, name)
            if (
                isinstance(actual, bool)
                or type(actual) is not int
                or actual != expected
            ):
                _fail("credit_invalid_policy")
        if self.weak_max_confidence_milli >= self.strong_min_confidence_milli:
            _fail("credit_invalid_policy")


CREDIT_RELATIONSHIP_LOCKED_POLICY: Final[Mapping[str, int]] = MappingProxyType(
    {
        "max_rows": CREDIT_MAX_ROWS,
        "max_claims_per_row": CREDIT_MAX_CLAIMS_PER_ROW,
        "max_revisions_per_row": CREDIT_MAX_REVISIONS_PER_ROW,
        "max_counterparties": CREDIT_MAX_COUNTERPARTIES,
        "max_notices": CREDIT_MAX_NOTICES,
        "due_horizon_ticks": CREDIT_DUE_HORIZON_TICKS,
        "grace_ticks": CREDIT_GRACE_TICKS,
        "stale_after_ticks": CREDIT_STALE_AFTER_TICKS,
        "accept_min_willingness_milli": CREDIT_ACCEPT_MIN_WILLINGNESS_MILLI,
        "strong_min_confidence_milli": CREDIT_STRONG_MIN_CONFIDENCE_MILLI,
        "weak_max_confidence_milli": CREDIT_WEAK_MAX_CONFIDENCE_MILLI,
        "max_principal_quantity": CREDIT_MAX_PRINCIPAL_QUANTITY,
        "max_repayment_quantity": CREDIT_MAX_REPAYMENT_QUANTITY,
        "max_collateral_quantity": CREDIT_MAX_COLLATERAL_QUANTITY,
        "ratio_max_milli": CREDIT_RATIO_MAX_MILLI,
        "confidence_base": 200,
        "confidence_per_own_claim": 150,
        "confidence_per_received_claim": 100,
        "confidence_per_promise": 100,
    }
)

_DEFAULT_POLICY: Final[CreditRelationshipPolicy] = CreditRelationshipPolicy()


def default_credit_relationship_policy() -> CreditRelationshipPolicy:
    """Return the single locked credit relationship policy instance."""

    return _DEFAULT_POLICY


def _require_ratio(value: object, *, maximum: int, code: str) -> int:
    if isinstance(value, bool) or type(value) is not int or not 0 <= value <= maximum:
        _fail(code)
    return value


def _require_quantity(value: object, *, minimum: int, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or type(value) is not int
        or not minimum <= value <= maximum
    ):
        _fail("credit_invalid_terms")
    return value


def _require_entity(value: object) -> EntityId:
    if type(value) is not EntityId:
        _fail("credit_invalid_identifier")
    return value


def _require_enum(value: object, enum_type: type[StrEnum]) -> StrEnum:
    if type(value) is not enum_type:
        _fail("credit_invalid_enum")
    return value


def _invert(direction: CreditDirection) -> CreditDirection:
    if direction is CreditDirection.OWNER_DEBTOR:
        return CreditDirection.OWNER_CREDITOR
    return CreditDirection.OWNER_DEBTOR


def _claim_key(claim: CreditClaim) -> tuple[str, str, str, int, str]:
    return (
        claim.anchor,
        claim.act.value,
        claim.source.value,
        claim.source_tick,
        claim.counterparty_id.value,
    )


@dataclass(frozen=True, slots=True)
class CreditTerms:
    """Owner-local item-kind terms for one receive-now / repay-later belief."""

    principal_kind: ItemKind
    principal_quantity: int
    repayment_kind: ItemKind
    repayment_quantity: int
    due_tick: int | None
    condition: CreditCondition
    collateral_kind: CreditCollateralKind
    collateral_item_kind: ItemKind | None
    collateral_quantity: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "principal_kind", _require_item_kind(self.principal_kind)
        )
        object.__setattr__(
            self, "repayment_kind", _require_item_kind(self.repayment_kind)
        )
        principal = _require_quantity(
            self.principal_quantity,
            minimum=1,
            maximum=CREDIT_MAX_PRINCIPAL_QUANTITY,
        )
        repayment = _require_quantity(
            self.repayment_quantity,
            minimum=1,
            maximum=CREDIT_MAX_REPAYMENT_QUANTITY,
        )
        if self.due_tick is not None:
            _require_tick(self.due_tick)
        condition = _require_enum(self.condition, CreditCondition)
        collateral = _require_enum(self.collateral_kind, CreditCollateralKind)
        item_kind = self.collateral_item_kind
        if item_kind is not None:
            object.__setattr__(
                self, "collateral_item_kind", _require_item_kind(item_kind)
            )
        quantity = self.collateral_quantity
        if isinstance(quantity, bool) or type(quantity) is not int or quantity < 0:
            _fail("credit_invalid_terms")
        if collateral in {
            CreditCollateralKind.NONE,
            CreditCollateralKind.UNSPECIFIED,
        }:
            if item_kind is not None or quantity != 0:
                _fail("credit_invalid_terms")
        elif collateral in {
            CreditCollateralKind.ITEM_PLEDGE,
            CreditCollateralKind.CUSTODY_PLEDGE,
        }:
            if item_kind is None or not 1 <= quantity <= CREDIT_MAX_COLLATERAL_QUANTITY:
                _fail("credit_invalid_terms")
        else:
            if item_kind is not None or quantity != 0:
                _fail("credit_invalid_terms")
        object.__setattr__(self, "principal_quantity", principal)
        object.__setattr__(self, "repayment_quantity", repayment)
        object.__setattr__(self, "condition", condition)
        object.__setattr__(self, "collateral_kind", collateral)
        object.__setattr__(self, "collateral_quantity", quantity)

    def repayment_ratio_milli(self) -> int:
        """Return the descriptive integer repayment ratio, capped by policy."""

        return min(
            CREDIT_RATIO_MAX_MILLI,
            self.repayment_quantity * CREDIT_CONFIDENCE_MAX_MILLI
            // self.principal_quantity,
        )


CREDIT_REVISION_REASONS: Final[frozenset[str]] = frozenset(
    {"renegotiated", "corrected"}
)


@dataclass(frozen=True, slots=True)
class CreditTermsRevision:
    """One retained earlier-terms entry; never an enforced amendment."""

    tick: int
    terms: CreditTerms
    reason: str

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_tick(self.tick)
        if type(self.terms) is not CreditTerms:
            _fail("credit_invalid_terms")
        if type(self.reason) is not str or self.reason not in CREDIT_REVISION_REASONS:
            _fail("credit_invalid_terms")


@dataclass(frozen=True, slots=True)
class CreditClaim:
    """One owner-authored or received credit claim. Testimony, never a contract."""

    act: CreditAct
    direction: CreditDirection
    anchor: str
    terms: CreditTerms
    paid_quantity: int
    opened_tick: int
    confidence_milli: int
    counterparty_id: EntityId
    source: CreditClaimSource
    source_tick: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        act = _require_enum(self.act, CreditAct)
        _require_enum(self.direction, CreditDirection)
        require_credit_anchor(self.anchor)
        if type(self.terms) is not CreditTerms:
            _fail("credit_invalid_terms")
        paid = _require_quantity(
            self.paid_quantity, minimum=0, maximum=CREDIT_MAX_REPAYMENT_QUANTITY
        )
        if act is not CreditAct.REPAY and paid != 0:
            _fail("credit_invalid_terms")
        _require_tick(self.opened_tick)
        _require_ratio(
            self.confidence_milli,
            maximum=CREDIT_CONFIDENCE_MAX_MILLI,
            code="credit_invalid_confidence",
        )
        _require_entity(self.counterparty_id)
        _require_enum(self.source, CreditClaimSource)
        _require_tick(self.source_tick)
        object.__setattr__(self, "paid_quantity", paid)


@dataclass(frozen=True, slots=True)
class CreditCounterpartySignal:
    """One bounded projection of directed relationship trust."""

    counterparty_id: EntityId
    trust_milli: int
    confidence_milli: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_entity(self.counterparty_id)
        _require_ratio(
            self.trust_milli,
            maximum=CREDIT_CONFIDENCE_MAX_MILLI,
            code="credit_invalid_confidence",
        )
        _require_ratio(
            self.confidence_milli,
            maximum=CREDIT_CONFIDENCE_MAX_MILLI,
            code="credit_invalid_confidence",
        )


@dataclass(frozen=True, slots=True)
class CreditRepaymentObservation:
    """One owner-observed physical transfer offered as repayment evidence."""

    counterparty_id: EntityId
    item_kind: ItemKind
    quantity: int
    tick: int

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_entity(self.counterparty_id)
        object.__setattr__(self, "item_kind", _require_item_kind(self.item_kind))
        _require_quantity(
            self.quantity, minimum=1, maximum=CREDIT_MAX_REPAYMENT_QUANTITY
        )
        _require_tick(self.tick)


@dataclass(frozen=True, slots=True)
class CreditRelationshipRow:
    """One owner's belief about a single credit agreement."""

    anchor: str
    counterparty_id: EntityId
    direction: CreditDirection
    terms: CreditTerms
    status: CreditStatus
    paid_quantity: int
    expectation_milli: int
    trust_milli: int
    trust_confidence_milli: int
    price_confidence_milli: int
    confidence_milli: int
    level: CreditExpectationLevel
    proposed_by_owner: bool
    last_repayment_tick: int | None
    own_claim_count: int
    received_claim_count: int
    promise_count: int
    revisions: tuple[CreditTermsRevision, ...]
    claims: tuple[CreditClaim, ...]
    first_tick: int
    last_tick: int
    row_id: str

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        require_credit_anchor(self.anchor)
        _require_entity(self.counterparty_id)
        _require_enum(self.direction, CreditDirection)
        if type(self.terms) is not CreditTerms:
            _fail("credit_invalid_terms")
        _require_enum(self.status, CreditStatus)
        _require_ratio(
            self.paid_quantity,
            maximum=self.terms.repayment_quantity,
            code="credit_invalid_terms",
        )
        for name in (
            "expectation_milli",
            "trust_milli",
            "trust_confidence_milli",
            "price_confidence_milli",
            "confidence_milli",
        ):
            _require_ratio(
                getattr(self, name),
                maximum=CREDIT_CONFIDENCE_MAX_MILLI,
                code="credit_invalid_confidence",
            )
        _require_enum(self.level, CreditExpectationLevel)
        if type(self.proposed_by_owner) is not bool:
            _fail("credit_invalid_policy")
        if self.last_repayment_tick is not None:
            _require_tick(self.last_repayment_tick)
        for name in ("own_claim_count", "received_claim_count", "promise_count"):
            _require_tick(getattr(self, name))
        if isinstance(self.revisions, (str, bytes)) or not isinstance(
            self.revisions, (list, tuple)
        ):
            _fail("credit_invalid_identifier")
        revisions = tuple(self.revisions)
        if len(revisions) > CREDIT_MAX_REVISIONS_PER_ROW:
            _fail("credit_invalid_policy")
        for revision in revisions:
            if type(revision) is not CreditTermsRevision:
                _fail("credit_invalid_identifier")
        if isinstance(self.claims, (str, bytes)) or not isinstance(
            self.claims, (list, tuple)
        ):
            _fail("credit_invalid_identifier")
        claims = tuple(self.claims)
        if len(claims) > CREDIT_MAX_CLAIMS_PER_ROW:
            _fail("credit_invalid_policy")
        for claim in claims:
            if type(claim) is not CreditClaim:
                _fail("credit_invalid_identifier")
            if claim.anchor != self.anchor:
                _fail("credit_invalid_identifier")
        keys = tuple(_claim_key(claim) for claim in claims)
        if keys != tuple(sorted(set(keys))):
            _fail("credit_invalid_identifier")
        first = _require_tick(self.first_tick)
        last = _require_tick(self.last_tick)
        if last < first:
            _fail("credit_invalid_identifier")
        if self.last_repayment_tick is not None and not (
            first <= self.last_repayment_tick <= last
        ):
            _fail("credit_invalid_identifier")
        object.__setattr__(self, "revisions", revisions)
        object.__setattr__(self, "claims", claims)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(self, "row_id", require_credit_row_id(self.row_id))


def _validate_notices(
    values: object, policy: CreditRelationshipPolicy
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        _fail("credit_invalid_policy")
    items = tuple(values)
    for item in items:
        if type(item) is not str or item not in CREDIT_NOTICE_CODES:
            _fail("credit_invalid_policy")
    return tuple(sorted(set(items))[: policy.max_notices])


@dataclass(frozen=True, slots=True)
class CreditRelationshipLedger:
    """One owner's credit rows. ``None`` means credit mode is off."""

    owner_id: AgentId
    rows: tuple[CreditRelationshipRow, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = CREDIT_RELATIONSHIPS_POLICY_VERSION

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _require_owner_id(self.owner_id)
        if self.policy_version != CREDIT_RELATIONSHIPS_POLICY_VERSION:
            _fail("credit_invalid_policy")
        if isinstance(self.rows, (str, bytes)) or not isinstance(
            self.rows, (list, tuple)
        ):
            _fail("credit_invalid_policy")
        rows = tuple(self.rows)
        if len(rows) > CREDIT_MAX_ROWS:
            _fail("credit_invalid_policy")
        seen: set[str] = set()
        for row in rows:
            if type(row) is not CreditRelationshipRow:
                _fail("credit_invalid_identifier")
            if row.row_id in seen:
                _fail("credit_invalid_identifier")
            if row.row_id != credit_row_id(owner, row.anchor):
                _fail("credit_invalid_identifier")
            seen.add(row.row_id)
        object.__setattr__(self, "owner_id", owner)
        object.__setattr__(self, "rows", rows)
        object.__setattr__(
            self, "notices", _validate_notices(self.notices, _DEFAULT_POLICY)
        )


def empty_credit_relationships(owner_id: AgentId) -> CreditRelationshipLedger:
    """Return an enabled-but-empty credit ledger for one owner."""

    if type(owner_id) is not AgentId:
        _fail("credit_invalid_identifier")
    return CreditRelationshipLedger(owner_id=owner_id)


def require_owner_credit_relationships(
    value: object | None,
    owner_id: AgentId,
    *,
    field_name: str = "credit_relationships",
) -> None:
    """Reject a foreign or mistyped ledger. ``None`` passes."""

    if value is None:
        return
    if type(owner_id) is not AgentId:
        _fail("credit_invalid_identifier")
    if type(value) is not CreditRelationshipLedger:
        _LOG.error(
            "credit_relationship_carry_rejected field=%s reason=invalid_type",
            field_name,
        )
        raise TypeError(f"{field_name} must be CreditRelationshipLedger or None")
    if value.owner_id != owner_id:
        _LOG.error(
            "credit_relationship_carry_rejected field=%s reason=foreign", field_name
        )
        _fail("credit_invalid_identifier")


def validate_credit_relationship_caps(
    ledger: object, policy: object | None = None
) -> None:
    """Validate every policy cap on one ledger; raise on overflow."""

    if type(ledger) is not CreditRelationshipLedger:
        raise TypeError("ledger must be CreditRelationshipLedger")
    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    if len(ledger.rows) > active.max_rows:
        _fail("credit_invalid_policy")
    counterparties = {row.counterparty_id.value for row in ledger.rows}
    if len(counterparties) > active.max_counterparties:
        _fail("credit_invalid_policy")
    for row in ledger.rows:
        if len(row.claims) > active.max_claims_per_row:
            _fail("credit_invalid_policy")
        if len(row.revisions) > active.max_revisions_per_row:
            _fail("credit_invalid_policy")
    if len(ledger.notices) > active.max_notices:
        _fail("credit_invalid_policy")


def _require_policy(value: object) -> CreditRelationshipPolicy:
    if type(value) is not CreditRelationshipPolicy:
        _fail("credit_invalid_policy")
    return value


@dataclass(slots=True)
class _RowState:
    anchor: str
    counterparty_id: EntityId
    direction: CreditDirection
    terms: CreditTerms
    status: CreditStatus
    paid_quantity: int
    proposed_by_owner: bool
    last_repayment_tick: int | None
    own_claim_count: int
    received_claim_count: int
    promise_count: int
    revisions: list[CreditTermsRevision]
    claims: dict[tuple[str, str, str, int, str], CreditClaim]
    first_tick: int
    last_tick: int


def _state_from_row(row: CreditRelationshipRow) -> _RowState:
    return _RowState(
        anchor=row.anchor,
        counterparty_id=row.counterparty_id,
        direction=row.direction,
        terms=row.terms,
        status=row.status,
        paid_quantity=row.paid_quantity,
        proposed_by_owner=row.proposed_by_owner,
        last_repayment_tick=row.last_repayment_tick,
        own_claim_count=row.own_claim_count,
        received_claim_count=row.received_claim_count,
        promise_count=row.promise_count,
        revisions=list(row.revisions),
        claims={_claim_key(claim): claim for claim in row.claims},
        first_tick=row.first_tick,
        last_tick=row.last_tick,
    )


def _touch(state: _RowState, *ticks: int) -> None:
    for value in ticks:
        state.first_tick = min(state.first_tick, value)
        state.last_tick = max(state.last_tick, value)


def _row_id_taken(
    states: Mapping[tuple[str, str], _RowState], owner_id: AgentId, anchor: str
) -> bool:
    candidate = credit_row_id(owner_id, anchor)
    return any(
        credit_row_id(owner_id, state.anchor) == candidate
        for state in states.values()
    )


_TERMINAL_FOR_REPAY: Final[frozenset[CreditStatus]] = frozenset(
    {
        CreditStatus.FORGIVEN,
        CreditStatus.DISPUTED,
        CreditStatus.WITHDRAWN,
        CreditStatus.DECLINED,
    }
)


def _apply_act(
    state: _RowState,
    claim: CreditClaim,
    *,
    tick: int,
    notices: set[str],
) -> None:
    act = claim.act
    if act is CreditAct.PROPOSE:
        if state.terms != claim.terms:
            state.revisions.append(
                CreditTermsRevision(
                    tick=claim.source_tick, terms=claim.terms, reason="corrected"
                )
            )
            if len(state.revisions) > CREDIT_MAX_REVISIONS_PER_ROW:
                del state.revisions[
                    : len(state.revisions) - CREDIT_MAX_REVISIONS_PER_ROW
                ]
                notices.add("credit_ledger_truncated")
        return
    if state.terms != claim.terms and act is not CreditAct.RENEGOTIATE:
        notices.add("credit_terms_mismatch")
        return
    status = state.status
    if act is CreditAct.ACCEPT:
        if status is CreditStatus.PROPOSED:
            state.status = CreditStatus.ACCEPTED
        else:
            notices.add("credit_claim_rejected")
        return
    if act is CreditAct.DECLINE:
        if status is CreditStatus.PROPOSED:
            state.status = CreditStatus.DECLINED
        else:
            notices.add("credit_claim_rejected")
        return
    if act is CreditAct.WITHDRAW:
        if status is CreditStatus.PROPOSED:
            state.status = CreditStatus.WITHDRAWN
        else:
            notices.add("credit_claim_rejected")
        return
    if act is CreditAct.REPAY:
        if status in _TERMINAL_FOR_REPAY:
            notices.add("credit_claim_rejected")
            return
        if claim.paid_quantity == 0:
            return
        state.paid_quantity = min(
            state.terms.repayment_quantity,
            state.paid_quantity + claim.paid_quantity,
        )
        state.last_repayment_tick = tick
        if state.paid_quantity >= state.terms.repayment_quantity:
            state.status = CreditStatus.REPAID
        else:
            state.status = CreditStatus.PARTIALLY_REPAID
        return
    if act is CreditAct.DEFAULT:
        self_declared = claim.direction is CreditDirection.OWNER_DEBTOR
        on_time = state.terms.due_tick is not None and tick >= state.terms.due_tick
        if not (on_time or self_declared):
            notices.add("credit_claim_rejected")
            return
        state.status = CreditStatus.DEFAULTED
        return
    if act is CreditAct.FORGIVE:
        if status is CreditStatus.WITHDRAWN:
            notices.add("credit_claim_rejected")
            return
        state.status = CreditStatus.FORGIVEN
        return
    if act is CreditAct.DISPUTE:
        if status is CreditStatus.WITHDRAWN:
            notices.add("credit_claim_rejected")
            return
        state.status = CreditStatus.DISPUTED
        return
    if act is CreditAct.RENEGOTIATE:
        previous = state.terms
        state.revisions.append(
            CreditTermsRevision(tick=tick, terms=previous, reason="renegotiated")
        )
        if len(state.revisions) > CREDIT_MAX_REVISIONS_PER_ROW:
            del state.revisions[: len(state.revisions) - CREDIT_MAX_REVISIONS_PER_ROW]
            notices.add("credit_ledger_truncated")
        state.terms = claim.terms
        if (
            previous.repayment_kind is not claim.terms.repayment_kind
            or previous.repayment_quantity != claim.terms.repayment_quantity
        ):
            state.paid_quantity = 0
            state.last_repayment_tick = None
        if status is CreditStatus.PROPOSED:
            state.status = CreditStatus.PROPOSED
        elif status in {
            CreditStatus.ACCEPTED,
            CreditStatus.OPEN,
            CreditStatus.PARTIALLY_REPAID,
        }:
            state.status = CreditStatus.OPEN
        return
    notices.add("credit_claim_rejected")


def _terms_from_commitment(
    commitment: CommitmentInterpretation,
) -> tuple[CreditTerms | None, str | None]:
    now_kind = commitment.now_item_kind
    later_kind = commitment.item_kind
    try:
        principal_kind = ItemKind(now_kind)
        repayment_kind = ItemKind(later_kind)
    except ValueError:
        return None, "credit_terms_unresolved"
    quantity = commitment.quantity
    if not 1 <= quantity <= CREDIT_MAX_PRINCIPAL_QUANTITY:
        return None, "credit_terms_unresolved"
    due_tick = commitment.due_tick
    condition = (
        CreditCondition.BY_DEADLINE
        if due_tick is not None
        else CreditCondition.ON_RECEIPT
    )
    return (
        CreditTerms(
            principal_kind=principal_kind,
            principal_quantity=quantity,
            repayment_kind=repayment_kind,
            repayment_quantity=min(quantity, CREDIT_MAX_REPAYMENT_QUANTITY),
            due_tick=due_tick,
            condition=condition,
            collateral_kind=CreditCollateralKind.NONE,
            collateral_item_kind=None,
            collateral_quantity=0,
        ),
        None,
    )


_COMMITMENT_CREDIT_STATUSES: Final[frozenset[str]] = frozenset(
    {"proposed", "accepted", "open", "partial", "fulfilled", "violated", "disputed"}
)


def _price_confidence(
    row: _RowState, prices: EmergentPriceLedger | None
) -> int:
    if prices is None:
        return 500
    values: list[int] = []
    for price_row in prices.rows:
        if price_row.unit_kind is None:
            continue
        pair = (price_row.item_kind, price_row.unit_kind)
        forward = (row.terms.principal_kind, row.terms.repayment_kind)
        reverse = (row.terms.repayment_kind, row.terms.principal_kind)
        if pair == forward or pair == reverse:
            values.append(price_row.confidence_milli)
    return max(values) if values else 500


def apply_credit_relationship_update(
    *,
    owner_id: AgentId,
    tick: int,
    claims: tuple[CreditClaim, ...] = (),
    repayments: tuple[CreditRepaymentObservation, ...] = (),
    prior: CreditRelationshipLedger | None = None,
    commitments: StructuredCommitmentLedger | None = None,
    prices: EmergentPriceLedger | None = None,
    signals: tuple[CreditCounterpartySignal, ...] = (),
    policy: CreditRelationshipPolicy | None = None,
) -> CreditRelationshipLedger:
    """Materialize one owner's credit beliefs from owner-scoped evidence only."""

    owner = _require_owner_id(owner_id)
    current_tick = _require_tick(tick)
    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    if prior is not None:
        if type(prior) is not CreditRelationshipLedger:
            raise TypeError("prior must be CreditRelationshipLedger or None")
        if prior.owner_id != owner:
            _fail("credit_invalid_identifier")
    for _name, values, row_type in (
        ("claims", claims, CreditClaim),
        ("repayments", repayments, CreditRepaymentObservation),
        ("signals", signals, CreditCounterpartySignal),
    ):
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            _fail("credit_invalid_identifier")
        for value in values:
            if type(value) is not row_type:
                _fail("credit_invalid_identifier")
    if commitments is not None:
        if type(commitments) is not StructuredCommitmentLedger:
            raise TypeError("commitments must be StructuredCommitmentLedger or None")
        if commitments.owner_id != owner:
            _fail("credit_invalid_identifier")
    if prices is not None:
        if type(prices) is not EmergentPriceLedger:
            raise TypeError("prices must be EmergentPriceLedger or None")
        if prices.owner_id != owner:
            _fail("credit_invalid_identifier")

    notices: set[str] = set(() if prior is None else prior.notices)
    states: dict[tuple[str, str], _RowState] = {}
    if prior is not None:
        for row in prior.rows:
            states[(row.counterparty_id.value, row.anchor)] = _state_from_row(row)

    for claim in claims:
        direction = (
            claim.direction
            if claim.source is CreditClaimSource.SELF_AUTHORED
            else _invert(claim.direction)
        )
        key = (claim.counterparty_id.value, claim.anchor)
        state = states.get(key)
        if claim.act is CreditAct.PROPOSE:
            expected = credit_anchor(
                party_a=owner.value,
                party_b=claim.counterparty_id.value,
                principal_kind=claim.terms.principal_kind,
                repayment_kind=claim.terms.repayment_kind,
                opened_tick=claim.opened_tick,
            )
            if expected != claim.anchor:
                notices.add("credit_anchor_ambiguous")
                continue
        if state is None:
            if _row_id_taken(states, owner, claim.anchor):
                notices.add("credit_anchor_ambiguous")
                continue
            state = _RowState(
                anchor=claim.anchor,
                counterparty_id=claim.counterparty_id,
                direction=direction,
                terms=claim.terms,
                status=CreditStatus.PROPOSED,
                paid_quantity=0,
                proposed_by_owner=(
                    claim.source is CreditClaimSource.SELF_AUTHORED
                    and claim.act is CreditAct.PROPOSE
                ),
                last_repayment_tick=None,
                own_claim_count=0,
                received_claim_count=0,
                promise_count=0,
                revisions=[],
                claims={},
                first_tick=claim.source_tick,
                last_tick=claim.source_tick,
            )
            states[key] = state
        claim_key = _claim_key(claim)
        if claim_key in state.claims:
            continue
        if len(state.claims) >= active.max_claims_per_row:
            notices.add("credit_ledger_truncated")
            continue
        state.claims[claim_key] = claim
        if claim.source is CreditClaimSource.SELF_AUTHORED:
            state.own_claim_count += 1
        else:
            state.received_claim_count += 1
        if claim.act is CreditAct.PROPOSE and (
            claim.source is CreditClaimSource.SELF_AUTHORED
        ):
            state.proposed_by_owner = True
        _touch(state, claim.opened_tick, claim.source_tick)
        _apply_act(state, claim, tick=current_tick, notices=notices)

    if commitments is not None:
        for commitment in commitments.interpretations:
            if (
                commitment.kind not in {"debt", "future_exchange"}
                or commitment.status not in _COMMITMENT_CREDIT_STATUSES
            ):
                continue
            terms, problem = _terms_from_commitment(commitment)
            if problem is not None or terms is None:
                notices.add(problem or "credit_terms_unresolved")
                continue
            owner_value = owner.value
            if commitment.debtor_id == owner_value:
                counterparty_value = commitment.creditor_id
                direction = CreditDirection.OWNER_DEBTOR
            elif commitment.creditor_id == owner_value:
                counterparty_value = commitment.debtor_id
                direction = CreditDirection.OWNER_CREDITOR
            else:
                notices.add("credit_counterparty_unresolved")
                continue
            if not counterparty_value:
                notices.add("credit_counterparty_unresolved")
                continue
            counterparty = EntityId(counterparty_value)
            anchor = credit_anchor(
                party_a=owner_value,
                party_b=counterparty_value,
                principal_kind=terms.principal_kind,
                repayment_kind=terms.repayment_kind,
                opened_tick=commitment.created_tick,
            )
            key = (counterparty_value, anchor)
            source = (
                CreditClaimSource.SELF_AUTHORED
                if (
                    (
                        direction is CreditDirection.OWNER_DEBTOR
                        and commitment.owed_by == "self"
                    )
                    or (
                        direction is CreditDirection.OWNER_CREDITOR
                        and commitment.owed_by == "counterparty"
                    )
                )
                else CreditClaimSource.COMMUNICATED
            )
            evidence = CreditClaim(
                act=CreditAct.PROPOSE,
                direction=direction,
                anchor=anchor,
                terms=terms,
                paid_quantity=0,
                opened_tick=commitment.created_tick,
                confidence_milli=min(
                    CREDIT_CONFIDENCE_MAX_MILLI,
                    round(commitment.confidence * CREDIT_CONFIDENCE_MAX_MILLI),
                ),
                counterparty_id=counterparty,
                source=source,
                source_tick=commitment.created_tick,
            )
            state = states.get(key)
            if state is None:
                if _row_id_taken(states, owner, anchor):
                    notices.add("credit_anchor_ambiguous")
                    continue
                state = _RowState(
                    anchor=anchor,
                    counterparty_id=counterparty,
                    direction=direction,
                    terms=terms,
                    status=(
                        CreditStatus.PROPOSED
                        if commitment.status == "proposed"
                        else CreditStatus.OPEN
                    ),
                    paid_quantity=0,
                    proposed_by_owner=source is CreditClaimSource.SELF_AUTHORED,
                    last_repayment_tick=None,
                    own_claim_count=0,
                    received_claim_count=0,
                    promise_count=0,
                    revisions=[],
                    claims={},
                    first_tick=commitment.created_tick,
                    last_tick=commitment.created_tick,
                )
                states[key] = state
            evidence_key = _claim_key(evidence)
            if evidence_key in state.claims:
                continue
            if len(state.claims) >= active.max_claims_per_row:
                notices.add("credit_ledger_truncated")
                continue
            state.claims[evidence_key] = evidence
            state.promise_count += 1
            _touch(state, commitment.created_tick)

    for observation in repayments:
        candidates = [
            state
            for state in states.values()
            if state.direction is CreditDirection.OWNER_DEBTOR
            and state.status
            in {
                CreditStatus.ACCEPTED,
                CreditStatus.OPEN,
                CreditStatus.PARTIALLY_REPAID,
            }
            and state.counterparty_id.value == observation.counterparty_id.value
            and state.terms.repayment_kind is observation.item_kind
        ]
        if len(candidates) > 1:
            notices.add("credit_repayment_ambiguous")
            continue
        if not candidates:
            notices.add("credit_repayment_unmatched")
            continue
        state = candidates[0]
        state.paid_quantity = min(
            state.terms.repayment_quantity,
            state.paid_quantity + observation.quantity,
        )
        state.last_repayment_tick = observation.tick
        if state.paid_quantity >= state.terms.repayment_quantity:
            state.status = CreditStatus.REPAID
        else:
            state.status = CreditStatus.PARTIALLY_REPAID
        _touch(state, observation.tick)

    for state in states.values():
        if (
            state.status
            in {
                CreditStatus.ACCEPTED,
                CreditStatus.OPEN,
                CreditStatus.PARTIALLY_REPAID,
            }
            and state.terms.due_tick is not None
            and current_tick > state.terms.due_tick + active.grace_ticks
            and state.paid_quantity < state.terms.repayment_quantity
        ):
            state.status = CreditStatus.EXPIRED
            notices.add("credit_overdue")

    signals_by_party = {signal.counterparty_id.value: signal for signal in signals}
    outcome: dict[str, tuple[int, int]] = {}
    for state in states.values():
        repaid, defaulted = outcome.get(state.counterparty_id.value, (0, 0))
        if state.status is CreditStatus.REPAID:
            repaid += 1
        elif state.status is CreditStatus.DEFAULTED:
            defaulted += 1
        outcome[state.counterparty_id.value] = (repaid, defaulted)

    rows: list[CreditRelationshipRow] = []
    for state in states.values():
        signal = signals_by_party.get(state.counterparty_id.value)
        trust = 500 if signal is None else signal.trust_milli
        trust_confidence = 200 if signal is None else signal.confidence_milli
        price_confidence = _price_confidence(state, prices)
        repaid, defaulted = outcome.get(state.counterparty_id.value, (0, 0))
        history = (
            500
            if repaid + defaulted == 0
            else repaid * CREDIT_CONFIDENCE_MAX_MILLI // (repaid + defaulted)
        )
        willingness = (
            trust * 500 + history * 300 + price_confidence * 200
        ) // CREDIT_CONFIDENCE_MAX_MILLI
        confidence = min(
            CREDIT_CONFIDENCE_MAX_MILLI,
            active.confidence_base
            + active.confidence_per_own_claim * min(4, state.own_claim_count)
            + active.confidence_per_received_claim
            * min(3, state.received_claim_count)
            + active.confidence_per_promise * min(3, state.promise_count),
        )
        if confidence < 450:
            level = CreditExpectationLevel.WEAK
        elif (
            confidence >= active.strong_min_confidence_milli
            and repaid > 0
            and (state.own_claim_count > 0 or state.promise_count > 0)
        ):
            level = CreditExpectationLevel.STRONG
        else:
            level = CreditExpectationLevel.EXPECTED
        claims_sorted = tuple(
            sorted(state.claims.values(), key=lambda claim: _claim_key(claim))
        )
        rows.append(
            CreditRelationshipRow(
                anchor=state.anchor,
                counterparty_id=state.counterparty_id,
                direction=state.direction,
                terms=state.terms,
                status=state.status,
                paid_quantity=state.paid_quantity,
                expectation_milli=willingness,
                trust_milli=trust,
                trust_confidence_milli=trust_confidence,
                price_confidence_milli=price_confidence,
                confidence_milli=confidence,
                level=level,
                proposed_by_owner=state.proposed_by_owner,
                last_repayment_tick=state.last_repayment_tick,
                own_claim_count=state.own_claim_count,
                received_claim_count=state.received_claim_count,
                promise_count=state.promise_count,
                revisions=tuple(state.revisions),
                claims=claims_sorted,
                first_tick=state.first_tick,
                last_tick=state.last_tick,
                row_id=credit_row_id(owner, state.anchor),
            )
        )

    rows.sort(key=lambda row: (row.counterparty_id.value, row.anchor))
    if len(rows) > active.max_rows:
        rows.sort(
            key=lambda row: (row.last_tick, row.counterparty_id.value, row.anchor)
        )
        rows = rows[-active.max_rows :]
        rows.sort(key=lambda row: (row.counterparty_id.value, row.anchor))
        notices.add("credit_ledger_truncated")

    ledger = CreditRelationshipLedger(
        owner_id=owner,
        rows=tuple(rows),
        notices=tuple(sorted(notices)),
        policy_version=CREDIT_RELATIONSHIPS_POLICY_VERSION,
    )
    validate_credit_relationship_caps(ledger, active)
    _LOG.debug(
        "credit_ledger_updated rows=%s claims=%s truncated=%s",
        len(ledger.rows),
        sum(len(row.claims) for row in ledger.rows),
        "credit_ledger_truncated" in ledger.notices,
    )
    return ledger
