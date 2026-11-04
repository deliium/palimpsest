"""Owner-scoped inter-society diplomacy beliefs.

Diplomacy is one owner's belief about recurring contact, envoys, negotiations,
and agreements with another party. It is never a polity, nation, civilization,
border, citizenship, treaty store, treaty authority, bilateral relationship
score, permission, or world capability. This module defines only the frozen
vocabulary, party grammar, identity prefixes, locked policy, scope-coverage
matrix, and error codes that later diplomacy code consumes.

No record or policy field may carry a numeric relationship value, valence,
ranking, or composite. Macro-level relationship evidence is derived by detached
analysis from independent lanes; it never becomes a single bilateral score.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, NoReturn, cast

__all__ = [
    "DIPLOMACY_AGREEMENT_MIN_PARTY_DECLARATIONS",
    "DIPLOMACY_CONFLICT_ID_PREFIX",
    "DIPLOMACY_CONTACT_ID_PREFIX",
    "DIPLOMACY_DECLARATION_ID_PREFIX",
    "DIPLOMACY_ENVOY_ID_PREFIX",
    "DIPLOMACY_ID_HEX_LEN",
    "DIPLOMACY_ID_PREFIXES",
    "DIPLOMACY_INSTRUMENT_ID_PREFIX",
    "DIPLOMACY_MISREPRESENTATION_ID_PREFIX",
    "DIPLOMACY_NEGOTIATION_ID_PREFIX",
    "DIPLOMACY_PARTY_ID_PREFIX",
    "DIPLOMACY_POLICY_VERSION",
    "DIPLOMACY_PUBLICATION_PREFIX",
    "DIPLOMACY_RELATION_ID_PREFIX",
    "DIPLOMACY_SCOPE_COVERAGE",
    "DIPLOMACY_SEPARATOR",
    "DIPLOMACY_TERMINATION_ID_PREFIX",
    "LONG_RUNNING_INSTRUMENT_KINDS",
    "DiplomacyError",
    "DiplomacyLedger",
    "DiplomacyPolicy",
    "DiplomaticAcceptanceBasis",
    "DiplomaticConflict",
    "DiplomaticConflictKind",
    "DiplomaticContact",
    "DiplomaticContactKind",
    "DiplomaticDeclaration",
    "DiplomaticDeclarationAct",
    "DiplomaticEnvoy",
    "DiplomaticEnvoyStatus",
    "DiplomaticInstrument",
    "DiplomaticInstrumentKind",
    "DiplomaticInstrumentStatus",
    "DiplomaticMisrepresentation",
    "DiplomaticMisrepresentationKind",
    "DiplomaticNegotiation",
    "DiplomaticNegotiationStatus",
    "DiplomaticParty",
    "DiplomaticPartyKind",
    "DiplomaticPartyResolution",
    "DiplomaticProvenance",
    "DiplomaticRelation",
    "DiplomaticStandingSummary",
    "DiplomaticTermKind",
    "DiplomaticTermination",
    "DiplomaticTerminationKind",
    "apply_diplomacy_termination",
    "apply_diplomacy_update",
    "assert_diplomacy_no_forbidden_fields",
    "claim_diplomacy_completion",
    "default_diplomacy_policy",
    "detect_diplomacy_conflicts",
    "detect_diplomatic_misrepresentation",
    "diplomacy_conflict_id",
    "diplomacy_contact_id",
    "diplomacy_declaration_id",
    "diplomacy_envoy_id",
    "diplomacy_envoy_status",
    "diplomacy_instrument_id",
    "diplomacy_instrument_status",
    "diplomacy_ledger_digest",
    "diplomacy_misrepresentation_id",
    "diplomacy_negotiation_id",
    "diplomacy_party_id",
    "diplomacy_record_id",
    "diplomacy_relation_id",
    "diplomacy_scope_covers",
    "diplomacy_standing_summary",
    "diplomacy_termination_id",
    "empty_diplomacy_ledger",
    "enforce_diplomacy_limits",
    "expire_diplomacy_records",
    "is_agreement_view",
    "record_diplomacy_utterance",
    "require_diplomacy_id",
    "require_diplomacy_subject",
    "require_diplomacy_token",
    "require_owner_diplomacy",
    "supersede_diplomacy_instruments",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.diplomacy")

DIPLOMACY_POLICY_VERSION: Final[str] = "diplomacy.v1"
DIPLOMACY_ID_HEX_LEN: Final[int] = 16
DIPLOMACY_SEPARATOR: Final[str] = "\x1f"
DIPLOMACY_PUBLICATION_PREFIX: Final[str] = "dip-pub-"
DIPLOMACY_AGREEMENT_MIN_PARTY_DECLARATIONS: Final[int] = 2

DIPLOMACY_RELATION_ID_PREFIX: Final[str] = "dpl-"
DIPLOMACY_PARTY_ID_PREFIX: Final[str] = "dpp-"
DIPLOMACY_CONTACT_ID_PREFIX: Final[str] = "dpc-"
DIPLOMACY_ENVOY_ID_PREFIX: Final[str] = "dpe-"
DIPLOMACY_NEGOTIATION_ID_PREFIX: Final[str] = "dpn-"
DIPLOMACY_INSTRUMENT_ID_PREFIX: Final[str] = "dpi-"
DIPLOMACY_DECLARATION_ID_PREFIX: Final[str] = "dpd-"
DIPLOMACY_MISREPRESENTATION_ID_PREFIX: Final[str] = "dps-"
DIPLOMACY_TERMINATION_ID_PREFIX: Final[str] = "dpt-"
DIPLOMACY_CONFLICT_ID_PREFIX: Final[str] = "dpx-"

DIPLOMACY_ID_PREFIXES: Final[tuple[str, ...]] = (
    DIPLOMACY_RELATION_ID_PREFIX,
    DIPLOMACY_PARTY_ID_PREFIX,
    DIPLOMACY_CONTACT_ID_PREFIX,
    DIPLOMACY_ENVOY_ID_PREFIX,
    DIPLOMACY_NEGOTIATION_ID_PREFIX,
    DIPLOMACY_INSTRUMENT_ID_PREFIX,
    DIPLOMACY_DECLARATION_ID_PREFIX,
    DIPLOMACY_MISREPRESENTATION_ID_PREFIX,
    DIPLOMACY_TERMINATION_ID_PREFIX,
    DIPLOMACY_CONFLICT_ID_PREFIX,
)

_ID_PATTERNS: Final[Mapping[str, re.Pattern[str]]] = MappingProxyType(
    {
        prefix: re.compile(rf"^{prefix}[0-9a-f]{{{DIPLOMACY_ID_HEX_LEN}}}$")
        for prefix in DIPLOMACY_ID_PREFIXES
    }
)
_SUBJECT_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_.:-]{1,32}$")
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]*$")

_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "truth",
        "verified",
        "legitimate",
        "authority",
        "permission",
        "allowed",
        "winner",
        "proxy",
        "binding",
        "treaty",
        "border",
        "citizenship",
        "score",
        "relation_score",
        "rank",
        "trust",
        "index",
        "composite",
        "overall_relation",
    }
)


class DiplomaticPartyKind(StrEnum):
    """Closed party kinds. None creates an objective collective or polity."""

    AGENT = "agent"
    ORGANIZATION = "organization"
    SETTLEMENT = "settlement"
    COALITION = "coalition"
    UNKNOWN = "unknown"


class DiplomaticPartyResolution(StrEnum):
    """Closed party-anchor resolution. Unresolved is legal and retained."""

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    UNKNOWN = "unknown"


class DiplomaticContactKind(StrEnum):
    """Closed contact channels. A report resolves nothing by itself."""

    DIRECT_CO_PRESENCE = "direct_co_presence"
    MEDIATED_MESSAGE = "mediated_message"
    WRITTEN_RECORD = "written_record"
    THIRD_PARTY_REPORT = "third_party_report"
    JOURNEY_PRESENCE = "journey_presence"
    UNKNOWN = "unknown"


class DiplomaticEnvoyStatus(StrEnum):
    """Closed envoy standing. Recognition is derived, never granted."""

    CLAIMED = "claimed"
    RECOGNIZED = "recognized"
    CONTESTED = "contested"
    REJECTED = "rejected"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


class DiplomaticNegotiationStatus(StrEnum):
    """Closed negotiation lifecycle beliefs."""

    OPENED = "opened"
    ONGOING = "ongoing"
    STALLED = "stalled"
    CLOSED = "closed"
    ABANDONED = "abandoned"
    UNKNOWN = "unknown"


class DiplomaticInstrumentKind(StrEnum):
    """Closed instrument kinds. No kind is binding authority."""

    PROPOSAL = "proposal"
    PROMISE = "promise"
    AGREEMENT = "agreement"
    DISPUTE = "dispute"
    SHARED_PROJECT = "shared_project"
    UNKNOWN = "unknown"


class DiplomaticInstrumentStatus(StrEnum):
    """Closed instrument statuses. Acceptance binds nobody."""

    PROPOSED = "proposed"
    OPEN = "open"
    APPARENTLY_ACCEPTED = "apparently_accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    UNRESOLVED = "unresolved"
    ACTIVE = "active"
    COMPLETED_CLAIMED = "completed_claimed"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class DiplomaticTermKind(StrEnum):
    """Closed term categories. A term is a belief, not an obligation."""

    MATERIAL_EXCHANGE = "material_exchange"
    SHARED_WORK = "shared_work"
    PASSAGE = "passage"
    RECOGNITION = "recognition"
    PROCEDURE = "procedure"
    UNKNOWN = "unknown"


class DiplomaticProvenance(StrEnum):
    """Closed provenance channel for one retained belief row."""

    SELF_DECLARED = "self_declared"
    PRINCIPAL_DECLARED = "principal_declared"
    COMMUNICATED = "communicated"
    WITNESSED_CONTACT = "witnessed_contact"
    WRITTEN_RECORD = "written_record"
    REPRESENTATION_BELIEF = "representation_belief"
    COLLECTIVE_DECISION = "collective_decision"
    UNKNOWN = "unknown"


class DiplomaticTerminationKind(StrEnum):
    """Closed termination kinds. History is appended, never deleted."""

    PARTY_WITHDREW = "party_withdrew"
    ENVOY_RECALLED = "envoy_recalled"
    ENVOY_RESIGNED = "envoy_resigned"
    AGREEMENT_DISPUTED = "agreement_disputed"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class DiplomaticMisrepresentationKind(StrEnum):
    """Closed misrepresentation observations. Never truth or guilt findings."""

    MANDATE_UNRECOGNIZED = "mandate_unrecognized"
    SCOPE_EXCEEDED = "scope_exceeded"
    CONTRADICTED_BY_PRINCIPAL = "contradicted_by_principal"
    CONTESTED_BY_MEMBER = "contested_by_member"
    UNKNOWN = "unknown"


class DiplomaticConflictKind(StrEnum):
    """Closed conflict kinds. Conflicts coexist and are never reconciled."""

    DUPLICATE_ENVOY = "duplicate_envoy"
    CONTRADICTORY_TERMS = "contradictory_terms"
    CONFLICTING_PARTY = "conflicting_party"
    AGREEMENT_DISPUTE = "agreement_dispute"
    UNKNOWN = "unknown"


DIPLOMACY_SCOPE_COVERAGE: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "contact": frozenset({"speak_for", "carry_message"}),
        "report": frozenset({"speak_for", "carry_message"}),
        "negotiate": frozenset({"negotiate"}),
        "proposal": frozenset({"negotiate", "speak_for"}),
        "agreement": frozenset({"negotiate", "decide"}),
        "promise": frozenset({"speak_for", "negotiate"}),
        "dispute": frozenset({"speak_for", "negotiate"}),
        "shared_project": frozenset({"coordinate_project"}),
    }
)

LONG_RUNNING_INSTRUMENT_KINDS: Final[frozenset[str]] = frozenset(
    {"agreement", "promise", "shared_project"}
)

_DIPLOMACY_POLICY_VALUES: Final[Mapping[str, int]] = MappingProxyType(
    {
        "agreement_min_party_declarations": 2,
        "max_relations": 24,
        "max_parties": 32,
        "max_contacts_per_relation": 16,
        "max_envoys_per_relation": 8,
        "max_negotiations_per_relation": 8,
        "max_instruments_per_relation": 24,
        "max_declarations_per_instrument": 16,
        "max_anchor_refs": 8,
        "max_total_records": 320,
        "max_frame_chars": 320,
    }
)


@dataclass(frozen=True, slots=True)
class DiplomacyPolicy:
    """Locked owner-local diplomacy bounds.

    Every value is part of the accepted contract. Any deviation is a programming
    error and fails closed with ``diplomacy_policy_not_locked``.
    """

    agreement_min_party_declarations: int = 2
    max_relations: int = 24
    max_parties: int = 32
    max_contacts_per_relation: int = 16
    max_envoys_per_relation: int = 8
    max_negotiations_per_relation: int = 8
    max_instruments_per_relation: int = 24
    max_declarations_per_instrument: int = 16
    max_anchor_refs: int = 8
    max_total_records: int = 320
    max_frame_chars: int = 320

    def __post_init__(self) -> None:
        for field in fields(type(self)):
            if field.name in _FORBIDDEN_FIELD_NAMES:
                raise DiplomacyError("diplomacy_policy_not_locked")
            expected = _DIPLOMACY_POLICY_VALUES[field.name]
            actual = getattr(self, field.name)
            if type(actual) is not type(expected) or actual != expected:
                raise DiplomacyError("diplomacy_policy_not_locked")


def default_diplomacy_policy() -> DiplomacyPolicy:
    """Return the one locked policy value."""

    _LOG.debug("diplomacy_policy_loaded version=%s", DIPLOMACY_POLICY_VERSION)
    return DiplomacyPolicy()


class DiplomacyError(ValueError):
    """Stable-code diplomacy violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    raise DiplomacyError(code)


def _digest(*parts: object) -> str:
    payload = DIPLOMACY_SEPARATOR.join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:DIPLOMACY_ID_HEX_LEN]


def _enum_text(value: object) -> str:
    if isinstance(value, StrEnum):
        return value.value
    if type(value) is str:
        return value
    return ""


def assert_diplomacy_no_forbidden_fields(names: Sequence[str]) -> None:
    """Reject any field name that would smuggle truth, authority, or a score."""

    if any(name in _FORBIDDEN_FIELD_NAMES for name in names):
        _fail("diplomacy_forbidden_field")


def require_diplomacy_id(value: object, prefix: str) -> str:
    """Validate one owner-local record id against its closed prefix."""

    pattern = _ID_PATTERNS.get(prefix)
    if pattern is None:
        _fail("diplomacy_invalid_id")
    if type(value) is not str or pattern.match(value) is None:
        _fail("diplomacy_invalid_id")
    return value


def require_diplomacy_token(value: object, *, max_chars: int) -> str:
    """Validate one bounded opaque token. Never free text."""

    if (
        type(value) is not str
        or not value
        or len(value) > max_chars
        or value != value.strip()
        or _TOKEN_PATTERN.match(value) is None
    ):
        _fail("diplomacy_untrusted_token")
    return value


def require_diplomacy_subject(value: object) -> str:
    """Validate a lowercase bounded topic subject. ``none`` is reserved."""

    if (
        type(value) is not str
        or _SUBJECT_PATTERN.match(value) is None
        or value == "none"
    ):
        _fail("diplomacy_invalid_subject")
    return value


def diplomacy_record_id(prefix: str, *parts: object) -> str:
    """Mint a deterministic owner-local diplomacy record id from evidence."""

    if type(prefix) is not str or prefix not in _ID_PATTERNS:
        _fail("diplomacy_invalid_id")
    return prefix + _digest("palimpsest.diplomacy.record.v1", prefix, *parts)


def diplomacy_scope_covers(
    *,
    scope_kind: object,
    duration_kind: object,
    instrument_kind: object,
    scope_subject: object,
    topic_subject: object,
) -> bool:
    """Decide whether one mandate belief covers one instrument kind.

    This is a belief consistency check, never a permission or legitimacy
    finding. ``single_act`` and ``occasion`` never cover a long-running
    instrument, and a named scope subject must match the instrument subject.
    """

    instrument = _enum_text(instrument_kind)
    scope = _enum_text(scope_kind)
    duration = _enum_text(duration_kind)
    allowed = DIPLOMACY_SCOPE_COVERAGE.get(instrument)
    if allowed is None or scope not in allowed:
        return False
    if instrument in LONG_RUNNING_INSTRUMENT_KINDS and duration in {
        "single_act",
        "occasion",
    }:
        return False
    if scope_subject is not None:
        return type(topic_subject) is str and topic_subject == scope_subject
    return True


class DiplomaticDeclarationAct(StrEnum):
    """Closed declaration acts. A declaration is a claim, never a finding."""

    PROPOSE = "propose"
    ACCEPT = "accept"
    REJECT = "reject"
    WITHDRAW = "withdraw"
    PROMISE = "promise"
    DISPUTE = "dispute"
    SHARED_PROJECT = "shared_project"
    REPORT = "report"


class DiplomaticAcceptanceBasis(StrEnum):
    """Diagnostic acceptance basis. Never a legitimacy verdict."""

    ALL_PARTIES_DECLARED = "all_parties_declared"
    OPENER_ONLY = "opener_only"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    DISPUTED = "disputed"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    NONE = "none"
    UNKNOWN = "unknown"


_DECLARATION_ACTS_BY_INSTRUMENT: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "proposal": frozenset({"propose", "accept", "reject", "withdraw", "report"}),
        "agreement": frozenset({"propose", "accept", "reject", "withdraw", "report"}),
        "promise": frozenset({"promise", "withdraw", "report"}),
        "dispute": frozenset({"dispute", "withdraw", "report"}),
        "shared_project": frozenset({"shared_project", "accept", "withdraw", "report"}),
    }
)
_TERMINATION_KINDS_BY_TARGET: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "instrument": frozenset(
            {"party_withdrew", "agreement_disputed", "superseded", "expired"}
        ),
        "envoy": frozenset(
            {"envoy_recalled", "envoy_resigned", "superseded", "expired"}
        ),
        "relation": frozenset({"party_withdrew"}),
    }
)
_COMPLETION_CLAIM_MARKER: Final[str] = "completion_claim"
_TICK_CODE: Final[str] = "diplomacy_invalid_tick"
_RECORD_CODE: Final[str] = "diplomacy_invalid_record"


def _require_enum(value: object, enum_type: type[StrEnum], code: str) -> StrEnum:
    if type(value) is not enum_type:
        _fail(code)
    return value


def _require_tick(value: object, code: str = _TICK_CODE) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        _fail(code)
    return value


def _owner_text(owner_id: object) -> str:
    owner = getattr(owner_id, "value", owner_id)
    if type(owner) is not str or not owner:
        _fail("diplomacy_owner_mismatch")
    return owner


def _require_tokens(
    values: object, *, max_items: int, max_chars: int = 128, code: str = _RECORD_CODE
) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        _fail(code)
    rows = tuple(values)
    if len(rows) > max_items:
        _fail(code)
    result: list[str] = []
    for value in rows:
        result.append(require_diplomacy_token(value, max_chars=max_chars))
    if len(set(result)) != len(result):
        _fail(code)
    return tuple(result)


def _require_optional_token(value: object, *, code: str = _RECORD_CODE) -> str | None:
    if value is None:
        return None
    try:
        return require_diplomacy_token(value, max_chars=128)
    except DiplomacyError:
        _fail(code)


def _require_rows(
    rows: object, row_type: type, code: str = _RECORD_CODE
) -> tuple[Any, ...]:
    if not isinstance(rows, (tuple, list)):
        _fail(code)
    values = tuple(rows)
    for row in values:
        if type(row) is not row_type:
            _fail(code)
    return values


def _require_ordered(rows: Sequence[Any], *, tick_name: str, id_name: str) -> None:
    keys = [(getattr(row, tick_name), getattr(row, id_name)) for row in rows]
    if keys != sorted(keys):
        _fail("diplomacy_unordered_rows")
    ids = [getattr(row, id_name) for row in rows]
    if len(set(ids)) != len(ids):
        _fail("diplomacy_duplicate_id")


def _check_no_forbidden(row: object) -> None:
    assert_diplomacy_no_forbidden_fields(
        [field.name for field in fields(cast(Any, type(row)))]
    )


@dataclass(frozen=True, slots=True)
class DiplomaticRelation:
    """Retained anchor for one long-running relation. Never a score."""

    relation_id: str
    party_ids: tuple[str, ...]
    opened_tick: int
    last_tick: int
    provenance: DiplomaticProvenance

    def __post_init__(self) -> None:
        _check_no_forbidden(self)
        require_diplomacy_id(self.relation_id, DIPLOMACY_RELATION_ID_PREFIX)
        parties = _require_tokens(self.party_ids, max_items=32, code=_RECORD_CODE)
        if len(parties) < 2:
            _fail("diplomacy_party_set_invalid")
        opened = _require_tick(self.opened_tick)
        last = _require_tick(self.last_tick)
        if last < opened:
            _fail(_RECORD_CODE)
        _require_enum(self.provenance, DiplomaticProvenance, _RECORD_CODE)


@dataclass(frozen=True, slots=True)
class DiplomaticParty:
    """Owner-local party anchor with a closed kind and resolution belief."""

    party_id: str
    kind: DiplomaticPartyKind
    anchor_ref: str | None
    resolution: DiplomaticPartyResolution
    first_seen_tick: int
    provenance: DiplomaticProvenance

    def __post_init__(self) -> None:
        _check_no_forbidden(self)
        require_diplomacy_id(self.party_id, DIPLOMACY_PARTY_ID_PREFIX)
        kind = _require_enum(self.kind, DiplomaticPartyKind, _RECORD_CODE)
        _require_enum(self.resolution, DiplomaticPartyResolution, _RECORD_CODE)
        _require_enum(self.provenance, DiplomaticProvenance, _RECORD_CODE)
        _require_tick(self.first_seen_tick)
        anchor = _require_optional_token(self.anchor_ref)
        object.__setattr__(self, "anchor_ref", anchor)
        if kind is DiplomaticPartyKind.UNKNOWN and anchor is not None:
            _fail("diplomacy_party_set_invalid")


@dataclass(frozen=True, slots=True)
class DiplomaticContact:
    """One retained contact episode. Co-presence is evidence, not truth."""

    contact_id: str
    relation_id: str
    tick: int
    contact_kind: DiplomaticContactKind
    location_anchor: str | None
    participant_count: int
    provenance: DiplomaticProvenance
    source_ref: str | None

    def __post_init__(self) -> None:
        _check_no_forbidden(self)
        require_diplomacy_id(self.contact_id, DIPLOMACY_CONTACT_ID_PREFIX)
        require_diplomacy_id(self.relation_id, DIPLOMACY_RELATION_ID_PREFIX)
        _require_tick(self.tick)
        _require_enum(self.contact_kind, DiplomaticContactKind, _RECORD_CODE)
        _require_enum(self.provenance, DiplomaticProvenance, _RECORD_CODE)
        object.__setattr__(
            self, "location_anchor", _require_optional_token(self.location_anchor)
        )
        object.__setattr__(self, "source_ref", _require_optional_token(self.source_ref))
        if (
            type(self.participant_count) is not int
            or isinstance(self.participant_count, bool)
            or self.participant_count < 1
        ):
            _fail("diplomacy_invalid_participant_count")


@dataclass(frozen=True, slots=True)
class DiplomaticEnvoy:
    """Accreditation-time envoy belief. ``status`` is never current standing."""

    envoy_id: str
    relation_id: str
    party_id: str
    envoy_ref: str
    mandate_ref: str | None
    status: DiplomaticEnvoyStatus
    accredited_tick: int
    end_tick: int | None
    revision: int
    provenance: DiplomaticProvenance

    def __post_init__(self) -> None:
        _check_no_forbidden(self)
        require_diplomacy_id(self.envoy_id, DIPLOMACY_ENVOY_ID_PREFIX)
        require_diplomacy_id(self.relation_id, DIPLOMACY_RELATION_ID_PREFIX)
        require_diplomacy_id(self.party_id, DIPLOMACY_PARTY_ID_PREFIX)
        object.__setattr__(
            self, "envoy_ref", require_diplomacy_token(self.envoy_ref, max_chars=128)
        )
        object.__setattr__(
            self, "mandate_ref", _require_optional_token(self.mandate_ref)
        )
        _require_enum(self.status, DiplomaticEnvoyStatus, _RECORD_CODE)
        _require_enum(self.provenance, DiplomaticProvenance, _RECORD_CODE)
        _require_tick(self.accredited_tick)
        if self.end_tick is not None:
            _require_tick(self.end_tick)
        if type(self.revision) is not int or self.revision < 0:
            _fail(_RECORD_CODE)


@dataclass(frozen=True, slots=True)
class DiplomaticNegotiation:
    """One retained negotiation episode over a bounded subject."""

    negotiation_id: str
    relation_id: str
    topic_subject: str
    status: DiplomaticNegotiationStatus
    opened_tick: int
    last_tick: int
    envoy_refs: tuple[str, ...]
    term_kind: DiplomaticTermKind
    provenance: DiplomaticProvenance
    revision: int

    def __post_init__(self) -> None:
        _check_no_forbidden(self)
        require_diplomacy_id(self.negotiation_id, DIPLOMACY_NEGOTIATION_ID_PREFIX)
        require_diplomacy_id(self.relation_id, DIPLOMACY_RELATION_ID_PREFIX)
        object.__setattr__(
            self, "topic_subject", require_diplomacy_subject(self.topic_subject)
        )
        _require_enum(self.status, DiplomaticNegotiationStatus, _RECORD_CODE)
        _require_enum(self.term_kind, DiplomaticTermKind, _RECORD_CODE)
        _require_enum(self.provenance, DiplomaticProvenance, _RECORD_CODE)
        opened = _require_tick(self.opened_tick)
        last = _require_tick(self.last_tick)
        if last < opened:
            _fail(_RECORD_CODE)
        object.__setattr__(
            self,
            "envoy_refs",
            _require_tokens(self.envoy_refs, max_items=8, code=_RECORD_CODE),
        )
        if type(self.revision) is not int or self.revision < 0:
            _fail(_RECORD_CODE)


@dataclass(frozen=True, slots=True)
class DiplomaticInstrument:
    """One proposal, promise, agreement view, dispute, or shared project."""

    instrument_id: str
    relation_id: str
    party_ids: tuple[str, ...]
    kind: DiplomaticInstrumentKind
    term_kind: DiplomaticTermKind
    topic_subject: str
    opener_envoy_ref: str | None
    opened_tick: int
    end_tick: int | None
    anchor_refs: tuple[str, ...]
    revision: int
    provenance: DiplomaticProvenance

    def __post_init__(self) -> None:
        _check_no_forbidden(self)
        require_diplomacy_id(self.instrument_id, DIPLOMACY_INSTRUMENT_ID_PREFIX)
        require_diplomacy_id(self.relation_id, DIPLOMACY_RELATION_ID_PREFIX)
        object.__setattr__(
            self,
            "party_ids",
            _require_tokens(self.party_ids, max_items=32, code=_RECORD_CODE),
        )
        _require_enum(self.kind, DiplomaticInstrumentKind, _RECORD_CODE)
        _require_enum(self.term_kind, DiplomaticTermKind, _RECORD_CODE)
        _require_enum(self.provenance, DiplomaticProvenance, _RECORD_CODE)
        object.__setattr__(
            self, "topic_subject", require_diplomacy_subject(self.topic_subject)
        )
        object.__setattr__(
            self, "opener_envoy_ref", _require_optional_token(self.opener_envoy_ref)
        )
        _require_tick(self.opened_tick)
        if self.end_tick is not None:
            _require_tick(self.end_tick)
        object.__setattr__(
            self,
            "anchor_refs",
            _require_tokens(self.anchor_refs, max_items=8, code=_RECORD_CODE),
        )
        if type(self.revision) is not int or self.revision < 0:
            _fail(_RECORD_CODE)


@dataclass(frozen=True, slots=True)
class DiplomaticDeclaration:
    """Immutable party declaration on one instrument."""

    declaration_id: str
    instrument_id: str
    declarer_party_id: str
    envoy_ref: str | None
    act: DiplomaticDeclarationAct
    declared_tick: int
    provenance: DiplomaticProvenance
    independence_ref: str | None
    revision: int

    def __post_init__(self) -> None:
        _check_no_forbidden(self)
        require_diplomacy_id(self.declaration_id, DIPLOMACY_DECLARATION_ID_PREFIX)
        require_diplomacy_id(self.instrument_id, DIPLOMACY_INSTRUMENT_ID_PREFIX)
        require_diplomacy_id(self.declarer_party_id, DIPLOMACY_PARTY_ID_PREFIX)
        object.__setattr__(self, "envoy_ref", _require_optional_token(self.envoy_ref))
        _require_enum(self.act, DiplomaticDeclarationAct, _RECORD_CODE)
        _require_enum(self.provenance, DiplomaticProvenance, _RECORD_CODE)
        _require_tick(self.declared_tick)
        object.__setattr__(
            self, "independence_ref", _require_optional_token(self.independence_ref)
        )
        if type(self.revision) is not int or self.revision < 0:
            _fail(_RECORD_CODE)


@dataclass(frozen=True, slots=True)
class DiplomaticMisrepresentation:
    """One retained observation of an envoy's claim exceeding belief."""

    misrepresentation_id: str
    instrument_id: str
    kind: DiplomaticMisrepresentationKind
    observed_tick: int
    envoy_ref: str
    declarer_party_id: str
    provenance: DiplomaticProvenance

    def __post_init__(self) -> None:
        _check_no_forbidden(self)
        require_diplomacy_id(
            self.misrepresentation_id, DIPLOMACY_MISREPRESENTATION_ID_PREFIX
        )
        require_diplomacy_id(self.instrument_id, DIPLOMACY_INSTRUMENT_ID_PREFIX)
        _require_enum(self.kind, DiplomaticMisrepresentationKind, _RECORD_CODE)
        _require_enum(self.provenance, DiplomaticProvenance, _RECORD_CODE)
        require_diplomacy_id(self.declarer_party_id, DIPLOMACY_PARTY_ID_PREFIX)
        object.__setattr__(
            self, "envoy_ref", require_diplomacy_token(self.envoy_ref, max_chars=128)
        )
        _require_tick(self.observed_tick)


@dataclass(frozen=True, slots=True)
class DiplomaticTermination:
    """One retained termination of an instrument, envoy, or relation."""

    termination_id: str
    target_kind: str
    target_ref: str
    kind: DiplomaticTerminationKind
    tick: int
    provenance: DiplomaticProvenance

    def __post_init__(self) -> None:
        _check_no_forbidden(self)
        require_diplomacy_id(self.termination_id, DIPLOMACY_TERMINATION_ID_PREFIX)
        if self.target_kind not in _TERMINATION_KINDS_BY_TARGET:
            _fail("diplomacy_unknown_termination_target")
        object.__setattr__(
            self, "target_ref", require_diplomacy_token(self.target_ref, max_chars=128)
        )
        kind = _require_enum(self.kind, DiplomaticTerminationKind, _RECORD_CODE)
        if kind.value not in _TERMINATION_KINDS_BY_TARGET[self.target_kind]:
            _fail("diplomacy_invalid_termination")
        _require_enum(self.provenance, DiplomaticProvenance, _RECORD_CODE)
        _require_tick(self.tick)


@dataclass(frozen=True, slots=True)
class DiplomaticConflict:
    """One retained conflict. Conflicts coexist and are never reconciled."""

    conflict_id: str
    relation_id: str
    kind: DiplomaticConflictKind
    observed_tick: int
    instrument_refs: tuple[str, ...]
    party_refs: tuple[str, ...]
    provenance: DiplomaticProvenance

    def __post_init__(self) -> None:
        _check_no_forbidden(self)
        require_diplomacy_id(self.conflict_id, DIPLOMACY_CONFLICT_ID_PREFIX)
        require_diplomacy_id(self.relation_id, DIPLOMACY_RELATION_ID_PREFIX)
        _require_enum(self.kind, DiplomaticConflictKind, _RECORD_CODE)
        _require_enum(self.provenance, DiplomaticProvenance, _RECORD_CODE)
        _require_tick(self.observed_tick)
        object.__setattr__(
            self,
            "instrument_refs",
            _require_tokens(self.instrument_refs, max_items=8, code=_RECORD_CODE),
        )
        object.__setattr__(
            self,
            "party_refs",
            _require_tokens(self.party_refs, max_items=8, code=_RECORD_CODE),
        )


def diplomacy_relation_id(owner_id: object, party_anchor_keys: Sequence[str]) -> str:
    """Mint a deterministic relation id from the owner and anchor keys."""

    return diplomacy_record_id(
        DIPLOMACY_RELATION_ID_PREFIX,
        _owner_text(owner_id),
        ",".join(sorted(str(key) for key in party_anchor_keys)),
    )


def diplomacy_party_id(
    owner_id: object,
    kind: DiplomaticPartyKind,
    anchor_ref: str | None,
) -> str:
    """Mint a deterministic party id from kind and anchor."""

    return diplomacy_record_id(
        DIPLOMACY_PARTY_ID_PREFIX,
        _owner_text(owner_id),
        kind.value,
        anchor_ref or "none",
    )


def diplomacy_contact_id(
    owner_id: object,
    relation_id: str,
    tick: int,
    contact_kind: DiplomaticContactKind,
    location_anchor: str | None,
    source_ref: str | None,
    ordinal: int = 0,
) -> str:
    """Mint a deterministic contact id from one observed episode."""

    return diplomacy_record_id(
        DIPLOMACY_CONTACT_ID_PREFIX,
        _owner_text(owner_id),
        relation_id,
        tick,
        contact_kind.value,
        location_anchor or "none",
        source_ref or "none",
        ordinal,
    )


def diplomacy_envoy_id(
    owner_id: object,
    relation_id: str,
    party_id: str,
    envoy_ref: str,
    accredited_tick: int,
    revision: int,
) -> str:
    """Mint a deterministic envoy accreditation id."""

    return diplomacy_record_id(
        DIPLOMACY_ENVOY_ID_PREFIX,
        _owner_text(owner_id),
        relation_id,
        party_id,
        envoy_ref,
        accredited_tick,
        revision,
    )


def diplomacy_negotiation_id(
    owner_id: object,
    relation_id: str,
    topic_subject: str,
    opened_tick: int,
    revision: int,
) -> str:
    """Mint a deterministic negotiation id."""

    return diplomacy_record_id(
        DIPLOMACY_NEGOTIATION_ID_PREFIX,
        _owner_text(owner_id),
        relation_id,
        topic_subject,
        opened_tick,
        revision,
    )


def diplomacy_instrument_id(
    owner_id: object,
    relation_id: str,
    kind: DiplomaticInstrumentKind,
    topic_subject: str,
    opened_tick: int,
) -> str:
    """Mint a deterministic instrument id."""

    return diplomacy_record_id(
        DIPLOMACY_INSTRUMENT_ID_PREFIX,
        _owner_text(owner_id),
        relation_id,
        kind.value,
        topic_subject,
        opened_tick,
    )


def diplomacy_declaration_id(
    owner_id: object,
    instrument_id: str,
    declarer_party_id: str,
    act: DiplomaticDeclarationAct,
    declared_tick: int,
    revision: int,
) -> str:
    """Mint a deterministic declaration id."""

    return diplomacy_record_id(
        DIPLOMACY_DECLARATION_ID_PREFIX,
        _owner_text(owner_id),
        instrument_id,
        declarer_party_id,
        act.value,
        declared_tick,
        revision,
    )


def diplomacy_misrepresentation_id(
    owner_id: object,
    instrument_id: str,
    kind: DiplomaticMisrepresentationKind,
    declaration_id: str,
) -> str:
    """Mint a deterministic misrepresentation id from its evidence row."""

    return diplomacy_record_id(
        DIPLOMACY_MISREPRESENTATION_ID_PREFIX,
        _owner_text(owner_id),
        instrument_id,
        kind.value,
        declaration_id,
    )


def diplomacy_termination_id(
    owner_id: object,
    target_kind: str,
    target_ref: str,
    kind: DiplomaticTerminationKind,
    tick: int,
) -> str:
    """Mint a deterministic termination id."""

    return diplomacy_record_id(
        DIPLOMACY_TERMINATION_ID_PREFIX,
        _owner_text(owner_id),
        target_kind,
        target_ref,
        kind.value,
        tick,
    )


def diplomacy_conflict_id(
    owner_id: object,
    relation_id: str,
    kind: DiplomaticConflictKind,
    refs: Sequence[str],
) -> str:
    """Mint a deterministic conflict id from its observed references."""

    return diplomacy_record_id(
        DIPLOMACY_CONFLICT_ID_PREFIX,
        _owner_text(owner_id),
        relation_id,
        kind.value,
        ",".join(sorted(str(ref) for ref in refs)),
    )


@dataclass(frozen=True, slots=True)
class DiplomaticStandingSummary:
    """Read-only counts over one owner's diplomacy beliefs. No score."""

    relations: int
    parties: int
    resolved_parties: int
    unresolved_parties: int
    envoy_status_counts: tuple[tuple[str, int], ...]
    instrument_status_counts: tuple[tuple[str, int], ...]
    terminations: int
    last_activity_tick: int

    def __post_init__(self) -> None:
        _check_no_forbidden(self)
        for name in (
            "relations",
            "parties",
            "resolved_parties",
            "unresolved_parties",
            "terminations",
            "last_activity_tick",
        ):
            _require_tick(getattr(self, name), _RECORD_CODE)
        for counts_name in ("envoy_status_counts", "instrument_status_counts"):
            counts = getattr(self, counts_name)
            if not isinstance(counts, tuple):
                _fail(_RECORD_CODE)
            for item in counts:
                if (
                    type(item) is not tuple
                    or len(item) != 2
                    or type(item[0]) is not str
                    or type(item[1]) is not int
                    or item[1] < 0
                ):
                    _fail(_RECORD_CODE)


@dataclass(frozen=True, slots=True)
class DiplomacyLedger:
    """One owner's long-running diplomacy beliefs.

    ``None`` means the mode is off. Every row is retained; statuses are derived.
    """

    owner_id: str
    tick: int = 0
    policy_version: str = DIPLOMACY_POLICY_VERSION
    revision: int = 0
    relations: tuple[DiplomaticRelation, ...] = ()
    parties: tuple[DiplomaticParty, ...] = ()
    contacts: tuple[DiplomaticContact, ...] = ()
    envoys: tuple[DiplomaticEnvoy, ...] = ()
    negotiations: tuple[DiplomaticNegotiation, ...] = ()
    instruments: tuple[DiplomaticInstrument, ...] = ()
    declarations: tuple[DiplomaticDeclaration, ...] = ()
    misrepresentations: tuple[DiplomaticMisrepresentation, ...] = ()
    terminations: tuple[DiplomaticTermination, ...] = ()
    conflicts: tuple[DiplomaticConflict, ...] = ()
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _check_no_forbidden(self)
        owner = _owner_text(self.owner_id)
        object.__setattr__(self, "owner_id", owner)
        if self.policy_version != DIPLOMACY_POLICY_VERSION:
            _fail("diplomacy_policy_mismatch")
        _require_tick(self.tick)
        _require_tick(self.revision, _RECORD_CODE)

        relations = _require_rows(self.relations, DiplomaticRelation)
        parties = _require_rows(self.parties, DiplomaticParty)
        contacts = _require_rows(self.contacts, DiplomaticContact)
        envoys = _require_rows(self.envoys, DiplomaticEnvoy)
        negotiations = _require_rows(self.negotiations, DiplomaticNegotiation)
        instruments = _require_rows(self.instruments, DiplomaticInstrument)
        declarations = _require_rows(self.declarations, DiplomaticDeclaration)
        misrepresentations = _require_rows(
            self.misrepresentations, DiplomaticMisrepresentation
        )
        terminations = _require_rows(self.terminations, DiplomaticTermination)
        conflicts = _require_rows(self.conflicts, DiplomaticConflict)

        _require_ordered(relations, tick_name="opened_tick", id_name="relation_id")
        _require_ordered(parties, tick_name="first_seen_tick", id_name="party_id")
        _require_ordered(contacts, tick_name="tick", id_name="contact_id")
        _require_ordered(envoys, tick_name="accredited_tick", id_name="envoy_id")
        _require_ordered(
            negotiations, tick_name="opened_tick", id_name="negotiation_id"
        )
        _require_ordered(instruments, tick_name="opened_tick", id_name="instrument_id")
        _require_ordered(
            declarations, tick_name="declared_tick", id_name="declaration_id"
        )
        _require_ordered(
            misrepresentations,
            tick_name="observed_tick",
            id_name="misrepresentation_id",
        )
        _require_ordered(terminations, tick_name="tick", id_name="termination_id")
        _require_ordered(conflicts, tick_name="observed_tick", id_name="conflict_id")

        party_by_id = {row.party_id: row for row in parties}
        relation_by_id = {row.relation_id: row for row in relations}
        envoy_by_id = {row.envoy_id: row for row in envoys}
        instrument_by_id = {row.instrument_id: row for row in instruments}

        for relation in relations:
            seen: set[str] = set()
            for party_id in relation.party_ids:
                if party_id not in party_by_id:
                    _fail("diplomacy_foreign_reference")
                if party_id in seen:
                    _fail("diplomacy_party_set_invalid")
                seen.add(party_id)
            self_party = party_by_id[relation.party_ids[0]]
            if (
                self_party.kind is not DiplomaticPartyKind.AGENT
                or self_party.anchor_ref != owner
            ):
                _fail("diplomacy_self_party_missing")

        for contact in contacts:
            if contact.relation_id not in relation_by_id:
                _fail("diplomacy_foreign_reference")

        for envoy in envoys:
            relation = relation_by_id.get(envoy.relation_id)
            if relation is None or envoy.party_id not in relation.party_ids:
                _fail("diplomacy_foreign_reference")

        for negotiation in negotiations:
            relation = relation_by_id.get(negotiation.relation_id)
            if relation is None:
                _fail("diplomacy_foreign_reference")
            envoy_refs = {
                row.envoy_ref
                for row in envoys
                if row.relation_id == negotiation.relation_id
            }
            if any(ref not in envoy_refs for ref in negotiation.envoy_refs):
                _fail("diplomacy_foreign_reference")
        negotiation_keys = [
            (row.relation_id, row.topic_subject, row.revision) for row in negotiations
        ]
        if len(set(negotiation_keys)) != len(negotiation_keys):
            _fail("diplomacy_duplicate_id")

        for instrument in instruments:
            relation = relation_by_id.get(instrument.relation_id)
            if relation is None or instrument.party_ids != relation.party_ids:
                _fail("diplomacy_instrument_party_mismatch")
            if instrument.opener_envoy_ref is not None and not any(
                row.relation_id == instrument.relation_id
                and row.envoy_ref == instrument.opener_envoy_ref
                for row in envoys
            ):
                _fail("diplomacy_foreign_reference")

        declaration_keys: set[tuple[str, str, str, int]] = set()
        for declaration in declarations:
            instrument = instrument_by_id.get(declaration.instrument_id)
            if instrument is None:
                _fail("diplomacy_foreign_reference")
            if declaration.declarer_party_id not in instrument.party_ids:
                _fail("diplomacy_party_set_invalid")
            if declaration.declared_tick < instrument.opened_tick:
                _fail("diplomacy_invalid_record")
            allowed = _DECLARATION_ACTS_BY_INSTRUMENT.get(instrument.kind.value)
            if allowed is None or declaration.act.value not in allowed:
                _fail("diplomacy_declaration_kind_mismatch")
            if declaration.envoy_ref is not None and not any(
                row.relation_id == instrument.relation_id
                and row.envoy_ref == declaration.envoy_ref
                for row in envoys
            ):
                _fail("diplomacy_foreign_reference")
            key = (
                declaration.instrument_id,
                declaration.declarer_party_id,
                declaration.act.value,
                declaration.revision,
            )
            if key in declaration_keys:
                _fail("diplomacy_duplicate_declaration")
            declaration_keys.add(key)

        for row in misrepresentations:
            instrument = instrument_by_id.get(row.instrument_id)
            if instrument is None or row.declarer_party_id not in instrument.party_ids:
                _fail("diplomacy_foreign_reference")

        for termination in terminations:
            if termination.target_kind == "instrument":
                exists = termination.target_ref in instrument_by_id
            elif termination.target_kind == "envoy":
                exists = termination.target_ref in envoy_by_id
            else:
                exists = termination.target_ref in relation_by_id
            if not exists:
                _fail("diplomacy_unknown_termination_target")

        for conflict in conflicts:
            relation = relation_by_id.get(conflict.relation_id)
            if relation is None:
                _fail("diplomacy_foreign_reference")
            if any(ref not in instrument_by_id for ref in conflict.instrument_refs):
                _fail("diplomacy_foreign_reference")
            if any(ref not in party_by_id for ref in conflict.party_refs):
                _fail("diplomacy_foreign_reference")

        notices = _require_tokens(self.notices, max_items=64, max_chars=64)
        object.__setattr__(self, "notices", notices)

        highest = max(
            (
                *(row.opened_tick for row in relations),
                *(row.first_seen_tick for row in parties),
                *(row.tick for row in contacts),
                *(row.accredited_tick for row in envoys),
                *(row.opened_tick for row in negotiations),
                *(row.opened_tick for row in instruments),
                *(row.declared_tick for row in declarations),
                *(row.observed_tick for row in misrepresentations),
                *(row.tick for row in terminations),
                *(row.observed_tick for row in conflicts),
                0,
            )
        )
        if highest > self.tick:
            _fail("diplomacy_invalid_tick")


def empty_diplomacy_ledger(owner_id: object, *, tick: int) -> DiplomacyLedger:
    """Return one empty owner ledger at ``tick``."""

    return DiplomacyLedger(owner_id=_owner_text(owner_id), tick=_require_tick(tick))


def require_owner_diplomacy(
    ledger: object,
    owner_id: object,
    *,
    field_name: str = "diplomacy",
) -> None:
    """Reject a foreign or mistyped ledger. ``None`` passes."""

    if ledger is None:
        return
    if type(ledger) is not DiplomacyLedger:
        raise TypeError(f"{field_name} must be DiplomacyLedger")
    if ledger.owner_id != _owner_text(owner_id):
        _fail("diplomacy_owner_mismatch")


def _json_default(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    raise TypeError("unsupported diplomacy digest value")


def diplomacy_ledger_digest(ledger: DiplomacyLedger) -> str:
    """Return a canonical digest over one owner's diplomacy beliefs."""

    if type(ledger) is not DiplomacyLedger:
        raise TypeError("ledger must be DiplomacyLedger")
    from dataclasses import asdict

    payload = {
        "owner_id": ledger.owner_id,
        "tick": ledger.tick,
        "policy_version": ledger.policy_version,
        "revision": ledger.revision,
        "notices": list(ledger.notices),
        "relations": [
            asdict(row) for row in sorted(ledger.relations, key=lambda r: r.relation_id)
        ],
        "parties": [
            asdict(row) for row in sorted(ledger.parties, key=lambda r: r.party_id)
        ],
        "contacts": [
            asdict(row) for row in sorted(ledger.contacts, key=lambda r: r.contact_id)
        ],
        "envoys": [
            asdict(row) for row in sorted(ledger.envoys, key=lambda r: r.envoy_id)
        ],
        "negotiations": [
            asdict(row)
            for row in sorted(ledger.negotiations, key=lambda r: r.negotiation_id)
        ],
        "instruments": [
            asdict(row)
            for row in sorted(ledger.instruments, key=lambda r: r.instrument_id)
        ],
        "declarations": [
            asdict(row)
            for row in sorted(ledger.declarations, key=lambda r: r.declaration_id)
        ],
        "misrepresentations": [
            asdict(row)
            for row in sorted(
                ledger.misrepresentations, key=lambda r: r.misrepresentation_id
            )
        ],
        "terminations": [
            asdict(row)
            for row in sorted(ledger.terminations, key=lambda r: r.termination_id)
        ],
        "conflicts": [
            asdict(row) for row in sorted(ledger.conflicts, key=lambda r: r.conflict_id)
        ],
    }
    text = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=_json_default
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_ENVOY_STATUS_MAP: Final[Mapping[str, DiplomaticEnvoyStatus]] = MappingProxyType(
    {
        "claimed": DiplomaticEnvoyStatus.CLAIMED,
        "recognized": DiplomaticEnvoyStatus.RECOGNIZED,
        "contested": DiplomaticEnvoyStatus.CONTESTED,
        "rejected": DiplomaticEnvoyStatus.REJECTED,
        "revoked": DiplomaticEnvoyStatus.REVOKED,
        "expired": DiplomaticEnvoyStatus.EXPIRED,
        "superseded": DiplomaticEnvoyStatus.SUPERSEDED,
        "unknown": DiplomaticEnvoyStatus.UNKNOWN,
    }
)


def _mandate_for(envoy: DiplomaticEnvoy, representation: object | None) -> Any:
    if representation is None or envoy.mandate_ref is None:
        return None
    for mandate in getattr(representation, "mandates", ()):
        if getattr(mandate, "mandate_id", None) == envoy.mandate_ref:
            return mandate
    return None


def diplomacy_envoy_status(
    envoy: DiplomaticEnvoy,
    representation: object | None,
    *,
    tick: int,
    policy: DiplomacyPolicy,
) -> DiplomaticEnvoyStatus:
    """Derive current envoy standing from the owner's representation ledger."""

    if type(envoy) is not DiplomaticEnvoy:
        raise TypeError("envoy must be DiplomaticEnvoy")
    if type(policy) is not DiplomacyPolicy:
        raise TypeError("policy must be DiplomacyPolicy")
    _require_tick(tick)
    if envoy.end_tick is not None and tick >= envoy.end_tick:
        return DiplomaticEnvoyStatus.EXPIRED
    if envoy.mandate_ref is None:
        return DiplomaticEnvoyStatus.CLAIMED
    mandate = _mandate_for(envoy, representation)
    if mandate is None:
        return DiplomaticEnvoyStatus.UNKNOWN
    end_tick = getattr(mandate, "end_tick", None)
    if type(end_tick) is int and tick >= end_tick:
        return DiplomaticEnvoyStatus.EXPIRED
    if bool(getattr(mandate, "revoked", False)):
        return DiplomaticEnvoyStatus.REVOKED
    if bool(getattr(mandate, "superseded", False)):
        return DiplomaticEnvoyStatus.SUPERSEDED
    if bool(getattr(mandate, "expired", False)):
        return DiplomaticEnvoyStatus.EXPIRED
    status = getattr(getattr(mandate, "status", None), "value", None)
    return _ENVOY_STATUS_MAP.get(cast(str, status), DiplomaticEnvoyStatus.UNKNOWN)


def _declaration_counts_for_party(
    declaration: DiplomaticDeclaration,
    instrument: DiplomaticInstrument,
    *,
    tick: int,
    policy: DiplomacyPolicy,
    representation: object | None,
    envoys: Sequence[DiplomaticEnvoy],
) -> bool:
    if declaration.envoy_ref is None:
        return True
    envoy = next(
        (
            row
            for row in envoys
            if row.relation_id == instrument.relation_id
            and row.envoy_ref == declaration.envoy_ref
        ),
        None,
    )
    if envoy is None:
        return False
    if (
        diplomacy_envoy_status(envoy, representation, tick=tick, policy=policy)
        is not DiplomaticEnvoyStatus.RECOGNIZED
    ):
        return False
    mandate = _mandate_for(envoy, representation)
    if mandate is None:
        return False
    return diplomacy_scope_covers(
        scope_kind=getattr(mandate, "scope_kind", None),
        duration_kind=getattr(mandate, "duration_kind", None),
        instrument_kind=instrument.kind,
        scope_subject=getattr(mandate, "scope_subject", None),
        topic_subject=instrument.topic_subject,
    )


def diplomacy_instrument_status(
    instrument: DiplomaticInstrument,
    declarations: Sequence[DiplomaticDeclaration],
    *,
    tick: int,
    policy: DiplomacyPolicy,
    representation: object | None = None,
    envoys: Sequence[DiplomaticEnvoy] = (),
) -> tuple[DiplomaticInstrumentStatus, DiplomaticAcceptanceBasis]:
    """Derive one instrument's current status from party declarations."""

    if type(instrument) is not DiplomaticInstrument:
        raise TypeError("instrument must be DiplomaticInstrument")
    if type(policy) is not DiplomacyPolicy:
        raise TypeError("policy must be DiplomacyPolicy")
    _require_tick(tick)
    rows = sorted(
        (
            row
            for row in declarations
            if type(row) is DiplomaticDeclaration
            and row.instrument_id == instrument.instrument_id
        ),
        key=lambda row: (row.declared_tick, row.declaration_id),
    )
    if instrument.end_tick is not None and tick >= instrument.end_tick:
        return DiplomaticInstrumentStatus.EXPIRED, DiplomaticAcceptanceBasis.EXPIRED
    if any(row.act is DiplomaticDeclarationAct.REJECT for row in rows):
        return DiplomaticInstrumentStatus.REJECTED, DiplomaticAcceptanceBasis.REJECTED
    if any(row.act is DiplomaticDeclarationAct.DISPUTE for row in rows):
        return (
            DiplomaticInstrumentStatus.UNRESOLVED,
            DiplomaticAcceptanceBasis.DISPUTED,
        )
    opener_party = instrument.party_ids[0]
    if any(
        row.act is DiplomaticDeclarationAct.WITHDRAW
        and row.declarer_party_id == opener_party
        for row in rows
    ):
        return (
            DiplomaticInstrumentStatus.WITHDRAWN,
            DiplomaticAcceptanceBasis.WITHDRAWN,
        )
    if any(
        row.act is DiplomaticDeclarationAct.REPORT
        and row.independence_ref == _COMPLETION_CLAIM_MARKER
        for row in rows
    ):
        return (
            DiplomaticInstrumentStatus.COMPLETED_CLAIMED,
            DiplomaticAcceptanceBasis.ALL_PARTIES_DECLARED,
        )

    accepted: set[str] = set()
    for row in rows:
        if row.act is not DiplomaticDeclarationAct.ACCEPT:
            continue
        if _declaration_counts_for_party(
            row,
            instrument,
            tick=tick,
            policy=policy,
            representation=representation,
            envoys=envoys,
        ):
            accepted.add(row.declarer_party_id)

    every_party = len(accepted) == len(instrument.party_ids) and len(
        instrument.party_ids
    ) >= max(2, policy.agreement_min_party_declarations)
    if every_party:
        if instrument.kind is DiplomaticInstrumentKind.SHARED_PROJECT:
            return DiplomaticInstrumentStatus.ACTIVE, (
                DiplomaticAcceptanceBasis.ALL_PARTIES_DECLARED
            )
        if instrument.kind in {
            DiplomaticInstrumentKind.PROPOSAL,
            DiplomaticInstrumentKind.AGREEMENT,
        }:
            return DiplomaticInstrumentStatus.APPARENTLY_ACCEPTED, (
                DiplomaticAcceptanceBasis.ALL_PARTIES_DECLARED
            )
    opener_declared = any(
        row.declarer_party_id == opener_party
        and row.act
        in {
            DiplomaticDeclarationAct.PROPOSE,
            DiplomaticDeclarationAct.PROMISE,
            DiplomaticDeclarationAct.DISPUTE,
            DiplomaticDeclarationAct.SHARED_PROJECT,
        }
        for row in rows
    )
    if opener_declared and len(rows) == 1:
        return DiplomaticInstrumentStatus.PROPOSED, (
            DiplomaticAcceptanceBasis.OPENER_ONLY
        )
    if instrument.kind is DiplomaticInstrumentKind.PROMISE:
        return DiplomaticInstrumentStatus.OPEN, DiplomaticAcceptanceBasis.NONE
    if instrument.kind is DiplomaticInstrumentKind.SHARED_PROJECT:
        return DiplomaticInstrumentStatus.OPEN, DiplomaticAcceptanceBasis.NONE
    return DiplomaticInstrumentStatus.PROPOSED, DiplomaticAcceptanceBasis.NONE


def is_agreement_view(
    instrument: DiplomaticInstrument,
    declarations: Sequence[DiplomaticDeclaration],
    *,
    tick: int,
    policy: DiplomacyPolicy,
    representation: object | None = None,
    envoys: Sequence[DiplomaticEnvoy] = (),
) -> bool:
    """Return whether an accepted proposal is an agreement view, not a row kind."""

    if type(instrument) is not DiplomaticInstrument:
        raise TypeError("instrument must be DiplomaticInstrument")
    if instrument.kind is not DiplomaticInstrumentKind.PROPOSAL:
        return False
    status, _ = diplomacy_instrument_status(
        instrument,
        declarations,
        tick=tick,
        policy=policy,
        representation=representation,
        envoys=envoys,
    )
    return status is DiplomaticInstrumentStatus.APPARENTLY_ACCEPTED


def diplomacy_standing_summary(
    ledger: DiplomacyLedger,
    *,
    tick: int | None = None,
    policy: DiplomacyPolicy | None = None,
    representation: object | None = None,
) -> DiplomaticStandingSummary:
    """Count rows and derived statuses. Carries no score or aggregate."""

    if type(ledger) is not DiplomacyLedger:
        raise TypeError("ledger must be DiplomacyLedger")
    current = ledger.tick if tick is None else _require_tick(tick)
    active_policy = default_diplomacy_policy() if policy is None else policy
    envoy_counts: dict[str, int] = {}
    for envoy_row in ledger.envoys:
        status = diplomacy_envoy_status(
            envoy_row, representation, tick=current, policy=active_policy
        )
        envoy_counts[status.value] = envoy_counts.get(status.value, 0) + 1
    instrument_counts: dict[str, int] = {}
    for instrument_row in ledger.instruments:
        instrument_status, _ = diplomacy_instrument_status(
            instrument_row,
            ledger.declarations,
            tick=current,
            policy=active_policy,
            representation=representation,
            envoys=ledger.envoys,
        )
        instrument_counts[instrument_status.value] = (
            instrument_counts.get(instrument_status.value, 0) + 1
        )
    highest = max((ledger.tick, *(row.first_seen_tick for row in ledger.parties), 0))
    return DiplomaticStandingSummary(
        relations=len(ledger.relations),
        parties=len(ledger.parties),
        resolved_parties=sum(
            1
            for row in ledger.parties
            if row.resolution is DiplomaticPartyResolution.RESOLVED
        ),
        unresolved_parties=sum(
            1
            for row in ledger.parties
            if row.resolution is DiplomaticPartyResolution.UNRESOLVED
        ),
        envoy_status_counts=tuple(sorted(envoy_counts.items())),
        instrument_status_counts=tuple(sorted(instrument_counts.items())),
        terminations=len(ledger.terminations),
        last_activity_tick=highest,
    )


def _bump(ledger: DiplomacyLedger, **changes: Any) -> DiplomacyLedger:
    tick = changes.pop("tick", ledger.tick)
    return replace(
        ledger,
        tick=max(ledger.tick, int(cast(int, tick))),
        revision=ledger.revision + 1,
        **changes,
    )


def _append_sorted(
    rows: Sequence[Any], new_rows: Sequence[Any], key_name: str
) -> tuple[Any, ...]:
    by_id = {getattr(row, key_name): row for row in rows}
    for row in new_rows:
        by_id.setdefault(getattr(row, key_name), row)
    return tuple(sorted(by_id.values(), key=lambda row: getattr(row, key_name)))


def apply_diplomacy_termination(
    ledger: DiplomacyLedger,
    *,
    target_kind: str,
    target_ref: str,
    kind: DiplomaticTerminationKind,
    tick: int,
    provenance: DiplomaticProvenance,
) -> DiplomacyLedger:
    """Append one retained termination row. Idempotent by content-addressed id."""

    if type(ledger) is not DiplomacyLedger:
        raise TypeError("ledger must be DiplomacyLedger")
    if target_kind not in _TERMINATION_KINDS_BY_TARGET:
        _fail("diplomacy_unknown_termination_target")
    if kind.value not in _TERMINATION_KINDS_BY_TARGET[target_kind]:
        _fail("diplomacy_invalid_termination")
    if target_kind == "instrument":
        exists = any(row.instrument_id == target_ref for row in ledger.instruments)
    elif target_kind == "envoy":
        exists = any(row.envoy_id == target_ref for row in ledger.envoys)
    else:
        exists = any(row.relation_id == target_ref for row in ledger.relations)
    if not exists:
        _fail("diplomacy_unknown_termination_target")
    termination_id = diplomacy_termination_id(
        ledger.owner_id, target_kind, target_ref, kind, tick
    )
    if any(row.termination_id == termination_id for row in ledger.terminations):
        return ledger
    row = DiplomaticTermination(
        termination_id=termination_id,
        target_kind=target_kind,
        target_ref=target_ref,
        kind=kind,
        tick=tick,
        provenance=provenance,
    )
    _LOG.info("diplomacy_instrument_terminated kind=%s", kind.value)
    return _bump(
        ledger,
        tick=tick,
        terminations=tuple(
            sorted(
                (*ledger.terminations, row),
                key=lambda item: (item.tick, item.termination_id),
            )
        ),
    )


def expire_diplomacy_records(
    ledger: DiplomacyLedger, *, tick: int, policy: DiplomacyPolicy
) -> DiplomacyLedger:
    """Append EXPIRED terminations at the exclusive boundary. Rows stay."""

    if type(ledger) is not DiplomacyLedger:
        raise TypeError("ledger must be DiplomacyLedger")
    if type(policy) is not DiplomacyPolicy:
        raise TypeError("policy must be DiplomacyPolicy")
    _require_tick(tick)
    updated = ledger
    expired_targets = {
        (row.target_kind, row.target_ref)
        for row in ledger.terminations
        if row.kind is DiplomaticTerminationKind.EXPIRED
    }
    for instrument in ledger.instruments:
        if (
            instrument.end_tick is not None
            and tick >= instrument.end_tick
            and ("instrument", instrument.instrument_id) not in expired_targets
        ):
            updated = apply_diplomacy_termination(
                updated,
                target_kind="instrument",
                target_ref=instrument.instrument_id,
                kind=DiplomaticTerminationKind.EXPIRED,
                tick=tick,
                provenance=DiplomaticProvenance.REPRESENTATION_BELIEF,
            )
    for envoy in ledger.envoys:
        if (
            envoy.end_tick is not None
            and tick >= envoy.end_tick
            and ("envoy", envoy.envoy_id) not in expired_targets
        ):
            updated = apply_diplomacy_termination(
                updated,
                target_kind="envoy",
                target_ref=envoy.envoy_id,
                kind=DiplomaticTerminationKind.EXPIRED,
                tick=tick,
                provenance=DiplomaticProvenance.REPRESENTATION_BELIEF,
            )
    return updated


def supersede_diplomacy_instruments(ledger: DiplomacyLedger) -> DiplomacyLedger:
    """Retain supersession when a later recognized instrument repeats a subject."""

    if type(ledger) is not DiplomacyLedger:
        raise TypeError("ledger must be DiplomacyLedger")
    updated = ledger
    superseded = {
        row.target_ref
        for row in updated.terminations
        if row.kind is DiplomaticTerminationKind.SUPERSEDED
    }
    groups: dict[tuple[str, str, str], list[DiplomaticInstrument]] = {}
    for instrument in ledger.instruments:
        groups.setdefault(
            (instrument.relation_id, instrument.kind.value, instrument.topic_subject),
            [],
        ).append(instrument)
    for rows in groups.values():
        ordered = sorted(rows, key=lambda row: (row.opened_tick, row.instrument_id))
        for index, later in enumerate(ordered):
            if not any(
                row.instrument_id == later.instrument_id
                and row.act is DiplomaticDeclarationAct.ACCEPT
                for row in ledger.declarations
            ):
                continue
            for earlier in ordered[:index]:
                if earlier.instrument_id in superseded:
                    continue
                accepted_parties = {
                    row.declarer_party_id
                    for row in ledger.declarations
                    if row.instrument_id == earlier.instrument_id
                    and row.act is DiplomaticDeclarationAct.ACCEPT
                }
                if accepted_parties == set(earlier.party_ids):
                    continue
                updated = apply_diplomacy_termination(
                    updated,
                    target_kind="instrument",
                    target_ref=earlier.instrument_id,
                    kind=DiplomaticTerminationKind.SUPERSEDED,
                    tick=max(updated.tick, later.opened_tick),
                    provenance=DiplomaticProvenance.COMMUNICATED,
                )
                superseded.add(earlier.instrument_id)
    return updated


def detect_diplomacy_conflicts(ledger: DiplomacyLedger) -> DiplomacyLedger:
    """Derive retained conflicts. Conflicts coexist and are never reconciled."""

    if type(ledger) is not DiplomacyLedger:
        raise TypeError("ledger must be DiplomacyLedger")
    rows: list[DiplomaticConflict] = []
    party_by_id = {row.party_id: row for row in ledger.parties}

    def add(
        relation_id: str,
        kind: DiplomaticConflictKind,
        refs: Sequence[str],
        *,
        party_refs: Sequence[str] = (),
    ) -> None:
        conflict_id = diplomacy_conflict_id(
            ledger.owner_id, relation_id, kind, tuple(refs)
        )
        rows.append(
            DiplomaticConflict(
                conflict_id=conflict_id,
                relation_id=relation_id,
                kind=kind,
                observed_tick=ledger.tick,
                instrument_refs=tuple(refs),
                party_refs=tuple(party_refs),
                provenance=DiplomaticProvenance.COMMUNICATED,
            )
        )

    envoy_groups: dict[tuple[str, str], list[DiplomaticEnvoy]] = {}
    for envoy in ledger.envoys:
        envoy_groups.setdefault((envoy.relation_id, envoy.party_id), []).append(envoy)
    for (relation_id, party_id), group in envoy_groups.items():
        mandates = {row.mandate_ref for row in group if row.mandate_ref is not None}
        if len(mandates) > 1:
            add(
                relation_id,
                DiplomaticConflictKind.DUPLICATE_ENVOY,
                (),
                party_refs=(party_id,),
            )

    term_groups: dict[tuple[str, str], list[DiplomaticInstrument]] = {}
    for instrument in ledger.instruments:
        term_groups.setdefault(
            (instrument.relation_id, instrument.topic_subject), []
        ).append(instrument)
    for (relation_id, _), instrument_group in term_groups.items():
        terms = {item.term_kind for item in instrument_group}
        if len(terms) > 1:
            add(
                relation_id,
                DiplomaticConflictKind.CONTRADICTORY_TERMS,
                tuple(sorted(item.instrument_id for item in instrument_group)),
            )

    for relation in ledger.relations:
        by_anchor: dict[str, set[str]] = {}
        for party_id in relation.party_ids:
            party = party_by_id[party_id]
            if party.anchor_ref is None:
                continue
            by_anchor.setdefault(party.anchor_ref, set()).add(party.kind.value)
        for anchor, kinds in by_anchor.items():
            if len(kinds) > 1:
                add(
                    relation.relation_id,
                    DiplomaticConflictKind.CONFLICTING_PARTY,
                    (),
                    party_refs=tuple(
                        sorted(
                            party_id
                            for party_id in relation.party_ids
                            if party_by_id[party_id].anchor_ref == anchor
                        )
                    ),
                )

    for dispute in ledger.instruments:
        if dispute.kind is not DiplomaticInstrumentKind.DISPUTE:
            continue
        for candidate in ledger.instruments:
            if (
                candidate.kind is DiplomaticInstrumentKind.PROPOSAL
                and candidate.relation_id == dispute.relation_id
                and candidate.topic_subject == dispute.topic_subject
                and any(
                    row.instrument_id == candidate.instrument_id
                    and row.act is DiplomaticDeclarationAct.ACCEPT
                    for row in ledger.declarations
                )
            ):
                add(
                    dispute.relation_id,
                    DiplomaticConflictKind.AGREEMENT_DISPUTE,
                    tuple(sorted((dispute.instrument_id, candidate.instrument_id))),
                )

    merged = {row.conflict_id: row for row in ledger.conflicts}
    for row in rows:
        merged.setdefault(row.conflict_id, row)
    if set(merged) == {row.conflict_id for row in ledger.conflicts}:
        return ledger
    return _bump(
        ledger,
        conflicts=tuple(
            sorted(
                merged.values(), key=lambda item: (item.observed_tick, item.conflict_id)
            )
        ),
    )


def _drop_oldest(
    rows: Sequence[Any], *, table: str, count: int
) -> tuple[tuple[Any, ...], int]:
    ordered = list(rows)
    drop = min(count, len(ordered))
    if drop <= 0:
        return tuple(ordered), 0
    _LOG.warning("diplomacy_truncated table=%s dropped=%s", table, drop)
    return tuple(ordered[drop:]), drop


def enforce_diplomacy_limits(
    ledger: DiplomacyLedger, *, policy: DiplomacyPolicy
) -> DiplomacyLedger:
    """Deterministically drop only documented low-priority rows."""

    if type(ledger) is not DiplomacyLedger:
        raise TypeError("ledger must be DiplomacyLedger")
    if type(policy) is not DiplomacyPolicy:
        raise TypeError("policy must be DiplomacyPolicy")

    contacts = list(ledger.contacts)
    envoys = list(ledger.envoys)
    negotiations = list(ledger.negotiations)
    instruments = list(ledger.instruments)
    declarations = list(ledger.declarations)
    relations = list(ledger.relations)
    parties = list(ledger.parties)
    notices = set(ledger.notices)
    before_counts = (
        len(relations),
        len(parties),
        len(contacts),
        len(envoys),
        len(negotiations),
        len(instruments),
        len(declarations),
    )

    if len(instruments) > policy.max_instruments_per_relation * max(1, len(relations)):
        grouped: dict[str, list[Any]] = {}
        for instrument_row in instruments:
            grouped.setdefault(instrument_row.relation_id, []).append(instrument_row)
        kept_instruments: list[Any] = []
        for group in grouped.values():
            if len(group) > policy.max_instruments_per_relation:
                kept_instruments.extend(group[-policy.max_instruments_per_relation :])
                notices.add("diplomacy_truncated:instruments")
                _LOG.warning(
                    "diplomacy_truncated table=instruments dropped=%s",
                    len(group) - policy.max_instruments_per_relation,
                )
            else:
                kept_instruments.extend(group)
        instruments = kept_instruments

    if len(contacts) > policy.max_contacts_per_relation * max(1, len(relations)):
        grouped_contacts: dict[str, list[Any]] = {}
        for contact_row in contacts:
            grouped_contacts.setdefault(contact_row.relation_id, []).append(contact_row)
        kept_contacts: list[Any] = []
        for group in grouped_contacts.values():
            if len(group) > policy.max_contacts_per_relation:
                kept_contacts.extend(group[-policy.max_contacts_per_relation :])
                notices.add("diplomacy_truncated:contacts")
                _LOG.warning(
                    "diplomacy_truncated table=contacts dropped=%s",
                    len(group) - policy.max_contacts_per_relation,
                )
            else:
                kept_contacts.extend(group)
        contacts = kept_contacts

    if len(negotiations) > policy.max_negotiations_per_relation * max(
        1, len(relations)
    ):
        grouped_negotiations: dict[str, list[Any]] = {}
        for negotiation_row in negotiations:
            grouped_negotiations.setdefault(negotiation_row.relation_id, []).append(
                negotiation_row
            )
        kept_negotiations: list[Any] = []
        for group in grouped_negotiations.values():
            if len(group) > policy.max_negotiations_per_relation:
                kept_negotiations.extend(group[-policy.max_negotiations_per_relation :])
                notices.add("diplomacy_truncated:negotiations")
                _LOG.warning(
                    "diplomacy_truncated table=negotiations dropped=%s",
                    len(group) - policy.max_negotiations_per_relation,
                )
            else:
                kept_negotiations.extend(group)
        negotiations = kept_negotiations

    if len(envoys) > policy.max_envoys_per_relation * max(1, len(relations)):
        grouped_envoys: dict[str, list[Any]] = {}
        for envoy_row in envoys:
            grouped_envoys.setdefault(envoy_row.relation_id, []).append(envoy_row)
        kept_envoys: list[Any] = []
        for group in grouped_envoys.values():
            if len(group) > policy.max_envoys_per_relation:
                kept_envoys.extend(group[-policy.max_envoys_per_relation :])
                notices.add("diplomacy_truncated:envoys")
                _LOG.warning(
                    "diplomacy_truncated table=envoys dropped=%s",
                    len(group) - policy.max_envoys_per_relation,
                )
            else:
                kept_envoys.extend(group)
        envoys = kept_envoys

    declaration_groups: dict[str, list[Any]] = {}
    for declaration_row in declarations:
        declaration_groups.setdefault(declaration_row.instrument_id, []).append(
            declaration_row
        )
    kept_declarations: list[Any] = []
    for group in declaration_groups.values():
        if len(group) > policy.max_declarations_per_instrument:
            kept_declarations.extend(group[-policy.max_declarations_per_instrument :])
            notices.add("diplomacy_truncated:declarations")
            _LOG.warning(
                "diplomacy_truncated table=declarations dropped=%s",
                len(group) - policy.max_declarations_per_instrument,
            )
        else:
            kept_declarations.extend(group)
    declarations = kept_declarations

    kept_ids = {row.instrument_id for row in instruments}
    declarations = [row for row in declarations if row.instrument_id in kept_ids]

    referenced_parties = {
        *[party_id for relation in relations for party_id in relation.party_ids],
        *[row.party_id for row in envoys],
        *[row.declarer_party_id for row in declarations],
    }
    if len(parties) > policy.max_parties:
        removable = [
            row
            for row in sorted(parties, key=lambda item: item.party_id)
            if row.party_id not in referenced_parties
        ]
        excess = len(parties) - policy.max_parties
        if excess > len(removable):
            _LOG.error("diplomacy_capacity_reached table=parties")
            _fail("diplomacy_capacity_reached")
        dropped_parties = {item.party_id for item in removable[:excess]}
        parties = [item for item in parties if item.party_id not in dropped_parties]
        notices.add("diplomacy_truncated:parties")
        _LOG.warning(
            "diplomacy_truncated table=parties dropped=%s", len(dropped_parties)
        )

    if len(relations) > policy.max_relations:
        removable_relations = [
            row
            for row in sorted(
                relations, key=lambda item: (item.opened_tick, item.relation_id)
            )
            if not any(
                instrument.relation_id == row.relation_id
                and any(
                    declaration.instrument_id == instrument.instrument_id
                    and declaration.act is DiplomaticDeclarationAct.ACCEPT
                    for declaration in declarations
                )
                for instrument in instruments
            )
        ]
        excess = len(relations) - policy.max_relations
        if excess > len(removable_relations):
            _LOG.error("diplomacy_capacity_reached table=relations")
            _fail("diplomacy_capacity_reached")
        dropped_relations = {row.relation_id for row in removable_relations[:excess]}
        relations = [
            row for row in relations if row.relation_id not in dropped_relations
        ]
        contacts = [row for row in contacts if row.relation_id not in dropped_relations]
        envoys = [row for row in envoys if row.relation_id not in dropped_relations]
        negotiations = [
            row for row in negotiations if row.relation_id not in dropped_relations
        ]
        instruments = [
            row for row in instruments if row.relation_id not in dropped_relations
        ]
        kept_ids = {row.instrument_id for row in instruments}
        declarations = [row for row in declarations if row.instrument_id in kept_ids]
        notices.add("diplomacy_truncated:relations")
        _LOG.warning(
            "diplomacy_truncated table=relations dropped=%s",
            len(dropped_relations),
        )

    def total() -> int:
        return sum(
            len(rows)
            for rows in (
                relations,
                parties,
                contacts,
                envoys,
                negotiations,
                instruments,
                declarations,
                ledger.misrepresentations,
                ledger.terminations,
                ledger.conflicts,
            )
        )

    table_order: list[tuple[str, list[Any]]] = [
        ("contacts", contacts),
        ("negotiations", negotiations),
        ("envoys", envoys),
        ("declarations", declarations),
        ("instruments", instruments),
        ("relations", relations),
    ]
    for table, rows in table_order:
        if total() <= policy.max_total_records:
            break
        excess_count = total() - policy.max_total_records
        if not rows:
            continue
        kept, dropped = _drop_oldest(rows, table=table, count=excess_count)
        if dropped:
            notices.add(f"diplomacy_truncated:{table}")
            if table == "contacts":
                contacts = list(kept)
            elif table == "negotiations":
                negotiations = list(kept)
            elif table == "envoys":
                envoys = list(kept)
            elif table == "declarations":
                declarations = list(kept)
            elif table == "instruments":
                instruments = list(kept)
                kept_ids = {row.instrument_id for row in instruments}
                declarations = [
                    row for row in declarations if row.instrument_id in kept_ids
                ]
            else:
                relations = list(kept)
                kept_relation_ids = {row.relation_id for row in relations}
                contacts = [r for r in contacts if r.relation_id in kept_relation_ids]
                envoys = [r for r in envoys if r.relation_id in kept_relation_ids]
                negotiations = [
                    r for r in negotiations if r.relation_id in kept_relation_ids
                ]
                instruments = [
                    r for r in instruments if r.relation_id in kept_relation_ids
                ]
                kept_ids = {row.instrument_id for row in instruments}
                declarations = [
                    row for row in declarations if row.instrument_id in kept_ids
                ]
    if total() > policy.max_total_records:
        _LOG.error("diplomacy_capacity_reached table=records")
        _fail("diplomacy_capacity_reached")

    after_counts = (
        len(relations),
        len(parties),
        len(contacts),
        len(envoys),
        len(negotiations),
        len(instruments),
        len(declarations),
    )
    if after_counts == before_counts:
        return ledger

    def ordered(rows: list[Any], tick_name: str, id_name: str) -> tuple[Any, ...]:
        return tuple(
            sorted(
                rows, key=lambda row: (getattr(row, tick_name), getattr(row, id_name))
            )
        )

    return _bump(
        ledger,
        notices=tuple(sorted(notices)),
        relations=ordered(relations, "opened_tick", "relation_id"),
        parties=ordered(parties, "first_seen_tick", "party_id"),
        contacts=ordered(contacts, "tick", "contact_id"),
        envoys=ordered(envoys, "accredited_tick", "envoy_id"),
        negotiations=ordered(negotiations, "opened_tick", "negotiation_id"),
        instruments=ordered(instruments, "opened_tick", "instrument_id"),
        declarations=ordered(declarations, "declared_tick", "declaration_id"),
    )


def _region_anchors(observation: object | None) -> tuple[str, ...]:
    from agents.cognition.delegation_representation import observation_region_anchors

    return observation_region_anchors(observation)


def _collective_ids(organization_concepts: object | None) -> frozenset[str]:
    if organization_concepts is None:
        return frozenset()
    return frozenset(
        str(getattr(concept, "organization_id", ""))
        for concept in getattr(organization_concepts, "concepts", ())
        if getattr(concept, "organization_id", None)
    )


def _party_resolution(
    kind: DiplomaticPartyKind,
    anchor: str | None,
    *,
    organization_concepts: object | None,
    region_anchors: Sequence[str],
) -> DiplomaticPartyResolution:
    if kind is DiplomaticPartyKind.AGENT:
        return (
            DiplomaticPartyResolution.RESOLVED
            if anchor is not None
            else DiplomaticPartyResolution.UNRESOLVED
        )
    if kind in {
        DiplomaticPartyKind.ORGANIZATION,
        DiplomaticPartyKind.COALITION,
    }:
        return (
            DiplomaticPartyResolution.RESOLVED
            if anchor is not None and anchor in _collective_ids(organization_concepts)
            else DiplomaticPartyResolution.UNRESOLVED
        )
    if kind is DiplomaticPartyKind.SETTLEMENT:
        return (
            DiplomaticPartyResolution.RESOLVED
            if anchor is not None and anchor in set(region_anchors)
            else DiplomaticPartyResolution.UNRESOLVED
        )
    return DiplomaticPartyResolution.UNRESOLVED


class _Builder:
    """Deterministic in-memory row accumulator for one update."""

    def __init__(self, ledger: DiplomacyLedger, *, owner_id: str, tick: int) -> None:
        self.owner_id = owner_id
        self.tick = tick
        self.relations = {row.relation_id: row for row in ledger.relations}
        self.parties = {row.party_id: row for row in ledger.parties}
        self.contacts = {row.contact_id: row for row in ledger.contacts}
        self.envoys = {row.envoy_id: row for row in ledger.envoys}
        self.negotiations = {row.negotiation_id: row for row in ledger.negotiations}
        self.instruments = {row.instrument_id: row for row in ledger.instruments}
        self.declarations = {row.declaration_id: row for row in ledger.declarations}
        self.misrepresentations = {
            row.misrepresentation_id: row for row in ledger.misrepresentations
        }
        self.terminations = {row.termination_id: row for row in ledger.terminations}
        self.conflicts = {row.conflict_id: row for row in ledger.conflicts}
        self.notices = set(ledger.notices)

    def self_party(self) -> str:
        party_id = diplomacy_party_id(
            self.owner_id, DiplomaticPartyKind.AGENT, self.owner_id
        )
        self.parties.setdefault(
            party_id,
            DiplomaticParty(
                party_id=party_id,
                kind=DiplomaticPartyKind.AGENT,
                anchor_ref=self.owner_id,
                resolution=DiplomaticPartyResolution.RESOLVED,
                first_seen_tick=self.tick,
                provenance=DiplomaticProvenance.SELF_DECLARED,
            ),
        )
        return party_id

    def add_party(
        self,
        kind: DiplomaticPartyKind,
        anchor: str | None,
        *,
        resolution: DiplomaticPartyResolution,
        provenance: DiplomaticProvenance,
    ) -> str:
        party_id = diplomacy_party_id(self.owner_id, kind, anchor)
        self.parties.setdefault(
            party_id,
            DiplomaticParty(
                party_id=party_id,
                kind=kind,
                anchor_ref=anchor,
                resolution=resolution,
                first_seen_tick=self.tick,
                provenance=provenance,
            ),
        )
        return party_id

    def add_relation(
        self,
        party_ids: Sequence[str],
        *,
        provenance: DiplomaticProvenance,
    ) -> str:
        self_party = self.self_party()
        ordered = (
            self_party,
            *(party_id for party_id in party_ids if party_id != self_party),
        )
        unique = tuple(dict.fromkeys(ordered))
        anchors = tuple(
            self.parties[party_id].anchor_ref or self.parties[party_id].party_id
            for party_id in sorted(unique)
        )
        relation_id = diplomacy_relation_id(self.owner_id, anchors)
        existing = self.relations.get(relation_id)
        if existing is None:
            self.relations[relation_id] = DiplomaticRelation(
                relation_id=relation_id,
                party_ids=unique,
                opened_tick=self.tick,
                last_tick=self.tick,
                provenance=provenance,
            )
        elif existing.last_tick != self.tick:
            self.relations[relation_id] = replace(existing, last_tick=self.tick)
        return relation_id

    def add_contact(
        self,
        relation_id: str,
        *,
        contact_kind: DiplomaticContactKind,
        location_anchor: str | None,
        participant_count: int,
        provenance: DiplomaticProvenance,
        source_ref: str | None,
    ) -> None:
        contact_id = diplomacy_contact_id(
            self.owner_id,
            relation_id,
            self.tick,
            contact_kind,
            location_anchor,
            source_ref,
        )
        self.contacts.setdefault(
            contact_id,
            DiplomaticContact(
                contact_id=contact_id,
                relation_id=relation_id,
                tick=self.tick,
                contact_kind=contact_kind,
                location_anchor=location_anchor,
                participant_count=participant_count,
                provenance=provenance,
                source_ref=source_ref,
            ),
        )

    def add_envoy(
        self,
        relation_id: str,
        party_id: str,
        envoy_ref: str,
        mandate_ref: str | None,
        *,
        representation: object | None,
        policy: DiplomacyPolicy,
        end_tick: int | None,
        provenance: DiplomaticProvenance,
        tick: int | None = None,
    ) -> str:
        current_tick = self.tick if tick is None else tick
        revision = sum(
            1
            for row in self.envoys.values()
            if row.relation_id == relation_id
            and row.party_id == party_id
            and row.envoy_ref == envoy_ref
        )
        envoy_id = diplomacy_envoy_id(
            self.owner_id,
            relation_id,
            party_id,
            envoy_ref,
            current_tick,
            revision,
        )
        existing = self.envoys.get(envoy_id)
        if existing is not None:
            return envoy_id
        provisional = DiplomaticEnvoy(
            envoy_id=envoy_id,
            relation_id=relation_id,
            party_id=party_id,
            envoy_ref=envoy_ref,
            mandate_ref=mandate_ref,
            status=DiplomaticEnvoyStatus.CLAIMED,
            accredited_tick=current_tick,
            end_tick=end_tick,
            revision=revision,
            provenance=provenance,
        )
        status = diplomacy_envoy_status(
            provisional, representation, tick=current_tick, policy=policy
        )
        self.envoys[envoy_id] = replace(provisional, status=status)
        return envoy_id

    def add_negotiation(
        self,
        relation_id: str,
        *,
        topic_subject: str,
        envoy_refs: Sequence[str],
        term_kind: DiplomaticTermKind,
        provenance: DiplomaticProvenance,
    ) -> str:
        revision = sum(
            1
            for row in self.negotiations.values()
            if row.relation_id == relation_id and row.topic_subject == topic_subject
        )
        negotiation_id = diplomacy_negotiation_id(
            self.owner_id, relation_id, topic_subject, self.tick, revision
        )
        self.negotiations.setdefault(
            negotiation_id,
            DiplomaticNegotiation(
                negotiation_id=negotiation_id,
                relation_id=relation_id,
                topic_subject=topic_subject,
                status=DiplomaticNegotiationStatus.OPENED,
                opened_tick=self.tick,
                last_tick=self.tick,
                envoy_refs=tuple(envoy_refs),
                term_kind=term_kind,
                provenance=provenance,
                revision=revision,
            ),
        )
        return negotiation_id

    def add_instrument(
        self,
        relation_id: str,
        *,
        kind: DiplomaticInstrumentKind,
        topic_subject: str,
        term_kind: DiplomaticTermKind,
        opener_envoy_ref: str | None,
        end_tick: int | None,
        anchor_refs: Sequence[str],
        provenance: DiplomaticProvenance,
    ) -> str:
        relation = self.relations[relation_id]
        instrument_id = diplomacy_instrument_id(
            self.owner_id, relation_id, kind, topic_subject, self.tick
        )
        self.instruments.setdefault(
            instrument_id,
            DiplomaticInstrument(
                instrument_id=instrument_id,
                relation_id=relation_id,
                party_ids=relation.party_ids,
                kind=kind,
                term_kind=term_kind,
                topic_subject=topic_subject,
                opener_envoy_ref=opener_envoy_ref,
                opened_tick=self.tick,
                end_tick=end_tick,
                anchor_refs=tuple(anchor_refs),
                revision=0,
                provenance=provenance,
            ),
        )
        return instrument_id

    def add_declaration(
        self,
        instrument_id: str,
        *,
        declarer_party_id: str,
        envoy_ref: str | None,
        act: DiplomaticDeclarationAct,
        provenance: DiplomaticProvenance,
        independence_ref: str | None,
        revision: int,
        tick: int | None = None,
    ) -> str:
        current_tick = self.tick if tick is None else tick
        declaration_id = diplomacy_declaration_id(
            self.owner_id,
            instrument_id,
            declarer_party_id,
            act,
            current_tick,
            revision,
        )
        self.declarations.setdefault(
            declaration_id,
            DiplomaticDeclaration(
                declaration_id=declaration_id,
                instrument_id=instrument_id,
                declarer_party_id=declarer_party_id,
                envoy_ref=envoy_ref,
                act=act,
                declared_tick=current_tick,
                provenance=provenance,
                independence_ref=independence_ref,
                revision=revision,
            ),
        )
        return declaration_id

    def build(self) -> DiplomacyLedger:
        def ordered(
            rows: Mapping[str, Any], tick_name: str, id_name: str
        ) -> tuple[Any, ...]:
            return tuple(
                sorted(
                    rows.values(),
                    key=lambda row: (getattr(row, tick_name), getattr(row, id_name)),
                )
            )

        return DiplomacyLedger(
            owner_id=self.owner_id,
            tick=self.tick,
            revision=1,
            relations=ordered(self.relations, "opened_tick", "relation_id"),
            parties=ordered(self.parties, "first_seen_tick", "party_id"),
            contacts=ordered(self.contacts, "tick", "contact_id"),
            envoys=ordered(self.envoys, "accredited_tick", "envoy_id"),
            negotiations=ordered(self.negotiations, "opened_tick", "negotiation_id"),
            instruments=ordered(self.instruments, "opened_tick", "instrument_id"),
            declarations=ordered(self.declarations, "declared_tick", "declaration_id"),
            misrepresentations=ordered(
                self.misrepresentations, "observed_tick", "misrepresentation_id"
            ),
            terminations=ordered(self.terminations, "tick", "termination_id"),
            conflicts=ordered(self.conflicts, "observed_tick", "conflict_id"),
            notices=tuple(sorted(self.notices)),
        )


_ACT_TO_INSTRUMENT: Final[Mapping[str, DiplomaticInstrumentKind]] = MappingProxyType(
    {
        "dip_propose": DiplomaticInstrumentKind.PROPOSAL,
        "dip_promise": DiplomaticInstrumentKind.PROMISE,
        "dip_dispute": DiplomaticInstrumentKind.DISPUTE,
        "dip_shared_project": DiplomaticInstrumentKind.SHARED_PROJECT,
    }
)
_FRAME_TO_DECLARATION: Final[Mapping[str, DiplomaticDeclarationAct]] = MappingProxyType(
    {
        "dip_propose": DiplomaticDeclarationAct.PROPOSE,
        "dip_promise": DiplomaticDeclarationAct.PROMISE,
        "dip_accept": DiplomaticDeclarationAct.ACCEPT,
        "dip_reject": DiplomaticDeclarationAct.REJECT,
        "dip_withdraw": DiplomaticDeclarationAct.WITHDRAW,
        "dip_dispute": DiplomaticDeclarationAct.DISPUTE,
        "dip_shared_project": DiplomaticDeclarationAct.SHARED_PROJECT,
        "dip_report": DiplomaticDeclarationAct.REPORT,
    }
)


def _frame_party(
    builder: _Builder,
    frame: object,
    *,
    organization_concepts: object | None,
    region_anchors: Sequence[str],
    provenance: DiplomaticProvenance,
) -> tuple[DiplomaticPartyKind, str | None, str]:
    kind = getattr(frame, "party_kind", None) or DiplomaticPartyKind.AGENT
    anchor = getattr(frame, "party_ref", None)
    if anchor is None:
        return DiplomaticPartyKind.AGENT, builder.owner_id, builder.self_party()
    resolution = _party_resolution(
        kind,
        anchor,
        organization_concepts=organization_concepts,
        region_anchors=region_anchors,
    )
    if resolution is not DiplomaticPartyResolution.RESOLVED:
        _LOG.warning("diplomacy_party_unresolved kind=%s", kind.value)
    party_id = builder.add_party(
        kind, anchor, resolution=resolution, provenance=provenance
    )
    return kind, anchor, party_id


def _resolve_party_id(
    builder: _Builder,
    kind: DiplomaticPartyKind,
    anchor: str | None,
    *,
    organization_concepts: object | None,
    region_anchors: Sequence[str],
    provenance: DiplomaticProvenance,
) -> str:
    if anchor is None:
        return builder.self_party()
    resolution = _party_resolution(
        kind,
        anchor,
        organization_concepts=organization_concepts,
        region_anchors=region_anchors,
    )
    if resolution is not DiplomaticPartyResolution.RESOLVED:
        _LOG.warning("diplomacy_party_unresolved kind=%s", kind.value)
    return builder.add_party(kind, anchor, resolution=resolution, provenance=provenance)


def _process_frame(
    builder: _Builder,
    frame: object,
    *,
    policy: DiplomacyPolicy,
    representation: object | None,
    organization_concepts: object | None,
    region_anchors: Sequence[str],
    anchor_refs: Sequence[str],
    provenance: DiplomaticProvenance,
) -> None:
    from agents.cognition.diplomacy_communication import DiplomaticAct

    act = getattr(frame, "act", None)
    if type(act) is not DiplomaticAct:
        return
    owner = builder.owner_id
    actor = getattr(frame, "actor_ref", None) or getattr(frame, "envoy_ref", None)
    kind = getattr(frame, "party_kind", None) or DiplomaticPartyKind.AGENT
    party_anchor = getattr(frame, "party_ref", None)
    envoy_ref = getattr(frame, "envoy_ref", None)

    declaration_acts = {
        DiplomaticAct.ACCEPT,
        DiplomaticAct.REJECT,
        DiplomaticAct.WITHDRAW,
        DiplomaticAct.REPORT,
    }
    if act in declaration_acts:
        instrument_id = getattr(frame, "instrument_ref", None)
        instrument = builder.instruments.get(instrument_id or "")
        if instrument is None:
            builder.notices.add("diplomacy_unknown_instrument")
            return
        declarer_anchor = party_anchor or (owner if actor == owner else actor)
        declarer_party = _resolve_party_id(
            builder,
            kind if party_anchor else DiplomaticPartyKind.AGENT,
            declarer_anchor,
            organization_concepts=organization_concepts,
            region_anchors=region_anchors,
            provenance=provenance,
        )
        if declarer_party not in instrument.party_ids:
            _fail("diplomacy_party_set_invalid")
        declaration_envoy = (
            actor
            if actor is not None and actor not in {declarer_anchor, owner}
            else None
        )
        if declaration_envoy is not None and not any(
            row.relation_id == instrument.relation_id
            and row.envoy_ref == declaration_envoy
            for row in builder.envoys.values()
        ):
            builder.add_envoy(
                instrument.relation_id,
                declarer_party,
                declaration_envoy,
                getattr(frame, "mandate_ref", None),
                representation=representation,
                policy=policy,
                end_tick=getattr(frame, "end_tick", None),
                provenance=provenance,
            )
        for row in builder.declarations.values():
            if (
                row.instrument_id == instrument_id
                and declaration_envoy is not None
                and row.envoy_ref == declaration_envoy
                and row.declarer_party_id != declarer_party
            ):
                builder.notices.add("diplomacy_party_duplicate")
                return
        if declaration_envoy is not None and type(declaration_envoy) is not str:
            _fail("diplomacy_party_set_invalid")
        builder.add_declaration(
            instrument_id,  # type: ignore[arg-type]
            declarer_party_id=declarer_party,
            envoy_ref=declaration_envoy,
            act=_FRAME_TO_DECLARATION[act.value],
            provenance=provenance,
            independence_ref=getattr(frame, "declaration_ref", None),
            revision=getattr(frame, "revision", 0),
        )
        return

    counterparty_anchor = party_anchor or actor or owner
    counterparty_party = _resolve_party_id(
        builder,
        kind,
        counterparty_anchor,
        organization_concepts=organization_concepts,
        region_anchors=region_anchors,
        provenance=provenance,
    )
    relation = getattr(frame, "relation_ref", None)
    if relation not in builder.relations:
        relation = builder.add_relation((counterparty_party,), provenance=provenance)

    if act is DiplomaticAct.CONTACT:
        contact_kind = (
            DiplomaticContactKind.MEDIATED_MESSAGE
            if actor in {None, owner, counterparty_anchor}
            else DiplomaticContactKind.THIRD_PARTY_REPORT
        )
        builder.add_contact(
            relation,
            contact_kind=contact_kind,
            location_anchor=None,
            participant_count=2,
            provenance=provenance,
            source_ref=getattr(frame, "declaration_ref", None),
        )
        _LOG.debug("diplomacy_contact_recorded kind=%s", contact_kind.value)
        return

    if act is DiplomaticAct.ACCREDIT:
        envoy_party = (
            builder.self_party() if actor in {None, owner} else counterparty_party
        )
        builder.add_envoy(
            relation,
            envoy_party,
            envoy_ref or owner,
            getattr(frame, "mandate_ref", None),
            representation=representation,
            policy=policy,
            end_tick=getattr(frame, "end_tick", None),
            provenance=provenance,
        )
        return

    if act is DiplomaticAct.RECALL:
        matching = [
            row
            for row in builder.envoys.values()
            if row.relation_id == relation and row.envoy_ref == (envoy_ref or owner)
        ]
        if not matching:
            builder.notices.add("diplomacy_unknown_envoy")
            return
        target = max(matching, key=lambda row: (row.accredited_tick, row.envoy_id))
        termination_id = diplomacy_termination_id(
            builder.owner_id,
            "envoy",
            target.envoy_id,
            DiplomaticTerminationKind.ENVOY_RECALLED,
            builder.tick,
        )
        builder.terminations.setdefault(
            termination_id,
            DiplomaticTermination(
                termination_id=termination_id,
                target_kind="envoy",
                target_ref=target.envoy_id,
                kind=DiplomaticTerminationKind.ENVOY_RECALLED,
                tick=builder.tick,
                provenance=provenance,
            ),
        )
        return

    if act is DiplomaticAct.OPEN_NEGOTIATION:
        envoy_rows = {
            row.envoy_ref
            for row in builder.envoys.values()
            if row.relation_id == relation
        }
        negotiating = (envoy_ref,) if envoy_ref in envoy_rows else ()
        builder.add_negotiation(
            relation,
            topic_subject=frame.topic_subject,
            envoy_refs=negotiating,
            term_kind=getattr(frame, "term_kind", None) or DiplomaticTermKind.UNKNOWN,
            provenance=provenance,
        )
        return

    if act.value in _ACT_TO_INSTRUMENT:
        instrument_kind = _ACT_TO_INSTRUMENT[act.value]
        topic = frame.topic_subject
        if actor in {None, owner}:
            declarer_party = builder.self_party()
            declaration_envoy = None
        else:
            declarer_party = counterparty_party
            declaration_envoy = actor if actor != counterparty_anchor else None
        if declaration_envoy is not None and not any(
            row.relation_id == relation and row.envoy_ref == declaration_envoy
            for row in builder.envoys.values()
        ):
            builder.add_envoy(
                relation,
                declarer_party,
                declaration_envoy,
                getattr(frame, "mandate_ref", None),
                representation=representation,
                policy=policy,
                end_tick=getattr(frame, "end_tick", None),
                provenance=provenance,
            )
        instrument_id = builder.add_instrument(
            relation,
            kind=instrument_kind,
            topic_subject=topic,
            term_kind=getattr(frame, "term_kind", None) or DiplomaticTermKind.UNKNOWN,
            opener_envoy_ref=declaration_envoy,
            end_tick=getattr(frame, "end_tick", None),
            anchor_refs=anchor_refs,
            provenance=provenance,
        )
        if declaration_envoy is not None and type(declaration_envoy) is not str:
            _fail("diplomacy_party_set_invalid")
        builder.add_declaration(
            instrument_id,
            declarer_party_id=declarer_party,
            envoy_ref=declaration_envoy,
            act=_FRAME_TO_DECLARATION[act.value],
            provenance=provenance,
            independence_ref=getattr(frame, "declaration_ref", None),
            revision=getattr(frame, "revision", 0),
        )
        return


def _apply_frames(
    builder: _Builder,
    frames: Sequence[object],
    *,
    policy: DiplomacyPolicy,
    representation: object | None,
    organization_concepts: object | None,
    observation: object | None,
    anchor_refs: Sequence[str],
) -> None:
    region_anchors = _region_anchors(observation)
    rank = {
        "dip_contact": 0,
        "dip_accredit": 1,
        "dip_recall": 2,
        "dip_open_negotiation": 3,
        "dip_propose": 4,
        "dip_promise": 4,
        "dip_dispute": 4,
        "dip_shared_project": 4,
        "dip_accept": 5,
        "dip_reject": 5,
        "dip_withdraw": 5,
        "dip_report": 5,
    }
    ordered = sorted(
        frames,
        key=lambda frame: (
            rank.get(getattr(getattr(frame, "act", None), "value", ""), 9),
            getattr(frame, "relation_ref", None) or "",
            getattr(frame, "instrument_ref", None) or "",
            getattr(frame, "topic_subject", None) or "",
            getattr(frame, "revision", 0),
            getattr(frame, "envoy_ref", None) or "",
        ),
    )
    for frame in ordered:
        _process_frame(
            builder,
            frame,
            policy=policy,
            representation=representation,
            organization_concepts=organization_concepts,
            region_anchors=region_anchors,
            anchor_refs=anchor_refs,
            provenance=getattr(frame, "provenance", None)
            or DiplomaticProvenance.COMMUNICATED,
        )


def _apply_contact_anchors(
    builder: _Builder, observation: object | None, *, owner_id: str
) -> None:
    from agents.cognition.diplomacy_communication import (
        diplomacy_contact_anchors_from_observation,
    )

    for anchor in diplomacy_contact_anchors_from_observation(
        observation, owner_id=owner_id
    ):
        party_ids: list[str] = []
        for ref in anchor.participant_refs:
            party_ids.append(
                builder.add_party(
                    DiplomaticPartyKind.AGENT,
                    ref,
                    resolution=DiplomaticPartyResolution.RESOLVED,
                    provenance=DiplomaticProvenance.WITNESSED_CONTACT,
                )
            )
        if not party_ids:
            continue
        relation_id = builder.add_relation(
            tuple(party_ids), provenance=DiplomaticProvenance.WITNESSED_CONTACT
        )
        builder.add_contact(
            relation_id,
            contact_kind=anchor.contact_kind,
            location_anchor=anchor.location_anchor,
            participant_count=anchor.participant_count,
            provenance=DiplomaticProvenance.WITNESSED_CONTACT,
            source_ref=anchor.source_ref,
        )
    if observation is not None:
        _LOG.debug(
            "diplomacy_prepare relations=%s contacts=%s envoys=%s negotiations=%s",
            len(builder.relations),
            len(builder.contacts),
            len(builder.envoys),
            len(builder.negotiations),
        )


def detect_diplomatic_misrepresentation(
    ledger: DiplomacyLedger,
    representation: object | None,
    *,
    tick: int,
    policy: DiplomacyPolicy,
) -> DiplomacyLedger:
    """Derive retained misrepresentation observations. Never truth or guilt."""

    if type(ledger) is not DiplomacyLedger:
        raise TypeError("ledger must be DiplomacyLedger")
    if type(policy) is not DiplomacyPolicy:
        raise TypeError("policy must be DiplomacyPolicy")
    _require_tick(tick)
    by_instrument: dict[str, list[DiplomaticDeclaration]] = {}
    for declaration in ledger.declarations:
        by_instrument.setdefault(declaration.instrument_id, []).append(declaration)
    instrument_by_id = {row.instrument_id: row for row in ledger.instruments}
    authority_acts = {
        DiplomaticDeclarationAct.ACCEPT,
        DiplomaticDeclarationAct.PROMISE,
        DiplomaticDeclarationAct.DISPUTE,
        DiplomaticDeclarationAct.SHARED_PROJECT,
        DiplomaticDeclarationAct.PROPOSE,
    }
    rows = {row.misrepresentation_id: row for row in ledger.misrepresentations}

    def add(
        declaration: DiplomaticDeclaration,
        kind: DiplomaticMisrepresentationKind,
    ) -> None:
        row_id = diplomacy_misrepresentation_id(
            ledger.owner_id,
            declaration.instrument_id,
            kind,
            declaration.declaration_id,
        )
        rows.setdefault(
            row_id,
            DiplomaticMisrepresentation(
                misrepresentation_id=row_id,
                instrument_id=declaration.instrument_id,
                kind=kind,
                observed_tick=tick,
                envoy_ref=declaration.envoy_ref or "",
                declarer_party_id=declaration.declarer_party_id,
                provenance=DiplomaticProvenance.REPRESENTATION_BELIEF,
            ),
        )

    for declaration in ledger.declarations:
        if declaration.envoy_ref is None:
            continue
        instrument = instrument_by_id.get(declaration.instrument_id)
        if instrument is None:
            continue
        envoy = next(
            (
                row
                for row in ledger.envoys
                if row.relation_id == instrument.relation_id
                and row.envoy_ref == declaration.envoy_ref
            ),
            None,
        )
        if envoy is None:
            continue
        status = diplomacy_envoy_status(envoy, representation, tick=tick, policy=policy)
        if declaration.act in authority_acts and status is not (
            DiplomaticEnvoyStatus.RECOGNIZED
        ):
            add(declaration, DiplomaticMisrepresentationKind.MANDATE_UNRECOGNIZED)
        if status is DiplomaticEnvoyStatus.RECOGNIZED:
            mandate = _mandate_for(envoy, representation)
            if mandate is not None and not diplomacy_scope_covers(
                scope_kind=getattr(mandate, "scope_kind", None),
                duration_kind=getattr(mandate, "duration_kind", None),
                instrument_kind=instrument.kind,
                scope_subject=getattr(mandate, "scope_subject", None),
                topic_subject=instrument.topic_subject,
            ):
                add(declaration, DiplomaticMisrepresentationKind.SCOPE_EXCEEDED)
        for other in by_instrument.get(declaration.instrument_id, ()):
            if other.declaration_id == declaration.declaration_id:
                continue
            if (
                declaration.act is DiplomaticDeclarationAct.ACCEPT
                and other.envoy_ref is None
                and other.declarer_party_id == declaration.declarer_party_id
                and other.act
                in {
                    DiplomaticDeclarationAct.REJECT,
                    DiplomaticDeclarationAct.WITHDRAW,
                }
                and other.declared_tick > declaration.declared_tick
            ):
                add(
                    declaration,
                    DiplomaticMisrepresentationKind.CONTRADICTED_BY_PRINCIPAL,
                )
            if (
                declaration.act is DiplomaticDeclarationAct.ACCEPT
                and other.envoy_ref is None
                and other.declarer_party_id != declaration.declarer_party_id
                and other.act is DiplomaticDeclarationAct.REJECT
                and other.declared_tick >= declaration.declared_tick
            ):
                add(
                    declaration,
                    DiplomaticMisrepresentationKind.CONTESTED_BY_MEMBER,
                )

    if set(rows) == {row.misrepresentation_id for row in ledger.misrepresentations}:
        return ledger
    for row in rows.values():
        _LOG.info("diplomacy_misrepresentation_recorded kind=%s", row.kind.value)
    return _bump(
        ledger,
        misrepresentations=tuple(
            sorted(
                rows.values(),
                key=lambda item: (item.observed_tick, item.misrepresentation_id),
            )
        ),
    )


def apply_diplomacy_update(
    *,
    owner_id: object,
    tick: int,
    observation: object,
    prior: DiplomacyLedger | None,
    frames: Sequence[object] = (),
    representation: object | None = None,
    organization_concepts: object | None = None,
    collective_decisions: object | None = None,
    structured_commitments: object | None = None,
    disputes: object | None = None,
    evidence: object | None = None,
    policy: DiplomacyPolicy | None = None,
    anchor_refs: Sequence[str] = (),
) -> DiplomacyLedger:
    """Fold owner-visible evidence and speech into one diplomacy ledger."""

    active_policy = default_diplomacy_policy() if policy is None else policy
    if type(active_policy) is not DiplomacyPolicy:
        raise TypeError("policy must be DiplomacyPolicy")
    owner = _owner_text(owner_id)
    current_tick = _require_tick(tick)
    if prior is not None:
        if type(prior) is not DiplomacyLedger:
            raise TypeError("prior must be DiplomacyLedger or None")
        if prior.owner_id != owner:
            _fail("diplomacy_owner_mismatch")
        if prior.tick > current_tick:
            _fail("diplomacy_invalid_tick")
    base = prior or empty_diplomacy_ledger(owner, tick=current_tick)
    builder = _Builder(base, owner_id=owner, tick=max(current_tick, base.tick))
    _apply_contact_anchors(builder, observation, owner_id=owner)
    from agents.cognition.diplomacy_communication import (
        diplomacy_frames_from_observation,
    )

    observed_frames = diplomacy_frames_from_observation(observation, owner_id=owner)
    _apply_frames(
        builder,
        (*observed_frames, *frames),
        policy=active_policy,
        representation=representation,
        organization_concepts=organization_concepts,
        observation=observation,
        anchor_refs=anchor_refs,
    )
    ledger = builder.build()
    ledger = detect_diplomatic_misrepresentation(
        ledger, representation, tick=current_tick, policy=active_policy
    )
    ledger = expire_diplomacy_records(ledger, tick=current_tick, policy=active_policy)
    ledger = supersede_diplomacy_instruments(ledger)
    ledger = detect_diplomacy_conflicts(ledger)
    return enforce_diplomacy_limits(ledger, policy=active_policy)


def record_diplomacy_utterance(
    ledger: DiplomacyLedger,
    command: object,
    *,
    owner_id: object,
    tick: int,
    representation: object | None = None,
    organization_concepts: object | None = None,
    collective_decisions: object | None = None,
    structured_commitments: object | None = None,
    disputes: object | None = None,
    evidence: object | None = None,
    policy: DiplomacyPolicy | None = None,
    anchor_refs: Sequence[str] = (),
) -> DiplomacyLedger:
    """Record the owner's own already-selected ``dip_v1`` speech."""

    if type(ledger) is not DiplomacyLedger:
        raise TypeError("ledger must be DiplomacyLedger")
    owner = _owner_text(owner_id)
    if ledger.owner_id != owner:
        _fail("diplomacy_owner_mismatch")
    current_tick = _require_tick(tick)
    if current_tick < ledger.tick:
        _fail("diplomacy_invalid_tick")
    active_policy = default_diplomacy_policy() if policy is None else policy
    if type(active_policy) is not DiplomacyPolicy:
        raise TypeError("policy must be DiplomacyPolicy")
    from agents.cognition.diplomacy_communication import (
        diplomacy_frames_from_command,
    )

    frames = diplomacy_frames_from_command(command, owner_id=owner)
    if not frames:
        return ledger
    builder = _Builder(ledger, owner_id=owner, tick=max(current_tick, ledger.tick))
    _apply_frames(
        builder,
        frames,
        policy=active_policy,
        representation=representation,
        organization_concepts=organization_concepts,
        observation=None,
        anchor_refs=anchor_refs,
    )
    return builder.build()


def claim_diplomacy_completion(
    ledger: DiplomacyLedger,
    *,
    instrument_id: str,
    declarer_party_id: str,
    tick: int,
    provenance: DiplomaticProvenance = DiplomaticProvenance.COMMUNICATED,
) -> DiplomacyLedger:
    """Append the owner's own completion claim. Never verifies completion."""

    if type(ledger) is not DiplomacyLedger:
        raise TypeError("ledger must be DiplomacyLedger")
    instrument = next(
        (row for row in ledger.instruments if row.instrument_id == instrument_id),
        None,
    )
    if instrument is None:
        _fail("diplomacy_unknown_instrument")
    if declarer_party_id not in instrument.party_ids:
        _fail("diplomacy_party_set_invalid")
    if instrument.kind not in {
        DiplomaticInstrumentKind.PROMISE,
        DiplomaticInstrumentKind.SHARED_PROJECT,
    }:
        _fail("diplomacy_instrument_kind_mismatch")
    declaration_id = diplomacy_declaration_id(
        ledger.owner_id,
        instrument_id,
        declarer_party_id,
        DiplomaticDeclarationAct.REPORT,
        tick,
        0,
    )
    if any(row.declaration_id == declaration_id for row in ledger.declarations):
        return ledger
    row = DiplomaticDeclaration(
        declaration_id=declaration_id,
        instrument_id=instrument_id,
        declarer_party_id=declarer_party_id,
        envoy_ref=None,
        act=DiplomaticDeclarationAct.REPORT,
        declared_tick=tick,
        provenance=provenance,
        independence_ref=_COMPLETION_CLAIM_MARKER,
        revision=0,
    )
    return _bump(
        ledger,
        tick=tick,
        declarations=tuple(
            sorted(
                (*ledger.declarations, row),
                key=lambda item: (item.declared_tick, item.declaration_id),
            )
        ),
    )
