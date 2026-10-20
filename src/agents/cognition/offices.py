"""Owner-scoped subjective office concepts and recognized-role succession.

An office concept is one owner's private belief that a *persistent recognized
role* exists, independent of whoever currently occupies it. It is never an
objective entity, a world permission, an engine-declared legitimacy, or a
predefined job. Owners may disagree about the role, its duties, its expected
authority, whether an occupant left, and who should replace them.

Updates read only one owner's ``Observation``, owner-safe identity projection,
previous ``OfficeConceptLedger``, and delivered structured testimony. They never
read ``WorldState``, ``WorldEvent``, another owner's ledger, or analysis rows.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any, Final, cast

from agents.cognition.models import ActionDirection, OwnerSafeSocialIdentity
from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int
from world.observations import Observation

__all__ = [
    "FORBIDDEN_OFFICE_CONCEPT_FIELD_NAMES",
    "OFFICE_CONCEPT_POLICY_VERSION",
    "OfficeAuthorityBelief",
    "OfficeAuthorityKind",
    "OfficeConcept",
    "OfficeConceptLedger",
    "OfficeConceptPolicy",
    "OfficeConceptStatus",
    "OfficeDutyBelief",
    "OfficeDutyKind",
    "OfficeEvidence",
    "OfficeEvidenceChannel",
    "OfficeFunction",
    "OfficeOccupantClaim",
    "OfficeOccupantStatus",
    "OfficeRecognitionAppraisal",
    "OfficeRevisionKind",
    "OfficeRevisionRecord",
    "OfficeSuccessionKind",
    "OfficeSuccessionRecord",
    "OfficeSupportRecord",
    "appraise_office_recognition",
    "default_office_concept_policy",
    "empty_office_concept_ledger",
    "office_communicate_utterance",
    "office_concept_id",
    "office_direction_preference",
    "office_evidence_id",
    "office_inception_digest",
    "office_role_signature",
    "require_owner_offices",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.offices")

OFFICE_CONCEPT_POLICY_VERSION: Final[str] = "offices-succession.v1"
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_RECOGNITION_FLOOR: Final[float] = 0.45
_CHANNEL_FLOOR: Final[float] = 0.30
_RETIRE_STRENGTH: Final[float] = 0.10
_DECAY: Final[float] = 0.03
_PROMOTION_COUNT: Final[int] = 3
_PROMOTION_ROOTS: Final[int] = 2
_PREFERENCE_MARGIN: Final[float] = 0.10
_UTTERANCE_INTERVAL: Final[int] = 4
_MAX_CONCEPTS: Final[int] = 16
_MAX_EVIDENCE: Final[int] = 48
_MAX_DUTIES: Final[int] = 8
_MAX_AUTHORITIES: Final[int] = 8
_MAX_OCCUPANTS: Final[int] = 8
_MAX_SUPPORTERS: Final[int] = 16
_MAX_SUCCESSIONS: Final[int] = 16
_MAX_REVISIONS: Final[int] = 16
_MAX_NOTICES: Final[int] = 16
_FUNCTION_DELTA: Final[float] = 0.12
_EXPECTATION_DELTA: Final[float] = 0.10
_ENDORSEMENT_DELTA: Final[float] = 0.12
_COMMUNICATED_DELTA: Final[float] = 0.08
_REMEMBERED_DELTA: Final[float] = 0.05
_LOSS_DELTA: Final[float] = 0.20
_SUPPORT_DELTA: Final[float] = 0.10
_OPPOSITION_DELTA: Final[float] = 0.12

_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_DIGEST_LEN: Final[int] = 16

_OFFICE_PREDICATE: Final[str] = "office_role"
_OFFICE_DUTY_PREDICATE: Final[str] = "office_duty"
_OFFICE_AUTHORITY_PREDICATE: Final[str] = "office_authority"
_OFFICE_ENDORSE_PREDICATE: Final[str] = "office_endorse"
_OFFICE_DISPUTE_PREDICATE: Final[str] = "office_dispute"
_OFFICE_RELINQUISH_PREDICATE: Final[str] = "office_relinquish"
_OFFICE_SUCCESSION_PREDICATE: Final[str] = "office_succession"

_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "cap_exceeded",
        "unresolved_entity",
        "unresolved_office",
        "ambiguous_office",
        "unsupported_evidence",
        "duplicate_evidence",
        "foreign_owner",
        "invalid_token",
        "influence_only",
        "missing_independent_root",
        "insufficient_recurrence",
        "no_role_directed_evidence",
        "self_endorsement",
        "duplicate_root",
    }
)

_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {
        "MetricDocument",
        "MetricComputationInputs",
        "InstitutionCandidateRow",
        "InstitutionEmergenceResult",
        "InstitutionPersistenceRow",
        "OfficeContinuityRow",
        "OfficeSuccessionRow",
    }
)

FORBIDDEN_OFFICE_CONCEPT_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "government",
        "religion",
        "religious_body",
        "court",
        "police",
        "corporation",
        "political_party",
        "institution",
        "institution_id",
        "institution_type",
        "office_type",
        "rank",
        "title",
        "election",
        "vote",
        "tax",
        "law",
        "state",
        "current_occupant",
    }
)


class OfficeFunction(StrEnum):
    """Closed functions grounded in existing observed action kinds."""

    COLLECTIVE_PROJECT = "collective_project"
    PUBLIC_GOOD = "public_good"
    REPOSITORY = "repository"
    TEACHING = "teaching"
    HELP = "help"
    EXCHANGE = "exchange"
    COORDINATION = "coordination"
    CONFLICT_MEDIATION = "conflict_mediation"


class OfficeEvidenceChannel(StrEnum):
    """Closed provenance for one item of office evidence."""

    OBSERVED = "observed"
    COMMUNICATED = "communicated"
    REMEMBERED = "remembered"


class OfficeConceptStatus(StrEnum):
    """Closed lifecycle for one owner's office concept."""

    PROPOSED = "proposed"
    RECOGNIZED = "recognized"
    DISPUTED = "disputed"
    VACANT = "vacant"
    FADING = "fading"
    ABANDONED = "abandoned"


class OfficeOccupantStatus(StrEnum):
    """Closed epistemic status of one occupant claim."""

    CANDIDATE = "candidate"
    PREFERRED = "preferred"
    DISPUTED = "disputed"
    OPPOSED = "opposed"
    UNCERTAIN = "uncertain"


class OfficeDutyKind(StrEnum):
    """Duties are recognized expectations, never engine-enforced rules."""

    PERFORM = "perform"
    COORDINATE = "coordinate"
    MAINTAIN = "maintain"
    TRANSMIT = "transmit"
    MEDIATE = "mediate"


class OfficeAuthorityKind(StrEnum):
    """Expected authority is a revisable belief, never a permission."""

    DEFERENCE = "deference"
    REQUEST = "request"
    COORDINATION = "coordination"
    ACCESS = "access"
    ALLOCATION = "allocation"


class OfficeRevisionKind(StrEnum):
    """Closed reason for retaining a role revision."""

    DUTY_REVISED = "duty_revised"
    AUTHORITY_REVISED = "authority_revised"
    LABEL_REVISED = "label_revised"


class OfficeSuccessionKind(StrEnum):
    """Closed succession/loss transitions."""

    OCCUPANT_LOST = "occupant_lost"
    OCCUPANT_ABSENT = "occupant_absent"
    OCCUPANT_RETURNED = "occupant_returned"
    OCCUPANT_RELINQUISHED = "occupant_relinquished"
    SUCCESSOR_PROPOSED = "successor_proposed"
    SUCCESSION_DISPUTED = "succession_disputed"
    ABANDONED = "abandoned"
    ROLE_CHANGED = "role_changed"


_FUNCTION_BY_OCCURRENCE: Final[Mapping[str, OfficeFunction]] = {
    "collective_project_contributed": OfficeFunction.COLLECTIVE_PROJECT,
    "collective_project_started": OfficeFunction.COLLECTIVE_PROJECT,
    "public_good_maintained": OfficeFunction.PUBLIC_GOOD,
    "public_good_contributed": OfficeFunction.PUBLIC_GOOD,
    "repository_member_deposited": OfficeFunction.REPOSITORY,
    "repository_member_retrieved": OfficeFunction.REPOSITORY,
    "repository_maintained": OfficeFunction.REPOSITORY,
    "repository_established": OfficeFunction.REPOSITORY,
    "teaching": OfficeFunction.TEACHING,
    "taught": OfficeFunction.TEACHING,
    "help": OfficeFunction.HELP,
    "helped": OfficeFunction.HELP,
    "exchange": OfficeFunction.EXCHANGE,
    "traded": OfficeFunction.EXCHANGE,
    "coordination": OfficeFunction.COORDINATION,
    "mediated": OfficeFunction.CONFLICT_MEDIATION,
}


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "office_concept_validation_failed field=%s reason_code=%s", field_name, code
    )
    return ValueError(f"{field_name}: {code}")


def _sha256_hex(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _digest16(material: str) -> str:
    return _sha256_hex(material)[:_DIGEST_LEN]


def _quantize(value: float) -> float:
    steps = round(value / 1e-6)
    quantized = float(Decimal(steps) * _QUANTUM)
    return 0.0 if quantized == 0.0 else quantized


def _apply_delta(current: float, delta: float) -> float:
    total = (Decimal(str(current)) + Decimal(str(delta))).quantize(
        _QUANTUM, rounding=ROUND_HALF_UP
    )
    number = float(total)
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return 0.0 if number == 0.0 else number


def _finite(field_name: str, value: object) -> float:
    if isinstance(value, bool) or type(value) not in {int, float}:
        raise _fail(field_name, "invalid_type")
    number = float(cast("float | int", value))
    if not math.isfinite(number):
        raise _fail(field_name, "nonfinite")
    return _quantize(number)


def _locked_float(field_name: str, value: object, expected: float) -> float:
    number = _finite(field_name, value)
    if _quantize(number) != _quantize(expected):
        raise _fail(field_name, "unsupported_policy")
    return _quantize(expected)


def _locked_int(field_name: str, value: object, expected: int) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise _fail(field_name, "invalid_type")
    if value != expected:
        raise _fail(field_name, "unsupported_policy")
    return value


def _require_hex_id(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in _HEX for char in value)
    ):
        raise _fail(field_name, "invalid_id")
    return value


def _require_digest(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _DIGEST_LEN
        or any(char not in _HEX for char in value)
    ):
        raise _fail(field_name, "invalid_digest")
    return value


def _require_token(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise _fail(field_name, "illegal_token")
    if len(value) > 32:
        raise _fail(field_name, "illegal_token")
    lowered = value.lower()
    if not lowered.replace("_", "").replace("-", "").isalnum():
        raise _fail(field_name, "illegal_token")
    return lowered


def _require_tuple(field_name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, Sequence
    ):
        raise _fail(field_name, "invalid_type")
    return tuple(values)


def _reject_forbidden(value: object) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    name = type(value).__name__
    module = type(value).__module__
    if (
        name in _FORBIDDEN_TYPES
        or module == "analysis"
        or module.startswith("analysis.")
    ):
        raise TypeError(f"{name}: forbidden_input")


def _reject_forbidden_fields(model: type) -> None:
    names = {item.name for item in fields(model)}
    forbidden = names & FORBIDDEN_OFFICE_CONCEPT_FIELD_NAMES
    if forbidden:
        _LOG.error(
            "office_concept_forbidden_field model=%s field_count=%s",
            model.__name__,
            len(forbidden),
        )
        raise ValueError(f"{model.__name__}: forbidden_field_name")


def office_inception_digest(
    function: OfficeFunction,
    context_key: str,
    inception_lineage: str,
) -> str:
    """Stable inception discriminator from the first qualifying evidence."""
    if type(function) is not OfficeFunction:
        raise _fail("function", "invalid_type")
    context = _require_digest("context_key", context_key)
    if not isinstance(inception_lineage, str) or not inception_lineage:
        raise _fail("inception_lineage", "invalid_type")
    return _digest16(f"{function.value}|{context}|{inception_lineage}")


def office_concept_id(
    owner_id: AgentId,
    inception_digest: str,
    collision_discriminator: int = 0,
) -> str:
    """Owner-scoped stable office identity, fixed at inception.

    Never derived from the current occupant, supporters, label, or growing
    evidence set.
    """
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    inception = _require_digest("inception_digest", inception_digest)
    if (
        isinstance(collision_discriminator, bool)
        or type(collision_discriminator) is not int
        or collision_discriminator < 0
    ):
        raise _fail("collision_discriminator", "invalid_type")
    return _sha256_hex(f"{owner_id.value}|office|{inception}|{collision_discriminator}")


def office_role_signature(
    function: OfficeFunction,
    context_key: str,
    duty_kinds: Sequence[OfficeDutyKind] = (),
) -> str:
    """Mutable-by-revision role signature; labels are deliberately excluded."""
    if type(function) is not OfficeFunction:
        raise _fail("function", "invalid_type")
    context = _require_digest("context_key", context_key)
    kinds = sorted(
        kind.value
        for kind in _require_tuple("duty_kinds", duty_kinds)
        if type(kind) is OfficeDutyKind
    )
    return _digest16(f"{function.value}|{context}|" + "|".join(kinds))


def office_evidence_id(
    concept_id: str,
    ordinal: int,
    channel: OfficeEvidenceChannel,
    lineage_ref: str,
) -> str:
    head = _require_hex_id("concept_id", concept_id)
    if isinstance(ordinal, bool) or type(ordinal) is not int or ordinal < 0:
        raise _fail("ordinal", "invalid_type")
    if type(channel) is not OfficeEvidenceChannel:
        raise _fail("channel", "unknown_channel")
    if not isinstance(lineage_ref, str) or not lineage_ref:
        raise _fail("lineage_ref", "invalid_type")
    return _sha256_hex(f"{head}|office|{ordinal}|{channel.value}|{lineage_ref}")


@dataclass(frozen=True, slots=True)
class OfficeEvidence:
    """One bounded item of provenance-aware office evidence."""

    evidence_id: str
    ordinal: int
    channel: OfficeEvidenceChannel
    lineage_ref: str
    root_ref: str
    tick: int
    context_key: str
    function: OfficeFunction
    actor_id: AgentId | None = None
    supporter_id: AgentId | None = None
    independently_evidenced: bool = False

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "evidence_id", _require_hex_id("evidence_id", self.evidence_id)
        )
        if isinstance(self.ordinal, bool) or type(self.ordinal) is not int:
            raise _fail("evidence.ordinal", "invalid_type")
        if self.ordinal < 0:
            raise _fail("evidence.ordinal", "out_of_range")
        if type(self.channel) is not OfficeEvidenceChannel:
            raise _fail("evidence.channel", "unknown_channel")
        if not isinstance(self.lineage_ref, str) or not self.lineage_ref:
            raise _fail("evidence.lineage_ref", "invalid_type")
        if not isinstance(self.root_ref, str) or not self.root_ref:
            raise _fail("evidence.root_ref", "invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("OfficeEvidence.tick", self.tick),
        )
        object.__setattr__(
            self,
            "context_key",
            _require_digest("evidence.context_key", self.context_key),
        )
        if type(self.function) is not OfficeFunction:
            raise _fail("evidence.function", "invalid_type")
        for name in ("actor_id", "supporter_id"):
            value = getattr(self, name)
            if value is not None and type(value) is not AgentId:
                raise _fail(f"evidence.{name}", "invalid_type")
        if type(self.independently_evidenced) is not bool:
            raise _fail("evidence.independently_evidenced", "invalid_type")


@dataclass(frozen=True, slots=True)
class OfficeDutyBelief:
    """A recognized duty expectation in a particular context."""

    duty_id: str
    kind: OfficeDutyKind
    function: OfficeFunction
    context_key: str
    strength: float
    first_tick: int
    last_tick: int
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(self, "duty_id", _require_hex_id("duty_id", self.duty_id))
        if type(self.kind) is not OfficeDutyKind:
            raise _fail("duty.kind", "invalid_type")
        if type(self.function) is not OfficeFunction:
            raise _fail("duty.function", "invalid_type")
        object.__setattr__(
            self,
            "context_key",
            _require_digest("duty.context_key", self.context_key),
        )
        object.__setattr__(
            self, "strength", _require_strength("duty.strength", self.strength)
        )
        _require_span("duty", self.first_tick, self.last_tick)
        object.__setattr__(
            self,
            "evidence_ids",
            _require_id_tuple("duty.evidence_ids", self.evidence_ids),
        )


@dataclass(frozen=True, slots=True)
class OfficeAuthorityBelief:
    """A revisable expectation of authority, never an objective permission."""

    authority_id: str
    kind: OfficeAuthorityKind
    context_key: str
    strength: float
    first_tick: int
    last_tick: int
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "authority_id", _require_hex_id("authority_id", self.authority_id)
        )
        if type(self.kind) is not OfficeAuthorityKind:
            raise _fail("authority.kind", "invalid_type")
        object.__setattr__(
            self,
            "context_key",
            _require_digest("authority.context_key", self.context_key),
        )
        object.__setattr__(
            self,
            "strength",
            _require_strength("authority.strength", self.strength),
        )
        _require_span("authority", self.first_tick, self.last_tick)
        object.__setattr__(
            self,
            "evidence_ids",
            _require_id_tuple("authority.evidence_ids", self.evidence_ids),
        )


@dataclass(frozen=True, slots=True)
class OfficeOccupantClaim:
    """One candidate occupant belief; claims are never globally authoritative."""

    claim_id: str
    occupant_id: AgentId
    status: OfficeOccupantStatus
    support_strength: float
    opposition_strength: float
    first_tick: int
    last_tick: int
    attributed_supporters: tuple[AgentId, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(self, "claim_id", _require_hex_id("claim_id", self.claim_id))
        if type(self.occupant_id) is not AgentId:
            raise _fail("claim.occupant_id", "invalid_type")
        if type(self.status) is not OfficeOccupantStatus:
            raise _fail("claim.status", "invalid_type")
        object.__setattr__(
            self,
            "support_strength",
            _require_strength("claim.support_strength", self.support_strength),
        )
        object.__setattr__(
            self,
            "opposition_strength",
            _require_strength("claim.opposition_strength", self.opposition_strength),
        )
        _require_span("claim", self.first_tick, self.last_tick)
        supporters: list[AgentId] = []
        for supporter in _require_tuple(
            "claim.attributed_supporters", self.attributed_supporters
        ):
            if type(supporter) is not AgentId:
                raise _fail("claim.attributed_supporters", "invalid_type")
            if supporter in supporters:
                raise _fail("claim.attributed_supporters", "duplicate_supporter")
            supporters.append(supporter)
        object.__setattr__(self, "attributed_supporters", tuple(supporters))
        object.__setattr__(
            self,
            "evidence_ids",
            _require_id_tuple("claim.evidence_ids", self.evidence_ids),
        )


@dataclass(frozen=True, slots=True)
class OfficeSupportRecord:
    """One attributed endorsement with owner-local evidence and provenance."""

    support_id: str
    supporter_id: AgentId | None
    target_occupant_id: AgentId
    strength: float
    independently_evidenced: bool
    root_ref: str
    first_tick: int
    last_tick: int
    evidence_id: str
    resolved: bool = True

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "support_id", _require_hex_id("support_id", self.support_id)
        )
        if self.supporter_id is not None and type(self.supporter_id) is not AgentId:
            raise _fail("support.supporter_id", "invalid_type")
        if type(self.target_occupant_id) is not AgentId:
            raise _fail("support.target_occupant_id", "invalid_type")
        object.__setattr__(
            self, "strength", _require_strength("support.strength", self.strength)
        )
        if type(self.independently_evidenced) is not bool:
            raise _fail("support.independently_evidenced", "invalid_type")
        if not isinstance(self.root_ref, str) or not self.root_ref:
            raise _fail("support.root_ref", "invalid_type")
        _require_span("support", self.first_tick, self.last_tick)
        object.__setattr__(
            self,
            "evidence_id",
            _require_hex_id("support.evidence_id", self.evidence_id),
        )
        if type(self.resolved) is not bool:
            raise _fail("support.resolved", "invalid_type")
        if not self.resolved and self.supporter_id is not None:
            raise _fail("support.resolved", "unresolved_requires_absent_supporter")


@dataclass(frozen=True, slots=True)
class OfficeRevisionRecord:
    """Immutable retained duty/authority/label revision."""

    revision_id: str
    kind: OfficeRevisionKind
    tick: int
    role_signature_before: str
    role_signature_after: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "revision_id", _require_hex_id("revision_id", self.revision_id)
        )
        if type(self.kind) is not OfficeRevisionKind:
            raise _fail("revision.kind", "invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("OfficeRevisionRecord.tick", self.tick),
        )
        object.__setattr__(
            self,
            "role_signature_before",
            _require_digest("revision.before", self.role_signature_before),
        )
        object.__setattr__(
            self,
            "role_signature_after",
            _require_digest("revision.after", self.role_signature_after),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _require_id_tuple("revision.evidence_ids", self.evidence_ids),
        )


@dataclass(frozen=True, slots=True)
class OfficeSuccessionRecord:
    """Immutable retained succession / loss / change transition."""

    succession_id: str
    kind: OfficeSuccessionKind
    tick: int
    evidence_ids: tuple[str, ...] = ()
    prior_occupant_id: AgentId | None = None
    proposed_occupant_id: AgentId | None = None
    predecessor_office_id: str | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "succession_id", _require_hex_id("succession_id", self.succession_id)
        )
        if type(self.kind) is not OfficeSuccessionKind:
            raise _fail("succession.kind", "invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("OfficeSuccessionRecord.tick", self.tick),
        )
        for name in ("prior_occupant_id", "proposed_occupant_id"):
            value = getattr(self, name)
            if value is not None and type(value) is not AgentId:
                raise _fail(f"succession.{name}", "invalid_type")
        if self.predecessor_office_id is not None:
            object.__setattr__(
                self,
                "predecessor_office_id",
                _require_hex_id(
                    "succession.predecessor_office_id", self.predecessor_office_id
                ),
            )
        object.__setattr__(
            self,
            "evidence_ids",
            _require_id_tuple("succession.evidence_ids", self.evidence_ids),
        )


def _require_strength(field_name: str, value: object) -> float:
    number = _finite(field_name, value)
    if number < 0.0 or number > 1.0:
        raise _fail(field_name, "out_of_range")
    return number


def _require_span(prefix: str, first_tick: object, last_tick: object) -> None:
    first = require_exact_nonneg_int(f"{prefix}.first_tick", first_tick)
    last = require_exact_nonneg_int(f"{prefix}.last_tick", last_tick)
    if last < first:
        raise _fail(f"{prefix}.last_tick", "before_first_tick")


def _require_id_tuple(field_name: str, values: object) -> tuple[str, ...]:
    items: list[str] = []
    for item in _require_tuple(field_name, values):
        item_id = _require_hex_id(field_name, item)
        if item_id in items:
            raise _fail(field_name, "duplicate_id")
        items.append(item_id)
    return tuple(items)


@dataclass(frozen=True, slots=True)
class OfficeConcept:
    """One owner's concept of a persistent recognized role.

    Occupant claims, duties, authority expectations, supporters, and retained
    history are all separate from the persistent role identity.
    """

    office_id: str
    owner_id: AgentId
    function: OfficeFunction
    context_key: str
    inception_digest: str
    collision_discriminator: int
    role_signature: str
    status: OfficeConceptStatus
    function_strength: float
    expectation_strength: float
    endorsement_strength: float
    first_tick: int
    last_tick: int
    evidence_count: int
    independent_root_count: int
    label_token: str | None = None
    predecessor_office_id: str | None = None
    duties: tuple[OfficeDutyBelief, ...] = ()
    authorities: tuple[OfficeAuthorityBelief, ...] = ()
    occupants: tuple[OfficeOccupantClaim, ...] = ()
    supporters: tuple[OfficeSupportRecord, ...] = ()
    succession: tuple[OfficeSuccessionRecord, ...] = ()
    revisions: tuple[OfficeRevisionRecord, ...] = ()
    evidence: tuple[OfficeEvidence, ...] = ()
    last_utterance_tick: int | None = None
    pruned_evidence_count: int = 0
    pruned_succession_count: int = 0
    pruned_revision_count: int = 0
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        object.__setattr__(
            self, "office_id", _require_hex_id("office_id", self.office_id)
        )
        if type(self.function) is not OfficeFunction:
            raise _fail("function", "invalid_type")
        object.__setattr__(
            self, "context_key", _require_digest("context_key", self.context_key)
        )
        object.__setattr__(
            self,
            "inception_digest",
            _require_digest("inception_digest", self.inception_digest),
        )
        if (
            isinstance(self.collision_discriminator, bool)
            or type(self.collision_discriminator) is not int
            or self.collision_discriminator < 0
        ):
            raise _fail("collision_discriminator", "invalid_type")
        expected_id = office_concept_id(
            self.owner_id, self.inception_digest, self.collision_discriminator
        )
        if self.office_id != expected_id:
            raise _fail("office_id", "id_mismatch")
        object.__setattr__(
            self,
            "role_signature",
            _require_digest("role_signature", self.role_signature),
        )
        if type(self.status) is not OfficeConceptStatus:
            raise _fail("status", "unknown_status")
        for name in (
            "function_strength",
            "expectation_strength",
            "endorsement_strength",
        ):
            object.__setattr__(self, name, _require_strength(name, getattr(self, name)))
        _require_span("concept", self.first_tick, self.last_tick)
        for name in ("evidence_count", "independent_root_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise _fail(name, "invalid_type")
        if self.label_token is not None:
            object.__setattr__(
                self, "label_token", _require_token("label_token", self.label_token)
            )
        if self.predecessor_office_id is not None:
            object.__setattr__(
                self,
                "predecessor_office_id",
                _require_hex_id("predecessor_office_id", self.predecessor_office_id),
            )
        if self.predecessor_office_id == self.office_id:
            raise _fail("predecessor_office_id", "self_predecessor")
        if self.last_utterance_tick is not None:
            object.__setattr__(
                self,
                "last_utterance_tick",
                require_exact_nonneg_int(
                    "OfficeConcept.last_utterance_tick", self.last_utterance_tick
                ),
            )
        for name, expected_type, cap, key_field in (
            ("duties", OfficeDutyBelief, _MAX_DUTIES, "duty_id"),
            ("authorities", OfficeAuthorityBelief, _MAX_AUTHORITIES, "authority_id"),
            ("occupants", OfficeOccupantClaim, _MAX_OCCUPANTS, "claim_id"),
            ("supporters", OfficeSupportRecord, _MAX_SUPPORTERS, "support_id"),
            ("succession", OfficeSuccessionRecord, _MAX_SUCCESSIONS, "succession_id"),
            ("revisions", OfficeRevisionRecord, _MAX_REVISIONS, "revision_id"),
            ("evidence", OfficeEvidence, _MAX_EVIDENCE, "evidence_id"),
        ):
            items = _require_tuple(name, getattr(self, name))
            checked: list[object] = []
            seen: set[str] = set()
            for item in items:
                if type(item) is not expected_type:
                    raise _fail(name, "invalid_type")
                key = getattr(item, key_field, None)
                if isinstance(key, str):
                    if key in seen:
                        raise _fail(name, "duplicate_id")
                    seen.add(key)
                checked.append(item)
            if len(checked) > cap:
                raise _fail(name, "cap_exceeded")
            object.__setattr__(self, name, tuple(checked))
        for name in (
            "pruned_evidence_count",
            "pruned_succession_count",
            "pruned_revision_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise _fail(name, "invalid_type")
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        if len(checked_notices) > _MAX_NOTICES:
            raise _fail("notices", "cap_exceeded")
        object.__setattr__(self, "notices", tuple(checked_notices))
        self._require_evidence_consistency()

    def _require_evidence_consistency(self) -> None:
        seen: set[str] = set()
        previous_ordinal = -1
        previous_tick = -1
        for item in self.evidence:
            if item.evidence_id in seen:
                raise _fail("evidence", "duplicate_evidence")
            if item.ordinal <= previous_ordinal:
                raise _fail("evidence.ordinal", "not_monotonic")
            if item.tick < previous_tick:
                raise _fail("evidence.tick", "not_monotonic")
            if item.context_key != self.context_key:
                raise _fail("evidence.context_key", "context_mismatch")
            if item.function is not self.function:
                raise _fail("evidence.function", "function_mismatch")
            seen.add(item.evidence_id)
            previous_ordinal = item.ordinal
            previous_tick = item.tick
        if self.evidence_count < len(self.evidence):
            raise _fail("evidence_count", "below_retained_count")
        if self.evidence:
            if self.first_tick != self.evidence[0].tick:
                raise _fail("first_tick", "evidence_mismatch")
            if self.last_tick < self.evidence[-1].tick:
                raise _fail("last_tick", "evidence_mismatch")

    @property
    def recognized(self) -> bool:
        return self.status is OfficeConceptStatus.RECOGNIZED

    @property
    def abandoned(self) -> bool:
        return self.status is OfficeConceptStatus.ABANDONED

    @property
    def occupant_candidates(self) -> tuple[AgentId, ...]:
        return tuple(claim.occupant_id for claim in self.occupants)

    @property
    def preferred_occupant(self) -> AgentId | None:
        """Optional non-authoritative preference; ties stay unresolved."""
        if not self.occupants:
            return None
        ranked = sorted(
            self.occupants,
            key=lambda claim: (
                -(claim.support_strength - claim.opposition_strength),
                claim.occupant_id.value,
            ),
        )
        if len(ranked) > 1:
            top = ranked[0].support_strength - ranked[0].opposition_strength
            second = ranked[1].support_strength - ranked[1].opposition_strength
            if abs(top - second) < _PREFERENCE_MARGIN:
                return None
        if ranked[0].status is OfficeOccupantStatus.OPPOSED:
            return None
        return ranked[0].occupant_id

    @property
    def evidence_coverage(self) -> str:
        return "partial" if self.pruned_evidence_count else "complete"

    @property
    def succession_coverage(self) -> str:
        return "partial" if self.pruned_succession_count else "complete"

    @property
    def revision_coverage(self) -> str:
        return "partial" if self.pruned_revision_count else "complete"


@dataclass(frozen=True, slots=True)
class OfficeConceptLedger:
    """Owner-scoped office concepts. ``None`` means the mode is off."""

    owner_id: AgentId
    concepts: tuple[OfficeConcept, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = OFFICE_CONCEPT_POLICY_VERSION
    pruned_concept_count: int = 0

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version != OFFICE_CONCEPT_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        concepts = _require_tuple("concepts", self.concepts)
        checked: list[OfficeConcept] = []
        seen: set[str] = set()
        for item in concepts:
            if type(item) is not OfficeConcept:
                raise _fail("concepts", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("concepts.owner_id", "owner_mismatch")
            if item.office_id in seen:
                raise _fail("concepts", "duplicate_concept")
            seen.add(item.office_id)
            checked.append(item)
        if len(checked) > _MAX_CONCEPTS:
            raise _fail("concepts", "cap_exceeded")
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        if len(checked_notices) > _MAX_NOTICES:
            raise _fail("notices", "cap_exceeded")
        if (
            isinstance(self.pruned_concept_count, bool)
            or type(self.pruned_concept_count) is not int
            or self.pruned_concept_count < 0
        ):
            raise _fail("pruned_concept_count", "invalid_type")
        object.__setattr__(self, "concepts", tuple(checked))
        object.__setattr__(self, "notices", tuple(checked_notices))
        _LOG.debug(
            "office_concept_ledger_constructed owner_id=%s policy_version=%s "
            "concept_count=%s",
            self.owner_id.value,
            self.policy_version,
            len(self.concepts),
        )

    @property
    def recognized_count(self) -> int:
        return sum(1 for concept in self.concepts if concept.recognized)

    @property
    def coverage(self) -> str:
        return "partial" if self.pruned_concept_count else "complete"


@dataclass(frozen=True, slots=True)
class OfficeConceptPolicy:
    """Locked office-succession constants. Runner JSON does not carry these."""

    version: str = OFFICE_CONCEPT_POLICY_VERSION
    recognition_floor: float = _RECOGNITION_FLOOR
    channel_floor: float = _CHANNEL_FLOOR
    retire_strength: float = _RETIRE_STRENGTH
    decay: float = _DECAY
    promotion_count: int = _PROMOTION_COUNT
    promotion_roots: int = _PROMOTION_ROOTS
    preference_margin: float = _PREFERENCE_MARGIN
    utterance_interval: int = _UTTERANCE_INTERVAL
    max_concepts: int = _MAX_CONCEPTS
    max_evidence: int = _MAX_EVIDENCE
    max_duties: int = _MAX_DUTIES
    max_authorities: int = _MAX_AUTHORITIES
    max_occupants: int = _MAX_OCCUPANTS
    max_supporters: int = _MAX_SUPPORTERS
    max_successions: int = _MAX_SUCCESSIONS
    max_revisions: int = _MAX_REVISIONS
    function_delta: float = _FUNCTION_DELTA
    expectation_delta: float = _EXPECTATION_DELTA
    endorsement_delta: float = _ENDORSEMENT_DELTA
    communicated_delta: float = _COMMUNICATED_DELTA
    remembered_delta: float = _REMEMBERED_DELTA
    loss_delta: float = _LOSS_DELTA
    support_delta: float = _SUPPORT_DELTA
    opposition_delta: float = _OPPOSITION_DELTA

    def __post_init__(self) -> None:
        if self.version != OFFICE_CONCEPT_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        floats = (
            ("recognition_floor", _RECOGNITION_FLOOR),
            ("channel_floor", _CHANNEL_FLOOR),
            ("retire_strength", _RETIRE_STRENGTH),
            ("decay", _DECAY),
            ("preference_margin", _PREFERENCE_MARGIN),
            ("function_delta", _FUNCTION_DELTA),
            ("expectation_delta", _EXPECTATION_DELTA),
            ("endorsement_delta", _ENDORSEMENT_DELTA),
            ("communicated_delta", _COMMUNICATED_DELTA),
            ("remembered_delta", _REMEMBERED_DELTA),
            ("loss_delta", _LOSS_DELTA),
            ("support_delta", _SUPPORT_DELTA),
            ("opposition_delta", _OPPOSITION_DELTA),
        )
        for name, expected in floats:
            object.__setattr__(
                self, name, _locked_float(name, getattr(self, name), expected)
            )
        counts = (
            ("promotion_count", _PROMOTION_COUNT),
            ("promotion_roots", _PROMOTION_ROOTS),
            ("utterance_interval", _UTTERANCE_INTERVAL),
            ("max_concepts", _MAX_CONCEPTS),
            ("max_evidence", _MAX_EVIDENCE),
            ("max_duties", _MAX_DUTIES),
            ("max_authorities", _MAX_AUTHORITIES),
            ("max_occupants", _MAX_OCCUPANTS),
            ("max_supporters", _MAX_SUPPORTERS),
            ("max_successions", _MAX_SUCCESSIONS),
            ("max_revisions", _MAX_REVISIONS),
        )
        for name, expected in counts:
            object.__setattr__(
                self, name, _locked_int(name, getattr(self, name), expected)
            )


@dataclass(frozen=True, slots=True)
class OfficeRecognitionAppraisal:
    """Deterministic recognition verdict; a proposal is never proof."""

    reason: str
    recognized: bool
    proposed: bool
    independent_root_count: int
    qualifying_evidence_count: int


def appraise_office_recognition(
    *,
    function_strength: float,
    expectation_strength: float,
    endorsement_strength: float,
    independent_root_count: int,
    qualifying_evidence_count: int,
    policy: OfficeConceptPolicy | None = None,
) -> OfficeRecognitionAppraisal:
    """Classify a role as proposed/recognized without any social authority.

    Recognition requires recurring function evidence *and* distinct,
    provenance-independent role-directed expectation or endorsement. Repeated
    influence by one person alone can never promote a role.
    """
    active = default_office_concept_policy() if policy is None else policy
    if type(active) is not OfficeConceptPolicy:
        raise TypeError("policy must be OfficeConceptPolicy or None")
    function = _require_strength("function_strength", function_strength)
    expectation = _require_strength("expectation_strength", expectation_strength)
    endorsement = _require_strength("endorsement_strength", endorsement_strength)
    for name, value in (
        ("independent_root_count", independent_root_count),
        ("qualifying_evidence_count", qualifying_evidence_count),
    ):
        if isinstance(value, bool) or type(value) is not int or value < 0:
            raise _fail(name, "invalid_type")
    role_directed = max(expectation, endorsement)
    proposed = (
        function >= active.channel_floor
        and qualifying_evidence_count >= active.promotion_count
    )
    recognized = (
        function >= active.recognition_floor
        and role_directed >= active.channel_floor
        and qualifying_evidence_count >= active.promotion_count
        and independent_root_count >= active.promotion_roots
    )
    if recognized:
        reason = "recognized"
    elif proposed and role_directed < active.channel_floor:
        reason = "influence_only"
    elif proposed:
        reason = "missing_independent_root"
    else:
        reason = "insufficient_recurrence"
    return OfficeRecognitionAppraisal(
        reason=reason,
        recognized=recognized,
        proposed=proposed,
        independent_root_count=independent_root_count,
        qualifying_evidence_count=qualifying_evidence_count,
    )


_DUTY_DIRECTION: Final[Mapping[OfficeDutyKind, ActionDirection]] = {
    OfficeDutyKind.PERFORM: ActionDirection.HELP,
    OfficeDutyKind.COORDINATE: ActionDirection.COMMUNICATE,
    OfficeDutyKind.MAINTAIN: ActionDirection.SEARCH,
    OfficeDutyKind.TRANSMIT: ActionDirection.COMMUNICATE,
    OfficeDutyKind.MEDIATE: ActionDirection.COMMUNICATE,
}


def office_direction_preference(
    ledger: object | None,
    *,
    policy: OfficeConceptPolicy | None = None,
) -> ActionDirection | None:
    """Bounded direction bias from a recognized office, never an obligation.

    Only an already-recognized role can bias selection among admissible
    existing futures. Influence-only proposals return ``None``. The result is a
    preference, not a permission, veto, or forced action.
    """
    if type(ledger) is not OfficeConceptLedger:
        return None
    active = default_office_concept_policy() if policy is None else policy
    if type(active) is not OfficeConceptPolicy:
        raise TypeError("policy must be OfficeConceptPolicy or None")
    for concept in sorted(ledger.concepts, key=lambda item: item.office_id):
        if not concept.recognized:
            continue
        duties = sorted(
            concept.duties, key=lambda item: (-item.strength, item.kind.value)
        )
        for duty in duties:
            if duty.strength < active.channel_floor:
                continue
            direction = _DUTY_DIRECTION.get(duty.kind)
            if direction is not None:
                return direction
        if concept.preferred_occupant is not None and concept.supporters:
            return ActionDirection.COMMUNICATE
    return None


def default_office_concept_policy() -> OfficeConceptPolicy:
    """Return the only accepted office-succession policy."""
    return OfficeConceptPolicy()


def empty_office_concept_ledger(owner_id: AgentId) -> OfficeConceptLedger:
    """Ledger with no concepts. Disabled mode does not call this."""
    return OfficeConceptLedger(owner_id=owner_id)


def require_owner_offices(
    ledger: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped office ledger. ``None`` is passthrough."""
    if ledger is None:
        return
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(ledger) is not OfficeConceptLedger:
        _LOG.warning("office_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be OfficeConceptLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "office_concept_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning("office_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError(f"{field_name} owner_id mismatch")


# ---------------------------------------------------------------------------
# Evidence adapters and deterministic update policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _OfficeSignal:
    predicate: str
    function: OfficeFunction
    context_key: str
    lineage_ref: str
    root_ref: str
    channel: OfficeEvidenceChannel
    actor_id: AgentId | None = None
    occupant_id: AgentId | None = None
    alleged_supporter_id: AgentId | None = None
    duty_kind: OfficeDutyKind | None = None
    authority_kind: OfficeAuthorityKind | None = None
    confidence: float = 1.0
    independently_evidenced: bool = True
    alleged_supporter_unresolved: bool = False


def _context_key(observation: Observation) -> str:
    location = (
        "none"
        if observation.self_body is None
        else observation.self_body.location_id.value
    )
    day_phase = "none" if observation.day_phase is None else observation.day_phase.value
    return _digest16(
        f"office-context|{observation.world_id.value}|{location}|{day_phase}"
    )


def _actor_agent(
    identity: OwnerSafeSocialIdentity, entity_id: EntityId | None
) -> AgentId | None:
    if entity_id is None:
        return None
    if entity_id == identity.owner_entity_id:
        return identity.owner_id
    for binding in identity.counterparts:
        if binding.entity_id == entity_id:
            return binding.agent_id
    return None


def _function_for_kind(kind: str) -> OfficeFunction | None:
    direct = _FUNCTION_BY_OCCURRENCE.get(kind)
    if direct is not None:
        return direct
    for function in OfficeFunction:
        if kind == function.value:
            return function
    return None


def _parse_context_token(token: str, fallback: str) -> str:
    head = token.split("|", 1)[0].strip()
    if len(head) == _DIGEST_LEN and all(char in _HEX for char in head):
        return head
    return fallback


def _parse_optional_entity(token: str) -> EntityId | None:
    token = token.strip()
    if not token or token == "-":
        return None
    return EntityId(token)


def _parse_duty_kind(token: str) -> OfficeDutyKind | None:
    try:
        return OfficeDutyKind(token.strip())
    except ValueError:
        return None


def _parse_authority_kind(token: str) -> OfficeAuthorityKind | None:
    try:
        return OfficeAuthorityKind(token.strip())
    except ValueError:
        return None


def _signals_from_observation(
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    context_key: str,
) -> list[_OfficeSignal]:
    signals: list[_OfficeSignal] = []
    for ordinal, occurrence in enumerate(observation.occurrences):
        function = _function_for_kind(occurrence.kind)
        if function is None:
            continue
        actor = _actor_agent(identity, occurrence.actor_id)
        lineage = f"occurrence-{observation.tick}-{ordinal}-{occurrence.kind}"
        signals.append(
            _OfficeSignal(
                predicate="office_function",
                function=function,
                context_key=context_key,
                lineage_ref=lineage,
                root_ref=f"observed|{occurrence.kind}|{actor.value if actor else '-'}",
                channel=OfficeEvidenceChannel.OBSERVED,
                actor_id=actor,
            )
        )
    for ordinal, communication in enumerate(observation.communications):
        speaker = _actor_agent(identity, communication.speaker_id)
        declared = communication.utterance.declared
        root_ref = f"communication|{declared.root_communication_id.value}"
        for relation_index, relation in enumerate(
            communication.utterance.content.relations
        ):
            function = _function_for_kind(relation.subject)
            if function is None:
                continue
            parts = relation.object.split("|")
            context = _parse_context_token(relation.object, context_key)
            occupant_entity = (
                _parse_optional_entity(parts[1]) if len(parts) > 1 else None
            )
            alleged_entity = (
                _parse_optional_entity(parts[2]) if len(parts) > 2 else None
            )
            signals.append(
                _OfficeSignal(
                    predicate=relation.predicate,
                    function=function,
                    context_key=context,
                    lineage_ref=(
                        f"communication-{observation.tick}-{ordinal}-"
                        f"{relation_index}-{relation.predicate}"
                    ),
                    root_ref=root_ref,
                    channel=OfficeEvidenceChannel.COMMUNICATED,
                    actor_id=speaker,
                    occupant_id=_actor_agent(identity, occupant_entity),
                    alleged_supporter_id=_actor_agent(identity, alleged_entity),
                    alleged_supporter_unresolved=(
                        alleged_entity is not None
                        and _actor_agent(identity, alleged_entity) is None
                    ),
                    duty_kind=(_parse_duty_kind(parts[1]) if len(parts) > 1 else None),
                    authority_kind=(
                        _parse_authority_kind(parts[1]) if len(parts) > 1 else None
                    ),
                    independently_evidenced=speaker is not None,
                )
            )
    return signals


def _signals_from_local_ledger(
    ledger: object | None,
    *,
    owner_id: AgentId,
    channel: str,
    fallback_context: str,
) -> list[_OfficeSignal]:
    """Conservative adapter for owner-local norm/convention/institution rows.

    Only rows that explicitly expose a closed office function, a context key,
    and a recognized marker contribute role-directed expectation evidence.
    Unknown row shapes are ignored rather than guessed.
    """
    if ledger is None:
        return []
    ledger_owner = getattr(ledger, "owner_id", None)
    if ledger_owner is not None and ledger_owner != owner_id:
        raise ValueError("local office evidence owner_id mismatch")
    rows: list[object] = []
    for attribute in ("concepts", "norms", "conventions", "beliefs"):
        value = getattr(ledger, attribute, None)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            rows.extend(value)
    signals: list[_OfficeSignal] = []
    for ordinal, row in enumerate(rows):
        function = _function_for_kind(str(getattr(row, "function", "")))
        if function is None:
            continue
        context = str(getattr(row, "context_key", fallback_context))
        if len(context) != _DIGEST_LEN or any(char not in _HEX for char in context):
            continue
        status = str(
            getattr(getattr(row, "status", None), "value", getattr(row, "status", ""))
        )
        if status not in {"recognized", "accepted", "shared"} and not bool(
            getattr(row, "recognized", False)
        ):
            continue
        row_id = str(
            getattr(row, "concept_id", None)
            or getattr(row, "norm_id", None)
            or getattr(row, "convention_id", None)
            or getattr(row, "belief_id", None)
            or f"row-{ordinal}"
        )
        signals.append(
            _OfficeSignal(
                predicate="office_role",
                function=function,
                context_key=context,
                lineage_ref=f"{channel}-{ordinal}-{row_id}",
                root_ref=f"{channel}|{row_id}",
                channel=OfficeEvidenceChannel.OBSERVED,
                actor_id=owner_id,
            )
        )
    return signals


def _signals_from_episodes(
    context: object,
    identity: OwnerSafeSocialIdentity,
    context_key: str,
) -> list[_OfficeSignal]:
    from agents.cognition.models import RetrievedMemoryContext, episode_facts

    if context is None:
        return []
    if type(context) is not RetrievedMemoryContext:
        raise TypeError("retrieved_memory_context must be RetrievedMemoryContext")
    if context.owner_id != identity.owner_id:
        raise ValueError("retrieved_memory_context owner_id mismatch")
    signals: list[_OfficeSignal] = []
    for facts in episode_facts(context):
        concept_text = {item.mention_id: item.concept for item in facts.concepts}
        entity_by_mention = {
            item.mention_id: item.entity_id
            for item in facts.entities
            if item.entity_id is not None
        }
        for relation in facts.relations:
            predicate = relation.predicate
            if not predicate.startswith("office_"):
                continue
            subject_text = concept_text.get(relation.subject.mention_id, "")
            function = _function_for_kind(subject_text)
            if function is None:
                continue
            object_text = concept_text.get(relation.object.mention_id, "")
            object_entity = entity_by_mention.get(relation.object.mention_id)
            parts = object_text.split("|")
            remembered_context = _parse_context_token(object_text, context_key)
            occupant = _actor_agent(identity, object_entity)
            if occupant is None and len(parts) > 1:
                occupant = _actor_agent(identity, _parse_optional_entity(parts[1]))
            alleged = None
            if len(parts) > 2:
                alleged = _actor_agent(identity, _parse_optional_entity(parts[2]))
            signals.append(
                _OfficeSignal(
                    predicate=predicate,
                    function=function,
                    context_key=remembered_context,
                    lineage_ref=f"remembered-{facts.episode_id}-{relation.relation_id.value}",
                    root_ref=f"remembered|{facts.episode_id}",
                    channel=OfficeEvidenceChannel.REMEMBERED,
                    actor_id=_actor_agent(identity, None),
                    occupant_id=occupant,
                    alleged_supporter_id=alleged,
                    alleged_supporter_unresolved=(len(parts) > 2 and alleged is None),
                    duty_kind=(_parse_duty_kind(parts[1]) if len(parts) > 1 else None),
                    authority_kind=(
                        _parse_authority_kind(parts[1]) if len(parts) > 1 else None
                    ),
                    confidence=facts.confidence,
                    independently_evidenced=occupant is not None,
                )
            )
    return signals


class _OfficeDraft:
    """Mutable per-update accumulator. Never escapes this module."""

    __slots__ = (
        "abandoned",
        "authorities",
        "authority_evidence",
        "collision_discriminator",
        "context_key",
        "duties",
        "duty_evidence",
        "endorsement_strength",
        "evidence",
        "expectation_strength",
        "first_tick",
        "function",
        "function_strength",
        "inception_digest",
        "label_token",
        "last_tick",
        "last_utterance_tick",
        "lost_occupants",
        "notices",
        "occupants",
        "office_id",
        "owner_id",
        "predecessor_office_id",
        "pruned_evidence_count",
        "pruned_revision_count",
        "pruned_succession_count",
        "revisions",
        "role_roots",
        "role_signature",
        "succession",
        "supporters",
        "touched",
    )

    def __init__(
        self,
        *,
        office_id: str,
        function: OfficeFunction,
        context_key: str,
        inception_digest: str,
        collision_discriminator: int,
        tick: int,
    ) -> None:
        self.office_id = office_id
        self.owner_id = AgentId("placeholder-owner")
        self.function = function
        self.context_key = context_key
        self.inception_digest = inception_digest
        self.collision_discriminator = collision_discriminator
        self.role_signature = office_role_signature(function, context_key)
        self.first_tick = tick
        self.last_tick = tick
        self.function_strength = 0.0
        self.expectation_strength = 0.0
        self.endorsement_strength = 0.0
        self.role_roots: set[str] = set()
        self.evidence: list[OfficeEvidence] = []
        self.duties: dict[OfficeDutyKind, OfficeDutyBelief] = {}
        self.authorities: dict[OfficeAuthorityKind, OfficeAuthorityBelief] = {}
        self.occupants: dict[AgentId, OfficeOccupantClaim] = {}
        self.supporters: list[OfficeSupportRecord] = []
        self.succession: list[OfficeSuccessionRecord] = []
        self.revisions: list[OfficeRevisionRecord] = []
        self.label_token: str | None = None
        self.last_utterance_tick: int | None = None
        self.abandoned = False
        self.lost_occupants: set[AgentId] = set()
        self.predecessor_office_id: str | None = None
        self.pruned_evidence_count = 0
        self.pruned_succession_count = 0
        self.pruned_revision_count = 0
        self.notices: list[str] = []
        self.touched = False


def _draft_from_concept(concept: OfficeConcept) -> _OfficeDraft:
    draft = _OfficeDraft(
        office_id=concept.office_id,
        function=concept.function,
        context_key=concept.context_key,
        inception_digest=concept.inception_digest,
        collision_discriminator=concept.collision_discriminator,
        tick=concept.first_tick,
    )
    draft.owner_id = concept.owner_id
    draft.role_signature = concept.role_signature
    draft.first_tick = concept.first_tick
    draft.last_tick = concept.last_tick
    draft.function_strength = concept.function_strength
    draft.expectation_strength = concept.expectation_strength
    draft.endorsement_strength = concept.endorsement_strength
    draft.evidence = list(concept.evidence)
    draft.duties = {item.kind: item for item in concept.duties}
    draft.authorities = {item.kind: item for item in concept.authorities}
    draft.occupants = {item.occupant_id: item for item in concept.occupants}
    draft.supporters = list(concept.supporters)
    draft.succession = list(concept.succession)
    draft.revisions = list(concept.revisions)
    draft.label_token = concept.label_token
    draft.last_utterance_tick = concept.last_utterance_tick
    draft.abandoned = concept.abandoned
    for item in concept.succession:
        if (
            item.kind is OfficeSuccessionKind.OCCUPANT_LOST
            and item.proposed_occupant_id is not None
        ):
            draft.lost_occupants.add(item.proposed_occupant_id)
        elif (
            item.kind is OfficeSuccessionKind.OCCUPANT_RETURNED
            and item.proposed_occupant_id is not None
        ):
            draft.lost_occupants.discard(item.proposed_occupant_id)
    draft.predecessor_office_id = concept.predecessor_office_id
    draft.pruned_evidence_count = concept.pruned_evidence_count
    draft.pruned_succession_count = concept.pruned_succession_count
    draft.pruned_revision_count = concept.pruned_revision_count
    draft.notices = list(concept.notices)
    for evidence_item in concept.evidence:
        if (
            evidence_item.channel is not OfficeEvidenceChannel.OBSERVED
            or evidence_item.actor_id is None
        ):
            draft.role_roots.add(evidence_item.root_ref)
    draft.role_roots.update(
        support_item.root_ref
        for support_item in concept.supporters
        if support_item.independently_evidenced
    )
    return draft


def _notice(notices: list[str], reason: str) -> None:
    if reason not in notices:
        notices.append(reason)


def _draft_map(
    owner_id: AgentId,
    previous: OfficeConceptLedger,
) -> dict[tuple[OfficeFunction, str], _OfficeDraft]:
    drafts: dict[tuple[OfficeFunction, str], _OfficeDraft] = {}
    for concept in previous.concepts:
        if concept.abandoned:
            continue
        drafts[(concept.function, concept.context_key)] = _draft_from_concept(concept)
    return drafts


def _draft_for_key(
    *,
    owner_id: AgentId,
    drafts: dict[tuple[OfficeFunction, str], _OfficeDraft],
    function: OfficeFunction,
    context_key: str,
    lineage_ref: str,
    tick: int,
    notices: list[str],
    policy: OfficeConceptPolicy,
) -> _OfficeDraft | None:
    key = (function, context_key)
    existing = drafts.get(key)
    if existing is not None:
        return existing
    if len(drafts) >= policy.max_concepts:
        _notice(notices, "cap_exceeded")
        return None
    inception = office_inception_digest(function, context_key, lineage_ref)
    occupied = {
        draft.inception_digest for draft in drafts.values() if draft.inception_digest
    }
    discriminator = 0
    office_id = office_concept_id(owner_id, inception, discriminator)
    while office_id in {draft.office_id for draft in drafts.values()}:
        discriminator += 1
        office_id = office_concept_id(owner_id, inception, discriminator)
    if inception in occupied:
        _notice(notices, "duplicate_root")
    draft = _OfficeDraft(
        office_id=office_id,
        function=function,
        context_key=context_key,
        inception_digest=inception,
        collision_discriminator=discriminator,
        tick=tick,
    )
    draft.owner_id = owner_id
    same_context = [
        item
        for item in drafts.values()
        if item.context_key == context_key
        and item.function is not function
        and not item.abandoned
    ]
    if same_context:
        predecessor = max(
            same_context, key=lambda item: (item.last_tick, item.office_id)
        )
        draft.predecessor_office_id = predecessor.office_id
        draft.succession.append(
            OfficeSuccessionRecord(
                succession_id=_sha256_hex(
                    f"{office_id}|succession|{tick}|role_changed|0"
                ),
                kind=OfficeSuccessionKind.ROLE_CHANGED,
                tick=tick,
                predecessor_office_id=predecessor.office_id,
            )
        )
    drafts[key] = draft
    return draft


def _record_evidence(
    draft: _OfficeDraft,
    *,
    signal: _OfficeSignal,
    tick: int,
    policy: OfficeConceptPolicy,
) -> OfficeEvidence | None:
    if len(draft.evidence) >= policy.max_evidence:
        draft.pruned_evidence_count += 1
        _notice(draft.notices, "cap_exceeded")
        return None
    ordinal = (draft.evidence[-1].ordinal + 1) if draft.evidence else 0
    evidence = OfficeEvidence(
        evidence_id=office_evidence_id(
            draft.office_id, ordinal, signal.channel, signal.lineage_ref
        ),
        ordinal=ordinal,
        channel=signal.channel,
        lineage_ref=signal.lineage_ref,
        root_ref=signal.root_ref,
        tick=tick,
        context_key=draft.context_key,
        function=draft.function,
        actor_id=signal.actor_id,
        supporter_id=signal.alleged_supporter_id,
        independently_evidenced=signal.independently_evidenced,
    )
    draft.evidence.append(evidence)
    draft.last_tick = max(draft.last_tick, tick)
    draft.touched = True
    return evidence


def _confidence_delta(confidence: float, delta: float) -> float:
    if confidence <= 0.0:
        return 0.0
    return _quantize(delta * min(1.0, confidence))


def _upsert_duty(
    draft: _OfficeDraft,
    kind: OfficeDutyKind,
    tick: int,
    evidence_id: str,
    confidence: float,
    policy: OfficeConceptPolicy,
    *,
    delta: float | None = None,
) -> None:
    if kind not in draft.duties and len(draft.duties) >= policy.max_duties:
        _notice(draft.notices, "cap_exceeded")
        return
    current = draft.duties.get(kind)
    strength = _apply_delta(
        0.0 if current is None else current.strength,
        _confidence_delta(
            confidence, policy.function_delta if delta is None else delta
        ),
    )
    first_tick = tick if current is None else current.first_tick
    evidence_ids = (
        (evidence_id,) if current is None else (*current.evidence_ids, evidence_id)
    )
    if len(evidence_ids) > policy.max_evidence:
        evidence_ids = evidence_ids[-policy.max_evidence :]
    draft.duties[kind] = OfficeDutyBelief(
        duty_id=_sha256_hex(f"{draft.office_id}|duty|{kind.value}|{draft.context_key}"),
        kind=kind,
        function=draft.function,
        context_key=draft.context_key,
        strength=strength,
        first_tick=first_tick,
        last_tick=tick,
        evidence_ids=evidence_ids,
    )


def _upsert_authority(
    draft: _OfficeDraft,
    kind: OfficeAuthorityKind,
    tick: int,
    evidence_id: str,
    confidence: float,
    policy: OfficeConceptPolicy,
) -> None:
    if (
        kind not in draft.authorities
        and len(draft.authorities) >= policy.max_authorities
    ):
        _notice(draft.notices, "cap_exceeded")
        return
    current = draft.authorities.get(kind)
    strength = _apply_delta(
        0.0 if current is None else current.strength,
        _confidence_delta(confidence, policy.expectation_delta),
    )
    first_tick = tick if current is None else current.first_tick
    evidence_ids = (
        (evidence_id,) if current is None else (*current.evidence_ids, evidence_id)
    )
    if len(evidence_ids) > policy.max_evidence:
        evidence_ids = evidence_ids[-policy.max_evidence :]
    draft.authorities[kind] = OfficeAuthorityBelief(
        authority_id=_sha256_hex(
            f"{draft.office_id}|authority|{kind.value}|{draft.context_key}"
        ),
        kind=kind,
        context_key=draft.context_key,
        strength=strength,
        first_tick=first_tick,
        last_tick=tick,
        evidence_ids=evidence_ids,
    )


def _upsert_occupant(
    draft: _OfficeDraft,
    occupant: AgentId,
    tick: int,
    evidence_id: str,
    *,
    support: float,
    opposition: float,
    policy: OfficeConceptPolicy,
    supporter: AgentId | None = None,
) -> None:
    if occupant not in draft.occupants and len(draft.occupants) >= policy.max_occupants:
        _notice(draft.notices, "cap_exceeded")
        return
    current = draft.occupants.get(occupant)
    support_strength = _apply_delta(
        0.0 if current is None else current.support_strength, support
    )
    opposition_strength = _apply_delta(
        0.0 if current is None else current.opposition_strength, opposition
    )
    first_tick = tick if current is None else current.first_tick
    existing_supporters = () if current is None else current.attributed_supporters
    attributed = existing_supporters
    if supporter is not None and supporter not in existing_supporters:
        attributed = (*existing_supporters, supporter)
    evidence_ids = (
        (evidence_id,) if current is None else (*current.evidence_ids, evidence_id)
    )
    if len(evidence_ids) > policy.max_evidence:
        evidence_ids = evidence_ids[-policy.max_evidence :]
    if opposition_strength >= support_strength and opposition_strength > 0.0:
        status = OfficeOccupantStatus.OPPOSED
    elif support_strength > 0.0:
        status = OfficeOccupantStatus.CANDIDATE
    else:
        status = OfficeOccupantStatus.UNCERTAIN
    draft.occupants[occupant] = OfficeOccupantClaim(
        claim_id=_sha256_hex(f"{draft.office_id}|occupant|{occupant.value}"),
        occupant_id=occupant,
        status=status,
        support_strength=support_strength,
        opposition_strength=opposition_strength,
        first_tick=first_tick,
        last_tick=tick,
        attributed_supporters=attributed,
        evidence_ids=evidence_ids,
    )


def _record_support(
    draft: _OfficeDraft,
    *,
    signal: _OfficeSignal,
    tick: int,
    evidence_id: str,
    policy: OfficeConceptPolicy,
) -> None:
    if signal.occupant_id is None:
        _notice(draft.notices, "unresolved_entity")
        return
    if signal.actor_id is None:
        _notice(draft.notices, "unresolved_entity")
        return
    supporter = signal.alleged_supporter_id
    if signal.alleged_supporter_unresolved:
        supporter = None
        resolved = False
        independently = False
    elif supporter is not None and supporter != signal.actor_id:
        resolved = False
        independently = False
    else:
        supporter = signal.actor_id
        resolved = True
        independently = signal.independently_evidenced
    if supporter == signal.occupant_id:
        _notice(draft.notices, "self_endorsement")
        return
    if len(draft.supporters) >= policy.max_supporters:
        _notice(draft.notices, "cap_exceeded")
        return
    if any(
        item.root_ref == signal.root_ref
        and item.target_occupant_id == signal.occupant_id
        for item in draft.supporters
    ):
        _notice(draft.notices, "duplicate_root")
        return
    root_key = f"support|{signal.root_ref}|{signal.occupant_id.value}"
    draft.supporters.append(
        OfficeSupportRecord(
            support_id=_sha256_hex(
                f"{draft.office_id}|support|{supporter.value if supporter else '-'}|"
                f"{signal.occupant_id.value}|{root_key}"
            ),
            supporter_id=supporter,
            target_occupant_id=signal.occupant_id,
            strength=_confidence_delta(signal.confidence, policy.support_delta),
            independently_evidenced=independently and resolved,
            root_ref=signal.root_ref,
            first_tick=tick,
            last_tick=tick,
            evidence_id=evidence_id,
            resolved=resolved,
        )
    )
    if independently and resolved:
        draft.role_roots.add(signal.root_ref)


def _apply_signal(
    draft: _OfficeDraft,
    signal: _OfficeSignal,
    tick: int,
    policy: OfficeConceptPolicy,
) -> None:
    evidence = _record_evidence(draft, signal=signal, tick=tick, policy=policy)
    if evidence is None:
        return
    predicate = signal.predicate
    if predicate == "office_function":
        draft.function_strength = _apply_delta(
            draft.function_strength,
            _confidence_delta(signal.confidence, policy.function_delta),
        )
        _upsert_duty(
            draft,
            OfficeDutyKind.PERFORM,
            tick,
            evidence.evidence_id,
            signal.confidence,
            policy,
        )
    elif predicate in {"office_role", "office_expectation", "office_change"}:
        draft.expectation_strength = _apply_delta(
            draft.expectation_strength,
            _confidence_delta(signal.confidence, policy.expectation_delta),
        )
        if signal.actor_id is not None and signal.actor_id != draft.owner_id:
            if signal.channel is not OfficeEvidenceChannel.OBSERVED:
                draft.role_roots.add(signal.root_ref)
    elif predicate == "office_duty":
        if signal.duty_kind is None:
            _notice(draft.notices, "unsupported_evidence")
            return
        before = draft.role_signature
        had_kind = signal.duty_kind in draft.duties
        _upsert_duty(
            draft,
            signal.duty_kind,
            tick,
            evidence.evidence_id,
            signal.confidence,
            policy,
            delta=policy.expectation_delta,
        )
        _refresh_role_signature(draft)
        if not had_kind and draft.role_signature != before:
            _append_revision(
                draft,
                kind=OfficeRevisionKind.DUTY_REVISED,
                tick=tick,
                evidence_id=evidence.evidence_id,
                before=before,
                policy=policy,
            )
    elif predicate == "office_authority":
        if signal.authority_kind is None:
            _notice(draft.notices, "unsupported_evidence")
            return
        before = draft.role_signature
        had_kind = signal.authority_kind in draft.authorities
        _upsert_authority(
            draft,
            signal.authority_kind,
            tick,
            evidence.evidence_id,
            signal.confidence,
            policy,
        )
        if not had_kind:
            _append_revision(
                draft,
                kind=OfficeRevisionKind.AUTHORITY_REVISED,
                tick=tick,
                evidence_id=evidence.evidence_id,
                before=before,
                policy=policy,
            )
    elif predicate == "office_endorse":
        draft.endorsement_strength = _apply_delta(
            draft.endorsement_strength,
            _confidence_delta(signal.confidence, policy.endorsement_delta),
        )
        _record_support(
            draft,
            signal=signal,
            tick=tick,
            evidence_id=evidence.evidence_id,
            policy=policy,
        )
        if signal.occupant_id is not None:
            _upsert_occupant(
                draft,
                signal.occupant_id,
                tick,
                evidence.evidence_id,
                support=_confidence_delta(signal.confidence, policy.support_delta),
                opposition=0.0,
                policy=policy,
                supporter=signal.actor_id,
            )
    elif predicate == "office_dispute":
        draft.expectation_strength = _apply_delta(
            draft.expectation_strength,
            _confidence_delta(signal.confidence, policy.expectation_delta),
        )
        if signal.occupant_id is not None:
            _upsert_occupant(
                draft,
                signal.occupant_id,
                tick,
                evidence.evidence_id,
                support=0.0,
                opposition=_confidence_delta(
                    signal.confidence, policy.opposition_delta
                ),
                policy=policy,
            )
    elif predicate in {
        "office_relinquish",
        "office_succession",
        "office_lost",
        "office_return",
        "office_abandon",
    }:
        _apply_succession_signal(draft, signal, tick, evidence.evidence_id, policy)
    else:
        _notice(draft.notices, "unsupported_evidence")


def _append_revision(
    draft: _OfficeDraft,
    *,
    kind: OfficeRevisionKind,
    tick: int,
    evidence_id: str,
    before: str,
    policy: OfficeConceptPolicy,
) -> None:
    if len(draft.revisions) >= policy.max_revisions:
        draft.pruned_revision_count += 1
        _notice(draft.notices, "cap_exceeded")
        return
    draft.revisions.append(
        OfficeRevisionRecord(
            revision_id=_sha256_hex(
                f"{draft.office_id}|revision|{tick}|{kind.value}|{len(draft.revisions)}"
            ),
            kind=kind,
            tick=tick,
            role_signature_before=before,
            role_signature_after=draft.role_signature,
            evidence_ids=(evidence_id,),
        )
    )


def _refresh_role_signature(draft: _OfficeDraft) -> None:
    draft.role_signature = office_role_signature(
        draft.function,
        draft.context_key,
        tuple(sorted(draft.duties, key=lambda item: item.value)),
    )


def _append_succession(
    draft: _OfficeDraft,
    *,
    kind: OfficeSuccessionKind,
    tick: int,
    evidence_ids: tuple[str, ...],
    policy: OfficeConceptPolicy,
    prior_occupant_id: AgentId | None = None,
    proposed_occupant_id: AgentId | None = None,
) -> bool:
    if len(draft.succession) >= policy.max_successions:
        draft.pruned_succession_count += 1
        _notice(draft.notices, "cap_exceeded")
        return False
    ordinal = len(draft.succession)
    draft.succession.append(
        OfficeSuccessionRecord(
            succession_id=_sha256_hex(
                f"{draft.office_id}|succession|{tick}|{kind.value}|{ordinal}"
            ),
            kind=kind,
            tick=tick,
            evidence_ids=evidence_ids,
            prior_occupant_id=prior_occupant_id,
            proposed_occupant_id=proposed_occupant_id,
        )
    )
    return True


def _apply_succession_signal(
    draft: _OfficeDraft,
    signal: _OfficeSignal,
    tick: int,
    evidence_id: str,
    policy: OfficeConceptPolicy,
) -> None:
    if signal.predicate == "office_abandon":
        draft.abandoned = True
        _append_succession(
            draft,
            kind=OfficeSuccessionKind.ABANDONED,
            tick=tick,
            evidence_ids=(evidence_id,),
            policy=policy,
            prior_occupant_id=signal.actor_id,
        )
        return
    kind = {
        "office_relinquish": OfficeSuccessionKind.OCCUPANT_RELINQUISHED,
        "office_succession": OfficeSuccessionKind.SUCCESSOR_PROPOSED,
        "office_lost": OfficeSuccessionKind.OCCUPANT_LOST,
        "office_return": OfficeSuccessionKind.OCCUPANT_RETURNED,
    }[signal.predicate]
    prior = (
        signal.occupant_id
        if signal.predicate in {"office_relinquish", "office_lost", "office_return"}
        else None
    )
    _append_succession(
        draft,
        kind=kind,
        tick=tick,
        evidence_ids=(evidence_id,),
        policy=policy,
        prior_occupant_id=prior,
        proposed_occupant_id=signal.occupant_id,
    )
    if kind is OfficeSuccessionKind.OCCUPANT_LOST and signal.occupant_id is not None:
        draft.lost_occupants.add(signal.occupant_id)
    if (
        kind is OfficeSuccessionKind.OCCUPANT_RETURNED
        and signal.occupant_id is not None
    ):
        draft.lost_occupants.discard(signal.occupant_id)
    if (
        kind is OfficeSuccessionKind.SUCCESSOR_PROPOSED
        and signal.occupant_id is not None
    ):
        _upsert_occupant(
            draft,
            signal.occupant_id,
            tick,
            evidence_id,
            support=_confidence_delta(signal.confidence, policy.support_delta),
            opposition=0.0,
            policy=policy,
            supporter=signal.actor_id,
        )


def _freeze_draft(
    draft: _OfficeDraft,
    owner_id: AgentId,
    tick: int,
    policy: OfficeConceptPolicy,
) -> OfficeConcept:
    retention = max(draft.first_tick, tick - 64)
    evidence = [item for item in draft.evidence if item.tick >= retention]
    draft.pruned_evidence_count += len(draft.evidence) - len(evidence)
    succession = [item for item in draft.succession if item.tick >= retention]
    draft.pruned_succession_count += len(draft.succession) - len(succession)
    revisions = [item for item in draft.revisions if item.tick >= retention]
    draft.pruned_revision_count += len(draft.revisions) - len(revisions)
    drafts = draft
    appraisal = appraise_office_recognition(
        function_strength=drafts.function_strength,
        expectation_strength=drafts.expectation_strength,
        endorsement_strength=drafts.endorsement_strength,
        independent_root_count=len(drafts.role_roots),
        qualifying_evidence_count=len(drafts.evidence),
        policy=policy,
    )
    occupant_margin = _occupant_margin(tuple(drafts.occupants.values()))
    if drafts.abandoned:
        status = OfficeConceptStatus.ABANDONED
    elif (
        appraisal.recognized and len(drafts.occupants) > 1 and occupant_margin is False
    ):
        status = OfficeConceptStatus.DISPUTED
    elif appraisal.recognized:
        status = OfficeConceptStatus.RECOGNIZED
    elif drafts.occupants and occupant_margin is False:
        status = OfficeConceptStatus.DISPUTED
    elif (
        drafts.function_strength < policy.retire_strength
        and drafts.expectation_strength < policy.retire_strength
    ):
        status = OfficeConceptStatus.FADING
    else:
        status = OfficeConceptStatus.PROPOSED
    if not drafts.evidence:
        status = OfficeConceptStatus.PROPOSED
    if not appraisal.recognized and appraisal.reason in _NOTICE_REASONS:
        _notice(drafts.notices, appraisal.reason)
    return OfficeConcept(
        office_id=drafts.office_id,
        owner_id=owner_id,
        function=drafts.function,
        context_key=drafts.context_key,
        inception_digest=drafts.inception_digest,
        collision_discriminator=drafts.collision_discriminator,
        role_signature=drafts.role_signature,
        status=status,
        function_strength=drafts.function_strength,
        expectation_strength=drafts.expectation_strength,
        endorsement_strength=drafts.endorsement_strength,
        first_tick=evidence[0].tick if evidence else drafts.first_tick,
        last_tick=max(drafts.last_tick, tick),
        evidence_count=len(drafts.evidence),
        independent_root_count=len(drafts.role_roots),
        label_token=drafts.label_token,
        predecessor_office_id=drafts.predecessor_office_id,
        duties=tuple(sorted(drafts.duties.values(), key=lambda item: item.kind.value)),
        authorities=tuple(
            sorted(drafts.authorities.values(), key=lambda item: item.kind.value)
        ),
        occupants=tuple(
            sorted(drafts.occupants.values(), key=lambda item: item.occupant_id.value)
        ),
        supporters=tuple(drafts.supporters),
        succession=tuple(succession),
        revisions=tuple(revisions),
        evidence=tuple(evidence),
        last_utterance_tick=drafts.last_utterance_tick,
        pruned_evidence_count=drafts.pruned_evidence_count,
        pruned_succession_count=drafts.pruned_succession_count,
        pruned_revision_count=drafts.pruned_revision_count,
        notices=tuple(drafts.notices),
    )


def _occupant_margin(claims: Sequence[OfficeOccupantClaim]) -> bool | None:
    if not claims:
        return None
    ranked = sorted(
        claims,
        key=lambda claim: (
            -(claim.support_strength - claim.opposition_strength),
            claim.occupant_id.value,
        ),
    )
    if len(ranked) == 1:
        return ranked[0].status is not OfficeOccupantStatus.OPPOSED
    top = ranked[0].support_strength - ranked[0].opposition_strength
    second = ranked[1].support_strength - ranked[1].opposition_strength
    return abs(top - second) >= _PREFERENCE_MARGIN


_DEPARTURE_KINDS: Final[frozenset[str]] = frozenset(
    {"move", "journey_started", "journey_ended", "flee", "fled"}
)


def _process_availability(
    drafts: dict[tuple[OfficeFunction, str], _OfficeDraft],
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    tick: int,
    policy: OfficeConceptPolicy,
) -> None:
    """Apply observed death/departure/return to retained occupant claims.

    Absence alone never establishes vacancy; a departure reduces the belief
    that an occupant is available but does not prove relinquishment.
    """
    for draft in drafts.values():
        if draft.abandoned or not draft.occupants:
            continue
        for occurrence in observation.occurrences:
            actor = _actor_agent(identity, occurrence.actor_id)
            if actor is None or actor not in draft.occupants:
                continue
            if occurrence.kind == "died":
                _record_availability(
                    draft,
                    observation=observation,
                    actor=actor,
                    kind=OfficeSuccessionKind.OCCUPANT_LOST,
                    lineage=(
                        f"availability-died-{tick}-{occurrence.kind}-"
                        f"{occurrence.provenance.source_event_id}"
                    ),
                    policy=policy,
                )
            elif occurrence.kind in _DEPARTURE_KINDS:
                _record_availability(
                    draft,
                    observation=observation,
                    actor=actor,
                    kind=OfficeSuccessionKind.OCCUPANT_ABSENT,
                    lineage=(
                        f"availability-absent-{tick}-{occurrence.kind}-"
                        f"{occurrence.provenance.source_event_id}"
                    ),
                    policy=policy,
                )
        for body in observation.visible_bodies:
            actor = _actor_agent(identity, body.entity_id)
            if actor is None or actor not in draft.lost_occupants:
                continue
            _record_availability(
                draft,
                observation=observation,
                actor=actor,
                kind=OfficeSuccessionKind.OCCUPANT_RETURNED,
                lineage=f"availability-returned-{tick}-{body.entity_id.value}",
                policy=policy,
            )


def _record_availability(
    draft: _OfficeDraft,
    *,
    observation: Observation,
    actor: AgentId,
    kind: OfficeSuccessionKind,
    lineage: str,
    policy: OfficeConceptPolicy,
) -> None:
    signal = _OfficeSignal(
        predicate="office_function",
        function=draft.function,
        context_key=draft.context_key,
        lineage_ref=lineage,
        root_ref=f"observed|availability|{actor.value}",
        channel=OfficeEvidenceChannel.OBSERVED,
        actor_id=actor,
    )
    evidence = _record_evidence(
        draft, signal=signal, tick=observation.tick, policy=policy
    )
    if evidence is None:
        return
    if any(
        item.kind is kind
        and item.proposed_occupant_id == actor
        and item.tick == observation.tick
        for item in draft.succession
    ):
        return
    _append_succession(
        draft,
        kind=kind,
        tick=observation.tick,
        evidence_ids=(evidence.evidence_id,),
        policy=policy,
        prior_occupant_id=actor
        if kind is not OfficeSuccessionKind.OCCUPANT_RETURNED
        else None,
        proposed_occupant_id=actor,
    )
    if kind is OfficeSuccessionKind.OCCUPANT_LOST:
        draft.lost_occupants.add(actor)
    elif kind is OfficeSuccessionKind.OCCUPANT_RETURNED:
        draft.lost_occupants.discard(actor)


def _decay(
    drafts: dict[tuple[OfficeFunction, str], _OfficeDraft],
    tick: int,
    policy: OfficeConceptPolicy,
) -> None:
    for draft in drafts.values():
        if draft.touched:
            continue
        draft.last_tick = max(draft.last_tick, tick)
        draft.function_strength = _apply_delta(draft.function_strength, -policy.decay)
        draft.expectation_strength = _apply_delta(
            draft.expectation_strength, -policy.decay
        )
        draft.endorsement_strength = _apply_delta(
            draft.endorsement_strength, -policy.decay
        )


def apply_office_concept_update(
    observation: object,
    identity: object,
    previous: object = None,
    retrieved_memory_context: object = None,
    speaker_trust: Mapping[str, float] | None = None,
    policy: OfficeConceptPolicy | None = None,
    norms: object | None = None,
    conventions: object | None = None,
    institution_concepts: object | None = None,
) -> OfficeConceptLedger:
    """Apply one tick of owner-scoped office evidence.

    Evidence comes only from the owner's observation, owner-safe identity
    projection, the prepared ``RetrievedMemoryContext`` episode facts, and the
    previous office ledger. Influence-only recurrence produces a tentative
    proposal, never a recognized role.
    """
    for value in (
        observation,
        identity,
        previous,
        retrieved_memory_context,
        speaker_trust,
        policy,
        norms,
        conventions,
        institution_concepts,
    ):
        _reject_forbidden(value)
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    if previous is not None and type(previous) is not OfficeConceptLedger:
        raise TypeError("previous must be OfficeConceptLedger or None")
    active_policy = default_office_concept_policy() if policy is None else policy
    if type(active_policy) is not OfficeConceptPolicy:
        raise TypeError("policy must be OfficeConceptPolicy or None")
    owner_id = identity.owner_id
    if previous is not None and previous.owner_id != owner_id:
        _LOG.warning("office_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError("previous owner_id mismatch")
    trust = _normalize_trust(speaker_trust)
    context_key = _context_key(observation)
    drafts = _draft_map(owner_id, previous or empty_office_concept_ledger(owner_id))
    notices: list[str] = list(previous.notices) if previous is not None else []
    signals = _signals_from_observation(observation, identity, context_key)
    signals.extend(
        _signals_from_episodes(retrieved_memory_context, identity, context_key)
    )
    signals.extend(
        _signals_from_local_ledger(
            norms, owner_id=owner_id, channel="norm", fallback_context=context_key
        )
    )
    signals.extend(
        _signals_from_local_ledger(
            conventions,
            owner_id=owner_id,
            channel="convention",
            fallback_context=context_key,
        )
    )
    signals.extend(
        _signals_from_local_ledger(
            institution_concepts,
            owner_id=owner_id,
            channel="institution",
            fallback_context=context_key,
        )
    )
    for signal in signals:
        draft = _draft_for_key(
            owner_id=owner_id,
            drafts=drafts,
            function=signal.function,
            context_key=signal.context_key,
            lineage_ref=signal.lineage_ref,
            tick=observation.tick,
            notices=notices,
            policy=active_policy,
        )
        if draft is None:
            continue
        confidence = signal.confidence
        if signal.actor_id is not None:
            confidence *= trust.get(signal.actor_id.value, 1.0)
        if confidence <= 0.0:
            _notice(draft.notices, "unsupported_evidence")
            continue
        adjusted = _OfficeSignal(
            predicate=signal.predicate,
            function=signal.function,
            context_key=signal.context_key,
            lineage_ref=signal.lineage_ref,
            root_ref=signal.root_ref,
            channel=signal.channel,
            actor_id=signal.actor_id,
            occupant_id=signal.occupant_id,
            alleged_supporter_id=signal.alleged_supporter_id,
            duty_kind=signal.duty_kind,
            authority_kind=signal.authority_kind,
            confidence=confidence,
            independently_evidenced=signal.independently_evidenced,
            alleged_supporter_unresolved=signal.alleged_supporter_unresolved,
        )
        _apply_signal(draft, adjusted, observation.tick, active_policy)
    _process_availability(
        drafts, observation, identity, observation.tick, active_policy
    )
    _decay(drafts, observation.tick, active_policy)
    frozen = [
        _freeze_draft(draft, owner_id, observation.tick, active_policy)
        for draft in sorted(drafts.values(), key=lambda item: item.office_id)
        if draft.evidence
    ]
    if previous is not None:
        frozen.extend(concept for concept in previous.concepts if concept.abandoned)
    concepts = tuple(sorted(frozen, key=lambda item: item.office_id))
    ledger = OfficeConceptLedger(
        owner_id=owner_id,
        concepts=concepts,
        notices=tuple(notices),
        pruned_concept_count=(0 if previous is None else previous.pruned_concept_count),
    )
    _LOG.info(
        "office_concept_ledger_updated owner_id=%s office_count=%s recognized_count=%s",
        owner_id.value,
        len(ledger.concepts),
        ledger.recognized_count,
    )
    return ledger


def _normalize_trust(speaker_trust: Mapping[str, float] | None) -> dict[str, float]:
    if speaker_trust is None:
        return {}
    if not isinstance(speaker_trust, Mapping):
        raise TypeError("speaker_trust must be a mapping")
    normalized: dict[str, float] = {}
    for key, value in speaker_trust.items():
        if not isinstance(key, str) or not key:
            raise ValueError("speaker_trust key invalid")
        normalized[key] = _require_strength(f"speaker_trust.{key}", value)
    return normalized


# ---------------------------------------------------------------------------
# Structured role communication
# ---------------------------------------------------------------------------

_COMMUNICATION_PREDICATES: Final[dict[str, str]] = {
    "role": _OFFICE_PREDICATE,
    "duty": _OFFICE_DUTY_PREDICATE,
    "authority": _OFFICE_AUTHORITY_PREDICATE,
    "endorse": _OFFICE_ENDORSE_PREDICATE,
    "dispute": _OFFICE_DISPUTE_PREDICATE,
    "relinquish": _OFFICE_RELINQUISH_PREDICATE,
    "succession": _OFFICE_SUCCESSION_PREDICATE,
}


def _entity_for_agent(
    identity: OwnerSafeSocialIdentity, agent_id: AgentId
) -> EntityId | None:
    if agent_id == identity.owner_id:
        return identity.owner_entity_id
    for binding in identity.counterparts:
        if binding.agent_id == agent_id:
            return binding.entity_id
    return None


def _is_communication_command(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def _select_office_for_speech(
    ledger: OfficeConceptLedger,
    tick: int,
    policy: OfficeConceptPolicy,
) -> tuple[OfficeConcept, OfficeDutyKind | None, OfficeAuthorityKind | None] | None:
    for concept in sorted(ledger.concepts, key=lambda item: item.office_id):
        if not concept.recognized:
            continue
        if (
            concept.last_utterance_tick is not None
            and tick - concept.last_utterance_tick < policy.utterance_interval
        ):
            continue
        duty = max(
            concept.duties,
            key=lambda item: (item.strength, item.kind.value),
            default=None,
        )
        authority = max(
            concept.authorities,
            key=lambda item: (item.strength, item.kind.value),
            default=None,
        )
        return (
            concept,
            (None if duty is None else duty.kind),
            (None if authority is None else authority.kind),
        )
    return None


def office_communicate_utterance(
    command: object,
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    ledger: object | None,
    mode: object | None,
    policy: OfficeConceptPolicy | None = None,
) -> object:
    """Stamp an existing Talk/Tell with one owner-scoped role relation recipe.

    Only a recognized office may speak. The recipient forms fresh local
    evidence; no ledger row, occupant choice, or supporter count is copied.
    """
    from world.communications import (
        CommunicationRelation,
        CommunicationSourceBasis,
        origin_utterance,
    )

    if getattr(mode, "value", None) != "deterministic":
        return command
    if type(observation) is not Observation or observation.tick != tick:
        return command
    if not _is_communication_command(command):
        return command
    if type(ledger) is not OfficeConceptLedger or not ledger.concepts:
        return command
    if identity is None or ledger.owner_id != owner_id:
        return command
    active_policy = default_office_concept_policy() if policy is None else policy
    if type(active_policy) is not OfficeConceptPolicy:
        raise TypeError("policy must be OfficeConceptPolicy or None")
    selected = _select_office_for_speech(ledger, tick, active_policy)
    if selected is None:
        return command
    concept, duty_kind, authority_kind = selected
    preferred = concept.preferred_occupant
    preferred_entity = (
        None if preferred is None else _entity_for_agent(identity, preferred)
    )
    occupant_token = "-" if preferred_entity is None else preferred_entity.value
    relations = [
        CommunicationRelation(
            subject=concept.function.value,
            predicate=_OFFICE_PREDICATE,
            object=f"{concept.context_key}|{occupant_token}|-",
        )
    ]
    if duty_kind is not None:
        relations.append(
            CommunicationRelation(
                subject=concept.function.value,
                predicate=_OFFICE_DUTY_PREDICATE,
                object=f"{concept.context_key}|{duty_kind.value}|-",
            )
        )
    if authority_kind is not None:
        relations.append(
            CommunicationRelation(
                subject=concept.function.value,
                predicate=_OFFICE_AUTHORITY_PREDICATE,
                object=f"{concept.context_key}|{authority_kind.value}|-",
            )
        )
    if preferred is not None and any(item.resolved for item in concept.supporters):
        speaker_entity = identity.owner_entity_id
        relations.append(
            CommunicationRelation(
                subject=concept.function.value,
                predicate=_OFFICE_ENDORSE_PREDICATE,
                object=f"{concept.context_key}|{occupant_token}|{speaker_entity.value}",
            )
        )
    utterance = origin_utterance(
        text="office_role",
        speaker_id=identity.owner_entity_id,
        communication_id=f"office-{owner_id.value}-{tick}-{concept.office_id[:8]}",
        relations=tuple(relations),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    _LOG.debug(
        "office_response_selected owner_id=%s tick=%s office_id=%s relation_count=%s",
        owner_id.value,
        tick,
        concept.office_id[:8],
        len(relations),
    )
    typed_command = cast(Any, command)
    return typed_command.__class__(
        recipient_id=typed_command.recipient_id,
        utterance=utterance,
    )
