"""One owner's beliefs about external accounting-like records.

Nothing here creates an objective ledger, a bank, money, enforceable debt, or
an auditable book of record. A record is an external objective mark; this
module stores only what one owner believes the mark says. Assessments such as
``consistent`` or ``suspected_fraudulent`` are appraisals, never truth,
authenticity, or fraud findings.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, NoReturn, cast

from agents.models import AgentId

__all__ = [
    "ACCOUNTING_ANCHOR_HEX_LEN",
    "ACCOUNTING_CLAIM_SOURCE_CODES",
    "ACCOUNTING_COUNTERPARTY_TOKEN_PREFIX",
    "ACCOUNTING_DIRECTION_CODES",
    "ACCOUNTING_ENTRY_ANCHOR_PREFIX",
    "ACCOUNTING_ENTRY_ID_PREFIX",
    "ACCOUNTING_ENTRY_KIND_CODES",
    "ACCOUNTING_FORBIDDEN_FIELD_NAMES",
    "ACCOUNTING_ITEM_KINDS",
    "ACCOUNTING_LEDGERS_LOCKED_POLICY",
    "ACCOUNTING_LEDGERS_POLICY_VERSION",
    "ACCOUNTING_NOTICE_CODES",
    "ACCOUNTING_ORGANIZATION_TOKEN_PREFIX",
    "ACCOUNTING_PUBLICATION_PREFIX",
    "ACCOUNTING_RECORD_PREDICATE",
    "ACCOUNTING_RECORD_TOKEN_PREFIX",
    "AccountingAct",
    "AccountingClaim",
    "AccountingClaimSource",
    "AccountingDirection",
    "AccountingEntry",
    "AccountingEntryKind",
    "AccountingEntryRevision",
    "AccountingLedger",
    "AccountingLedgerError",
    "AccountingLedgerPolicy",
    "AccountingRecordAssessment",
    "AccountingRecordIntegrity",
    "AccountingRecordObservation",
    "AccountingRecordTerm",
    "AccountingTerms",
    "accounting_counterparty_token",
    "accounting_entry_anchor",
    "accounting_entry_id",
    "accounting_evidence_candidates",
    "accounting_organization_token",
    "accounting_publication_id",
    "accounting_record_token",
    "apply_accounting_ledger_update",
    "default_accounting_ledger_policy",
    "empty_accounting_ledger",
    "encode_accounting_record_relation",
    "parse_accounting_record",
    "parse_accounting_record_relation",
    "require_accounting_anchor",
    "require_accounting_counterparty_token",
    "require_accounting_entry_id",
    "require_accounting_organization_token",
    "require_accounting_publication_id",
    "require_accounting_record_token",
    "require_owner_accounting_ledger",
    "validate_accounting_ledger_caps",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.accounting_ledgers"
)

ACCOUNTING_LEDGERS_POLICY_VERSION: Final[str] = "accounting-ledgers.v1"
ACCOUNTING_RECORD_PREDICATE: Final[str] = "acc_v1"

ACCOUNTING_ENTRY_ANCHOR_PREFIX: Final[str] = "acct-"
ACCOUNTING_ENTRY_ID_PREFIX: Final[str] = "acce-"
ACCOUNTING_RECORD_TOKEN_PREFIX: Final[str] = "accrec-"
ACCOUNTING_ORGANIZATION_TOKEN_PREFIX: Final[str] = "accorg-"
ACCOUNTING_COUNTERPARTY_TOKEN_PREFIX: Final[str] = "accpeer-"
ACCOUNTING_PUBLICATION_PREFIX: Final[str] = "acct-pub-"
ACCOUNTING_ANCHOR_HEX_LEN: Final[int] = 16

_HEX: Final[str] = "0123456789abcdef"
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

_ENTRY_ANCHOR_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{re.escape(ACCOUNTING_ENTRY_ANCHOR_PREFIX)}[0-9a-f]{{{ACCOUNTING_ANCHOR_HEX_LEN}}}$"
)
_ENTRY_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{re.escape(ACCOUNTING_ENTRY_ID_PREFIX)}[0-9a-f]{{{ACCOUNTING_ANCHOR_HEX_LEN}}}$"
)
_RECORD_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{re.escape(ACCOUNTING_RECORD_TOKEN_PREFIX)}[0-9a-f]{{{ACCOUNTING_ANCHOR_HEX_LEN}}}$"
)
_ORGANIZATION_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{re.escape(ACCOUNTING_ORGANIZATION_TOKEN_PREFIX)}[0-9a-f]{{{ACCOUNTING_ANCHOR_HEX_LEN}}}$"
)
_COUNTERPARTY_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{re.escape(ACCOUNTING_COUNTERPARTY_TOKEN_PREFIX)}[0-9a-f]{{{ACCOUNTING_ANCHOR_HEX_LEN}}}$"
)
_PUBLICATION_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{re.escape(ACCOUNTING_PUBLICATION_PREFIX)}[0-9a-f]{{{ACCOUNTING_ANCHOR_HEX_LEN}}}$"
)


class AccountingEntryKind(StrEnum):
    """Closed descriptive record kinds. Never a balance or ownership right."""

    EXCHANGE = "exchange"
    DEBT = "debt"
    INVENTORY = "inventory"
    ORGANIZATIONAL_RESOURCE = "organizational_resource"
    CONTRIBUTION = "contribution"


class AccountingDirection(StrEnum):
    """Closed owner-relative direction of one accounting entry."""

    INFLOW = "inflow"
    OUTFLOW = "outflow"
    HOLDING = "holding"
    RECEIVABLE = "receivable"
    PAYABLE = "payable"
    CONTRIBUTION = "contribution"


class AccountingRecordAssessment(StrEnum):
    """Closed owner appraisal of one external record. Never truth or fraud."""

    UNASSESSED = "unassessed"
    CONSISTENT = "consistent"
    CONTRADICTED = "contradicted"
    OUTDATED = "outdated"
    SUSPECTED_FRAUDULENT = "suspected_fraudulent"
    DAMAGED = "damaged"


class AccountingRecordIntegrity(StrEnum):
    """Observed physical integrity of an external record. Never truth."""

    INTACT = "intact"
    DAMAGED = "damaged"
    PARTIALLY_LOST = "partially_lost"
    UNKNOWN = "unknown"


class AccountingClaimSource(StrEnum):
    """Closed provenance of one owner accounting claim."""

    DIRECT_RECORD = "direct_record"
    COMMUNICATED = "communicated"
    DERIVED = "derived"
    UNKNOWN = "unknown"


class AccountingAct(StrEnum):
    """Closed accounting speech acts. Every act is a declaration."""

    DECLARE_ENTRY = "declare_entry"
    CITE_RECORD = "cite_record"
    AFFIRM_ENTRY = "affirm_entry"
    DISPUTE_ENTRY = "dispute_entry"
    CORRECT_ENTRY = "correct_entry"
    RETRACT_ENTRY = "retract_entry"


ACCOUNTING_ENTRY_KIND_CODES: Final[Mapping[str, AccountingEntryKind]] = (
    MappingProxyType(
        {
            "xch": AccountingEntryKind.EXCHANGE,
            "dbt": AccountingEntryKind.DEBT,
            "inv": AccountingEntryKind.INVENTORY,
            "org": AccountingEntryKind.ORGANIZATIONAL_RESOURCE,
            "ctb": AccountingEntryKind.CONTRIBUTION,
        }
    )
)
ACCOUNTING_DIRECTION_CODES: Final[Mapping[str, AccountingDirection]] = (
    MappingProxyType(
        {
            "in": AccountingDirection.INFLOW,
            "out": AccountingDirection.OUTFLOW,
            "hold": AccountingDirection.HOLDING,
            "recv": AccountingDirection.RECEIVABLE,
            "pay": AccountingDirection.PAYABLE,
            "ctb": AccountingDirection.CONTRIBUTION,
        }
    )
)
ACCOUNTING_ITEM_KINDS: Final[frozenset[str]] = frozenset(
    {"food", "water", "material", "medical", "generic", "tool", "unknown"}
)
ACCOUNTING_CLAIM_SOURCE_CODES: Final[frozenset[str]] = frozenset(
    source.value for source in AccountingClaimSource
)

ACCOUNTING_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "truth",
        "verified",
        "canonical_ledger",
        "audited",
        "objective_balance",
        "book_value",
        "solvent",
        "credit_score",
        "money",
        "currency",
        "price",
        "interest",
        "principal_balance",
        "reconciled",
        "fraud",
        "archive",
        "institution",
        "meaning",
    }
)

_MAX_ENTRIES: Final[int] = 32
_MAX_CLAIMS_PER_ENTRY: Final[int] = 16
_MAX_REVISIONS_PER_ENTRY: Final[int] = 8
_MAX_EVIDENCE_PER_ENTRY: Final[int] = 8
_MAX_NOTICES: Final[int] = 8
_MAX_COUNTERPARTIES: Final[int] = 8
_MAX_QUANTITY: Final[int] = 64
_MAX_VALUATION_MILLI: Final[int] = 64_000
_MAX_CONFIDENCE_MILLI: Final[int] = 1_000
_MAX_RECORD_AGE_TICKS: Final[int] = 128
_MAX_DUE_HORIZON_TICKS: Final[int] = 64
_STRONG_CONFIDENCE_MILLI: Final[int] = 750
_DISPUTED_CONFIDENCE_MILLI: Final[int] = 500
_TRUST_NEUTRAL_MILLI: Final[int] = 500
_COMMUNICATED_CONFIDENCE_PENALTY_MILLI: Final[int] = 200


class AccountingLedgerError(ValueError):
    """Fail-closed owner accounting error; ``args[0]`` is a stable code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "accounting_invalid_policy"
        return str(self.args[0])


def _fail(code: str) -> NoReturn:
    _LOG.error("accounting_ledger_contract_invalid reason_code=%s", code)
    raise AccountingLedgerError(code)


def _digest16(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[
        :ACCOUNTING_ANCHOR_HEX_LEN
    ]


def _require_material(value: object) -> str:
    if type(value) is not str or not value:
        _fail("accounting_invalid_identifier")
    return value


def _require_tick(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _fail("accounting_invalid_identifier")
    return value


def accounting_record_token(artifact_id: str) -> str:
    """Mint one opaque ``accrec-`` token for an observed artifact id."""

    return ACCOUNTING_RECORD_TOKEN_PREFIX + _digest16(_require_material(artifact_id))


def accounting_organization_token(concept_id: str) -> str:
    """Mint one opaque ``accorg-`` token for an owner organization concept."""

    return ACCOUNTING_ORGANIZATION_TOKEN_PREFIX + _digest16(
        _require_material(concept_id)
    )


def accounting_counterparty_token(actor_id: str) -> str:
    """Mint one opaque ``accpeer-`` token for a counterparty id."""

    return ACCOUNTING_COUNTERPARTY_TOKEN_PREFIX + _digest16(
        _require_material(actor_id)
    )


def accounting_entry_anchor(
    *,
    owner_id: object,
    record_token: str,
    entry_kind: AccountingEntryKind,
    ordinal: int,
) -> str:
    """Mint one deterministic owner-local ``acct-`` entry anchor."""

    owner = _require_material(getattr(owner_id, "value", owner_id))
    token = require_accounting_record_token(record_token)
    if type(entry_kind) is not AccountingEntryKind:
        _fail("accounting_invalid_identifier")
    position = _require_tick(ordinal)
    return ACCOUNTING_ENTRY_ANCHOR_PREFIX + _digest16(
        "|".join((owner, token, entry_kind.value, str(position)))
    )


def accounting_entry_id(owner_id: object, anchor: str) -> str:
    """Mint one deterministic owner-local ``acce-`` entry id."""

    owner = _require_material(getattr(owner_id, "value", owner_id))
    exact_anchor = require_accounting_anchor(anchor)
    return ACCOUNTING_ENTRY_ID_PREFIX + _digest16(owner + "|" + exact_anchor)


def accounting_publication_id(material: str) -> str:
    """Mint one deterministic ``acct-pub-`` publication id."""

    return ACCOUNTING_PUBLICATION_PREFIX + _digest16(_require_material(material))


def _require_pattern(
    value: object,
    pattern: re.Pattern[str],
    code: str,
) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        _fail(code)
    return value


def require_accounting_anchor(value: object) -> str:
    """Validate one exact ``acct-`` entry anchor."""

    return _require_pattern(value, _ENTRY_ANCHOR_PATTERN, "accounting_invalid_anchor")


def require_accounting_entry_id(value: object) -> str:
    """Validate one exact owner-local ``acce-`` entry id."""

    return _require_pattern(value, _ENTRY_ID_PATTERN, "accounting_invalid_identifier")


def require_accounting_record_token(value: object) -> str:
    """Validate one exact opaque ``accrec-`` record token."""

    return _require_pattern(
        value, _RECORD_TOKEN_PATTERN, "accounting_invalid_identifier"
    )


def require_accounting_organization_token(value: object) -> str:
    """Validate one exact opaque ``accorg-`` organization token."""

    return _require_pattern(
        value, _ORGANIZATION_TOKEN_PATTERN, "accounting_invalid_identifier"
    )


def require_accounting_counterparty_token(value: object) -> str:
    """Validate one exact opaque ``accpeer-`` counterparty token."""

    return _require_pattern(
        value, _COUNTERPARTY_TOKEN_PATTERN, "accounting_invalid_identifier"
    )


def require_accounting_publication_id(value: object) -> str:
    """Validate one exact ``acct-pub-`` publication id."""

    return _require_pattern(
        value, _PUBLICATION_PATTERN, "accounting_invalid_identifier"
    )


@dataclass(frozen=True, slots=True)
class AccountingLedgerPolicy:
    """Locked owner-local accounting bounds and formula constants."""

    max_entries: int = _MAX_ENTRIES
    max_claims_per_entry: int = _MAX_CLAIMS_PER_ENTRY
    max_revisions_per_entry: int = _MAX_REVISIONS_PER_ENTRY
    max_evidence_per_entry: int = _MAX_EVIDENCE_PER_ENTRY
    max_notices: int = _MAX_NOTICES
    max_counterparties: int = _MAX_COUNTERPARTIES
    max_quantity: int = _MAX_QUANTITY
    max_valuation_milli: int = _MAX_VALUATION_MILLI
    max_confidence_milli: int = _MAX_CONFIDENCE_MILLI
    max_record_age_ticks: int = _MAX_RECORD_AGE_TICKS
    max_due_horizon_ticks: int = _MAX_DUE_HORIZON_TICKS
    strong_confidence_milli: int = _STRONG_CONFIDENCE_MILLI
    disputed_confidence_milli: int = _DISPUTED_CONFIDENCE_MILLI
    trust_neutral_milli: int = _TRUST_NEUTRAL_MILLI
    communicated_confidence_penalty_milli: int = (
        _COMMUNICATED_CONFIDENCE_PENALTY_MILLI
    )

    def __post_init__(self) -> None:
        for name, expected in ACCOUNTING_LEDGERS_LOCKED_POLICY.items():
            actual = getattr(self, name)
            if (
                isinstance(actual, bool)
                or type(actual) is not int
                or actual != expected
            ):
                _fail("accounting_invalid_policy")
        if self.disputed_confidence_milli >= self.strong_confidence_milli:
            _fail("accounting_invalid_policy")


ACCOUNTING_LEDGERS_LOCKED_POLICY: Final[Mapping[str, int]] = MappingProxyType(
    {
        "max_entries": _MAX_ENTRIES,
        "max_claims_per_entry": _MAX_CLAIMS_PER_ENTRY,
        "max_revisions_per_entry": _MAX_REVISIONS_PER_ENTRY,
        "max_evidence_per_entry": _MAX_EVIDENCE_PER_ENTRY,
        "max_notices": _MAX_NOTICES,
        "max_counterparties": _MAX_COUNTERPARTIES,
        "max_quantity": _MAX_QUANTITY,
        "max_valuation_milli": _MAX_VALUATION_MILLI,
        "max_confidence_milli": _MAX_CONFIDENCE_MILLI,
        "max_record_age_ticks": _MAX_RECORD_AGE_TICKS,
        "max_due_horizon_ticks": _MAX_DUE_HORIZON_TICKS,
        "strong_confidence_milli": _STRONG_CONFIDENCE_MILLI,
        "disputed_confidence_milli": _DISPUTED_CONFIDENCE_MILLI,
        "trust_neutral_milli": _TRUST_NEUTRAL_MILLI,
        "communicated_confidence_penalty_milli": (
            _COMMUNICATED_CONFIDENCE_PENALTY_MILLI
        ),
    }
)

_DEFAULT_POLICY: Final[AccountingLedgerPolicy] = AccountingLedgerPolicy()


def default_accounting_ledger_policy() -> AccountingLedgerPolicy:
    """Return the single locked accounting ledger policy instance."""

    return _DEFAULT_POLICY


@dataclass(frozen=True, slots=True)
class AccountingRecordTerm:
    """One decoded ``acc_v1`` relation triple. A claim, never truth."""

    entry_kind: AccountingEntryKind
    direction: AccountingDirection
    item_kind: str
    quantity: int

    def __post_init__(self) -> None:
        if type(self.entry_kind) is not AccountingEntryKind:
            _fail("accounting_record_invalid")
        if type(self.direction) is not AccountingDirection:
            _fail("accounting_record_invalid")
        if self.item_kind not in ACCOUNTING_ITEM_KINDS:
            _fail("accounting_record_invalid")
        if (
            isinstance(self.quantity, bool)
            or type(self.quantity) is not int
            or not 1 <= self.quantity <= _MAX_QUANTITY
        ):
            _fail("accounting_record_invalid")


def _entry_code(entry_kind: AccountingEntryKind) -> str:
    for code, candidate in ACCOUNTING_ENTRY_KIND_CODES.items():
        if candidate is entry_kind:
            return code
    _fail("accounting_record_invalid")
    raise AssertionError("unreachable")


def _direction_code(direction: AccountingDirection) -> str:
    for code, candidate in ACCOUNTING_DIRECTION_CODES.items():
        if candidate is direction:
            return code
    _fail("accounting_record_invalid")
    raise AssertionError("unreachable")


def parse_accounting_record_relation(
    subject: object, object_token: object
) -> AccountingRecordTerm:
    """Decode one ``<entry_code>_<item_kind>`` / ``<direction_code><qty>`` pair."""

    if type(subject) is not str or type(object_token) is not str:
        _fail("accounting_record_invalid")
    if _TOKEN_PATTERN.fullmatch(subject) is None:
        _fail("accounting_record_invalid")
    if _TOKEN_PATTERN.fullmatch(object_token) is None:
        _fail("accounting_record_invalid")
    entry_code, separator, item_kind = subject.partition("_")
    if not separator or item_kind not in ACCOUNTING_ITEM_KINDS:
        _fail("accounting_record_invalid")
    entry_kind = ACCOUNTING_ENTRY_KIND_CODES.get(entry_code)
    if entry_kind is None:
        _fail("accounting_record_invalid")
    direction: AccountingDirection | None = None
    quantity_text = ""
    for code in sorted(
        ACCOUNTING_DIRECTION_CODES, key=len, reverse=True
    ):
        if object_token.startswith(code):
            direction = ACCOUNTING_DIRECTION_CODES[code]
            quantity_text = object_token[len(code) :]
            break
    if direction is None or not quantity_text or not quantity_text.isdigit():
        _fail("accounting_record_invalid")
    quantity = int(quantity_text)
    if not 1 <= quantity <= _MAX_QUANTITY or str(quantity) != quantity_text:
        _fail("accounting_record_invalid")
    return AccountingRecordTerm(
        entry_kind=entry_kind,
        direction=direction,
        item_kind=item_kind,
        quantity=quantity,
    )


def encode_accounting_record_relation(
    entry_kind: AccountingEntryKind,
    direction: AccountingDirection,
    item_kind: str,
    quantity: int,
) -> tuple[str, str]:
    """Encode one validated subject/object pair for an existing artifact mark."""

    term = AccountingRecordTerm(
        entry_kind=entry_kind,
        direction=direction,
        item_kind=item_kind,
        quantity=quantity,
    )
    return (
        f"{_entry_code(term.entry_kind)}_{term.item_kind}",
        f"{_direction_code(term.direction)}{term.quantity}",
    )


_LOG.debug(
    "accounting_ledger_contract_built entries=%s notices=%s",
    _MAX_ENTRIES,
    _MAX_NOTICES,
)


ACCOUNTING_NOTICE_CODES: Final[frozenset[str]] = frozenset(
    {
        "accounting_ledger_truncated",
        "accounting_record_invalid",
        "accounting_record_ambiguous",
        "accounting_claim_rejected",
        "accounting_counterparty_unresolved",
        "accounting_item_unresolved",
        "accounting_evidence_unresolved",
    }
)

ACCOUNTING_REVISION_REASONS: Final[frozenset[str]] = frozenset(
    {
        "declared",
        "corrected",
        "disputed",
        "retracted",
        "affirmed",
        "cited",
        "record_revised",
        "record_disagreement",
        "derived",
    }
)

_ASSESSMENT_SEVERITY: Final[Mapping[AccountingRecordAssessment, int]] = (
    MappingProxyType(
        {
            AccountingRecordAssessment.UNASSESSED: 0,
            AccountingRecordAssessment.CONSISTENT: 1,
            AccountingRecordAssessment.SUSPECTED_FRAUDULENT: 2,
            AccountingRecordAssessment.CONTRADICTED: 3,
            AccountingRecordAssessment.OUTDATED: 4,
            AccountingRecordAssessment.DAMAGED: 5,
        }
    )
)
_ASSESSMENT_BY_SEVERITY: Final[Mapping[int, AccountingRecordAssessment]] = (
    MappingProxyType(
        {severity: assessment for assessment, severity in _ASSESSMENT_SEVERITY.items()}
    )
)


def _reject_forbidden_fields(cls: type[object]) -> None:
    names = set(getattr(cls, "__dataclass_fields__", {}))
    if names & ACCOUNTING_FORBIDDEN_FIELD_NAMES:
        _fail("accounting_invalid_policy")


def _require_owner_id(value: object) -> AgentId:
    if type(value) is not AgentId:
        _fail("accounting_invalid_identifier")
    return value


def _require_enum(value: object, enum_type: type[StrEnum]) -> StrEnum:
    if type(value) is not enum_type:
        _fail("accounting_invalid_enum")
    return value


def _require_bounded_int(
    value: object, *, minimum: int, maximum: int, code: str
) -> int:
    if (
        isinstance(value, bool)
        or type(value) is not int
        or not minimum <= value <= maximum
    ):
        _fail(code)
    return value


def _require_optional_token(
    value: object, validator: Callable[[object], str]
) -> str | None:
    if value is None:
        return None
    return validator(value)


def _item_kind_value(value: object) -> str:
    if type(value) is str and value in ACCOUNTING_ITEM_KINDS:
        return value
    raw = getattr(value, "value", None)
    if type(raw) is str and raw in ACCOUNTING_ITEM_KINDS:
        return raw
    return "unknown"


def _severity(assessment: AccountingRecordAssessment) -> int:
    return _ASSESSMENT_SEVERITY[assessment]


def _raise_severity(
    current: AccountingRecordAssessment, target: AccountingRecordAssessment
) -> AccountingRecordAssessment:
    if _severity(target) > _severity(current):
        return target
    return current


@dataclass(frozen=True, slots=True)
class AccountingTerms:
    """Item-kind terms of one accounting record. Not a balance or valuation."""

    entry_kind: AccountingEntryKind
    direction: AccountingDirection
    item_kind: str
    quantity: int
    valuation_milli: int | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_enum(self.entry_kind, AccountingEntryKind)
        _require_enum(self.direction, AccountingDirection)
        if self.item_kind not in ACCOUNTING_ITEM_KINDS:
            _fail("accounting_invalid_terms")
        _require_bounded_int(
            self.quantity,
            minimum=1,
            maximum=_MAX_QUANTITY,
            code="accounting_invalid_terms",
        )
        if self.valuation_milli is not None:
            _require_bounded_int(
                self.valuation_milli,
                minimum=0,
                maximum=_MAX_VALUATION_MILLI,
                code="accounting_invalid_terms",
            )


@dataclass(frozen=True, slots=True)
class AccountingEntryRevision:
    """One retained earlier accounting belief. Never an enforced amendment."""

    tick: int
    terms: AccountingTerms
    assessment: AccountingRecordAssessment
    reason_code: str

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        _require_tick(self.tick)
        if type(self.terms) is not AccountingTerms:
            _fail("accounting_invalid_terms")
        _require_enum(self.assessment, AccountingRecordAssessment)
        if (
            type(self.reason_code) is not str
            or self.reason_code not in ACCOUNTING_REVISION_REASONS
        ):
            _fail("accounting_invalid_terms")


@dataclass(frozen=True, slots=True)
class AccountingRecordObservation:
    """One owner-observed external durable record. Carries objective marks only."""

    record_token: str
    record_genre: str | None
    integrity: AccountingRecordIntegrity
    content_revision: int
    relations: tuple[tuple[str, str, str], ...]
    tick: int
    ordinal: int = 0

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        require_accounting_record_token(self.record_token)
        if self.record_genre is not None and type(self.record_genre) is not str:
            _fail("accounting_invalid_terms")
        _require_enum(self.integrity, AccountingRecordIntegrity)
        _require_tick(self.content_revision)
        if isinstance(self.relations, (str, bytes)) or not isinstance(
            self.relations, Sequence
        ):
            _fail("accounting_invalid_identifier")
        relations = tuple(self.relations)
        for relation in relations:
            if type(relation) is not tuple or len(relation) != 3:
                _fail("accounting_invalid_identifier")
            if any(type(part) is not str for part in relation):
                _fail("accounting_invalid_identifier")
        _require_tick(self.tick)
        _require_tick(self.ordinal)
        object.__setattr__(self, "relations", relations)


@dataclass(frozen=True, slots=True)
class AccountingClaim:
    """One owner-authored or received accounting claim. Testimony, never truth."""

    anchor: str
    terms: AccountingTerms
    act: AccountingAct
    source: AccountingClaimSource
    confidence_milli: int
    tick: int
    ordinal: int = 0
    record_token: str | None = None
    organization_token: str | None = None
    counterparty_token: str | None = None
    assessment: AccountingRecordAssessment = AccountingRecordAssessment.UNASSESSED
    integrity: AccountingRecordIntegrity = AccountingRecordIntegrity.UNKNOWN

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        require_accounting_anchor(self.anchor)
        if type(self.terms) is not AccountingTerms:
            _fail("accounting_invalid_terms")
        _require_enum(self.act, AccountingAct)
        _require_enum(self.source, AccountingClaimSource)
        _require_bounded_int(
            self.confidence_milli,
            minimum=0,
            maximum=_MAX_CONFIDENCE_MILLI,
            code="accounting_invalid_confidence",
        )
        _require_tick(self.tick)
        _require_tick(self.ordinal)
        _require_optional_token(self.record_token, require_accounting_record_token)
        _require_optional_token(
            self.organization_token, require_accounting_organization_token
        )
        _require_optional_token(
            self.counterparty_token, require_accounting_counterparty_token
        )
        _require_enum(self.assessment, AccountingRecordAssessment)
        _require_enum(self.integrity, AccountingRecordIntegrity)


@dataclass(frozen=True, slots=True)
class AccountingEntry:
    """One owner's belief about one accounting-like external record."""

    entry_id: str
    anchor: str
    record_token: str | None
    record_genre: str | None
    organization_token: str | None
    counterparty_token: str | None
    terms: AccountingTerms
    assessment: AccountingRecordAssessment
    integrity: AccountingRecordIntegrity
    confidence_milli: int
    evidence_refs: tuple[str, ...]
    revisions: tuple[AccountingEntryRevision, ...]
    first_tick: int
    last_tick: int
    source: AccountingClaimSource
    record_content_revision: int = 0
    claims: tuple[AccountingClaim, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(self, "entry_id", require_accounting_entry_id(self.entry_id))
        object.__setattr__(self, "anchor", require_accounting_anchor(self.anchor))
        _require_optional_token(self.record_token, require_accounting_record_token)
        _require_optional_token(
            self.organization_token, require_accounting_organization_token
        )
        _require_optional_token(
            self.counterparty_token, require_accounting_counterparty_token
        )
        if self.record_genre is not None and type(self.record_genre) is not str:
            _fail("accounting_invalid_terms")
        if type(self.terms) is not AccountingTerms:
            _fail("accounting_invalid_terms")
        _require_enum(self.assessment, AccountingRecordAssessment)
        _require_enum(self.integrity, AccountingRecordIntegrity)
        _require_bounded_int(
            self.confidence_milli,
            minimum=0,
            maximum=_MAX_CONFIDENCE_MILLI,
            code="accounting_invalid_confidence",
        )
        _require_enum(self.source, AccountingClaimSource)
        _require_tick(self.first_tick)
        _require_tick(self.last_tick)
        _require_tick(self.record_content_revision)
        if self.last_tick < self.first_tick:
            _fail("accounting_invalid_identifier")
        for name, maximum in (
            ("evidence_refs", _MAX_EVIDENCE_PER_ENTRY),
            ("revisions", _MAX_REVISIONS_PER_ENTRY),
            ("claims", _MAX_CLAIMS_PER_ENTRY),
        ):
            values = getattr(self, name)
            if isinstance(values, (str, bytes)) or not isinstance(
                values, (list, tuple)
            ):
                _fail("accounting_invalid_identifier")
            values = tuple(values)
            if len(values) > maximum:
                _fail("accounting_invalid_policy")
            object.__setattr__(self, name, values)
        for ref in self.evidence_refs:
            if type(ref) is not str or not ref:
                _fail("accounting_invalid_identifier")
        for revision in self.revisions:
            if type(revision) is not AccountingEntryRevision:
                _fail("accounting_invalid_identifier")
        for claim in self.claims:
            if type(claim) is not AccountingClaim or claim.anchor != self.anchor:
                _fail("accounting_invalid_identifier")


def _validate_notices(
    values: object, policy: AccountingLedgerPolicy
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        _fail("accounting_invalid_policy")
    items = tuple(values)
    for item in items:
        if type(item) is not str or item not in ACCOUNTING_NOTICE_CODES:
            _fail("accounting_invalid_policy")
    return tuple(sorted(set(items))[: policy.max_notices])


@dataclass(frozen=True, slots=True)
class AccountingLedger:
    """One owner's accounting entries. ``empty`` means accounting is off."""

    owner_id: AgentId
    entries: tuple[AccountingEntry, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = ACCOUNTING_LEDGERS_POLICY_VERSION
    invalid_tokens: int = 0

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        owner = _require_owner_id(self.owner_id)
        if self.policy_version != ACCOUNTING_LEDGERS_POLICY_VERSION:
            _fail("accounting_invalid_policy")
        if isinstance(self.entries, (str, bytes)) or not isinstance(
            self.entries, (list, tuple)
        ):
            _fail("accounting_invalid_policy")
        entries = tuple(self.entries)
        if len(entries) > _MAX_ENTRIES:
            _fail("accounting_invalid_policy")
        seen: set[str] = set()
        for entry in entries:
            if type(entry) is not AccountingEntry:
                _fail("accounting_invalid_identifier")
            if entry.entry_id in seen:
                _fail("accounting_invalid_identifier")
            if entry.entry_id != accounting_entry_id(owner, entry.anchor):
                _fail("accounting_invalid_identifier")
            seen.add(entry.entry_id)
        invalid = _require_bounded_int(
            self.invalid_tokens,
            minimum=0,
            maximum=1_000_000,
            code="accounting_invalid_policy",
        )
        object.__setattr__(self, "owner_id", owner)
        object.__setattr__(self, "entries", entries)
        object.__setattr__(
            self, "notices", _validate_notices(self.notices, _DEFAULT_POLICY)
        )
        object.__setattr__(self, "invalid_tokens", invalid)


def empty_accounting_ledger(owner_id: object) -> AccountingLedger:
    """Return an enabled-but-empty accounting ledger for one owner."""

    return AccountingLedger(owner_id=_require_owner_id(owner_id))


def require_owner_accounting_ledger(
    value: object | None,
    owner_id: object,
    *,
    field_name: str = "accounting_ledger",
) -> None:
    """Reject a foreign or mistyped ledger. ``None`` passes."""

    if value is None:
        return
    owner = _require_owner_id(owner_id)
    if type(value) is not AccountingLedger:
        _LOG.error(
            "accounting_ledger_carry_rejected field=%s reason=invalid_type",
            field_name,
        )
        raise TypeError(f"{field_name} must be AccountingLedger or None")
    if value.owner_id != owner:
        _LOG.error(
            "accounting_ledger_carry_rejected field=%s reason=foreign", field_name
        )
        _fail("accounting_invalid_identifier")


def validate_accounting_ledger_caps(
    ledger: object, policy: object | None = None
) -> None:
    """Validate every policy cap on one ledger; raise on overflow."""

    if type(ledger) is not AccountingLedger:
        raise TypeError("ledger must be AccountingLedger")
    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    if len(ledger.entries) > active.max_entries:
        _fail("accounting_invalid_policy")
    counterparties = {
        entry.counterparty_token
        for entry in ledger.entries
        if entry.counterparty_token is not None
    }
    if len(counterparties) > active.max_counterparties:
        _fail("accounting_invalid_policy")
    for entry in ledger.entries:
        if len(entry.claims) > active.max_claims_per_entry:
            _fail("accounting_invalid_policy")
        if len(entry.revisions) > active.max_revisions_per_entry:
            _fail("accounting_invalid_policy")
        if len(entry.evidence_refs) > active.max_evidence_per_entry:
            _fail("accounting_invalid_policy")
    if len(ledger.notices) > active.max_notices:
        _fail("accounting_invalid_policy")


def _require_policy(value: object) -> AccountingLedgerPolicy:
    if type(value) is not AccountingLedgerPolicy:
        _fail("accounting_invalid_policy")
    return value


def parse_accounting_record(
    observation: AccountingRecordObservation,
) -> tuple[AccountingTerms, ...]:
    """Decode ``acc_v1`` relation triples. Unknown triples are ignored."""

    if type(observation) is not AccountingRecordObservation:
        raise TypeError("observation must be AccountingRecordObservation")
    if observation.record_genre is None:
        return ()
    terms: list[AccountingTerms] = []
    for subject, predicate, object_token in observation.relations:
        if predicate != ACCOUNTING_RECORD_PREDICATE:
            continue
        try:
            term = parse_accounting_record_relation(subject, object_token)
        except AccountingLedgerError:
            _LOG.warning("accounting_ledger_record_invalid reason=invalid_tokens")
            continue
        terms.append(
            AccountingTerms(
                entry_kind=term.entry_kind,
                direction=term.direction,
                item_kind=term.item_kind,
                quantity=term.quantity,
            )
        )
    return tuple(terms)


@dataclass(slots=True)
class _EntryState:
    anchor: str
    record_token: str | None
    record_genre: str | None
    organization_token: str | None
    counterparty_token: str | None
    terms: AccountingTerms
    assessment: AccountingRecordAssessment
    integrity: AccountingRecordIntegrity
    confidence_milli: int
    evidence_refs: list[str]
    revisions: list[AccountingEntryRevision]
    claims: dict[tuple[object, ...], AccountingClaim]
    first_tick: int
    last_tick: int
    source: AccountingClaimSource
    record_content_revision: int = 0
    retracted: bool = False


def _state_from_entry(entry: AccountingEntry) -> _EntryState:
    return _EntryState(
        anchor=entry.anchor,
        record_token=entry.record_token,
        record_genre=entry.record_genre,
        organization_token=entry.organization_token,
        counterparty_token=entry.counterparty_token,
        terms=entry.terms,
        assessment=entry.assessment,
        integrity=entry.integrity,
        confidence_milli=entry.confidence_milli,
        evidence_refs=list(entry.evidence_refs),
        revisions=list(entry.revisions),
        claims={_claim_key(claim): claim for claim in entry.claims},
        first_tick=entry.first_tick,
        last_tick=entry.last_tick,
        source=entry.source,
        record_content_revision=entry.record_content_revision,
    )


def _claim_key(claim: AccountingClaim) -> tuple[object, ...]:
    return (
        claim.anchor,
        claim.act.value,
        claim.source.value,
        claim.tick,
        claim.ordinal,
        claim.terms.entry_kind.value,
        claim.terms.direction.value,
        claim.terms.item_kind,
        claim.terms.quantity,
        claim.confidence_milli,
    )


def _append_revision(
    state: _EntryState,
    *,
    tick: int,
    terms: AccountingTerms,
    assessment: AccountingRecordAssessment,
    reason_code: str,
    notices: set[str],
    policy: AccountingLedgerPolicy,
) -> None:
    if state.revisions:
        latest = state.revisions[-1]
        if (
            latest.tick == tick
            and latest.terms == terms
            and latest.assessment is assessment
            and latest.reason_code == reason_code
        ):
            return
    state.revisions.append(
        AccountingEntryRevision(
            tick=tick,
            terms=terms,
            assessment=assessment,
            reason_code=reason_code,
        )
    )
    if len(state.revisions) > policy.max_revisions_per_entry:
        del state.revisions[: len(state.revisions) - policy.max_revisions_per_entry]
        notices.add("accounting_ledger_truncated")


def _new_state(
    *,
    owner_id: object,
    anchor: str,
    terms: AccountingTerms,
    tick: int,
    source: AccountingClaimSource,
    record_token: str | None,
    record_genre: str | None,
    organization_token: str | None,
    counterparty_token: str | None,
    integrity: AccountingRecordIntegrity,
    confidence_milli: int,
    record_content_revision: int,
) -> _EntryState:
    return _EntryState(
        anchor=anchor,
        record_token=record_token,
        record_genre=record_genre,
        organization_token=organization_token,
        counterparty_token=counterparty_token,
        terms=terms,
        assessment=AccountingRecordAssessment.UNASSESSED,
        integrity=integrity,
        confidence_milli=confidence_milli,
        evidence_refs=[],
        revisions=[],
        claims={},
        first_tick=tick,
        last_tick=tick,
        source=source,
        record_content_revision=record_content_revision,
    )


def _touch(state: _EntryState, tick: int) -> None:
    state.first_tick = min(state.first_tick, tick)
    state.last_tick = max(state.last_tick, tick)


def _assess(
    state: _EntryState, *, latest_record_revision: Mapping[str, int]
) -> AccountingRecordAssessment:
    assessment = state.assessment
    if state.integrity in {
        AccountingRecordIntegrity.DAMAGED,
        AccountingRecordIntegrity.PARTIALLY_LOST,
    }:
        assessment = _raise_severity(
            assessment, AccountingRecordAssessment.DAMAGED
        )
    token = state.record_token
    if (
        token is not None
        and state.record_content_revision
        < latest_record_revision.get(token, state.record_content_revision)
    ):
        assessment = _raise_severity(
            assessment, AccountingRecordAssessment.OUTDATED
        )
    if state.retracted:
        return assessment
    if assessment is AccountingRecordAssessment.UNASSESSED and (
        state.integrity is AccountingRecordIntegrity.INTACT
    ):
        return AccountingRecordAssessment.CONSISTENT
    return assessment


def _fold_record(
    state: _EntryState | None,
    observation: AccountingRecordObservation,
    terms: AccountingTerms,
    ordinal: int,
    *,
    owner_id: object,
    tick: int,
    notices: set[str],
    policy: AccountingLedgerPolicy,
    latest_record_revision: dict[str, int],
) -> _EntryState:
    token = observation.record_token
    anchor = accounting_entry_anchor(
        owner_id=owner_id,
        record_token=token,
        entry_kind=terms.entry_kind,
        ordinal=ordinal,
    )
    integrity = observation.integrity
    if state is None:
        state = _new_state(
            owner_id=owner_id,
            anchor=anchor,
            terms=terms,
            tick=tick,
            source=AccountingClaimSource.DIRECT_RECORD,
            record_token=token,
            record_genre=observation.record_genre,
            organization_token=None,
            counterparty_token=None,
            integrity=integrity,
            confidence_milli=(
                600
                if integrity is AccountingRecordIntegrity.INTACT
                else 500
            ),
            record_content_revision=observation.content_revision,
        )
        return state
    if state.record_token != token:
        notices.add("accounting_record_ambiguous")
        return state
    if observation.content_revision < state.record_content_revision:
        return state
    if observation.content_revision > state.record_content_revision:
        state.record_content_revision = observation.content_revision
        state.assessment = _raise_severity(
            state.assessment, AccountingRecordAssessment.OUTDATED
        )
    state.integrity = (
        integrity
        if _severity(_assessment_for_integrity(integrity))
        > _severity(_assessment_for_integrity(state.integrity))
        else state.integrity
    )
    if state.terms != terms:
        if observation.content_revision > state.record_content_revision:
            _append_revision(
                state,
                tick=tick,
                terms=state.terms,
                assessment=state.assessment,
                reason_code="record_revised",
                notices=notices,
                policy=policy,
            )
            state.terms = terms
        else:
            state.assessment = _raise_severity(
                state.assessment, AccountingRecordAssessment.SUSPECTED_FRAUDULENT
            )
            _append_revision(
                state,
                tick=tick,
                terms=terms,
                assessment=state.assessment,
                reason_code="record_disagreement",
                notices=notices,
                policy=policy,
            )
    _touch(state, tick)
    return state


def _assessment_for_integrity(
    integrity: AccountingRecordIntegrity,
) -> AccountingRecordAssessment:
    if integrity in {
        AccountingRecordIntegrity.DAMAGED,
        AccountingRecordIntegrity.PARTIALLY_LOST,
    }:
        return AccountingRecordAssessment.DAMAGED
    if integrity is AccountingRecordIntegrity.INTACT:
        return AccountingRecordAssessment.CONSISTENT
    return AccountingRecordAssessment.UNASSESSED


def _fold_claim(
    state: _EntryState | None,
    claim: AccountingClaim,
    *,
    owner_id: object,
    tick: int,
    notices: set[str],
    policy: AccountingLedgerPolicy,
) -> _EntryState | None:
    confidence = claim.confidence_milli
    if claim.source is AccountingClaimSource.COMMUNICATED:
        confidence = max(
            0, confidence - policy.communicated_confidence_penalty_milli
        )
    if state is None:
        if claim.act not in {
            AccountingAct.DECLARE_ENTRY,
            AccountingAct.CORRECT_ENTRY,
            AccountingAct.AFFIRM_ENTRY,
            AccountingAct.CITE_RECORD,
        }:
            notices.add("accounting_claim_rejected")
            return None
        state = _new_state(
            owner_id=owner_id,
            anchor=claim.anchor,
            terms=claim.terms,
            tick=claim.tick,
            source=claim.source,
            record_token=claim.record_token,
            record_genre=None,
            organization_token=claim.organization_token,
            counterparty_token=claim.counterparty_token,
            integrity=claim.integrity,
            confidence_milli=confidence,
            record_content_revision=0,
        )
        if claim.assessment is not AccountingRecordAssessment.UNASSESSED:
            state.assessment = claim.assessment
    key = _claim_key(claim)
    if key in state.claims:
        return state
    if len(state.claims) >= policy.max_claims_per_entry:
        notices.add("accounting_ledger_truncated")
        return state
    state.claims[key] = claim
    _touch(state, claim.tick)

    act = claim.act
    if act is AccountingAct.DECLARE_ENTRY:
        if state.terms != claim.terms:
            _append_revision(
                state,
                tick=claim.tick,
                terms=state.terms,
                assessment=state.assessment,
                reason_code="declared",
                notices=notices,
                policy=policy,
            )
            state.terms = claim.terms
        state.record_token = claim.record_token or state.record_token
        state.record_genre = state.record_genre or None
        state.organization_token = (
            claim.organization_token or state.organization_token
        )
        state.counterparty_token = (
            claim.counterparty_token or state.counterparty_token
        )
        state.source = claim.source
        state.confidence_milli = max(state.confidence_milli, confidence)
    elif act is AccountingAct.AFFIRM_ENTRY:
        state.confidence_milli = min(
            policy.max_confidence_milli, state.confidence_milli + 100
        )
        if state.assessment is AccountingRecordAssessment.UNASSESSED:
            state.assessment = AccountingRecordAssessment.CONSISTENT
    elif act is AccountingAct.CITE_RECORD:
        reference = claim.record_token or claim.anchor
        if reference not in state.evidence_refs:
            if len(state.evidence_refs) >= policy.max_evidence_per_entry:
                notices.add("accounting_ledger_truncated")
            else:
                state.evidence_refs.append(reference)
    elif act is AccountingAct.DISPUTE_ENTRY:
        state.confidence_milli = confidence
        if confidence >= policy.disputed_confidence_milli:
            state.assessment = _raise_severity(
                state.assessment, AccountingRecordAssessment.SUSPECTED_FRAUDULENT
            )
        else:
            _append_revision(
                state,
                tick=claim.tick,
                terms=state.terms,
                assessment=state.assessment,
                reason_code="disputed",
                notices=notices,
                policy=policy,
            )
    elif act is AccountingAct.CORRECT_ENTRY:
        _append_revision(
            state,
            tick=claim.tick,
            terms=state.terms,
            assessment=state.assessment,
            reason_code="corrected",
            notices=notices,
            policy=policy,
        )
        state.terms = claim.terms
        state.assessment = claim.assessment
        state.integrity = claim.integrity
        state.source = claim.source
        state.confidence_milli = confidence
        state.retracted = False
    elif act is AccountingAct.RETRACT_ENTRY:
        _append_revision(
            state,
            tick=claim.tick,
            terms=state.terms,
            assessment=state.assessment,
            reason_code="retracted",
            notices=notices,
            policy=policy,
        )
        state.confidence_milli = 0
        state.retracted = True
    return state


def _anchor_for_derived(
    *,
    owner_id: object,
    material: str,
    entry_kind: AccountingEntryKind,
    ordinal: int,
) -> str:
    record_token = accounting_record_token(material)
    return accounting_entry_anchor(
        owner_id=owner_id,
        record_token=record_token,
        entry_kind=entry_kind,
        ordinal=ordinal,
    )


def _fold_commitments(
    states: dict[str, _EntryState],
    *,
    owner_id: object,
    tick: int,
    commitments: Sequence[object],
    notices: set[str],
    policy: AccountingLedgerPolicy,
) -> None:
    owner_value = str(getattr(owner_id, "value", owner_id))
    for ordinal, commitment in enumerate(commitments):
        debtor = getattr(commitment, "debtor_id", None)
        creditor = getattr(commitment, "creditor_id", None)
        if not debtor or not creditor:
            notices.add("accounting_counterparty_unresolved")
            continue
        if owner_value == debtor:
            counterparty = creditor
            direction = AccountingDirection.PAYABLE
        elif owner_value == creditor:
            counterparty = debtor
            direction = AccountingDirection.RECEIVABLE
        else:
            notices.add("accounting_counterparty_unresolved")
            continue
        item_kind = _item_kind_value(getattr(commitment, "item_kind", None))
        quantity = getattr(commitment, "quantity", 1)
        quantity = (
            quantity
            if isinstance(quantity, int) and not isinstance(quantity, bool)
            else 1
        )
        quantity = max(1, min(policy.max_quantity, quantity))
        due_tick = getattr(commitment, "due_tick", None)
        material = "|".join(
            (
                "commitment",
                owner_value,
                str(counterparty),
                item_kind,
                str(quantity),
                str(due_tick),
            )
        )
        anchor = _anchor_for_derived(
            owner_id=owner_id,
            material=material,
            entry_kind=AccountingEntryKind.DEBT,
            ordinal=ordinal,
        )
        terms = AccountingTerms(
            entry_kind=AccountingEntryKind.DEBT,
            direction=direction,
            item_kind=item_kind,
            quantity=quantity,
        )
        counterparty_token = accounting_counterparty_token(str(counterparty))
        if anchor in states:
            if states[anchor].terms != terms:
                _append_revision(
                    states[anchor],
                    tick=tick,
                    terms=states[anchor].terms,
                    assessment=states[anchor].assessment,
                    reason_code="derived",
                    notices=notices,
                    policy=policy,
                )
                states[anchor].terms = terms
            _touch(states[anchor], tick)
            continue
        states[anchor] = _new_state(
            owner_id=owner_id,
            anchor=anchor,
            terms=terms,
            tick=tick,
            source=AccountingClaimSource.DERIVED,
            record_token=None,
            record_genre=None,
            organization_token=None,
            counterparty_token=counterparty_token,
            integrity=AccountingRecordIntegrity.UNKNOWN,
            confidence_milli=500,
            record_content_revision=0,
        )


def _fold_valuations(
    states: dict[str, _EntryState],
    *,
    valuations: Sequence[object],
    notices: set[str],
    policy: AccountingLedgerPolicy,
) -> None:
    for valuation in valuations:
        item_kind = _item_kind_value(getattr(valuation, "item_kind", None))
        reservation = getattr(valuation, "reservation", None)
        if not isinstance(reservation, (int, float)) or isinstance(
            reservation, bool
        ):
            notices.add("accounting_item_unresolved")
            continue
        milli = round(float(reservation) * 1000.0)
        milli = max(0, min(policy.max_valuation_milli, milli))
        matches = sorted(
            (
                state
                for state in states.values()
                if state.terms.item_kind == item_kind
            ),
            key=lambda state: (state.anchor, state.terms.entry_kind.value),
        )
        if not matches:
            notices.add("accounting_item_unresolved")
            continue
        state = matches[0]
        if state.terms.valuation_milli != milli:
            state.terms = AccountingTerms(
                entry_kind=state.terms.entry_kind,
                direction=state.terms.direction,
                item_kind=state.terms.item_kind,
                quantity=state.terms.quantity,
                valuation_milli=milli,
            )


def _fold_contributions(
    states: dict[str, _EntryState],
    *,
    owner_id: object,
    contributions: Sequence[object],
    notices: set[str],
    policy: AccountingLedgerPolicy,
) -> None:
    owner_value = str(getattr(owner_id, "value", owner_id))
    for ordinal, contribution in enumerate(contributions):
        actor = getattr(contribution, "actor_id", None)
        if not actor or str(actor) != owner_value:
            continue
        item_id = getattr(contribution, "item_id", None)
        contribution_tick = getattr(contribution, "tick", 0)
        if not isinstance(contribution_tick, int) or isinstance(
            contribution_tick, bool
        ):
            contribution_tick = 0
        labor = getattr(contribution, "labor_delta", 1)
        if not isinstance(labor, int) or isinstance(labor, bool) or labor == 0:
            labor = 1
        quantity = max(1, min(policy.max_quantity, abs(labor)))
        material = "|".join(
            ("contribution", owner_value, str(item_id), str(contribution_tick))
        )
        anchor = _anchor_for_derived(
            owner_id=owner_id,
            material=material,
            entry_kind=AccountingEntryKind.CONTRIBUTION,
            ordinal=ordinal,
        )
        terms = AccountingTerms(
            entry_kind=AccountingEntryKind.CONTRIBUTION,
            direction=AccountingDirection.CONTRIBUTION,
            item_kind="generic",
            quantity=quantity,
        )
        if anchor in states:
            if states[anchor].terms.quantity != quantity:
                states[anchor].assessment = _raise_severity(
                    states[anchor].assessment,
                    AccountingRecordAssessment.CONTRADICTED,
                )
            _touch(states[anchor], contribution_tick)
            continue
        states[anchor] = _new_state(
            owner_id=owner_id,
            anchor=anchor,
            terms=terms,
            tick=contribution_tick,
            source=AccountingClaimSource.DERIVED,
            record_token=accounting_record_token(material),
            record_genre=None,
            organization_token=None,
            counterparty_token=None,
            integrity=AccountingRecordIntegrity.UNKNOWN,
            confidence_milli=500,
            record_content_revision=0,
        )


def _fold_organizations(
    states: dict[str, _EntryState],
    *,
    owner_id: object,
    tick: int,
    organizations: Sequence[object],
    notices: set[str],
    policy: AccountingLedgerPolicy,
) -> None:
    ordinal = 0
    for organization in organizations:
        concept_id = getattr(organization, "concept_id", None) or getattr(
            organization, "organization_id", None
        )
        if not concept_id:
            continue
        organization_token = accounting_organization_token(str(concept_id))
        resources = getattr(organization, "resources", ()) or ()
        for resource in resources:
            anchor_id = getattr(resource, "anchor_id", None)
            if not anchor_id:
                continue
            item_kind = _item_kind_value(
                getattr(resource, "resource_kind", None)
            )
            material = "|".join(
                ("organization", str(concept_id), str(anchor_id))
            )
            anchor = _anchor_for_derived(
                owner_id=owner_id,
                material=material,
                entry_kind=AccountingEntryKind.ORGANIZATIONAL_RESOURCE,
                ordinal=ordinal,
            )
            ordinal += 1
            terms = AccountingTerms(
                entry_kind=AccountingEntryKind.ORGANIZATIONAL_RESOURCE,
                direction=AccountingDirection.HOLDING,
                item_kind=item_kind,
                quantity=1,
            )
            if anchor in states:
                states[anchor].organization_token = organization_token
                _touch(states[anchor], tick)
                continue
            states[anchor] = _new_state(
                owner_id=owner_id,
                anchor=anchor,
                terms=terms,
                tick=tick,
                source=AccountingClaimSource.DERIVED,
                record_token=accounting_record_token(material),
                record_genre=None,
                organization_token=organization_token,
                counterparty_token=None,
                integrity=AccountingRecordIntegrity.UNKNOWN,
                confidence_milli=500,
                record_content_revision=0,
            )


def _claim_from_communication(value: object) -> AccountingClaim | None:
    communication = cast(Any, value)
    anchor = getattr(communication, "anchor", None) or getattr(
        communication, "entry_anchor", None
    )
    if not anchor:
        return None
    try:
        return AccountingClaim(
            anchor=anchor,
            terms=communication.terms,
            act=communication.act,
            source=AccountingClaimSource.COMMUNICATED,
            confidence_milli=communication.confidence_milli,
            tick=communication.tick,
            ordinal=getattr(value, "ordinal", 0),
            record_token=getattr(value, "record_token", None),
            organization_token=getattr(value, "organization_token", None),
            counterparty_token=getattr(value, "counterparty_token", None),
            assessment=getattr(
                value, "assessment", AccountingRecordAssessment.UNASSESSED
            ),
            integrity=getattr(
                value, "integrity", AccountingRecordIntegrity.UNKNOWN
            ),
        )
    except (AccountingLedgerError, AttributeError, TypeError):
        return None


def apply_accounting_ledger_update(
    *,
    owner_id: object,
    tick: int,
    records: Sequence[AccountingRecordObservation] = (),
    claims: Sequence[AccountingClaim] = (),
    communications: Sequence[object] = (),
    prior: AccountingLedger | None = None,
    commitments: Sequence[object] | None = None,
    valuations: Sequence[object] | None = None,
    contributions: Sequence[object] = (),
    organizations: Sequence[object] | None = None,
    policy: AccountingLedgerPolicy | None = None,
) -> AccountingLedger:
    """Materialize one owner's accounting beliefs from owner-scoped evidence only."""

    owner = _require_owner_id(owner_id)
    current_tick = _require_tick(tick)
    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    if prior is not None:
        if type(prior) is not AccountingLedger:
            raise TypeError("prior must be AccountingLedger or None")
        if prior.owner_id != owner:
            _fail("accounting_invalid_identifier")
    for values, row_type in (
        (records, AccountingRecordObservation),
        (claims, AccountingClaim),
    ):
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            _fail("accounting_invalid_identifier")
        for value in values:
            if type(value) is not row_type:
                _fail("accounting_invalid_identifier")
    notices: set[str] = set(() if prior is None else prior.notices)
    invalid_tokens = 0 if prior is None else prior.invalid_tokens
    states: dict[str, _EntryState] = {}
    if prior is not None:
        for entry in prior.entries:
            states[entry.anchor] = _state_from_entry(entry)

    latest_record_revision: dict[str, int] = {}
    for observation in records:
        latest_record_revision[observation.record_token] = max(
            latest_record_revision.get(observation.record_token, 0),
            observation.content_revision,
        )

    for observation in records:
        if observation.record_genre is None:
            continue
        try:
            decoded = parse_accounting_record(observation)
        except (AccountingLedgerError, TypeError):
            invalid_tokens += 1
            notices.add("accounting_record_invalid")
            continue
        invalid_count = sum(
            1
            for _subject, predicate, _object in observation.relations
            if predicate == ACCOUNTING_RECORD_PREDICATE
        ) - len(decoded)
        invalid_tokens += max(0, invalid_count)
        if invalid_count:
            notices.add("accounting_record_invalid")
        for ordinal, terms in enumerate(decoded):
            token = observation.record_token
            anchor = accounting_entry_anchor(
                owner_id=owner,
                record_token=token,
                entry_kind=terms.entry_kind,
                ordinal=ordinal,
            )
            existing = states.get(anchor)
            state = _fold_record(
                existing,
                observation,
                terms,
                ordinal,
                owner_id=owner,
                tick=current_tick,
                notices=notices,
                policy=active,
                latest_record_revision=latest_record_revision,
            )
            states[anchor] = state

    for claim in claims:
        try:
            updated = _fold_claim(
                states.get(claim.anchor),
                claim,
                owner_id=owner,
                tick=current_tick,
                notices=notices,
                policy=active,
            )
        except AccountingLedgerError:
            notices.add("accounting_claim_rejected")
            continue
        if updated is not None:
            states[updated.anchor] = updated

    for communication in communications:
        communicated_claim = _claim_from_communication(communication)
        if communicated_claim is None:
            notices.add("accounting_claim_rejected")
            continue
        try:
            updated = _fold_claim(
                states.get(communicated_claim.anchor),
                communicated_claim,
                owner_id=owner,
                tick=current_tick,
                notices=notices,
                policy=active,
            )
        except AccountingLedgerError:
            notices.add("accounting_claim_rejected")
            continue
        if updated is not None:
            states[updated.anchor] = updated

    if commitments:
        _fold_commitments(
            states,
            owner_id=owner,
            tick=current_tick,
            commitments=commitments,
            notices=notices,
            policy=active,
        )
    if valuations:
        _fold_valuations(
            states,
            valuations=valuations,
            notices=notices,
            policy=active,
        )
    if contributions:
        _fold_contributions(
            states,
            owner_id=owner,
            contributions=contributions,
            notices=notices,
            policy=active,
        )
    if organizations:
        _fold_organizations(
            states,
            owner_id=owner,
            tick=current_tick,
            organizations=organizations,
            notices=notices,
            policy=active,
        )

    entries: list[AccountingEntry] = []
    for state in states.values():
        state.assessment = _assess(
            state, latest_record_revision=latest_record_revision
        )
        claims_sorted = tuple(
            sorted(state.claims.values(), key=_claim_key)
        )
        revisions_sorted = tuple(
            sorted(
                state.revisions,
                key=lambda revision: (
                    revision.tick,
                    revision.reason_code,
                    revision.terms.entry_kind.value,
                    revision.terms.direction.value,
                    revision.terms.item_kind,
                    revision.terms.quantity,
                ),
            )
        )
        entries.append(
            AccountingEntry(
                entry_id=accounting_entry_id(owner, state.anchor),
                anchor=state.anchor,
                record_token=state.record_token,
                record_genre=state.record_genre,
                organization_token=state.organization_token,
                counterparty_token=state.counterparty_token,
                terms=state.terms,
                assessment=state.assessment,
                integrity=state.integrity,
                confidence_milli=state.confidence_milli,
                evidence_refs=tuple(sorted(state.evidence_refs)),
                revisions=revisions_sorted,
                first_tick=state.first_tick,
                last_tick=state.last_tick,
                source=state.source,
                record_content_revision=state.record_content_revision,
                claims=claims_sorted,
            )
        )
    entries.sort(key=lambda entry: (entry.anchor, entry.entry_id))
    if len(entries) > active.max_entries:
        entries.sort(
            key=lambda entry: (
                entry.last_tick,
                entry.source.value,
                entry.anchor,
                entry.entry_id,
            )
        )
        entries = entries[-active.max_entries :]
        entries.sort(key=lambda entry: (entry.anchor, entry.entry_id))
        notices.add("accounting_ledger_truncated")
    counterparties = {
        entry.counterparty_token
        for entry in entries
        if entry.counterparty_token is not None
    }
    if len(counterparties) > active.max_counterparties:
        allowed = set(sorted(counterparties)[: active.max_counterparties])
        entries = [
            entry
            for entry in entries
            if entry.counterparty_token is None
            or entry.counterparty_token in allowed
        ]
        notices.add("accounting_ledger_truncated")

    ledger = AccountingLedger(
        owner_id=owner,
        entries=tuple(entries),
        notices=tuple(sorted(notices)),
        policy_version=ACCOUNTING_LEDGERS_POLICY_VERSION,
        invalid_tokens=invalid_tokens,
    )
    validate_accounting_ledger_caps(ledger, active)
    _LOG.debug(
        "accounting_ledger_folded entries=%s claims=%s notices=%s",
        len(ledger.entries),
        sum(len(entry.claims) for entry in ledger.entries),
        len(ledger.notices),
    )
    return ledger


def accounting_evidence_candidates(
    ledger: AccountingLedger,
    *,
    owner_id: object,
    tick: int,
    policy: AccountingLedgerPolicy | None = None,
) -> tuple[object, ...]:
    """Return at most four owner-scoped evidence candidates. Never writes."""

    if type(ledger) is not AccountingLedger:
        raise TypeError("ledger must be AccountingLedger")
    owner = _require_owner_id(owner_id)
    if ledger.owner_id != owner:
        _fail("accounting_invalid_identifier")
    _require_tick(tick)
    active = _DEFAULT_POLICY if policy is None else _require_policy(policy)
    try:
        from agents.cognition.evidence_testimony import (
            EvidenceIntegrityBelief,
            EvidenceObservedReference,
            EvidencePriorAgreement,
            EvidenceReferenceKind,
            EvidenceSourceKind,
            evidence_source_id,
        )
    except ImportError:
        return ()

    def _integrity(value: AccountingRecordIntegrity) -> object:
        if value is AccountingRecordIntegrity.INTACT:
            return EvidenceIntegrityBelief.INTACT
        if value is AccountingRecordIntegrity.DAMAGED:
            return EvidenceIntegrityBelief.DAMAGED
        if value is AccountingRecordIntegrity.PARTIALLY_LOST:
            return EvidenceIntegrityBelief.PARTIALLY_LOST
        return EvidenceIntegrityBelief.UNCERTAIN

    candidates: list[object] = []
    ordered = sorted(
        ledger.entries,
        key=lambda entry: (
            0 if entry.terms.entry_kind is not AccountingEntryKind.DEBT else 1,
            entry.last_tick,
            entry.entry_id,
        ),
        reverse=True,
    )
    for entry in ordered:
        anchor = entry.record_token or entry.organization_token or entry.entry_id
        if entry.terms.entry_kind is AccountingEntryKind.DEBT:
            local_ref = evidence_source_id(
                str(getattr(owner, "value", owner)),
                EvidenceSourceKind.PRIOR_AGREEMENT,
                EvidenceReferenceKind.COMMITMENT,
                entry.entry_id,
                len(candidates),
            )
            party = entry.counterparty_token or "unknown"
            candidates.append(
                EvidencePriorAgreement(
                    local_ref=local_ref,
                    parties=(
                        str(getattr(owner, "value", owner)),
                        party,
                    ),
                    kind="commitment",
                    tick=max(entry.last_tick, tick),
                    confidence=entry.confidence_milli
                    / active.max_confidence_milli,
                    ordinal=len(candidates),
                    owner_id=str(getattr(owner, "value", owner)),
                )
            )
        else:
            reference_kind = (
                EvidenceReferenceKind.ORGANIZATION_RECORD
                if entry.organization_token is not None
                else EvidenceReferenceKind.DURABLE_RECORD
            )
            reference_id = evidence_source_id(
                str(getattr(owner, "value", owner)),
                EvidenceSourceKind.WRITTEN_RECORD,
                reference_kind,
                anchor,
                len(candidates),
            )
            candidates.append(
                EvidenceObservedReference(
                    reference_kind=reference_kind,
                    reference_id=reference_id,
                    tick=max(entry.last_tick, tick),
                    integrity=_integrity(entry.integrity),  # type: ignore[arg-type]
                    correlation_id=entry.record_token,
                    ordinal=len(candidates),
                    owner_id=str(getattr(owner, "value", owner)),
                )
            )
        if len(candidates) >= 4:
            break
    return tuple(candidates)
