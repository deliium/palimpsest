"""Owner-scoped subjective concepts of persistent recurring patterns.

An institution concept is a private belief that some regularity keeps showing up:
the same actor keeps performing a function, a procedure repeats, an expectation
is held, a legitimacy belief is held, a function is resumed after a death, or a
practice spans generations. It is never an objective entity, never a world rule,
and never shared between owners. No predefined category (government, religion,
court, police, corporation, political party) exists anywhere.

Updates read one owner's ``Observation``, identity projection, previous
``InstitutionConceptLedger``, the owner's own norm/convention/group/possession
ledgers, and optional already-loaded memories. They never read ``WorldState``,
``WorldEvent``, another owner's ledger, or analysis documents.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any, Final, cast

from agents.cognition.models import OwnerSafeSocialIdentity
from agents.models import AgentId
from world.identifiers import EntityId, require_exact_nonneg_int
from world.observations import Observation, ObservedCommunication

__all__ = [
    "FORBIDDEN_INSTITUTION_CONCEPT_FIELD_NAMES",
    "INSTITUTION_CONCEPT_POLICY_VERSION",
    "InstitutionConcept",
    "InstitutionConceptEvidence",
    "InstitutionConceptLedger",
    "InstitutionConceptPolicy",
    "InstitutionConceptStatus",
    "InstitutionConceptualization",
    "InstitutionEvidenceChannel",
    "InstitutionPatternChannel",
    "apply_institution_concept_update",
    "default_institution_concept_policy",
    "empty_institution_concept_ledger",
    "institution_communicate_utterance",
    "institution_concept_id",
    "institution_evidence_id",
    "require_owner_institution_concepts",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.institution_concepts")

INSTITUTION_CONCEPT_POLICY_VERSION: Final[str] = "institution-concepts.v1"
_QUANTUM: Final[Decimal] = Decimal("0.000001")
_RECOGNITION_FLOOR: Final[float] = 0.45
_CHANNEL_FLOOR: Final[float] = 0.30
_RETIRE_STRENGTH: Final[float] = 0.12
_DECAY: Final[float] = 0.04
_PROMOTION_COUNT: Final[int] = 3
_PROMOTION_CHANNELS: Final[int] = 3
_UTTERANCE_INTERVAL: Final[int] = 4
_MAX_CONCEPTS: Final[int] = 16
_MAX_EVIDENCE: Final[int] = 32
_MAX_NOTICES: Final[int] = 16
_ROLE_DELTA: Final[float] = 0.14
_PROCEDURE_DELTA: Final[float] = 0.12
_EXPECTATION_DELTA: Final[float] = 0.10
_LEGITIMACY_DELTA: Final[float] = 0.12
_SUCCESSION_DELTA: Final[float] = 0.18
_CONTINUITY_DELTA: Final[float] = 0.10
_COMMUNICATED_DELTA: Final[float] = 0.10
_REMEMBERED_DELTA: Final[float] = 0.06

_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_DIGEST_LEN: Final[int] = 16
_PATTERN_PREDICATE: Final[str] = "institution_pattern"
_CUSTOM_PREDICATE: Final[str] = "custom"

_NOTICE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "cap_exceeded",
        "unresolved_entity",
        "unsupported_evidence",
        "duplicate_evidence",
        "foreign_owner",
        "invalid_token",
    }
)

_FORBIDDEN_TYPES: Final[frozenset[str]] = frozenset(
    {
        "MetricDocument",
        "MetricComputationInputs",
        "InstitutionCandidateRow",
        "InstitutionEmergenceResult",
        "InstitutionPersistenceRow",
    }
)

# Institutional vocabulary is rejected as a *field name* in the new modules.
# Pre-existing negative-assertion fields elsewhere are deliberately untouched.
FORBIDDEN_INSTITUTION_CONCEPT_FIELD_NAMES: Final[frozenset[str]] = frozenset(
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
        "office",
        "state",
    }
)

_FUNCTION_OCCURRENCES: Final[frozenset[str]] = frozenset(
    {
        "collective_project_contributed",
        "collective_project_started",
        "public_good_maintained",
        "public_good_contributed",
        "repository_member_deposited",
        "repository_member_retrieved",
        "repository_maintained",
        "repository_established",
        "teaching",
        "taught",
        "help",
        "helped",
    }
)

_SUCCESSION_OCCURRENCES: Final[frozenset[str]] = frozenset(
    {
        "repository_maintained",
        "public_good_maintained",
        "collective_project_contributed",
    }
)


class InstitutionPatternChannel(StrEnum):
    """Closed pattern-strength channels mirroring the analytical lanes."""

    ROLE_RECOGNITION = "role_recognition"
    PROCEDURE_RECURRENCE = "procedure_recurrence"
    SOCIAL_EXPECTATION = "social_expectation"
    LEGITIMACY_BELIEF = "legitimacy_belief"
    SUCCESSION_OBSERVED = "succession_observed"
    GENERATIONAL_CONTINUITY = "generational_continuity"


class InstitutionEvidenceChannel(StrEnum):
    """Closed evidence provenance for one concept item."""

    OBSERVED = "observed"
    COMMUNICATED = "communicated"
    REMEMBERED = "remembered"


class InstitutionConceptStatus(StrEnum):
    """Closed lifecycle for one owner's institution concept."""

    CANDIDATE = "candidate"
    RECOGNIZED = "recognized"
    FADING = "fading"
    RETIRED = "retired"


class InstitutionConceptualization(StrEnum):
    """Closed label treatment. ``NAMED_CUSTOM`` is self-contained evidence."""

    NONE = "none"
    NAMED_USUAL = "named_usual"
    NAMED_CUSTOM = "named_custom"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "institution_concept_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _sha256_hex(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


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
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    return number


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
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise _fail(field_name, "illegal_token")
    return value


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
        or module.startswith("analysis")
        or module.startswith("analysis.")
    ):
        raise TypeError(f"{name}: forbidden_input")


def _reject_forbidden_fields(model: type) -> None:
    names = {item.name for item in fields(model)}
    forbidden = names & FORBIDDEN_INSTITUTION_CONCEPT_FIELD_NAMES
    if forbidden:
        _LOG.error(
            "institution_concept_forbidden_field model=%s field_count=%s",
            model.__name__,
            len(forbidden),
        )
        raise ValueError(f"{model.__name__}: forbidden_field_name")


def _owner_digest(owner_id: AgentId) -> str:
    return _sha256_hex(f"owner|{owner_id.value}")


def _entity_digest(token: str) -> str:
    return _sha256_hex(f"entity|{token}")[:_DIGEST_LEN]


def _group_digest(material: str) -> str:
    return _sha256_hex(f"institution-group|{material}")


def institution_concept_id(owner_id: AgentId, anchor_digests: Sequence[str]) -> str:
    """Owner-scoped content-derived concept identity (RNG-free)."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    anchors = sorted(
        {
            _require_digest("anchor_digest", anchor)
            for anchor in _require_tuple("anchor_digests", anchor_digests)
        }
    )
    if not anchors:
        raise _fail("anchor_digests", "empty")
    return _sha256_hex(f"{owner_id.value}|institution-concept|" + "|".join(anchors))


def institution_evidence_id(
    concept_id: str,
    ordinal: int,
    channel: InstitutionEvidenceChannel,
    pattern: InstitutionPatternChannel,
    lineage_ref: str,
) -> str:
    head = _require_hex_id("concept_id", concept_id)
    if isinstance(ordinal, bool) or type(ordinal) is not int or ordinal < 0:
        raise _fail("ordinal", "invalid_type")
    if type(channel) is not InstitutionEvidenceChannel:
        raise _fail("channel", "unknown_channel")
    if type(pattern) is not InstitutionPatternChannel:
        raise _fail("pattern", "unknown_pattern")
    if not isinstance(lineage_ref, str) or not lineage_ref:
        raise _fail("lineage_ref", "invalid_type")
    return _sha256_hex(
        f"{head}|{ordinal}|{channel.value}|{pattern.value}|{lineage_ref}"
    )


def _channel_strength(
    channel: InstitutionPatternChannel, strengths: Mapping[str, float]
) -> float:
    return strengths.get(channel.value, 0.0)


@dataclass(frozen=True, slots=True)
class InstitutionConceptEvidence:
    """One bounded item of evidence for one concept channel."""

    evidence_id: str
    ordinal: int
    channel: InstitutionEvidenceChannel
    pattern: InstitutionPatternChannel
    lineage_ref: str
    tick: int
    anchor_digest: str
    actor_id: AgentId | None = None

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        object.__setattr__(
            self, "evidence_id", _require_hex_id("evidence_id", self.evidence_id)
        )
        if isinstance(self.ordinal, bool) or type(self.ordinal) is not int:
            raise _fail("evidence.ordinal", "invalid_type")
        if self.ordinal < 0:
            raise _fail("evidence.ordinal", "out_of_range")
        if type(self.channel) is not InstitutionEvidenceChannel:
            raise _fail("evidence.channel", "unknown_channel")
        if type(self.pattern) is not InstitutionPatternChannel:
            raise _fail("evidence.pattern", "unknown_pattern")
        if not isinstance(self.lineage_ref, str) or not self.lineage_ref:
            raise _fail("evidence.lineage_ref", "invalid_type")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("InstitutionConceptEvidence.tick", self.tick),
        )
        object.__setattr__(
            self,
            "anchor_digest",
            _require_digest("evidence.anchor_digest", self.anchor_digest),
        )
        if self.actor_id is not None and type(self.actor_id) is not AgentId:
            raise _fail("evidence.actor_id", "invalid_type")


@dataclass(frozen=True, slots=True)
class InstitutionConcept:
    """One owner's concept of a persistent recurring pattern.

    Six closed strength channels replace any institution-type label. The
    ``group_key`` is an opaque digest used only to merge evidence across ticks.
    """

    concept_id: str
    owner_id: AgentId
    group_key: str
    anchor_digests: tuple[str, ...]
    status: InstitutionConceptStatus
    conceptualization: InstitutionConceptualization
    role_recognition: float
    procedure_recurrence: float
    social_expectation: float
    legitimacy_belief: float
    succession_observed: float
    generational_continuity: float
    evidence_count: int
    first_tick: int
    last_tick: int
    label_token: str | None = None
    last_utterance_tick: int | None = None
    evidence: tuple[InstitutionConceptEvidence, ...] = ()
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        object.__setattr__(
            self, "group_key", _require_hex_id("group_key", self.group_key)
        )
        anchors = _require_tuple("anchor_digests", self.anchor_digests)
        checked_anchors: list[str] = []
        for anchor in anchors:
            head = _require_digest("anchor_digests", anchor)
            if head in checked_anchors:
                raise _fail("anchor_digests", "duplicate_anchor")
            checked_anchors.append(head)
        if not checked_anchors:
            raise _fail("anchor_digests", "empty")
        expected_id = institution_concept_id(self.owner_id, checked_anchors)
        object.__setattr__(
            self, "concept_id", _require_hex_id("concept_id", self.concept_id)
        )
        if self.concept_id != expected_id:
            raise _fail("concept_id", "id_mismatch")
        if type(self.status) is not InstitutionConceptStatus:
            raise _fail("status", "unknown_status")
        if type(self.conceptualization) is not InstitutionConceptualization:
            raise _fail("conceptualization", "unknown_conceptualization")
        strengths = (
            ("role_recognition", self.role_recognition),
            ("procedure_recurrence", self.procedure_recurrence),
            ("social_expectation", self.social_expectation),
            ("legitimacy_belief", self.legitimacy_belief),
            ("succession_observed", self.succession_observed),
            ("generational_continuity", self.generational_continuity),
        )
        for name, value in strengths:
            quantized = _quantize(_finite(name, value))
            if quantized < 0.0 or quantized > 1.0:
                raise _fail(name, "out_of_range")
            object.__setattr__(self, name, quantized)
        if self.label_token is not None:
            object.__setattr__(
                self, "label_token", _require_token("label_token", self.label_token)
            )
        if (
            self.conceptualization is InstitutionConceptualization.NAMED_CUSTOM
            and self.label_token is None
        ):
            raise _fail("label_token", "named_custom_requires_token")
        if (
            self.conceptualization is InstitutionConceptualization.NONE
            and self.label_token is not None
        ):
            raise _fail("label_token", "none_forbids_token")
        if (
            isinstance(self.evidence_count, bool)
            or type(self.evidence_count) is not int
        ):
            raise _fail("evidence_count", "invalid_type")
        if self.evidence_count < 0:
            raise _fail("evidence_count", "out_of_range")
        object.__setattr__(
            self,
            "first_tick",
            require_exact_nonneg_int("InstitutionConcept.first_tick", self.first_tick),
        )
        object.__setattr__(
            self,
            "last_tick",
            require_exact_nonneg_int("InstitutionConcept.last_tick", self.last_tick),
        )
        if self.last_tick < self.first_tick:
            raise _fail("last_tick", "before_first_tick")
        if self.last_utterance_tick is not None:
            object.__setattr__(
                self,
                "last_utterance_tick",
                require_exact_nonneg_int(
                    "InstitutionConcept.last_utterance_tick", self.last_utterance_tick
                ),
            )
        evidence = _require_tuple("evidence", self.evidence)
        checked_evidence: list[InstitutionConceptEvidence] = []
        seen: set[str] = set()
        previous_ordinal = -1
        previous_tick = -1
        for item in evidence:
            if type(item) is not InstitutionConceptEvidence:
                raise _fail("evidence", "invalid_type")
            if item.evidence_id in seen:
                raise _fail("evidence", "duplicate_evidence")
            if item.ordinal <= previous_ordinal:
                raise _fail("evidence.ordinal", "not_monotonic")
            if item.tick < previous_tick:
                raise _fail("evidence.tick", "not_monotonic")
            if item.anchor_digest not in checked_anchors:
                raise _fail("evidence.anchor_digest", "not_in_concept")
            seen.add(item.evidence_id)
            previous_ordinal = item.ordinal
            previous_tick = item.tick
            checked_evidence.append(item)
        if len(checked_evidence) > _MAX_EVIDENCE:
            raise _fail("evidence", "cap_exceeded")
        if checked_evidence and self.evidence_count < len(checked_evidence):
            raise _fail("evidence_count", "below_evidence")
        notices = _require_tuple("notices", self.notices)
        checked_notices: list[str] = []
        for item in notices:
            if not isinstance(item, str) or item not in _NOTICE_REASONS:
                raise _fail("notices", "invalid_notice")
            if item not in checked_notices:
                checked_notices.append(item)
        if len(checked_notices) > _MAX_NOTICES:
            raise _fail("notices", "cap_exceeded")
        object.__setattr__(self, "anchor_digests", tuple(checked_anchors))
        object.__setattr__(self, "evidence", tuple(checked_evidence))
        object.__setattr__(self, "notices", tuple(checked_notices))

    def strength_for(self, channel: InstitutionPatternChannel) -> float:
        if type(channel) is not InstitutionPatternChannel:
            raise _fail("channel", "unknown_channel")
        return float(getattr(self, channel.value))

    @property
    def recognized(self) -> bool:
        return self.status is InstitutionConceptStatus.RECOGNIZED

    @property
    def active_channels(self) -> tuple[InstitutionPatternChannel, ...]:
        return tuple(
            channel
            for channel in InstitutionPatternChannel
            if self.strength_for(channel) >= _CHANNEL_FLOOR
        )


@dataclass(frozen=True, slots=True)
class InstitutionConceptLedger:
    """Owner-scoped institution concepts. ``None`` means the mode is off."""

    owner_id: AgentId
    concepts: tuple[InstitutionConcept, ...] = ()
    notices: tuple[str, ...] = ()
    policy_version: str = INSTITUTION_CONCEPT_POLICY_VERSION

    def __post_init__(self) -> None:
        _reject_forbidden_fields(type(self))
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if self.policy_version != INSTITUTION_CONCEPT_POLICY_VERSION:
            raise _fail("policy_version", "unsupported_policy")
        concepts = _require_tuple("concepts", self.concepts)
        checked: list[InstitutionConcept] = []
        seen: set[str] = set()
        seen_groups: set[str] = set()
        for item in concepts:
            if type(item) is not InstitutionConcept:
                raise _fail("concepts", "invalid_type")
            if item.owner_id != self.owner_id:
                raise _fail("concepts.owner_id", "owner_mismatch")
            if item.concept_id in seen:
                raise _fail("concepts", "duplicate_concept")
            if item.group_key in seen_groups:
                raise _fail("concepts", "duplicate_group")
            seen.add(item.concept_id)
            seen_groups.add(item.group_key)
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
        object.__setattr__(self, "concepts", tuple(checked))
        object.__setattr__(self, "notices", tuple(checked_notices))
        _LOG.debug(
            "institution_concept_ledger_constructed owner_id=%s policy_version=%s "
            "concept_count=%s",
            self.owner_id.value,
            self.policy_version,
            len(self.concepts),
        )


@dataclass(frozen=True, slots=True)
class InstitutionConceptPolicy:
    """Locked institution-concept constants. Runner JSON does not carry these."""

    version: str = INSTITUTION_CONCEPT_POLICY_VERSION
    recognition_floor: float = _RECOGNITION_FLOOR
    channel_floor: float = _CHANNEL_FLOOR
    retire_strength: float = _RETIRE_STRENGTH
    decay: float = _DECAY
    promotion_count: int = _PROMOTION_COUNT
    promotion_channels: int = _PROMOTION_CHANNELS
    utterance_interval: int = _UTTERANCE_INTERVAL
    max_concepts: int = _MAX_CONCEPTS
    max_evidence: int = _MAX_EVIDENCE
    role_delta: float = _ROLE_DELTA
    procedure_delta: float = _PROCEDURE_DELTA
    expectation_delta: float = _EXPECTATION_DELTA
    legitimacy_delta: float = _LEGITIMACY_DELTA
    succession_delta: float = _SUCCESSION_DELTA
    continuity_delta: float = _CONTINUITY_DELTA
    communicated_delta: float = _COMMUNICATED_DELTA
    remembered_delta: float = _REMEMBERED_DELTA

    def __post_init__(self) -> None:
        if self.version != INSTITUTION_CONCEPT_POLICY_VERSION:
            raise _fail("version", "unsupported_policy")
        floats = (
            ("recognition_floor", _RECOGNITION_FLOOR),
            ("channel_floor", _CHANNEL_FLOOR),
            ("retire_strength", _RETIRE_STRENGTH),
            ("decay", _DECAY),
            ("role_delta", _ROLE_DELTA),
            ("procedure_delta", _PROCEDURE_DELTA),
            ("expectation_delta", _EXPECTATION_DELTA),
            ("legitimacy_delta", _LEGITIMACY_DELTA),
            ("succession_delta", _SUCCESSION_DELTA),
            ("continuity_delta", _CONTINUITY_DELTA),
            ("communicated_delta", _COMMUNICATED_DELTA),
            ("remembered_delta", _REMEMBERED_DELTA),
        )
        for name, expected in floats:
            object.__setattr__(
                self, name, _locked_float(name, getattr(self, name), expected)
            )
        counts = (
            ("promotion_count", _PROMOTION_COUNT),
            ("promotion_channels", _PROMOTION_CHANNELS),
            ("utterance_interval", _UTTERANCE_INTERVAL),
            ("max_concepts", _MAX_CONCEPTS),
            ("max_evidence", _MAX_EVIDENCE),
        )
        for name, expected in counts:
            object.__setattr__(
                self, name, _locked_int(name, getattr(self, name), expected)
            )


def default_institution_concept_policy() -> InstitutionConceptPolicy:
    """Return the only accepted institution-concept policy."""
    return InstitutionConceptPolicy()


def empty_institution_concept_ledger(owner_id: AgentId) -> InstitutionConceptLedger:
    """Ledger with no concepts. Disabled mode does not call this."""
    return InstitutionConceptLedger(owner_id=owner_id)


def require_owner_institution_concepts(
    ledger: object,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    """Reject a foreign or mistyped ledger. ``None`` is passthrough."""
    if ledger is None:
        return
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    if type(ledger) is not InstitutionConceptLedger:
        _LOG.warning("institution_concept_carry_rejected reason=%s", "invalid_type")
        raise TypeError(f"{field_name} must be InstitutionConceptLedger")
    if ledger.owner_id != owner_id:
        _LOG.error(
            "institution_concept_validation_failed field=%s reason_code=%s",
            field_name,
            "owner_mismatch",
        )
        _LOG.warning("institution_concept_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError(f"{field_name} owner_id mismatch")


class _ConceptDraft:
    """Mutable per-update accumulator. Never escapes this module."""

    __slots__ = (
        "anchors",
        "conceptualization",
        "evidence",
        "first_tick",
        "group_key",
        "label_token",
        "last_tick",
        "last_utterance_tick",
        "notices",
        "strengths",
        "touched",
    )

    def __init__(self, group_key: str, tick: int) -> None:
        self.group_key = group_key
        self.anchors: list[str] = []
        self.strengths: dict[str, float] = {
            channel.value: 0.0 for channel in InstitutionPatternChannel
        }
        self.evidence: list[InstitutionConceptEvidence] = []
        self.first_tick = tick
        self.last_tick = tick
        self.conceptualization = InstitutionConceptualization.NONE
        self.label_token: str | None = None
        self.last_utterance_tick: int | None = None
        self.notices: list[str] = []
        self.touched = False


def _notice(notices: list[str], reason: str) -> None:
    if reason not in notices:
        notices.append(reason)


def _drafts_from(
    owner_id: AgentId,
    previous: InstitutionConceptLedger | None,
    policy: InstitutionConceptPolicy,
) -> dict[str, _ConceptDraft]:
    drafts: dict[str, _ConceptDraft] = {}
    if previous is None:
        return drafts
    for concept in previous.concepts:
        draft = _ConceptDraft(concept.group_key, concept.first_tick)
        draft.anchors = list(concept.anchor_digests)
        for channel in InstitutionPatternChannel:
            draft.strengths[channel.value] = concept.strength_for(channel)
        draft.evidence = list(concept.evidence)
        draft.last_tick = concept.last_tick
        draft.conceptualization = concept.conceptualization
        draft.label_token = concept.label_token
        draft.last_utterance_tick = concept.last_utterance_tick
        drafts[concept.group_key] = draft
    return drafts


def _draft_for(
    drafts: dict[str, _ConceptDraft],
    group_key: str,
    tick: int,
    policy: InstitutionConceptPolicy,
    notices: list[str],
) -> _ConceptDraft | None:
    draft = drafts.get(group_key)
    if draft is not None:
        return draft
    if len(drafts) >= policy.max_concepts:
        _notice(notices, "cap_exceeded")
        return None
    draft = _ConceptDraft(group_key, tick)
    drafts[group_key] = draft
    return draft


def _record_evidence(
    draft: _ConceptDraft,
    owner_id: AgentId,
    channel: InstitutionPatternChannel,
    evidence_channel: InstitutionEvidenceChannel,
    lineage_ref: str,
    tick: int,
    anchor_digest: str,
    delta: float,
    policy: InstitutionConceptPolicy,
    actor_id: AgentId | None = None,
) -> bool:
    if len(draft.evidence) >= policy.max_evidence:
        _notice(draft.notices, "cap_exceeded")
        return False
    if anchor_digest not in draft.anchors:
        draft.anchors.append(anchor_digest)
    draft.strengths[channel.value] = _apply_delta(draft.strengths[channel.value], delta)
    ordinal = len(draft.evidence)
    concept_id = institution_concept_id(owner_id, draft.anchors)
    evidence = InstitutionConceptEvidence(
        evidence_id=institution_evidence_id(
            concept_id,
            ordinal,
            evidence_channel,
            channel,
            lineage_ref,
        ),
        ordinal=ordinal,
        channel=evidence_channel,
        pattern=channel,
        lineage_ref=lineage_ref,
        tick=tick,
        anchor_digest=anchor_digest,
        actor_id=actor_id,
    )
    draft.evidence.append(evidence)
    draft.last_tick = max(draft.last_tick, tick)
    draft.touched = True
    return True


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


def _seq_digest(material: str) -> str:
    return _sha256_hex(f"institution-sequence|{material}")[:_DIGEST_LEN]


def _observe_occurrences(
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: dict[str, _ConceptDraft],
    notices: list[str],
    policy: InstitutionConceptPolicy,
) -> None:
    location = (
        None if observation.self_body is None else observation.self_body.location_id
    )
    location_token = "none" if location is None else location.value
    day_phase = "none" if observation.day_phase is None else observation.day_phase.value
    sequence: list[str] = []
    for ordinal, occurrence in enumerate(observation.occurrences):
        kind = occurrence.kind
        sequence.append(kind)
        if kind not in _FUNCTION_OCCURRENCES:
            continue
        actor = _actor_agent(identity, occurrence.actor_id)
        if actor is None:
            if occurrence.actor_id is not None:
                _notice(notices, "unresolved_entity")
            continue
        anchor = _seq_digest(f"role|{kind}|{actor.value}")
        group_key = _group_digest(f"role|{kind}|{actor.value}")
        draft = _draft_for(drafts, group_key, observation.tick, policy, notices)
        if draft is None:
            continue
        lineage = f"occurrence-{observation.tick}-{ordinal}-{kind}"
        _record_evidence(
            draft,
            identity.owner_id,
            InstitutionPatternChannel.ROLE_RECOGNITION,
            InstitutionEvidenceChannel.OBSERVED,
            lineage,
            observation.tick,
            anchor,
            policy.role_delta,
            policy,
            actor,
        )
    if sequence:
        seq_digest = _seq_digest(f"{location_token}|{day_phase}|" + "|".join(sequence))
        anchor = _seq_digest(f"procedure|{seq_digest}|{location_token}|{day_phase}")
        group_key = _group_digest(
            f"procedure|{seq_digest}|{location_token}|{day_phase}"
        )
        draft = _draft_for(drafts, group_key, observation.tick, policy, notices)
        if draft is not None:
            _record_evidence(
                draft,
                identity.owner_id,
                InstitutionPatternChannel.PROCEDURE_RECURRENCE,
                InstitutionEvidenceChannel.OBSERVED,
                f"procedure-{observation.tick}-{seq_digest}",
                observation.tick,
                anchor,
                policy.procedure_delta,
                policy,
                None,
            )


def _observe_projects(
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: dict[str, _ConceptDraft],
    notices: list[str],
    policy: InstitutionConceptPolicy,
) -> None:
    for project_ordinal, project in enumerate(observation.collective_projects):
        for contribution_ordinal, contribution in enumerate(project.contributions):
            if not contribution.accepted:
                continue
            actor = _actor_agent(identity, contribution.actor_id)
            if actor is None:
                _notice(notices, "unresolved_entity")
                continue
            anchor = _seq_digest(f"project-role|{project.kind}|{actor.value}")
            group_key = _group_digest(f"project-role|{project.kind}|{actor.value}")
            draft = _draft_for(drafts, group_key, observation.tick, policy, notices)
            if draft is None:
                continue
            _record_evidence(
                draft,
                identity.owner_id,
                InstitutionPatternChannel.ROLE_RECOGNITION,
                InstitutionEvidenceChannel.OBSERVED,
                f"project-{project_ordinal}-{contribution_ordinal}-{contribution.tick}",
                observation.tick,
                anchor,
                policy.role_delta,
                policy,
                actor,
            )


def _observe_repositories(
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: dict[str, _ConceptDraft],
    notices: list[str],
    policy: InstitutionConceptPolicy,
) -> None:
    for ordinal, repository in enumerate(observation.repositories):
        founders = repository.founder_ids or ()
        for founder_ordinal, founder in enumerate(founders):
            actor = _actor_agent(identity, founder)
            if actor is None:
                _notice(notices, "unresolved_entity")
                continue
            anchor = _seq_digest(f"repository-role|{actor.value}")
            group_key = _group_digest(f"repository-role|{actor.value}")
            draft = _draft_for(drafts, group_key, observation.tick, policy, notices)
            if draft is None:
                continue
            _record_evidence(
                draft,
                identity.owner_id,
                InstitutionPatternChannel.ROLE_RECOGNITION,
                InstitutionEvidenceChannel.OBSERVED,
                f"repository-{ordinal}-{founder_ordinal}",
                observation.tick,
                anchor,
                policy.role_delta,
                policy,
                actor,
            )


def _social_draft(
    drafts: dict[str, _ConceptDraft],
    tick: int,
    policy: InstitutionConceptPolicy,
    notices: list[str],
) -> _ConceptDraft | None:
    """Attach expectation/legitimacy evidence to an existing regularity.

    Owners relate a norm-like expectation to a pattern they already notice. If
    no regularity exists yet, evidence forms its own owner-level concept. The
    choice is deterministic (lowest group key).
    """
    if drafts:
        key = min(drafts)
        return drafts[key]
    group_key = _group_digest("social|self")
    return _draft_for(drafts, group_key, tick, policy, notices)


def _observe_norms(
    owner_id: AgentId,
    norms: object | None,
    drafts: dict[str, _ConceptDraft],
    notices: list[str],
    policy: InstitutionConceptPolicy,
) -> None:
    if norms is None:
        return
    if getattr(norms, "owner_id", None) != owner_id:
        _notice(notices, "foreign_owner")
        return
    beliefs = getattr(norms, "beliefs", ())
    if not isinstance(beliefs, Sequence):
        return
    for belief in beliefs:
        status = getattr(belief, "status", None)
        if getattr(status, "value", None) not in {"active", "emerging", "candidate"}:
            continue
        belief_id = getattr(belief, "belief_id", None)
        if not isinstance(belief_id, str):
            continue
        anchor = _seq_digest(f"norm|{belief_id}")
        draft = _social_draft(drafts, 0, policy, notices)
        if draft is None:
            continue
        draft.first_tick = min(draft.first_tick, 0)
        _record_evidence(
            draft,
            owner_id,
            InstitutionPatternChannel.SOCIAL_EXPECTATION,
            InstitutionEvidenceChannel.REMEMBERED,
            f"norm-{belief_id}",
            max(draft.last_tick, 0),
            anchor,
            policy.expectation_delta,
            policy,
            None,
        )
        supporters = getattr(belief, "supporters", ())
        if isinstance(supporters, Sequence) and len(supporters) >= 2:
            _record_evidence(
                draft,
                owner_id,
                InstitutionPatternChannel.LEGITIMACY_BELIEF,
                InstitutionEvidenceChannel.REMEMBERED,
                f"norm-support-{belief_id}",
                max(draft.last_tick, 0),
                _seq_digest(f"norm-support|{belief_id}"),
                policy.legitimacy_delta,
                policy,
                None,
            )


def _observe_conventions(
    owner_id: AgentId,
    conventions: object | None,
    drafts: dict[str, _ConceptDraft],
    notices: list[str],
    policy: InstitutionConceptPolicy,
) -> None:
    if conventions is None:
        return
    if getattr(conventions, "owner_id", None) != owner_id:
        _notice(notices, "foreign_owner")
        return
    beliefs = getattr(conventions, "beliefs", ())
    if not isinstance(beliefs, Sequence):
        return
    for belief in beliefs:
        status = getattr(belief, "status", None)
        if getattr(status, "value", None) not in {"active", "candidate"}:
            continue
        belief_id = getattr(belief, "belief_id", None)
        if not isinstance(belief_id, str):
            continue
        anchor = _seq_digest(f"convention|{belief_id}")
        draft = _social_draft(drafts, 0, policy, notices)
        if draft is None:
            continue
        _record_evidence(
            draft,
            owner_id,
            InstitutionPatternChannel.SOCIAL_EXPECTATION,
            InstitutionEvidenceChannel.REMEMBERED,
            f"convention-{belief_id}",
            max(draft.last_tick, 0),
            anchor,
            policy.expectation_delta,
            policy,
            None,
        )


def _observe_groups(
    owner_id: AgentId,
    groups: object | None,
    drafts: dict[str, _ConceptDraft],
    notices: list[str],
    policy: InstitutionConceptPolicy,
) -> None:
    if groups is None:
        return
    if getattr(groups, "owner_id", None) != owner_id:
        _notice(notices, "foreign_owner")
        return
    beliefs = getattr(groups, "beliefs", ())
    if not isinstance(beliefs, Sequence):
        return
    for belief in beliefs:
        status = getattr(belief, "status", None)
        if getattr(status, "value", None) not in {"active", "candidate"}:
            continue
        belief_id = getattr(belief, "belief_id", None)
        if not isinstance(belief_id, str):
            continue
        anchor = _seq_digest(f"group|{belief_id}")
        draft = _social_draft(drafts, 0, policy, notices)
        if draft is None:
            continue
        _record_evidence(
            draft,
            owner_id,
            InstitutionPatternChannel.SOCIAL_EXPECTATION,
            InstitutionEvidenceChannel.REMEMBERED,
            f"group-{belief_id}",
            max(draft.last_tick, 0),
            anchor,
            policy.expectation_delta,
            policy,
            None,
        )


def _observe_possession(
    owner_id: AgentId,
    possession: object | None,
    drafts: dict[str, _ConceptDraft],
    notices: list[str],
    policy: InstitutionConceptPolicy,
) -> None:
    if possession is None:
        return
    if getattr(possession, "owner_id", None) != owner_id:
        _notice(notices, "foreign_owner")
        return
    supports = getattr(possession, "supports", ())
    if not isinstance(supports, Sequence):
        return
    for pair in supports:
        if not isinstance(pair, tuple) or len(pair) != 2:
            continue
        doctrine, count = pair
        if not isinstance(doctrine, str) or not isinstance(count, int):
            continue
        if count < 1:
            continue
        anchor = _seq_digest(f"legitimacy|{doctrine}")
        draft = _social_draft(drafts, 0, policy, notices)
        if draft is None:
            continue
        _record_evidence(
            draft,
            owner_id,
            InstitutionPatternChannel.LEGITIMACY_BELIEF,
            InstitutionEvidenceChannel.REMEMBERED,
            f"doctrine-{doctrine}-{count}",
            max(draft.last_tick, 0),
            anchor,
            policy.legitimacy_delta,
            policy,
            None,
        )


def _observe_memories(
    owner_id: AgentId,
    memories: Sequence[object],
    drafts: dict[str, _ConceptDraft],
    notices: list[str],
    policy: InstitutionConceptPolicy,
) -> None:
    for draft in drafts.values():
        if draft.touched:
            continue
        if not draft.evidence:
            continue
        _record_evidence(
            draft,
            owner_id,
            InstitutionPatternChannel.ROLE_RECOGNITION,
            InstitutionEvidenceChannel.REMEMBERED,
            f"remembered-{draft.group_key[:16]}-{draft.last_tick}",
            draft.last_tick,
            draft.anchors[0],
            policy.remembered_delta,
            policy,
            None,
        )


def _observe_transmission(
    observation: Observation,
    identity: OwnerSafeSocialIdentity,
    drafts: dict[str, _ConceptDraft],
    notices: list[str],
    policy: InstitutionConceptPolicy,
) -> None:
    for ordinal, communication in enumerate(observation.communications):
        if type(communication) is not ObservedCommunication:
            continue
        if communication.listener_id != identity.owner_entity_id:
            continue
        if communication.action_kind not in {"talk", "ask", "tell"}:
            continue
        for relation in communication.utterance.content.relations:
            if relation.predicate == _CUSTOM_PREDICATE:
                _apply_custom_label(
                    identity,
                    drafts,
                    notices,
                    policy,
                    relation.subject,
                    relation.object,
                    observation.tick,
                    ordinal,
                )
                continue
            if relation.predicate != _PATTERN_PREDICATE:
                continue
            try:
                channel = InstitutionPatternChannel(relation.subject)
            except ValueError:
                _notice(notices, "unsupported_evidence")
                continue
            object_token = relation.object
            if not isinstance(object_token, str) or not object_token:
                continue
            anchor = _seq_digest(f"communicated|{channel.value}|{object_token}")
            group_key = _group_digest(f"communicated|{channel.value}|{object_token}")
            draft = _draft_for(drafts, group_key, observation.tick, policy, notices)
            if draft is None:
                continue
            _record_evidence(
                draft,
                identity.owner_id,
                channel,
                InstitutionEvidenceChannel.COMMUNICATED,
                f"communication-{observation.tick}-{ordinal}-{channel.value}",
                observation.tick,
                anchor,
                policy.communicated_delta,
                policy,
                None,
            )


def _apply_custom_label(
    identity: OwnerSafeSocialIdentity,
    drafts: dict[str, _ConceptDraft],
    notices: list[str],
    policy: InstitutionConceptPolicy,
    subject: object,
    token: object,
    tick: int,
    ordinal: int,
) -> None:
    """Attach an opaque custom label carried by a self-contained transmission.

    The label never identifies an institution type; it is a private token the
    receiver may adopt alongside its own independently formed evidence.
    """
    if not isinstance(subject, str):
        _notice(notices, "unsupported_evidence")
        return
    try:
        channel = InstitutionPatternChannel(subject)
    except ValueError:
        _notice(notices, "unsupported_evidence")
        return
    if not isinstance(token, str) or "|" not in token:
        _notice(notices, "unsupported_evidence")
        return
    group_material, _, label_material = token.partition("|")
    if not group_material or not label_material:
        _notice(notices, "unsupported_evidence")
        return
    try:
        label_token = _require_token("label_token", label_material)
    except ValueError:
        _notice(notices, "invalid_token")
        return
    group_key = _group_digest(f"communicated|{channel.value}|{group_material}")
    draft = drafts.get(group_key)
    if draft is None:
        _notice(notices, "unsupported_evidence")
        return
    strongest = max(
        InstitutionPatternChannel,
        key=lambda item: (draft.strengths[item.value], item.value),
    )
    if not _record_evidence(
        draft,
        identity.owner_id,
        strongest,
        InstitutionEvidenceChannel.COMMUNICATED,
        f"custom-{tick}-{ordinal}-{label_token}",
        tick,
        _seq_digest(f"custom|{group_key}|{label_token}"),
        policy.communicated_delta,
        policy,
        None,
    ):
        return
    draft.conceptualization = InstitutionConceptualization.NAMED_CUSTOM
    draft.label_token = label_token
    _LOG.debug(
        "institution_custom_label_applied owner_id=%s tick=%s channel=%s",
        identity.owner_id.value,
        tick,
        channel.value,
    )


def _decay(
    drafts: dict[str, _ConceptDraft],
    tick: int,
    policy: InstitutionConceptPolicy,
) -> None:
    for draft in drafts.values():
        if draft.touched:
            continue
        draft.last_tick = max(draft.last_tick, tick)
        for channel in InstitutionPatternChannel:
            draft.strengths[channel.value] = _apply_delta(
                draft.strengths[channel.value], -policy.decay
            )


def _freeze(
    draft: _ConceptDraft,
    owner_id: AgentId,
    policy: InstitutionConceptPolicy,
) -> InstitutionConcept | None:
    if not draft.anchors:
        return None
    channel_count = sum(
        1
        for channel in InstitutionPatternChannel
        if draft.strengths[channel.value] >= policy.channel_floor
    )
    highest = max(draft.strengths.values())
    if (
        len(draft.evidence) >= policy.promotion_count
        and channel_count >= policy.promotion_channels
        and highest >= policy.recognition_floor
    ):
        status = InstitutionConceptStatus.RECOGNIZED
    elif highest < policy.retire_strength:
        status = InstitutionConceptStatus.RETIRED
    elif highest < policy.recognition_floor:
        status = InstitutionConceptStatus.CANDIDATE
    else:
        status = InstitutionConceptStatus.FADING
    concept_id = institution_concept_id(owner_id, draft.anchors)
    return InstitutionConcept(
        concept_id=concept_id,
        owner_id=owner_id,
        group_key=draft.group_key,
        anchor_digests=tuple(draft.anchors),
        status=status,
        conceptualization=draft.conceptualization,
        role_recognition=draft.strengths[
            InstitutionPatternChannel.ROLE_RECOGNITION.value
        ],
        procedure_recurrence=draft.strengths[
            InstitutionPatternChannel.PROCEDURE_RECURRENCE.value
        ],
        social_expectation=draft.strengths[
            InstitutionPatternChannel.SOCIAL_EXPECTATION.value
        ],
        legitimacy_belief=draft.strengths[
            InstitutionPatternChannel.LEGITIMACY_BELIEF.value
        ],
        succession_observed=draft.strengths[
            InstitutionPatternChannel.SUCCESSION_OBSERVED.value
        ],
        generational_continuity=draft.strengths[
            InstitutionPatternChannel.GENERATIONAL_CONTINUITY.value
        ],
        evidence_count=len(draft.evidence),
        first_tick=draft.first_tick,
        last_tick=draft.last_tick,
        label_token=draft.label_token,
        last_utterance_tick=draft.last_utterance_tick,
        evidence=tuple(draft.evidence),
        notices=tuple(draft.notices),
    )


def apply_institution_concept_update(
    observation: object,
    identity: object,
    previous: object = None,
    norms: object | None = None,
    conventions: object | None = None,
    groups: object | None = None,
    possession: object | None = None,
    memories: Sequence[object] = (),
    advice_delta: Sequence[object] = (),
    mentorship: object | None = None,
    policy: InstitutionConceptPolicy | None = None,
) -> InstitutionConceptLedger | None:
    """Apply one tick of owner-scoped institution-concept evidence.

    Disabled callers do not call this function. Evidence is drawn only from the
    owner's observation, identity projection, previous ledger, and the owner's
    own norm/convention/group/possession ledgers. No institution type is ever
    inferred or stored.
    """
    _LOG.debug(
        "apply_institution_concept_update owner_id=%s tick=%s",
        getattr(getattr(identity, "owner_id", None), "value", None),
        getattr(observation, "tick", None),
    )
    for value in (
        observation,
        identity,
        previous,
        norms,
        conventions,
        groups,
        possession,
        memories,
        advice_delta,
        mentorship,
        policy,
    ):
        _reject_forbidden(value)
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(identity) is not OwnerSafeSocialIdentity:
        raise TypeError("identity must be OwnerSafeSocialIdentity")
    if previous is not None and type(previous) is not InstitutionConceptLedger:
        raise TypeError("previous must be InstitutionConceptLedger or None")
    active_policy = default_institution_concept_policy() if policy is None else policy
    if type(active_policy) is not InstitutionConceptPolicy:
        raise TypeError("policy must be InstitutionConceptPolicy or None")
    owner_id = identity.owner_id
    if previous is not None and previous.owner_id != owner_id:
        _LOG.warning("institution_concept_carry_rejected reason=%s", "owner_mismatch")
        raise ValueError("previous owner_id mismatch")
    drafts = _drafts_from(owner_id, previous, active_policy)
    notices: list[str] = []
    _observe_occurrences(observation, identity, drafts, notices, active_policy)
    _observe_projects(observation, identity, drafts, notices, active_policy)
    _observe_repositories(observation, identity, drafts, notices, active_policy)
    _observe_norms(owner_id, norms, drafts, notices, active_policy)
    _observe_conventions(owner_id, conventions, drafts, notices, active_policy)
    _observe_groups(owner_id, groups, drafts, notices, active_policy)
    _observe_possession(owner_id, possession, drafts, notices, active_policy)
    _observe_transmission(observation, identity, drafts, notices, active_policy)
    _observe_memories(owner_id, memories, drafts, notices, active_policy)
    _decay(drafts, observation.tick, active_policy)
    concepts: list[InstitutionConcept] = []
    for draft in drafts.values():
        concept = _freeze(draft, owner_id, active_policy)
        if concept is not None:
            concepts.append(concept)
    ledger = InstitutionConceptLedger(
        owner_id=owner_id,
        concepts=tuple(concepts),
        notices=tuple(notices),
    )
    recognized = sum(1 for concept in ledger.concepts if concept.recognized)
    _LOG.info(
        "institution_concept_ledger_updated owner_id=%s concept_count=%s "
        "recognized_count=%s",
        owner_id.value,
        len(ledger.concepts),
        recognized,
    )
    return ledger


def _is_communication_command(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def institution_communicate_utterance(
    command: object,
    *,
    owner_id: AgentId,
    tick: int,
    observation: Observation,
    identity: OwnerSafeSocialIdentity | None,
    ledger: object | None,
    mode: object | None,
    policy: InstitutionConceptPolicy | None = None,
) -> object:
    """Stamp an existing Talk/Tell with one opaque pattern relation recipe.

    Only one recognized concept's strongest active channel is shared. The
    recipient forms its own independent evidence; no ledger row is copied.
    """
    from agents.cognition.configuration import CognitionInstitutionConceptMode
    from world.communications import (
        CommunicationRelation,
        CommunicationSourceBasis,
        origin_utterance,
    )

    if mode is not CognitionInstitutionConceptMode.DETERMINISTIC:
        return command
    if type(observation) is not Observation or observation.tick != tick:
        return command
    if not _is_communication_command(command):
        return command
    if type(ledger) is not InstitutionConceptLedger or not ledger.concepts:
        return command
    if identity is None or ledger.owner_id != owner_id:
        return command
    active_policy = default_institution_concept_policy() if policy is None else policy
    chosen: InstitutionConcept | None = None
    chosen_channel: InstitutionPatternChannel | None = None
    for concept in sorted(ledger.concepts, key=lambda item: item.concept_id):
        if concept.status is not InstitutionConceptStatus.RECOGNIZED:
            continue
        if (
            concept.last_utterance_tick is not None
            and tick - concept.last_utterance_tick < active_policy.utterance_interval
        ):
            continue
        strongest = max(
            InstitutionPatternChannel,
            key=lambda channel: (concept.strength_for(channel), channel.value),
        )
        if concept.strength_for(strongest) < active_policy.channel_floor:
            continue
        chosen = concept
        chosen_channel = strongest
        break
    if chosen is None or chosen_channel is None:
        return command
    relations = [
        CommunicationRelation(
            subject=chosen_channel.value,
            predicate=_PATTERN_PREDICATE,
            object=chosen.group_key,
        )
    ]
    if (
        chosen.conceptualization is InstitutionConceptualization.NAMED_CUSTOM
        and chosen.label_token is not None
    ):
        relations.append(
            CommunicationRelation(
                subject=chosen_channel.value,
                predicate=_CUSTOM_PREDICATE,
                object=f"{chosen.group_key}|{chosen.label_token}",
            )
        )
    utterance = origin_utterance(
        text=_PATTERN_PREDICATE,
        speaker_id=identity.owner_entity_id,
        communication_id=(
            f"institution-concept-{owner_id.value}-{tick}-{chosen_channel.value}"
        ),
        relations=tuple(relations),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    _LOG.debug(
        "institution_concept_response_selected owner_id=%s tick=%s channel=%s",
        owner_id.value,
        tick,
        chosen_channel.value,
    )
    return cast(Any, command).__class__(
        recipient_id=cast(Any, command).recipient_id,
        utterance=utterance,
    )
